<div align="center">
  <img src="assets/sirius_banner.png" alt="Sirius" width="100%"/>
</div>

<p align="center">
  <em>A signal arrives before the rise.</em>
</p>

<p align="center">
  <a href="https://github.com/Mimar2026/sirius/actions/workflows/monthly_run.yml">
    <img src="https://github.com/Mimar2026/sirius/actions/workflows/monthly_run.yml/badge.svg" alt="Monthly Run Status"/>
  </a>
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"/>
  <img src="https://img.shields.io/badge/systems-5_parallel-success.svg" alt="5 Parallel Systems"/>
  <img src="https://img.shields.io/badge/markets-US_+_BIST-orange.svg" alt="US + BIST"/>
</p>

---

# Sirius — Multi-Strategy Momentum Portföy Motoru

ABD ve Türk hisse senedi piyasaları için aylık çalışan momentum tabanlı portföy seçim sistemi. **5 paralel strateji** her ay otomatik olarak top portföyleri seçer ve Telegram üzerinden bildirim gönderir.

İsim Antik Mısır'da Nil'in taşmasını müjdeleyen Sirius yıldızından gelir. Gözlenebilir bir sinyal, sonraki bereketin habercisidir. Sistem de aynı mantıkla çalışır: her ay başında bir sinyal verir, ardından yükseliş gelir.

## Sistem Mimarisi
SIRIUS - 5 Paralel Momentum Sistemi
═══════════════════════════════════
ABD Piyasası (S&P 500 + Nasdaq 100, ~516 hisse)
├── 🌟 Saf Momentum         → Top 10 (en güçlü 10)
├── 🌐 Sektör Diverse       → Top 10 (max 3 hisse/sektör)
└── 💎 Quality Momentum     → Top 10 (momentum + ROE + marj)
BIST (Borsa İstanbul)
├── 🇹🇷 BIST Katılım        → Top 5 (237 katılım hissesi)
└── 🇹🇷 BIST Genel          → Top 5 (568 BIST hisse)
OTOMATİZASYON
├── Her ayın 1'i 09:00 TSİ otomatik çalışır
├── 5 paralel job, GitHub Actions
├── 5 ayrı Telegram bildirimi
├── Hata yakalama + retry mantığı
└── Maliyet: $0

## Özellikler

- **Tam otonom** — Her ayın 1'i 09:00 TSİ GitHub Actions üzerinde otomatik çalışır
- **Çoklu strateji** — 5 farklı stratejinin paralel sonuçlarını alabilirsin
- **İki pazar** — ABD ve BIST için ayrı sistemler
- **Telegram entegrasyonu** — Anlık bildirim, otomatik mesaj
- **Hibrit veri kaynağı** — BIST için borsapy + isyatirimhisse (failover)
- **Hata yönetimi** — Retry mantığı + Telegram'a hata bildirimi
- **Sıfır maliyet** — Tüm bileşenler ücretsiz

## ABD Stratejileri (Backtest Sonuçları)

7 yıllık tarihsel veride 3 farklı ABD stratejisinin karşılaştırması:

| Metrik | Saf Momentum | Sektör Diverse | Quality | S&P 500 |
|---|---|---|---|---|
| Toplam Getiri (6 yıl) | **%1.818** | %1.243 | %837 | %167 |
| Yıllık Bileşik | **%63,62** | %54,17 | %45,20 | %17,75 |
| Sharpe Oranı | 1,67 | 1,64 | **1,68** | 1,13 |
| Maksimum Drawdown | -%20,40 | -%20,25 | **-%15,74** | -%23,93 |
| Kazanma Oranı | %65,28 | %66,67 | **%75,00** | %66,67 |

Backtest dönemi: 2020-06 → 2026-05 (72 ay)

### Stratejilerin Karakteri

- **Saf Momentum:** En yüksek getiri, en yüksek volatilite. Trend takip.
- **Sektör Diverse:** Dengeli, çeşitlendirilmiş. Konsantrasyon riski düşük.
- **Quality Momentum:** En düşük drawdown, en yüksek Sharpe. Risk-ayarlı şampiyon.

## BIST Stratejileri

| Strateji | Evren | Top N | Açıklama |
|---|---|---|---|
| **BIST Katılım** | 237 katılım hissesi | 5 | İslami finans uyumlu |
| **BIST Genel** | 568 BIST hissesi | 5 | Tüm pazar evreni |

## Sistem Nasıl Çalışır

### Momentum Skoru Hesaplama

Her ay sonunda her hisse için kompozit momentum skoru hesaplanır:

1. Son 3 aylık getiri
2. Son 6 aylık getiri
3. Son 12 aylık getiri

Her getiri yüzdelik dilime çevrilir, üçünün ortalaması alınır. Bu skor sıralamasıyla top N hisse seçilir.

### Strateji Özelleştirmeleri

**Saf Momentum:** Hiç filtre yok, ham sıralama
**Sektör Diverse:** Her sektörden max 3 hisse
**Quality:** Final skor = %60 momentum + %40 quality (ROE + brüt marj)
**BIST Katılım/Genel:** Saf momentum, top 5 seçim

## Otomatik Çalıştırma

Sistem her ayın 1'i 09:00 Türkiye saatinde GitHub Actions üzerinde **5 paralel job** olarak çalışır:

1. GitHub sanal makineleri başlatılır (5 adet, paralel)
2. Bağımlılıklar yüklenir (yfinance, pandas, isyatirimhisse, borsapy vs.)
3. Her sistem kendi evrenini ve veri kaynağını kullanır
4. Top N hisseler seçilir
5. Telegram bot üzerinden 5 ayrı bildirim gönderilir

