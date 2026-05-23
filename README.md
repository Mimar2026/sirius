## Sistem Hakkında Notlar

### Güçlü Yönler
- **Tutarlı outperformance:** 6 yılın 6'sında da S&P 500'ü yendi
- **2022 ayı piyasasında pozitif getiri** — momentum stratejileri için olağandışı
- **Düşük max drawdown** — Çoklu lookback rejim değişikliklerini hızlı yakalar
- **Yüksek Sharpe oranı** (1,67) — Risk-ayarlı getiri üstün

### Riskler
- **Survivorship bias:** Backtest şu anki S&P 500 üyelerini kullanır. Gerçek getiri %5-15 daha düşük olabilir.
- **İşlem maliyetleri** hesaplanmamış (~%1-3/yıl azaltabilir)
- **Vergi:** Aylık rebalans nedeniyle kısa vadeli sermaye kazancı vergisi yüksek
- **Konsantrasyon riski:** Top 10 ağırlıklı olarak teknoloji/yarı iletken sektöründe
- **Momentum crash riski:** Trend dönüşlerinde sert düşüşler yaşanabilir

## Veri Kaynakları

- **Fiyat verisi:** [yfinance](https://github.com/ranaroussi/yfinance) — ücretsiz, sınırsız
- **Hisse listesi:** Wikipedia (S&P 500, Nasdaq 100)

## Teknoloji Yığını

- **Python 3.11** — Ana dil
- **pandas + numpy** — Veri işleme
- **yfinance** — Fiyat verisi
- **lxml + beautifulsoup4** — Web scraping
- **requests** — HTTP istekleri (Telegram + Wikipedia)
- **GitHub Actions** — Otomatik aylık çalıştırma
- **Telegram Bot API** — Bildirim sistemi

## Yol Haritası

- [x] **Temel momentum modeli** — 3+6+12 ay kompozit skor
- [x] **Backtest motoru** — 7 yıllık tarihsel test
- [x] **Telegram bildirimi** — Otomatik aylık mesaj
- [x] **GitHub Actions** ile otomatik aylık çalıştırma — Aktif (her ayın 1'i 09:00 TSİ)
- [ ] **Hata yakalama ve retry mantığı** (workflow güçlendirme)
- [ ] **Geçmiş seçimler logu** (commit history içinde)
- [ ] **Quality faktörü** ekleme (ROE, kâr büyümesi, brüt marj)
- [ ] **Sektör çeşitlendirme** kuralı
- [ ] **Düşük volatilite** filtresi
- [ ] **QuantConnect** entegrasyonu (point-in-time veri)
- [ ] **BIST evrenine uyarlama** (katılım vs genel)
- [ ] **Dashboard** (web arayüzü)

## Performans Karşılaştırması

Akademik literatürdeki momentum stratejilerinin tipik özellikleri ile Sirius'un karşılaştırması:

| Metrik | Akademik Ortalama | Sirius | Fark |
|---|---|---|---|
| Yıllık alfa (S&P 500 üstü) | %3-7 | %45,64 | Çoklu lookback avantajı |
| Sharpe oranı | 0,7-1,1 | 1,67 | Çok güçlü |
| Max drawdown | -%30 ile -%50 | -%20,40 | Olağandışı koruma |

**Not:** Sirius'un yüksek performansı kısmen survivorship bias ve son yıllardaki güçlü AI/teknoloji rallisinden kaynaklanır. Gerçek dünyada bu rakamların %30-50'si ölçeğinde performans gerçekçi bir beklentidir.

## Lisans

MIT License — özgürce kullanabilir, değiştirebilir, dağıtabilirsin.

## Uyarı

Bu proje **eğitim ve araştırma amaçlıdır**. Yatırım tavsiyesi değildir. Geçmiş performans gelecek getiri garantisi vermez. Yatırım kararlarınız ve sonuçları size aittir. Kullanmadan önce kendi araştırmanı yap ve riski anla.

---

<div align="center">
  <sub>Built with care, guided by a star.</sub>
  <br/>
  <sub>⭐ <a href="https://github.com/Mimar2026/sirius">github.com/Mimar2026/sirius</a></sub>
</div>
