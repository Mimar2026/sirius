"""
Sirius QUALITY - Quality Momentum (ABD)

Momentum + ROE + Brut Marj + Kar Buyumesi. Performans takipli.
"""

import os
import time
import traceback
import yfinance as yf
import pandas as pd

from momentum_system import (
    telegram_gonder,
    telegram_hata_gonder,
    retry,
    hisse_evrenini_cek,
    fiyat_verisi_cek,
    aylik_fiyatlara_donustur,
    momentum_skoru_hesapla,
)

from sirius_helpers import (
    telegram_mesaji_detayli,
    PORTFOY_ABD,
    POZISYON_YUZDE_ABD,
    AY_ISIMLERI,
)

from performans_tracker import (
    gecmis_oku,
    gecmis_kaydet,
    onceki_portfoy_performans_hesapla,
    kumulatif_performans_hesapla,
    yeni_kayit_olustur,
)


SISTEM_KODU = "quality"


def fundamental_veri_cek(semboller):
    fundamentals = {}
    for sembol in semboller:
        try:
            info = yf.Ticker(sembol).info
            
            roe = info.get("returnOnEquity")
            brut_marj = info.get("grossMargins")
            kar_buyumesi = info.get("earningsGrowth")
            piyasa_degeri = info.get("marketCap")
            sektor = info.get("sector", "Unknown")
            
            fundamentals[sembol] = {
                "ROE": roe * 100 if roe is not None else None,
                "BrutMarj": brut_marj * 100 if brut_marj is not None else None,
                "KarBuyumesi": kar_buyumesi * 100 if kar_buyumesi is not None else None,
                "PiyasaDegeri_Mr": piyasa_degeri / 1_000_000_000 if piyasa_degeri else None,
                "Sektor": sektor
            }
            time.sleep(0.1)
        except Exception:
            fundamentals[sembol] = {
                "ROE": None, "BrutMarj": None, "KarBuyumesi": None,
                "PiyasaDegeri_Mr": None, "Sektor": "Unknown"
            }
    
    return fundamentals


def quality_skoru_hesapla(skor_df, fundamentals):
    fundamental_list = []
    for _, row in skor_df.iterrows():
        sembol = row["Sembol"]
        f = fundamentals.get(sembol, {})
        fundamental_list.append({
            "Sembol": sembol,
            "ROE": f.get("ROE"),
            "BrutMarj": f.get("BrutMarj"),
            "KarBuyumesi": f.get("KarBuyumesi"),
            "PiyasaDegeri_Mr": f.get("PiyasaDegeri_Mr"),
            "Sektor": f.get("Sektor", "Unknown")
        })
    
    fund_df = pd.DataFrame(fundamental_list)
    combined = skor_df.merge(fund_df, on="Sembol", how="left")
    
    quality_filter = (
        combined["ROE"].notna() & 
        combined["BrutMarj"].notna() &
        (combined["PiyasaDegeri_Mr"] >= 2)
    )
    
    quality_eligible = combined[quality_filter].copy()
    
    if len(quality_eligible) < 10:
        print("  UYARI: Quality filtreden gecen hisse az (" + str(len(quality_eligible)) + ")")
        return combined.sort_values("Momentum", ascending=False)
    
    quality_eligible["ROE_Rank"] = quality_eligible["ROE"].rank(pct=True) * 100
    quality_eligible["Marj_Rank"] = quality_eligible["BrutMarj"].rank(pct=True) * 100
    
    if quality_eligible["KarBuyumesi"].notna().sum() >= 5:
        quality_eligible["Buyume_Rank"] = quality_eligible["KarBuyumesi"].rank(pct=True) * 100
        quality_eligible["Quality"] = (
            quality_eligible["ROE_Rank"] + 
            quality_eligible["Marj_Rank"] + 
            quality_eligible["Buyume_Rank"]
        ) / 3
    else:
        quality_eligible["Quality"] = (
            quality_eligible["ROE_Rank"] + 
            quality_eligible["Marj_Rank"]
        ) / 2
    
    quality_eligible["Final"] = (
        quality_eligible["Momentum"] * 0.6 + 
        quality_eligible["Quality"] * 0.4
    )
    
    return quality_eligible.sort_values("Final", ascending=False)


def quality_ek_bilgi_olustur(top10):
    ek = "<b>💎 Quality Metrikleri:</b>\n"
    
    if "ROE" in top10.columns:
        ort_roe = top10["ROE"].dropna().mean()
        if not pd.isna(ort_roe):
            ek += f"   • Ortalama ROE: {ort_roe:+.1f}%\n"
    
    if "BrutMarj" in top10.columns:
        ort_marj = top10["BrutMarj"].dropna().mean()
        if not pd.isna(ort_marj):
            ek += f"   • Ortalama brüt marj: {ort_marj:.1f}%\n"
    
    if "Quality" in top10.columns:
        ort_quality = top10["Quality"].dropna().mean()
        if not pd.isna(ort_quality):
            ek += f"   • Ortalama Quality: {ort_quality:.1f}/100\n"
    
    if "Final" in top10.columns:
        ort_final = top10["Final"].dropna().mean()
        if not pd.isna(ort_final):
            ek += f"   • Ortalama Final: {ort_final:.1f}/100"
    
    return ek


