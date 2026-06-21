"""
hukuk_motoru.py - UCP 600 / ISBP 821 Kural Motoru v3.0

Duzeltilen hatalar (v2 -> v3):
  - HATA-01: dict.upper() -> _metin() helper ile guveli erisim
  - HATA-02: Naive digit parser -> alan bazli kilo parser
  - HATA-03: Tek belge hatasi analizi durduruyor -> try/except izolasyon
  - HATA-04: kurallar.json yoksa eken donus -> bos dict ile devam
  - HATA-05: Tutar: goods_value vs cif_total -> CIF oncelikli parser
"""
from __future__ import annotations

import json
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

AY_MAP: dict[str, int] = {
    "JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
    "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12,
    "JANUARY":1,"FEBRUARY":2,"MARCH":3,"APRIL":4,"JUNE":6,
    "JULY":7,"AUGUST":8,"SEPTEMBER":9,"OCTOBER":10,"NOVEMBER":11,"DECEMBER":12,
}

KIRLI_BL = [
    "CLAUSED","DAMAGED","TORN","WET CARGO","INSUFFICIENT PACKING",
    "PARTLY DAMAGED","RUSTED","LEAKING","STAINED","BROKEN",
]


# ---------------------------------------------------------------------------
# Yardimci: depo erisimi - HATA-01 FIX
# ---------------------------------------------------------------------------
def _metin(depo: dict, anahtar: str) -> str:
    """depo[key] None, string veya dict olabilir. Her durumda string doner."""
    kayit = depo.get(anahtar)
    if kayit is None:
        return ""
    if isinstance(kayit, str):
        return kayit
    if isinstance(kayit, dict):
        v = kayit.get("metin") or kayit.get("icerik") or ""
        return v if isinstance(v, str) else ""
    return ""


# ---------------------------------------------------------------------------
# Tutar normallesme - HATA-05 FIX
# ---------------------------------------------------------------------------
def _normalize(metin: str) -> Optional[float]:
    """23,940 / 23.940 / 23,940.00 / 23.940,00 / USD 23,940 -> 23940.0"""
    if not metin:
        return None
    s = re.sub(r'[A-Za-z$\u20ac\xa3\t ]', '', str(metin)).strip()
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
            sonrasi = s[sv+1:]
            s = s.replace(',', '') if len(sonrasi) == 3 else s.replace(',', '.')
        elif nc == 1 and vc == 0:
            sonrasi = s[sn+1:]
            if len(sonrasi) == 3:
                s = s.replace('.', '')
        elif sv > sn:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
        return float(s) if s else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# CIF fatura ayrıstırıcı - HATA-05 FIX
# ---------------------------------------------------------------------------
def _invoice_tutarlari(metin: str) -> dict[str, Optional[float]]:
    def _bul(desenler):
        for d in desenler:
            m = re.search(d, metin, re.IGNORECASE)
            if m:
                v = _normalize(m.group(1))
                if v is not None:
                    return v
        return None

    goods = _bul([
        r'(?:GOODS?\s+VALUE|CARGO\s+VALUE|FOB\s+(?:VALUE|AMOUNT))'
        r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
    ])
    freight = _bul([
        r'(?:FREIGHT|OCEAN\s+FREIGHT)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
    ])
    ins = _bul([
        r'(?:INSURANCE\s+(?:PREMIUM|AMOUNT)|INS\.?)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
    ])
    cif = _bul([
        r'(?:TOTAL\s+CIF\s+(?:VALUE|AMOUNT)|CIF\s+(?:TOTAL|VALUE|AMOUNT))'
        r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
    ])
    total = _bul([
        r'(?:TOTAL\s+(?:INVOICE\s+)?(?:VALUE|AMOUNT)|INVOICE\s+(?:TOTAL|AMOUNT|VALUE)'
        r'|AMOUNT\s+DUE|GRAND\s+TOTAL)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)(?=\s*$)',
    ])
    if cif is None and goods is not None:
        computed = goods + (freight or 0) + (ins or 0)
        if computed > goods:
            cif = computed
    return {"goods_value": goods, "freight": freight, "insurance": ins,
            "cif_total": cif, "invoice_total": total}


def _lc_tutari(d: dict) -> Optional[float]:
    """Oncelik: cif_total > invoice_total > goods_value"""
    return d.get("cif_total") or d.get("invoice_total") or d.get("goods_value")


# ---------------------------------------------------------------------------
# Alan bazli kilo parser - HATA-02 FIX
# ---------------------------------------------------------------------------
def _kilo_bul(metin: str) -> Optional[float]:
    """GROSS WEIGHT / NET WEIGHT / WEIGHT / KGS onekli alanlardan kilo cikarir."""
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
            v = _normalize(m.group(1))
            if v:
                return v
    return None


