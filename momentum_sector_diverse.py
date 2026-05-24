"""
Sirius DIVERSE - Sektor Cesitlendirmeli Momentum
Aynı momentum mantigi + sektor cesitlendirme filtresi.

Her sektorden maksimum 3 hisse alir, boylece top 10
tek tema/sektorde konsantre olmaz.

Sirius: A signal arrives before the rise.
"""

import os
import time
import traceback
import yfinance as yf
import pandas as pd
import requests
from io import StringIO


# Mevcut momentum_system.py'den fonksiyonlari kullan
from momentum_system import (
    telegram_gonder,
    telegram_hata_gonder,
    retry,
    hisse_evrenini_cek,
    fiyat_verisi_cek,
    aylik_fiyatlara_donustur,
    momentum_skoru_hesapla,
)


def sektor_bilgisi_cek(semboller):
    """
    Verilen sembollerin sektor bilgisini yfinance'ten ceker.
    Hata olursa "Unknown" atar.
    """
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
    """
    Momentum siralamasini koruyarak sektor cesitlendirme uygular.
    Her sektorden maksimum max_sektor kadar hisse alir.
    """
    # Sektor sayilarini takip et
    sektor_sayilari = {}
    secilen_hisseler = []
    
    # Skor sirasinda gec
    for _, row in skor_df.iterrows():
        sembol = row["Sembol"]
        sektor = sektor_dict.get(sembol, "Unknown")
        
        # Bu sektorden kac adet var?
        mevcut_sayi = sektor_sayilari.get(sektor, 0)
        
        # Eger sektorden henuz max_sektor kadar yoksa, ekle
        if mevcut_sayi < max_sektor:
            secilen_hisseler.append(sembol)
            sektor_sayilari[sektor] = mevcut_sayi + 1
            
            # Top N'e ulastik mi?
            if len(secilen_hisseler) >= top_n:
                break
    
    # Filtreden gecmis hisseleri DataFrame olarak don
    return skor_df[skor_df["Sembol"].isin(secilen_hisseler)].copy()


def telegram_mesaji_olustur_diverse(top10, tarih, sektor_dict):
    """Top 10 listesini Telegram mesajina cevirir (sektor bilgisi dahil)."""
    ay_isimleri = {
        1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
        5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
        9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik"
    }
    ay_adi = ay_isimleri[tarih.month]
    yil = tarih.year
    
    mesaj = "<b>🌐 SIRIUS DIVERSE - " + ay_adi + " " + str(yil) + "</b>\n"
    mesaj += "<i>Sektor cesitlendirmeli versiyon</i>\n\n"
    mesaj += "<b>Top 10 Hisse:</b>\n"
    mesaj += "<pre>"
    
    for i, (_, row) in enumerate(top10.iterrows(), 1):
        sembol = row["Sembol"]
        skor = row["Momentum"]
        sektor = sektor_dict.get(sembol, "Unknown")[:12]
        mesaj += "{:2}. {:5} | {:5.1f} | {}\n".format(i, sembol, skor, sektor)
    
    mesaj += "</pre>\n"
    
    # Sektor dagilimi
    secilen_sektorler = [sektor_dict.get(s, "Unknown") for s in top10["Sembol"].tolist()]
    sektor_dagilimi = {}
    for s in secilen_sektorler:
        sektor_dagilimi[s] = sektor_dagilimi.get(s, 0) + 1
    
    mesaj += "\n<b>Sektor Dagilimi:</b>\n"
    for sektor, sayi in sorted(sektor_dagilimi.items(), key=lambda x: -x[1]):
        mesaj += "• " + sektor + ": " + str(sayi) + "\n"
    
    mesaj += "\n📅 Veri: " + tarih.strftime("%Y-%m-%d") + "\n"
    mesaj += "📊 Ort. 6A getiri: {:+.1f}%".format(top10["6 Ay %"].mean())
    
    return mesaj


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
        
        # Adim 3: Momentum hesapla (top 50 al, sonra filtreleyecegiz)
        print("\n[3/5] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top50 = skor.head(50)
        
        # Adim 4: Sektor bilgilerini cek (50 hisse icin, ~30 saniye)
        print("\n[4/5] Sektor bilgisi cekiliyor (~30 saniye)...")
        sektor_dict = sektor_bilgisi_cek(top50["Sembol"].tolist())
        
        # Sektor cesitlendirme uygula
        top10 = sektor_cesitlendirme_uygula(top50, sektor_dict, top_n=10, max_sektor=3)
        
        print("\n" + "=" * 70)
        print("DIVERSE TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        
        # Sektor kolonunu ekle goster
        gosterim = top10[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].copy()
        gosterim["Sektor"] = gosterim["Sembol"].map(sektor_dict)
        print(gosterim.round(2).to_string(index=False))
        
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
        # Adim 5: Telegram bildirim
        print("\n[5/5] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_olustur_diverse(top10, aylik.index[-1], sektor_dict)
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