Tüm süreç ~15-30 dakika sürer ve kullanıcı müdahalesi gerektirmez.

Workflow durumunu görmek için: [Actions sekmesi](https://github.com/Mimar2026/sirius/actions)

## Manuel Çalıştırma

Bağımlılıkları yükle ve istediğin scripti çalıştır:

    pip install -r requirements.txt
    
    # ABD sistemleri
    python momentum_system.py              # Saf momentum
    python momentum_sector_diverse.py      # Sektör diverse
    python momentum_quality.py             # Quality momentum
    
    # BIST sistemleri
    python bist_momentum_katilim.py        # BIST katılım
    python bist_momentum_genel.py          # BIST genel
    
    # Backtest karşılaştırma
    python backtest_compare.py             # 3 ABD stratejisi 7 yıllık karşılaştırma

## Telegram Bildirimi

Sistem her çalıştığında Telegram'a otomatik mesaj gönderir:

    export TELEGRAM_BOT_TOKEN="bot_tokeniniz"
    export TELEGRAM_CHAT_ID="chat_id_niz"

Bot kurulumu için [BotFather](https://t.me/BotFather).

GitHub Actions kullanıyorsan token'ları **Repository Secrets** içinde saklamalısın.

## Dosya Yapısı

    sirius/
    ├── .github/workflows/
    │   └── monthly_run.yml              # Otomatik aylık çalıştırma
    ├── assets/
    │   ├── sirius_avatar.png
    │   ├── sirius_avatar_hd.png
    │   ├── sirius_banner.png
    │   └── ...
    ├── README.md
    ├── requirements.txt
    │
    │── ABD Sistemleri ──
    ├── momentum_system.py               # Saf momentum
    ├── momentum_sector_diverse.py       # Sektör çeşitlendirmeli
    ├── momentum_quality.py              # Quality + momentum
    ├── backtest.py                      # Tek strateji backtest
    ├── backtest_compare.py              # 3 strateji karşılaştırma
    │
    │── BIST Sistemleri ──
    ├── bist_hisseler.py                 # Hisse listeleri (237 + 568)
    ├── bist_data.py                     # Hibrit veri çekme
    ├── bist_momentum_katilim.py         # BIST katılım top 5
    └── bist_momentum_genel.py           # BIST genel top 5

## Veri Kaynakları

### ABD
- **Fiyat:** [yfinance](https://github.com/ranaroussi/yfinance) — Yahoo Finance
- **Evren:** Wikipedia (S&P 500 + Nasdaq 100)
- **Fundamental:** yfinance (ROE, marj, sektör)

### BIST
- **Birincil:** [borsapy](https://github.com/saidsurucu/borsapy) — yfinance benzeri modern API
- **Yedek:** [isyatirimhisse](https://github.com/urazakgul/isyatirimhisse) — İş Yatırım resmi kaynaklı
- **Evren:** KAP resmi endeks listeleri (XKTUM + XUTUM)

## Teknoloji Yığını

Python 3.11, pandas, numpy, yfinance, borsapy, isyatirimhisse, lxml, beautifulsoup4, requests, GitHub Actions, Telegram Bot API.

## Sistem Hakkında Notlar

### Güçlü Yönler
- **5 stratejinin paralel çalışması** — her birinin kendine özgü karakteri
- **2022 ayı piyasasında pozitif getiri** (momentum stratejileri için olağandışı)
- **Sektör ve quality filtreleri** ile risk yönetimi seçenekleri
- **Hibrit veri kaynakları** — failover mantığı ile dayanıklılık
- **Tam otomatik** — her ay 1'i otomatik çalışır

### Riskler ve Sınırlamalar
- **Survivorship bias:** Backtest mevcut endeks üyelerini kullanır
- **İşlem maliyetleri** hesaplanmamış (~%1-3/yıl)
- **Vergi:** Aylık rebalans → yüksek kısa vadeli sermaye kazancı vergisi
- **Konsantrasyon riski:** Saf momentum'da yüksek (Diverse ile azalır)
- **Momentum crash riski:** Trend dönüşlerinde sert düşüşler
- **Quality verisi look-ahead bias:** Backtest yaklaşık sonuç verir

## Yol Haritası

- [x] Temel momentum modeli (3+6+12 ay kompozit skor)
- [x] Backtest motoru (7 yıllık tarihsel test)
- [x] Telegram bildirimi
- [x] GitHub Actions ile otomatik aylık çalıştırma
- [x] Hata yakalama ve retry mantığı
- [x] Sektör çeşitlendirme stratejisi
- [x] Quality momentum stratejisi
- [x] 3 ABD stratejisinin karşılaştırmalı backtest'i
- [x] BIST Katılım modeli (top 5)
- [x] BIST Genel modeli (top 5)
- [x] Hibrit BIST veri kaynağı (borsapy + isyatirimhisse)
- [ ] BIST için karşılaştırmalı backtest
- [ ] Geçmiş seçimler logu (commit history)
- [ ] QuantConnect entegrasyonu (point-in-time veri)
- [ ] Düşük volatilite filtresi
- [ ] Karma portföy stratejisi (Momentum + Diverse + Quality)
- [ ] Dashboard (web arayüzü)

## Uyarı

Bu proje **eğitim ve araştırma amaçlıdır**. Yatırım tavsiyesi değildir. Geçmiş performans gelecek getiri garantisi vermez. Kullanmadan önce kendi araştırmanı yap ve riski anla.

## Lisans

MIT License

---

<div align="center">
  <sub>Built with care, guided by a star.</sub>
  <br/>
  <sub>⭐ <a href="https://github.com/Mimar2026/sirius">github.com/Mimar2026/sirius</a></sub>
</div>
