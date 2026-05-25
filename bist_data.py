"""
Sirius BIST - Veri Cekme Modulu (Hibrit)

Iki kaynak kullanir:
1. borsapy (birincil - hizli, batch destekli)
2. isyatirimhisse (yedek - kararli, resmi kaynak)

Biri basarisiz olursa digeri devreye girer (failover).
"""

import time
import pandas as pd

# Iki paketi de import et
# Eger biri yuklu degilse hata mesajini yakala
BORSAPY_VAR = False
ISYATIRIM_VAR = False

try:
    import borsapy as bp
    BORSAPY_VAR = True
except ImportError:
    print("UYARI: borsapy yuklu degil. Sadece isyatirimhisse kullanilacak.")

try:
    from isyatirimhisse import veri_cek as isyat_veri_cek
    ISYATIRIM_VAR = True
except ImportError:
    print("UYARI: isyatirimhisse yuklu degil. Sadece borsapy kullanilacak.")


def borsapy_ile_cek(sembol, baslangic, bitis):
    """
    Tek hisse icin borsapy kullanarak gunluk fiyat verisi ceker.
    Format: baslangic ve bitis "YYYY-MM-DD" stringi olmali.
    """
    if not BORSAPY_VAR:
        raise Exception("borsapy yuklu degil")
    
    ticker = bp.Ticker(sembol)
    
    # Tarih araligi hesapla
    baslangic_dt = pd.to_datetime(baslangic)
    bitis_dt = pd.to_datetime(bitis)
    gun_sayisi = (bitis_dt - baslangic_dt).days
    
    # Period stringi belirle
    if gun_sayisi <= 30:
        period = "1ay"
    elif gun_sayisi <= 90:
        period = "3ay"
    elif gun_sayisi <= 180:
        period = "6ay"
    elif gun_sayisi <= 365:
        period = "1y"
    elif gun_sayisi <= 730:
        period = "2y"
    elif gun_sayisi <= 1825:
        period = "5y"
    else:
        period = "max"
    
    df = ticker.history(period=period)
    
    # Tarih indekslerini filtrele
    df = df[(df.index >= baslangic_dt) & (df.index <= bitis_dt)]
    
    return df


def isyatirimhisse_ile_cek(sembol, baslangic, bitis):
    """
    Tek hisse icin isyatirimhisse kullanarak gunluk fiyat verisi ceker.
    Format: tarih formati "DD-MM-YYYY" (paket buyle bekliyor).
    """
    if not ISYATIRIM_VAR:
        raise Exception("isyatirimhisse yuklu degil")
    
    # Tarih formatini cevir (YYYY-MM-DD -> DD-MM-YYYY)
    baslangic_iy = pd.to_datetime(baslangic).strftime("%d-%m-%Y")
    bitis_iy = pd.to_datetime(bitis).strftime("%d-%m-%Y")
    
    df = isyat_veri_cek(
        sembol=sembol,
        baslangic_tarih=baslangic_iy,
        bitis_tarih=bitis_iy,
        frekans='1g'
    )
    
    return df


def fiyat_cek(sembol, baslangic, bitis, kaynak="auto"):
    """
    Ana fiyat cekme fonksiyonu.
    
    Args:
        sembol: BIST hisse kodu (orn: "THYAO")
        baslangic: Baslangic tarihi "YYYY-MM-DD" formatinda
        bitis: Bitis tarihi "YYYY-MM-DD" formatinda
        kaynak: "borsapy", "isyatirim" veya "auto" (her ikisini de dene)
    
    Returns:
        pandas DataFrame veya None (basarisiz olursa)
    """
    if kaynak == "borsapy":
        return borsapy_ile_cek(sembol, baslangic, bitis)
    
    if kaynak == "isyatirim":
        return isyatirimhisse_ile_cek(sembol, baslangic, bitis)
    
    # Auto mode: once borsapy dene, sonra isyatirim
    try:
        df = borsapy_ile_cek(sembol, baslangic, bitis)
        if df is not None and len(df) > 0:
            return df
    except Exception as e:
        print(f"  [{sembol}] borsapy hatasi: {str(e)[:80]}")
    
    # Yedek olarak isyatirim
    try:
        df = isyatirimhisse_ile_cek(sembol, baslangic, bitis)
        if df is not None and len(df) > 0:
            return df
    except Exception as e:
        print(f"  [{sembol}] isyatirimhisse hatasi: {str(e)[:80]}")
    
    return None


