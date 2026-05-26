"""
Sirius - Performans Takip Modulu

Her sistem icin gecmis portfoylerin kapsamli performans analizini yapar:
- Aylik getiri
- Kumulatif getiri (bilesik)
- Yillik bilesik (annualized)
- En iyi/en kotu hisse
- Drawdown
- Sharpe orani

JSON dosyalari "gecmis/" klasorunde tutulur, her sistem icin ayri.
"""

import os
import json
import math
from datetime import datetime
import pandas as pd
import numpy as np


GECMIS_KLASORU = "gecmis"


def gecmis_klasoru_olustur():
    """gecmis/ klasoru yoksa olustur."""
    if not os.path.exists(GECMIS_KLASORU):
        os.makedirs(GECMIS_KLASORU)


def gecmis_dosya_yolu(sistem_kodu):
    """sistem_kodu icin JSON dosya yolu doner."""
    return os.path.join(GECMIS_KLASORU, f"{sistem_kodu}.json")


def gecmis_oku(sistem_kodu, portfoy_baslangic=10000, para_birimi="$"):
    """
    Sistemin gecmis JSON dosyasini okur.
    Yoksa bos yapi olusturur.
    """
    gecmis_klasoru_olustur()
    yol = gecmis_dosya_yolu(sistem_kodu)
    
    if not os.path.exists(yol):
        return {
            "sistem_kodu": sistem_kodu,
            "portfoy_baslangic": portfoy_baslangic,
            "para_birimi": para_birimi,
            "olusturma_tarihi": datetime.now().strftime("%Y-%m-%d"),
            "kayitlar": []
        }
    
    with open(yol, 'r', encoding='utf-8') as f:
        return json.load(f)


def gecmis_kaydet(sistem_kodu, veri):
    """Sistemin gecmisini JSON'a kaydeder."""
    gecmis_klasoru_olustur()
    yol = gecmis_dosya_yolu(sistem_kodu)
    
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(veri, f, indent=2, ensure_ascii=False)


def hisse_kapanis_cek(sembol, kaynak_func):
    """
    Tek bir hissenin guncel kapanis fiyatini ceker.
    kaynak_func: fiyat cekme fonksiyonu (yfinance veya bist_data)
    """
    try:
        return kaynak_func(sembol)
    except Exception as e:
        print(f"  [Kapanis] {sembol}: hata {e}")
        return None


def onceki_portfoy_performans_hesapla(onceki_kayit, guncel_fiyatlar):
    """
    Onceki portfoyu guncel fiyatlarla degerleyip aylik getiri hesaplar.
    
    Args:
        onceki_kayit: Onceki ayin kaydi (dict)
        guncel_fiyatlar: {sembol: float} - guncel kapanis fiyatlari
    
    Returns:
        dict: {
            "portfoy_yeni_deger": ...,
            "aylik_getiri_pct": ...,
            "hisse_detaylari": [{sembol, giris, son, getiri_pct}, ...]
        }
    """
    hisseler = onceki_kayit.get("hisseler", [])
    if not hisseler:
        return None
    
    # Her hisse icin yeni deger hesapla
    hisse_detaylari = []
    toplam_yeni_deger = 0
    toplam_giris_tutar = 0
    
    for hisse in hisseler:
        sembol = hisse["sembol"]
        giris_fiyat = hisse.get("giris_fiyat", 0)
        lot = hisse.get("lot", 0)
        
        guncel_fiyat = guncel_fiyatlar.get(sembol)
        
        if guncel_fiyat is None or guncel_fiyat <= 0:
            # Veri yoksa hisse "donmus" varsay (getiri 0)
            yeni_deger = lot * giris_fiyat
            getiri_pct = 0
            durum = "VERI_YOK"
        else:
            yeni_deger = lot * guncel_fiyat
            getiri_pct = ((guncel_fiyat - giris_fiyat) / giris_fiyat) * 100 if giris_fiyat > 0 else 0
            durum = "OK"
        
        giris_tutar = lot * giris_fiyat
        
        hisse_detaylari.append({
            "sembol": sembol,
            "giris_fiyat": giris_fiyat,
            "son_fiyat": guncel_fiyat if guncel_fiyat else giris_fiyat,
            "getiri_pct": round(getiri_pct, 2),
            "giris_tutar": round(giris_tutar, 2),
            "yeni_deger": round(yeni_deger, 2),
            "durum": durum
        })
        
        toplam_yeni_deger += yeni_deger
        toplam_giris_tutar += giris_tutar
    
    aylik_getiri_pct = ((toplam_yeni_deger - toplam_giris_tutar) / toplam_giris_tutar) * 100 if toplam_giris_tutar > 0 else 0
    
    return {
        "portfoy_yeni_deger": round(toplam_yeni_deger, 2),
        "portfoy_giris_deger": round(toplam_giris_tutar, 2),
        "aylik_getiri_pct": round(aylik_getiri_pct, 2),
        "hisse_detaylari": hisse_detaylari
    }


