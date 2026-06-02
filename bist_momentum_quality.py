"""
Sirius BIST QUALITY - Quality Momentum (BIST)

Y\u00f6neticinin sistemine daha yak\u0131n: momentum + quality filtreler.

Quality faktorleri:
- Likidite (ortalama hacim)
- Trend tutarliligi (pozitif ay sayisi)
- Volatilite stabilitesi
- Drawdown direnci
- Asiri yukselis cezasi (parabolik move'lara)

Top 5, esit agirlik (%20).
"""

import os
import time
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from bist_hisseler import BIST_KATILIM
from bist_data import coklu_fiyat_cek, aylik_fiyatlara_donustur, fiyat_cek
from momentum_system import (
    telegram_gonder,
    telegram_hata_gonder,
    retry,
    momentum_skoru_hesapla,
)

from sirius_helpers import (
    telegram_mesaji_detayli,
    PORTFOY_BIST,
    POZISYON_YUZDE_BIST,
    AY_ISIMLERI,
)

from performans_tracker import (
    gecmis_oku,
    gecmis_kaydet,
    onceki_portfoy_performans_hesapla,
    kumulatif_performans_hesapla,
    yeni_kayit_olustur,
)


SISTEM_KODU = "bist_quality"


def quality_metrikleri_hesapla(sembol, gunluk_fiyatlar, aylik_fiyatlar):
    """
    Bir hisse icin quality metriklerini hesaplar.
    Veri: Sadece fiyat (BIST'te fundamental yok).
    """
    if sembol not in gunluk_fiyatlar.columns:
        return None
    
    seri = gunluk_fiyatlar[sembol].dropna()
    if len(seri) < 60:  # En az 2 ay veri
        return None
    
    metrikler = {}
    
    # 1. Volatilite (gunluk getiri std)
    gunluk_getiri = seri.pct_change().dropna()
    metrikler["volatilite"] = float(gunluk_getiri.tail(60).std() * 100)
    
    # 2. Trend tutarliligi (son 12 ay icinde kac ay pozitif)
    if sembol in aylik_fiyatlar.columns:
        aylik_seri = aylik_fiyatlar[sembol].dropna()
        if len(aylik_seri) >= 13:
            son_12 = aylik_seri.tail(13)
            aylik_getiri = son_12.pct_change().dropna()
            metrikler["pozitif_ay_sayisi"] = int((aylik_getiri > 0).sum())
        else:
            metrikler["pozitif_ay_sayisi"] = 6  # Ortalama
    else:
        metrikler["pozitif_ay_sayisi"] = 6
    
    # 3. Drawdown direnci (son 12 ayin max dususu)
    son_252 = seri.tail(252)  # ~1 yil islem gunu
    if len(son_252) > 50:
        kumulatif = (1 + son_252.pct_change().fillna(0)).cumprod()
        running_max = kumulatif.cummax()
        drawdown = (kumulatif - running_max) / running_max * 100
        metrikler["max_drawdown"] = float(drawdown.min())
    else:
        metrikler["max_drawdown"] = -20.0  # Default
    
    # 4. Likidite proxy - son 30 gunun hareketinin volatilitesi
    # Gercek hacim olmadan, fiyat hareketi yogunlugundan tahmin
    son_30 = seri.tail(30)
    if len(son_30) >= 10:
        # Fiyat skalasina gore normalize edilmis hareket
        fiyat_hareket = son_30.diff().abs().mean()
        ort_fiyat = son_30.mean()
        if ort_fiyat > 0:
            metrikler["aktivite_proxy"] = float((fiyat_hareket / ort_fiyat) * 100)
        else:
            metrikler["aktivite_proxy"] = 0
    else:
        metrikler["aktivite_proxy"] = 0
    
    return metrikler