def coklu_fiyat_cek(semboller, baslangic, bitis, ilerleme_goster=True):
    """
    Birden fazla hisse icin fiyat verisi ceker.
    
    Sembollerin her birini tek tek dener, basarisiz olanlari atlar.
    
    Returns:
        Tum hisselerin kapanis fiyatlarini iceren bir DataFrame.
        Index: tarih, Columns: hisse kodlari.
    """
    fiyat_dict = {}
    basarisiz = []
    
    for i, sembol in enumerate(semboller):
        if ilerleme_goster and (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(semboller)} hisse islendi...")
        
        try:
            df = fiyat_cek(sembol, baslangic, bitis, kaynak="auto")
            
            if df is None or len(df) == 0:
                basarisiz.append(sembol)
                continue
            
            # Kapanis kolonunu bul (Close veya CLOSING gibi olabilir)
            kapanis_kol = None
            for kol_aday in ['Close', 'close', 'CLOSE', 'HGDG_KAPANIS', 'Kapanis']:
                if kol_aday in df.columns:
                    kapanis_kol = kol_aday
                    break
            
            if kapanis_kol is None:
                # Eger bir kapanis kolonu yoksa, ilk numerik kolonu kullan
                numerik_kollar = df.select_dtypes(include='number').columns
                if len(numerik_kollar) > 0:
                    kapanis_kol = numerik_kollar[0]
                else:
                    basarisiz.append(sembol)
                    continue
            
            fiyat_dict[sembol] = df[kapanis_kol]
            
            # Cok hizli istek atmamak icin kucuk bekleme
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  [{sembol}] hata: {str(e)[:80]}")
            basarisiz.append(sembol)
    
    if ilerleme_goster:
        print(f"\n  Basarili: {len(fiyat_dict)} hisse")
        print(f"  Basarisiz: {len(basarisiz)} hisse")
        if basarisiz and len(basarisiz) < 20:
            print(f"  Basarisiz semboller: {', '.join(basarisiz)}")
    
    # Tum hisseleri tek bir DataFrame'de birlestir
    if len(fiyat_dict) == 0:
        return pd.DataFrame()
    
    sonuc = pd.DataFrame(fiyat_dict)
    return sonuc


def aylik_fiyatlara_donustur(gunluk_fiyatlar, min_veri_yuzdesi=70):
    """
    Gunluk fiyatlari aylik kapanislara cevirir.
    Yeterli verisi olmayan hisseleri eler.
    """
    aylik = gunluk_fiyatlar.resample("ME").last()
    veri_yuzdesi = aylik.notna().sum() / len(aylik) * 100
    gecerli = veri_yuzdesi[veri_yuzdesi >= min_veri_yuzdesi].index.tolist()
    return aylik[gecerli]


# ====================================================================
# TEST
# ====================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BIST DATA MODULU - TEST")
    print("=" * 60)
    
    print(f"\nborsapy yuklu mu: {BORSAPY_VAR}")
    print(f"isyatirimhisse yuklu mu: {ISYATIRIM_VAR}")
    
    # Tek hisse testi
    print("\n[Test 1] THYAO son 30 gun verisi...")
    df = fiyat_cek("THYAO", "2026-04-25", "2026-05-25")
    if df is not None:
        print(f"  Basarili. {len(df)} gunluk veri:")
        print(df.tail(5).to_string())
    else:
        print("  Basarisiz!")
    
    # Coklu hisse testi
    print("\n[Test 2] 5 hisselik mini batch testi...")
    test_semboller = ["THYAO", "AKBNK", "ASELS", "GARAN", "BIMAS"]
    coklu_df = coklu_fiyat_cek(test_semboller, "2026-04-25", "2026-05-25")
    print(f"\n  Sonuc boyut: {coklu_df.shape}")
    if not coklu_df.empty:
        print("\n  Son 3 satir:")
        print(coklu_df.tail(3).to_string())
    
    print("\n" + "=" * 60)
    print("Test tamamlandi.")
