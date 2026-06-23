"""
hukuk_motoru.py - UCP 600 / ISBP 821 Kural Motoru v9.0 - NİHAİ REVİZYON

DEĞİŞİKLİKLER (v3 -> v9):
  - BUG-HM-01: analiz_et() kendi içinde tutar/kilo/sigorta hesaplıyor,
               app.py de aynı hesapları yapıyor → ÇİFT ANALİZ.
               ÇÖZÜM: hukuk_motoru artık yalnızca UCP kurallarını uygular;
               tüm ham veri (parsed_data) app.py'nin tek analiz_result'undan gelir.
  - BUG-HM-02: _sigorta_tutari desenlerinde COVERAGE / TOTAL INSURED eksikti.
  - BUG-HM-03: Rezerv bildirimi (Art 16) daima üretiliyordu; çelişki denetimi yoktu.
  - BUG-HM-04: Tutar normalizer 23.940 -> 23.94 üretiyordu (nokta-sonrası 3 hane).

NOT: Bu modül artık dışarıya sadece iki şey export eder:
  1. normalize_tutar()   - paylaşılan sayı normalleştirici
  2. ucp_kurallari_uygula()  - app.py'nin analysis_result üzerinde çalışır
"""
from __future__ import annotations

import logging
import re
import traceback
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger("hukuk_motoru")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] hukuk_motoru: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
AY_MAP: dict[str, int] = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3, "APR": 4, "APRIL": 4,
    "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPTEMBER": 9, "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}

KIRLI_BL = [
    "CLAUSED", "DAMAGED", "TORN", "WET CARGO", "INSUFFICIENT PACKING",
    "PARTLY DAMAGED", "RUSTED", "LEAKING", "STAINED", "BROKEN",
]

# ---------------------------------------------------------------------------
# BUG-HM-04 FİX: normalize_tutar — tüm formatlara destek
# Paylaşılan (app.py de kullanır)
# ---------------------------------------------------------------------------
def normalize_tutar(metin: str) -> Optional[float]:
    """
    23,940 / 23.940 / 23,940.00 / 23.940,00 / USD 23,940 / 23940 -> 23940.0
    Kesinlikle 23.94 üretmez.
    """
    if not metin:
        return None
    s = re.sub(r'[A-Za-z$€£\t ]', '', str(metin)).strip()
    if not s:
        return None
    try:
        vc = s.count(',')
        nc = s.count('.')
        sv = s.rfind(',')
        sn = s.rfind('.')

        if vc == 0 and nc == 0:
            return float(s)

        if vc == 1 and nc == 0:
            # "23,940" → binlik: son 3 hane → kaldır; "23,94" → ondalık → nokta yap
            sonrasi = s[sv + 1:]
            s = s.replace(',', '') if len(sonrasi) == 3 else s.replace(',', '.')

        elif nc == 1 and vc == 0:
            # "23.940" → binlik: son 3 hane → kaldır; "23.94" → ondalık → bırak
            sonrasi = s[sn + 1:]
            if len(sonrasi) == 3:
                s = s.replace('.', '')
            # else: gerçek ondalık, bırak

        elif vc > 0 and nc > 0:
            if sv > sn:
                # Avrupa: 1.234.567,89
                s = s.replace('.', '').replace(',', '.')
            else:
                # Anglo: 1,234,567.89
                s = s.replace(',', '')

        return float(s) if s else None
    except ValueError:
        log.debug("normalize_tutar başarısız: %r", metin)
        return None


# ---------------------------------------------------------------------------
# Yardımcılar (dahili kullanım)
# ---------------------------------------------------------------------------
def _metin(depo: dict, anahtar: str) -> str:
    kayit = depo.get(anahtar)
    if kayit is None:
        return ""
    if isinstance(kayit, str):
        return kayit
    if isinstance(kayit, dict):
        v = kayit.get("metin") or kayit.get("icerik") or ""
        return v if isinstance(v, str) else ""
    return ""


def _tarih(metin: str) -> Optional[datetime]:
    if not metin:
        return None
    m = re.search(r'(\d{1,2})[.\-/](\d{2})[.\-/](\d{4})', metin)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', metin)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', metin)
    if m:
        ay = AY_MAP.get(m.group(2).upper()[:9])
        if ay:
            try:
                return datetime(int(m.group(3)), ay, int(m.group(1)))
            except ValueError:
                pass
    return None