def main():
    print("=" * 70)
    print("SIRIUS QUALITY - Performans Takipli")
    print("=" * 70)
    
    try:
        # Gecmisi oku
        print("\n[0/6] Gecmis okunuyor...")
        gecmis = gecmis_oku(SISTEM_KODU, portfoy_baslangic=PORTFOY_ABD, para_birimi="$")
        print(f"  {len(gecmis['kayitlar'])} onceki kayit var")
        
        # Adim 1: Hisse evreni
        print("\n[1/6] Hisse evreni cekiliyor...")
        semboller = retry(hisse_evrenini_cek, max_deneme=3, bekleme=10, adim_adi="Hisse evreni")
        print("  " + str(len(semboller)) + " hisse")
        
        # Adim 2: Fiyat verisi
        print("\n[2/6] Fiyat verisi cekiliyor...")
        fiyatlar = retry(lambda: fiyat_verisi_cek(semboller), max_deneme=3, bekleme=15, adim_adi="Fiyat verisi")
        aylik = aylik_fiyatlara_donustur(fiyatlar)
        print("  " + str(aylik.shape[1]) + " hisse / " + str(aylik.shape[0]) + " ay")
        
        # Adim 3: Onceki portfoyun performansi
        print("\n[3/6] Onceki portfoyun performansi hesaplaniyor...")
        if gecmis["kayitlar"]:
            onceki_kayit = gecmis["kayitlar"][-1]
            
            guncel_fiyatlar = {}
            for hisse in onceki_kayit.get("hisseler", []):
                sembol = hisse["sembol"]
                if sembol in aylik.columns:
                    son_fiyat = aylik[sembol].iloc[-1]
                    if pd.notna(son_fiyat):
                        guncel_fiyatlar[sembol] = float(son_fiyat)
            
            performans = onceki_portfoy_performans_hesapla(onceki_kayit, guncel_fiyatlar)
            if performans:
                onceki_kayit["onceki_ay_performans"] = performans
                print(f"  Onceki ay getirisi: {performans['aylik_getiri_pct']:+.2f}%")
        else:
            print("  Henuz onceki kayit yok.")
        
        kumulatif = kumulatif_performans_hesapla(gecmis)
        
        # Adim 4: Momentum hesapla (top 50)
        print("\n[4/6] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top50 = skor.head(50)
        
        # Adim 5: Fundamental veriler + Quality skor
        print("\n[5/6] Fundamental veri cekiliyor...")
        fundamentals = fundamental_veri_cek(top50["Sembol"].tolist())
        
        ranked = quality_skoru_hesapla(top50, fundamentals)
        top10 = ranked.head(10)
        
        print("\n" + "=" * 70)
        print("QUALITY TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        
        gosterim_kolonlari = ["Sembol", "Momentum"]
        if "Quality" in top10.columns:
            gosterim_kolonlari.append("Quality")
        if "Final" in top10.columns:
            gosterim_kolonlari.append("Final")
        if "ROE" in top10.columns:
            gosterim_kolonlari.append("ROE")
        if "BrutMarj" in top10.columns:
            gosterim_kolonlari.append("BrutMarj")
        if "Sektor" in top10.columns:
            gosterim_kolonlari.append("Sektor")
        
        print(top10[gosterim_kolonlari].round(2).to_string(index=False))
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
        # Sektor dict
        sektor_dict = {}
        if "Sektor" in top10.columns:
            for _, row in top10.iterrows():
                sektor_dict[row["Sembol"]] = row.get("Sektor", "Unknown")
        
        # Ek bilgi
        ek_bilgi = quality_ek_bilgi_olustur(top10)
        
        # Yeni kayit
        guncel_portfoy_buyuklugu = kumulatif.get("portfoy_guncel", PORTFOY_ABD)
        
        kapanis_dict = {}
        for sembol in top10["Sembol"]:
            if sembol in aylik.columns:
                kapanis_dict[sembol] = float(aylik[sembol].iloc[-1])
        
        veri_tarih = aylik.index[-1]
        if veri_tarih.month == 12:
            sonraki_ay_adi = f"Ocak {veri_tarih.year + 1}"
        else:
            sonraki_ay_adi = f"{AY_ISIMLERI[veri_tarih.month + 1]} {veri_tarih.year}"
        
        yeni_kayit = yeni_kayit_olustur(
            top10, kapanis_dict, veri_tarih, sonraki_ay_adi,
            guncel_portfoy_buyuklugu, POZISYON_YUZDE_ABD
        )
        
        gecmis["kayitlar"].append(yeni_kayit)
        gecmis_kaydet(SISTEM_KODU, gecmis)
        print(f"  Gecmise kaydedildi: gecmis/{SISTEM_KODU}.json")
        
        # Adim 6: Telegram
        print("\n[6/6] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_detayli(
            top_n_df=top10,
            tarih=aylik.index[-1],
            sistem_adi="QUALITY",
            sistem_emoji="💎",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="$",
            portfoy_buyuklugu=PORTFOY_ABD,
            pozisyon_yuzde=POZISYON_YUZDE_ABD,
            para_format=",.2f",
            sektor_dict=sektor_dict if sektor_dict else None,
            ek_bilgi=ek_bilgi,
            performans_bilgisi=kumulatif,
            gecmis_veri=gecmis
        )
        
        telegram_basarili = telegram_gonder(telegram_mesaji)
        
        if not telegram_basarili:
            raise Exception("Telegram mesaji gonderilemedi")
        
        print("\n" + "=" * 70)
        print("Tamamlandi.")
        print("=" * 70)
    
    except Exception as e:
        hata_detayi = traceback.format_exc()
        print("\n" + "!" * 70)
        print("HATA OLUSTU!")
        print("!" * 70)
        print(hata_detayi)
        
        try:
            telegram_hata_gonder("Sirius QUALITY", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