def kumulatif_performans_hesapla(gecmis_veri):
    """
    Tum gecmis kayitlardan kumulatif performans hesaplar.
    
    Returns:
        dict: {
            "portfoy_baslangic": ...,
            "portfoy_guncel": ...,
            "toplam_kar_zarar": ...,
            "toplam_getiri_pct": ...,
            "ay_sayisi": ...,
            "yillik_bilesik_pct": ...,
            "max_drawdown_pct": ...,
            "sharpe": ...
        }
    """
    kayitlar = gecmis_veri.get("kayitlar", [])
    baslangic = gecmis_veri.get("portfoy_baslangic", 10000)
    
    if not kayitlar:
        return {
            "portfoy_baslangic": baslangic,
            "portfoy_guncel": baslangic,
            "toplam_kar_zarar": 0,
            "toplam_getiri_pct": 0,
            "ay_sayisi": 0,
            "yillik_bilesik_pct": 0,
            "max_drawdown_pct": 0,
            "sharpe": 0,
            "kayit_var": False
        }
    
    # Aylik getiri serisi olustur (sadece performans hesaplanmis kayitlardan)
    aylik_getiriler = []
    portfoy_seyir = [baslangic]
    
    for kayit in kayitlar:
        performans = kayit.get("onceki_ay_performans")
        if performans:
            getiri = performans.get("aylik_getiri_pct", 0) / 100
            aylik_getiriler.append(getiri)
            portfoy_seyir.append(portfoy_seyir[-1] * (1 + getiri))
    
    guncel = portfoy_seyir[-1]
    toplam_kar = guncel - baslangic
    toplam_getiri_pct = ((guncel - baslangic) / baslangic) * 100
    ay_sayisi = len(aylik_getiriler)
    
    # Yillik bilesik (annualized)
    if ay_sayisi >= 1:
        yillik_bilesik = (math.pow(guncel / baslangic, 12 / ay_sayisi) - 1) * 100
    else:
        yillik_bilesik = 0
    
    # Max drawdown
    max_drawdown = 0
    if len(portfoy_seyir) > 1:
        peak = portfoy_seyir[0]
        for v in portfoy_seyir:
            if v > peak:
                peak = v
            dd = ((v - peak) / peak) * 100
            if dd < max_drawdown:
                max_drawdown = dd
    
    # Sharpe (en az 3 ay olmali)
    if ay_sayisi >= 3:
        arr = np.array(aylik_getiriler)
        if arr.std() > 0:
            sharpe = (arr.mean() / arr.std()) * math.sqrt(12)
        else:
            sharpe = 0
    else:
        sharpe = 0
    
    return {
        "portfoy_baslangic": round(baslangic, 2),
        "portfoy_guncel": round(guncel, 2),
        "toplam_kar_zarar": round(toplam_kar, 2),
        "toplam_getiri_pct": round(toplam_getiri_pct, 2),
        "ay_sayisi": ay_sayisi,
        "yillik_bilesik_pct": round(yillik_bilesik, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "sharpe": round(sharpe, 2),
        "kayit_var": True,
        "aylik_getiriler": [round(g * 100, 2) for g in aylik_getiriler]
    }


def en_iyi_en_kotu_hisseler(gecmis_veri):
    """Tum gecmis hisselerin performansini analiz edip en iyi/en kotuyu doner."""
    tum_hisseler = []
    
    for kayit in gecmis_veri.get("kayitlar", []):
        performans = kayit.get("onceki_ay_performans")
        if not performans:
            continue
        
        for h in performans.get("hisse_detaylari", []):
            tum_hisseler.append({
                "sembol": h["sembol"],
                "ay": kayit.get("ay_adi", ""),
                "getiri": h.get("getiri_pct", 0)
            })
    
    if not tum_hisseler:
        return None, None
    
    en_iyi = max(tum_hisseler, key=lambda x: x["getiri"])
    en_kotu = min(tum_hisseler, key=lambda x: x["getiri"])
    
    return en_iyi, en_kotu


def yeni_kayit_olustur(top_n_df, kapanis_fiyatlari, tarih, ay_adi, portfoy_buyuklugu, pozisyon_yuzde):
    """
    Yeni bir portfoy kaydi olusturur (henuz performans yok, sadece secimler).
    
    Args:
        top_n_df: Secilen hisseler DataFrame
        kapanis_fiyatlari: {sembol: float}
        tarih: datetime
        ay_adi: "Haziran 2026"
        portfoy_buyuklugu: 10000 veya 100000
        pozisyon_yuzde: 10 veya 20
    """
    pozisyon_tutar = portfoy_buyuklugu * (pozisyon_yuzde / 100)
    
    hisseler = []
    for _, row in top_n_df.iterrows():
        sembol = row["Sembol"]
        kapanis = kapanis_fiyatlari.get(sembol, 0)
        
        if kapanis and kapanis > 0:
            lot = pozisyon_tutar / kapanis
        else:
            lot = 0
        
        hisseler.append({
            "sembol": sembol,
            "giris_fiyat": round(float(kapanis), 4) if kapanis else 0,
            "lot": round(float(lot), 4),
            "tutar": round(pozisyon_tutar, 2),
            "skor": round(float(row.get("Momentum", 0)), 2)
        })
    
    return {
        "tarih": tarih.strftime("%Y-%m-%d"),
        "ay_adi": ay_adi,
        "portfoy_buyuklugu": portfoy_buyuklugu,
        "pozisyon_yuzde": pozisyon_yuzde,
        "hisseler": hisseler,
        "kayit_zamani": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def performans_metni_olustur(kumulatif, gecmis_veri, para_birimi, para_format=",.2f"):
    """Telegram mesaji icin performans metnini olusturur."""
    if not kumulatif.get("kayit_var") or kumulatif.get("ay_sayisi", 0) == 0:
        # Henuz performans kaydi yok
        return None
    
    metin = "<b>📊 PERFORMANS GEÇMİŞİ</b>\n"
    metin += "━━━━━━━━━━━━━━━━━━━━\n"
    
    baslangic = kumulatif["portfoy_baslangic"]
    guncel = kumulatif["portfoy_guncel"]
    kar = kumulatif["toplam_kar_zarar"]
    yuzde = kumulatif["toplam_getiri_pct"]
    ay_sayisi = kumulatif["ay_sayisi"]
    
    metin += f"💰 Başlangıç: {para_birimi}{baslangic:{para_format}}\n"
    metin += f"📈 Güncel değer: {para_birimi}{guncel:{para_format}}\n"
    
    # Kar/zarar
    if kar >= 0:
        metin += f"🟢 Toplam kar: {para_birimi}+{kar:{para_format}} (+{yuzde:.2f}%)\n"
    else:
        metin += f"🔴 Toplam zarar: {para_birimi}{kar:{para_format}} ({yuzde:.2f}%)\n"
    
    metin += f"📅 Dönem: {ay_sayisi} ay\n"
    
    # Yillik bilesik (en az 1 ay varsa)
    yillik = kumulatif["yillik_bilesik_pct"]
    if yillik >= 0:
        metin += f"📊 Yıllık bileşik: +{yillik:.1f}%\n"
    else:
        metin += f"📊 Yıllık bileşik: {yillik:.1f}%\n"
    
    # Max drawdown (en az 2 ay varsa anlamli)
    if ay_sayisi >= 2:
        dd = kumulatif["max_drawdown_pct"]
        metin += f"📉 Max düşüş: {dd:.1f}%\n"
    
    # Sharpe (en az 3 ay)
    if ay_sayisi >= 3:
        sharpe = kumulatif["sharpe"]
        metin += f"⚡ Sharpe: {sharpe:.2f}\n"
    
    # Son ayin detayi
    kayitlar = gecmis_veri.get("kayitlar", [])
    if len(kayitlar) >= 2:
        # Son kayit yeni portfoy, ondan onceki "gecen ay"
        gecen_ay_kayit = kayitlar[-1]
        performans = gecen_ay_kayit.get("onceki_ay_performans")
        
        if performans:
            metin += "\n<b>🗓️ Geçen Ay Detay</b>\n"
            aylik_getiri = performans.get("aylik_getiri_pct", 0)
            metin += f"   Aylık: {aylik_getiri:+.2f}%\n"
            
            # En iyi/en kotu hisseler (gecen aydan)
            hisseler = performans.get("hisse_detaylari", [])
            if hisseler:
                hisseler_sirali = sorted(hisseler, key=lambda x: x.get("getiri_pct", 0), reverse=True)
                
                en_iyi = hisseler_sirali[0]
                en_kotu = hisseler_sirali[-1]
                
                metin += f"   🏆 En iyi: {en_iyi['sembol']} {en_iyi['getiri_pct']:+.1f}%\n"
                metin += f"   📉 En kötü: {en_kotu['sembol']} {en_kotu['getiri_pct']:+.1f}%\n"
    
    # Aylik dagilim (son 6 ay)
    aylik_getiriler = kumulatif.get("aylik_getiriler", [])
    if len(aylik_getiriler) >= 1:
        son_aylar = aylik_getiriler[-6:]
        metin += "\n<b>📊 Son Aylar:</b>\n"
        for i, getiri in enumerate(son_aylar):
            isaret = "+" if getiri >= 0 else ""
            metin += f"   • Ay {len(aylik_getiriler) - len(son_aylar) + i + 1}: {isaret}{getiri:.1f}%\n"
    
    metin += "━━━━━━━━━━━━━━━━━━━━"
    
    return metin
