"""
hukuk_motoru.py - UCP 600 / ISBP 821 Kural Motoru v9.1
Görev: Yorum, hukuki değerlendirme, rezerv analizi.
Finansal hesap YAPMAZ. Yeni veri çıkarmaz. analysis_result'u yorumlar.
"""
from __future__ import annotations
import logging, re, traceback
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger("hukuk_motoru")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] hukuk_motoru: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.DEBUG)

AY_MAP = {"JAN":1,"JANUARY":1,"FEB":2,"FEBRUARY":2,"MAR":3,"MARCH":3,
          "APR":4,"APRIL":4,"MAY":5,"JUN":6,"JUNE":6,"JUL":7,"JULY":7,
          "AUG":8,"AUGUST":8,"SEP":9,"SEPTEMBER":9,"OCT":10,"OCTOBER":10,
          "NOV":11,"NOVEMBER":11,"DEC":12,"DECEMBER":12}

KIRLI_BL = ["CLAUSED","DAMAGED","TORN","WET CARGO","INSUFFICIENT PACKING",
            "PARTLY DAMAGED","RUSTED","LEAKING","STAINED","BROKEN"]

# ── MT700 alan metadata ──────────────────────────────────────────────────────
MT700_META: dict[str, dict] = {
    "20": {
        "ad": "Documentary Credit Number",
        "aciklama": "Akreditifin benzersiz referans numarasıdır.",
        "yorum": (
            "Tüm ibraz belgelerinde (fatura, konşimento, sigorta poliçesi) "
            "aynı LC referansının kullanılması önerilir. "
            "Farklı referans kullanımı Art 14(a) kapsamında soru işareti yaratabilir."
        ),
        "madde": "UCP 600 Art 14(a)",
    },
    "31D": {
        "ad": "Expiry Date & Place",
        "aciklama": "Akreditifin son geçerlilik tarihi ve yeridir.",
        "yorum": (
            "Bu tarihten sonra yapılan belgeli ibrazlar banka tarafından reddedilebilir. "
            "Geçerlilik yeri, ibrazın nerede yapılacağını belirler (Art 6(d)(i))."
        ),
        "madde": "UCP 600 Art 6",
    },
    "32B": {
        "ad": "Currency & Amount",
        "aciklama": "Akreditifin para birimi ve tutarıdır.",
        "yorum": (
            "Fatura tutarı bu değeri aşamaz. Art 30(b) uyarınca %5 tolerans uygulanabilir; "
            "'ABOUT' / 'APPROXIMATELY' ifadesi varsa %10 tolerans geçerlidir. "
            "Eşitlik (sapma = 0) her zaman uyumludur."
        ),
        "madde": "UCP 600 Art 18 / Art 30",
    },
    "40A": {
        "ad": "Form of Documentary Credit",
        "aciklama": "Akreditifin türüdür (IRREVOCABLE, TRANSFERABLE vb.).",
        "yorum": (
            "IRREVOCABLE: Tüm tarafların onayı olmadan değiştirilemez (Art 10). "
            "TRANSFERABLE: Lehdar aracı bankaya devredebilir (Art 38). "
            "Diğer türler Art 3 kapsamında değerlendirilir."
        ),
        "madde": "UCP 600 Art 3 / Art 10 / Art 38",
    },
    "44C": {
        "ad": "Latest Date of Shipment",
        "aciklama": "Malların en geç yüklenebileceği tarihtir.",
        "yorum": (
            "Konşimentodaki 'Shipped on Board' tarihi bu değeri geçemez. "
            "Geç yükleme doğrudan MAJOR DISCREPANCY sebebidir (Art 14(c)). "
            "ISBP 821 E5: tarih çelişkisi varsa en erken tarih esas alınır."
        ),
        "madde": "UCP 600 Art 14(c) / ISBP 821 E5",
    },
    "44E": {
        "ad": "Port of Loading / Airport of Departure",
        "aciklama": "Yükleme limanı veya kalkış havalimanıdır.",
        "yorum": (
            "Konşimentodaki yükleme limanı bu değerle uyumlu olmalıdır. "
            "Farklı liman rezerv sebebi olabilir (ISBP 821 E10)."
        ),
        "madde": "ISBP 821 E10",
    },
    "44F": {
        "ad": "Port of Discharge / Airport of Destination",
        "aciklama": "Boşaltma limanı veya varış havalimanıdır.",
        "yorum": (
            "Konşimentodaki varış limanı bu değerle uyumlu olmalıdır. "
            "Farklı varış rezerv sebebi olabilir (ISBP 821 E11)."
        ),
        "madde": "ISBP 821 E11",
    },
    "45A": {
        "ad": "Description of Goods",
        "aciklama": "LC'nin mal tanımıdır.",
        "yorum": (
            "Fatura, mal tanımını bu alanla tam veya kısmi uyumlu şekilde içermelidir. "
            "Art 18(c): Fatura mal tanımı LC'deki tanımla çelişemez; "
            "daha genel ifade kullanılabilir, çelişkili ifade kullanılamaz. "
            "ISBP 821 C3: genel niteleme kabul edilir."
        ),
        "madde": "UCP 600 Art 18(c) / ISBP 821 C3",
    },
    "46A": {
        "ad": "Documents Required",
        "aciklama": "İbraz edilmesi zorunlu belgeler listesidir.",
        "yorum": (
            "Bu alanda talep edilen her belgenin eksiksiz ibraz edilmesi zorunludur. "
            "Eksik belge Art 14(a) kapsamında ret sebebidir. "
            "ISBP 821 A21: belge sayısı belirtilmişse o kadar orijinal sunulmalıdır."
        ),
        "madde": "UCP 600 Art 14(a) / ISBP 821 A21",
    },
    "47A": {
        "ad": "Additional Conditions",
        "aciklama": "LC'nin ek şartları ve özel koşullarıdır.",
        "yorum": (
            "Bu alanda belirtilen her koşul bağlayıcıdır. "
            "Yoruma açık ifadeler (Art 5) banka tarafından görmezden gelinebilir. "
            "Somut koşullar karşılanmazsa Art 16 bildirimi gündeme gelebilir."
        ),
        "madde": "UCP 600 Art 5 / Art 16",
    },
    "48": {
        "ad": "Period for Presentation",
        "aciklama": "Yükleme tarihinden sonra ibraz için verilen süredir.",
        "yorum": (
            "Art 14(c): Belirtilmemişse 21 takvim günü uygulanır. "
            "Bu süre aşıldığında belgeler reddedilebilir. "
            "Süre, geçerlilik tarihi ile sınırlıdır."
        ),
        "madde": "UCP 600 Art 14(c)",
    },
}

