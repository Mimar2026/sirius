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
from datetime import datetime, timedelta

from bist_hisseler import BIST_KATILIM
from bist_data import coklu_fiyat_cek, aylik_fiyatlara_donustur
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
)


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
        
        # Adim 2: Fiyat verisi cek
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
        
        # Timezone temizle
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
        
        # Adim 4: Telegram - detayli mesaj (TL ile)
        print("\n[4/4] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_detayli(
            top_n_df=top5,
            tarih=aylik.index[-1],
            sistem_adi="BIST KATILIM",
            sistem_emoji="🇹🇷",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="₺",
            portfoy_buyuklugu=PORTFOY_BIST,
            pozisyon_yuzde=POZISYON_YUZDE_BIST,
            para_format=",.2f"
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
            telegram_hata_gonder("Sirius BIST KATILIM", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
