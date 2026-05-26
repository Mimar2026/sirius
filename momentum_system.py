"""
Sirius - Saf Momentum Portfoy Sistemi (ABD) - Performans Takipli

Her ay basinda calistir, top 10 hisseleri secer, performans takibi yapar.
"""

import os
import time
import traceback
import yfinance as yf
import pandas as pd
import requests
from io import StringIO

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


SISTEM_KODU = "momentum"


# ====================================================================
# TELEGRAM AYARLARI
# ====================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def telegram_gonder(mesaj):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  [Telegram] Token veya Chat ID tanimli degil.")
        return False
    
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.json().get("ok"):
            print("  [Telegram] Mesaj gonderildi.")
            return True
        else:
            print("  [Telegram] Hata: " + str(response.json()))
            return False
    except Exception as e:
        print("  [Telegram] Baglanti hatasi: " + str(e))
        return False


def telegram_hata_gonder(adim, hata_mesaji):
    from datetime import datetime
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    mesaj = (
        "<b>⚠️ SIRIUS - Hata Bildirimi</b>\n\n"
        "<b>Tarih:</b> " + tarih + "\n"
        "<b>Adim:</b> " + adim + "\n"
        "<b>Hata:</b> <code>" + str(hata_mesaji)[:500] + "</code>\n\n"
        "<i>Logs:</i> https://github.com/Mimar2026/sirius/actions"
    )
    telegram_gonder(mesaj)


def retry(fonksiyon, max_deneme=3, bekleme=5, adim_adi="islem"):
    son_hata = None
    for deneme in range(1, max_deneme + 1):
        try:
            sonuc = fonksiyon()
            if deneme > 1:
                print("  [Retry] " + adim_adi + " " + str(deneme) + ". denemede basarili.")
            return sonuc
        except Exception as e:
            son_hata = e
            print("  [Retry] " + adim_adi + " - Deneme " + str(deneme) + "/" + str(max_deneme) + " basarisiz: " + str(e))
            if deneme < max_deneme:
                print("  [Retry] " + str(bekleme) + " saniye bekleniyor...")
                time.sleep(bekleme)
    
    raise Exception(adim_adi + " - " + str(max_deneme) + " deneme sonrasi basarisiz: " + str(son_hata))


def hisse_evrenini_cek():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    sp_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    sp_response = requests.get(sp_url, headers=headers, timeout=15)
    sp500 = pd.read_html(StringIO(sp_response.text))[0]["Symbol"].tolist()
    
    nq_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    nq_response = requests.get(nq_url, headers=headers, timeout=15)
    nq_tablolari = pd.read_html(StringIO(nq_response.text))
    nq_tablo = next(
        (t for t in nq_tablolari 
         if ("Ticker" in t.columns or "Symbol" in t.columns) and len(t) >= 90),
        None
    )
    sembol_kol = "Ticker" if "Ticker" in nq_tablo.columns else "Symbol"
    nasdaq100 = nq_tablo[sembol_kol].tolist()
    
    birlesik = sorted(list(set(sp500) | set(nasdaq100)))
    return [s.replace(".", "-") for s in birlesik]


def fiyat_verisi_cek(semboller, donem="2y"):
    veri = yf.download(semboller, period=donem, interval="1d", progress=False, auto_adjust=True)
    return veri["Close"]


def aylik_fiyatlara_donustur(gunluk_fiyatlar, min_veri_yuzdesi=80):
    aylik = gunluk_fiyatlar.resample("ME").last()
    veri_yuzdesi = aylik.notna().sum() / len(aylik) * 100
    gecerli = veri_yuzdesi[veri_yuzdesi >= min_veri_yuzdesi].index.tolist()
    return aylik[gecerli]