# ── normalize_tutar (paylaşılan export) ─────────────────────────────────────
def normalize_tutar(metin: str) -> Optional[float]:
    """23,940 / 23.940 / 23.940,00 → 23940.0  (23.94 üretmez)"""
    if not metin:
        return None
    s = re.sub(r'[A-Za-z$€£\t ]', '', str(metin)).strip()
    if not s:
        return None
    try:
        vc, nc = s.count(','), s.count('.')
        sv, sn = s.rfind(','), s.rfind('.')
        if vc == 0 and nc == 0:
            return float(s)
        if vc == 1 and nc == 0:
            s = s.replace(',', '') if len(s[sv+1:]) == 3 else s.replace(',', '.')
        elif nc == 1 and vc == 0:
            if len(s[sn+1:]) == 3:
                s = s.replace('.', '')
        elif vc > 0 and nc > 0:
            s = s.replace('.','').replace(',','.') if sv > sn else s.replace(',','')
        return float(s) if s else None
    except ValueError:
        return None

# ── Dahili yardımcılar ───────────────────────────────────────────────────────
def _tarih(metin: str) -> Optional[datetime]:
    if not metin:
        return None
    for pat, grp in [
        (r'(\d{1,2})[.\-/](\d{2})[.\-/](\d{4})', lambda m: datetime(int(m[3]),int(m[2]),int(m[1]))),
        (r'(\d{4})-(\d{2})-(\d{2})',               lambda m: datetime(int(m[1]),int(m[2]),int(m[3]))),
    ]:
        m = re.search(pat, metin)
        if m:
            try: return grp(m.groups())
            except ValueError: pass
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', metin)
    if m:
        ay = AY_MAP.get(m.group(2).upper()[:9])
        if ay:
            try: return datetime(int(m.group(3)), ay, int(m.group(1)))
            except ValueError: pass
    return None

