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


def son_fiyat_ve_ortalama_hesapla(aylik_fiyatlar, gunluk_fiyatlar=None):
    """
    Her hisse icin son kapanis ve 30-gun ortalama hesaplar.
    Returns: {sembol: {"kapanis": float, "ort_30": float, "volatilite": float}}
    """
    sonuc = {}
    if gunluk_fiyatlar is None:
        # Eger gunluk veri yoksa, sadece aylik son fiyati kullan
        for sembol in aylik_fiyatlar.columns:
            if pd.notna(aylik_fiyatlar[sembol].iloc[-1]):
                sonuc[sembol] = {
                    "kapanis": float(aylik_fiyatlar[sembol].iloc[-1]),
                    "ort_30": float(aylik_fiyatlar[sembol].iloc[-1]),
                    "volatilite": 0.0
                }
        return sonuc
    
    # Gunluk veri varsa hesapla
    son_30 = gunluk_fiyatlar.tail(30)
    
    for sembol in gunluk_fiyatlar.columns:
        seri = gunluk_fiyatlar[sembol].dropna()
        if len(seri) == 0:
            continue
        
        kapanis = float(seri.iloc[-1])
        ort_30 = float(son_30[sembol].dropna().mean()) if len(son_30[sembol].dropna()) > 0 else kapanis
        
        # Gunluk volatilite (std / ortalama * 100)
        getiri = seri.pct_change().dropna().tail(30)
        volatilite = float(getiri.std() * 100) if len(getiri) > 0 else 0.0
        
        sonuc[sembol] = {
            "kapanis": kapanis,
            "ort_30": ort_30,
            "volatilite": volatilite
        }
    
    return sonuc


def risk_seviyesi_hesapla(row, fiyat_bilgi=None):
    """
    Her hisse icin 1-5 arasi risk skoru hesaplar.
    Returns: (skor, gosterge_string)
    """
    risk = 0
    
    # 1. Yuksek volatilite (gunluk std > %5)
    if fiyat_bilgi and fiyat_bilgi.get("volatilite", 0) > 5:
        risk += 1
    elif fiyat_bilgi and fiyat_bilgi.get("volatilite", 0) > 3:
        risk += 0  # Orta volatilite, risk artirma
    
    # 2. Asiri getiri (12A > %300 yani overextended)
    getiri_12 = row.get("12 Ay %", 0)
    if pd.notna(getiri_12):
        if getiri_12 > 500:
            risk += 2
        elif getiri_12 > 300:
            risk += 1
    
    # 3. Cok yuksek 6A getiri (parabolik hareket)
    getiri_6 = row.get("6 Ay %", 0)
    if pd.notna(getiri_6):
        if getiri_6 > 200:
            risk += 1
    
    # 4. Cok yuksek skor (overcrowded trade)
    skor = row.get("Momentum", 0)
    if skor > 99.5:
        risk += 1
    
    # En fazla 5
    risk = min(risk, 5)
    
    # Gosterge
    if risk == 0:
        gosterge = "🟢 (0/5)"
    elif risk == 1:
        gosterge = "⚠️ (1/5)"
    elif risk == 2:
        gosterge = "⚠️⚠️ (2/5)"
    elif risk == 3:
        gosterge = "⚠️⚠️⚠️ (3/5)"
    elif risk == 4:
        gosterge = "🔴🔴🔴🔴 (4/5)"
    else:
        gosterge = "🔴🔴🔴🔴🔴 (5/5)"
    
    return risk, gosterge


