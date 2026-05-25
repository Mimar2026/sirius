"""
Sirius - 3 Strateji Karsilastirmali Backtest

Uc stratejiyi ayni 7 yillik veride test eder:
1. Saf Momentum
2. Sektor Cesitlendirme  
3. Quality Momentum

Sonuc: hangi strateji daha iyi performans gostermis?

NOT: Quality ve Diverse versiyonlarinda hafif look-ahead bias var
(fundamental ve sektor verisi gunumuz, tarihi degil).
"""

import yfinance as yf
import pandas as pd
import numpy as np
import time
import traceback
from momentum_system import hisse_evrenini_cek


# ====================================================================
# YARDIMCI FONKSIYONLAR
# ====================================================================

def momentum_skoru_df(aylik_fiyatlar, i, lookback_aylar=[3, 6, 12]):
    """Belirli bir tarihte momentum skoru hesaplar."""
    getiriler = {}
    for ay in lookback_aylar:
        simdiki = aylik_fiyatlar.iloc[i]
        gecmis = aylik_fiyatlar.iloc[i - ay]
        getiriler[ay] = ((simdiki / gecmis) - 1) * 100
    
    skor_df = pd.DataFrame(getiriler).dropna()
    if len(skor_df) == 0:
        return None
    
    for ay in lookback_aylar:
        skor_df["rank_" + str(ay)] = skor_df[ay].rank(pct=True) * 100
    
    skor_df["Momentum"] = skor_df[["rank_" + str(ay) for ay in lookback_aylar]].mean(axis=1)
    return skor_df.sort_values("Momentum", ascending=False)


def istatistikler(getiri_serisi):
    """Performans istatistiklerini hesaplar."""
    kumulatif = (1 + getiri_serisi / 100).cumprod() * 100
    toplam = kumulatif.iloc[-1] - 100
    yillik = ((kumulatif.iloc[-1] / 100) ** (12 / len(getiri_serisi)) - 1) * 100
    sharpe = (getiri_serisi.mean() / getiri_serisi.std()) * np.sqrt(12) if getiri_serisi.std() > 0 else 0
    
    running_max = kumulatif.cummax()
    drawdown = (kumulatif - running_max) / running_max * 100
    
    return {
        "Toplam Getiri %": round(toplam, 2),
        "Yillik Bilesik %": round(yillik, 2),
        "Sharpe": round(sharpe, 2),
        "Max Drawdown %": round(drawdown.min(), 2),
        "Kazanma Orani %": round((getiri_serisi > 0).sum() / len(getiri_serisi) * 100, 2)
    }


# ====================================================================
# 3 STRATEJI BACKTEST
# ====================================================================

def backtest_saf_momentum(aylik_fiyatlar, top_n=10):
    """1. Saf Momentum stratejisi backtest."""
    en_uzun = 12
    getiri_listesi = []
    
    for i in range(en_uzun, len(aylik_fiyatlar) - 1):
        skor_df = momentum_skoru_df(aylik_fiyatlar, i)
        if skor_df is None or len(skor_df) < top_n:
            continue
        
        top_secim = skor_df.head(top_n).index.tolist()
        
        simdi = aylik_fiyatlar.iloc[i][top_secim]
        gelecek = aylik_fiyatlar.iloc[i + 1][top_secim].dropna()
        ortak = simdi.index.intersection(gelecek.index)
        
        if len(ortak) == 0:
            continue
        
        hisse_getirileri = (gelecek[ortak] / simdi[ortak]) - 1
        getiri_listesi.append({
            "tarih": aylik_fiyatlar.index[i + 1],
            "getiri": hisse_getirileri.mean() * 100
        })
    
    return pd.DataFrame(getiri_listesi).set_index("tarih")


