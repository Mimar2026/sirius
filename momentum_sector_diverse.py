"""
Sirius DIVERSE - Sektor Cesitlendirmeli Momentum (ABD)

Her sektorden maksimum 3 hisse. Performans takipli.
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


SISTEM_KODU = "diverse"


def sektor_bilgisi_cek(semboller):
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
    print("SIRIUS DIVERSE - Sektor Cesitlendirmeli Momentum - Performans Takipli")
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
        
        # Adim 5: Sektor bilgisi
        print("\n[5/6] Sektor bilgisi cekiliyor...")
        sektor_dict = sektor_bilgisi_cek(top50["Sembol"].tolist())
        
        top10 = sektor_cesitlendirme_uygula(top50, sektor_dict, top_n=10, max_sektor=3)
        
        print("\n" + "=" * 70)
        print("DIVERSE TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        gosterim = top10[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].copy()
        gosterim["Sektor"] = gosterim["Sembol"].map(sektor_dict)
        print(gosterim.round(2).to_string(index=False))
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
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
            sistem_adi="DIVERSE",
            sistem_emoji="🌐",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="$",
            portfoy_buyuklugu=PORTFOY_ABD,
            pozisyon_yuzde=POZISYON_YUZDE_ABD,
            para_format=",.2f",
            sektor_dict=sektor_dict,
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
            telegram_hata_gonder("Sirius DIVERSE Aylik Calistirma", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