def quality_skoru_hesapla_bist(skor_df, gunluk_fiyatlar, aylik_fiyatlar):
    """
    BIST hisseleri icin Quality skoru hesaplar.
    Final = Momentum * 0.6 + Quality * 0.4
    """
    print("  Quality metrikleri hesaplaniyor...")
    
    quality_list = []
    for _, row in skor_df.iterrows():
        sembol = row["Sembol"]
        metrikler = quality_metrikleri_hesapla(sembol, gunluk_fiyatlar, aylik_fiyatlar)
        
        if metrikler is None:
            quality_list.append({
                "Sembol": sembol,
                "Volatilite_Q": None,
                "PozitifAy_Q": None,
                "Drawdown_Q": None,
                "Aktivite_Q": None
            })
            continue
        
        quality_list.append({
            "Sembol": sembol,
            "Volatilite_Q": metrikler["volatilite"],
            "PozitifAy_Q": metrikler["pozitif_ay_sayisi"],
            "Drawdown_Q": metrikler["max_drawdown"],
            "Aktivite_Q": metrikler["aktivite_proxy"]
        })
    
    q_df = pd.DataFrame(quality_list)
    combined = skor_df.merge(q_df, on="Sembol", how="left")
    
    # Quality icin yeterli verisi olanlari filtrele
    quality_eligible = combined[
        combined["Volatilite_Q"].notna() &
        combined["PozitifAy_Q"].notna()
    ].copy()
    
    if len(quality_eligible) < 10:
        print(f"  UYARI: Quality verisi az ({len(quality_eligible)}), sadece momentum kullanilacak")
        return combined.sort_values("Momentum", ascending=False)
    
    # Quality sub-skorlari (yuzdelik dilim)
    # Volatilite: dusuk olan iyi (ters rank)
    quality_eligible["Vol_Rank"] = (100 - quality_eligible["Volatilite_Q"].rank(pct=True) * 100)
    
    # Pozitif ay: yuksek olan iyi
    quality_eligible["Pozitif_Rank"] = quality_eligible["PozitifAy_Q"].rank(pct=True) * 100
    
    # Drawdown: yakın 0'a olan iyi (negatif degerler)
    quality_eligible["DD_Rank"] = quality_eligible["Drawdown_Q"].rank(pct=True) * 100
    
    # Asiri yukselis cezasi: 6A getiri %500+ ise puan dusur
    quality_eligible["AsirilikCezasi"] = 100
    if "6 Ay %" in quality_eligible.columns:
        quality_eligible.loc[quality_eligible["6 Ay %"] > 500, "AsirilikCezasi"] = 50
        quality_eligible.loc[quality_eligible["6 Ay %"] > 800, "AsirilikCezasi"] = 25
    
    # Quality skoru
    quality_eligible["Quality"] = (
        quality_eligible["Vol_Rank"] * 0.30 +
        quality_eligible["Pozitif_Rank"] * 0.25 +
        quality_eligible["DD_Rank"] * 0.25 +
        quality_eligible["AsirilikCezasi"] * 0.20
    )
    
    # Final skor
    quality_eligible["Final"] = (
        quality_eligible["Momentum"] * 0.6 + 
        quality_eligible["Quality"] * 0.4
    )
    
    return quality_eligible.sort_values("Final", ascending=False)


def quality_ek_bilgi_olustur_bist(top5):
    """BIST Quality icin ek metrikler."""
    ek = "<b>💎 Quality Metrikleri:</b>\n"
    
    if "Volatilite_Q" in top5.columns:
        ort_vol = top5["Volatilite_Q"].dropna().mean()
        if not pd.isna(ort_vol):
            ek += f"   • Ortalama volatilite: %{ort_vol:.1f}\n"
    
    if "PozitifAy_Q" in top5.columns:
        ort_poz = top5["PozitifAy_Q"].dropna().mean()
        if not pd.isna(ort_poz):
            ek += f"   • Ortalama pozitif ay: {ort_poz:.1f}/12\n"
    
    if "Drawdown_Q" in top5.columns:
        ort_dd = top5["Drawdown_Q"].dropna().mean()
        if not pd.isna(ort_dd):
            ek += f"   • Ortalama max düşüş: {ort_dd:.1f}%\n"
    
    if "Quality" in top5.columns:
        ort_q = top5["Quality"].dropna().mean()
        if not pd.isna(ort_q):
            ek += f"   • Ortalama Quality: {ort_q:.1f}/100\n"
    
    if "Final" in top5.columns:
        ort_final = top5["Final"].dropna().mean()
        if not pd.isna(ort_final):
            ek += f"   • Ortalama Final: {ort_final:.1f}/100"
    
    return ek


