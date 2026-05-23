"""
Sirius - 7 Yillik Tarihsel Backtest Motoru
"""

import yfinance as yf
import pandas as pd
import numpy as np
from momentum_system import hisse_evrenini_cek


def momentum_backtest(aylik_fiyatlar, top_n=10, lookback_aylar=[3, 6, 12]):
    """Aylik momentum bazli backtest."""
    en_uzun = max(lookback_aylar)
    portfoy_getiriler = []
    
    for i in range(en_uzun, len(aylik_fiyatlar) - 1):
        bugun = aylik_fiyatlar.index[i]
        bir_sonraki = aylik_fiyatlar.index[i + 1]
        
        getiriler = {}
        for ay in lookback_aylar:
            simdiki = aylik_fiyatlar.iloc[i]
            gecmis = aylik_fiyatlar.iloc[i - ay]
            getiriler[ay] = ((simdiki / gecmis) - 1) * 100
        
        skor_df = pd.DataFrame(getiriler).dropna()
        if len(skor_df) < top_n:
            continue
        
        for ay in lookback_aylar:
            skor_df[f"rank_{ay}"] = skor_df[ay].rank(pct=True) * 100
        
        skor_df["toplam"] = skor_df[[f"rank_{ay}" for ay in lookback_aylar]].mean(axis=1)
        top_secim = skor_df.nlargest(top_n, "toplam").index.tolist()
        
        simdi = aylik_fiyatlar.loc[bugun, top_secim]
        gelecek = aylik_fiyatlar.loc[bir_sonraki, top_secim].dropna()
        ortak = simdi.index.intersection(gelecek.index)
        
        if len(ortak) == 0:
            continue
        
        hisse_getirileri = (gelecek[ortak] / simdi[ortak]) - 1
        aylik_getiri = hisse_getirileri.mean() * 100
        
        portfoy_getiriler.append({
            "tarih": bir_sonraki,
            "getiri": aylik_getiri,
            "hisseler": ",".join(top_secim)
        })
    
    return pd.DataFrame(portfoy_getiriler).set_index("tarih")


def istatistikler(getiri_serisi):
    """Performans istatistiklerini hesaplar."""
    kumulatif = (1 + getiri_serisi / 100).cumprod() * 100
    toplam = kumulatif.iloc[-1] - 100
    yillik = ((kumulatif.iloc[-1] / 100) ** (12 / len(getiri_serisi)) - 1) * 100
    sharpe = (getiri_serisi.mean() / getiri_serisi.std()) * np.sqrt(12)
    
    running_max = kumulatif.cummax()
    drawdown = (kumulatif - running_max) / running_max * 100
    
    return {
        "Toplam Getiri %": round(toplam, 2),
        "Yillik Bilesik %": round(yillik, 2),
        "Sharpe": round(sharpe, 2),
        "Max Drawdown %": round(drawdown.min(), 2),
        "Kazanma Orani %": round((getiri_serisi > 0).sum() / len(getiri_serisi) * 100, 2)
    }


def main():
    print("=" * 70)
    print("SIRIUS - 7 YILLIK BACKTEST")
    print("=" * 70)
    
    print("\n[1/4] Hisse evreni cekiliyor...")
    semboller = hisse_evrenini_cek()
    
    print("\n[2/4] 7 yillik veri cekiliyor (3-5 dakika)...")
    veri = yf.download(semboller, period="7y", interval="1d", progress=True, auto_adjust=True)
    fiyatlar = veri["Close"]
    aylik = fiyatlar.resample("ME").last()
    yeterli = aylik.notna().sum() / len(aylik) * 100
    aylik = aylik[yeterli[yeterli >= 80].index.tolist()]
    print(f"  {aylik.shape[1]} hisse / {aylik.shape[0]} ay")
    
    print("\n[3/4] Backtest calistiriliyor...")
    sonuclar = momentum_backtest(aylik, top_n=10)
    
    print("\n[4/4] SPY kiyaslamasi...")
    spy = yf.download("SPY", start=aylik.index[0], end=aylik.index[-1], progress=False)
    spy_getiri = spy["Close"].resample("ME").last().pct_change() * 100
    spy_hizali = spy_getiri.reindex(sonuclar.index).dropna()
    
    p_istat = istatistikler(sonuclar["getiri"])
    s_istat = istatistikler(spy_hizali)
    
    print("\n" + "=" * 70)
    print("SONUCLAR")
    print("=" * 70)
    print(f"Donem: {sonuclar.index[0].date()} - {sonuclar.index[-1].date()}")
    print(f"Ay sayisi: {len(sonuclar)}\n")
    print(f"{'Metrik':<25} {'Sirius':>15} {'SPY':>15}")
    print("-" * 55)
    for m in p_istat:
        print(f"{m:<25} {p_istat[m]:>15} {s_istat.get(m, '-'):>15}")
    
    print("\nYillik dagilim:")
    sonuclar["yil"] = sonuclar.index.year
    yillik = sonuclar.groupby("yil")["getiri"].apply(
        lambda x: ((1 + x/100).prod() - 1) * 100
    ).round(2)
    print(yillik.to_string())


if __name__ == "__main__":
    main()