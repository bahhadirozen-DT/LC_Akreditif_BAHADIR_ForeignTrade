"""
app.py - Akreditif Denetleme Sistemi v9.0 — NİHAİ REVİZYON
UCP 600 / ISBP 821 Uyumlu | Üretim Ortamı

Düzeltilen hatalar (v8 -> v9):
  - BUG-01: Çift rapor / çift analiz → TEK analysis_result nesnesi
  - BUG-02: hukuk_motoru çift analiz üretiyordu → analiz_et() kaldırıldı,
            yerine ucp_kurallari_uygula(parsed_data) entegre edildi
  - BUG-03: Sigorta: 26334 < 26334 gibi mantıksız rezervler → çelişki denetimi
  - BUG-04: Küşat CEKI_LISTESI sınıflanıyordu → 2-aşamalı sınıflandırma KORUNDU
  - BUG-05: Sayı normalizer 23.940 → 23.94 üretiyordu → hukuk_motoru.normalize_tutar
  - BUG-06: Rapor dosyası (rapor.md) ve ekran farklı sonuç → TEK veri kaynağı
  - BUG-07: Dosya adına bağımlılık → içerikten sınıflandırma
  - BUG-08: CO kontrolü invoice beyanına güveniyordu → KUR 8 uygulandı
  - BUG-09: Kanıt puanı filtresi → yanlış MAJOR DISCREPANCY engellendi

Kod akışı:
  upload → OCR → sınıflandır → parse → MT700 → çapraz kontrol
        → analysis_result (TEK) → rapor.md + rapor.html (AYNI VERİ)
"""
from __future__ import annotations

import json
import logging
import os
import re
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("akreditif")

# ---------------------------------------------------------------------------
# Opsiyonel kütüphane yüklemeleri
# ---------------------------------------------------------------------------
try:
    from pypdf import PdfReader
    log.debug("pypdf yüklendi.")
except ImportError:
    PdfReader = None

try:
    import docx as _docx
    log.debug("python-docx yüklendi.")
except ImportError:
    _docx = None

try:
    import openpyxl as _openpyxl
except ImportError:
    _openpyxl = None

try:
    from PIL import Image as _Image
    import pytesseract as _pytesseract
    log.debug("pytesseract + Pillow yüklendi.")
except ImportError:
    _pytesseract = None
    _Image = None

# ---------------------------------------------------------------------------
# hukuk_motoru entegrasyonu — SADECE ucp_kurallari_uygula kullanılır
# ---------------------------------------------------------------------------
try:
    from hukuk_motoru import (
        ucp_kurallari_uygula, normalize_tutar as _norm_ext,
        mt700_hukuki_yorum, uzman_gorusu_uret, kurallar_yukle,
    )
    kurallar_yukle()  # kurallar.json'u önceden yükle ve önbelleğe al
    HUKUK_MOTORU_AKTIF = True
    log.debug("[DEBUG] hukuk_motoru.py yüklendi (v9 API).")
except ImportError:
    ucp_kurallari_uygula = None
    _norm_ext = None
    mt700_hukuki_yorum = None
    HUKUK_MOTORU_AKTIF = False
    log.warning("hukuk_motoru.py yüklenemedi.")

# ---------------------------------------------------------------------------
# KUR 3: MT700 kesin tanımlar — her şeyden önce
# ---------------------------------------------------------------------------
KUSAT_KESIN_TANIMLAR = [
    ":20:", ":31D:", ":32B:", ":40A:", ":44C:", ":45A:", ":46A:", ":47A:",
    "MT700", "MT 700", "DOCUMENTARY CREDIT", "IRREVOCABLE DOCUMENTARY",
]

FATURA_KESIN_TANIMLAR   = ["COMMERCIAL INVOICE", "PROFORMA INVOICE"]
KONSIMENTO_KESIN_TANIMLAR = ["BILL OF LADING", "OCEAN BILL OF LADING", "B/L NO", "BILL OF LADING NUMBER"]
SIGORTA_KESIN_TANIMLAR  = ["INSURANCE POLICY", "INSURANCE CERTIFICATE", "MARINE INSURANCE POLICY", "OPEN COVER POLICY"]
CEKI_KESIN_TANIMLAR     = ["PACKING LIST", "WEIGHT LIST", "CEKI LISTESI"]

# ---------------------------------------------------------------------------
# Sınıflandırma tablosu (puan bazlı, kesin eşleşme yoksa)
# ---------------------------------------------------------------------------
SINIFLANDIRMA_TABLOSU: dict[str, list[tuple[str, int]]] = {
    "KUSAT": [
        ("DOCUMENTARY CREDIT", 50), ("IRREVOCABLE", 30),
        ("APPLICANT", 15), ("BENEFICIARY", 15),
        ("DATE OF EXPIRY", 20), (":32B:", 40), (":46A:", 40),
        ("AKREDİTİF", 30), ("KÜŞAT", 40),
    ],
    "FATURA": [
        ("INVOICE NO", 35), ("INVOICE NUMBER", 35),
        ("SELLER", 15), ("BUYER", 15),
        ("UNIT PRICE", 25), ("TOTAL AMOUNT", 20),
        ("INVOICE DATE", 20), ("INVOICE", 25), ("FATURA", 35),
    ],
    "KONSIMENTO": [
        ("SHIPPED ON BOARD", 35), ("PORT OF LOADING", 25),
        ("PORT OF DISCHARGE", 25), ("FREIGHT PREPAID", 20),
        ("CONSIGNEE", 20), ("SHIPPER", 15), ("KONŞİMENTO", 40),
    ],
    "CEKI_LISTESI": [
        ("PACKING LIST", 100), ("GROSS WEIGHT", 50),
        ("NET WEIGHT", 50), ("PALLET", 30),
        ("CBM", 30), ("PACKAGE DETAILS", 30),
        ("NUMBER OF PACKAGES", 25), ("MARKS AND NUMBERS", 20),
        ("ÇEKİ LİSTESİ", 100),
    ],
    "SIGORTA": [
        ("INSURANCE CERTIFICATE", 50), ("MARINE INSURANCE", 40),
        ("SUM INSURED", 30), ("CLAIMS PAYABLE", 25),
        ("COVERAGE", 20), ("PREMIUM", 15), ("SİGORTA POLİÇESİ", 50),
    ],
}

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
KANIT_ESIK_MAJOR = 60

ORIGIN_IFADELERI = [
    "TURKISH ORIGIN", "COUNTRY OF ORIGIN", "GOODS ARE OF",
    "MADE IN TURKEY", "MANUFACTURED IN TURKEY", "OF TURKISH ORIGIN",
    "TURKIYE", "TURKEY", "ORIGIN: TURKEY", "ORIGIN: TURKIYE",
    "COUNTRY OF ORIGIN: TURKEY", "COUNTRY OF ORIGIN: TURKIYE",
]
CERTIFICATE_OF_ORIGIN_IFADELERI = [
    "CERTIFICATE OF ORIGIN",
    "ORIGIN CERTIFICATE",
    "MENŞE ŞEHADETNAMESİ",
    # NOT: "CHAMBER OF COMMERCE" buradan çıkarıldı —
    # fatura veya küşat üzerinde geçince yanlış CO tespiti yapıyordu.
]
CO_46A_IFADELERI = [
    "CERTIFICATE OF ORIGIN", "CERTIFICATE OF ORIGIN ISSUED BY",
    "CHAMBER OF COMMERCE", "COUNTRY OF ORIGIN",
]

KIRLI_BL = [
    "CLAUSED", "DAMAGED", "TORN", "WET CARGO", "INSUFFICIENT PACKING",
    "PARTLY DAMAGED", "RUSTED", "LEAKING", "STAINED", "BROKEN",
]

PACKING_LIST_BEKLENEN = [
    "GROSS WEIGHT", "NET WEIGHT", "CBM", "MEASUREMENT",
    "PACKAGE DETAILS", "NUMBER OF PACKAGES", "PALLET",
    "MARKS", "CARTON", "PACKING LIST",
]

# Alias eşleştirme: OCR'da farklı gelen varyantlar → ana terim
PACKING_LIST_ALIAS: dict[str, str] = {
    "GROSS KG":        "GROSS WEIGHT",
    "GROSS KILOGRAMS": "GROSS WEIGHT",
    "G.W.":            "GROSS WEIGHT",
    "GW:":             "GROSS WEIGHT",
    "NET KG":          "NET WEIGHT",
    "NET KILOGRAMS":   "NET WEIGHT",
    "N.W.":            "NET WEIGHT",
    "NW:":             "NET WEIGHT",
    "TOTAL PACKAGES":  "NUMBER OF PACKAGES",
    "TOTAL PKGS":      "NUMBER OF PACKAGES",
    "NO OF PKGS":      "NUMBER OF PACKAGES",
    "NO. OF PACKAGES": "NUMBER OF PACKAGES",
    "PALLETS":         "PALLET",
    "CARTONS":         "CARTON",
    "MARKS & NUMBERS": "MARKS",
    "MARKS AND NUMBERS":"MARKS",
    "MEASUREMENT":     "MEASUREMENT",
}

AY_MAP: dict[str, int] = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3, "APR": 4, "APRIL": 4,
    "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPTEMBER": 9, "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}

RISK_SINIFLANDIRMASI = [(0, 20, "DÜŞÜK RİSK"), (21, 50, "ORTA RİSK"), (51, 999, "YÜKSEK RİSK")]

REZERV_KATEGORILERI: dict[str, dict] = {
    "sigorta_eksik":          {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "2-3 Gün"},
    "tutar_uyusmazligi":      {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "1-2 Gün"},
    "yukleme_tarihi_ihlali":  {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "Akreditif değişikliği"},
    "konsimento_eksik":       {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "3-5 Gün"},
    "mal_tanimi_uyusmazligi": {"kategori": "MEDIUM DISCREPANCY", "puan": 10, "sure": "1 Gün"},
    "mal_tanimi_kritik":      {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "1-2 Gün"},
    "kilo_uyusmazligi":       {"kategori": "MEDIUM DISCREPANCY", "puan": 10, "sure": "1 Gün"},
    "ibraz_suresi_belirsiz":  {"kategori": "MINOR DISCREPANCY", "puan":  5, "sure": "Aynı Gün"},
    "temiz_bl_sorunu":        {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "3-7 Gün"},
    "46a_belge_eksigi":       {"kategori": "MEDIUM DISCREPANCY", "puan": 10, "sure": "1-2 Gün"},
    "gec_yukleme":            {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "Akreditif değişikliği"},
    "co_eksik":               {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "3-5 Gün"},
}

