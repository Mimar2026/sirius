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
  <img src="https://img.shields.io/badge/systems-6_parallel-success.svg" alt="6 Parallel Systems"/>
  <img src="https://img.shields.io/badge/markets-US_+_BIST-orange.svg" alt="US + BIST"/>
  <img src="https://img.shields.io/badge/performance-tracked-blueviolet.svg" alt="Performance Tracked"/>
</p>

---

# Sirius — Multi-Strategy Momentum Portföy Motoru

ABD ve Türk hisse senedi piyasaları için aylık çalışan, momentum tabanlı **6 paralel strateji** yöneten otonom portföy seçim sistemi. Her ay başında otomatik çalışır, her stratejinin top hisselerini seçer, performansları takip eder ve Telegram üzerinden detaylı bildirim gönderir.

İsim Antik Mısır'da Nil'in taşmasını müjdeleyen Sirius yıldızından gelir. Gözlenebilir bir sinyal, sonraki bereketin habercisidir. Sistem de aynı mantıkla çalışır: her ay başında bir sinyal verir, ardından yükseliş gelir.

## Sistem MimarisiSIRIUS — 6 PARALEL MOMENTUM SİSTEMİ
═══════════════════════════════════════ABD Piyasası (S&P 500 + Nasdaq 100, ~516 hisse)
├── 🌟 Saf Momentum         → Top 10 (en güçlü 10)
├── 🌐 Sektör Diverse       → Top 10 (max 3 hisse/sektör)
└── 💎 Quality Momentum     → Top 10 (momentum + ROE + marj)BIST (Borsa İstanbul)
├── 🇹🇷 BIST Katılım        → Top 5 (237 katılım hissesi)
├── 🇹🇷 BIST Genel          → Top 5 (568 BIST hissesi)
└── 💎 BIST Quality         → Top 5 (momentum + quality)PORTFOY YÖNETİMİ
├── ABD: 3 × $10,000 (her sistem bağımsız)
├── BIST: 3 × ₺100,000 (her sistem bağımsız)
├── Eşit ağırlık (her hisse %10 ABD, %20 BIST)
└── Bileşik büyüme (kazanç sonraki aya aktarılır)OTOMATİZASYON
├── Her ayın 1'i 09:00 TSİ otomatik çalışır
├── 6 sıralı job, GitHub Actions
├── 6 ayrı Telegram bildirimi
├── Hata yakalama + retry mantığı
├── JSON tabanlı performans takip
└── Maliyet: $0

## Özellikler

- **Tam otonom** — Her ayın 1'i 09:00 TSİ GitHub Actions üzerinde otomatik çalışır
- **6 farklı strateji** — Risk profillerine göre seçim yapma imkanı
- **İki pazar** — ABD ve BIST için ayrı sistemler
- **Performans takip** — Aylık getiri, kümülatif kazanç, Sharpe, drawdown
- **Telegram bildirimi** — Detaylı aksiyon mesajları (giriş, hedef, stop, lot)
- **Hibrit veri kaynağı** — BIST için borsapy + isyatirimhisse failover
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
| **BIST Katılım** | 237 katılım hissesi | 5 | İslami finans uyumlu, saf momentum |
| **BIST Genel** | 568 BIST hissesi | 5 | Tüm pazar evreni, saf momentum |
| **BIST Quality** | 237 katılım hissesi | 5 | Momentum + Quality (likidite, volatilite, trend tutarlılığı) |

## Sistem Nasıl Çalışır

### Momentum Skoru Hesaplama

Her ay sonunda her hisse için kompozit momentum skoru hesaplanır:

1. Son 3 aylık getiri
2. Son 6 aylık getiri
3. Son 12 aylık getiri

Her getiri yüzdelik dilime çevrilir, üçünün ortalaması alınır. Bu skor sıralamasıyla top N hisse seçilir.

### Strateji Özelleştirmeleri

| Strateji | Filtre |
|---|---|
| Saf Momentum | Yok, ham sıralama |
| Sektör Diverse | Her sektörden max 3 hisse |
| Quality (ABD) | %60 momentum + %40 quality (ROE + marj + büyüme) |
| BIST Quality | %60 momentum + %40 quality (volatilite + trend tutarlılığı + drawdown + aşırılık cezası) |
| BIST Katılım/Genel | Saf momentum, top 5 |