# ---------------------------------------------------------------------------
# Tarih ayrıstırıcı
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# B/L tarih bulma - HATA-08 FIX
# ---------------------------------------------------------------------------
def _bl_tarihi(metin: str) -> Optional[str]:
    if not metin:
        return None
    t = (
        r'([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'
        r'|[\d]{4}-[\d]{2}-[\d]{2}'
        r'|[\d]{1,2}[-\s][A-Z]{3,9}[-\s][\d]{4}'
        r'|[\d]{1,2}\s+[A-Z][a-z]{2,8}\s+[\d]{4})'
    )
    desenler = [
        rf'SHIPPED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
        rf'SHIPPED\s+ON\s+BOARD\s*\n\s*{t}',
        rf'ON\s+BOARD\s+DATE\s*[:\-]?\s*{t}',
        rf'DATE\s+OF\s+SHIPMENT\s*[:\-]?\s*{t}',
        rf'LOADED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
        rf'VESSEL\s+LOADED\s*[:\-]?\s*{t}',
        rf'ON\s+BOARD\s*[:\-]?\s*{t}',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Kurallar yukleyici - HATA-04 FIX
# ---------------------------------------------------------------------------
def _kurallari_yukle() -> dict:
    try:
        with open("kurallar.json", encoding="utf-8") as f:
            data = json.load(f)
        log.debug("kurallar.json yuklendi.")
        return data
    except FileNotFoundError:
        log.warning("kurallar.json bulunamadi — bos kurallarla devam.")
        return {}
    except (json.JSONDecodeError, Exception) as e:
        log.error("kurallar.json hatasi: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Sigorta tutari - HATA-03 FIX
# ---------------------------------------------------------------------------
def _sigorta_tutari(metin: str) -> Optional[float]:
    if not metin:
        return None
    desenler = [
        r'(?:SUM\s+INSURED|AMOUNT\s+INSURED|INSURED\s+VALUE|INSURED\s+AMOUNT)'
        r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        r'(?:INSURANCE\s+AMOUNT|INSURANCE\s+VALUE|COVERAGE\s+AMOUNT|POLICY\s+AMOUNT)'
        r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
    ]
    for d in desenler:
        m = re.search(d, metin, re.IGNORECASE)
        if m:
            v = _normalize(m.group(1))
            if v:
                log.debug("Sigorta tutari = %.2f", v)
                return v
    return None


# ---------------------------------------------------------------------------
# Ana analiz fonksiyonu
# ---------------------------------------------------------------------------
def analiz_et(depo: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """
    UCP 600 kural motorunu calistirir.

    Parametreler
    ------------
    depo : dict
      Her deger string veya dict{"metin":...} olabilir.

    Doner
    -----
    list[tuple[madde, aciklama, durum, detay]]
      durum: OK | REZERV | UYARI | HATA | BILGI
    """
    log.debug("analiz_et() cagridi. Anahtarlar: %s", list(depo.keys()))

    rapor: list[tuple[str, str, str, str]] = []
    rezerv_var = False

    data = _kurallari_yukle()

    # ── 1. Kritik Kontroller (kurallar.json) ──────────────────────────
    for kural in data.get("kritik_kontroller", []):
        anahtar  = kural.get("anahtar", "")
        madde    = kural.get("madde", "?")
        aciklama = kural.get("aciklama", "")

        for evrak_tipi in depo:
            try:
                # HATA-01 FIX: _metin() ile dict.upper() hatasi yok
                icerik = _metin(depo, evrak_tipi)
                if not icerik:
                    continue
                if anahtar.upper() in icerik.upper():
                    rapor.append((madde, aciklama, "OK",
                                  f"Dogrulandi: '{anahtar}' — {evrak_tipi}"))
                    log.debug("Kural gecti: %s / %s", madde, evrak_tipi)
            except Exception as exc:
                # HATA-03 FIX: tek belge hatasi analizi durdurmaz
                log.error("Kural kontrolu hatasi [%s/%s]: %s", madde, evrak_tipi, exc)
                rapor.append((madde, aciklama, "HATA",
                              f"Belge:{evrak_tipi} | Hata:{exc} | {traceback.format_exc()}"))

    # ── 2. Tutar Kontrolu - HATA-05 FIX: CIF oncelikli ──────────────
    fatura_text = _metin(depo, "FATURA")
    kusat_text  = _metin(depo, "KUSAT")

    if fatura_text and kusat_text:
        try:
            fat_t = _invoice_tutarlari(fatura_text)
            fat_v = _lc_tutari(fat_t)

            # 32B alani veya serbest metin
            lc_v: Optional[float] = None
            m32b = re.search(r':?32B[:\s]*[A-Z]{3}\s*([\d,\.]+)', kusat_text, re.IGNORECASE)
            if m32b:
                lc_v = _normalize(m32b.group(1))
            if lc_v is None:
                lc_v = _lc_tutari(_invoice_tutarlari(kusat_text))

            log.debug("Tutar: Fatura CIF=%s | LC=%s", fat_v, lc_v)

            if fat_v is not None and lc_v is not None and lc_v > 0:
                sapma = abs(fat_v - lc_v) / lc_v * 100
                tolerans = 10 if any(
                    x in kusat_text.upper() for x in ["ABOUT", "APPROXIMATELY"]
                ) else 5
                if sapma <= tolerans:
                    rapor.append(("Art 30", "Tutar Tolerans", "OK",
                                  f"Fatura CIF:{fat_v:,.2f} | LC:{lc_v:,.2f} | "
                                  f"Sapma:%{sapma:.1f} <= %{tolerans}"))
                else:
                    rezerv_var = True
                    rapor.append(("Art 18", "Tutar Uyusmazligi", "REZERV",
                                  f"Fatura CIF:{fat_v:,.2f} | LC:{lc_v:,.2f} | "
                                  f"Sapma:%{sapma:.1f} > %{tolerans}"))
            else:
                rapor.append(("Art 30", "Tutar", "BILGI",
                              "Tutar tespit edilemedi — manuel kontrol."))
        except Exception as exc:
            log.error("Tutar kontrolu hatasi: %s", exc)
            rapor.append(("Art 30", "Tutar", "HATA",
                          f"{exc} | {traceback.format_exc()}"))

    # ── 3. Kilo Kontrolu - HATA-02 FIX: alan bazli parser ───────────
    konsimento_text = _metin(depo, "KONSIMENTO")

    if fatura_text and konsimento_text:
        try:
            fat_k = _kilo_bul(fatura_text)
            kon_k = _kilo_bul(konsimento_text)
            log.debug("Kilo: Fatura=%s | Konsimento=%s", fat_k, kon_k)

            if fat_k is not None and kon_k is not None:
                if abs(fat_k - kon_k) < 1.0:
                    rapor.append(("Art 30", "Kilo Kontrolu", "OK",
                                  f"Kilo eslesti: {fat_k:,.2f} KG"))
                else:
                    rezerv_var = True
                    rapor.append(("Art 30", "Kilo Kontrolu", "REZERV",
                                  f"Fatura:{fat_k:,.2f} KG | Konsimento:{kon_k:,.2f} KG"))
            else:
                eksik = ([n for n,v in [("Fatura",fat_k),("Konsimento",kon_k)] if v is None])
                rapor.append(("Art 30", "Kilo", "BILGI",
                              f"Kilo tespit edilemedi: {', '.join(eksik)}"))
        except Exception as exc:
            log.error("Kilo kontrolu hatasi: %s", exc)
            rapor.append(("Art 30", "Kilo", "HATA",
                          f"{exc} | {traceback.format_exc()}"))

    # ── 4. Shipped on Board (Art 20) ─────────────────────────────────
    if konsimento_text:
        try:
            bl_u = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
                rapor.append(("Art 20", "Shipped on Board", "OK",
                              "On Board serhi mevcut (Art 20a-ii)."))
            else:
                rezerv_var = True
                rapor.append(("Art 20", "Shipped on Board", "REZERV",
                              "On Board serhi bulunamadi!"))
        except Exception as exc:
            log.error("On Board kontrolu hatasi: %s", exc)
            rapor.append(("Art 20", "Shipped on Board", "HATA", str(exc)))

    # ── 5. Temiz Konsimento (Art 27) ─────────────────────────────────
    if konsimento_text:
        try:
            kirli = [k for k in KIRLI_BL if k in konsimento_text.upper()]
            if kirli:
                rezerv_var = True
                rapor.append(("Art 27", "Temiz Konsimento", "REZERV",
                              f"Kirli ifade: {', '.join(kirli)}"))
            else:
                rapor.append(("Art 27", "Temiz Konsimento", "OK",
                              "Olumsuz kloz bulunamadi (Art 27 uyumlu)."))
        except Exception as exc:
            log.error("Temiz BL kontrolu hatasi: %s", exc)
            rapor.append(("Art 27", "Temiz Konsimento", "HATA", str(exc)))

    # ── 6. B/L Yukleme Tarihi (Art 20) ───────────────────────────────
    if konsimento_text and kusat_text:
        try:
            bl_str = _bl_tarihi(konsimento_text)
            lc_44c = None
            for d in [
                r'44C[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
                r'44C[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
                r'LATEST\s+DATE\s+OF\s+SHIPMENT[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
            ]:
                m = re.search(d, kusat_text, re.IGNORECASE)
                if m:
                    lc_44c = m.group(1)
                    break

            if bl_str and lc_44c:
                bl_dt = _tarih(bl_str)
                lc_dt = _tarih(lc_44c)
                if bl_dt and lc_dt:
                    if bl_dt <= lc_dt:
                        rapor.append(("Art 20", "Yukleme Tarihi", "OK",
                                      f"B/L:{bl_str} <= 44C:{lc_44c}"))
                    else:
                        rezerv_var = True
                        rapor.append(("Art 20", "Yukleme Tarihi", "REZERV",
                                      f"GEC YUKLEME: B/L:{bl_str} > 44C:{lc_44c}"))
                else:
                    rapor.append(("Art 20", "Yukleme Tarihi", "BILGI",
                                  f"Tarih formati tanınamadi: B/L:{bl_str} | 44C:{lc_44c}"))
            else:
                rapor.append(("Art 20", "Yukleme Tarihi", "BILGI",
                              f"Tarih tespit edilemedi — B/L:{bl_str or '-'} 44C:{lc_44c or '-'}"))
        except Exception as exc:
            log.error("Yukleme tarihi hatasi: %s", exc)
            rapor.append(("Art 20", "Yukleme Tarihi", "HATA", str(exc)))

    # ── 7. Sigorta (Art 28) ───────────────────────────────────────────
    sigorta_text = _metin(depo, "SIGORTA")
    if kusat_text:
        try:
            cif_var = any(x in kusat_text.upper() for x in ["CIF", "CIP"])
            if cif_var:
                if sigorta_text:
                    sig_t = _sigorta_tutari(sigorta_text)
                    fat_t2 = _invoice_tutarlari(fatura_text)
                    fat_v2 = _lc_tutari(fat_t2)
                    if sig_t and fat_v2:
                        min_t = fat_v2 * 1.10
                        if sig_t >= min_t:
                            rapor.append(("Art 28", "Sigorta Teminati", "OK",
                                          f"Sigorta:{sig_t:,.2f} >= Min:{min_t:,.2f}"))
                        else:
                            rezerv_var = True
                            rapor.append(("Art 28", "Sigorta Teminati", "REZERV",
                                          f"Yetersiz: {sig_t:,.2f} < {min_t:,.2f}"))
                    else:
                        rapor.append(("Art 28", "Sigorta", "OK",
                                      "Sigorta belgesi mevcut (tutar kontrolu yapılamadı)."))
                else:
                    rezerv_var = True
                    rapor.append(("Art 28", "Sigorta", "REZERV",
                                  "CIF/CIP teslimde sigorta belgesi bulunamadi!"))
        except Exception as exc:
            log.error("Sigorta kontrolu hatasi: %s", exc)
            rapor.append(("Art 28", "Sigorta", "HATA", str(exc)))

    # ── 8. Zorunlu Kurallar (kurallar.json) ──────────────────────────
    for kural in data.get("zorunlu_kurallar", []):
        try:
            madde    = kural.get("madde", "?")
            aciklama = kural.get("aciklama", "")
            anahtar  = kural.get("anahtar", "")
            belge    = kural.get("belge", "")
            if not anahtar:
                continue
            hedef = _metin(depo, belge) if belge else ""
            if not hedef:
                hedef = " ".join(
                    _metin(depo, k) for k in depo if k != "DIGER_BELGELER"
                )
            if anahtar.upper() in hedef.upper():
                rapor.append((madde, aciklama, "OK", f"Zorunlu kural: '{anahtar}'"))
            else:
                rapor.append((madde, aciklama, "BILGI",
                              f"Anahtar bulunamadi: '{anahtar}' — manuel kontrol."))
        except Exception as exc:
            log.error("Zorunlu kural hatasi [%s]: %s", kural, exc)
            rapor.append(("?", str(kural), "HATA",
                          f"{exc} | {traceback.format_exc()}"))

    # ── 9. Art 16 Rezerv Bildirimi ────────────────────────────────────
    rezerv_listesi = [r for r in rapor if r[2] == "REZERV"]
    if rezerv_var and rezerv_listesi:
        ozet = "; ".join(r[3] for r in rezerv_listesi)
        mektup = (
            f"\n--- REZERV BILDIRIMI (Art 16) ---\n"
            f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"Inceleme sonucunda asagidaki uyumsuzluklar saptanmistir:\n"
            + "\n".join(f"  - {r[3]}" for r in rezerv_listesi) +
            f"\n5 is gunu icinde duzeltme yapilmalidir.\n"
            f"---------------------------------\n"
        )
        rapor.append(("Art 16", "Rezerv Bildirimi", "UYARI", mektup))
        log.debug("Art 16 bildirimi olusturuldu. Rezerv sayisi: %d", len(rezerv_listesi))

    log.debug("analiz_et() tamamlandi. Toplam kayit: %d", len(rapor))
    return rapor
