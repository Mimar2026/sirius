"""
Sirius - Gunluk Stop / Hedef Kontrolu

6 sistemin (ABD + BIST) SON kayitlarindaki hisseleri kontrol eder.
Fiyat stop seviyesine dusmusse veya hedefe ulasmissa Telegram'a bildirir.
Her hisse icin bildirim SADECE BIR KEZ gonderilir (JSON'da bayrak tutulur).

Bu script otomatik islem yapmaz - sadece bilgilendirir. Karar kullanicinindir.
"""

import traceback
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from momentum_system import telegram_gonder, telegram_hata_gonder
from bist_data import coklu_fiyat_cek
from performans_tracker import gecmis_oku, gecmis_kaydet


STOP_YUZDE = 15

SISTEMLER = [
    {"kod": "momentum", "emoji": "🌟", "adi": "MOMENTUM", "pazar": "ABD", "para": "$"},
    {"kod": "diverse", "emoji": "🌐", "adi": "DIVERSE", "pazar": "ABD", "para": "$"},
    {"kod": "quality", "emoji": "💎", "adi": "QUALITY", "pazar": "ABD", "para": "$"},
    {"kod": "bist_katilim", "emoji": "🇹🇷", "adi": "BIST KATILIM", "pazar": "BIST", "para": "₺"},
    {"kod": "bist_genel", "emoji": "🇹🇷", "adi": "BIST GENEL", "pazar": "BIST", "para": "₺"},
    {"kod": "bist_quality", "emoji": "💎", "adi": "BIST QUALITY", "pazar": "BIST", "para": "₺"},
]


def abd_guncel_fiyatlar(semboller):
    """ABD sembolleri icin son islem gunu kapanis fiyatlarini ceker."""
    sonuc = {}
    if not semboller:
        return sonuc

    try:
        veri = yf.download(semboller, period="5d", interval="1d", progress=False, auto_adjust=True)
        kapanis = veri["Close"]
        if isinstance(kapanis, pd.Series):
            son = kapanis.dropna()
            if len(son) > 0:
                sonuc[semboller[0]] = float(son.iloc[-1])
        else:
            for sembol in kapanis.columns:
                son = kapanis[sembol].dropna()
                if len(son) > 0:
                    sonuc[sembol] = float(son.iloc[-1])
    except Exception as e:
        print(f"  UYARI: Toplu ABD fiyat cekme hatasi: {e}")

    eksikler = [s for s in semboller if s not in sonuc]
    for sembol in eksikler:
        try:
            veri = yf.Ticker(sembol).history(period="5d")
            if len(veri) > 0:
                sonuc[sembol] = float(veri["Close"].iloc[-1])
        except Exception:
            pass

    return sonuc


def bist_guncel_fiyatlar(semboller):
    """BIST sembolleri icin guncel kapanis fiyatlarini ceker (hibrit kaynak)."""
    if not semboller:
        return {}

    bitis = datetime.now().strftime("%Y-%m-%d")
    baslangic = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    df = coklu_fiyat_cek(semboller, baslangic, bitis, ilerleme_goster=False)

    sonuc = {}
    if df.empty:
        return sonuc

    for sembol in df.columns:
        son = df[sembol].dropna()
        if len(son) > 0:
            sonuc[sembol] = float(son.iloc[-1])

    return sonuc