## Performans Takip Sistemi

Her sistem kendi JSON dosyasında geçmiş portföy seçimlerini saklar:gecmis/
├── momentum.json
├── diverse.json
├── quality.json
├── bist_katilim.json
├── bist_genel.json
└── bist_quality.json

Her ay:
1. Önceki ayın portföyü güncel fiyatlarla değerlenir
2. Aylık getiri hesaplanır
3. Kümülatif performans güncellenir (toplam getiri, yıllık bileşik, drawdown, Sharpe)
4. Yeni portföy seçimi yapılır ve JSON'a eklenir
5. Telegram'da hem performans hem yeni seçim gösterilir

### Hesaplanan Metrikler

- Toplam kâr/zarar (mutlak ve yüzde)
- Yıllık bileşik getiri (annualized)
- Maksimum drawdown
- Sharpe oranı (3+ ay sonra anlamlı)
- Aylık dağılım
- En iyi/en kötü performans gösteren hisseler

## Otomatik Çalıştırma

Sistem her ayın 1'i 09:00 Türkiye saatinde GitHub Actions üzerinde 6 sıralı job olarak çalışır:

1. GitHub sanal makinesi başlatılır
2. Bağımlılıklar yüklenir
3. Önceki portföy değerlenir
4. Yeni portföy seçilir
5. JSON güncellenir, repo'ya commit edilir
6. Telegram bildirimi gönderilir
7. Bir sonraki sisteme geçilir

Tüm süreç ~45-60 dakika sürer ve kullanıcı müdahalesi gerektirmez.

