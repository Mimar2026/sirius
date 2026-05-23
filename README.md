<div align="center">
  <img src="assets/sirius_banner.png" alt="Sirius" width="100%"/>
</div>

<p align="center">
  <em>A signal arrives before the rise.</em>
</p>

---

# Sirius — Momentum Portfolio Engine

ABD hisse senetleri icin aylik calisan momentum tabanli portfoy secim sistemi. S&P 500 ve Nasdaq 100 evreninden her ay basinda en guclu momentum sergileyen 10 hisseyi secer.

Isim Antik Misir`da Nil`in tasmasini mujdeleyen Sirius yildizindan gelir. Gozlenebilir bir sinyal, sonraki bereketin habercisidir. Bu sistem de ayni mantikla calisir: her ay basinda bir sinyal verir, ardindan yukselis gelir.

## Ozet Istatistikler (Backtest)

| Metrik | Sirius Portfoy | S&P 500 (SPY) |
|---|---|---|
| Toplam Getiri (6 yil) | **%1.806** | %167 |
| Yillik Bilesik Getiri | **%63,44** | %17,80 |
| Sharpe Orani | **1,67** | 1,13 |
| Maksimum Drawdown | **-%20,40** | -%23,93 |
| Kazandiran Ay Orani | **%65,28** | - |

Backtest donemi: 2020-06 -> 2026-05 (72 ay)

## Yillik Getiri Dagilimi

| Yil | Sirius | S&P 500 | Fark |
|---|---|---|---|
| 2020 | +%76,21 | +%24,42 | **+%51,79** |
| 2021 | +%31,26 | +%28,73 | +%2,54 |
| 2022 | +%10,66 | -%18,18 | **+%28,83** |
| 2023 | +%39,94 | +%26,18 | +%13,76 |
| 2024 | +%76,16 | +%24,89 | **+%51,28** |
| 2025 | +%57,75 | +%17,72 | **+%40,03** |
| 2026 (5 ay) | +%91,52 | +%9,93 | **+%81,58** |

Sistemin en dikkat cekici ozelligi 2022 ayi piyasasinda pozitif getiri saglamasi. S&P 500 -%18 kaybederken Sirius +%10,66 kazandirdi. Bu, coklu lookback (3+6+12 ay) yapisinin trend donuslerini hizli yakalamasindan kaynaklanir.

## Sistem Nasil Calisir

### Evren
- S&P 500 uyeleri (~503 hisse)
- Nasdaq 100 uyeleri (~101 hisse)
- Birlesik evren: ~516 hisse
- Veri filtresi sonrasi: ~500 hisse

### Skor Hesaplama
Her ay sonunda her hisse icin kompozit momentum skoru hesaplanir:

1. Son 3 aylik getiri
2. Son 6 aylik getiri
3. Son 12 aylik getiri

Her getiri yuzdelik dilime cevrilir, ucunun ortalamasi alinir. En yuksek skorlu 10 hisse secilir.

### Portfoy Kurallari
- **Hisse sayisi:** 10
- **Agirlik:** Esit (%10 her hisse)
- **Rebalans:** Aylik (her ayin ilk islem gunu)
- **Cikis kurali:** Skor siralamasinda ilk 10`un disina cikanlar elenir

## Kurulum

```bash
# Bagimliliklari yukle
pip install -r requirements.txt

# Bu ayin top 10`unu gor
python momentum_system.py

# Tam backtest calistir
python backtest.py
```

## Dosya Yapisi

```
sirius/
|-- README.md
|-- requirements.txt
|-- momentum_system.py
|-- backtest.py
|-- .gitignore
`-- assets/
    |-- sirius_avatar.svg
    |-- sirius_avatar.png
    |-- sirius_avatar_hd.png
    |-- sirius_banner.svg
    `-- sirius_banner.png
```

## Sistem Hakkinda Notlar

### Guclu Yonler
- **Tutarli outperformance:** 6 yilin 6`sinda da S&P 500`u yendi
- **2022 ayi piyasasinda pozitif getiri** -- momentum stratejileri icin olagandisi
- **Dusuk max drawdown** -- Coklu lookback rejim degisikliklerini hizli yakalar
- **Yuksek Sharpe orani** (1,67) -- Risk-ayarli getiri ustun

### Riskler
- **Survivorship bias:** Backtest su anki S&P 500 uyelerini kullanir. Gercek getiri %5-15 daha dusuk olabilir.
- **Islem maliyetleri** hesaplanmamis (~%1-3/yil azaltabilir)
- **Vergi:** Aylik rebalans nedeniyle kisa vadeli sermaye kazanci vergisi yuksek
- **Konsantrasyon riski:** Top 10 agirlikli olarak teknoloji/yari iletken sektorunde
- **Momentum crash riski:** Trend donuslerinde sert dususler yasanabilir

## Veri Kaynaklari

- **Fiyat verisi:** [yfinance](https://github.com/ranaroussi/yfinance) -- ucretsiz, sinirsiz
- **Hisse listesi:** Wikipedia (S&P 500, Nasdaq 100)

## Yol Haritasi

- [ ] **Quality faktoru** ekleme (ROE, kar buyumesi, brut marj)
- [ ] **Sektor cesitlendirme** kurali
- [ ] **Dusuk volatilite** filtresi
- [ ] **QuantConnect** entegrasyonu (point-in-time veri)
- [ ] **BIST evrenine uyarlama** (katilim vs genel)
- [ ] **GitHub Actions** ile otomatik aylik calistirma
- [ ] **Dashboard** (web arayuzu)

## Uyari

Bu proje **egitim ve arastirma amaclidir**. Yatirim tavsiyesi degildir. Gecmis performans gelecek getiri garantisi vermez. Yatirim kararlariniz ve sonuclari size aittir.

## Lisans

MIT License

---

<div align="center">
  <sub>Built with care, guided by a star.</sub>
</div>