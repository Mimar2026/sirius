"""
Sirius BIST KATILIM - Top 5 Saf Momentum

Yoneticinin sistemiyle birebir aynı parametreler:
- Evren: BIST KATILIM TUM (237 hisse)
- Skor: 3+6+12 ay kompozit momentum
- Top N: 5 hisse
- Agirlik: Esit (%20 her)
- Rebalans: Aylik

A signal arrives before the rise.
"""

import os
import time
import traceback
import pandas as pd
import requests
from datetime import datetime, timedelta

# Mevcut modullerden import
from bist_hisseler import BIST_KATILIM
from bist_data import coklu_fiyat_cek, aylik_fiyatlara_donustur
from momentum_system import (
    telegram_gonder,
    telegram_hata_gonder,
    retry,
    momentum_skoru_hesapla,
)


def telegram_mesaji_bist_katilim(top5, tarih):
    """BIST KATILIM top 5 listesini Telegram mesajina cevirir."""
    ay_isimleri = {
        1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
        5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
        9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik"
    }
    ay_adi = ay_isimleri[tarih.month]
    yil = tarih.year
    
    mesaj = "<b>🇹🇷 SIRIUS BIST KATILIM - " + ay_adi + " " + str(yil) + "</b>\n"
    mesaj += "<i>Katilim finans uyumlu top 5 momentum</i>\n\n"
    mesaj += "<b>Top 5 Hisse:</b>\n"
    mesaj += "<pre>"
    
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        sembol = row["Sembol"]
        skor = row["Momentum"]
        getiri_6 = row["6 Ay %"]
        mesaj += "{:2}. {:6} | Skor: {:5.1f} | 6A: {:+7.1f}%\n".format(i, sembol, skor, getiri_6)
    
    mesaj += "</pre>\n"
    mesaj += "📅 Veri: " + tarih.strftime("%Y-%m-%d") + "\n"
    mesaj += "📊 Ortalama 6A: {:+.1f}%\n".format(top5["6 Ay %"].mean())
    mesaj += "📈 Ortalama 12A: {:+.1f}%".format(top5["12 Ay %"].mean())
    
    return mesaj


def main():
    print("=" * 70)
    print("SIRIUS BIST KATILIM - TOP 5 SAF MOMENTUM")
    print("A signal arrives before the rise.")
    print("=" * 70)
    
    try:
        # Adim 1: Hisse evreni (zaten elimizde)
        print("\n[1/4] Hisse evreni hazirlaniyor...")
        semboller = BIST_KATILIM
        print(f"  {len(semboller)} hisse (BIST KATILIM TUM)")
        
        # Adim 2: Fiyat verisi cek (son 14 ay = 12 ay backtest + ek tampon)
        print("\n[2/4] Fiyat verisi cekiliyor (5-10 dakika)...")
        bitis = datetime.now().strftime("%Y-%m-%d")
        baslangic = (datetime.now() - timedelta(days=450)).strftime("%Y-%m-%d")
        
        fiyatlar = retry(
            lambda: coklu_fiyat_cek(semboller, baslangic, bitis, ilerleme_goster=True),
            max_deneme=2,
            bekleme=30,
            adim_adi="BIST KATILIM fiyat verisi cekme"
        )
        
        if fiyatlar.empty:
            raise Exception("Hic veri cekilemedi!")
        
        # Eger DatetimeIndex tz-aware ise tz-naive yap
        if hasattr(fiyatlar.index, 'tz') and fiyatlar.index.tz is not None:
            fiyatlar.index = fiyatlar.index.tz_localize(None)
        
        # Aylik kapanislara cevir
        aylik = aylik_fiyatlara_donustur(fiyatlar)
        print(f"\n  {aylik.shape[1]} hissenin gecerli verisi var ({aylik.shape[0]} ay)")
        
        if aylik.shape[1] < 5:
            raise Exception(f"Yeterli hisse yok (sadece {aylik.shape[1]} hisse)")
        
        # Adim 3: Momentum skorlama
        print("\n[3/4] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top5 = skor.head(5)
        
        print("\n" + "=" * 70)
        print(f"BU AYIN TOP 5 KATILIM HISSESI ({aylik.index[-1].date()})")
        print("=" * 70)
        print(top5[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].round(2).to_string(index=False))
        print(f"\nSemboller: {', '.join(top5['Sembol'].tolist())}")
        
        # Adim 4: Telegram
        print("\n[4/4] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_bist_katilim(top5, aylik.index[-1])
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
            telegram_hata_gonder("Sirius BIST KATILIM", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