def momentum_skoru_hesapla(aylik_fiyatlar, lookback_aylar=[3, 6, 12]):
    simdiki = aylik_fiyatlar.iloc[-1]
    
    getiriler = {}
    for ay in lookback_aylar:
        gecmis = aylik_fiyatlar.iloc[-(ay + 1)]
        getiriler[str(ay) + "_ay"] = ((simdiki / gecmis) - 1) * 100
    
    skor_df = pd.DataFrame({
        "Sembol": aylik_fiyatlar.columns,
        **{str(ay) + " Ay %": getiriler[str(ay) + "_ay"].values for ay in lookback_aylar}
    }).dropna()
    
    for ay in lookback_aylar:
        skor_df[str(ay) + "_rank"] = skor_df[str(ay) + " Ay %"].rank(pct=True) * 100
    
    rank_kolonlari = [str(ay) + "_rank" for ay in lookback_aylar]
    skor_df["Momentum"] = skor_df[rank_kolonlari].mean(axis=1)
    
    return skor_df.sort_values("Momentum", ascending=False).reset_index(drop=True)


def main():
    print("=" * 70)
    print("SIRIUS MOMENTUM (ABD) - Performans Takipli")
    print("=" * 70)
    
    try:
        # Gecmisi oku
        print("\n[0/5] Gecmis okunuyor...")
        gecmis = gecmis_oku(SISTEM_KODU, portfoy_baslangic=PORTFOY_ABD, para_birimi="$")
        print(f"  {len(gecmis['kayitlar'])} onceki kayit var")
        
        # Adim 1: Hisse evreni
        print("\n[1/5] Hisse evreni cekiliyor...")
        semboller = retry(hisse_evrenini_cek, max_deneme=3, bekleme=10, adim_adi="Hisse evreni")
        print("  " + str(len(semboller)) + " hisse")
        
        # Adim 2: Fiyat verisi
        print("\n[2/5] Fiyat verisi cekiliyor...")
        fiyatlar = retry(lambda: fiyat_verisi_cek(semboller), max_deneme=3, bekleme=15, adim_adi="Fiyat verisi")
        aylik = aylik_fiyatlara_donustur(fiyatlar)
        print("  " + str(aylik.shape[1]) + " hisse / " + str(aylik.shape[0]) + " ay")
        
        # Adim 3: Onceki portfoyun performansi (varsa)
        print("\n[3/5] Onceki portfoyun performansi hesaplaniyor...")
        if gecmis["kayitlar"]:
            onceki_kayit = gecmis["kayitlar"][-1]
            
            # Onceki hisselerin guncel kapanis fiyatlarini al
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
            print("  Henuz onceki kayit yok, atlaniyor.")
        
        # Kumulatif performans
        kumulatif = kumulatif_performans_hesapla(gecmis)
        
        # Adim 4: Yeni top 10 momentum
        print("\n[4/5] Yeni momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top10 = skor.head(10)
        
        print("\n" + "=" * 70)
        print("YENI TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        print(top10[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].round(2).to_string(index=False))
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
        # Yeni kayit olustur ve gecmise ekle
        guncel_portfoy_buyuklugu = kumulatif.get("portfoy_guncel", PORTFOY_ABD)
        
        kapanis_dict = {}
        for sembol in top10["Sembol"]:
            if sembol in aylik.columns:
                kapanis_dict[sembol] = float(aylik[sembol].iloc[-1])
        
        # Sonraki ay icin ay adi (veri tarihinin bir sonraki ayi)
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
        
        # Adim 5: Telegram
        print("\n[5/5] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_detayli(
            top_n_df=top10,
            tarih=aylik.index[-1],
            sistem_adi="MOMENTUM",
            sistem_emoji="🌟",
            gunluk_fiyatlar=fiyatlar,
            aylik_fiyatlar=aylik,
            para_birimi="$",
            portfoy_buyuklugu=PORTFOY_ABD,
            pozisyon_yuzde=POZISYON_YUZDE_ABD,
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
            telegram_hata_gonder("Sirius Momentum (ABD)", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
