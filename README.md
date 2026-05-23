<div align="center">
  <img src="assets/sirius_banner.png" alt="Sirius" width="100%"/>
</div>

<p align="center">
  <em>A signal arrives before the rise.</em>
</p>

---

# Sirius — Momentum Portföy Motoru

ABD hisse senetleri için aylık çalışan momentum tabanlı portföy seçim sistemi. S&P 500 ve Nasdaq 100 evreninden her ay başında en güçlü momentum sergileyen 10 hisseyi seçer.

İsim Antik Mısır'da Nil'in taşmasını müjdeleyen Sirius yıldızından gelir. Gözlenebilir bir sinyal, sonraki bereketin habercisidir. Bu sistem de aynı mantıkla çalışır: her ay başında bir sinyal verir, ardından yükseliş gelir.

## Özet İstatistikler (Backtest)

| Metrik | Sirius Portföy | S&P 500 (SPY) |
|---|---|---|
| Toplam Getiri (6 yıl) | **%1.806** | %167 |
| Yıllık Bileşik Getiri | **%63,44** | %17,80 |
| Sharpe Oranı | **1,67** | 1,13 |
| Maksimum Drawdown | **-%20,40** | -%23,93 |
| Kazandıran Ay Oranı | **%65,28** | - |

Backtest dönemi: 2020-06 → 2026-05 (72 ay)

## Yıllık Getiri Dağılımı

| Yıl | Sirius | S&P 500 | Fark |
|---|---|---|---|
| 2020 | +%76,21 | +%24,42 | **+%51,79** |
| 2021 | +%31,26 | +%28,73 | +%2,54 |
| 2022 | +%10,66 | -%18,18 | **+%28,83** |
| 2023 | +%39,94 | +%26,18 | +%13,76 |
| 2024 | +%76,16 | +%24,89 | **+%51,28** |
| 2025 | +%57,75 | +%17,72 | **+%40,03** |
| 2026 (5 ay) | +%91,52 | +%9,93 | **+%81,58** |

Sistemin en dikkat çekici özelliği 2022 ayı piyasasında pozitif getiri sağlaması. S&P 500 -%18 kaybederken Sirius +%10,66 kazandırdı. Bu, çoklu lookback (3+6+12 ay) yapısının trend dönüşlerini hızlı yakalamasından kaynaklanır.

## Sistem Nasıl Çalışır

### Evren
- S&P 500 üyeleri (~503 hisse)
- Nasdaq 100 üyeleri (~101 hisse)
- Birleşik evren: ~516 hisse
- Veri filtresi sonrası: ~500 hisse

### Skor Hesaplama
Her ay sonunda her hisse için kompozit momentum skoru hesaplanır:

1. Son 3 aylık getiri
2. Son 6 aylık getiri
3. Son 12 aylık getiri

Her getiri yüzdelik dilime çevrilir, üçünün ortalaması alınır. En yüksek skorlu 10 hisse seçilir.

### Portföy Kuralları
- **Hisse sayısı:** 10
- **Ağırlık:** Eşit (%10 her hisse)
- **Rebalans:** Aylık (her ayın ilk işlem günü)
- **Çıkış kuralı:** Skor sıralamasında ilk 10'un dışına çıkanlar elenir

## Kurulum

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Bu ayın top 10'unu gör
python momentum_system.py

# Tam backtest çalıştır
python backtest.py
```

## Telegram Bildirimi (İsteğe Bağlı)

Sistem her çalıştığında Telegram'a otomatik mesaj gönderebilir. Aktifleştirmek için:

```bash
export TELEGRAM_BOT_TOKEN="bot_tokeniniz"
export TELEGRAM_CHAT_ID="chat_id_niz"
python momentum_system.py
```

Detay için: [BotFather](https://t.me/BotFather) üzerinden bot oluştur ve token al.

## Dosya Yapısı
