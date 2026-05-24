"""
Sirius QUALITY - Quality Momentum Versiyonu
Momentum + Quality faktorlerin birlestirildigi versiyon.

Aynı momentum mantigi + ROE, Brut Marj, Kar Buyumesi filtresi.
Hem fiyat trendi guclu hem temelleri saglam hisseleri secer.

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


def fundamental_veri_cek(semboller):
    """
    Verilen sembollerin fundamental bilgisini yfinance'ten ceker.
    Eksik veri olanlar None doner.
    """
    fundamentals = {}
    for sembol in semboller:
        try:
            info = yf.Ticker(sembol).info
            
            roe = info.get("returnOnEquity")
            brut_marj = info.get("grossMargins")
            kar_buyumesi = info.get("earningsGrowth")
            piyasa_degeri = info.get("marketCap")
            sektor = info.get("sector", "Unknown")
            
            fundamentals[sembol] = {
                "ROE": roe * 100 if roe is not None else None,
                "BrutMarj": brut_marj * 100 if brut_marj is not None else None,
                "KarBuyumesi": kar_buyumesi * 100 if kar_buyumesi is not None else None,
                "PiyasaDegeri_Mr": piyasa_degeri / 1_000_000_000 if piyasa_degeri else None,
                "Sektor": sektor
            }
            time.sleep(0.1)
        except Exception:
            fundamentals[sembol] = {
                "ROE": None, "BrutMarj": None, "KarBuyumesi": None,
                "PiyasaDegeri_Mr": None, "Sektor": "Unknown"
            }
    
    return fundamentals


def quality_skoru_hesapla(skor_df, fundamentals):
    """
    Momentum skoruna ek olarak quality skoru hesaplar.
    Final skor = %60 Momentum + %40 Quality
    """
    # Fundamental verileri DataFrame'e cevir
    fundamental_list = []
    for _, row in skor_df.iterrows():
        sembol = row["Sembol"]
        f = fundamentals.get(sembol, {})
        fundamental_list.append({
            "Sembol": sembol,
            "ROE": f.get("ROE"),
            "BrutMarj": f.get("BrutMarj"),
            "KarBuyumesi": f.get("KarBuyumesi"),
            "PiyasaDegeri_Mr": f.get("PiyasaDegeri_Mr"),
            "Sektor": f.get("Sektor", "Unknown")
        })
    
    fund_df = pd.DataFrame(fundamental_list)
    
    # Birlestir
    combined = skor_df.merge(fund_df, on="Sembol", how="left")
    
    # Quality skoru hesaplamak icin yeterli verisi olanlari filtrele
    quality_filter = (
        combined["ROE"].notna() & 
        combined["BrutMarj"].notna() &
        (combined["PiyasaDegeri_Mr"] >= 2)  # Min 2 milyar dolar
    )
    
    quality_eligible = combined[quality_filter].copy()
    
    if len(quality_eligible) < 10:
        print("  UYARI: Quality filtreden gecen hisse az (" + str(len(quality_eligible)) + ")")
        print("  Sadece momentum siralamasi kullanilacak.")
        return combined.sort_values("Momentum", ascending=False)
    
    # Quality sub-skorlari (yuzdelik dilim)
    quality_eligible["ROE_Rank"] = quality_eligible["ROE"].rank(pct=True) * 100
    quality_eligible["Marj_Rank"] = quality_eligible["BrutMarj"].rank(pct=True) * 100
    
    # Kar buyumesi NaN olanlar var, atlat
    if quality_eligible["KarBuyumesi"].notna().sum() >= 5:
        quality_eligible["Buyume_Rank"] = quality_eligible["KarBuyumesi"].rank(pct=True) * 100
        quality_eligible["Quality"] = (
            quality_eligible["ROE_Rank"] + 
            quality_eligible["Marj_Rank"] + 
            quality_eligible["Buyume_Rank"]
        ) / 3
    else:
        # Kar buyumesi verisi yetersizse, sadece ROE + Marj kullan
        quality_eligible["Quality"] = (
            quality_eligible["ROE_Rank"] + 
            quality_eligible["Marj_Rank"]
        ) / 2
    
    # Final skor = %60 Momentum + %40 Quality
    quality_eligible["Final"] = (
        quality_eligible["Momentum"] * 0.6 + 
        quality_eligible["Quality"] * 0.4
    )
    
    return quality_eligible.sort_values("Final", ascending=False)


def telegram_mesaji_olustur_quality(top10, tarih):
    """Quality versiyonu icin Telegram mesaji."""
    ay_isimleri = {
        1: "Ocak", 2: "Subat", 3: "Mart", 4: "Nisan",
        5: "Mayis", 6: "Haziran", 7: "Temmuz", 8: "Agustos",
        9: "Eylul", 10: "Ekim", 11: "Kasim", 12: "Aralik"
    }
    ay_adi = ay_isimleri[tarih.month]
    yil = tarih.year
    
    mesaj = "<b>💎 SIRIUS QUALITY - " + ay_adi + " " + str(yil) + "</b>\n"
    mesaj += "<i>Momentum + Quality versiyonu</i>\n\n"
    mesaj += "<b>Top 10 Hisse:</b>\n"
    mesaj += "<pre>"
    
    for i, (_, row) in enumerate(top10.iterrows(), 1):
        sembol = row["Sembol"]
        final = row.get("Final", row.get("Momentum", 0))
        roe = row.get("ROE")
        roe_str = "{:5.1f}".format(roe) if roe is not None and not pd.isna(roe) else "  N/A"
        mesaj += "{:2}. {:5} | F:{:5.1f} | ROE:{}%\n".format(i, sembol, final, roe_str)
    
    mesaj += "</pre>\n"
    
    # Sektor dagilimi
    if "Sektor" in top10.columns:
        sektor_dagilimi = top10["Sektor"].value_counts()
        mesaj += "\n<b>Sektor Dagilimi:</b>\n"
        for sektor, sayi in sektor_dagilimi.items():
            mesaj += "• " + str(sektor) + ": " + str(sayi) + "\n"
    
    mesaj += "\n📅 Veri: " + tarih.strftime("%Y-%m-%d") + "\n"
    mesaj += "📊 Ort. 6A getiri: {:+.1f}%\n".format(top10["6 Ay %"].mean())
    if "ROE" in top10.columns:
        ort_roe = top10["ROE"].dropna().mean()
        mesaj += "💼 Ort. ROE: {:+.1f}%".format(ort_roe)
    
    return mesaj


def main():
    print("=" * 70)
    print("SIRIUS QUALITY - QUALITY MOMENTUM")
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
        
        # Adim 3: Momentum hesapla (top 50)
        print("\n[3/5] Momentum hesaplaniyor...")
        skor = momentum_skoru_hesapla(aylik)
        top50 = skor.head(50)
        
        # Adim 4: Fundamental veriler cek (50 hisse, ~1 dakika)
        print("\n[4/5] Fundamental veri cekiliyor (~1 dakika)...")
        fundamentals = fundamental_veri_cek(top50["Sembol"].tolist())
        
        # Quality skoru hesapla ve final siralama
        ranked = quality_skoru_hesapla(top50, fundamentals)
        top10 = ranked.head(10)
        
        print("\n" + "=" * 70)
        print("QUALITY TOP 10 (" + str(aylik.index[-1].date()) + ")")
        print("=" * 70)
        
        # Goster
        gosterim_kolonlari = ["Sembol", "Momentum"]
        if "Quality" in top10.columns:
            gosterim_kolonlari.append("Quality")
        if "Final" in top10.columns:
            gosterim_kolonlari.append("Final")
        if "ROE" in top10.columns:
            gosterim_kolonlari.append("ROE")
        if "BrutMarj" in top10.columns:
            gosterim_kolonlari.append("BrutMarj")
        if "Sektor" in top10.columns:
            gosterim_kolonlari.append("Sektor")
        
        print(top10[gosterim_kolonlari].round(2).to_string(index=False))
        print("\nSemboller: " + ", ".join(top10["Sembol"].tolist()))
        
        # Adim 5: Telegram bildirim
        print("\n[5/5] Telegram bildirimi gonderiliyor...")
        telegram_mesaji = telegram_mesaji_olustur_quality(top10, aylik.index[-1])
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
            telegram_hata_gonder("Sirius QUALITY Aylik Calistirma", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")
        
        raise


if __name__ == "__main__":
    main()