def _celiski_denetle(a: Optional[float], b: Optional[float], iliski: str = ">=") -> bool:
    """True = uyumlu. 26334.0 >= 26334.000000000004 → round ile True."""
    if a is None or b is None:
        return False
    a2, b2 = round(a, 2), round(b, 2)
    if iliski == ">=" : return a2 >= b2
    if iliski == "<=" : return a2 <= b2
    if iliski == "==" : return abs(a2-b2) < 0.01
    return False


# ── MT700 Akıllı Yorum Motoru ────────────────────────────────────────────────
def mt700_hukuki_yorum(parsed: dict[str, Any]) -> list[dict]:
    """
    MT700 alanları için hukuki ve operasyonel yorum üretir.
    Yeni hesaplama yapmaz — parsed_data'daki mevcut verileri kullanır.

    Döner: list[dict] — her kayıt:
      {alan, ad, deger, aciklama, yorum, madde, karsilastirma, sonuc}
    """
    mt700 = parsed.get("mt700_alanlari", {})
    fatura_tutar = parsed.get("fatura_tutar")
    lc_tutar     = parsed.get("lc_tutar")
    bl_tarih_str = parsed.get("bl_tarih_str")
    sigorta_t    = parsed.get("sigorta_tutari")
    incoterm     = parsed.get("incoterm", "")
    alan_44c     = parsed.get("alan_44c", "")

    sonuclar: list[dict] = []

    for alan, meta in MT700_META.items():
        deger = mt700.get(alan)
        if not deger:
            continue

        karsilastirma = ""
        sonuc         = "BİLGİ"

        # ── Alan bazlı karşılaştırma ve sonuç ──────────────────────────
        if alan == "32B" and fatura_tutar and lc_tutar and lc_tutar > 0:
            sapma = (fatura_tutar - lc_tutar) / lc_tutar * 100
            karsilastirma = (
                f"LC Tutarı: {lc_tutar:,.2f} | "
                f"Fatura CIF: {fatura_tutar:,.2f} | "
                f"Sapma: %{sapma:+.2f}"
            )
            sonuc = "✓ UYUMLU" if abs(sapma) <= 5 else "⚠ REZERV RİSKİ"

        elif alan == "44C":
            if bl_tarih_str and alan_44c:
                bl_dt = _tarih(bl_tarih_str)
                lc_dt = _tarih(alan_44c)
                if bl_dt and lc_dt:
                    karsilastirma = (
                        f"B/L On Board: {bl_tarih_str} | "
                        f"44C Son Yükleme: {alan_44c}"
                    )
                    sonuc = "✓ UYUMLU" if bl_dt <= lc_dt else "⚠ GEÇ YÜKLEME — MAJOR DISCREPANCY"
            elif alan_44c:
                karsilastirma = f"Son Yükleme: {alan_44c} | B/L tarihi tespit edilemedi."
                sonuc = "MANUEL KONTROL"

        elif alan == "45A":
            mal = parsed.get("mal_tanimi_oran")
            if mal is not None:
                karsilastirma = f"Fatura mal tanımı örtüşme oranı: %{mal*100:.0f}"
                sonuc = ("✓ UYUMLU" if mal >= 0.8
                         else "⚠ DÜŞÜK BENZERLİK" if mal >= 0.5
                         else "⚠ REZERV RİSKİ")
            else:
                sonuc = "MANUEL KONTROL"

        elif alan == "46A":
            eksik = parsed.get("eksik_belgeler_46a", [])
            if eksik:
                karsilastirma = f"Eksik: {', '.join(eksik)}"
                sonuc = "⚠ EKSİK BELGE — REZERV"
            else:
                sonuc = "✓ UYUMLU"

        elif alan == "32B" and incoterm in ["CIF","CIP"] and sigorta_t and fatura_tutar:
            min_t   = round(fatura_tutar * 1.10, 2)
            sig_t_r = round(sigorta_t, 2)
            uyumlu  = _celiski_denetle(sig_t_r, min_t, ">=")
            karsilastirma = f"Sigorta: {sig_t_r:,.2f} | Min (CIF×110%): {min_t:,.2f}"
            sonuc = "✓ UYUMLU" if uyumlu else "⚠ YETERSİZ TEMİNAT"

        sonuclar.append({
            "alan":           alan,
            "ad":             meta["ad"],
            "deger":          deger[:120],
            "aciklama":       meta["aciklama"],
            "yorum":          meta["yorum"],
            "madde":          meta["madde"],
            "karsilastirma":  karsilastirma,
            "sonuc":          sonuc,
        })

    log.debug("[DEBUG] mt700_hukuki_yorum: %d alan yorumlandı.", len(sonuclar))
    return sonuclar


