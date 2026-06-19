"""
hukuk_motoru.py — UCP 600 / ISBP 821 Kural Motoru
Üretim Ortamı Sürümü v2.0

Düzeltilen Kritik Hatalar:
  - BUG-01: 'dict' object has no attribute 'upper'
    depo[key] artık dict; icerik = depo[key]["metin"] şeklinde erişilir.
  - BUG-02: re.search(r"(\d+)") — ilk rakamı alıyordu (örn. Invoice No)
    Alan bazlı kilo parser'a geçildi (GROSS WEIGHT / NET WEIGHT / KGS önekli).
  - BUG-03: Herhangi bir belge hatası tüm analizi durduruyordu.
    Her belge try/except ile sarıldı; hata rapora yazılıp devam edildi.
  - BUG-04: kurallar.json yoksa fonksiyon erken dönüyordu.
    Dosya yoksa boş kurallar ile devam edilir, analiz durmuyor.
"""
from __future__ import annotations

import json
import logging
import re
import traceback
from datetime import datetime
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger("hukuk_motoru")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(levelname)s] hukuk_motoru: %(message)s"))
    log.addHandler(_h)
log.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
AY_MAP: dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3,  "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7,  "AUG": 8,
    "SEP": 9, "OCT": 10,"NOV": 11, "DEC": 12,
    "JANUARY":1,"FEBRUARY":2,"MARCH":3,"APRIL":4,
    "JUNE":6,"JULY":7,"AUGUST":8,"SEPTEMBER":9,
    "OCTOBER":10,"NOVEMBER":11,"DECEMBER":12,
}

KIRLI_BL: list[str] = [
    "CLAUSED","DAMAGED","TORN","WET CARGO",
    "INSUFFICIENT PACKING","PARTLY DAMAGED",
    "RUSTED","LEAKING","STAINED","BROKEN",
]


# ---------------------------------------------------------------------------
# Yardımcı: depodaki belgenin metin içeriğini güvenli şekilde al
# ---------------------------------------------------------------------------
def _metin(depo: dict[str, Any], anahtar: str) -> str:
    """
    depo[anahtar] None, string veya {"metin": "...", ...} olabilir.
    Her durumda string döner; hata olmaz.
    """
    kayit = depo.get(anahtar)
    if kayit is None:
        return ""
    if isinstance(kayit, str):
        # Eski format uyumluluğu: değer doğrudan string ise kabul et
        return kayit
    if isinstance(kayit, dict):
        v = kayit.get("metin") or kayit.get("icerik") or ""
        return v if isinstance(v, str) else ""
    return ""