def backtest_diverse(aylik_fiyatlar, sektor_dict, top_n=10, max_sektor=3):
    """2. Sektor Cesitlendirmeli Momentum backtest."""
    en_uzun = 12
    getiri_listesi = []
    
    for i in range(en_uzun, len(aylik_fiyatlar) - 1):
        skor_df = momentum_skoru_df(aylik_fiyatlar, i)
        if skor_df is None:
            continue
        
        # Sektor cesitlendirme uygula
        sektor_sayilari = {}
        secilen = []
        
        # Top 50 icinden sektor kuralina gore filtrele
        top50 = skor_df.head(50)
        for sembol in top50.index:
            sektor = sektor_dict.get(sembol, "Unknown")
            mevcut = sektor_sayilari.get(sektor, 0)
            
            if mevcut < max_sektor:
                secilen.append(sembol)
                sektor_sayilari[sektor] = mevcut + 1
                
                if len(secilen) >= top_n:
                    break
        
        if len(secilen) < top_n:
            continue
        
        simdi = aylik_fiyatlar.iloc[i][secilen]
        gelecek = aylik_fiyatlar.iloc[i + 1][secilen].dropna()
        ortak = simdi.index.intersection(gelecek.index)
        
        if len(ortak) == 0:
            continue
        
        hisse_getirileri = (gelecek[ortak] / simdi[ortak]) - 1
        getiri_listesi.append({
            "tarih": aylik_fiyatlar.index[i + 1],
            "getiri": hisse_getirileri.mean() * 100
        })
    
    return pd.DataFrame(getiri_listesi).set_index("tarih")


def backtest_quality(aylik_fiyatlar, fundamentals, top_n=10):
    """3. Quality Momentum backtest."""
    en_uzun = 12
    getiri_listesi = []
    
    for i in range(en_uzun, len(aylik_fiyatlar) - 1):
        skor_df = momentum_skoru_df(aylik_fiyatlar, i)
        if skor_df is None:
            continue
        
        # Top 50 al
        top50 = skor_df.head(50).copy()
        
        # Fundamental verileri ekle
        for sembol in top50.index:
            f = fundamentals.get(sembol, {})
            top50.loc[sembol, "ROE"] = f.get("ROE")
            top50.loc[sembol, "BrutMarj"] = f.get("BrutMarj")
            top50.loc[sembol, "PiyasaDegeri_Mr"] = f.get("PiyasaDegeri_Mr")
        
        # Filtrele
        filtreli = top50[
            (top50["ROE"].notna()) &
            (top50["BrutMarj"].notna()) &
            (top50["PiyasaDegeri_Mr"] >= 2)
        ].copy()
        
        if len(filtreli) < top_n:
            # Yeterli kalmadiysa sade momentum kullan
            top_secim = top50.head(top_n).index.tolist()
        else:
            # Quality skor
            filtreli["ROE_R"] = filtreli["ROE"].rank(pct=True) * 100
            filtreli["Marj_R"] = filtreli["BrutMarj"].rank(pct=True) * 100
            filtreli["Quality"] = (filtreli["ROE_R"] + filtreli["Marj_R"]) / 2
            filtreli["Final"] = filtreli["Momentum"] * 0.6 + filtreli["Quality"] * 0.4
            filtreli = filtreli.sort_values("Final", ascending=False)
            top_secim = filtreli.head(top_n).index.tolist()
        
        simdi = aylik_fiyatlar.iloc[i][top_secim]
        gelecek = aylik_fiyatlar.iloc[i + 1][top_secim].dropna()
        ortak = simdi.index.intersection(gelecek.index)
        
        if len(ortak) == 0:
            continue
        
        hisse_getirileri = (gelecek[ortak] / simdi[ortak]) - 1
        getiri_listesi.append({
            "tarih": aylik_fiyatlar.index[i + 1],
            "getiri": hisse_getirileri.mean() * 100
        })
    
    return pd.DataFrame(getiri_listesi).set_index("tarih")


# ====================================================================
# YARDIMCI: Fundamental/Sektor toplu cekme
# ====================================================================