def main():
    print("=" * 70)
    print("SIRIUS - GUNLUK STOP / HEDEF KONTROLU")
    print("=" * 70)

    try:
        sistem_verileri = {}
        abd_semboller = set()
        bist_semboller = set()

        print("\n[1/4] Sistemlerin son kayitlari okunuyor...")
        for s in SISTEMLER:
            gecmis = gecmis_oku(s["kod"], portfoy_baslangic=0, para_birimi="")
            kayitlar = gecmis.get("kayitlar", [])
            if not kayitlar:
                sistem_verileri[s["kod"]] = None
                continue

            son_kayit = kayitlar[-1]
            sistem_verileri[s["kod"]] = {"gecmis": gecmis, "kayit": son_kayit}

            for h in son_kayit.get("hisseler", []):
                if s["pazar"] == "ABD":
                    abd_semboller.add(h["sembol"])
                else:
                    bist_semboller.add(h["sembol"])

        print(f"  ABD sembolleri ({len(abd_semboller)}): {', '.join(sorted(abd_semboller))}")
        print(f"  BIST sembolleri ({len(bist_semboller)}): {', '.join(sorted(bist_semboller))}")

        print("\n[2/4] Guncel fiyatlar cekiliyor...")
        abd_fiyat = abd_guncel_fiyatlar(sorted(abd_semboller)) if abd_semboller else {}
        bist_fiyat = bist_guncel_fiyatlar(sorted(bist_semboller)) if bist_semboller else {}
        print(f"  ABD: {len(abd_fiyat)}/{len(abd_semboller)} fiyat alindi")
        print(f"  BIST: {len(bist_fiyat)}/{len(bist_semboller)} fiyat alindi")

        print("\n[3/4] Stop/hedef kontrolu yapiliyor...")
        stop_mesajlari = []
        hedef_mesajlari = []
        degisen_sistemler = set()

        for s in SISTEMLER:
            veri = sistem_verileri.get(s["kod"])
            if veri is None:
                continue

            fiyat_kaynagi = abd_fiyat if s["pazar"] == "ABD" else bist_fiyat
            kayit = veri["kayit"]

            for h in kayit.get("hisseler", []):
                sembol = h["sembol"]
                giris = h.get("giris_fiyat", 0)
                skor = h.get("skor", 0)

                guncel = fiyat_kaynagi.get(sembol)
                if guncel is None or guncel <= 0 or giris <= 0:
                    continue

                hedef_yuzde = 30 if skor > 99.5 else 25
                hedef = giris * (1 + hedef_yuzde / 100)
                stop = giris * (1 - STOP_YUZDE / 100)
                getiri_pct = ((guncel - giris) / giris) * 100

                stop_bildirildi = h.get("stop_bildirildi", False)
                hedef_bildirildi = h.get("hedef_bildirildi", False)

                if guncel <= stop and not stop_bildirildi:
                    h["stop_bildirildi"] = True
                    degisen_sistemler.add(s["kod"])
                    stop_mesajlari.append(
                        f"   [{s['emoji']} {s['adi']}] {sembol}: giris {s['para']}{giris:.2f} "
                        f"→ simdi {s['para']}{guncel:.2f} ({getiri_pct:+.1f}%)"
                    )

                if guncel >= hedef and not hedef_bildirildi:
                    h["hedef_bildirildi"] = True
                    degisen_sistemler.add(s["kod"])
                    hedef_mesajlari.append(
                        f"   [{s['emoji']} {s['adi']}] {sembol}: giris {s['para']}{giris:.2f} "
                        f"→ simdi {s['para']}{guncel:.2f} ({getiri_pct:+.1f}%)"
                    )

        print("\n[4/4] Sonuclar kaydediliyor ve bildirim gonderiliyor...")
        for kod in degisen_sistemler:
            gecmis_kaydet(kod, sistem_verileri[kod]["gecmis"])
            print(f"  Guncellendi: gecmis/{kod}.json")

        if stop_mesajlari or hedef_mesajlari:
            tarih = datetime.now().strftime("%Y-%m-%d")
            mesaj = "<b>⚡ SIRIUS - Stop / Hedef Bildirimi</b>\n\n"

            if stop_mesajlari:
                mesaj += "<b>🛑 STOP TETIKLENDI:</b>\n"
                mesaj += "\n".join(stop_mesajlari) + "\n\n"

            if hedef_mesajlari:
                mesaj += "<b>🎯 HEDEF TETIKLENDI:</b>\n"
                mesaj += "\n".join(hedef_mesajlari) + "\n\n"

            mesaj += f"📅 {tarih}\n"
            mesaj += "<i>Bu bilgi amaclidir, otomatik islem yapilmaz. Karar sana ait.</i>"

            telegram_gonder(mesaj)
            print("  Bildirim gonderildi.")
        else:
            print("  Tetiklenen stop veya hedef yok. Bildirim gonderilmedi.")

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
            telegram_hata_gonder("Sirius Stop/Hedef Kontrolu", str(e))
        except:
            print("Telegram hata bildirimi de gonderilemedi.")

        raise


if __name__ == "__main__":
    main()