Workflow durumu: [Actions sekmesi](https://github.com/Mimar2026/sirius/actions)

## Telegram Mesaj İçeriği

Her hisse için:
- Giriş fiyatı (son kapanış)
- Hedef fiyat (+%25 / +%30)
- Stop-loss (-%15)
- 30 günlük ortalama
- Momentum skoru ve getiriler
- Volatilite seviyesi
- Risk skoru (0-5)
- Net alım tutarı ve lot/hisse sayısı

Mesaj sonunda:
- Portföy özeti (ortalama skor, risk, getiri)
- Sektör dağılımı
- Performans geçmişi (varsa)
- Geçerlilik tarihleri

## Manuel Çalıştırma

```bashpip install -r requirements.txtABD sistemleri
python momentum_system.py              # Saf momentum
python momentum_sector_diverse.py      # Sektör diverse
python momentum_quality.py             # Quality momentumBIST sistemleri
python bist_momentum_katilim.py        # BIST katılım
python bist_momentum_genel.py          # BIST genel
python bist_momentum_quality.py        # BIST qualityBacktest karşılaştırma
python backtest_compare.py             # 3 ABD stratejisi 7 yıllık karşılaştırma

## Telegram Bot Kurulumu

```bashexport TELEGRAM_BOT_TOKEN="bot_tokeniniz"
export TELEGRAM_CHAT_ID="chat_id_niz"

Bot oluşturmak için [BotFather](https://t.me/BotFather). GitHub Actions kullanıyorsan token'ları Repository Secrets içinde saklamalısın.

## Dosya Yapısısirius/
├── .github/workflows/
│   └── monthly_run.yml              # Otomatik aylık çalıştırma
├── assets/
│   ├── sirius_avatar.png
│   ├── sirius_avatar_hd.png
│   ├── sirius_banner.png
│   └── ...
├── gecmis/                          # Performans geçmişi (auto-generated)
│   ├── momentum.json
│   ├── diverse.json
│   ├── quality.json
│   ├── bist_katilim.json
│   ├── bist_genel.json
│   └── bist_quality.json
├── README.md
├── requirements.txt
│
├── sirius_helpers.py                # Ortak yardımcı fonksiyonlar
├── performans_tracker.py            # Performans hesaplama modülü
│
├── momentum_system.py               # ABD - Saf momentum
├── momentum_sector_diverse.py       # ABD - Sektör çeşitlendirme
├── momentum_quality.py              # ABD - Quality momentum
├── backtest.py                      # Tek strateji backtest
├── backtest_compare.py              # 3 ABD stratejisi karşılaştırma
│
├── bist_hisseler.py                 # BIST hisse listeleri (237 + 568)
├── bist_data.py                     # Hibrit BIST veri çekme
├── bist_momentum_katilim.py         # BIST katılım top 5
├── bist_momentum_genel.py           # BIST genel top 5
└── bist_momentum_quality.py         # BIST quality top 5

## Veri Kaynakları

### ABD
- **Fiyat:** [yfinance](https://github.com/ranaroussi/yfinance) — Yahoo Finance
- **Evren:** Wikipedia (S&P 500 + Nasdaq 100)
- **Fundamental:** yfinance (ROE, marj, sektör)

### BIST
- **Birincil:** [borsapy](https://github.com/saidsurucu/borsapy) — modern API
- **Yedek:** [isyatirimhisse](https://github.com/urazakgul/isyatirimhisse) — İş Yatırım kaynaklı
- **Evren:** KAP resmi endeks listeleri (XKTUM + XUTUM)

## Teknoloji Yığını

Python 3.11, pandas, numpy, yfinance, borsapy, isyatirimhisse, lxml, beautifulsoup4, requests, GitHub Actions, Telegram Bot API, JSON tabanlı veri saklama.

## Sistem Hakkında Notlar

### Güçlü Yönler
- **6 stratejinin paralel çalışması** — farklı risk profillerine seçenek
- **Performans takibi otomatik** — gerçek getirileri ölç
- **2022 ayı piyasasında pozitif getiri** (ABD momentum için olağandışı)
- **Sektör ve quality filtreleri** ile risk yönetimi
- **Hibrit veri kaynakları** ile dayanıklılık
- **Tam otomatik** — kullanıcı müdahalesi gerekmez

### Riskler ve Sınırlamalar
- **Survivorship bias:** Backtest mevcut endeks üyelerini kullanır
- **İşlem maliyetleri** hesaplanmamış (~%1-3/yıl)
- **Vergi:** Aylık rebalans → yüksek kısa vadeli sermaye kazancı vergisi
- **Konsantrasyon riski:** Saf momentum'da yüksek
- **Momentum crash riski:** Trend dönüşlerinde sert düşüşler
- **Quality verisi look-ahead bias:** Backtest yaklaşık sonuç verir

## Yol Haritası

- [x] Temel momentum modeli (3+6+12 ay kompozit skor)
- [x] Backtest motoru (7 yıllık tarihsel test)
- [x] Telegram bildirimi
- [x] GitHub Actions ile otomatik aylık çalıştırma
- [x] Hata yakalama ve retry mantığı
- [x] Sektör çeşitlendirme stratejisi
- [x] Quality momentum stratejisi (ABD)
- [x] 3 ABD stratejisinin karşılaştırmalı backtest'i
- [x] BIST Katılım modeli (top 5)
- [x] BIST Genel modeli (top 5)
- [x] BIST Quality modeli (top 5)
- [x] Hibrit BIST veri kaynağı (borsapy + isyatirimhisse)
- [x] Detaylı Telegram mesajları (giriş + hedef + stop + lot)
- [x] JSON tabanlı performans takip sistemi
- [x] Kümülatif getiri ve yıllık bileşik hesabı
- [x] GitHub Actions otomatik commit (JSON kayıt)
- [ ] BIST için karşılaştırmalı backtest
- [ ] Karma portföy stratejisi (6 sistemin oylama birleşimi)
- [ ] QuantConnect entegrasyonu (point-in-time veri)
- [ ] Düşük volatilite filtresi
- [ ] Geçmiş seçimler dashboardu (web arayüzü)
- [ ] Hisse fundamental verisi BIST için (kurum veya API)

## Uyarı

Bu proje eğitim ve araştırma amaçlıdır. Yatırım tavsiyesi değildir. Geçmiş performans gelecek getiri garantisi vermez. Yatırım kararlarınız ve sonuçları size aittir. Kullanmadan önce kendi araştırmanı yap ve riski anla.

## Lisans

MIT License

---

<div align="center">
  <sub>Built with care, guided by a star.</sub>
  <br/>
  <sub>⭐ <a href="https://github.com/Mimar2026/sirius">github.com/Mimar2026/sirius</a></sub>
</div>
