"""
Sirius BIST GENEL - Top 5 Saf Momentum (568 hisse) - Performans Takipli

Yoneticinin "katilim disi" sistemiyle paralel:
- Evren: BIST TUM (568 hisse)
- Top 5, esit agirlik (%20 her)
- Aylik rebalans
"""

import os
import time
import traceback
import pandas as pd
from datetime import datetime, timedelta

from bist_hisseler import BIST_TUM
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
    AY_ISIMLERI,
)

from performans_tracker import (
    gecmis_oku,
    gecmis_kaydet,
    onceki_portfoy_performans_hesapla,
    kumulatif_performans_hesapla,
    yeni_kayit_olustur,
)


SISTEM_KODU = "bist_genel"


def main():
    print("=" * 70)
    print("SIRIUS BIST GENEL - Performans Takipli")
    print("=" * 70)
    
    try:
        # Gecmisi oku
        print("\n[0/5] Gecmis okunuyor...")
        gecmis = gecmis_oku(SISTEM_KODU, portfoy_baslangic=PORTFOY_BIST, para_birimi="₺")
        print(f"  {len(gecmis['kayitlar'])} onceki kayit var")
        
        # Adim 1: Hisse evreni
        print("\n[1/5] Hisse evreni hazirlaniyor...")
        semboller = BIST_TUM
        print(f"  {len(semboller)} hisse (BIST TUM)")
        
        # Adim 2: Fiyat verisi
        print("\n[2/5] Fiyat verisi cekiliyor (10-20 dakika)...")
        bitis = datetime.now().strftime("%Y-%m-%d")
        baslangic = (datetime.now() - timedelta(days=450)).strftime("%Y-%m-%d")
        
        fiyatlar = retry(
            lambda: coklu_fiyat_cek(semboller, baslangic, bitis, ilerleme_goster=True),
            max_deneme=2,
            bekleme=30,
            adim_adi="BIST GENEL fiyat verisi"
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
        print("\n[3/5] Onceki portfoyun performansi hesaplaniyor...")
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
        
        # Adim 4: Yeni momentum
        print("\n[4/5] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top5 = skor.head(5)
        
        print("\n" + "=" * 70)
        print(f"BU AYIN TOP 5 GENEL HISSESI ({aylik.index[-1].date()})")
        print("=" * 70)
        print(top5[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].round(2).to_string(index=False))
        print(f"\nSemboller: {', '.join(top5['Sembol'].tolist())}")
        
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
        
        # Adim 5: Telegram
        print("\n[5/5] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_detayli(
            top_n_df=top5,
            tarih=aylik.index[-1],
            sistem_adi="BIST GENEL",
            sistem_emoji="🇹🇷",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="₺",
            portfoy_buyuklugu=PORTFOY_BIST,
            pozisyon_yuzde=POZISYON_YUZDE_BIST,
            para_format=",.2f",
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
            telegram_hata_gonder("Sirius BIST GENEL", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