def topla_fundamental_ve_sektor(semboller):
    """Tum hisseler icin fundamental ve sektor bilgisini ceker."""
    print("  Toplam " + str(len(semboller)) + " hisse icin veri cekiliyor (~5-10 dakika)...")
    
    sektor_dict = {}
    fundamentals = {}
    
    for i, sembol in enumerate(semboller):
        try:
            info = yf.Ticker(sembol).info
            
            sektor_dict[sembol] = info.get("sector", "Unknown")
            
            roe = info.get("returnOnEquity")
            brut = info.get("grossMargins")
            piy = info.get("marketCap")
            
            fundamentals[sembol] = {
                "ROE": roe * 100 if roe is not None else None,
                "BrutMarj": brut * 100 if brut is not None else None,
                "PiyasaDegeri_Mr": piy / 1_000_000_000 if piy else None,
            }
            
            if (i + 1) % 50 == 0:
                print("    " + str(i + 1) + "/" + str(len(semboller)) + " tamamlandi...")
            
            time.sleep(0.05)
        except Exception:
            sektor_dict[sembol] = "Unknown"
            fundamentals[sembol] = {"ROE": None, "BrutMarj": None, "PiyasaDegeri_Mr": None}
    
    return sektor_dict, fundamentals


# ====================================================================
# ANA FONKSIYON
# ====================================================================