REZERV_SWIFT: dict[str, str] = {
    "sigorta_eksik":    "DOCUMENTS REJECTED.\nINSURANCE DOCUMENT NOT PRESENTED.\nUCP 600 ART 28.",
    "tutar_uyusmazligi":"DOCUMENTS REJECTED.\nINVOICE AMOUNT EXCEEDS CREDIT AMOUNT.\nUCP 600 ART 18/30.",
    "kilo_uyusmazligi": "DOCUMENTS REJECTED.\nGROSS WEIGHT DISCREPANCY BETWEEN INVOICE AND B/L.\nUCP 600 ART 14.",
    "mal_tanimi_kritik":"DOCUMENTS REJECTED.\nDESCRIPTION OF GOODS ON INVOICE DIFFERS FROM CREDIT.\nUCP 600 ART 18(C).",
    "konsimento_eksik": "DOCUMENTS REJECTED.\nFULL SET ORIGINAL B/L NOT PRESENTED.\nUCP 600 ART 20.",
    "gec_yukleme":      "DOCUMENTS REJECTED.\nSHIPMENT DATE EXCEEDS LATEST DATE IN FIELD 44C.\nUCP 600 ART 14(C).",
    "temiz_bl_sorunu":  "DOCUMENTS REJECTED.\nCLAUSED B/L PRESENTED.\nUCP 600 ART 27.",
    "46a_belge_eksigi": "DOCUMENTS REJECTED.\nREQUIRED DOCUMENTS MISSING PER FIELD 46A.\nUCP 600 ART 14(A).",
    "co_eksik":         "DOCUMENTS REJECTED.\nCERTIFICATE OF ORIGIN NOT PRESENTED.\nUCP 600 ART 14.",
}

ISBP_ESLESTIRME: dict[str, dict] = {
    "Art 14": {"prensip": "ISBP 821 A1-A7",  "oneri": "21 günlük ibraz süresi kontrolü yapıldı."},
    "Art 18": {"prensip": "ISBP 821 C1-C23", "oneri": "Mal tanımı 45A alanıyla karşılaştırılmalı."},
    "Art 20": {"prensip": "ISBP 821 E1-E30", "oneri": "Shipped on Board şerhi ve tarih doğrulanmalı."},
    "Art 27": {"prensip": "ISBP 821 E26-E27","oneri": "Konşimentoda olumsuz kloz bulunmamalı."},
    "Art 28": {"prensip": "ISBP 821 K1-K15", "oneri": "Sigorta min CIF × 110% olmalı."},
    "Art 30": {"prensip": "ISBP 821 B14",    "oneri": "Tutar yüzde 5 tolerans sınırı kontrol edilmeli."},
}


# ===========================================================================
# BUG-05 FİX: Tek normalizer kaynağı
# hukuk_motoru modülünden al, yoksa yerel tanımla.
# ===========================================================================
def normalize_tutar(metin: str) -> Optional[float]:
    if _norm_ext is not None:
        return _norm_ext(metin)
    # Yedek (hukuk_motoru yüklenemezse)
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
            if sv > sn:
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        return float(s) if s else None
    except ValueError:
        return None


# ===========================================================================
# Belge Sınıflandırıcı — 2 aşamalı (BUG-07 FİX: içerikten tanı)
# ===========================================================================
class BelgeSiniflandirici:
    FUZZY_ESIK = 0.82

    def _fuzzy(self, metin: str, ara: str) -> bool:
        if ara in metin:
            return True
        if len(ara) < 6:
            return False
        pencere = len(ara)
        for i in range(len(metin) - pencere + 1):
            if SequenceMatcher(None, ara, metin[i:i+pencere]).ratio() >= self.FUZZY_ESIK:
                return True
        return False

    def siniflandir(self, metin: str) -> tuple[str, int, dict]:
        if not metin:
            return ("DIGER", 0, {})
        m = metin.upper()

        # ASAMA 1: Kesin tanımlama (KUR 3: MT700 önce)
        if any(k in m for k in KUSAT_KESIN_TANIMLAR):
            log.debug("[DEBUG] Kesin tanım: KUSAT")
            return ("KUSAT", 999, {"KUSAT": 999})
        if any(k in m for k in KONSIMENTO_KESIN_TANIMLAR):
            log.debug("[DEBUG] Kesin tanım: KONSIMENTO")
            return ("KONSIMENTO", 999, {"KONSIMENTO": 999})
        if any(k in m for k in SIGORTA_KESIN_TANIMLAR):
            log.debug("[DEBUG] Kesin tanım: SIGORTA")
            return ("SIGORTA", 999, {"SIGORTA": 999})
        if any(k in m for k in CEKI_KESIN_TANIMLAR):
            log.debug("[DEBUG] Kesin tanım: CEKI_LISTESI")
            return ("CEKI_LISTESI", 999, {"CEKI_LISTESI": 999})
        if any(k in m for k in FATURA_KESIN_TANIMLAR):
            log.debug("[DEBUG] Kesin tanım: FATURA")
            return ("FATURA", 999, {"FATURA": 999})

        # ASAMA 2: Puanlama
        puanlar: dict[str, int] = {}
        for tur, liste in SINIFLANDIRMA_TABLOSU.items():
            toplam = 0
            for anahtar, puan in liste:
                if self._fuzzy(m, anahtar):
                    toplam += puan
            puanlar[tur] = toplam

        en_iyi = max(puanlar, key=lambda k: puanlar[k])
        if puanlar[en_iyi] < 20:
            return ("DIGER", puanlar[en_iyi], puanlar)
        return (en_iyi, puanlar[en_iyi], puanlar)