def telegram_mesaji_olustur(top10, tarih, gunluk_fiyatlar=None, aylik_fiyatlar=None):
    """Top 10 listesini detayli aksiyon mesajina cevirir."""
    ay_isimleri = {
        1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
        5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
        9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik"
    }
    ay_adi = ay_isimleri[tarih.month]
    yil = tarih.year
    
    # Sonraki ay (gecerlilik bitisi icin)
    if tarih.month == 12:
        sonraki_ay = "Ocak"
        sonraki_yil = yil + 1
    else:
        sonraki_ay = ay_isimleri[tarih.month + 1]
        sonraki_yil = yil
    
    # Fiyat ve volatilite hesapla
    fiyat_dict = son_fiyat_ve_ortalama_hesapla(aylik_fiyatlar, gunluk_fiyatlar) if aylik_fiyatlar is not None else {}
    
    mesaj = f"<b>🌟 SIRIUS - {ay_adi} {yil}</b>\n"
    mesaj += "<i>A signal arrives before the rise.</i>\n\n"
    mesaj += "<b>📊 Top 10 Portföy</b> (her hisse %10 ağırlık)\n"
    mesaj += "━━━━━━━━━━━━━━━━━━━━\n"
    
    toplam_risk = 0
    for i, (_, row) in enumerate(top10.iterrows(), 1):
        sembol = row["Sembol"]
        skor = row["Momentum"]
        getiri_3 = row.get("3 Ay %", 0)
        getiri_6 = row.get("6 Ay %", 0)
        getiri_12 = row.get("12 Ay %", 0)
        
        # Fiyat bilgisi
        f_info = fiyat_dict.get(sembol, {})
        kapanis = f_info.get("kapanis", 0)
        ort_30 = f_info.get("ort_30", 0)
        volatilite = f_info.get("volatilite", 0)
        
        # Risk hesapla
        risk_skor, risk_gosterge = risk_seviyesi_hesapla(row, f_info)
        toplam_risk += risk_skor
        
        # Trend yonu (kapanis vs 30-gun ort)
        if kapanis > 0 and ort_30 > 0:
            fark_yuzde = ((kapanis - ort_30) / ort_30) * 100
            if fark_yuzde > 5:
                trend = "⬆️"
            elif fark_yuzde < -5:
                trend = "⬇️"
            else:
                trend = "➡️"
        else:
            trend = "➡️"
        
        # Volatilite seviyesi
        if volatilite > 5:
            vol_str = "Yüksek"
        elif volatilite > 3:
            vol_str = "Orta"
        else:
            vol_str = "Düşük"
        
        # Hisse blogu
        mesaj += f"\n<b>▸ {i}. {sembol}</b> {trend}\n"
        if kapanis > 0:
            mesaj += f"   💵 Kapanış: ${kapanis:.2f}\n"
            mesaj += f"   📊 30g ort: ${ort_30:.2f}\n"
            min_p = min(kapanis, ort_30)
            max_p = max(kapanis, ort_30)
            mesaj += f"   🎯 Aralık: ${min_p:.2f} - ${max_p:.2f}\n"
        mesaj += f"   ⚡ Skor: {skor:.1f} | 6A: {getiri_6:+.0f}% | 12A: {getiri_12:+.0f}%\n"
        mesaj += f"   🌡️ Volatilite: {vol_str} ({volatilite:.1f}%)\n"
        mesaj += f"   {risk_gosterge}\n"
    
    # Portfoy ozeti
    ort_risk = toplam_risk / len(top10)
    mesaj += "\n━━━━━━━━━━━━━━━━━━━━\n"
    mesaj += "<b>📈 Portföy Özeti</b>\n"
    mesaj += f"  • Ortalama skor: {top10['Momentum'].mean():.1f}/100\n"
    mesaj += f"  • Ortalama 6A: {top10['6 Ay %'].mean():+.0f}%\n"
    mesaj += f"  • Ortalama 12A: {top10['12 Ay %'].mean():+.0f}%\n"
    mesaj += f"  • Ortalama risk: {ort_risk:.1f}/5\n"
    
    if ort_risk >= 3.5:
        mesaj += "  ⚠️ <b>YÜKSEK RİSK</b> - dikkatli ol\n"
    elif ort_risk >= 2.5:
        mesaj += "  ⚠️ Orta-yüksek risk\n"
    
    mesaj += "\n"
    mesaj += f"📅 Veri tarihi: {tarih.strftime('%Y-%m-%d')}\n"
    mesaj += f"⏳ Geçerli: 1-30 {ay_adi}\n"
    mesaj += f"🔄 Sonraki: 1 {sonraki_ay} 09:00\n\n"
    mesaj += "<i>⚠️ Yatırım tavsiyesi değildir. Geçmiş performans gelecek garantisi vermez.</i>"
    
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
        telegram_mesaji = telegram_mesaji_olustur(top10, aylik.index[-1], 
                                                    gunluk_fiyatlar=fiyatlar,
                                                    aylik_fiyatlar=aylik)
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
