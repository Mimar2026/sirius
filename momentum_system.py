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
    """S&P 500 ve Nasdaq 100 birlestirilmis hisse evrenini doner."""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # S&P 500
    sp_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    sp_response = requests.get(sp_url, headers=headers, timeout=15)
    sp_tablolari = pd.read_html(StringIO(sp_response.text))
    
    sp_tablo = None
    for t in sp_tablolari:
        if "Symbol" in t.columns and len(t) >= 400:
            sp_tablo = t
            break
    
    if sp_tablo is None:
        print("  UYARI: S&P 500 tablosu bulunamadi. Bulunan tablolar:")
        for i, t in enumerate(sp_tablolari):
            print(f"    Tablo {i}: {list(t.columns)[:5]}... ({len(t)} satir)")
        raise Exception("S&P 500 tablosu bulunamadi - Wikipedia sayfa yapisi degismis olabilir")
    
    sp500 = sp_tablo["Symbol"].tolist()
    
    # Nasdaq 100
    nq_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    nq_response = requests.get(nq_url, headers=headers, timeout=15)
    nq_tablolari = pd.read_html(StringIO(nq_response.text))
    
    nq_tablo = None
    sembol_kol = None
    olasi_kolonlar = ["Ticker", "Symbol", "Ticker symbol", "Ticker Symbol"]
    for t in nq_tablolari:
        for kol in olasi_kolonlar:
            if kol in t.columns and len(t) >= 80:
                nq_tablo = t
                sembol_kol = kol
                break
        if nq_tablo is not None:
            break
    
    if nq_tablo is None:
        print("  UYARI: Nasdaq-100 tablosu bulunamadi. Bulunan tablolar:")
        for i, t in enumerate(nq_tablolari):
            print(f"    Tablo {i}: {list(t.columns)[:5]}... ({len(t)} satir)")
        raise Exception("Nasdaq-100 tablosu bulunamadi - Wikipedia sayfa yapisi degismis olabilir")
    
    nasdaq100 = nq_tablo[sembol_kol].tolist()
    
    birlesik = sorted(list(set(sp500) | set(nasdaq100)))
    return [str(s).replace(".", "-") for s in birlesik]


def fiyat_verisi_cek(semboller, donem="2y"):
    veri = yf.download(semboller, period=donem, interval="1d", progress=False, auto_adjust=True)
    return veri["Close"]


def aylik_fiyatlara_donustur(gunluk_fiyatlar, min_veri_yuzdesi=80):
    aylik = gunluk_fiyatlar.resample("ME").last()
    veri_yuzdesi = aylik.notna().sum() / len(aylik) * 100
    gecerli = veri_yuzdesi[veri_yuzdesi >= min_veri_yuzdesi].index.tolist()
    return aylik[gecerli]


def momentum_sk