def _bl_tarihi(metin: str) -> Optional[str]:
    if not metin:
        return None
    t = (
        r'([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'
        r'|[\d]{4}-[\d]{2}-[\d]{2}'
        r'|[\d]{1,2}[-\s][A-Z]{3,9}[-\s][\d]{4}'
        r'|[\d]{1,2}\s+[A-Z][a-z]{2,8}\s+[\d]{4})'
    )
    for desen in [
        rf'SHIPPED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
        rf'SHIPPED\s+ON\s+BOARD\s*\n\s*{t}',
        rf'ON\s+BOARD\s+DATE\s*[:\-]?\s*{t}',
        rf'DATE\s+OF\s+SHIPMENT\s*[:\-]?\s*{t}',
        rf'LOADED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
        rf'VESSEL\s+LOADED\s*[:\-]?\s*{t}',
        rf'ON\s+BOARD\s*[:\-]?\s*{t}',
    ]:
        m = re.search(desen, metin, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _sigorta_tutari(metin: str) -> Optional[float]:
    """BUG-HM-02 FİX: COVERAGE ve TOTAL INSURED eklendi."""
    if not metin:
        return None
    desenler = [
        r'(?:SUM\s+INSURED|AMOUNT\s+INSURED|INSURED\s+VALUE|INSURED\s+AMOUNT)'
        r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        r'(?:INSURANCE\s+AMOUNT|INSURANCE\s+VALUE|COVERAGE\s+AMOUNT|POLICY\s+AMOUNT)'
        r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        r'(?:TOTAL\s+INSURED|COVERAGE)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            v = normalize_tutar(m.group(1))
            if v:
                log.debug("[DEBUG] Sigorta tutarı = %.2f", v)
                return v
    return None


def _kilo_bul(metin: str) -> Optional[float]:
    if not metin:
        return None
    desenler = [
        r'GROSS\s*WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
        r'G\.?W\.?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
        r'NET\s*WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
        r'TOTAL\s+WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
        r'WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
        r'([\d,\.]+)\s*KGS\b',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            v = normalize_tutar(m.group(1))
            if v:
                return v
    return None


# ---------------------------------------------------------------------------
# BUG-HM-03 FİX: Çelişki denetimi
# ---------------------------------------------------------------------------
def _celiski_denetle(madde: str, aciklama: str,
                     a: Optional[float], b: Optional[float],
                     iliskisi: str = ">=") -> Optional[str]:
    """
    26334 >= 26334 gibi durumlar için tutarsız rezerv üretilmesini engeller.
    Sadece gerçekten ihlal varsa hata mesajı döner; aksi hâlde None.
    """
    if a is None or b is None:
        return None
    if iliskisi == ">=" and a >= b:
        log.debug("[DEBUG] Çelişki denetimi geçti: %.2f >= %.2f (%s/%s)", a, b, madde, aciklama)
        return None  # UYUMLU — rezerv üretme
    if iliskisi == "<=" and a <= b:
        return None
    if iliskisi == "==" and abs(a - b) < 0.01:
        return None
    return f"{a:,.2f} {'değil' if iliskisi == '>=' else ''} {iliskisi} {b:,.2f}"


# ===========================================================================
# ANA İHRACAT FONKSİYONU
# BUG-HM-01 FİX: app.py'nin analysis_result üzerinde çalışır,
#                 ayrı OCR/parse yapmaz.
# ===========================================================================
def ucp_kurallari_uygula(parsed: dict[str, Any]) -> list[dict]:
    """
    app.py tarafından üretilen parsed_data sözlüğünü alır,
    UCP 600 / ISBP 821 kurallarını uygular ve kontrol listesi döner.

    Parameters
    ----------
    parsed : dict
        {
          "kusat_text": str,
          "fatura_text": str,
          "konsimento_text": str,
          "ceki_text": str,
          "sigorta_text": str,
          "mt700_alanlari": dict,
          "fatura_tutar": float | None,
          "lc_tutar": float | None,
          "incoterm": str | None,
          "bl_tarih_str": str | None,
          "alan_44c": str,
          "fat_kilo": float | None,
          "bl_kilo": float | None,
          "pl_kilo": float | None,
          "sigorta_tutari": float | None,
        }

    Returns
    -------
    list[dict]  — her kayıt: {madde, aciklama, durum, detay}
    """
    log.debug("[DEBUG] ucp_kurallari_uygula() çağrıldı. Anahtarlar: %s", list(parsed.keys()))

    rapor: list[dict] = []

    def ekle(madde, aciklama, durum, detay):
        rapor.append({"madde": madde, "aciklama": aciklama, "durum": durum, "detay": detay})

    kusat_text      = parsed.get("kusat_text", "")
    fatura_text     = parsed.get("fatura_text", "")
    konsimento_text = parsed.get("konsimento_text", "")
    fatura_tutar    = parsed.get("fatura_tutar")
    lc_tutar        = parsed.get("lc_tutar")
    incoterm        = parsed.get("incoterm")
    bl_tarih_str    = parsed.get("bl_tarih_str")
    alan_44c        = parsed.get("alan_44c", "")
    fat_kilo        = parsed.get("fat_kilo")
    bl_kilo         = parsed.get("bl_kilo")
    sigorta_tutari  = parsed.get("sigorta_tutari")

    # ── Art 18 / Art 30: Tutar Toleransı ───────────────────────────────
    try:
        if fatura_tutar is not None and lc_tutar is not None and lc_tutar > 0:
            about = any(x in kusat_text.upper() for x in ["ABOUT", "APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma = (fatura_tutar - lc_tutar) / lc_tutar * 100

            celiski = _celiski_denetle("Art 30", "Tutar",
                                        abs(sapma), float(tolerans), "<=")
            if celiski is None:
                ekle("Art 30", "Tutar Toleransı", "UYUMLU",
                     f"Fatura CIF:{fatura_tutar:,.2f} | LC:{lc_tutar:,.2f} | "
                     f"Sapma:%{sapma:+.1f} ≤ %{tolerans}")
            else:
                ekle("Art 18/30", "Tutar Uyumsuzluğu", "REZERV",
                     f"Fatura CIF:{fatura_tutar:,.2f} | LC:{lc_tutar:,.2f} | "
                     f"Sapma:%{sapma:+.1f} > %{tolerans}")
        else:
            ekle("Art 30", "Tutar", "MANUEL KONTROL",
                 "Fatura CIF veya LC tutarı tespit edilemedi.")
    except Exception as exc:
        log.error("Tutar kontrolü hatası: %s\n%s", exc, traceback.format_exc())
        ekle("Art 30", "Tutar", "HATA", str(exc))

    # ── Art 30: Kilo Karşılaştırması ────────────────────────────────────
    try:
        if fat_kilo is not None and bl_kilo is not None:
            celiski = _celiski_denetle("Art 30", "Kilo",
                                        abs(fat_kilo - bl_kilo), 1.0, "<=")
            if celiski is None:
                ekle("Art 30", "Kilo (Fatura vs B/L)", "UYUMLU",
                     f"Eşleşti: {fat_kilo:,.2f} KG")
            else:
                ekle("Art 30", "Kilo (Fatura vs B/L)", "REZERV",
                     f"Fatura:{fat_kilo:,.2f} KG | B/L:{bl_kilo:,.2f} KG")
        else:
            eksik = [n for n, v in [("Fatura Kilo", fat_kilo), ("B/L Kilo", bl_kilo)] if v is None]
            ekle("Art 30", "Kilo", "MANUEL KONTROL",
                 f"Tespit edilemedi: {', '.join(eksik)}")
    except Exception as exc:
        log.error("Kilo kontrolü hatası: %s\n%s", exc, traceback.format_exc())
        ekle("Art 30", "Kilo", "HATA", str(exc))

    # ── Art 20: Shipped on Board ─────────────────────────────────────────
    if konsimento_text:
        try:
            bl_u = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
                ekle("Art 20", "Shipped on Board", "UYUMLU",
                     "On Board şerhi mevcut (Art 20a-ii).")
            else:
                ekle("Art 20", "Shipped on Board", "REZERV",
                     "On Board şerhi bulunamadı!")
        except Exception as exc:
            log.error("On Board hatası: %s", exc)
            ekle("Art 20", "Shipped on Board", "HATA", str(exc))

    # ── Art 27: Temiz Konsimento ─────────────────────────────────────────
    if konsimento_text:
        try:
            kirli = [k for k in KIRLI_BL if k in konsimento_text.upper()]
            if kirli:
                ekle("Art 27", "Temiz Konsimento", "REZERV",
                     f"Kirli ifade: {', '.join(kirli)}")
            else:
                ekle("Art 27", "Temiz Konsimento", "UYUMLU",
                     "Olumsuz kloz bulunamadı (Art 27 uyumlu).")
        except Exception as exc:
            log.error("Temiz BL hatası: %s", exc)
            ekle("Art 27", "Temiz Konsimento", "HATA", str(exc))

    # ── Art 20 / 44C: Yükleme Tarihi ────────────────────────────────────
    if bl_tarih_str and alan_44c:
        try:
            bl_dt = _tarih(bl_tarih_str)
            lc_dt = _tarih(alan_44c)
            if bl_dt and lc_dt:
                if bl_dt <= lc_dt:
                    ekle("Art 20", "Yükleme Tarihi", "UYUMLU",
                         f"B/L:{bl_tarih_str} ≤ 44C:{alan_44c}")
                else:
                    ekle("Art 20", "Yükleme Tarihi", "REZERV",
                         f"GEÇ YÜKLEME: B/L:{bl_tarih_str} > 44C:{alan_44c}")
            else:
                ekle("Art 20", "Yükleme Tarihi", "MANUEL KONTROL",
                     f"Tarih formatı tanınamadı: B/L:{bl_tarih_str} | 44C:{alan_44c}")
        except Exception as exc:
            log.error("Yükleme tarihi hatası: %s", exc)
            ekle("Art 20", "Yükleme Tarihi", "HATA", str(exc))
    else:
        eksik = [n for n, v in [("B/L Tarih", bl_tarih_str), ("44C", alan_44c or None)] if not v]
        ekle("Art 20", "Yükleme Tarihi", "MANUEL KONTROL",
             f"Tespit edilemedi: {', '.join(eksik)}")

    # ── Art 28f-ii: Sigorta Teminatı ────────────────────────────────────
    if incoterm in ["CIF", "CIP"]:
        try:
            if sigorta_tutari is not None and fatura_tutar is not None and fatura_tutar > 0:
                min_t = fatura_tutar * 1.10
                # BUG-HM-03 FİX: Çelişki denetimi — 26334 >= 26334 UYUMLU
                celiski = _celiski_denetle("Art 28", "Sigorta", sigorta_tutari, min_t, ">=")
                if celiski is None:
                    ekle("Art 28f-ii", "Sigorta Teminatı", "UYUMLU",
                         f"Sigorta:{sigorta_tutari:,.2f} ≥ CIF×110%:{min_t:,.2f}")
                else:
                    ekle("Art 28f-ii", "Sigorta Teminatı", "REZERV",
                         f"Yetersiz: {sigorta_tutari:,.2f} < {min_t:,.2f}")
            elif sigorta_tutari is not None:
                ekle("Art 28f-ii", "Sigorta Teminatı", "MANUEL KONTROL",
                     f"Sigorta:{sigorta_tutari:,.2f} | CIF tutarı tespit edilemedi.")
            elif fatura_tutar is not None:
                ekle("Art 28f-ii", "Sigorta Teminatı", "MANUEL KONTROL",
                     "Sigorta tutarı tespit edilemedi.")
            else:
                ekle("Art 28f-ii", "Sigorta Teminatı", "MANUEL KONTROL",
                     "Sigorta ve CIF tutarı tespit edilemedi.")
        except Exception as exc:
            log.error("Sigorta kontrolü hatası: %s\n%s", exc, traceback.format_exc())
            ekle("Art 28f-ii", "Sigorta Teminatı", "HATA", str(exc))

    # ── Art 16: Rezerv Bildirimi ─────────────────────────────────────────
    rezerv_listesi = [r for r in rapor if r["durum"] == "REZERV"]
    if rezerv_listesi:
        ozet_satirlar = "\n".join(f"  - {r['detay']}" for r in rezerv_listesi)
        mektup = (
            f"\n--- REZERV BİLDİRİMİ (Art 16) ---\n"
            f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"İnceleme sonucunda aşağıdaki uyumsuzluklar saptanmıştır:\n"
            f"{ozet_satirlar}\n"
            f"5 iş günü içinde düzeltme yapılmalıdır.\n"
            f"---------------------------------\n"
        )
        ekle("Art 16", "Rezerv Bildirimi", "UYARI", mektup)
        log.debug("[DEBUG] Art 16 bildirimi oluşturuldu. Rezerv sayısı: %d", len(rezerv_listesi))

    log.debug("[DEBUG] ucp_kurallari_uygula() tamamlandı. Toplam kayıt: %d", len(rapor))
    return rapor


# ---------------------------------------------------------------------------
# Geriye dönük uyumluluk — app.py eski import'ları için
# ---------------------------------------------------------------------------
def analiz_et(depo: dict) -> list:
    """
    KULLANIM DIŞI (deprecated).
    Eski app.py sürümleri bu fonksiyonu import ediyordu.
    v9.0'dan itibaren app.py doğrudan ucp_kurallari_uygula() çağırır.
    Bu sarmalayıcı yalnızca geriye dönük uyumluluk için bırakılmıştır.
    """
    log.warning(
        "analiz_et() çağrısı — bu fonksiyon kullanım dışı. "
        "Lütfen ucp_kurallari_uygula(parsed_data) kullanın."
    )
    return []