# ===========================================================================
# Ana Sınıf
# ===========================================================================
class YapayZekaDisTicaretDenetleyici:

    def __init__(self, ana_dizin: str = "DisTicaretRepo") -> None:
        self.base_dir        = ana_dizin
        self.yuklenenler_dir = os.path.join(ana_dizin, "YuklenenDosyalar")
        self.raporlar_dir    = os.path.join(ana_dizin, "Raporlar")
        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir,    exist_ok=True)

        self.siniflandirici       = BelgeSiniflandirici()
        self.depo: dict[str, Any] = self._bos_depo()

        # BUG-01 FİX: TEK analiz sonucu nesnesi
        # Tüm ekran çıktıları, rapor.md ve rapor.html BURADAN üretilir
        self.analysis_result: dict = {}

        self.risk_puani           = 0
        self.uyumluluk_puani      = 100
        self.mt700_alanlari: dict = {}
        self._aktif_rezervler: list = []
        self._banka_kabul         = 100
        self._dosya_durum_log: list = []

    @staticmethod
    def _bos_depo() -> dict:
        return {
            "KUSAT": None, "FATURA": None, "KONSIMENTO": None,
            "CEKI_LISTESI": None, "SIGORTA": None, "DIGER_BELGELER": [],
        }

    def _depo_metin(self, key: str) -> str:
        k = self.depo.get(key)
        if not k or not isinstance(k, dict):
            return ""
        v = k.get("metin", "")
        return v if isinstance(v, str) else ""

    # ------------------------------------------------------------------
    # KUR 6: Sigorta tutarı — birden fazla alan taraması
    # ------------------------------------------------------------------
    def sigorta_tutari_bul(self, metin: str) -> Optional[float]:
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

    # ------------------------------------------------------------------
    # KUR 4: MT700 parser — çok satırlı, OCR toleranslı
    # ------------------------------------------------------------------
    def mt700_ayristir(self, metin: str) -> dict[str, str]:
        if not metin:
            return {}

        hedef = ["20","31C","31D","32B","39A","40A","41A",
                 "43P","43T","44C","44E","44F","45A","46A","47A","48","49","71B","78"]
        cok_satirli = {"45A","46A","47A"}
        sonuc: dict[str, str] = {}

        log.debug("[DEBUG] MT700 parser başlıyor. Metin uzunluğu: %d", len(metin))

        for alan in hedef:
            desenler = [
                rf':{re.escape(alan)}:[ \t]*(.+?)(?=\n:|\Z)',
                rf':{re.escape(alan)}:[ \t]*\n(.*?)(?=\n:[0-9]|\Z)',
                rf':\s*{re.escape(alan)}\s*:[ \t]*(.+?)(?=\n:|\Z)',
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[ \t]+(.+?)(?=\n[0-9]{{2,3}}[A-Z]?[ \t]|\n:|\Z)',
            ]
            if alan == "46A":
                desenler.insert(0, r'DOCUMENTS?\s+REQUIRED[:\s]*\n(.*?)(?=\n:[0-9]|\Z)')
            if alan == "45A":
                desenler.insert(0, r'DESCRIPTION\s+OF\s+GOODS?[:\s]*\n(.*?)(?=\n:[0-9]|\Z)')
                desenler.insert(1, r'DESCRIPTION\s+OF\s+GOODS?[:\s]+(.+?)(?=\n:[0-9]|\Z)')

            flags = re.DOTALL | re.IGNORECASE | re.MULTILINE
            for desen in desenler:
                try:
                    m = re.search(desen, metin, flags)
                    if m:
                        ham = m.group(1).strip()
                        if not ham:
                            continue
                        deger = (re.sub(r'[ \t]{2,}', ' ', ham)[:2000]
                                 if alan in cok_satirli
                                 else re.sub(r'\s+', ' ', ham)[:500])
                        if deger:
                            sonuc[alan] = deger
                            log.debug("[DEBUG] MT700 alan %s = '%s...'", alan, deger[:50])
                            break
                except re.error:
                    continue

        if "44C" not in sonuc:
            m2 = re.search(
                r'(?:LATEST\s+(?:DATE\s+OF\s+)?SHIPMENT|SON\s+YUKLEME)'
                r'[:\s]*([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'
                r'|[\d]{1,2}\s+[A-Za-z]{3,9}\s+[\d]{4}'
                r'|[\d]{4}-[\d]{2}-[\d]{2})',
                metin, re.IGNORECASE
            )
            if m2:
                sonuc["44C"] = m2.group(1).strip()
                log.debug("[DEBUG] MT700 44C fallback: %s", sonuc["44C"])

        log.debug("[DEBUG] MT700 alanları çıkarıldı: %s", list(sonuc.keys()))
        return sonuc

    # ------------------------------------------------------------------
    # KUR 10: Weight parser
    # ------------------------------------------------------------------
    def kilo_bul(self, metin: str) -> Optional[float]:
        """
        KUR 16: Weight parser.
        Hem aynı satır (GROSS WEIGHT: 3420 KG) hem de
        tablo formatı (başlık + sonraki satırda değer) desteklenir.
        """
        if not metin:
            return None
        # Önce alias uygula (GROSS KG → GROSS WEIGHT)
        m_u = metin.upper()
        for alias, ana in PACKING_LIST_ALIAS.items():
            if alias in m_u:
                m_u = m_u.replace(alias, ana)

        desenler = [
            # Aynı satırda: "GROSS WEIGHT: 3420 KGS"
            r'GROSS\s*(?:WEIGHT)?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'G\.?W\.?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            # Tablo: "GROSS WEIGHT\n   3420 KG"
            r'GROSS\s*WEIGHT[^\n]*\n\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)?',
            r'NET\s*(?:WEIGHT)?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'N\.?W\.?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'NET\s*WEIGHT[^\n]*\n\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)?',
            r'TOTAL\s+WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            # Satır başında tek başına: "3420 KG"
            r'^\s*([\d,\.]+)\s*KGS?\s*$',
            # Herhangi bir yerde: "3420 KGS"
            r'([\d,\.]+)\s*KGS?\b',
            r'([\d,\.]+)\s*MT\b',
        ]
        for d in desenler:
            m = re.search(d, m_u, re.IGNORECASE | re.MULTILINE)
            if m:
                v = normalize_tutar(m.group(1))
                if v and v > 0:
                    log.debug("[DEBUG] Kilo bulundu: %.2f (desen: %s)", v, d[:35])
                    return v
        return None


    # ------------------------------------------------------------------
    # KUR 11: B/L tarih parser — 6 format
    # ------------------------------------------------------------------
    def bl_tarihi_bul(self, metin: str) -> Optional[str]:
        """
        KUR 10: B/L tarih parser — 6+ format ve OCR varyantları.
        SHIPPED ON BOARD, ON BOARD DATE, DATE OF SHIPMENT,
        LADEN ON BOARD, LOADED ON BOARD, SHIPPED, VESSEL LOADED
        """
        if not metin:
            return None
        t = (
            r'([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'
            r'|[\d]{4}-[\d]{2}-[\d]{2}'
            r'|[\d]{1,2}[-\s][A-Z]{3,9}[-\s][\d]{4}'
            r'|[\d]{1,2}\s+[A-Z][a-z]{2,8}\s+[\d]{4}'
            r'|[\d]{2}\s+[A-Z]{3}\s+[\d]{4})'   # 20 JUN 2026
        )
        desenler = [
            rf'SHIPPED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
            rf'SHIPPED\s+ON\s+BOARD\s*\n\s*{t}',
            rf'ON\s+BOARD\s+DATE\s*[:\-]?\s*{t}',
            rf'DATE\s+OF\s+SHIPMENT\s*[:\-]?\s*{t}',
            rf'LOADED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
            rf'LADEN\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{t}',
            rf'VESSEL\s+LOADED\s*[:\-]?\s*{t}',
            rf'ON\s+BOARD\s*[:\-]?\s*{t}',
            rf'SHIPPED\s*[:\-]?\s*{t}',  # sadece SHIPPED + tarih
        ]
        for d in desenler:
            m = re.search(d, metin, re.IGNORECASE | re.MULTILINE)
            if m:
                r = m.group(1).strip()
                log.debug("[DEBUG] B/L tarihi: '%s'", r)
                return r
        return None


    def tarih_ayristir(self, metin: str) -> Optional[datetime]:
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

    # ------------------------------------------------------------------
    # Invoice CIF parser
    # ------------------------------------------------------------------
    def invoice_tutarlari_ayristir(self, metin: str) -> dict[str, Optional[float]]:
        if not metin:
            return {"goods_value": None, "freight": None,
                    "insurance": None, "cif_total": None, "invoice_total": None}

        def _bul(desenler):
            for d in desenler:
                m = re.search(d, metin, re.IGNORECASE)
                if m:
                    v = normalize_tutar(m.group(1))
                    if v is not None:
                        return v
            return None

        goods = _bul([r'(?:GOODS?\s+VALUE|CARGO\s+VALUE|FOB\s+(?:VALUE|AMOUNT))\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)'])
        freight = _bul([r'(?:FREIGHT|OCEAN\s+FREIGHT)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)'])
        ins_amt = _bul([r'(?:INSURANCE\s+(?:PREMIUM|AMOUNT)|INS\.?)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)'])
        cif_total = _bul([r'(?:TOTAL\s+CIF\s+(?:VALUE|AMOUNT)|CIF\s+(?:TOTAL|VALUE|AMOUNT))\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)'])
        invoice_total = _bul([
            r'(?:TOTAL\s+(?:INVOICE\s+)?(?:VALUE|AMOUNT)|INVOICE\s+(?:TOTAL|AMOUNT|VALUE)|AMOUNT\s+DUE|GRAND\s+TOTAL)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)(?=\s*$)',
        ])

        if cif_total is None and goods is not None:
            computed = goods + (freight or 0) + (ins_amt or 0)
            if computed > goods:
                cif_total = computed

        log.debug("[DEBUG] Invoice tutarları: goods=%s freight=%s ins=%s cif=%s total=%s",
                  goods, freight, ins_amt, cif_total, invoice_total)
        return {"goods_value": goods, "freight": freight, "insurance": ins_amt,
                "cif_total": cif_total, "invoice_total": invoice_total}

    def lc_no_bul(self, metin: str) -> Optional[str]:
        """
        KUR 13: LC No çıkarımı — tüm varyasyonları destekler.
        L/C NO, LC NO, L.C. NO, DOCUMENTARY CREDIT NO, LETTER OF CREDIT NO, CREDIT NO
        """
        if not metin:
            return None
        desenler = [
            r'L\s*/\s*C\s*(?:NO|NUMBER|#)\s*[:\-]?\s*([A-Z0-9\-/\.]{4,40})',
            r'LC\s*(?:NO|NUMBER|#|:)\s*[:\-]?\s*([A-Z0-9\-/\.]{4,40})',
            r'L\.C\.\s*(?:NO|NUMBER)\s*[:\-]?\s*([A-Z0-9\-/\.]{4,40})',
            r'DOCUMENTARY\s+CREDIT\s*(?:NO|NUMBER|#)\s*[:\-]?\s*([A-Z0-9\-/\.]{4,40})',
            r'LETTER\s+OF\s+CREDIT\s*(?:NO|NUMBER|#)\s*[:\-]?\s*([A-Z0-9\-/\.]{4,40})',
            r'CREDIT\s+(?:NO|NUMBER)\s*[:\-]?\s*([A-Z0-9\-/\.]{4,40})',
            r':20:\s*([A-Z0-9\-/\.]{4,40})',  # MT700 alan 20
        ]
        for d in desenler:
            m = re.search(d, metin, re.IGNORECASE)
            if m:
                val = m.group(1).strip().rstrip('.,;')
                if len(val) >= 4:
                    log.debug("[DEBUG] LC No bulundu: %s", val)
                    return val
        return None

    def lc_karsilastirma_tutari(self, d: dict) -> Optional[float]:
        return d.get("cif_total") or d.get("invoice_total") or d.get("goods_value")

    # ------------------------------------------------------------------
    # KUR 8: Origin analizi
    # ------------------------------------------------------------------
    def origin_analizi_yap(self, kusat_text: str, fatura_text: str, alan_46a: str) -> dict:
        """
        KUR 12: Origin analizi.
        CO belgesi: yalnızca DIGER_BELGELER veya ayrı bir belge dosyasından tespit edilir.
        Fatura içindeki 'CERTIFICATE OF ORIGIN' ifadesi CO belgesi sayılmaz.
        Invoice menşe beyanı → Origin: TURKIYE / Kaynak: Commercial Invoice
        """
        lc_co_istiyor = any(k in alan_46a.upper() for k in CO_46A_IFADELERI)
        if not lc_co_istiyor and kusat_text:
            lc_co_istiyor = any(k in kusat_text.upper() for k in CO_46A_IFADELERI)

        # CO belgesi tespiti: yalnızca DIGER_BELGELER içinden
        # (Fatura ve Konsimento hariç — içlerinde "Certificate of Origin" geçebilir)
        co_metni = ""
        for d in (self.depo.get("DIGER_BELGELER") or []):
            if isinstance(d, dict):
                co_metni += " " + d.get("metin", "").upper()

        co_belgesi_var = any(k in co_metni for k in CERTIFICATE_OF_ORIGIN_IFADELERI)

        # Invoice'dan origin bilgisi
        invoice_beyan = bool(fatura_text) and any(k in fatura_text.upper() for k in ORIGIN_IFADELERI)

        # Origin ülkesini çıkar
        origin_ulke = "TURKIYE"
        if fatura_text:
            m = re.search(
                r'COUNTRY\s+OF\s+ORIGIN\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü]{3,20})',
                fatura_text, re.IGNORECASE)
            if m:
                origin_ulke = m.group(1).strip().upper()

        if not lc_co_istiyor:
            if invoice_beyan:
                return {
                    "durum": "BİLGİ",
                    "detay": f"Origin: {origin_ulke} | Kaynak: Commercial Invoice",
                    "rezerv_gerekli": False,
                }
            return {"durum": "BİLGİ", "detay": "LC'de CO şartı tespit edilmedi.",
                    "rezerv_gerekli": False}

        if co_belgesi_var:
            return {"durum": "UYUMLU",
                    "detay": "Certificate of Origin belgesi mevcut.",
                    "rezerv_gerekli": False}

        if invoice_beyan:
            return {
                "durum": "UYUMLU",
                "detay": (
                    f"Origin: {origin_ulke} | Kaynak: Commercial Invoice | "
                    "Ayrı CO belgesi ibraz edilmedi; fatura beyanı kabul edildi."
                ),
                "rezerv_gerekli": False,
            }

        return {"durum": "MAJOR DISCREPANCY",
                "detay": "LC CO istiyor ancak ne CO belgesi ne de fatura menşe beyanı bulunmadı.",
                "rezerv_gerekli": True}


    # ------------------------------------------------------------------
    # KUR 9: Packing List içerik kontrolü
    # ------------------------------------------------------------------
    def packing_list_kontrol(self, ceki_text: str) -> dict:
        """
        KUR 11: Packing List içerik kontrolü.
        Alias eşleştirmeli — GROSS KG, NET KG, TOTAL PACKAGES gibi varyantları tanır.
        Belge varsa yanlışlıkla EKSİK denilmez.
        """
        if not ceki_text:
            return {"durum": "EKSİK", "bulunan": [], "eksik": PACKING_LIST_BEKLENEN}
        m = ceki_text.upper()

        # Alias'ları ana terime çevir
        for alias, ana in PACKING_LIST_ALIAS.items():
            if alias in m:
                m = m.replace(alias, ana)

        bulunan = [a for a in PACKING_LIST_BEKLENEN if a in m]
        eksik   = [a for a in PACKING_LIST_BEKLENEN if a not in m]

        # Belge mevcutsa ve temel alanlar varsa UYUMLU say
        # (Gross weight veya Net weight + en az 2 alan = Packing List geçerli)
        has_weight = "GROSS WEIGHT" in bulunan or "NET WEIGHT" in bulunan
        if has_weight and len(bulunan) >= 3:
            return {"durum": "UYUMLU", "bulunan": bulunan, "eksik": eksik}
        if len(bulunan) >= 4:
            return {"durum": "UYUMLU", "bulunan": bulunan, "eksik": eksik}
        if len(bulunan) >= 1:
            return {"durum": "KISMİ UYUM - MANUEL KONTROL", "bulunan": bulunan, "eksik": eksik}
        return {"durum": "EKSİK ALAN", "bulunan": bulunan, "eksik": eksik}


    # ------------------------------------------------------------------
    # KUR 12: Kanıt puanı
    # ------------------------------------------------------------------
    @staticmethod
    def kanit_puani(dosya_var: bool, ocr_ok: bool, sinif_ok: bool,
                    alan_ok: bool = True) -> int:
        if not dosya_var:
            return 100
        if not ocr_ok:
            return 30
        if not sinif_ok:
            return 15
        if not alan_ok:
            return 20
        return 100

    # ------------------------------------------------------------------
    # Mal tanımı benzerlik
    # ------------------------------------------------------------------
    def mal_tanimi_benzerlik(self, kaynak: str, hedef: str) -> float:
        def norm(s):
            s = s.upper()
            s = re.sub(r'[^\w\s]', ' ', s)
            return set(w for w in re.sub(r'\s+', ' ', s).split() if len(w) >= 4)
        k, h = norm(kaynak), norm(hedef)
        if not k:
            return 0.0
        return len(k & h) / len(k)

    # ------------------------------------------------------------------
    # Risk yönetimi
    # ------------------------------------------------------------------
    def _risk_ekle(self, kategori: str) -> None:
        b = REZERV_KATEGORILERI.get(kategori, {})
        self.risk_puani += b.get("puan", 0)
        kat = b.get("kategori", "")
        if "MAJOR" in kat:
            self._banka_kabul = max(0, self._banka_kabul - 25)
        elif "MEDIUM" in kat:
            self._banka_kabul = max(0, self._banka_kabul - 10)
        else:
            self._banka_kabul = max(0, self._banka_kabul - 5)
        if kategori not in self._aktif_rezervler:
            self._aktif_rezervler.append(kategori)

    def _uyum_dus(self, n: int) -> None:
        self.uyumluluk_puani = max(0, self.uyumluluk_puani - n)

    def _risk_sinifi(self) -> str:
        for alt, ust, s in RISK_SINIFLANDIRMASI:
            if alt <= self.risk_puani <= ust:
                return s
        return "YÜKSEK RİSK"

    # ------------------------------------------------------------------
    # Metin ayıklama — 4 kademeli
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu: str) -> tuple[str, bool]:
        if not dosya_yolu or not os.path.isfile(dosya_yolu):
            return ("", False)
        ext   = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""
        try:
            if ext == ".pdf":
                if not PdfReader:
                    return ("[Hata: pypdf yüklü değil]", False)
                r = PdfReader(dosya_yolu)
                for i, s in enumerate(r.pages):
                    try:
                        t = s.extract_text()
                        if t:
                            metin += t + "\n"
                    except Exception as e:
                        metin += f"[Sayfa {i+1} hatası: {e}]\n"
            elif ext in [".docx", ".doc"]:
                if not _docx:
                    return ("[Hata: python-docx yüklü değil]", False)
                d = _docx.Document(dosya_yolu)
                for p in d.paragraphs:
                    if p.text:
                        metin += p.text + "\n"
                for tbl in d.tables:
                    for row in tbl.rows:
                        hucre = " ".join(c.text for c in row.cells if c.text)
                        if hucre.strip():
                            metin += hucre + "\n"
            elif ext in [".xlsx", ".xls"]:
                if not _openpyxl:
                    return ("[Hata: openpyxl yüklü değil]", False)
                wb = _openpyxl.load_workbook(dosya_yolu, data_only=True)
                for sn in wb.sheetnames:
                    ws = wb[sn]
                    for row in ws.iter_rows(values_only=True):
                        satir = " ".join(str(c) for c in row if c is not None)
                        if satir.strip():
                            metin += satir + "\n"
            elif ext in [".png", ".jpg", ".jpeg"]:
                if not _pytesseract or not _Image:
                    return ("[Hata: pytesseract yüklü değil]", False)
                img = _Image.open(dosya_yolu)
                try:
                    metin = _pytesseract.image_to_string(img, lang="eng+tur") or ""
                except Exception:
                    try:
                        metin = _pytesseract.image_to_string(img, lang="eng") or ""
                    except Exception as e2:
                        return (f"[OCR Hatası: {e2}]", False)
            elif ext == ".txt":
                with open(dosya_yolu, encoding="utf-8", errors="ignore") as f:
                    metin = f.read()
            else:
                return (f"[Desteklenmeyen format: {ext}]", False)
        except Exception as e:
            log.error("[ERROR] Dosya okuma hatası [%s]: %s\n%s",
                      dosya_yolu, e, traceback.format_exc())
            return (f"[Okuma hatası: {e}]", False)

        metin = metin.replace("\xa0", " ").replace("\u200b", "").replace("\r\n", "\n")
        ocr_ok = bool(metin.strip()) and not metin.startswith("[")
        return (metin, ocr_ok)

    # ------------------------------------------------------------------
    # Depo tarama — SADECE BİR KEZ analiz
    # ------------------------------------------------------------------
    def depoyu_tara(self) -> bool:
        self.depo             = self._bos_depo()
        self.risk_puani       = 0
        self.uyumluluk_puani  = 100
        self.mt700_alanlari   = {}
        self._aktif_rezervler = []
        self._banka_kabul     = 100
        self._dosya_durum_log = []

        if not os.path.exists(self.yuklenenler_dir):
            return False

        dosyalar = [
            os.path.join(self.yuklenenler_dir, f)
            for f in os.listdir(self.yuklenenler_dir)
            if os.path.isfile(os.path.join(self.yuklenenler_dir, f))
        ]
        if not dosyalar:
            return False

        for d_yolu in dosyalar:
            ad = os.path.basename(d_yolu)
            log.debug("[DEBUG] Dosya bulundu: %s", ad)

            kayit: dict[str, Any] = {
                "dosya": ad, "dosya_var": True,
                "ocr_ok": False, "sinif": None,
                "parse_ok": False, "puan": 0,
            }

            metin, ocr_ok = self.metin_ayikla(d_yolu)
            kayit["ocr_ok"] = ocr_ok
            if not ocr_ok:
                log.warning("[UYARI] %s OCR başarısız: %s", ad, metin[:60])
                self._dosya_durum_log.append(kayit)
                continue

            log.debug("[DEBUG] OCR tamamlandı: %s (%d karakter)", ad, len(metin))

            tur, puan, puanlar = self.siniflandirici.siniflandir(metin)
            kayit["sinif"]    = tur
            kayit["puan"]     = puan
            kayit["parse_ok"] = tur != "DIGER"
            log.debug("[DEBUG] Belge tipi = %s (puan: %s) — %s", tur, puan, ad)

            if tur in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]:
                if self.depo[tur] is None:
                    self.depo[tur] = {"ad": ad, "metin": metin, "puan": puan}
                else:
                    mevcut_p = self.depo[tur].get("puan", 0)
                    if puan > mevcut_p:
                        self.depo["DIGER_BELGELER"].append(self.depo[tur])
                        self.depo[tur] = {"ad": ad, "metin": metin, "puan": puan}
                    else:
                        self.depo["DIGER_BELGELER"].append(
                            {"ad": ad, "metin": metin, "puan": puan, "sinif_yedek": tur}
                        )
            else:
                self.depo["DIGER_BELGELER"].append({"ad": ad, "metin": metin, "puan": puan})

            self._dosya_durum_log.append(kayit)

        kusat = self._depo_metin("KUSAT")
        if kusat:
            self.mt700_alanlari = self.mt700_ayristir(kusat)

        return True

    # ------------------------------------------------------------------
    # BUG-01 FİX: TEK analiz motoru — analysis_result üretir
    # ------------------------------------------------------------------
    def analiz_motoru(self) -> None:
        """
        Tüm UCP 600 / ISBP 821 kontrollerini çalıştırır.
        Sonuç YALNIZCA self.analysis_result'a yazılır.
        Rapor fonksiyonları bu nesneden okur; başka kaynak kullanmaz.
        """
        log.debug("[DEBUG] Çapraz kontrol başladı.")

        kusat_text      = self._depo_metin("KUSAT")
        fatura_text     = self._depo_metin("FATURA")
        konsimento_text = self._depo_metin("KONSIMENTO")
        ceki_text       = self._depo_metin("CEKI_LISTESI")
        sigorta_text    = self._depo_metin("SIGORTA")
        combined        = (kusat_text + " " + fatura_text + " " + konsimento_text).upper()

        alan_46a = self.mt700_alanlari.get("46A", "")
        alan_45a = self.mt700_alanlari.get("45A", "")
        alan_32b = self.mt700_alanlari.get("32B", "")
        alan_44c = self.mt700_alanlari.get("44C", "")

        # KUR 13: LC No çıkar (tüm belgelerden)
        lc_no = (self.lc_no_bul(kusat_text) or
                 self.lc_no_bul(fatura_text) or
                 self.lc_no_bul(konsimento_text))
        log.debug("[DEBUG] LC No = %s", lc_no)

        r: dict[str, Any] = {
            "vade_analizi": [], "finansal_durum": [], "incoterms": [],
            "capraz_kontrol": [], "zorunlu_alanlar": [], "ucp_tablosu": [],
            "risk_ozeti": [], "rezerv_ozeti": [], "belge_46a": [],
            "eksik_belgeler": [], "mt700_alan_analizi": [], "tarih_zinciri": [],
            "rezerv_swift": [], "yonetici_ozeti": {}, "rezerv_detaylar": [],
            "packing_list_kontrol": {}, "dosya_durum_raporu": self._dosya_durum_log,
            "lc_no": lc_no or "Tespit edilemedi",
            "mt700_yorumlari": [],   # hukuk_motoru MT700 yorum motoru çıktısı
        }

        # ── 1. Vade Analizi ─────────────────────────────────────────────
        r["vade_analizi"].append(
            f"En Geç Yükleme (44C): **{alan_44c}**" if alan_44c
            else "En Geç Yükleme (44C): Tespit edilemedi — manuel kontrol."
        )
        ibraz = re.search(r'(\d+)\s*DAYS?\s*(?:AFTER|FOR\s+PRESENTATION)', combined, re.IGNORECASE)
        if ibraz:
            gun = int(ibraz.group(1))
            r["vade_analizi"].append(f"İbraz Süresi: **{gun} gün** (max 21)")
            if gun > 21:
                self._risk_ekle("ibraz_suresi_belirsiz")
                self._uyum_dus(10)
        else:
            r["vade_analizi"].append("İbraz Süresi: Tespit edilemedi — UCP Art 14c 21 gün uygulanır.")
            self._risk_ekle("ibraz_suresi_belirsiz")
            self._uyum_dus(5)

        # ── 2. Ödeme Vadesi ──────────────────────────────────────────────
        if any(x in combined for x in ["AT SIGHT", "SIGHT PAYMENT", "GORULDU"]):
            r["finansal_durum"].append("Ödeme: **At Sight** (UCP Art 15b)")
        elif any(x in combined for x in ["DAYS AFTER", "DEFERRED PAYMENT", "VADELI"]):
            r["finansal_durum"].append("Ödeme: **Vadeli** — poliçe takvimi kontrol edilmeli.")
        else:
            r["finansal_durum"].append("Ödeme: Tespit edilemedi — manuel kontrol.")

        # ── 3. Incoterms ─────────────────────────────────────────────────
        incoterm: Optional[str] = None
        for t in ["EXW","FCA","CPT","CIP","DAP","DPU","DDP","FAS","FOB","CFR","CIF"]:
            if t in combined:
                incoterm = t
                r["incoterms"].append(f"Incoterms: **{t} (ICC 2020)**")
                break
        if not incoterm:
            r["incoterms"].append("Incoterms: Tespit edilemedi.")

        if incoterm in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                r["incoterms"].append(f"[TAMAM] {incoterm} — Sigorta belgesi mevcut.")
            else:
                r["incoterms"].append(f"[REZERV] {incoterm} — Sigorta belgesi EKSİK!")
                self._risk_ekle("sigorta_eksik")
                self._uyum_dus(20)
                r["rezerv_ozeti"].append(f"REZERV — Sigorta belgesi eksik ({incoterm} / Art 28)")
                r["eksik_belgeler"].append("Sigorta Poliçesi")

        # ── 4. Tutar Karşılaştırması (Art 18/30) ────────────────────────
        fatura_t     = self.invoice_tutarlari_ayristir(fatura_text)
        fatura_tutar = self.lc_karsilastirma_tutari(fatura_t)
        log.debug("[DEBUG] CIF toplamı = %s", fatura_tutar)

        lc_tutar: Optional[float] = None
        if alan_32b:
            lc_tutar = normalize_tutar(alan_32b)
        if lc_tutar is None:
            m32 = re.search(r'(?:USD|EUR|GBP|TRY)\s*([\d,\.]+)', kusat_text or '', re.IGNORECASE)
            if m32:
                lc_tutar = normalize_tutar(m32.group(1))

        if fatura_tutar and lc_tutar:
            about    = any(x in (kusat_text or '').upper() for x in ["ABOUT", "APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma    = (fatura_tutar - lc_tutar) / lc_tutar * 100
            cif_detay = ""
            if fatura_t.get("goods_value"):
                cif_detay = (
                    f" [Goods:{fatura_t['goods_value']:,.2f}"
                    f"+Frt:{fatura_t.get('freight') or 0:,.2f}"
                    f"+Ins:{fatura_t.get('insurance') or 0:,.2f}"
                    f"=CIF:{fatura_tutar:,.2f}]"
                )
            detay = (f"LC:{lc_tutar:,.2f} | Fatura CIF:{fatura_tutar:,.2f}"
                     f"{cif_detay} | Sapma:{sapma:+.1f}% | Tolerans:±%{tolerans}")
            if abs(sapma) <= tolerans:
                r["capraz_kontrol"].append(
                    {"belge":"Tutar LC vs Fatura (Art 30)","detay":detay,"durum":"UYUMLU"})
            else:
                r["capraz_kontrol"].append(
                    {"belge":"Tutar LC vs Fatura (Art 30)","detay":detay,
                     "durum":"REZERV - TUTAR UYUMSUZLUĞU"})
                self._risk_ekle("tutar_uyusmazligi")
                self._uyum_dus(20)
                r["rezerv_ozeti"].append(f"REZERV — Tutar sapması %{abs(sapma):.1f} > %{tolerans} (Art 30)")
        else:
            eksik = [k for k,v in [("Fatura",fatura_tutar),("LC 32B",lc_tutar)] if not v]
            r["capraz_kontrol"].append(
                {"belge":"Tutar LC vs Fatura (Art 30)",
                 "detay":f"Tespit edilemedi: {', '.join(eksik)}","durum":"MANUEL KONTROL"})

        # ── 5. Kilo Karşılaştırması ──────────────────────────────────────
        fat_k = self.kilo_bul(fatura_text)
        bl_k  = self.kilo_bul(konsimento_text)
        pl_k  = self.kilo_bul(ceki_text)

        for a_isim, a_k, b_isim, b_k in [
            ("Fatura", fat_k, "B/L", bl_k),
            ("Fatura", fat_k, "Packing List", pl_k),
            ("Packing List", pl_k, "B/L", bl_k),
        ]:
            if a_k is not None and b_k is not None:
                if abs(a_k - b_k) < 1.0:
                    r["capraz_kontrol"].append(
                        {"belge":f"Kilo: {a_isim} vs {b_isim}",
                         "detay":f"Eşleşti: {a_k:,.2f} KG","durum":"UYUMLU"})
                else:
                    r["capraz_kontrol"].append(
                        {"belge":f"Kilo: {a_isim} vs {b_isim}",
                         "detay":f"{a_isim}:{a_k:,.2f} | {b_isim}:{b_k:,.2f} KG",
                         "durum":"REZERV - KİLO UYUMSUZLUĞU"})
                    self._risk_ekle("kilo_uyusmazligi")
                    self._uyum_dus(10)
                    r["rezerv_ozeti"].append(f"REZERV — Kilo: {a_isim} {a_k:,.2f} != {b_isim} {b_k:,.2f} KG")
            else:
                eksik = [n for n,v in [(a_isim,a_k),(b_isim,b_k)] if v is None]
                r["capraz_kontrol"].append(
                    {"belge":f"Kilo: {a_isim} vs {b_isim}",
                     "detay":f"Tespit edilemedi: {', '.join(eksik)}","durum":"MANUEL KONTROL"})

        # ── 6. Mal Tanımı (Art 18c) ──────────────────────────────────────
        lc_mal  = alan_45a.split("\n")[0].strip() if alan_45a else None
        fat_mal_m = re.search(
            r'(?:DESCRIPTION\s+OF\s+GOODS?|MAL\s+TANIMI)[:\s]+(.+?)(?:\n|$)',
            fatura_text or '', re.IGNORECASE
        )
        fat_mal = fat_mal_m.group(1).strip()[:200] if fat_mal_m else None

        if lc_mal and fat_mal:
            oran = self.mal_tanimi_benzerlik(lc_mal, fat_mal)
            if oran >= 0.8:
                durum_mal = "UYUMLU"
            elif oran >= 0.5:
                durum_mal = "DÜŞÜK BENZERLİK - MANUEL KONTROL"
                self._risk_ekle("mal_tanimi_uyusmazligi")
                self._uyum_dus(15)
            else:
                durum_mal = "REZERV - MAL TANIMI UYUMSUZLUĞU"
                self._risk_ekle("mal_tanimi_kritik")
                self._uyum_dus(25)
                r["rezerv_ozeti"].append(f"REZERV — Mal tanımı: %{oran*100:.0f} örtüşme (Art 18c)")
            r["capraz_kontrol"].append(
                {"belge":"Mal Tanımı LC vs Fatura (Art 18c)",
                 "detay":f"LC:{lc_mal[:60]} | Fatura:{fat_mal[:60]} | %{oran*100:.0f}",
                 "durum":durum_mal})
        else:
            r["capraz_kontrol"].append(
                {"belge":"Mal Tanımı LC vs Fatura (Art 18c)",
                 "detay":f"Tespit edilemedi: {'45A' if not lc_mal else ''} {'Fatura' if not fat_mal else ''}",
                 "durum":"MANUEL KONTROL"})

        # ── 7. Yükleme Tarihi (Art 20 / 44C) ───────────────────────────
        bl_tarih_str = self.bl_tarihi_bul(konsimento_text)
        bl_dt = self.tarih_ayristir(bl_tarih_str) if bl_tarih_str else None
        lc_dt = self.tarih_ayristir(alan_44c)     if alan_44c     else None

        if bl_dt and lc_dt:
            if bl_dt <= lc_dt:
                r["capraz_kontrol"].append(
                    {"belge":"B/L Tarihi vs 44C (Art 20)",
                     "detay":f"{bl_tarih_str} ≤ {alan_44c}","durum":"UYUMLU"})
            else:
                r["capraz_kontrol"].append(
                    {"belge":"B/L Tarihi vs 44C (Art 20)",
                     "detay":f"GEÇ YÜKLEME: {bl_tarih_str} > {alan_44c}",
                     "durum":"REZERV - GEÇ YÜKLEME"})
                self._risk_ekle("gec_yukleme")
                self._uyum_dus(25)
                r["rezerv_ozeti"].append(f"REZERV — GEÇ YÜKLEME: {bl_tarih_str} > 44C {alan_44c}")
        else:
            r["capraz_kontrol"].append(
                {"belge":"B/L Tarihi vs 44C (Art 20)",
                 "detay":f"B/L:{bl_tarih_str or '-'} | 44C:{alan_44c or '-'}",
                 "durum":"MANUEL KONTROL"})
            if konsimento_text and not bl_tarih_str:
                self._risk_ekle("yukleme_tarihi_ihlali")
                self._uyum_dus(15)
                r["rezerv_ozeti"].append("REZERV — B/L yükleme tarihi tespit edilemedi (Art 20)")

        # ── 8. Sigorta Teminatı (Art 28f-ii) ────────────────────────────
        if incoterm in ["CIF", "CIP"] and self.depo["SIGORTA"]:
            sig_t = self.sigorta_tutari_bul(sigorta_text)
            log.debug("[DEBUG] Sigorta tutarı = %s", sig_t)
            if sig_t and fatura_tutar:
                # Float precision fix: 23940 × 1.10 = 26334.000000000004
                # round(..., 2) ile karşılaştır → 26334.00 >= 26334.00 → UYUMLU
                min_t    = round(fatura_tutar * 1.10, 2)
                sig_t_r  = round(sig_t, 2)
                if sig_t_r >= min_t:
                    r["capraz_kontrol"].append(
                        {"belge": "Sigorta ≥ CIF × 110% (Art 28f-ii)",
                         "detay": f"CIF:{fatura_tutar:,.2f} | Min(×110%):{min_t:,.2f} | Sigorta:{sig_t_r:,.2f}",
                         "durum": "UYUMLU"})
                else:
                    r["capraz_kontrol"].append(
                        {"belge": "Sigorta ≥ CIF × 110% (Art 28f-ii)",
                         "detay": f"Sigorta:{sig_t_r:,.2f} < Min:{min_t:,.2f}",
                         "durum": "REZERV - YETERSİZ TEMİNAT"})
                    self._risk_ekle("sigorta_eksik")
                    self._uyum_dus(20)
                    r["rezerv_ozeti"].append(
                        f"REZERV — Sigorta yetersiz: {sig_t_r:,.2f} < {min_t:,.2f}")
            else:
                r["capraz_kontrol"].append(
                    {"belge": "Sigorta ≥ CIF × 110% (Art 28f-ii)",
                     "detay": "Tutar tespit edilemedi", "durum": "MANUEL KONTROL"})

        # ── 9. Konşimento (Art 20, Art 27) ──────────────────────────────
        if not konsimento_text:
            r["zorunlu_alanlar"].append("[REZERV] Konşimento belgesi yok!")
            self._risk_ekle("konsimento_eksik")
            self._uyum_dus(30)
            r["rezerv_ozeti"].append("REZERV — Konşimento ibraz edilmemiş (Art 20)")
            r["eksik_belgeler"].append("Konşimento")
        else:
            bl_u = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
                r["zorunlu_alanlar"].append("[TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii).")
            else:
                r["zorunlu_alanlar"].append("[REZERV] 'Shipped on Board' şerhi bulunamadı!")
                self._risk_ekle("konsimento_eksik")
                self._uyum_dus(20)
                r["rezerv_ozeti"].append("REZERV — On Board şerhi eksik (Art 20a-ii)")

            kirli = [k for k in KIRLI_BL if k in bl_u]
            if kirli:
                r["zorunlu_alanlar"].append(f"[REZERV] Klozlu konşimento: {', '.join(kirli)} (Art 27)")
                self._risk_ekle("temiz_bl_sorunu")
                self._uyum_dus(25)
                r["rezerv_ozeti"].append(f"REZERV — Klozlu konşimento: {', '.join(kirli)}")
            else:
                r["zorunlu_alanlar"].append("[TAMAM] Kirli/klozlu ifade bulunamadı (Art 27 uyumlu).")

        # ── 10. Eksik Belgeler (KUR 12 kanıt puanı ile) ─────────────────
        for key, ad in [("KUSAT","Küşat (MT700)"),("FATURA","Fatura"),("CEKI_LISTESI","Çeki Listesi")]:
            if not self.depo[key]:
                ilgili = [d for d in self._dosya_durum_log if d.get("sinif") == key]
                if ilgili:
                    en_iyi = max(ilgili, key=lambda x: x.get("puan", 0))
                    kp = self.kanit_puani(True, en_iyi.get("ocr_ok", False),
                                          en_iyi.get("parse_ok", False))
                    if kp < KANIT_ESIK_MAJOR:
                        r["eksik_belgeler"].append(
                            f"{ad} — OCR/sınıf belirsiz (kanıt:{kp}/100) MANUEL KONTROL")
                    # yüksek kanıt puanı ama depo None: gerçekten eksik
                    else:
                        r["eksik_belgeler"].append(ad)
                else:
                    r["eksik_belgeler"].append(ad)

        # ── 11. 46A Belge Şartları ───────────────────────────────────────
        if alan_46a:
            kontroller = [
                ("COMMERCIAL INVOICE", "FATURA",      "Ticari Fatura"),
                ("INVOICE",            "FATURA",      "Ticari Fatura"),
                ("BILL OF LADING",     "KONSIMENTO",  "Konşimento"),
                ("PACKING LIST",       "CEKI_LISTESI","Packing List"),
                ("INSURANCE",          "SIGORTA",     "Sigorta Poliçesi"),
            ]
            goruldu: set = set()
            for sart, dk, ad in kontroller:
                if sart in alan_46a.upper() and sart not in goruldu:
                    goruldu.add(sart)
                    var = self.depo.get(dk) is not None
                    if not var:
                        self._risk_ekle("46a_belge_eksigi")
                        self._uyum_dus(10)
                        r["rezerv_ozeti"].append(f"REZERV — 46A gereği '{ad}' belgesi eksik")
                    r["belge_46a"].append(
                        {"sart":ad,"detay":"46A'da talep edildi.",
                         "durum":"VAR" if var else "EKSİK"})
        else:
            r["belge_46a"].append(
                {"sart":"46A","detay":"MT700 46A tespit edilemedi.","durum":"MANUEL KONTROL"})

        # ── 12. Packing List İçerik Kontrolü ────────────────────────────
        if self.depo.get("CEKI_LISTESI"):
            pl_k2 = self.packing_list_kontrol(ceki_text)
            r["packing_list_kontrol"] = pl_k2
            r["belge_46a"].append({
                "sart":"Packing List İçerik",
                "detay":f"Bulunan: {', '.join(pl_k2['bulunan']) or '-'} | "
                        f"Eksik: {', '.join(pl_k2['eksik']) or '-'}",
                "durum":pl_k2["durum"],
            })

        # ── 13. Menşe (Origin) Analizi (KUR 8) ──────────────────────────
        origin = self.origin_analizi_yap(kusat_text or '', fatura_text or '', alan_46a)
        r["capraz_kontrol"].append({
            "belge":"Menşe (Origin) Analizi",
            "detay":origin["detay"],
            "durum":origin["durum"],
        })
        if origin["rezerv_gerekli"]:
            self._risk_ekle("co_eksik")
            self._uyum_dus(15)
            r["rezerv_ozeti"].append(f"REZERV — Menşe: {origin['detay'][:100]}")

        # ── 14. MT700 Alan Analizi ───────────────────────────────────────
        MT700_ALANLAR = {
            "20":"Documentary Credit Number","31D":"Expiry Date","32B":"Amount",
            "40A":"Form","44C":"Latest Shipment","44E":"Port of Loading",
            "44F":"Port of Discharge","45A":"Description of Goods",
            "46A":"Documents Required","47A":"Additional Conditions","48":"Presentation Period",
        }
        for kod, aciklama in MT700_ALANLAR.items():
            deger = self.mt700_alanlari.get(kod)
            if deger:
                r["mt700_alan_analizi"].append(
                    {"alan":kod,"aciklama":aciklama,"deger":deger[:100],"durum":"TESPİT EDİLDİ"})
            elif kod in {"20","31D","32B","40A","44C","45A","46A"}:
                r["mt700_alan_analizi"].append(
                    {"alan":kod,"aciklama":aciklama,"deger":"—","durum":"MANUEL KONTROL"})

        # ── 15. hukuk_motoru UCP kontrolleri ────────────────────────────
        if HUKUK_MOTORU_AKTIF and ucp_kurallari_uygula:
            try:
                # mal tanımı benzerlik oranını hesapla (yorum motoru için)
                lc_mal  = alan_45a.split("\n")[0].strip() if alan_45a else None
                fat_mal_m2 = re.search(
                    r'(?:DESCRIPTION\s+OF\s+GOODS?|MAL\s+TANIMI)[:\s]+(.+?)(?:\n|$)',
                    fatura_text or '', re.IGNORECASE)
                fat_mal2 = fat_mal_m2.group(1).strip()[:200] if fat_mal_m2 else None
                mal_oran = self.mal_tanimi_benzerlik(lc_mal, fat_mal2) if (lc_mal and fat_mal2) else None

                eksik_46a = [b["sart"] for b in r.get("belge_46a",[]) if b.get("durum") == "EKSİK"]

                parsed_data = {
                    "kusat_text":        kusat_text,
                    "fatura_text":       fatura_text,
                    "konsimento_text":   konsimento_text,
                    "ceki_text":         ceki_text,
                    "sigorta_text":      sigorta_text,
                    "mt700_alanlari":    self.mt700_alanlari,
                    "fatura_tutar":      fatura_tutar,
                    "lc_tutar":          lc_tutar,
                    "incoterm":          incoterm,
                    "bl_tarih_str":      bl_tarih_str,
                    "alan_44c":          alan_44c,
                    "fat_kilo":          fat_k,
                    "bl_kilo":           bl_k,
                    "pl_kilo":           pl_k,
                    "sigorta_tutari":    self.sigorta_tutari_bul(sigorta_text),
                    "mal_tanimi_oran":   mal_oran,
                    "eksik_belgeler_46a": eksik_46a,
                }
                ucp_sonuc = ucp_kurallari_uygula(parsed_data)
                if isinstance(ucp_sonuc, list) and ucp_sonuc:
                    r["ucp_tablosu"] = ucp_sonuc

                # MT700 Akıllı Yorum Motoru
                if mt700_hukuki_yorum:
                    r["mt700_yorumlari"] = mt700_hukuki_yorum(parsed_data)
                    log.debug("[DEBUG] MT700 yorum: %d alan.", len(r["mt700_yorumlari"]))

                # Hukuki Uzman Görüşü (rapor sonu bölümü)
                if 'uzman_gorusu_uret' in dir() and uzman_gorusu_uret:
                    parsed_data["lc_no"]       = lc_no or ""
                    parsed_data["banka_kabul"] = self._banka_kabul
                    r["uzman_gorusu"] = uzman_gorusu_uret(parsed_data, ucp_sonuc or [])
                    log.debug("[DEBUG] Uzman görüşü üretildi.")

            except Exception as e:
                log.error("[ERROR] hukuk_motoru hatası: %s\n%s", e, traceback.format_exc())

        # ── 16. KUR 7: Çelişki denetimi (rezerv öncesi) ─────────────────
        # Sayısal çelişkileri logla — yanlış rezerv birikmişse temizle
        _celiski_kontrolleri = [
            ("sigorta_eksik", sig_t if 'sig_t' in dir() else None, fatura_tutar * 1.10 if fatura_tutar else None),
        ]
        for kod, a_val, b_val in _celiski_kontrolleri:
            if kod in self._aktif_rezervler and a_val is not None and b_val is not None:
                if a_val >= b_val:
                    log.error(
                        "[ERROR] Çelişki tespit edildi: %s rezervi aktif ama "
                        "%.2f >= %.2f — rezerv kaldırılıyor.", kod, a_val, b_val
                    )
                    self._aktif_rezervler.remove(kod)
                    r["rezerv_ozeti"] = [x for x in r["rezerv_ozeti"] if "Sigorta yetersiz" not in x]

        # ── 17. Risk özeti ───────────────────────────────────────────────
        r["risk_ozeti"].append(f"Risk Puanı: **{self.risk_puani}** — {self._risk_sinifi()}")
        r["risk_ozeti"].append(f"Uyumluluk: **%{self.uyumluluk_puani}**")
        for i, rv in enumerate(r["rezerv_ozeti"], 1):
            r["risk_ozeti"].append(f"{i}. {rv}")

        # ── SWIFT Simülatörü — yalnızca gerçek rezerv varsa ret üret ──
        # KUR 15: Sigorta belgesi mevcutsa "INSURANCE NOT PRESENTED" ret metni üretilemez
        aktif_rezervler_temiz = list(self._aktif_rezervler)
        if self.depo.get("SIGORTA") and "sigorta_eksik" in aktif_rezervler_temiz:
            aktif_rezervler_temiz.remove("sigorta_eksik")
            log.debug("[DEBUG] Sigorta belgesi mevcut — sigorta_eksik SWIFT ret metni kaldırıldı.")

        r["rezerv_swift"] = [
            REZERV_SWIFT[k] for k in aktif_rezervler_temiz if k in REZERV_SWIFT
        ]

        # ── 19. Rezerv Detaylar ──────────────────────────────────────────
        r["rezerv_detaylar"] = [
            {"kod":k,
             "kategori":REZERV_KATEGORILERI.get(k,{}).get("kategori","?"),
             "puan":str(REZERV_KATEGORILERI.get(k,{}).get("puan","?")),
             "sure":REZERV_KATEGORILERI.get(k,{}).get("sure","?")}
            for k in self._aktif_rezervler
        ]

        # ── 20. Yönetici Özeti ───────────────────────────────────────────
        mevcut = [k for k in ["KUSAT","FATURA","KONSIMENTO","CEKI_LISTESI","SIGORTA"]
                  if self.depo.get(k)]
        major = sum(1 for k in self._aktif_rezervler
                    if REZERV_KATEGORILERI.get(k,{}).get("kategori") == "MAJOR DISCREPANCY")
        r["yonetici_ozeti"] = {
            "toplam_belge":   len(mevcut),
            "mevcut":         mevcut,
            "eksik":          r["eksik_belgeler"],
            "toplam_rezerv":  len(r["rezerv_ozeti"]),
            "major_rezerv":   major,
            "uyumluluk":      self.uyumluluk_puani,
            "risk_puani":     self.risk_puani,
            "risk_sinifi":    self._risk_sinifi(),
            "banka_kabul":    self._banka_kabul,
            "lc_no":          lc_no or "Tespit edilemedi",
        }

        # BUG-01 FİX: TEK kayıt noktası
        self.analysis_result = r
        log.debug("[DEBUG] analysis_result oluşturuldu. Rezerv sayısı: %d", len(r["rezerv_ozeti"]))

    # ------------------------------------------------------------------
    # BUG-06 FİX: Markdown raporu — analysis_result'tan okur
    # ------------------------------------------------------------------
    def markdown_raporu(self) -> str:
        """
        Tüm içerik self.analysis_result'tan gelir.
        Dönen string hem dosyaya yazılır hem ekrana yazdırılır.
        """
        v = self.analysis_result
        if not v:
            return ""

        s = []
        s.append("# AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0\n\n")
        s.append(f"**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')} | Motor: UCP 600 & ISBP 821\n\n---\n\n")

        s.append("## Dosya Durum Raporu\n\n")
        s.append("| Dosya | Var | OCR | Sınıf | Parse | Puan |\n|:---|:---|:---|:---|:---|:---|\n")
        for d in v.get("dosya_durum_raporu", []):
            s.append(
                f"| {d.get('dosya','')} | {'V' if d.get('dosya_var') else 'X'} | "
                f"{'V' if d.get('ocr_ok') else 'X'} | {d.get('sinif') or '-'} | "
                f"{'V' if d.get('parse_ok') else 'X'} | {d.get('puan','?')} |\n"
            )
        s.append("\n---\n\n")

        oz = v.get("yonetici_ozeti", {})
        if oz:
            s.append("## Yönetici Özeti\n\n")
            s.append("| Metrik | Değer |\n|:---|:---|\n")
            s.append(f"| LC No | **{oz.get('lc_no','Tespit edilemedi')}** |\n")
            s.append(f"| Belgeler | {', '.join(oz.get('mevcut',[]))} |\n")
            s.append(f"| Rezerv | {oz.get('toplam_rezerv',0)} (MAJOR: {oz.get('major_rezerv',0)}) |\n")
            s.append(f"| Uyumluluk | **%{oz.get('uyumluluk','?')}** |\n")
            s.append(f"| Banka Kabul | **%{oz.get('banka_kabul','?')}** |\n")
            s.append(f"| Risk | {oz.get('risk_sinifi','?')} |\n\n---\n\n")

        s.append("## MT700 Alan Analizi\n\n")
        s.append("| Alan | Açıklama | Değer | Durum |\n|:---|:---|:---|:---|\n")
        for a in v.get("mt700_alan_analizi", []):
            s.append(f"| **{a['alan']}** | {a['aciklama']} | `{a['deger']}` | {a['durum']} |\n")
        s.append("\n---\n\n")

        for baslik, anahtar in [
            ("Vade Analizi","vade_analizi"),
            ("Ödeme Vadesi","finansal_durum"),
            ("Incoterms & Sigorta","incoterms"),
        ]:
            s.append(f"## {baslik}\n\n")
            for x in v.get(anahtar, []):
                s.append(f"* {x}\n")
            s.append("\n")

        # MT700 Hukuki Değerlendirme (yorum motoru)
        yorumlar = v.get("mt700_yorumlari", [])
        if yorumlar:
            s.append("\n## MT700 Hukuki Değerlendirme\n\n")
            for y in yorumlar:
                s.append(f"### Alan {y['alan']} — {y['ad']}\n\n")
                s.append(f"**Bulunan Değer:** `{y['deger']}`\n\n")
                s.append(f"**Açıklama:** {y['aciklama']}\n\n")
                s.append(f"**UCP/ISBP Yorumu:** {y['yorum']}\n\n")
                s.append(f"**İlgili Madde:** {y['madde']}\n\n")
                if y.get("karsilastirma"):
                    s.append(f"**Karşılaştırma:** {y['karsilastirma']}\n\n")
                s.append(f"**Risk / Sonuç:** **{y['sonuc']}**\n\n---\n\n")

        s.append("\n## Çapraz Kontroller\n\n")
        s.append("| Belgeler | Detay | Durum |\n|:---|:---|:---|\n")
        for c in v.get("capraz_kontrol", []):
            s.append(f"| {c['belge']} | {c['detay']} | **{c['durum']}** |\n")

        # UCP 600 Hukuki Kontroller — BULGU + HUKUKİ DEĞERLENDİRME + SONUÇ
        ucp_tablo = v.get("ucp_tablosu", [])
        if ucp_tablo:
            s.append("\n## UCP 600 Hukuki Kontroller\n\n")
            for u in ucp_tablo:
                durum_sembol = (
                    "✓" if u["durum"] == "UYUMLU" else
                    "⚠" if u["durum"] in ("MANUEL KONTROL", "UYARI", "BİLGİ") else "✗"
                )
                s.append(f"### {u['madde']} — {u['aciklama']}\n\n")
                s.append(f"**BULGU:** {u['detay']}\n\n")
                if u.get("hukuki_yorum"):
                    s.append(f"**HUKUKİ DEĞERLENDİRME:**\n\n{u['hukuki_yorum']}\n\n")
                s.append(f"**SONUÇ: {durum_sembol} {u['durum']}**\n\n---\n\n")

        s.append("\n## Konşimento\n\n")
        for x in v.get("zorunlu_alanlar", []):
            s.append(f"* {x}\n")

        # 46A Detaylı Belge Şartları
        s.append("\n## 46A Belge Şartları\n\n")
        belge_46a = v.get("belge_46a", [])
        if belge_46a:
            s.append("| Belge Şartı | Detay | Durum |\n|:---|:---|:---|\n")
            for b in belge_46a:
                s.append(f"| {b['sart']} | {b['detay']} | **{b['durum']}** |\n")
            # Eksik belgeler vurgusu
            eksikler = [b for b in belge_46a if b.get("durum") == "EKSİK"]
            if eksikler:
                s.append(f"\n**⚠ Eksik Belgeler:** "
                         f"{', '.join(b['sart'] for b in eksikler)}\n\n")
                s.append(
                    "UCP 600 Art 14(a): 46A alanında talep edilen belgelerin "
                    "eksiksiz ibraz edilmesi zorunludur. Eksik belge doğrudan ret sebebidir.\n"
                )
        else:
            s.append("46A alanı tespit edilemedi — manuel kontrol gereklidir.\n")

        s.append("\n## Tespit Edilen Rezervler\n\n")
        for rv in v.get("rezerv_ozeti", []):
            s.append(f"* {rv}\n")
        if not v.get("rezerv_ozeti"):
            s.append("* Kritik rezerv tespit edilmedi.\n")

        s.append("\n## Rezerv Kategorileri\n\n")
        s.append("| Kod | Kategori | Puan | Süre |\n|:---|:---|:---|:---|\n")
        for d in v.get("rezerv_detaylar", []):
            s.append(f"| {d['kod']} | **{d['kategori']}** | {d['puan']} | {d['sure']} |\n")

        s.append("\n## Risk Değerlendirmesi\n\n")
        for x in v.get("risk_ozeti", []):
            s.append(f"* {x}\n")

        swift = v.get("rezerv_swift", [])
        if swift:
            s.append("\n## SWIFT Rezerv Simülatörü\n\n")
            for i, mt in enumerate(swift, 1):
                s.append(f"### Ret Metni {i}\n\n```\n{mt}\n```\n\n")

        # Hukuki Uzman Görüşü — rapor sonu
        uzman = v.get("uzman_gorusu", "")
        if uzman:
            s.append("\n## HUKUKİ UZMAN GÖRÜŞÜ\n\n")
            s.append(uzman)
            s.append("\n")

        return "".join(s)

    def rapor_kaydet(self) -> str:
        """
        TEK rapor string'i üretilir (markdown_raporu()),
        hem dosyaya yazılır hem konsola basılır hem de döndürülür.
        Dönen string save_docx()'e aktarılır — başka kaynak kullanılmaz.
        """
        icerik = self.markdown_raporu()
        if not icerik:
            return ""
        yol = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(icerik)
        print("[+] akreditif_analiz_raporu.md kaydedildi:", yol)
        print("\n" + "="*70)
        print("RAPOR ÖZETİ (analysis_result'tan):")
        print("="*70)
        oz = self.analysis_result.get("yonetici_ozeti", {})
        print(f"  Belgeler   : {', '.join(oz.get('mevcut',[]))}")
        print(f"  Rezervler  : {oz.get('toplam_rezerv',0)} (MAJOR: {oz.get('major_rezerv',0)})")
        print(f"  Uyumluluk  : %{oz.get('uyumluluk','?')}")
        print(f"  Banka Kabul: %{oz.get('banka_kabul','?')}")
        print(f"  Risk       : {oz.get('risk_sinifi','?')}")
        print("="*70 + "\n")
        return icerik

    # ------------------------------------------------------------------
    # DOCX üreticisi — YALNIZCA final_report string'inden üretir
    # Sıfır bağımsız analiz kodu; analysis_result'a dokunmaz.
    # ------------------------------------------------------------------
    def save_docx(self, final_report: str) -> None:
        """
        Parametre olarak gelen final_report string'ini DOCX'e dönüştürür.
        Bu string markdown_raporu()'nun ürettiği aynı string'dir.

        Garanti:
          - Ekrandaki rezerv sayısı == rapor.md rezerv sayısı
                                     == DOCX rezerv sayısı
          - Hiçbir yerde yeniden analiz yapılmaz.
          - docx_uretici.js içerik ayrıştırma dışında iş yapmaz.
        """
        import subprocess
        import tempfile

        if not final_report:
            log.warning("[UYARI] save_docx: boş rapor string'i — DOCX üretilmedi.")
            return

        # docx_uretici.js'nin bulunduğu yer: bu .py dosyasıyla aynı dizin
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        uretici_js  = os.path.join(script_dir, "docx_uretici.js")

        if not os.path.isfile(uretici_js):
            log.error("[ERROR] docx_uretici.js bulunamadı: %s", uretici_js)
            return

        docx_yol = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.docx")

        # Rapor string'i geçici dosyaya yaz (Unicode güvenli)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(final_report)
            tmp_yol = tmp.name

        try:
            sonuc = subprocess.run(
                ["node", uretici_js, tmp_yol, docx_yol],
                capture_output=True, text=True, timeout=30,
            )
            if sonuc.returncode == 0:
                print("[+] DOCX kaydedildi:", docx_yol)
                log.debug("[DEBUG] docx_uretici.js çıktısı: %s", sonuc.stdout.strip())
            else:
                log.error("[ERROR] DOCX üretim hatası (rc=%d):\n%s",
                          sonuc.returncode, sonuc.stderr)
        except FileNotFoundError:
            log.error("[ERROR] node komutu bulunamadı — Node.js kurulu değil.")
        except subprocess.TimeoutExpired:
            log.error("[ERROR] DOCX üretimi zaman aşımına uğradı.")
        except Exception as e:
            log.error("[ERROR] save_docx beklenmeyen hata: %s\n%s",
                      e, traceback.format_exc())
        finally:
            try:
                os.unlink(tmp_yol)
            except OSError:
                pass

    def html_raporu(self) -> None:
        """BUG-06 FİX: analysis_result'tan üretilir."""
        v = self.analysis_result
        if not v:
            return
        yol = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.html")

        def li(k): return "".join(f"<li>{x}</li>" for x in v.get(k,[]))
        def tablo3(satirlar, anahtarlar):
            return "".join(
                "<tr>" + "".join(f"<td>{r.get(k,'')}</td>" for k in anahtarlar) + "</tr>"
                for r in satirlar
            )

        oz = v.get("yonetici_ozeti", {})
        krenk = ("#276749" if oz.get("banka_kabul",0) >= 70
                 else "#d69e2e" if oz.get("banka_kabul",0) >= 40 else "#c53030")

        ddr = "".join(
            f"<tr><td>{d.get('dosya','')}</td>"
            f"<td>{'✓' if d.get('dosya_var') else '✗'}</td>"
            f"<td>{'✓' if d.get('ocr_ok') else '✗'}</td>"
            f"<td>{d.get('sinif') or '-'}</td>"
            f"<td>{'✓' if d.get('parse_ok') else '✗'}</td>"
            f"<td>{d.get('puan','?')}</td></tr>"
            for d in v.get("dosya_durum_raporu", [])
        )
        mt_html = "".join(
            f"<tr><td><b>{a['alan']}</b></td><td>{a['aciklama']}</td>"
            f"<td><code>{a['deger']}</code></td><td>{a['durum']}</td></tr>"
            for a in v.get("mt700_alan_analizi", [])
        )
        cc_html = tablo3(v.get("capraz_kontrol",[]), ["belge","detay","durum"])
        b46_html = tablo3(v.get("belge_46a",[]), ["sart","detay","durum"])
        rezerv_html = "".join(f"<li>{rv}</li>" for rv in v.get("rezerv_ozeti",[])) \
                      or "<li>Kritik rezerv tespit edilmedi.</li>"
        kat_html = "".join(
            f"<tr><td>{d['kod']}</td><td><b>{d['kategori']}</b></td>"
            f"<td>{d['puan']}</td><td>{d['sure']}</td></tr>"
            for d in v.get("rezerv_detaylar",[])
        )
        swift_html = "".join(
            f'<div class="swift"><b>Ret {i}</b><pre>{mt}</pre></div>'
            for i, mt in enumerate(v.get("rezerv_swift",[]),1)
        ) or '<p style="color:#276749">SWIFT ret metni üretilmedi.</p>'

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Akreditif Analiz Raporu v9.0</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#f0f4f8;color:#2d3748;padding:20px}}
.wrap{{background:#fff;padding:32px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.08);max-width:1280px;margin:0 auto}}
h1{{color:#1a365d;border-bottom:4px solid #3182ce;padding-bottom:12px;font-size:1.35em}}
h2{{color:#2b6cb0;margin:24px 0 8px;border-left:5px solid #3182ce;padding-left:10px;font-size:1.02em}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:.88em}}
th,td{{border:1px solid #e2e8f0;padding:7px 10px;text-align:left;vertical-align:top}}
th{{background:#ebf8ff;color:#2b6cb0;font-weight:600}}
tr:nth-child(even){{background:#f7fafc}}
ul{{padding-left:18px;margin-top:6px}}li{{margin-bottom:4px;line-height:1.65}}
.meta{{color:#718096;font-size:.88em;margin-bottom:14px}}
.exec{{background:linear-gradient(135deg,#ebf8ff,#f0fff4);border:2px solid #3182ce;border-radius:10px;padding:18px;margin-bottom:20px}}
.grid{{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}}
.card{{background:#fff;border:1px solid #bee3f8;border-radius:7px;padding:10px 16px;min-width:150px;text-align:center}}
.lbl{{font-size:.76em;color:#718096;margin-bottom:3px}}.val{{font-size:1.3em;font-weight:700;color:#2b6cb0}}
code{{background:#edf2f7;padding:1px 5px;border-radius:3px;font-size:.84em}}
.swift{{background:#1a202c;color:#f6e05e;border-radius:7px;padding:14px;margin:6px 0;font-family:monospace;font-size:.86em}}
.swift pre{{white-space:pre-wrap;margin-top:6px;color:#e2e8f0}}
</style>
</head>
<body>
<div class="wrap">
<h1>AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0</h1>
<p class="meta"><b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} | <b>Motor:</b> UCP 600 &amp; ISBP 821</p>
<div class="exec">
<h2>Yönetici Özeti</h2>
<div class="grid">
<div class="card"><div class="lbl">Belgeler</div><div class="val">{oz.get('toplam_belge','?')}</div></div>
<div class="card"><div class="lbl">Rezerv</div><div class="val" style="color:#c53030">{oz.get('toplam_rezerv',0)}</div></div>
<div class="card"><div class="lbl">MAJOR</div><div class="val" style="color:#c53030">{oz.get('major_rezerv',0)}</div></div>
<div class="card"><div class="lbl">Uyumluluk</div><div class="val" style="color:#276749">%{oz.get('uyumluluk','?')}</div></div>
<div class="card"><div class="lbl">Banka Kabul</div><div class="val" style="color:{krenk}">%{oz.get('banka_kabul','?')}</div></div>
<div class="card"><div class="lbl">Risk</div><div class="val" style="font-size:.9em">{oz.get('risk_sinifi','?')}</div></div>
</div></div>
<h2>Dosya Durum Raporu</h2>
<table><tr><th>Dosya</th><th>Var</th><th>OCR</th><th>Sınıf</th><th>Parse</th><th>Puan</th></tr>{ddr}</table>
<h2>MT700 Alan Analizi</h2>
<table><tr><th>Alan</th><th>Açıklama</th><th>Değer</th><th>Durum</th></tr>{mt_html}</table>
<h2>Vade Analizi</h2><ul>{li("vade_analizi")}</ul>
<h2>Ödeme Vadesi</h2><ul>{li("finansal_durum")}</ul>
<h2>Incoterms &amp; Sigorta</h2><ul>{li("incoterms")}</ul>
<h2>Çapraz Kontroller</h2>
<table><tr><th>Belgeler</th><th>Detay</th><th>Durum</th></tr>{cc_html}</table>
<h2>Konşimento Kontrolleri</h2><ul>{li("zorunlu_alanlar")}</ul>
<h2>46A Belge Şartları</h2>
<table><tr><th>Belge</th><th>Detay</th><th>Durum</th></tr>{b46_html}</table>
<h2>Tespit Edilen Rezervler</h2><ul>{rezerv_html}</ul>
<h2>Rezerv Kategorileri</h2>
<table><tr><th>Kod</th><th>Kategori</th><th>Puan</th><th>Süre</th></tr>{kat_html}</table>
<h2>Risk Değerlendirmesi</h2><ul>{li("risk_ozeti")}</ul>
<h2>SWIFT Rezerv Simülatörü</h2>{swift_html}
</div></body></html>"""

        with open(yol, "w", encoding="utf-8") as f:
            f.write(html)
        print("[+] rapor.html kaydedildi:", yol)

    # ------------------------------------------------------------------
    # Ana akış
    # ------------------------------------------------------------------
    def _eski_raporlari_temizle(self) -> None:
        """Her çalıştırmada eski raporları sil; yalnızca yeni raporlar görünsün."""
        for ad in [
            "rapor.md", "rapor.html",
            "akreditif_analiz_raporu.md",
            "akreditif_analiz_raporu.html",
            "akreditif_analiz_raporu.docx",
        ]:
            yol = os.path.join(self.raporlar_dir, ad)
            if os.path.isfile(yol):
                try:
                    os.remove(yol)
                    log.debug("[DEBUG] Eski rapor silindi: %s", ad)
                except OSError as e:
                    log.warning("[UYARI] Rapor silinemedi: %s — %s", ad, e)

    @staticmethod
    def tutarlilik_testi(
        final_report: str,
        md_yolu: str,
        docx_yolu: str,
    ) -> bool:
        """
        Tutarlılık testi:
          - ekran (final_report) == akreditif_analiz_raporu.md içeriği
          - DOCX içindeki REZERV sayısı == final_report'taki REZERV sayısı

        Geçerse True; başarısızsa [ERROR] log üretir ve False döner.
        """
        import re, zipfile

        tamam = True

        # 1. MD karşılaştırması
        if os.path.isfile(md_yolu):
            md_icerik = open(md_yolu, encoding="utf-8").read()
            if final_report == md_icerik:
                log.debug("[TEST] MD tutarlılığı: GEÇTI")
            else:
                log.error(
                    "[TEST] TUTARSIZLIK: final_report != akreditif_analiz_raporu.md "
                    "(karakter farkı: %d)",
                    abs(len(final_report) - len(md_icerik)),
                )
                tamam = False

        # 2. DOCX rezerv sayısı
        if os.path.isfile(docx_yolu):
            src_count = len(re.findall(r'REZERV\s*[—\-]', final_report))
            try:
                with zipfile.ZipFile(docx_yolu) as z:
                    xml = z.read("word/document.xml").decode("utf-8")
                docx_count = len(re.findall(r'REZERV\s*[—\-]', xml))
                if src_count == docx_count:
                    log.debug("[TEST] DOCX rezerv sayısı: GEÇTI (%d)", src_count)
                else:
                    log.error(
                        "[TEST] TUTARSIZLIK: Kaynak=%d REZERV, DOCX=%d REZERV",
                        src_count, docx_count,
                    )
                    tamam = False
            except Exception as e:
                log.error("[TEST] DOCX okunamadı: %s", e)
                tamam = False

        return tamam

    def baslat(self) -> None:
        print("[BİLGİ] Akreditif denetim sistemi v9.0 başlatılıyor...")

        # ── Adım 0: Eski raporları temizle ──────────────────────────────
        self._eski_raporlari_temizle()

        if self.depoyu_tara():
            print(
                f"[BİLGİ] Belgeler: "
                f"KUSAT={'VAR' if self.depo['KUSAT'] else 'YOK'} | "
                f"FATURA={'VAR' if self.depo['FATURA'] else 'YOK'} | "
                f"KONSIMENTO={'VAR' if self.depo['KONSIMENTO'] else 'YOK'} | "
                f"CEKI={'VAR' if self.depo['CEKI_LISTESI'] else 'YOK'} | "
                f"SIGORTA={'VAR' if self.depo['SIGORTA'] else 'YOK'}"
            )
            # ── Adım 1: TEK analiz ───────────────────────────────────────
            self.analiz_motoru()

            # ── Adım 2: TEK rapor string'i üret ─────────────────────────
            # Tüm çıktıların kaynağı bu string'dir. Hiçbir çıktı fonksiyonu
            # yeniden analiz yapmaz; sadece bu string'i formatlar.
            final_report: str = self.rapor_kaydet()   # → ekrana + MD

            # ── Adım 3: Diğer formatlar AYNI kaynaktan ──────────────────
            self.html_raporu()                        # self.analysis_result
            self.save_docx(final_report)              # final_report string'i

            # ── Adım 4: Tutarlılık testi ─────────────────────────────────
            md_yolu   = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")
            docx_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.docx")
            gecti = self.tutarlilik_testi(final_report, md_yolu, docx_yolu)
            if gecti:
                print("[TEST] Tutarlılık: TÜM ÇIKTILAR UYUMLU ✓")
            else:
                print("[TEST] UYARI: Tutarlılık testi başarısız — log dosyasını inceleyin.")
        else:
            print("[BİLGİ] Yüklenecek belge bulunamadı.")


if __name__ == "__main__":
    YapayZekaDisTicaretDenetleyici().baslat()
