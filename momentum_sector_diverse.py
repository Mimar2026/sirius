"""
Sirius DIVERSE - Sektor Cesitlendirmeli Momentum (ABD)

Aynı momentum mantigi + sektor cesitlendirme filtresi.
Her sektorden maksimum 3 hisse alir.

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


def sektor_bilgisi_cek(semboller):
    """yfinance'ten sektor bilgisi ceker."""
    sektorler = {}
    for sembol in semboller:
        try:
            info = yf.Ticker(sembol).info
            sektor = info.get("sector", "Unknown")
            sektorler[sembol] = sektor
            time.sleep(0.1)
        except Exception:
            sektorler[sembol] = "Unknown"
    return sektorler


def sektor_cesitlendirme_uygula(skor_df, sektor_dict, top_n=10, max_sektor=3):
    """Sektor cesitlendirme uygular."""
    sektor_sayilari = {}
    secilen_hisseler = []
    
    for _, row in skor_df.iterrows():
        sembol = row["Sembol"]
        sektor = sektor_dict.get(sembol, "Unknown")
        
        mevcut_sayi = sektor_sayilari.get(sektor, 0)
        
        if mevcut_sayi < max_sektor:
            secilen_hisseler.append(sembol)
            sektor_sayilari[sektor] = mevcut_sayi + 1
            
            if len(secilen_hisseler) >= top_n:
                break
    
    return skor_df[skor_df["Sembol"].isin(secilen_hisseler)].copy()


def main():
    print("=" * 70)
    print("SIRIUS DIVERSE - SEKTOR CESITLENDIRMELI MOMENTUM")
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
        
        # Adim 4: Sektor bilgisi (50 hisse)
        print("\n[4/5] Sektor bilgisi cekiliyor (~30 saniye)...")
        sektor_dict = sektor_bilgisi_cek(top50["Sembol"].tolist())
        
        # Sektor cesitlendirme uygula
        top10 = sektor_cesitlendirme_uygula(top50, sektor_dict, top_n=10, max_sektor=3)
        
        print("\n" + "=" * 70)
        print("DIVERSE TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        gosterim = top10[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].copy()
        gosterim["Sektor"] = gosterim["Sembol"].map(sektor_dict)
        print(gosterim.round(2).to_string(index=False))
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
        # Adim 5: Telegram - detayli mesaj (sektor bilgisi ile)
        print("\n[5/5] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_detayli(
            top_n_df=top10,
            tarih=aylik.index[-1],
            sistem_adi="DIVERSE",
            sistem_emoji="🌐",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="$",
            portfoy_buyuklugu=PORTFOY_ABD,
            pozisyon_yuzde=POZISYON_YUZDE_ABD,
            para_format=",.2f",
            sektor_dict=sektor_dict
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
            telegram_hata_gonder("Sirius DIVERSE Aylik Calistirma", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