def main():
    print("=" * 70)
    print("SIRIUS - 3 STRATEJI KARSILASTIRMALI BACKTEST")
    print("=" * 70)
    
    # Adim 1: Hisse evreni
    print("\n[1/6] Hisse evreni cekiliyor...")
    semboller = hisse_evrenini_cek()
    print("  " + str(len(semboller)) + " hisse")
    
    # Adim 2: 7 yillik fiyat verisi
    print("\n[2/6] 7 yillik fiyat verisi cekiliyor (3-5 dakika)...")
    veri = yf.download(semboller, period="7y", interval="1d", progress=True, auto_adjust=True)
    fiyatlar = veri["Close"]
    aylik = fiyatlar.resample("ME").last()
    yeterli = aylik.notna().sum() / len(aylik) * 100
    aylik = aylik[yeterli[yeterli >= 80].index.tolist()]
    print("  " + str(aylik.shape[1]) + " hisse / " + str(aylik.shape[0]) + " ay")
    
    # Adim 3: Sektor + Fundamental veriler (tek seferde)
    print("\n[3/6] Sektor ve fundamental veriler cekiliyor (5-10 dakika)...")
    sektor_dict, fundamentals = topla_fundamental_ve_sektor(aylik.columns.tolist())
    print("  Tamamlandi")
    
    # Adim 4: 3 backtest
    print("\n[4/6] Backtest 1: Saf Momentum...")
    sonuc1 = backtest_saf_momentum(aylik, top_n=10)
    print("  " + str(len(sonuc1)) + " ay simulasyonu")
    
    print("\n[5/6] Backtest 2: Sektor Diverse...")
    sonuc2 = backtest_diverse(aylik, sektor_dict, top_n=10, max_sektor=3)
    print("  " + str(len(sonuc2)) + " ay simulasyonu")
    
    print("\n[6/6] Backtest 3: Quality Momentum...")
    sonuc3 = backtest_quality(aylik, fundamentals, top_n=10)
    print("  " + str(len(sonuc3)) + " ay simulasyonu")
    
    # SPY kiyaslamasi
    print("\nSPY kiyaslamasi...")
    spy = yf.download("SPY", start=aylik.index[0], end=aylik.index[-1], progress=False)
    spy_getiri = spy["Close"].resample("ME").last().pct_change() * 100
    
    # Sonuclari hizalama (en kisa donemi al)
    ortak_baslangic = max(sonuc1.index[0], sonuc2.index[0], sonuc3.index[0])
    ortak_son = min(sonuc1.index[-1], sonuc2.index[-1], sonuc3.index[-1])
    
    s1 = sonuc1.loc[ortak_baslangic:ortak_son]["getiri"]
    s2 = sonuc2.loc[ortak_baslangic:ortak_son]["getiri"]
    s3 = sonuc3.loc[ortak_baslangic:ortak_son]["getiri"]
    sp = spy_getiri.reindex(s1.index).dropna()
    
    # Istatistikleri hesapla
    i1 = istatistikler(s1)
    i2 = istatistikler(s2)
    i3 = istatistikler(s3)
    isp = istatistikler(sp) if len(sp) > 0 else {}
    
    # SONUCLAR
    print("\n" + "=" * 80)
    print("SONUCLAR")
    print("=" * 80)
    print("Donem: " + str(ortak_baslangic.date()) + " - " + str(ortak_son.date()))
    print("Ay sayisi: " + str(len(s1)))
    print()
    
    # Tablo
    metrikler = ["Toplam Getiri %", "Yillik Bilesik %", "Sharpe", "Max Drawdown %", "Kazanma Orani %"]
    print("{:<22} {:>12} {:>12} {:>12} {:>12}".format("Metrik", "Momentum", "Diverse", "Quality", "SPY"))
    print("-" * 75)
    for m in metrikler:
        v1 = i1.get(m, "-")
        v2 = i2.get(m, "-")
        v3 = i3.get(m, "-")
        vsp = isp.get(m, "-")
        print("{:<22} {:>12} {:>12} {:>12} {:>12}".format(m, str(v1), str(v2), str(v3), str(vsp)))
    
    # Yillik dagilim
    print("\n" + "=" * 80)
    print("YILLIK GETIRI DAGILIMI")
    print("=" * 80)
    
    df_yillik = pd.DataFrame({
        "Momentum": s1,
        "Diverse": s2,
        "Quality": s3,
        "SPY": sp
    })
    df_yillik["yil"] = df_yillik.index.year
    
    yillik = df_yillik.groupby("yil").apply(
        lambda x: pd.Series({
            col: round(((1 + x[col].dropna() / 100).prod() - 1) * 100, 2)
            for col in ["Momentum", "Diverse", "Quality", "SPY"]
        })
    )
    print(yillik.to_string())
    
    # Hangi kazandi?
    print("\n" + "=" * 80)
    print("KAZANAN STRATEJI")
    print("=" * 80)
    
    en_yuksek_getiri = max(i1["Toplam Getiri %"], i2["Toplam Getiri %"], i3["Toplam Getiri %"])
    en_yuksek_sharpe = max(i1["Sharpe"], i2["Sharpe"], i3["Sharpe"])
    
    if i1["Toplam Getiri %"] == en_yuksek_getiri:
        print("En yuksek getiri:  MOMENTUM (%" + str(i1["Toplam Getiri %"]) + ")")
    elif i2["Toplam Getiri %"] == en_yuksek_getiri:
        print("En yuksek getiri:  DIVERSE (%" + str(i2["Toplam Getiri %"]) + ")")
    else:
        print("En yuksek getiri:  QUALITY (%" + str(i3["Toplam Getiri %"]) + ")")
    
    if i1["Sharpe"] == en_yuksek_sharpe:
        print("En iyi Sharpe:     MOMENTUM (" + str(i1["Sharpe"]) + ")")
    elif i2["Sharpe"] == en_yuksek_sharpe:
        print("En iyi Sharpe:     DIVERSE (" + str(i2["Sharpe"]) + ")")
    else:
        print("En iyi Sharpe:     QUALITY (" + str(i3["Sharpe"]) + ")")
    
    en_iyi_dd = max(i1["Max Drawdown %"], i2["Max Drawdown %"], i3["Max Drawdown %"])
    if i1["Max Drawdown %"] == en_iyi_dd:
        print("En az drawdown:    MOMENTUM (" + str(i1["Max Drawdown %"]) + "%)")
    elif i2["Max Drawdown %"] == en_iyi_dd:
        print("En az drawdown:    DIVERSE (" + str(i2["Max Drawdown %"]) + "%)")
    else:
        print("En az drawdown:    QUALITY (" + str(i3["Max Drawdown %"]) + "%)")
    
    print("\nNot: Quality ve Diverse'te hafif look-ahead bias var (fundamental/sektor")
    print("verisi bugunkudur). Saf Momentum tam gercekci tarihsel test.")


if __name__ == "__main__":
    main()
