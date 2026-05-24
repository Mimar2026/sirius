"""
Sirius - Momentum Portfolio System (Robust Version)
Her ay basinda calistir, top 10 hisseleri ekrana basar ve Telegram'a gonderir.

Yeni: Retry mantigi + hata yakalama + Telegram'a hata bildirimi.

Sirius: A signal arrives before the rise.
"""

import os
import time
import traceback
import yfinance as yf
import pandas as pd
import requests
from io import StringIO


# ====================================================================
# TELEGRAM AYARLARI
# ====================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def telegram_gonder(mesaj):
    """Telegram bot uzerinden mesaj gonderir."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("  [Telegram] Token veya Chat ID tanimli degil, gonderilmedi.")
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
    """Hata durumunda Telegram'a uyari gonderir."""
    from datetime import datetime
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    mesaj = (
        "<b>⚠️ SIRIUS - Hata Bildirimi</b>\n\n"
        "<b>Tarih:</b> " + tarih + "\n"
        "<b>Adim:</b> " + adim + "\n"
        "<b>Hata:</b> <code>" + str(hata_mesaji)[:500] + "</code>\n\n"
        "<i>Lutfen actions sekmesinden detayli loga bakin:</i>\n"
        "https://github.com/Mimar2026/sirius/actions"
    )
    telegram_gonder(mesaj)


def retry(fonksiyon, max_deneme=3, bekleme=5, adim_adi="islem"):
    """
    Bir fonksiyonu hata durumunda max_deneme kez tekrar dener.
    Her deneme arasinda bekleme saniyesi bekler.
    """
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
    
    # Tum denemeler basarisiz
    raise Exception(adim_adi + " - " + str(max_deneme) + " deneme sonrasi basarisiz: " + str(son_hata))


def hisse_evrenini_cek():
    """S&P 500 ve Nasdaq 100 birlestirilmis hisse evrenini doner."""
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
    """Fiyat verisini ceker."""
    veri = yf.download(
        semboller, period=donem, interval="1d",
        progress=False, auto_adjust=True
    )
    return veri["Close"]


def aylik_fiyatlara_donustur(gunluk_fiyatlar, min_veri_yuzdesi=80):
    """Gunluk fiyatlari aylik kapanislara cevirir."""
    aylik = gunluk_fiyatlar.resample("ME").last()
    veri_yuzdesi = aylik.notna().sum() / len(aylik) * 100
    gecerli = veri_yuzdesi[veri_yuzdesi >= min_veri_yuzdesi].index.tolist()
    return aylik[gecerli]


def momentum_skoru_hesapla(aylik_fiyatlar, lookback_aylar=[3, 6, 12]):
    """Kompozit momentum skoru hesaplar."""
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


def telegram_mesaji_olustur(top10, tarih):
    """Top 10 listesini guzel formatli Telegram mesajina cevirir."""
    ay_isimleri = {
        1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
        5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
        9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik"
    }
    ay_adi = ay_isimleri[tarih.month]
    yil = tarih.year
    
    mesaj = "<b>🌟 SIRIUS - " + ay_adi + " " + str(yil) + " Portfoyu</b>\n\n"
    mesaj += "<i>A signal arrives before the rise.</i>\n\n"
    mesaj += "<b>Top 10 Hisse:</b>\n"
    mesaj += "<pre>"
    
    for i, (_, row) in enumerate(top10.iterrows(), 1):
        sembol = row["Sembol"]
        skor = row["Momentum"]
        getiri_6 = row["6 Ay %"]
        mesaj += "{:2}. {:6} | Skor: {:5.1f} | 6A: {:+6.1f}%\n".format(i, sembol, skor, getiri_6)
    
    mesaj += "</pre>\n"
    mesaj += "📅 Veri tarihi: " + tarih.strftime("%Y-%m-%d") + "\n"
    mesaj += "📊 Ortalama 6A getiri: {:+.1f}%\n".format(top10["6 Ay %"].mean())
    mesaj += "📈 Ortalama 12A getiri: {:+.1f}%".format(top10["12 Ay %"].mean())
    
    return mesaj


def main():
    print("=" * 70)
    print("SIRIUS - MOMENTUM PORTFOLIO ENGINE")
    print("A signal arrives before the rise.")
    print("=" * 70)
    
    try:
        # Adim 1: Hisse evreni
        print("\n[1/4] Hisse evreni cekiliyor...")
        semboller = retry(
            hisse_evrenini_cek,
            max_deneme=3,
            bekleme=10,
            adim_adi="Hisse evreni cekme"
        )
        print("  " + str(len(semboller)) + " hisse")
        
        # Adim 2: Fiyat verisi
        print("\n[2/4] Fiyat verisi cekiliyor (1-2 dakika)...")
        fiyatlar = retry(
            lambda: fiyat_verisi_cek(semboller),
            max_deneme=3,
            bekleme=15,
            adim_adi="Fiyat verisi cekme"
        )
        aylik = aylik_fiyatlara_donustur(fiyatlar)
        print("  " + str(aylik.shape[1]) + " hisse / " + str(aylik.shape[0]) + " ay")
        
        # Adim 3: Momentum hesapla
        print("\n[3/4] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top10 = skor.head(10)
        
        print("\n" + "=" * 70)
        print("BU AYIN TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        print(top10[["Sembol", "3 Ay %", "6 Ay %", "12 Ay %", "Momentum"]].round(2).to_string(index=False))
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
        # Adim 4: Telegram bildirim
        print("\n[4/4] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_olustur(top10, aylik.index[-1])
        telegram_basarili = telegram_gonder(telegram_mesaji)
        
        if not telegram_basarili:
            raise Exception("Telegram mesaji gonderilemedi")
        
        print("\n" + "=" * 70)
        print("Tamamlandi.")
        print("=" * 70)
    
    except Exception as e:
        # Herhangi bir adimda hata olursa
        hata_detayi = traceback.format_exc()
        print("\n" + "!" * 70)
        print("HATA OLUSTU!")
        print("!" * 70)
        print(hata_detayi)
        
        # Telegram'a hata bildirimi gonder
        try:
            telegram_hata_gonder("Sirius Aylik Calistirma", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        # GitHub Actions'in hata gormesi icin exception'i tekrar firlat
        raise


if __name__ == "__main__":
    main()