# ---------------------------------------------------------------------------
# Yardımcı: Alan bazlı kilo parser — BUG-02 düzeltmesi
# ---------------------------------------------------------------------------
def _kilo_bul(metin: str) -> Optional[float]:
    """
    GROSS WEIGHT / NET WEIGHT / WEIGHT / KGS önekli değerleri bulur.
    re.search(r"(\d+)") gibi naive yaklaşım kullanılmaz.
    """
    if not metin:
        return None
    desenler = [
        r'(?:GROSS\s*WEIGHT|G\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TONS?)',
        r'(?:NET\s*WEIGHT|N\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TONS?)',
        r'(?:TOTAL\s+)?WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TONS?)',
        r'([\d,\.]+)\s*KGS\b',
    ]
    for desen in desenler:
        try:
            m = re.search(desen, metin, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", ""))
        except (ValueError, re.error):
            continue
    return None


# ---------------------------------------------------------------------------
# Yardımcı: Tarih ayrıştırma
# ---------------------------------------------------------------------------
def _tarih_ayristir(metin: str) -> Optional[datetime]:
    if not metin:
        return None
    # DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY
    m = re.search(r'(\d{1,2})[.\-/](\d{2})[.\-/](\d{4})', metin)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', metin)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # DD MON YYYY
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
# Yardımcı: Para tutarı bul
# ---------------------------------------------------------------------------
def _para_tutari_bul(metin: str) -> Optional[float]:
    if not metin:
        return None
    desenler = [
        r'(?:TOTAL\s+AMOUNT|INVOICE\s+(?:VALUE|AMOUNT)|TOTAL\s+VALUE|AMOUNT\s+DUE)'
        r'\s*[:\-]?\s*(?:USD|EUR|GBP|TRY|CNY|JPY)?\s*([\d,\.]+)',
        r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)',
    ]
    for desen in desenler:
        try:
            m = re.search(desen, metin, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", ""))
        except (ValueError, re.error):
            continue
    return None


# ---------------------------------------------------------------------------
# Kurallar yükleyici — BUG-04 düzeltmesi: dosya yoksa boş döner, çökmez
# ---------------------------------------------------------------------------
def _kurallari_yukle() -> dict[str, Any]:
    try:
        with open("kurallar.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        log.debug("kurallar.json başarıyla yüklendi.")
        return data
    except FileNotFoundError:
        log.warning("kurallar.json bulunamadı — kural kütüphanesi olmadan devam ediliyor.")
        return {}
    except json.JSONDecodeError as e:
        log.error("kurallar.json ayrıştırma hatası: %s", e)
        return {}
    except Exception as e:
        log.error("kurallar.json yüklenirken beklenmeyen hata: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Ana analiz fonksiyonu
# ---------------------------------------------------------------------------
def analiz_et(depo: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """
    UCP 600 kural motorunu çalıştırır.

    Parametreler
    ------------
    depo : dict
        Her değer şu iki formattan birini taşıyabilir:
          - Eski format: depo["FATURA"] = "metin..."  (string)
          - Yeni format: depo["FATURA"] = {"metin": "...", "ad": "dosya.pdf", ...}

    Döner
    -----
    list[tuple[madde, aciklama, durum, detay]]
      durum: "OK" | "REZERV" | "UYARI" | "HATA" | "BİLGİ"
    """
    log.debug("analiz_et() çağrıldı. Depo anahtarları: %s", list(depo.keys()))

    rapor: list[tuple[str, str, str, str]] = []
    rezerv_var_mi = False

    # ── 1. Kural Kütüphanesi ─────────────────────────────────────────────
    data = _kurallari_yukle()

    # ── 2. Kritik Kontroller (kurallar.json'dan) ─────────────────────────
    for kural in data.get("kritik_kontroller", []):
        anahtar   = kural.get("anahtar", "")
        madde     = kural.get("madde", "?")
        aciklama  = kural.get("aciklama", "")

        for evrak_tipi in depo:
            try:
                icerik = _metin(depo, evrak_tipi)   # BUG-01 FIX: dict.upper() yok
                if not icerik:
                    continue
                if anahtar.upper() in icerik.upper():
                    rapor.append((madde, aciklama, "OK",
                                  f"Doğrulandı: '{anahtar}' — {evrak_tipi}"))
                    log.debug("Kural geçti: %s / %s", madde, evrak_tipi)
            except Exception as exc:
                # BUG-03 FIX: tek belge hatası analizi durdurmaz
                hata_detay = traceback.format_exc()
                log.error("Kural kontrolü hatası [%s / %s]: %s", madde, evrak_tipi, exc)
                rapor.append((madde, aciklama, "HATA",
                              f"Belge: {evrak_tipi} | Hata: {exc} | Satır: {hata_detay}"))

    # ── 3. Kilo Çapraz Kontrolü ───────────────────────────────────────────
    fatura_text     = _metin(depo, "FATURA")
    konsimento_text = _metin(depo, "KONSIMENTO")

    if fatura_text and konsimento_text:
        try:
            fat_kilo = _kilo_bul(fatura_text)      # BUG-02 FIX: alan bazlı parser
            kon_kilo = _kilo_bul(konsimento_text)

            log.debug("Fatura kilo: %s | Konşimento kilo: %s", fat_kilo, kon_kilo)

            if fat_kilo is not None and kon_kilo is not None:
                if abs(fat_kilo - kon_kilo) < 0.5:
                    rapor.append(("Art 30", "Ağırlık Kontrolü", "OK",
                                  f"Kilo eşleşti: {fat_kilo:,.2f} KG"))
                else:
                    rezerv_var_mi = True
                    rapor.append(("Art 30", "Ağırlık Kontrolü", "REZERV",
                                  f"Fatura: {fat_kilo:,.2f} KG — "
                                  f"Konşimento: {kon_kilo:,.2f} KG — uyuşmuyor!"))
            else:
                eksik = []
                if fat_kilo is None:
                    eksik.append("Fatura kilo okunamadı")
                if kon_kilo is None:
                    eksik.append("Konşimento kilo okunamadı")
                rapor.append(("Art 30", "Ağırlık Kontrolü", "BİLGİ",
                              " | ".join(eksik) + " — manuel kontrol gerekli"))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("Kilo kontrolü hatası: %s", exc)
            rapor.append(("Art 30", "Ağırlık Kontrolü", "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 4. Tutar Çapraz Kontrolü ──────────────────────────────────────────
    kusat_text = _metin(depo, "KUSAT")

    if fatura_text and kusat_text:
        try:
            fat_tutar = _para_tutari_bul(fatura_text)
            lc_tutar  = _para_tutari_bul(kusat_text)

            log.debug("Fatura tutar: %s | LC tutar: %s", fat_tutar, lc_tutar)

            if fat_tutar is not None and lc_tutar is not None and lc_tutar > 0:
                sapma = abs(fat_tutar - lc_tutar) / lc_tutar * 100
                tolerans = 10 if any(
                    x in kusat_text.upper() for x in ["ABOUT", "APPROXIMATELY"]
                ) else 5
                if sapma <= tolerans:
                    rapor.append(("Art 30", "Tutar Tolerans Kontrolü", "OK",
                                  f"Fatura: {fat_tutar:,.2f} | LC: {lc_tutar:,.2f} | "
                                  f"Sapma: %{sapma:.1f} ≤ %{tolerans} (uyumlu)"))
                else:
                    rezerv_var_mi = True
                    rapor.append(("Art 18", "Tutar Uyuşmazlığı", "REZERV",
                                  f"Fatura: {fat_tutar:,.2f} | LC: {lc_tutar:,.2f} | "
                                  f"Sapma: %{sapma:.1f} > %{tolerans} — tolerans aşıldı!"))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("Tutar kontrolü hatası: %s", exc)
            rapor.append(("Art 18", "Tutar Kontrolü", "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 5. Shipped on Board Kontrolü (Art 20) ────────────────────────────
    if konsimento_text:
        try:
            bl_upper = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_upper or "ON BOARD" in bl_upper:
                rapor.append(("Art 20", "Shipped on Board", "OK",
                              "Konşimentoda 'Shipped on Board' şerhi mevcut (Art 20a-ii uyumlu)."))
            else:
                rezerv_var_mi = True
                rapor.append(("Art 20", "Shipped on Board", "REZERV",
                              "Konşimentoda zorunlu 'Shipped on Board' şerhi bulunamadı!"))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("B/L on-board kontrolü hatası: %s", exc)
            rapor.append(("Art 20", "Shipped on Board", "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 6. Temiz Konşimento Kontrolü (Art 27) ────────────────────────────
    if konsimento_text:
        try:
            kirli = [k for k in KIRLI_BL if k in konsimento_text.upper()]
            if kirli:
                rezerv_var_mi = True
                rapor.append(("Art 27", "Temiz Konşimento", "REZERV",
                              f"Kirli/klozlu ifade tespit edildi: {', '.join(kirli)}"))
            else:
                rapor.append(("Art 27", "Temiz Konşimento", "OK",
                              "Konşimentoda olumsuz kloz ifadesi bulunamadı (Art 27 uyumlu)."))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("Temiz B/L kontrolü hatası: %s", exc)
            rapor.append(("Art 27", "Temiz Konşimento", "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 7. Sigorta Varlığı (Art 28) ───────────────────────────────────────
    sigorta_text = _metin(depo, "SIGORTA")
    if kusat_text:
        try:
            cif_var = any(x in kusat_text.upper() for x in ["CIF", "CIP"])
            if cif_var:
                if sigorta_text:
                    rapor.append(("Art 28", "Sigorta Poliçesi", "OK",
                                  "CIF/CIP teslimde sigorta poliçesi mevcut (Art 28 uyumlu)."))
                else:
                    rezerv_var_mi = True
                    rapor.append(("Art 28", "Sigorta Poliçesi", "REZERV",
                                  "CIF/CIP teslim şartı olmasına rağmen sigorta belgesi bulunamadı!"))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("Sigorta kontrolü hatası: %s", exc)
            rapor.append(("Art 28", "Sigorta Poliçesi", "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 8. En Geç Yükleme Tarihi Kontrolü (Art 20 / 44C) ────────────────
    if konsimento_text and kusat_text:
        try:
            bl_tarih_str = None
            for desen in [
                r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE)'
                r'[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
                r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE)'
                r'[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
            ]:
                m = re.search(desen, konsimento_text, re.IGNORECASE)
                if m:
                    bl_tarih_str = m.group(1)
                    break

            lc_tarih_str = None
            for desen in [
                r'44C[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
                r'LATEST\s+DATE\s+OF\s+SHIPMENT[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
                r'44C[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
            ]:
                m = re.search(desen, kusat_text, re.IGNORECASE)
                if m:
                    lc_tarih_str = m.group(1)
                    break

            if bl_tarih_str and lc_tarih_str:
                bl_dt = _tarih_ayristir(bl_tarih_str)
                lc_dt = _tarih_ayristir(lc_tarih_str)
                if bl_dt and lc_dt:
                    if bl_dt <= lc_dt:
                        rapor.append(("Art 20", "Yükleme Tarihi Kontrolü", "OK",
                                      f"B/L: {bl_tarih_str} ≤ 44C: {lc_tarih_str} (uyumlu)"))
                    else:
                        rezerv_var_mi = True
                        rapor.append(("Art 20", "Yükleme Tarihi Kontrolü", "REZERV",
                                      f"GEÇ YÜKLEME: B/L tarihi ({bl_tarih_str}) "
                                      f"44C son tarihini ({lc_tarih_str}) aşıyor!"))
                else:
                    rapor.append(("Art 20", "Yükleme Tarihi Kontrolü", "BİLGİ",
                                  f"Tarih ayrıştırılamadı — B/L: {bl_tarih_str} | "
                                  f"44C: {lc_tarih_str} — manuel kontrol gerekli"))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("Yükleme tarihi kontrolü hatası: %s", exc)
            rapor.append(("Art 20", "Yükleme Tarihi Kontrolü", "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 9. Zorunlu Kural Kontrolleri (kurallar.json) ──────────────────────
    for kural in data.get("zorunlu_kurallar", []):
        try:
            madde    = kural.get("madde", "?")
            aciklama = kural.get("aciklama", "")
            anahtar  = kural.get("anahtar", "")
            belge    = kural.get("belge", "")   # hangi depoya bakacağı

            if not anahtar:
                continue

            hedef_metin = _metin(depo, belge) if belge else ""
            if not hedef_metin:
                # Tüm depoda ara
                hedef_metin = " ".join(
                    _metin(depo, k) for k in depo if k != "DIGER_BELGELER"
                )

            if anahtar.upper() in hedef_metin.upper():
                rapor.append((madde, aciklama, "OK", f"Zorunlu kural doğrulandı: {anahtar}"))
            else:
                rapor.append((madde, aciklama, "BİLGİ",
                              f"Zorunlu kural anahtar kelimesi bulunamadı: '{anahtar}' — "
                              f"manuel kontrol önerilir"))
        except Exception as exc:
            hata_detay = traceback.format_exc()
            log.error("Zorunlu kural kontrolü hatası [%s]: %s", kural, exc)
            rapor.append(("?", str(kural), "HATA",
                          f"Hata: {exc} | {hata_detay}"))

    # ── 10. Art 16 Rezerv Bildirim Mektubu ───────────────────────────────
    rezerv_listesi = [r for r in rapor if r[2] == "REZERV"]
    if rezerv_var_mi and rezerv_listesi:
        rezerv_ozeti = "; ".join(r[3] for r in rezerv_listesi)
        mektup = (
            f"\n--- REZERV BİLDİRİM MEKTUBU (Art 16) ---\n"
            f"Konu: UCP 600 Madde 16 gereği rezerv bildirimi.\n"
            f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"İnceleme sonucunda belgelerde uyumsuzluk saptanmıştır.\n"
            f"Söz konusu rezervler:\n  - {rezerv_ozeti.replace('; ', chr(10) + '  - ')}\n"
            f"5 iş günü içerisinde düzeltme yapılmalıdır.\n"
            f"------------------------------------------\n"
        )
        rapor.append(("Art 16", "Rezerv Bildirimi", "UYARI", mektup))
        log.debug("Art 16 rezerv bildirimi oluşturuldu. Rezerv sayısı: %d", len(rezerv_listesi))

    log.debug("analiz_et() tamamlandı. Toplam kayıt: %d", len(rapor))
    return rapor