# ── UCP Kuralları Uygula ─────────────────────────────────────────────────────
def ucp_kurallari_uygula(parsed: dict[str, Any]) -> list[dict]:
    """
    app.py'nin hazırladığı parsed_data üzerinde UCP 600 kontrolleri uygular.
    Yeni hesaplama yapmaz.
    """
    log.debug("[DEBUG] ucp_kurallari_uygula() başladı.")
    rapor: list[dict] = []

    def ekle(madde, aciklama, durum, detay):
        rapor.append({"madde":madde,"aciklama":aciklama,"durum":durum,"detay":detay})

    fatura_tutar   = parsed.get("fatura_tutar")
    lc_tutar       = parsed.get("lc_tutar")
    incoterm       = parsed.get("incoterm")
    bl_tarih_str   = parsed.get("bl_tarih_str")
    alan_44c       = parsed.get("alan_44c","")
    fat_kilo       = parsed.get("fat_kilo")
    bl_kilo        = parsed.get("bl_kilo")
    sigorta_tutari = parsed.get("sigorta_tutari")
    kusat_text     = parsed.get("kusat_text","")
    konsimento_text= parsed.get("konsimento_text","")

    # Art 18/30: Tutar
    try:
        if fatura_tutar and lc_tutar and lc_tutar > 0:
            about    = any(x in kusat_text.upper() for x in ["ABOUT","APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma    = (fatura_tutar - lc_tutar) / lc_tutar * 100
            if abs(sapma) <= tolerans:
                ekle("Art 30","Tutar Toleransı","UYUMLU",
                     f"CIF:{fatura_tutar:,.2f} | LC:{lc_tutar:,.2f} | Sapma:%{sapma:+.1f}")
            else:
                ekle("Art 18/30","Tutar Uyumsuzluğu","REZERV",
                     f"CIF:{fatura_tutar:,.2f} | LC:{lc_tutar:,.2f} | Sapma:%{sapma:+.1f}")
        else:
            ekle("Art 30","Tutar","MANUEL KONTROL","CIF veya LC tutarı tespit edilemedi.")
    except Exception as e:
        ekle("Art 30","Tutar","HATA",str(e))

    # Art 30: Kilo
    try:
        if fat_kilo and bl_kilo:
            if abs(fat_kilo - bl_kilo) < 1.0:
                ekle("Art 30","Kilo (Fatura vs B/L)","UYUMLU",f"Eşleşti: {fat_kilo:,.2f} KG")
            else:
                ekle("Art 30","Kilo (Fatura vs B/L)","REZERV",
                     f"Fatura:{fat_kilo:,.2f} | B/L:{bl_kilo:,.2f} KG")
        else:
            eksik = [n for n,v in [("Fatura Kilo",fat_kilo),("B/L Kilo",bl_kilo)] if not v]
            ekle("Art 30","Kilo","MANUEL KONTROL",f"Tespit edilemedi: {', '.join(eksik)}")
    except Exception as e:
        ekle("Art 30","Kilo","HATA",str(e))

    # Art 20: On Board
    if konsimento_text:
        bl_u = konsimento_text.upper()
        if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
            ekle("Art 20","Shipped on Board","UYUMLU","On Board şerhi mevcut.")
        else:
            ekle("Art 20","Shipped on Board","REZERV","On Board şerhi bulunamadı!")

    # Art 27: Temiz B/L
    if konsimento_text:
        kirli = [k for k in KIRLI_BL if k in konsimento_text.upper()]
        if kirli:
            ekle("Art 27","Temiz Konsimento","REZERV",f"Kirli ifade: {', '.join(kirli)}")
        else:
            ekle("Art 27","Temiz Konsimento","UYUMLU","Olumsuz kloz bulunamadı.")

    # Art 20/44C: Yükleme tarihi
    if bl_tarih_str and alan_44c:
        bl_dt = _tarih(bl_tarih_str)
        lc_dt = _tarih(alan_44c)
        if bl_dt and lc_dt:
            if bl_dt <= lc_dt:
                ekle("Art 20","Yükleme Tarihi","UYUMLU",f"B/L:{bl_tarih_str} ≤ 44C:{alan_44c}")
            else:
                ekle("Art 20","Yükleme Tarihi","REZERV",
                     f"GEÇ YÜKLEME: {bl_tarih_str} > {alan_44c}")
        else:
            ekle("Art 20","Yükleme Tarihi","MANUEL KONTROL","Tarih formatı tanınamadı.")
    else:
        eksik = [n for n,v in [("B/L Tarih",bl_tarih_str),("44C",alan_44c or None)] if not v]
        ekle("Art 20","Yükleme Tarihi","MANUEL KONTROL",f"Tespit edilemedi: {', '.join(eksik)}")

    # Art 28f-ii: Sigorta — EŞİTLİK UYUMLUDUR
    if incoterm in ["CIF","CIP"]:
        if sigorta_tutari and fatura_tutar and fatura_tutar > 0:
            # round() zorunlu: 23940 × 1.10 = 26334.000000000004 (float precision)
            min_t   = round(fatura_tutar * 1.10, 2)
            sig_t_r = round(sigorta_tutari, 2)
            if _celiski_denetle(sig_t_r, min_t, ">="):
                ekle("Art 28f-ii","Sigorta Teminatı","UYUMLU",
                     f"Sigorta:{sig_t_r:,.2f} ≥ CIF×110%:{min_t:,.2f}")
            else:
                ekle("Art 28f-ii","Sigorta Teminatı","REZERV",
                     f"Yetersiz: {sig_t_r:,.2f} < {min_t:,.2f}")
        elif sigorta_tutari:
            ekle("Art 28f-ii","Sigorta Teminatı","MANUEL KONTROL",
                 f"Sigorta:{sigorta_tutari:,.2f} | CIF tespit edilemedi.")
        else:
            ekle("Art 28f-ii","Sigorta Teminatı","MANUEL KONTROL","Sigorta tutarı tespit edilemedi.")

    # Art 16: Rezerv bildirimi
    rezervler = [r for r in rapor if r["durum"] == "REZERV"]
    if rezervler:
        ozet = "\n".join(f"  - {r['detay']}" for r in rezervler)
        ekle("Art 16","Rezerv Bildirimi","UYARI",
             f"\n--- REZERV BİLDİRİMİ ---\n"
             f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
             f"{ozet}\n5 iş günü içinde düzeltme yapılmalıdır.")

    log.debug("[DEBUG] ucp_kurallari_uygula: %d kayıt.", len(rapor))
    return rapor


def analiz_et(depo: dict) -> list:
    """Kullanım dışı — geriye dönük uyumluluk."""
    log.warning("analiz_et() deprecated. ucp_kurallari_uygula() kullanın.")
    return []