def main():
    print("=" * 70)
    print("SIRIUS BIST QUALITY - Performans Takipli")
    print("=" * 70)
    
    try:
        # Gecmisi oku
        print("\n[0/6] Gecmis okunuyor...")
        gecmis = gecmis_oku(SISTEM_KODU, portfoy_baslangic=PORTFOY_BIST, para_birimi="₺")
        print(f"  {len(gecmis['kayitlar'])} onceki kayit var")
        
        # Adim 1: Hisse evreni
        print("\n[1/6] Hisse evreni hazirlaniyor...")
        semboller = BIST_KATILIM
        print(f"  {len(semboller)} hisse (BIST KATILIM TUM)")
        
        # Adim 2: Fiyat verisi
        print("\n[2/6] Fiyat verisi cekiliyor (5-10 dakika)...")
        bitis = datetime.now().strftime("%Y-%m-%d")
        baslangic = (datetime.now() - timedelta(days=450)).strftime("%Y-%m-%d")
        
        fiyatlar = retry(
            lambda: coklu_fiyat_cek(semboller, baslangic, bitis, ilerleme_goster=True),
            max_deneme=2,
            bekleme=30,
            adim_adi="BIST KATILIM fiyat verisi"
        )
        
        if fiyatlar.empty:
            raise Exception("Hic veri cekilemedi!")
        
        if hasattr(fiyatlar.index, 'tz') and fiyatlar.index.tz is not None:
            fiyatlar.index = fiyatlar.index.tz_localize(None)
        
        aylik = aylik_fiyatlara_donustur(fiyatlar)
        print(f"\n  {aylik.shape[1]} hisse / {aylik.shape[0]} ay")
        
        if aylik.shape[1] < 5:
            raise Exception(f"Yeterli hisse yok (sadece {aylik.shape[1]} hisse)")
        
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
        
        # Adim 4: Momentum (top 30 al, sonra quality filtrele)
        print("\n[4/6] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top30 = skor.head(30)
        
        # Adim 5: Quality skoru
        print("\n[5/6] Quality skor hesaplaniyor...")
        ranked = quality_skoru_hesapla_bist(top30, fiyatlar, aylik)
        top5 = ranked.head(5)
        
        print("\n" + "=" * 70)
        print(f"QUALITY TOP 5 ({aylik.index[-1].date()})")
        print("=" * 70)
        
        gosterim_kolonlari = ["Sembol", "Momentum"]
        if "Quality" in top5.columns:
            gosterim_kolonlari.append("Quality")
        if "Final" in top5.columns:
            gosterim_kolonlari.append("Final")
        if "Volatilite_Q" in top5.columns:
            gosterim_kolonlari.append("Volatilite_Q")
        if "PozitifAy_Q" in top5.columns:
            gosterim_kolonlari.append("PozitifAy_Q")
        
        print(top5[gosterim_kolonlari].round(2).to_string(index=False))
        print(f"\nSemboller: {', '.join(top5['Sembol'].tolist())}")
        
        # Ek bilgi
        ek_bilgi = quality_ek_bilgi_olustur_bist(top5)
        
        # Yeni kayit
        guncel_portfoy_buyuklugu = kumulatif.get("portfoy_guncel", PORTFOY_BIST)
        
        kapanis_dict = {}
        for sembol in top5["Sembol"]:
            if sembol in aylik.columns:
                kapanis_dict[sembol] = float(aylik[sembol].iloc[-1])
        
        veri_tarih = aylik.index[-1]
        if veri_tarih.month == 12:
            sonraki_ay_adi = f"Ocak {veri_tarih.year + 1}"
        else:
            sonraki_ay_adi = f"{AY_ISIMLERI[veri_tarih.month + 1]} {veri_tarih.year}"
        
        yeni_kayit = yeni_kayit_olustur(
            top5, kapanis_dict, veri_tarih, sonraki_ay_adi,
            guncel_portfoy_buyuklugu, POZISYON_YUZDE_BIST
        )
        
        gecmis["kayitlar"].append(yeni_kayit)
        gecmis_kaydet(SISTEM_KODU, gecmis)
        print(f"  Gecmise kaydedildi: gecmis/{SISTEM_KODU}.json")
        
        # Adim 6: Telegram
        print("\n[6/6] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_detayli(
            top_n_df=top5,
            tarih=aylik.index[-1],
            sistem_adi="BIST QUALITY",
            sistem_emoji="💎",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="₺",
            portfoy_buyuklugu=PORTFOY_BIST,
            pozisyon_yuzde=POZISYON_YUZDE_BIST,
            para_format=",.2f",
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
            telegram_hata_gonder("Sirius BIST QUALITY", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
