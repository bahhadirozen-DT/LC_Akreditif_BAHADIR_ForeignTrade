"""
app.py - Akreditif Denetleme Sistemi v8.0
UCP 600 / ISBP 821 Uyumlu | Uretim Ortami

Duzeltilen hatalar (v7 -> v8):
  - HATA-01: Kusat CEKI_LISTESI olarak siniflaniyordu -> 2 assamali siniflandirma
  - HATA-02: MT700 parser calismiyor -> sifirdan yazildi
  - HATA-03: Sigorta tutari yanlis okunuyordu -> SUM INSURED parser
  - HATA-04: Sayi normallesme hatalari -> gelismis normalize_tutar
  - HATA-05: CO kontrolu calismiyor -> 46A parser duzeltildi
  - HATA-06: Packing List icerik kontrolu -> genisletildi
  - HATA-07: Weight parser -> alan bazli
  - HATA-08: B/L tarih parser -> 6 format
  - HATA-09: Yanlis rezerv -> kanit puani filtresi
  - HATA-10: Dosya durum raporu -> 4 kademeli
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
# Opsiyonel kutuphane yuklemeleri
# ---------------------------------------------------------------------------
try:
    from pypdf import PdfReader
    log.debug("pypdf yuklendi.")
except ImportError:
    PdfReader = None

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt
    log.debug("python-docx yuklendi.")
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    from PIL import Image
    import pytesseract
    log.debug("pytesseract + Pillow yuklendi.")
except ImportError:
    pytesseract = None
    Image = None

# ---------------------------------------------------------------------------
# hukuk_motoru entegrasyonu
# ---------------------------------------------------------------------------
try:
    from hukuk_motoru import analiz_et as hukuk_motoru_analiz_et
    HUKUK_MOTORU_AKTIF = True
    log.debug("hukuk_motoru.py yuklendi.")
except ImportError:
    hukuk_motoru_analiz_et = None
    HUKUK_MOTORU_AKTIF = False

# ---------------------------------------------------------------------------
# HATA-01 FIX: 2 asamali siniflandirma
# Asama 1 - Kesin tanimalar (puanlama calistirilmaz)
# ---------------------------------------------------------------------------
KUSAT_KESIN_TANIMLAR = [
    ":20:", ":31D:", ":32B:", ":40A:", ":44C:", ":45A:", ":46A:", ":47A:",
    "MT700", "MT 700", "DOCUMENTARY CREDIT", "IRREVOCABLE DOCUMENTARY",
]

FATURA_KESIN_TANIMLAR = [
    "COMMERCIAL INVOICE",
    "PROFORMA INVOICE",
]

KONSIMENTO_KESIN_TANIMLAR = [
    "BILL OF LADING",
    "OCEAN BILL OF LADING",
    "B/L NO",
    "BILL OF LADING NUMBER",
]

SIGORTA_KESIN_TANIMLAR = [
    "INSURANCE POLICY",
    "INSURANCE CERTIFICATE",
    "MARINE INSURANCE POLICY",
    "OPEN COVER POLICY",
]

CEKI_KESIN_TANIMLAR = [
    "PACKING LIST",
    "WEIGHT LIST",
    "CEKI LISTESI",
]

# ---------------------------------------------------------------------------
# Asama 2 - Puanlama tablosu (kesin tanim yoksa)
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
        ("INVOICE DATE", 20), ("INVOICE", 25),
        ("FATURA", 35),
    ],
    "KONSIMENTO": [
        ("SHIPPED ON BOARD", 35), ("PORT OF LOADING", 25),
        ("PORT OF DISCHARGE", 25), ("FREIGHT PREPAID", 20),
        ("CONSIGNEE", 20), ("SHIPPER", 15),
        ("KONŞİMENTO", 40),
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
        ("COVERAGE", 20), ("PREMIUM", 15),
        ("SİGORTA POLİÇESİ", 50),
    ],
}

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
KANIT_ESIK_MAJOR = 60

ORIGIN_IFADELERI = [
    "TURKISH ORIGIN", "COUNTRY OF ORIGIN", "GOODS ARE OF",
    "MADE IN TURKEY", "MANUFACTURED IN TURKEY", "OF TURKISH ORIGIN",
]

CERTIFICATE_OF_ORIGIN_IFADELERI = [
    "CERTIFICATE OF ORIGIN", "ORIGIN CERTIFICATE",
    "CHAMBER OF COMMERCE", "MENŞE ŞEHADETNAMESİ",
]

CO_46A_IFADELERI = [
    "CERTIFICATE OF ORIGIN", "CERTIFICATE OF ORIGIN ISSUED BY",
    "CHAMBER OF COMMERCE", "COUNTRY OF ORIGIN",
]

KIRLI_BL = [
    "CLAUSED", "DAMAGED", "TORN", "WET CARGO",
    "INSUFFICIENT PACKING", "PARTLY DAMAGED",
    "RUSTED", "LEAKING", "STAINED", "BROKEN",
]

PACKING_LIST_BEKLENEN = [
    "GROSS WEIGHT", "NET WEIGHT", "CBM", "MEASUREMENT",
    "PACKAGE DETAILS", "NUMBER OF PACKAGES", "PALLET",
    "MARKS", "CARTON", "PACKING LIST",
]

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
    "sigorta_eksik":          {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "2-3 Gun"},
    "tutar_uyusmazligi":      {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "1-2 Gun"},
    "yukleme_tarihi_ihlali":  {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "Akreditif degisikligi"},
    "konsimento_eksik":       {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "3-5 Gun"},
    "mal_tanimi_uyusmazligi": {"kategori": "MEDIUM DISCREPANCY","puan": 10, "sure": "1 Gun"},
    "mal_tanimi_kritik":      {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "1-2 Gun"},
    "kilo_uyusmazligi":       {"kategori": "MEDIUM DISCREPANCY","puan": 10, "sure": "1 Gun"},
    "ibraz_suresi_belirsiz":  {"kategori": "MINOR DISCREPANCY", "puan":  5, "sure": "Ayni Gun"},
    "temiz_bl_sorunu":        {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "3-7 Gun"},
    "46a_belge_eksigi":       {"kategori": "MEDIUM DISCREPANCY","puan": 10, "sure": "1-2 Gun"},
    "gec_yukleme":            {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "Akreditif degisikligi"},
    "co_eksik":               {"kategori": "MAJOR DISCREPANCY", "puan": 25, "sure": "3-5 Gun"},
}

ISBP_ESLESTIRME: dict[str, dict] = {
    "Art 14": {"prensip": "ISBP 821 A1-A7", "oneri": "21 gunluk ibraz suresi kontrolu yapildi."},
    "Art 18": {"prensip": "ISBP 821 C1-C23", "oneri": "Mal tanimi 45A alaniyla karsilastirilmali."},
    "Art 20": {"prensip": "ISBP 821 E1-E30", "oneri": "Shipped on Board serhi ve tarih dogrulanmali."},
    "Art 27": {"prensip": "ISBP 821 E26-E27","oneri": "Konsimentoda olumsuz kloz bulunmamali."},
    "Art 28": {"prensip": "ISBP 821 K1-K15", "oneri": "Sigorta min CIF x 110 olmali."},
    "Art 30": {"prensip": "ISBP 821 B14",    "oneri": "Tutar yuzde 5 tolerans siniri kontrol edilmeli."},
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


# ===========================================================================
# Belge Siniflandirici - 2 Asamali
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

        # --- ASAMA 1: Kesin tanimlama (HATA-01 FIX) ---
        if any(k in m for k in KUSAT_KESIN_TANIMLAR):
            log.debug("  -> Kesin tanim: KUSAT")
            return ("KUSAT", 999, {"KUSAT": 999})
        if any(k in m for k in KONSIMENTO_KESIN_TANIMLAR):
            log.debug("  -> Kesin tanim: KONSIMENTO")
            return ("KONSIMENTO", 999, {"KONSIMENTO": 999})
        if any(k in m for k in SIGORTA_KESIN_TANIMLAR):
            log.debug("  -> Kesin tanim: SIGORTA")
            return ("SIGORTA", 999, {"SIGORTA": 999})
        if any(k in m for k in CEKI_KESIN_TANIMLAR):
            log.debug("  -> Kesin tanim: CEKI_LISTESI")
            return ("CEKI_LISTESI", 999, {"CEKI_LISTESI": 999})
        if any(k in m for k in FATURA_KESIN_TANIMLAR):
            log.debug("  -> Kesin tanim: FATURA")
            return ("FATURA", 999, {"FATURA": 999})

        # --- ASAMA 2: Puanlama ---
        puanlar: dict[str, int] = {}
        for tur, liste in SINIFLANDIRMA_TABLOSU.items():
            toplam = 0
            for anahtar, puan in liste:
                if self._fuzzy(m, anahtar):
                    toplam += puan
                    log.debug("  Esleme [%s]: '%s' (+%d)", tur, anahtar, puan)
            puanlar[tur] = toplam

        en_iyi = max(puanlar, key=lambda k: puanlar[k])
        if puanlar[en_iyi] < 20:
            return ("DIGER", puanlar[en_iyi], puanlar)
        return (en_iyi, puanlar[en_iyi], puanlar)


# ===========================================================================
# Ana Sinif
# ===========================================================================
class YapayZekaDisTicaretDenetleyici:

    def __init__(self, ana_dizin: str = "DisTicaretRepo") -> None:
        self.base_dir        = ana_dizin
        self.yuklenenler_dir = os.path.join(ana_dizin, "YuklenenDosyalar")
        self.raporlar_dir    = os.path.join(ana_dizin, "Raporlar")
        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir,    exist_ok=True)

        self.siniflandirici          = BelgeSiniflandirici()
        self.depo: dict[str, Any]    = self._bos_depo()
        self.analiz_verisi: dict     = {}
        self.risk_puani              = 0
        self.uyumluluk_puani         = 100
        self.mt700_alanlari: dict    = {}
        self._aktif_rezervler: list  = []
        self._banka_kabul            = 100
        self._dosya_durum_log: list  = []

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
    # HATA-04 FIX: Gelismis sayi normallesme
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_tutar(metin: str) -> Optional[float]:
        """
        Tum para birimi formatlarini float'a cevirir.
        23,940 / 23.940 / 23,940.00 / 23.940,00 / USD 23,940 -> 23940.0
        """
        if not metin:
            return None
        # Para birimi, bosluk, tab temizle
        s = re.sub(r'[A-Za-z$\u20ac\xa3\t ]', '', str(metin)).strip()
        if not s:
            return None
        try:
            virgul_say = s.count(',')
            nokta_say  = s.count('.')
            son_v = s.rfind(',')
            son_n = s.rfind('.')

            if virgul_say == 0 and nokta_say == 0:
                return float(s)

            if virgul_say == 1 and nokta_say == 0:
                # 23,940 -> binlik mi? Son 3 hane kontrol
                sonrasi = s[son_v+1:]
                s = s.replace(',', '') if len(sonrasi) == 3 else s.replace(',', '.')

            elif nokta_say == 1 and virgul_say == 0:
                # 23.940 -> binlik mi?
                sonrasi = s[son_n+1:]
                if len(sonrasi) == 3:
                    s = s.replace('.', '')
                # else: gercek ondalik, birak

            elif son_v > son_n:
                # Avrupa: 23.940,00
                s = s.replace('.', '').replace(',', '.')
            else:
                # Anglo: 23,940.00
                s = s.replace(',', '')

            return float(s) if s else None
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # HATA-03 FIX: Sigorta tutari - SUM INSURED oncelikli
    # ------------------------------------------------------------------
    def sigorta_tutari_bul(self, metin: str) -> Optional[float]:
        if not metin:
            return None
        desenler = [
            r'(?:SUM\s+INSURED|AMOUNT\s+INSURED|INSURED\s+VALUE|INSURED\s+AMOUNT)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:INSURANCE\s+AMOUNT|INSURANCE\s+VALUE|COVERAGE\s+AMOUNT)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:TOTAL\s+INSURED|POLICY\s+AMOUNT)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        ]
        for d in desenler:
            m = re.search(d, metin, re.IGNORECASE)
            if m:
                v = self.normalize_tutar(m.group(1))
                if v:
                    log.debug("Sigorta tutari = %.2f", v)
                    return v
        return None

    # ------------------------------------------------------------------
    # HATA-02 FIX: MT700 parser - sifirdan yazildi
    # ------------------------------------------------------------------
    def mt700_ayristir(self, metin: str) -> dict[str, str]:
        """
        SWIFT MT700 formatindan alanlari cikarir.
        :32B:USD23940 veya :32B:\nUSD 23,940 gibi formatlari destekler.
        Cok satirli alanlar (45A, 46A, 47A) tam okunur.
        OCR toleransi: buyuk/kucuk harf, fazla bosluk.
        """
        if not metin:
            return {}

        hedef = ["20","31C","31D","32B","39A","40A","41A",
                 "43P","43T","44C","44E","44F","45A","46A","47A","48","49","71B","78"]
        cok_satirli = {"45A","46A","47A"}
        sonuc: dict[str, str] = {}

        log.debug("[DEBUG] MT700 parser basliyor. Metin uzunlugu: %d", len(metin))

        # Her alan icin: bu alandan sonraki alana kadar oku
        for alan in hedef:
            # Desenler - oncelik sirasi onemli
            desenler = [
                # Standart SWIFT: :32B:USD23940
                rf':{re.escape(alan)}:[ \t]*(.+?)(?=\n:|\Z)',
                # Cok satirli: :45A:\nicerik
                rf':{re.escape(alan)}:[ \t]*\n(.*?)(?=\n:[0-9]|\Z)',
                # Bosluklu: : 32B : deger
                rf':\s*{re.escape(alan)}\s*:[ \t]*(.+?)(?=\n:|\Z)',
                # Etiketsiz, sadece alan no + icerik ayni satirda
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[ \t]+(.+?)(?=\n[0-9]{{2,3}}[A-Z]?[ \t]|\n:|\Z)',
            ]

            # 46A icin ek: "DOCUMENTS REQUIRED" basligini da dene
            if alan == "46A":
                desenler.insert(0,
                    r'DOCUMENTS?\s+REQUIRED[:\s]*\n(.*?)(?=\n:[0-9]|\Z)'
                )
            if alan == "45A":
                desenler.insert(0,
                    r'DESCRIPTION\s+OF\s+GOODS?[:\s]*\n(.*?)(?=\n:[0-9]|\Z)'
                )
                desenler.insert(1,
                    r'DESCRIPTION\s+OF\s+GOODS?[:\s]+(.+?)(?=\n:[0-9]|\Z)'
                )

            flags = re.DOTALL | re.IGNORECASE | re.MULTILINE
            for desen in desenler:
                try:
                    m = re.search(desen, metin, flags)
                    if m:
                        ham = m.group(1).strip()
                        if not ham:
                            continue
                        if alan in cok_satirli:
                            deger = re.sub(r'[ \t]{2,}', ' ', ham)[:2000]
                        else:
                            deger = re.sub(r'\s+', ' ', ham)[:500]
                        if deger:
                            sonuc[alan] = deger
                            log.debug("[DEBUG] MT700 alan %s = '%s...'", alan, deger[:50])
                            break
                except re.error:
                    continue

        # 44C fallback - son yukleme tarihi
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

        log.debug("[DEBUG] MT700 alanlari cikarildi: %s", list(sonuc.keys()))
        return sonuc

    # ------------------------------------------------------------------
    # HATA-07 FIX: Alan bazli weight parser
    # ------------------------------------------------------------------
    def kilo_bul(self, metin: str) -> Optional[float]:
        if not metin:
            return None
        desenler = [
            r'GROSS\s*WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'G\.?W\.?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'NET\s*WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'N\.?W\.?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'TOTAL\s+WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'WEIGHT\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT\b|TON)',
            r'([\d,\.]+)\s*KGS\b',
        ]
        for d in desenler:
            m = re.search(d, metin, re.IGNORECASE)
            if m:
                v = self.normalize_tutar(m.group(1))
                if v:
                    return v
        return None

    # ------------------------------------------------------------------
    # HATA-08 FIX: B/L tarih parser - 6 format
    # ------------------------------------------------------------------
    def bl_tarihi_bul(self, metin: str) -> Optional[str]:
        if not metin:
            return None
        # Tarih formatlari
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
                r = m.group(1).strip()
                log.debug("B/L tarihi tespit edildi: '%s'", r)
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
    # Invoice CIF parser - HATA-04 FIX
    # ------------------------------------------------------------------
    def invoice_tutarlari_ayristir(self, metin: str) -> dict[str, Optional[float]]:
        if not metin:
            return {"goods_value": None, "freight": None,
                    "insurance": None, "cif_total": None, "invoice_total": None}

        def _bul(desenler):
            for d in desenler:
                m = re.search(d, metin, re.IGNORECASE)
                if m:
                    v = self.normalize_tutar(m.group(1))
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
        ins_amt = _bul([
            r'(?:INSURANCE\s+(?:PREMIUM|AMOUNT)|INS\.?)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        ])
        cif_total = _bul([
            r'(?:TOTAL\s+CIF\s+(?:VALUE|AMOUNT)|CIF\s+(?:TOTAL|VALUE|AMOUNT))'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        ])
        invoice_total = _bul([
            r'(?:TOTAL\s+(?:INVOICE\s+)?(?:VALUE|AMOUNT)|INVOICE\s+(?:TOTAL|AMOUNT|VALUE)'
            r'|AMOUNT\s+DUE|GRAND\s+TOTAL)\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)(?=\s*$)',
        ])

        if cif_total is None and goods is not None:
            computed = goods + (freight or 0) + (ins_amt or 0)
            if computed > goods:
                cif_total = computed

        log.debug("Invoice tutarlari: goods=%s freight=%s ins=%s cif=%s total=%s",
                  goods, freight, ins_amt, cif_total, invoice_total)
        return {"goods_value": goods, "freight": freight, "insurance": ins_amt,
                "cif_total": cif_total, "invoice_total": invoice_total}

    def lc_karsilastirma_tutari(self, d: dict) -> Optional[float]:
        """Oncelik: cif_total > invoice_total > goods_value"""
        return d.get("cif_total") or d.get("invoice_total") or d.get("goods_value")

    # ------------------------------------------------------------------
    # HATA-05+06 FIX: Origin analizi, 46A icin CO tara
    # ------------------------------------------------------------------
    def origin_analizi_yap(self, kusat_text: str, fatura_text: str,
                           alan_46a: str) -> dict:
        lc_co_istiyor = any(k in alan_46a.upper() for k in CO_46A_IFADELERI)
        if not lc_co_istiyor and kusat_text:
            lc_co_istiyor = any(k in kusat_text.upper() for k in CO_46A_IFADELERI)

        tum_metin = " ".join(
            self._depo_metin(k)
            for k in ["KUSAT","FATURA","KONSIMENTO","CEKI_LISTESI","SIGORTA"]
        ).upper()
        for d in (self.depo.get("DIGER_BELGELER") or []):
            if isinstance(d, dict):
                tum_metin += " " + d.get("metin","").upper()

        co_belgesi_var = any(k in tum_metin for k in CERTIFICATE_OF_ORIGIN_IFADELERI)
        invoice_beyan  = bool(fatura_text) and any(k in fatura_text.upper() for k in ORIGIN_IFADELERI)

        if not lc_co_istiyor:
            return {"durum": "BİLGİ", "detay": "LC'de CO sartidetected edilmedi.",
                    "rezerv_gerekli": False}
        if co_belgesi_var:
            return {"durum": "UYUMLU", "detay": "Certificate of Origin belgesi mevcut.",
                    "rezerv_gerekli": False}
        if invoice_beyan:
            return {
                "durum": "UYARI",
                "detay": ("Invoice'da menşe beyanı mevcut ('goods are of Turkish origin') "
                          "ancak bu ifade Certificate of Origin YERINE GECMEZ. "
                          "Ayri CO belgesi ibraz edilmeli."),
                "rezerv_gerekli": True,
            }
        return {"durum": "MAJOR DISCREPANCY",
                "detay": "LC CO istiyor ancak ne CO belgesi ne de invoice beyan bulunmadi.",
                "rezerv_gerekli": True}

    # ------------------------------------------------------------------
    # HATA-06 FIX: Packing List icerik kontrolu
    # ------------------------------------------------------------------
    def packing_list_kontrol(self, ceki_text: str) -> dict:
        if not ceki_text:
            return {"durum": "EKSİK", "bulunan": [], "eksik": PACKING_LIST_BEKLENEN}
        m = ceki_text.upper()
        bulunan = [a for a in PACKING_LIST_BEKLENEN if a in m]
        eksik   = [a for a in PACKING_LIST_BEKLENEN if a not in m]
        if len(bulunan) >= 4:
            return {"durum": "UYUMLU", "bulunan": bulunan, "eksik": eksik}
        if len(bulunan) >= 1:
            return {"durum": "KISMİ UYUM - MANUEL KONTROL", "bulunan": bulunan, "eksik": eksik}
        return {"durum": "EKSİK ALAN", "bulunan": bulunan, "eksik": eksik}

    # ------------------------------------------------------------------
    # HATA-09 FIX: Kanit puani
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
    # Mal tanimi karsilastirma
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
    # Risk puan yonetimi
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
    # HATA-10 FIX: Metin ayiklama - 4 kademeli durum
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu: str) -> tuple[str, bool]:
        if not dosya_yolu or not os.path.isfile(dosya_yolu):
            return ("", False)
        ext   = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""
        try:
            if ext == ".pdf":
                if not PdfReader:
                    return ("[Hata: pypdf yuklu degil]", False)
                r = PdfReader(dosya_yolu)
                for i, s in enumerate(r.pages):
                    try:
                        t = s.extract_text()
                        if t:
                            metin += t + "\n"
                    except Exception as e:
                        metin += f"[Sayfa {i+1} hatasi: {e}]\n"
            elif ext in [".docx", ".doc"]:
                if not docx:
                    return ("[Hata: python-docx yuklu degil]", False)
                d = docx.Document(dosya_yolu)
                for p in d.paragraphs:
                    if p.text:
                        metin += p.text + "\n"
                for tbl in d.tables:
                    for row in tbl.rows:
                        hucre = " ".join(c.text for c in row.cells if c.text)
                        if hucre.strip():
                            metin += hucre + "\n"
            elif ext in [".xlsx", ".xls"]:
                if not openpyxl:
                    return ("[Hata: openpyxl yuklu degil]", False)
                wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
                for sn in wb.sheetnames:
                    ws = wb[sn]
                    for row in ws.iter_rows(values_only=True):
                        satir = " ".join(str(c) for c in row if c is not None)
                        if satir.strip():
                            metin += satir + "\n"
            elif ext in [".png", ".jpg", ".jpeg"]:
                if not pytesseract or not Image:
                    return ("[Hata: pytesseract yuklu degil]", False)
                img = Image.open(dosya_yolu)
                try:
                    metin = pytesseract.image_to_string(img, lang="eng+tur") or ""
                except Exception:
                    try:
                        metin = pytesseract.image_to_string(img, lang="eng") or ""
                    except Exception as e2:
                        return (f"[OCR Hatasi: {e2}]", False)
            elif ext == ".txt":
                with open(dosya_yolu, encoding="utf-8", errors="ignore") as f:
                    metin = f.read()
            else:
                return (f"[Desteklenmeyen format: {ext}]", False)
        except Exception as e:
            log.error("Dosya okuma hatasi [%s]: %s\n%s", dosya_yolu, e, traceback.format_exc())
            return (f"[Okuma hatasi: {e}]", False)

        metin = metin.replace("\xa0", " ").replace("\u200b", "").replace("\r\n", "\n")
        ocr_ok = bool(metin.strip()) and not metin.startswith("[")
        return (metin, ocr_ok)

    # ------------------------------------------------------------------
    # Depo tarama
    # ------------------------------------------------------------------
    def depoyu_tara(self) -> bool:
        self.depo                = self._bos_depo()
        self.risk_puani          = 0
        self.uyumluluk_puani     = 100
        self.mt700_alanlari      = {}
        self._aktif_rezervler    = []
        self._banka_kabul        = 100
        self._dosya_durum_log    = []

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
                log.warning("[UYARI] %s OCR basarisiz: %s", ad, metin[:60])
                self._dosya_durum_log.append(kayit)
                continue

            log.debug("[DEBUG] OCR tamamlandi: %s (%d karakter)", ad, len(metin))

            tur, puan, puanlar = self.siniflandirici.siniflandir(metin)
            kayit["sinif"] = tur
            kayit["puan"]  = puan
            kayit["parse_ok"] = tur != "DIGER"

            log.debug("[DEBUG] Belge tipi = %s (puan: %s) — %s", tur, puan, ad)

            if tur in ["KUSAT","FATURA","KONSIMENTO","CEKI_LISTESI","SIGORTA"]:
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
    # UCP 600 Kural Motoru
    # ------------------------------------------------------------------
    def ucp600_kural_motoru(self) -> None:
        log.debug("[DEBUG] Capraz kontrol basladi.")

        kusat_text = self._depo_metin("KUSAT")
        fatura_text = self._depo_metin("FATURA")
        konsimento_text = self._depo_metin("KONSIMENTO")
        ceki_text = self._depo_metin("CEKI_LISTESI")
        sigorta_text = self._depo_metin("SIGORTA")
        combined = (kusat_text + " " + fatura_text + " " + konsimento_text).upper()

        # MT700'den alanlar
        alan_46a = self.mt700_alanlari.get("46A", "")
        alan_45a = self.mt700_alanlari.get("45A", "")
        alan_32b = self.mt700_alanlari.get("32B", "")
        alan_44c = self.mt700_alanlari.get("44C", "")

        sonuclar: dict[str, Any] = {
            "vade_analizi": [], "finansal_durum": [], "incoterms": [],
            "capraz_kontrol": [], "zorunlu_alanlar": [], "ucp_tablosu": [],
            "risk_ozeti": [], "rezerv_ozeti": [], "belge_46a": [],
            "isbp_tablosu": [], "eksik_belgeler": [],
            "mt700_alan_analizi": [], "tarih_zinciri": [],
            "rezerv_swift": [], "yonetici_ozeti": {},
            "rezerv_detaylar": [], "dosya_durum_raporu": self._dosya_durum_log,
            "packing_list_kontrol": {},
        }

        # ── 1. Vade Analizi ──
        if alan_44c:
            sonuclar["vade_analizi"].append(f"En Gec Yukleme (44C): **{alan_44c}**")
        else:
            sonuclar["vade_analizi"].append("En Gec Yukleme (44C): Tespit edilemedi — manuel kontrol.")

        ibraz = re.search(r'(\d+)\s*DAYS?\s*(?:AFTER|FOR\s+PRESENTATION)', combined, re.IGNORECASE)
        if ibraz:
            gun = int(ibraz.group(1))
            sonuclar["vade_analizi"].append(f"Ibraz Suresi: **{gun} gun** (max 21)")
            if gun > 21:
                self._risk_ekle("ibraz_suresi_belirsiz")
                self._uyum_dus(10)
        else:
            sonuclar["vade_analizi"].append("Ibraz Suresi: Tespit edilemedi — UCP Art 14c 21 gun uygulanir.")
            self._risk_ekle("ibraz_suresi_belirsiz")
            self._uyum_dus(5)

        # ── 2. Odeme Vadesi ──
        if any(x in combined for x in ["AT SIGHT","SIGHT PAYMENT","GORULDU"]):
            sonuclar["finansal_durum"].append("Odeme: **At Sight** (UCP Art 15b)")
        elif any(x in combined for x in ["DAYS AFTER","DEFERRED PAYMENT","VADELI"]):
            sonuclar["finansal_durum"].append("Odeme: **Vadeli** — poliçe takvimi kontrol edilmeli.")
        else:
            sonuclar["finansal_durum"].append("Odeme: Tespit edilemedi — manuel kontrol.")

        # ── 3. Incoterms ──
        incoterm: Optional[str] = None
        for t in ["EXW","FCA","CPT","CIP","DAP","DPU","DDP","FAS","FOB","CFR","CIF"]:
            if t in combined:
                incoterm = t
                sonuclar["incoterms"].append(f"Incoterms: **{t} (ICC 2020)**")
                break
        if not incoterm:
            sonuclar["incoterms"].append("Incoterms: Tespit edilemedi.")

        # CIF/CIP sigorta kontrolu
        if incoterm in ["CIF","CIP"]:
            if self.depo["SIGORTA"]:
                sonuclar["incoterms"].append(f"[TAMAM] {incoterm} — Sigorta belgesi mevcut.")
            else:
                sonuclar["incoterms"].append(f"[REZERV] {incoterm} — Sigorta belgesi EKSIK!")
                self._risk_ekle("sigorta_eksik")
                self._uyum_dus(20)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Sigorta belgesi eksik ({incoterm} / Art 28)"
                )
                sonuclar["eksik_belgeler"].append("Sigorta Poliçesi")

        # ── 4. Tutar Karsilastirmasi (Art 18/30) ──
        fatura_t = self.invoice_tutarlari_ayristir(fatura_text)
        fatura_tutar = self.lc_karsilastirma_tutari(fatura_t)
        log.debug("[DEBUG] CIF toplami = %s", fatura_tutar)

        lc_tutar: Optional[float] = None
        if alan_32b:
            lc_tutar = self.normalize_tutar(alan_32b)
        if lc_tutar is None:
            lc_tutar = self.normalize_tutar(
                re.search(r'(?:USD|EUR|GBP|TRY)\s*([\d,\.]+)', kusat_text or '', re.IGNORECASE)
                and re.search(r'(?:USD|EUR|GBP|TRY)\s*([\d,\.]+)', kusat_text or '', re.IGNORECASE).group(1)
            )

        if fatura_tutar and lc_tutar:
            about = any(x in (kusat_text or '').upper() for x in ["ABOUT","APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma = (fatura_tutar - lc_tutar) / lc_tutar * 100
            cif_detay = ""
            if fatura_t.get("goods_value"):
                cif_detay = (
                    f" [Goods:{fatura_t['goods_value']:,.2f}"
                    f"+Frt:{fatura_t.get('freight') or 0:,.2f}"
                    f"+Ins:{fatura_t.get('insurance') or 0:,.2f}=CIF:{fatura_tutar:,.2f}]"
                )
            detay = (f"LC:{lc_tutar:,.2f} | Fatura CIF:{fatura_tutar:,.2f}"
                     f"{cif_detay} | Sapma:{sapma:+.1f}% | Tolerans:±%{tolerans}")
            if abs(sapma) <= tolerans:
                sonuclar["capraz_kontrol"].append(
                    {"belge":"Tutar LC vs Fatura (Art 30)","detay":detay,"durum":"UYUMLU"})
            else:
                sonuclar["capraz_kontrol"].append(
                    {"belge":"Tutar LC vs Fatura (Art 30)","detay":detay,
                     "durum":"REZERV - TUTAR UYUSMAZLIGI"})
                self._risk_ekle("tutar_uyusmazligi")
                self._uyum_dus(20)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Tutar sapması %{abs(sapma):.1f} > %{tolerans} (Art 30)"
                )
        else:
            eksik = [k for k,v in [("Fatura",fatura_tutar),("LC 32B",lc_tutar)] if not v]
            sonuclar["capraz_kontrol"].append(
                {"belge":"Tutar LC vs Fatura (Art 30)",
                 "detay":f"Tespit edilemedi: {', '.join(eksik)}","durum":"MANUEL KONTROL"})

        # ── 5. Kilo Karsilastirmasi ──
        fat_k = self.kilo_bul(fatura_text)
        bl_k  = self.kilo_bul(konsimento_text)
        pl_k  = self.kilo_bul(ceki_text)

        for (a_isim, a_k, b_isim, b_k) in [
            ("Fatura", fat_k, "B/L", bl_k),
            ("Fatura", fat_k, "Packing List", pl_k),
            ("Packing List", pl_k, "B/L", bl_k),
        ]:
            if a_k is not None and b_k is not None:
                if abs(a_k - b_k) < 1.0:
                    sonuclar["capraz_kontrol"].append(
                        {"belge":f"Kilo: {a_isim} vs {b_isim}",
                         "detay":f"Eslesti: {a_k:,.2f} KG","durum":"UYUMLU"})
                else:
                    sonuclar["capraz_kontrol"].append(
                        {"belge":f"Kilo: {a_isim} vs {b_isim}",
                         "detay":f"{a_isim}:{a_k:,.2f} | {b_isim}:{b_k:,.2f} KG",
                         "durum":"REZERV - KILO UYUSMAZLIGI"})
                    self._risk_ekle("kilo_uyusmazligi")
                    self._uyum_dus(10)
                    sonuclar["rezerv_ozeti"].append(
                        f"REZERV — Kilo: {a_isim} {a_k:,.2f} != {b_isim} {b_k:,.2f} KG"
                    )
            else:
                eksik = [n for n,v in [(a_isim,a_k),(b_isim,b_k)] if v is None]
                sonuclar["capraz_kontrol"].append(
                    {"belge":f"Kilo: {a_isim} vs {b_isim}",
                     "detay":f"Tespit edilemedi: {', '.join(eksik)}","durum":"MANUEL KONTROL"})

        # ── 6. Mal Tanimi (Art 18c) ──
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
                durum_mal = "DUSUK BENZERLIK - MANUEL KONTROL"
                self._risk_ekle("mal_tanimi_uyusmazligi")
                self._uyum_dus(15)
            else:
                durum_mal = "REZERV - MAL TANIMI UYUSMAZLIGI"
                self._risk_ekle("mal_tanimi_kritik")
                self._uyum_dus(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Mal tanimi: %{oran*100:.0f} örtüsme (Art 18c)"
                )
            sonuclar["capraz_kontrol"].append(
                {"belge":"Mal Tanimi LC vs Fatura (Art 18c)",
                 "detay":f"LC:{lc_mal[:60]} | Fatura:{fat_mal[:60]} | %{oran*100:.0f}",
                 "durum":durum_mal})
        else:
            sonuclar["capraz_kontrol"].append(
                {"belge":"Mal Tanimi LC vs Fatura (Art 18c)",
                 "detay":f"Tespit edilemedi: {'45A' if not lc_mal else ''} {'Fatura' if not fat_mal else ''}",
                 "durum":"MANUEL KONTROL"})

        # ── 7. Yukleme Tarihi (Art 20 / 44C) ──
        bl_tarih_str = self.bl_tarihi_bul(konsimento_text)
        lc_tarih_str = alan_44c
        bl_dt = self.tarih_ayristir(bl_tarih_str) if bl_tarih_str else None
        lc_dt = self.tarih_ayristir(lc_tarih_str) if lc_tarih_str else None

        if bl_dt and lc_dt:
            if bl_dt <= lc_dt:
                sonuclar["capraz_kontrol"].append(
                    {"belge":"B/L Tarihi vs 44C (Art 20)",
                     "detay":f"{bl_tarih_str} <= {lc_tarih_str}","durum":"UYUMLU"})
            else:
                sonuclar["capraz_kontrol"].append(
                    {"belge":"B/L Tarihi vs 44C (Art 20)",
                     "detay":f"GEC YUKLEME: {bl_tarih_str} > {lc_tarih_str}",
                     "durum":"REZERV - GEC YUKLEME"})
                self._risk_ekle("gec_yukleme")
                self._uyum_dus(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — GEC YUKLEME: {bl_tarih_str} > 44C {lc_tarih_str}"
                )
        elif bl_tarih_str or lc_tarih_str:
            sonuclar["capraz_kontrol"].append(
                {"belge":"B/L Tarihi vs 44C (Art 20)",
                 "detay":f"B/L:{bl_tarih_str or '-'} | 44C:{lc_tarih_str or '-'}",
                 "durum":"MANUEL KONTROL"})
        else:
            sonuclar["capraz_kontrol"].append(
                {"belge":"B/L Tarihi vs 44C (Art 20)",
                 "detay":"Her iki tarih de tespit edilemedi","durum":"MANUEL KONTROL"})
            if konsimento_text:
                self._risk_ekle("yukleme_tarihi_ihlali")
                self._uyum_dus(15)
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — B/L yukleme tarihi tespit edilemedi (Art 20)"
                )

        # ── 8. Sigorta Teminati (Art 28f-ii) ──
        if incoterm in ["CIF","CIP"] and self.depo["SIGORTA"]:
            sig_t = self.sigorta_tutari_bul(sigorta_text)
            log.debug("[DEBUG] Sigorta tutari = %s", sig_t)
            if sig_t and fatura_tutar:
                min_t = fatura_tutar * 1.10
                if sig_t >= min_t:
                    sonuclar["capraz_kontrol"].append(
                        {"belge":"Sigorta >= CIF x 110% (Art 28f-ii)",
                         "detay":f"Sigorta:{sig_t:,.2f} | Min:{min_t:,.2f}","durum":"UYUMLU"})
                else:
                    sonuclar["capraz_kontrol"].append(
                        {"belge":"Sigorta >= CIF x 110% (Art 28f-ii)",
                         "detay":f"Sigorta:{sig_t:,.2f} < Min:{min_t:,.2f}",
                         "durum":"REZERV - YETERSIZ TEMINAT"})
                    self._risk_ekle("sigorta_eksik")
                    self._uyum_dus(20)
                    sonuclar["rezerv_ozeti"].append(
                        f"REZERV — Sigorta yetersiz: {sig_t:,.2f} < {min_t:,.2f}"
                    )
            else:
                sonuclar["capraz_kontrol"].append(
                    {"belge":"Sigorta >= CIF x 110% (Art 28f-ii)",
                     "detay":"Tutar tespit edilemedi","durum":"MANUEL KONTROL"})

        # ── 9. Konsimento (Art 20, Art 27) ──
        if not konsimento_text:
            sonuclar["zorunlu_alanlar"].append("[REZERV] Konsimento belgesi yok!")
            self._risk_ekle("konsimento_eksik")
            self._uyum_dus(30)
            sonuclar["rezerv_ozeti"].append("REZERV — Konsimento ibraz edilmemis (Art 20)")
            sonuclar["eksik_belgeler"].append("Konsimento")
        else:
            bl_u = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] 'Shipped on Board' serhi mevcut (Art 20a-ii).")
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[REZERV] 'Shipped on Board' serhi bulunamadi!")
                self._risk_ekle("konsimento_eksik")
                self._uyum_dus(20)
                sonuclar["rezerv_ozeti"].append("REZERV — On Board serhi eksik (Art 20a-ii)")

            kirli = [k for k in KIRLI_BL if k in bl_u]
            if kirli:
                sonuclar["zorunlu_alanlar"].append(
                    f"[REZERV] Klozlu konsimento: {', '.join(kirli)} (Art 27)")
                self._risk_ekle("temiz_bl_sorunu")
                self._uyum_dus(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Klozlu konsimento: {', '.join(kirli)}")
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Kirli/klozlu ifade bulunamadi (Art 27 uyumlu).")

        # ── 10. Eksik Belgeler (HATA-09 FIX: kanit puani ile) ──
        for key, ad in [("KUSAT","Kusat (MT700)"),("FATURA","Fatura"),
                        ("CEKI_LISTESI","Ceki Listesi")]:
            if not self.depo[key]:
                ilgili = [d for d in self._dosya_durum_log if d.get("sinif") == key]
                if ilgili:
                    en_iyi = max(ilgili, key=lambda x: x.get("puan",0))
                    kp = self.kanit_puani(True, en_iyi.get("ocr_ok",False),
                                          en_iyi.get("parse_ok",False))
                    if kp < KANIT_ESIK_MAJOR:
                        sonuclar["eksik_belgeler"].append(
                            f"{ad} — OCR/sinif belirsiz (kanit:{kp}/100) MANUEL KONTROL"
                        )
                else:
                    sonuclar["eksik_belgeler"].append(ad)

        # ── 11. 46A Belge Sartlari ──
        if alan_46a:
            kontroller = [
                ("COMMERCIAL INVOICE","FATURA","Ticari Fatura"),
                ("INVOICE","FATURA","Ticari Fatura"),
                ("BILL OF LADING","KONSIMENTO","Konsimento"),
                ("PACKING LIST","CEKI_LISTESI","Packing List"),
                ("INSURANCE","SIGORTA","Sigorta Policesi"),
            ]
            goruldu = set()
            for sart, dk, ad in kontroller:
                if sart in alan_46a.upper() and sart not in goruldu:
                    goruldu.add(sart)
                    var = self.depo.get(dk) is not None
                    if not var:
                        self._risk_ekle("46a_belge_eksigi")
                        self._uyum_dus(10)
                        sonuclar["rezerv_ozeti"].append(
                            f"REZERV — 46A geregi '{ad}' belgesi eksik"
                        )
                    sonuclar["belge_46a"].append(
                        {"sart":ad,"detay":"46A'da talep edildi.",
                         "durum":"VAR" if var else "EKSIK"})
        else:
            sonuclar["belge_46a"].append(
                {"sart":"46A","detay":"MT700 46A tespit edilemedi.","durum":"MANUEL KONTROL"})

        # ── 12. Packing List Icerik Kontrolu ──
        if self.depo.get("CEKI_LISTESI"):
            pl_k = self.packing_list_kontrol(ceki_text)
            sonuclar["packing_list_kontrol"] = pl_k
            sonuclar["belge_46a"].append({
                "sart":"Packing List Icerik",
                "detay":f"Bulunan: {', '.join(pl_k['bulunan']) or '-'} | "
                        f"Eksik: {', '.join(pl_k['eksik']) or '-'}",
                "durum":pl_k["durum"],
            })

        # ── 13. HATA-05 FIX: Origin Analizi ──
        origin = self.origin_analizi_yap(kusat_text or '', fatura_text or '', alan_46a)
        sonuclar["capraz_kontrol"].append({
            "belge":"Mense (Origin) Analizi",
            "detay":origin["detay"],
            "durum":origin["durum"],
        })
        if origin["rezerv_gerekli"]:
            self._risk_ekle("co_eksik")
            self._uyum_dus(15)
            sonuclar["rezerv_ozeti"].append(
                f"REZERV — Mense: {origin['detay'][:100]}"
            )

        # ── 14. MT700 Alan Analizi ──
        MT700_ALANLAR = {
            "20":"Documentary Credit Number","31D":"Expiry Date","32B":"Amount",
            "40A":"Form","44C":"Latest Shipment","44E":"Port of Loading",
            "44F":"Port of Discharge","45A":"Description of Goods",
            "46A":"Documents Required","47A":"Additional Conditions","48":"Presentation Period",
        }
        for kod, aciklama in MT700_ALANLAR.items():
            deger = self.mt700_alanlari.get(kod)
            if deger:
                sonuclar["mt700_alan_analizi"].append(
                    {"alan":kod,"aciklama":aciklama,"deger":deger[:100],"durum":"TESPIT EDILDI"})
            elif kod in {"20","31D","32B","40A","44C","45A","46A"}:
                sonuclar["mt700_alan_analizi"].append(
                    {"alan":kod,"aciklama":aciklama,"deger":"—","durum":"TESPIT EDILEMEDI"})

        # ── 15. Hukuk Motoru ──
        if HUKUK_MOTORU_AKTIF and hukuk_motoru_analiz_et:
            try:
                r = hukuk_motoru_analiz_et(self.depo)
                if isinstance(r, list) and r:
                    sonuclar["ucp_tablosu"] = r
            except Exception as e:
                log.warning("hukuk_motoru hatasi: %s", e)
                log.debug(traceback.format_exc())

        # ── 16. Risk Ozeti ──
        sonuclar["risk_ozeti"].append(
            f"Risk Puani: **{self.risk_puani}** — {self._risk_sinifi()}")
        sonuclar["risk_ozeti"].append(
            f"Uyumluluk: **%{self.uyumluluk_puani}**")
        for i, r in enumerate(sonuclar["rezerv_ozeti"], 1):
            sonuclar["risk_ozeti"].append(f"{i}. {r}")

        # ── 17. SWIFT Simulatoru ──
        sonuclar["rezerv_swift"] = [
            REZERV_SWIFT[k] for k in self._aktif_rezervler if k in REZERV_SWIFT
        ]

        # ── 18. Rezerv Detaylar ──
        sonuclar["rezerv_detaylar"] = [
            {"kod":k,
             "kategori":REZERV_KATEGORILERI.get(k,{}).get("kategori","?"),
             "puan":str(REZERV_KATEGORILERI.get(k,{}).get("puan","?")),
             "sure":REZERV_KATEGORILERI.get(k,{}).get("sure","?")}
            for k in self._aktif_rezervler
        ]

        # ── 19. Yonetici Ozeti ──
        mevcut = [k for k in ["KUSAT","FATURA","KONSIMENTO","CEKI_LISTESI","SIGORTA"]
                  if self.depo.get(k)]
        major = sum(1 for k in self._aktif_rezervler
                    if REZERV_KATEGORILERI.get(k,{}).get("kategori") == "MAJOR DISCREPANCY")
        sonuclar["yonetici_ozeti"] = {
            "toplam_belge":   len(mevcut),
            "mevcut":         mevcut,
            "eksik":          sonuclar["eksik_belgeler"],
            "toplam_rezerv":  len(sonuclar["rezerv_ozeti"]),
            "major_rezerv":   major,
            "uyumluluk":      self.uyumluluk_puani,
            "risk_puani":     self.risk_puani,
            "risk_sinifi":    self._risk_sinifi(),
            "banka_kabul":    self._banka_kabul,
        }

        self.analiz_verisi = sonuclar

    # ------------------------------------------------------------------
    # Markdown raporu
    # ------------------------------------------------------------------
    def markdown_raporu(self) -> None:
        v = self.analiz_verisi
        if not v:
            return
        yol = os.path.join(self.raporlar_dir, "rapor.md")
        s = []
        s.append("# AKREDITIF ANALIZ RAPORU v8.0\n\n")
        s.append(f"**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')} | Motor: UCP 600 & ISBP 821\n\n---\n\n")

        # Dosya Durum
        s.append("## Dosya Durum Raporu\n\n")
        s.append("| Dosya | Var | OCR | Sinif | Parse | Puan |\n|:---|:---|:---|:---|:---|:---|\n")
        for d in v.get("dosya_durum_raporu",[]):
            s.append(
                f"| {d.get('dosya','')} | {'V' if d.get('dosya_var') else 'X'} | "
                f"{'V' if d.get('ocr_ok') else 'X'} | {d.get('sinif') or '-'} | "
                f"{'V' if d.get('parse_ok') else 'X'} | {d.get('puan','?')} |\n"
            )
        s.append("\n---\n\n")

        # Yonetici Ozeti
        oz = v.get("yonetici_ozeti",{})
        if oz:
            s.append("## Yonetici Ozeti\n\n")
            s.append(f"| Metrik | Deger |\n|:---|:---|\n")
            s.append(f"| Belgeler | {', '.join(oz.get('mevcut',[]))} |\n")
            s.append(f"| Rezerv | {oz.get('toplam_rezerv',0)} (MAJOR: {oz.get('major_rezerv',0)}) |\n")
            s.append(f"| Uyumluluk | **%{oz.get('uyumluluk','?')}** |\n")
            s.append(f"| Banka Kabul | **%{oz.get('banka_kabul','?')}** |\n")
            s.append(f"| Risk | {oz.get('risk_sinifi','?')} |\n\n---\n\n")

        # MT700
        s.append("## MT700 Alan Analizi\n\n")
        s.append("| Alan | Aciklama | Deger | Durum |\n|:---|:---|:---|:---|\n")
        for a in v.get("mt700_alan_analizi",[]):
            s.append(f"| **{a['alan']}** | {a['aciklama']} | `{a['deger']}` | {a['durum']} |\n")
        s.append("\n---\n\n")

        for baslik, anahtar in [
            ("Vade Analizi","vade_analizi"),
            ("Odeme Vadesi","finansal_durum"),
            ("Incoterms & Sigorta","incoterms"),
        ]:
            s.append(f"## {baslik}\n\n")
            for x in v.get(anahtar,[]): s.append(f"* {x}\n")
            s.append("\n")

        s.append("## Capraz Kontroller\n\n")
        s.append("| Belgeler | Detay | Durum |\n|:---|:---|:---|\n")
        for c in v.get("capraz_kontrol",[]):
            s.append(f"| {c['belge']} | {c['detay']} | **{c['durum']}** |\n")

        s.append("\n## Konsimento\n\n")
        for x in v.get("zorunlu_alanlar",[]): s.append(f"* {x}\n")

        s.append("\n## 46A Belge Sartlari\n\n")
        s.append("| Belge | Detay | Durum |\n|:---|:---|:---|\n")
        for b in v.get("belge_46a",[]):
            s.append(f"| {b['sart']} | {b['detay']} | **{b['durum']}** |\n")

        s.append("\n## Tespit Edilen Rezervler\n\n")
        for r in v.get("rezerv_ozeti",[]): s.append(f"* {r}\n")
        if not v.get("rezerv_ozeti"):
            s.append("* Kritik rezerv tespit edilmedi.\n")

        s.append("\n## Rezerv Kategorileri\n\n")
        s.append("| Kod | Kategori | Puan | Sure |\n|:---|:---|:---|:---|\n")
        for d in v.get("rezerv_detaylar",[]):
            s.append(f"| {d['kod']} | **{d['kategori']}** | {d['puan']} | {d['sure']} |\n")

        s.append("\n## Risk Degerlendirmesi\n\n")
        for x in v.get("risk_ozeti",[]): s.append(f"* {x}\n")

        swift = v.get("rezerv_swift",[])
        if swift:
            s.append("\n## SWIFT Rezerv Simulatoru\n\n")
            for i, mt in enumerate(swift,1):
                s.append(f"### Ret Metni {i}\n\n```\n{mt}\n```\n\n")

        with open(yol, "w", encoding="utf-8") as f:
            f.writelines(s)
        print("[+] Markdown raporu olusturuldu:", yol)

    # ------------------------------------------------------------------
    # HTML raporu
    # ------------------------------------------------------------------
    def html_raporu(self) -> None:
        v = self.analiz_verisi
        if not v:
            return
        yol = os.path.join(self.raporlar_dir, "rapor.html")

        def li(k): return "".join(f"<li>{x}</li>" for x in v.get(k,[]))
        def tablo3(satirlar, anahtarlar):
            return "".join(
                "<tr>" + "".join(f"<td>{r.get(k,'')}</td>" for k in anahtarlar) + "</tr>"
                for r in satirlar
            )

        oz = v.get("yonetici_ozeti",{})
        krenk = ("#276749" if oz.get("banka_kabul",0) >= 70
                 else "#d69e2e" if oz.get("banka_kabul",0) >= 40 else "#c53030")

        ddr = "".join(
            f"<tr><td>{d.get('dosya','')}</td>"
            f"<td>{'V' if d.get('dosya_var') else 'X'}</td>"
            f"<td>{'V' if d.get('ocr_ok') else 'X'}</td>"
            f"<td>{d.get('sinif') or '-'}</td>"
            f"<td>{'V' if d.get('parse_ok') else 'X'}</td>"
            f"<td>{d.get('puan','?')}</td></tr>"
            for d in v.get("dosya_durum_raporu",[])
        )
        mt_html = "".join(
            f"<tr><td><b>{a['alan']}</b></td><td>{a['aciklama']}</td>"
            f"<td><code>{a['deger']}</code></td><td>{a['durum']}</td></tr>"
            for a in v.get("mt700_alan_analizi",[])
        )
        cc_html = tablo3(v.get("capraz_kontrol",[]), ["belge","detay","durum"])
        b46_html = tablo3(v.get("belge_46a",[]), ["sart","detay","durum"])
        rezerv_html = "".join(
            f"<li>{r}</li>" for r in v.get("rezerv_ozeti",[])
        ) or "<li>Kritik rezerv tespit edilmedi.</li>"
        kat_html = "".join(
            f"<tr><td>{d['kod']}</td><td><b>{d['kategori']}</b></td>"
            f"<td>{d['puan']}</td><td>{d['sure']}</td></tr>"
            for d in v.get("rezerv_detaylar",[])
        )
        swift_html = "".join(
            f'<div class="swift"><b>Ret {i}</b><pre>{mt}</pre></div>'
            for i,mt in enumerate(v.get("rezerv_swift",[]),1)
        ) or '<p style="color:#276749">SWIFT ret metni uretilmedi.</p>'

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Akreditif Analiz Raporu v8.0</title>
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
<h1>AKREDITIF GELISMIS HUKUKI VE SAYISAL UZMAN DENETIM RAPORU v8.0</h1>
<p class="meta"><b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} | <b>Motor:</b> UCP 600 &amp; ISBP 821</p>

<div class="exec">
<h2>Yonetici Ozeti</h2>
<div class="grid">
<div class="card"><div class="lbl">Belgeler</div><div class="val">{oz.get('toplam_belge','?')}</div></div>
<div class="card"><div class="lbl">Rezerv</div><div class="val" style="color:#c53030">{oz.get('toplam_rezerv',0)}</div></div>
<div class="card"><div class="lbl">MAJOR</div><div class="val" style="color:#c53030">{oz.get('major_rezerv',0)}</div></div>
<div class="card"><div class="lbl">Uyumluluk</div><div class="val" style="color:#276749">%{oz.get('uyumluluk','?')}</div></div>
<div class="card"><div class="lbl">Banka Kabul</div><div class="val" style="color:{krenk}">%{oz.get('banka_kabul','?')}</div></div>
<div class="card"><div class="lbl">Risk</div><div class="val" style="font-size:.9em">{oz.get('risk_sinifi','?')}</div></div>
</div>
</div>

<h2>Dosya Durum Raporu</h2>
<table><tr><th>Dosya</th><th>Var</th><th>OCR</th><th>Sinif</th><th>Parse</th><th>Puan</th></tr>{ddr}</table>

<h2>MT700 Alan Analizi</h2>
<table><tr><th>Alan</th><th>Aciklama</th><th>Deger</th><th>Durum</th></tr>{mt_html}</table>

<h2>Vade Analizi</h2><ul>{li("vade_analizi")}</ul>
<h2>Odeme Vadesi</h2><ul>{li("finansal_durum")}</ul>
<h2>Incoterms &amp; Sigorta</h2><ul>{li("incoterms")}</ul>

<h2>Capraz Kontroller</h2>
<table><tr><th>Belgeler</th><th>Detay</th><th>Durum</th></tr>{cc_html}</table>

<h2>Konsimento Kontrolleri</h2><ul>{li("zorunlu_alanlar")}</ul>

<h2>46A Belge Sartlari</h2>
<table><tr><th>Belge</th><th>Detay</th><th>Durum</th></tr>{b46_html}</table>

<h2>Tespit Edilen Rezervler</h2><ul>{rezerv_html}</ul>

<h2>Rezerv Kategorileri</h2>
<table><tr><th>Kod</th><th>Kategori</th><th>Puan</th><th>Sure</th></tr>{kat_html}</table>

<h2>Risk Degerlendirmesi</h2><ul>{li("risk_ozeti")}</ul>

<h2>SWIFT Rezerv Simulatoru</h2>{swift_html}
</div></body></html>"""

        with open(yol, "w", encoding="utf-8") as f:
            f.write(html)
        print("[+] HTML raporu olusturuldu:", yol)

    # ------------------------------------------------------------------
    # Ana akis
    # ------------------------------------------------------------------
    def baslat(self) -> None:
        print("[BİLGİ] Akreditif denetim sistemi v8.0 baslatiyor...")
        if self.depoyu_tara():
            print(
                f"[BİLGİ] Belgeler: "
                f"KUSAT={'VAR' if self.depo['KUSAT'] else 'YOK'} | "
                f"FATURA={'VAR' if self.depo['FATURA'] else 'YOK'} | "
                f"KONSIMENTO={'VAR' if self.depo['KONSIMENTO'] else 'YOK'} | "
                f"CEKI={'VAR' if self.depo['CEKI_LISTESI'] else 'YOK'} | "
                f"SIGORTA={'VAR' if self.depo['SIGORTA'] else 'YOK'}"
            )
            self.ucp600_kural_motoru()
            self.markdown_raporu()
            self.html_raporu()
            print(
                f"[SONUC] Risk:{self.risk_puani} {self._risk_sinifi()} | "
                f"Uyumluluk:%{self.uyumluluk_puani} | BankaKabul:%{self._banka_kabul}"
            )
        else:
            print("[BİLGİ] Yuklenecek belge bulunamadi.")


if __name__ == "__main__":
    YapayZekaDisTicaretDenetleyici().baslat()
