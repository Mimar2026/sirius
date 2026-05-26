"""
Sirius - Ortak Yardimci Fonksiyonlar

Bu dosya tum sistemlerin (ABD ve BIST) ortak kullandigi:
- Risk hesaplama
- Hedef/stop fiyat hesaplama
- Portfoy bilgisi
- Detayli Telegram mesaji olusturma

icin yardimci fonksiyonlari icerir.
"""

import pandas as pd


# ====================================================================
# PORTFOY BUYUKLUKLERI (sabit, bakiye guncellemesi icin buradan degistir)
# ====================================================================

PORTFOY_ABD = 10000      # USD - her ABD sistemi icin
PORTFOY_BIST = 100000    # TL - her BIST sistemi icin

POZISYON_YUZDE_ABD = 10   # 10 hisse oldugu icin %10
POZISYON_YUZDE_BIST = 20  # 5 hisse oldugu icin %20


# ====================================================================
# AY ISIMLERI
# ====================================================================

AY_ISIMLERI = {
    1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
    5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
    9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik"
}


def son_fiyat_ve_ortalama_hesapla(aylik_fiyatlar, gunluk_fiyatlar=None):
    """Son kapanis + 30 gun ortalama + volatilite hesaplar."""
    sonuc = {}
    
    if gunluk_fiyatlar is None:
        if aylik_fiyatlar is None:
            return sonuc
        for sembol in aylik_fiyatlar.columns:
            if pd.notna(aylik_fiyatlar[sembol].iloc[-1]):
                sonuc[sembol] = {
                    "kapanis": float(aylik_fiyatlar[sembol].iloc[-1]),
                    "ort_30": float(aylik_fiyatlar[sembol].iloc[-1]),
                    "volatilite": 0.0
                }
        return sonuc
    
    son_30 = gunluk_fiyatlar.tail(30)
    
    for sembol in gunluk_fiyatlar.columns:
        seri = gunluk_fiyatlar[sembol].dropna()
        if len(seri) == 0:
            continue
        
        kapanis = float(seri.iloc[-1])
        son_30_seri = son_30[sembol].dropna()
        ort_30 = float(son_30_seri.mean()) if len(son_30_seri) > 0 else kapanis
        
        getiri = seri.pct_change().dropna().tail(30)
        volatilite = float(getiri.std() * 100) if len(getiri) > 0 else 0.0
        
        sonuc[sembol] = {
            "kapanis": kapanis,
            "ort_30": ort_30,
            "volatilite": volatilite
        }
    
    return sonuc


def hedef_ve_stop_hesapla(row, kapanis):
    """Hedef fiyat ve stop-loss hesaplar."""
    if kapanis is None or kapanis <= 0:
        return None, None, None, None
    
    skor = row.get("Momentum", 0)
    
    # Hedef
    if skor > 99.5:
        hedef_yuzde = 30
    else:
        hedef_yuzde = 25
    hedef = kapanis * (1 + hedef_yuzde / 100)
    
    # Stop
    stop_yuzde = 15
    stop = kapanis * (1 - stop_yuzde / 100)
    
    return hedef, hedef_yuzde, stop, stop_yuzde


def risk_seviyesi_hesapla(row, fiyat_bilgi=None):
    """Her hisse icin 1-5 arasi risk skoru."""
    risk = 0
    
    if fiyat_bilgi and fiyat_bilgi.get("volatilite", 0) > 5:
        risk += 1
    
    getiri_12 = row.get("12 Ay %", 0)
    if pd.notna(getiri_12):
        if getiri_12 > 500:
            risk += 2
        elif getiri_12 > 300:
            risk += 1
    
    getiri_6 = row.get("6 Ay %", 0)
    if pd.notna(getiri_6):
        if getiri_6 > 200:
            risk += 1
    
    skor = row.get("Momentum", 0)
    if skor > 99.5:
        risk += 1
    
    risk = min(risk, 5)
    
    if risk == 0:
        gosterge = "🟢 Risk: 0/5"
    elif risk == 1:
        gosterge = "⚠️ Risk: 1/5"
    elif risk == 2:
        gosterge = "⚠️⚠️ Risk: 2/5"
    elif risk == 3:
        gosterge = "⚠️⚠️⚠️ Risk: 3/5"
    elif risk == 4:
        gosterge = "🔴 Risk: 4/5"
    else:
        gosterge = "🔴🔴 Risk: 5/5"
    
    return risk, gosterge


