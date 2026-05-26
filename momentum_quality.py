"""
Sirius QUALITY - Quality Momentum (ABD)

Momentum + Quality faktorlerin birlestirildigi versiyon.
ROE, Brut Marj, Kar Buyumesi filtresi.

Sirius: A signal arrives before the rise.
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
)


def fundamental_veri_cek(semboller):
    """yfinance'ten fundamental veri ceker."""
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
    """Momentum + Quality kompozit skoru hesaplar."""
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
    """Quality'ye ozel ek istatistikleri olusturur (mesaj sonuna eklenir)."""
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
            ek += f"   • Ortalama Quality skoru: {ort_quality:.1f}/100\n"
    
    if "Final" in top10.columns:
        ort_final = top10["Final"].dropna().mean()
        if not pd.isna(ort_final):
            ek += f"   • Ortalama Final skor: {ort_final:.1f}/100"
    
    return ek


def main():
    print("=" * 70)
    print("SIRIUS QUALITY - QUALITY MOMENTUM")
    print("A signal arrives before the rise.")
    print("=" * 70)
    
    try:
        # Adim 1: Hisse evreni
        print("\n[1/5] Hisse evreni cekiliyor...")
        semboller = retry(
            hisse_evrenini_cek,
            max_deneme=3,
            bekleme=10,
            adim_adi="Hisse evreni cekme"
        )
        print("  " + str(len(semboller)) + " hisse")
        
        # Adim 2: Fiyat verisi
        print("\n[2/5] Fiyat verisi cekiliyor (1-2 dakika)...")
        fiyatlar = retry(
            lambda: fiyat_verisi_cek(semboller),
            max_deneme=3,
            bekleme=15,
            adim_adi="Fiyat verisi cekme"
        )
        aylik = aylik_fiyatlara_donustur(fiyatlar)
        print("  " + str(aylik.shape[1]) + " hisse / " + str(aylik.shape[0]) + " ay")
        
        # Adim 3: Momentum hesapla (top 50)
        print("\n[3/5] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top50 = skor.head(50)
        
        # Adim 4: Fundamental veriler
        print("\n[4/5] Fundamental veri cekiliyor (~1 dakika)...")
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
        
        # Sektor dict (mesaja eklemek icin)
        sektor_dict = {}
        if "Sektor" in top10.columns:
            for _, row in top10.iterrows():
                sektor_dict[row["Sembol"]] = row.get("Sektor", "Unknown")
        
        # Ek bilgi (Quality metrikleri)
        ek_bilgi = quality_ek_bilgi_olustur(top10)
        
        # Adim 5: Telegram - detayli mesaj
        print("\n[5/5] Telegram bildirimi gonderiliyor...")
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
            ek_bilgi=ek_bilgi
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
            telegram_hata_gonder("Sirius QUALITY Aylik Calistirma", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