def alim_miktari_hesapla(portfoy_buyuklugu, pozisyon_yuzde, kapanis):
    """
    Her hisse icin net alim miktarini hesaplar.
    
    Args:
        portfoy_buyuklugu: Toplam portfoy (USD veya TL)
        pozisyon_yuzde: Hisse basina yuzde (ABD %10, BIST %20)
        kapanis: Hisse kapanis fiyati
    
    Returns:
        (tutar, hisse_adedi) tuple
    """
    if kapanis is None or kapanis <= 0:
        return None, None
    
    tutar = portfoy_buyuklugu * (pozisyon_yuzde / 100)
    hisse_adedi = tutar / kapanis
    
    return tutar, hisse_adedi


def telegram_mesaji_detayli(
    top_n_df, 
    tarih, 
    sistem_adi,
    sistem_emoji,
    gunluk_fiyatlar=None, 
    aylik_fiyatlar=None,
    para_birimi="$",
    portfoy_buyuklugu=10000,
    pozisyon_yuzde=10,
    para_format=",.0f",
    sektor_dict=None,
    ek_bilgi=None
):
    """
    Detayli aksiyon mesaji olusturur.
    
    Args:
        top_n_df: Secilen hisseler DataFrame
        tarih: Veri tarihi
        sistem_adi: "Saf Momentum", "BIST Katilim" vb.
        sistem_emoji: "🌟", "🇹🇷" vb.
        gunluk_fiyatlar: Gunluk fiyat verisi (volatilite icin)
        aylik_fiyatlar: Aylik fiyat verisi
        para_birimi: "$" veya "₺"
        portfoy_buyuklugu: 10000 (USD) veya 100000 (TL)
        pozisyon_yuzde: 10 (ABD) veya 20 (BIST)
        para_format: ",.0f" (TL icin) veya ",.2f" ($ icin)
        sektor_dict: Sektor bilgisi (varsa)
        ek_bilgi: Ek satir (Quality skoru gibi)
    """
    # Tarih veri tarihidir. Portfoy SONRAKI ay icin gecerli.
    # Ornegin Mayis 31 verisi -> Haziran ayi portfoyu
    if tarih.month == 12:
        portfoy_ay = 1
        portfoy_yil = tarih.year + 1
    else:
        portfoy_ay = tarih.month + 1
        portfoy_yil = tarih.year
    
    ay_adi = AY_ISIMLERI[portfoy_ay]
    yil = portfoy_yil
    
    # Sonraki ay (gecerlilik bitisi icin)
    if portfoy_ay == 12:
        sonraki_ay = "Ocak"
    else:
        sonraki_ay = AY_ISIMLERI[portfoy_ay + 1]
    
    # Fiyat hesapla
    fiyat_dict = son_fiyat_ve_ortalama_hesapla(aylik_fiyatlar, gunluk_fiyatlar) if (gunluk_fiyatlar is not None or aylik_fiyatlar is not None) else {}
    
    # Pozisyon basina tutar
    pozisyon_tutar = portfoy_buyuklugu * (pozisyon_yuzde / 100)
    
    # Mesaj basi
    mesaj = f"<b>{sistem_emoji} SIRIUS {sistem_adi} - {ay_adi} {yil}</b>\n"
    mesaj += "<i>A signal arrives before the rise.</i>\n\n"
    mesaj += f"<b>💰 Portföy: {para_birimi}{portfoy_buyuklugu:{para_format}}</b>\n"
    mesaj += f"<b>📊 Top {len(top_n_df)} Hisse</b> (her hisse %{pozisyon_yuzde} = {para_birimi}{pozisyon_tutar:{para_format}})\n"
    mesaj += "━━━━━━━━━━━━━━━━━━━━\n"
    
    toplam_risk = 0
    
    for i, (_, row) in enumerate(top_n_df.iterrows(), 1):
        sembol = row["Sembol"]
        skor = row["Momentum"]
        getiri_6 = row.get("6 Ay %", 0)
        getiri_12 = row.get("12 Ay %", 0)
        
        f_info = fiyat_dict.get(sembol, {})
        kapanis = f_info.get("kapanis", 0)
        ort_30 = f_info.get("ort_30", 0)
        volatilite = f_info.get("volatilite", 0)
        
        risk_skor, risk_gosterge = risk_seviyesi_hesapla(row, f_info)
        toplam_risk += risk_skor
        
        # Trend yonu
        if kapanis > 0 and ort_30 > 0:
            fark = ((kapanis - ort_30) / ort_30) * 100
            if fark > 5:
                trend = "⬆️"
            elif fark < -5:
                trend = "⬇️"
            else:
                trend = "➡️"
        else:
            trend = "➡️"
        
        # Volatilite
        if volatilite > 5:
            vol_str = f"Yüksek (%{volatilite:.1f})"
        elif volatilite > 3:
            vol_str = f"Orta (%{volatilite:.1f})"
        else:
            vol_str = f"Düşük (%{volatilite:.1f})"
        
        # Hedef ve stop
        hedef, hedef_p, stop, stop_p = hedef_ve_stop_hesapla(row, kapanis)
        
        # Alim miktari
        tutar, hisse_adedi = alim_miktari_hesapla(portfoy_buyuklugu, pozisyon_yuzde, kapanis)
        
        # Hisse blogu
        mesaj += f"\n<b>▸ {i}. {sembol}</b> {trend}"
        if sektor_dict:
            sektor = sektor_dict.get(sembol, "")[:15]
            if sektor:
                mesaj += f" <i>({sektor})</i>"
        mesaj += "\n"
        
        if kapanis > 0:
            mesaj += f"   💵 Giriş: {para_birimi}{kapanis:{para_format}}\n"
            if hedef:
                mesaj += f"   🎯 Hedef: {para_birimi}{hedef:{para_format}} (+{hedef_p}%)\n"
                mesaj += f"   🛑 Stop: {para_birimi}{stop:{para_format}} (-{stop_p}%)\n"
            mesaj += f"   📊 30g ort: {para_birimi}{ort_30:{para_format}}\n"
        
        mesaj += f"   ⚡ Skor: {skor:.1f} | 6A: {getiri_6:+.0f}%"
        if pd.notna(getiri_12):
            mesaj += f" | 12A: {getiri_12:+.0f}%"
        mesaj += "\n"
        
        mesaj += f"   🌡️ Vol: {vol_str}\n"
        mesaj += f"   {risk_gosterge}\n"
        
        if hisse_adedi is not None and hisse_adedi > 0:
            if para_birimi == "$":
                mesaj += f"   💰 Alım: {para_birimi}{tutar:,.0f} ({hisse_adedi:.2f} hisse)\n"
            else:
                mesaj += f"   💰 Alım: {para_birimi}{tutar:,.0f} ({hisse_adedi:.0f} lot)\n"
    
    # Portfoy ozeti
    ort_risk = toplam_risk / len(top_n_df)
    mesaj += "\n━━━━━━━━━━━━━━━━━━━━\n"
    mesaj += "<b>📈 Portföy Özeti</b>\n"
    mesaj += f"   • Ortalama skor: {top_n_df['Momentum'].mean():.1f}/100\n"
    mesaj += f"   • Ortalama 6A: {top_n_df['6 Ay %'].mean():+.0f}%\n"
    
    if "12 Ay %" in top_n_df.columns:
        mesaj += f"   • Ortalama 12A: {top_n_df['12 Ay %'].mean():+.0f}%\n"
    
    mesaj += f"   • Ortalama risk: {ort_risk:.1f}/5\n"
    
    if ort_risk >= 3.5:
        mesaj += "   ⚠️ <b>YÜKSEK RİSK</b>\n"
    elif ort_risk >= 2.5:
        mesaj += "   ⚠️ Orta-yüksek risk\n"
    
    # Sektor dagilimi (varsa)
    if sektor_dict:
        secilen_sektorler = [sektor_dict.get(s, "Unknown") for s in top_n_df["Sembol"].tolist()]
        sektor_dagilimi = {}
        for s in secilen_sektorler:
            sektor_dagilimi[s] = sektor_dagilimi.get(s, 0) + 1
        
        mesaj += "\n<b>🏭 Sektör Dağılımı:</b>\n"
        for sektor, sayi in sorted(sektor_dagilimi.items(), key=lambda x: -x[1]):
            mesaj += f"   • {sektor}: {sayi}\n"
    
    # Ek bilgi (Quality icin ROE vs.)
    if ek_bilgi:
        mesaj += f"\n{ek_bilgi}\n"
    
    # Footer
    mesaj += "\n"
    mesaj += f"📅 Veri: {tarih.strftime('%Y-%m-%d')}\n"
    # Portfoy ayinin son gunu
    if portfoy_ay in [1, 3, 5, 7, 8, 10, 12]:
        son_gun = 31
    elif portfoy_ay == 2:
        # Subat - artik yil kontrolu
        if (portfoy_yil % 4 == 0 and portfoy_yil % 100 != 0) or (portfoy_yil % 400 == 0):
            son_gun = 29
        else:
            son_gun = 28
    else:
        son_gun = 30
    
    mesaj += f"⏳ Geçerli: 1-{son_gun} {ay_adi}\n"
    mesaj += f"🔄 Sonraki: 1 {sonraki_ay} 09:00\n\n"
    mesaj += "<i>⚠️ Yatırım tavsiyesi değildir. Geçmiş performans gelecek garantisi vermez.</i>"
    
    return mesaj
