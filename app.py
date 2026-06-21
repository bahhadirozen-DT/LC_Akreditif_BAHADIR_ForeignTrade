"""
app.py — Yapay Zeka Destekli Dış Ticaret Akreditif Denetleme Sistemi
UCP 600 / ISBP 821 Uyumlu | Üretim Ortamı Sürümü v7.0

Düzeltilen Kritik Hatalar (v6.0 → v7.0):
  - BUG-01: Belge tespiti dosya adına bağımlıydı → içerik tabanlı sınıflandırma
  - BUG-02: 'dict' object has no attribute 'upper' → _depo_metin() helper ile önlendi
  - BUG-03: re.search naive digit parser ilk rakamı alıyordu → alan bazlı kilo parser
  - BUG-04: Tek belge hatası tüm analizi durduruyordu → try/except ile izolasyon
  - BUG-05: Belge bulunamazsa "EKSİK" yazılıyordu; dosya var / OCR başarılı / sınıf
            ayrımı yapılmıyordu → 3 kademeli durum raporlaması eklendi

Bağımlılıklar (opsiyonel):
    pypdf, python-docx, openpyxl, Pillow, pytesseract
    hukuk_motoru.py, kurallar.json
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
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("akreditif")

# ---------------------------------------------------------------------------
# Opsiyonel kütüphane yüklemeleri
# ---------------------------------------------------------------------------
try:
    from pypdf import PdfReader
    log.debug("pypdf yüklendi.")
except ImportError:
    PdfReader = None  # type: ignore
    log.warning("pypdf yüklü değil — PDF okuma devre dışı.")

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt
    log.debug("python-docx yüklendi.")
except ImportError:
    docx = None  # type: ignore
    log.warning("python-docx yüklü değil — Word raporu devre dışı.")

try:
    import openpyxl
    log.debug("openpyxl yüklendi.")
except ImportError:
    openpyxl = None  # type: ignore

try:
    from PIL import Image
    import pytesseract
    log.debug("pytesseract + Pillow yüklendi.")
except ImportError:
    pytesseract = None  # type: ignore
    Image = None  # type: ignore
    log.warning("pytesseract / Pillow yüklü değil — OCR devre dışı.")

# ---------------------------------------------------------------------------
# hukuk_motoru entegrasyonu
# ---------------------------------------------------------------------------
try:
    from hukuk_motoru import analiz_et as hukuk_motoru_analiz_et
    HUKUK_MOTORU_AKTIF = True
    log.debug("hukuk_motoru.py yüklendi.")
except ImportError:
    hukuk_motoru_analiz_et = None  # type: ignore
    HUKUK_MOTORU_AKTIF = False
    log.warning("hukuk_motoru.py bulunamadı.")

# ---------------------------------------------------------------------------
# İçerik tabanlı belge sınıflandırma — puanlama tablosu
# BUG-01 FIX: Artık dosya adına değil içeriğe göre sınıflandırılır.
# ---------------------------------------------------------------------------
SINIFLANDIRMA_TABLOSU: dict[str, list[tuple[str, int]]] = {
    "KUSAT": [
        ("DOCUMENTARY CREDIT", 40),
        ("MT700", 40),
        ("MT 700", 40),
        ("IRREVOCABLE", 25),
        (":32B:", 30),
        ("FIELD 46A", 20),
        ("FIELD 45A", 20),
        ("45A:", 20),
        ("46A:", 20),
        ("DATE OF EXPIRY", 15),
        ("APPLICANT", 10),
        ("BENEFICIARY", 10),
        ("DOCUMENTARY", 10),
        ("KÜŞAT", 40),
        ("AKREDİTİF", 25),
    ],
    "FATURA": [
        ("COMMERCIAL INVOICE", 40),
        ("INVOICE NO", 30),
        ("INVOICE NUMBER", 30),
        ("SELLER", 10),
        ("BUYER", 10),
        ("UNIT PRICE", 20),
        ("TOTAL AMOUNT", 15),
        ("TOTAL VALUE", 15),
        ("INVOICE DATE", 15),
        ("INVOICE", 20),
        ("FATURA", 30),
        ("SATICI", 10),
        ("ALICI", 10),
    ],
    "KONSIMENTO": [
        ("BILL OF LADING", 40),
        ("OCEAN BILL OF LADING", 50),
        ("B/L NO", 30),
        ("SHIPPED ON BOARD", 30),
        ("PORT OF LOADING", 20),
        ("PORT OF DISCHARGE", 20),
        ("FREIGHT PREPAID", 15),
        ("CONSIGNEE", 15),
        ("SHIPPER", 10),
        ("KONŞİMENTO", 40),
        ("KONSIMENTO", 40),
    ],
    "CEKI_LISTESI": [
        ("PACKING LIST", 100),      # BUG-05 FIX: yükseltildi, Invoice ile çakışma önlendi
        ("GROSS WEIGHT", 50),
        ("NET WEIGHT", 50),
        ("PALLET", 30),
        ("CBM", 30),
        ("PACKAGE DETAILS", 30),
        ("PACKING DETAILS", 30),
        ("MEASUREMENT", 20),
        ("NUMBER OF PACKAGES", 25),
        ("CARTON", 15),
        ("ÇEKİ LİSTESİ", 100),
        ("CEKI LISTESI", 100),
        ("WEIGHT LIST", 30),
        ("MARKS AND NUMBERS", 20),
    ],
    "SIGORTA": [
        ("INSURANCE POLICY", 40),
        ("INSURANCE CERTIFICATE", 40),
        ("MARINE INSURANCE", 35),
        ("SUM INSURED", 25),
        ("CLAIMS PAYABLE", 20),
        ("COVERAGE", 15),
        ("PREMIUM", 10),
        ("SİGORTA POLİÇESİ", 40),
        ("SİGORTA SERTİFİKASI", 40),
    ],
}

# OCR hata toleransı için fuzzy eşik (0-1)
FUZZY_ESIK = 0.82

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
KIRLI_BL_IFADELERI: list[str] = [
    "CLAUSED", "DAMAGED", "TORN", "WET CARGO",
    "INSUFFICIENT PACKING", "PARTLY DAMAGED",
    "RUSTED", "LEAKING", "STAINED", "BROKEN",
]

BIRIM_NORMALIZASYON: dict[str, str] = {
    "KG": "KG", "KGS": "KG",
    "TON": "TON", "TONS": "TON", "MT": "TON",
    "PCS": "PCS", "PIECES": "PCS", "PIECE": "PCS",
    "CTN": "CTN", "CARTON": "CTN", "CARTONS": "CTN",
    "BOX": "BOX", "BOXES": "BOX",
    "SET": "SET", "SETS": "SET",
    "UNIT": "UNIT", "UNITS": "UNIT",
}

# ---------------------------------------------------------------------------
# Kanıt puanı eşiği — bu değerin altında MAJOR REZERV üretilmez, MANUEL KONTROL yazılır
# ---------------------------------------------------------------------------
KANIT_ESIK_MAJOR = 60   # 0-100 arası; 60 altı = belirsiz kanıt → MAJOR üretme

# ---------------------------------------------------------------------------
# Origin anahtar kelimeleri
# ---------------------------------------------------------------------------
ORIGIN_IFADELERI = [
    "TURKISH ORIGIN", "COUNTRY OF ORIGIN", "GOODS ARE OF", "MADE IN TURKEY",
    "MANUFACTURED IN TURKEY", "PRODUCED IN TURKEY", "ORIGIN: TURKEY",
    "ORIGIN : TURKEY", "OF TURKISH ORIGIN",
]
CERTIFICATE_OF_ORIGIN_IFADELERI = [
    "CERTIFICATE OF ORIGIN", "ORIGIN CERTIFICATE", "CO ISSUED BY",
    "CHAMBER OF COMMERCE", "MENŞE ŞEHADETNAMESİ", "MENŞE BELGESİ",
]

# ---------------------------------------------------------------------------
# 46A Packing List içerik şartları
# ---------------------------------------------------------------------------
PACKING_LIST_BEKLENEN_ALANLAR = [
    "GROSS WEIGHT", "NET WEIGHT", "CBM", "MEASUREMENT",
    "PACKAGE DETAILS", "PALLET", "PACKING DETAILS",
    "MARKS", "NUMBER OF PACKAGES", "CARTON",
]

AY_ISIMLERI: dict[str, int] = {
    "JAN": 1, "JANUARY": 1,    "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,      "APR": 4, "APRIL": 4,
    "MAY": 5,                   "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,       "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPTEMBER": 9,  "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}

RISK_PUANLARI: dict[str, int] = {
    "sigorta_eksik": 30, "tutar_uyusmazligi": 40,
    "yukleme_tarihi_ihlali": 40, "konsimento_eksik": 50,
    "mal_tanimi_uyusmazligi": 35, "mal_tanimi_kritik": 50,
    "kilo_uyusmazligi": 20, "ibraz_suresi_belirsiz": 10,
    "temiz_bl_sorunu": 45, "46a_belge_eksigi": 25, "gec_yukleme": 40,
}

RISK_SINIFLANDIRMASI: list[tuple[int, int, str]] = [
    (0,   20, "DÜŞÜK RİSK"),
    (21,  50, "ORTA RİSK"),
    (51, 999, "YÜKSEK RİSK"),
]

REZERV_KATEGORILERI: dict[str, dict[str, Any]] = {
    "sigorta_eksik":          {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "2-3 Gün"},
    "tutar_uyusmazligi":      {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "1-2 Gün"},
    "yukleme_tarihi_ihlali":  {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "Akreditif değişikliği"},
    "konsimento_eksik":       {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "3-5 Gün"},
    "mal_tanimi_uyusmazligi": {"kategori": "MEDIUM DISCREPANCY", "puan": 10, "sure": "1 Gün"},
    "mal_tanimi_kritik":      {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "1-2 Gün"},
    "kilo_uyusmazligi":       {"kategori": "MEDIUM DISCREPANCY", "puan": 10, "sure": "1 Gün"},
    "ibraz_suresi_belirsiz":  {"kategori": "MINOR DISCREPANCY",  "puan":  5, "sure": "Aynı Gün"},
    "temiz_bl_sorunu":        {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "3-7 Gün"},
    "46a_belge_eksigi":       {"kategori": "MEDIUM DISCREPANCY", "puan": 10, "sure": "1-2 Gün"},
    "gec_yukleme":            {"kategori": "MAJOR DISCREPANCY",  "puan": 25, "sure": "Akreditif değişikliği"},
}

MT700_ALAN_ACIKLAMALARI: dict[str, str] = {
    "20":  "Documentary Credit Number",
    "31C": "Date of Issue",
    "31D": "Date and Place of Expiry",
    "32B": "Currency Code, Amount",
    "39A": "Percentage Credit Amount Tolerance",
    "39B": "Maximum Credit Amount",
    "40A": "Form of Documentary Credit",
    "41A": "Available With",
    "43P": "Partial Shipments",
    "43T": "Transhipment",
    "44C": "Latest Date of Shipment",
    "44E": "Port of Loading",
    "44F": "Port of Discharge",
    "45A": "Description of Goods",
    "46A": "Documents Required",
    "47A": "Additional Conditions",
    "48":  "Period for Presentation (days)",
    "49":  "Confirmation Instructions",
    "71B": "Charges",
    "78":  "Instructions to the Paying Bank",
}

ISBP_ESLESTIRME: dict[str, dict[str, str]] = {
    "Art 14": {
        "prensip":  "ISBP 821 § A1-A7 — Belge İnceleme Prensipleri",
        "aciklama": "Banka belgeleri ibraz tarihinden itibaren en fazla 5 iş günü içinde inceler.",
        "oneri":    "İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır.",
    },
    "Art 18": {
        "prensip":  "ISBP 821 § C1-C23 — Ticari Fatura",
        "aciklama": "Faturadaki mal tanımı akreditifte yer alan ifadeyle birebir uyumlu olmalıdır.",
        "oneri":    "Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin.",
    },
    "Art 20": {
        "prensip":  "ISBP 821 § E1-E30 — Konşimento",
        "aciklama": "'Shipped on Board' şerhi yükleme tarihini açıkça göstermelidir.",
        "oneri":    "Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisini doğrulayın.",
    },
    "Art 27": {
        "prensip":  "ISBP 821 § E26-E27 — Temiz Taşıma Belgesi",
        "aciklama": "Konşimento üzerinde malın durumuna ilişkin olumsuz kayıt bulunmamalıdır.",
        "oneri":    "Konşimentonun taşıyıcı tarafından 'clean' olarak düzenlendiğini teyit edin.",
    },
    "Art 28": {
        "prensip":  "ISBP 821 § K1-K15 — Sigorta Belgesi",
        "aciklama": "Sigorta belgesi en az fatura bedelinin %110'unu teminat altına almalıdır.",
        "oneri":    "Sigorta poliçesinin döviz cinsini, teminat tutarını ve kapsamı akreditifle karşılaştırın.",
    },
    "Art 30": {
        "prensip":  "ISBP 821 § B14 — Miktar ve Tutar Tolerans",
        "aciklama": "'About'/'approximately' varsa %10, yoksa %5 tolerans uygulanır.",
        "oneri":    "Fatura tutarının akreditif tutarıyla %5 sapma sınırı içinde kaldığını doğrulayın.",
    },
}

REZERV_SWIFT_SABLONLARI: dict[str, str] = {
    "sigorta_eksik": (
        "DOCUMENTS REJECTED.\n\nINSURANCE DOCUMENT AS REQUIRED BY FIELD 46A\n"
        "OF THE CREDIT HAS NOT BEEN PRESENTED.\nUCP 600 ARTICLE 28."
    ),
    "tutar_uyusmazligi": (
        "DOCUMENTS REJECTED.\n\nINVOICE AMOUNT EXCEEDS THE CREDIT AMOUNT.\n"
        "UCP 600 ARTICLE 18 / ARTICLE 30."
    ),
    "kilo_uyusmazligi": (
        "DOCUMENTS REJECTED.\n\nGROSS WEIGHT AS SHOWN ON COMMERCIAL INVOICE\n"
        "DOES NOT CORRESPOND WITH THAT SHOWN ON BILL OF LADING.\n"
        "UCP 600 ARTICLE 14 / ISBP 821 § C10."
    ),
    "mal_tanimi_kritik": (
        "DOCUMENTS REJECTED.\n\nDESCRIPTION OF GOODS ON COMMERCIAL INVOICE\n"
        "DOES NOT CORRESPOND WITH THAT STATED IN THE CREDIT.\n"
        "UCP 600 ARTICLE 18(C) / ISBP 821 § C5."
    ),
    "konsimento_eksik": (
        "DOCUMENTS REJECTED.\n\nFULL SET OF ORIGINAL BILLS OF LADING\n"
        "AS REQUIRED BY THE CREDIT HAS NOT BEEN PRESENTED.\nUCP 600 ARTICLE 20."
    ),
    "gec_yukleme": (
        "DOCUMENTS REJECTED.\n\nSHIPMENT DATE AS EVIDENCED BY BILL OF LADING\n"
        "IS LATER THAN THE LATEST DATE OF SHIPMENT STIPULATED IN FIELD 44C.\n"
        "UCP 600 ARTICLE 14(C) / ARTICLE 20."
    ),
    "temiz_bl_sorunu": (
        "DOCUMENTS REJECTED.\n\nBILL OF LADING BEARS CLAUSE(S) OR NOTATION(S)\n"
        "ADVERSELY COMMENTING ON THE CONDITION OF THE GOODS.\n"
        "UCP 600 ARTICLE 27 / ISBP 821 § E26."
    ),
    "46a_belge_eksigi": (
        "DOCUMENTS REJECTED.\n\nONE OR MORE DOCUMENTS AS REQUIRED BY FIELD 46A\n"
        "OF THE CREDIT HAVE NOT BEEN PRESENTED.\nUCP 600 ARTICLE 14(A) / ARTICLE 16."
    ),
}


# ===========================================================================
# İçerik Tabanlı Belge Sınıflandırıcı
# ===========================================================================
class BelgeSiniflandirici:
    """
    Dosya adından bağımsız, OCR/metin içeriğinden belge türü belirler.
    Puanlama tablosu ile çalışır; fuzzy matching OCR hatalarını tolere eder.
    """

    def __init__(self, fuzzy_esik: float = FUZZY_ESIK) -> None:
        self.fuzzy_esik = fuzzy_esik

    def _fuzzy_icerir_mi(self, metin: str, aranacak: str) -> bool:
        """
        Metinde aranacak ifadenin fuzzy karşılığını arar.
        OCR hataları: INVOICE→INV0ICE, BILL→BlLL, INSURANCE→INSURANCF vb.
        """
        aranacak_u = aranacak.upper()
        # Önce hızlı tam eşleşme
        if aranacak_u in metin:
            return True
        # Pencere boyutu = ifade uzunluğu + %20 tolerans
        pencere = len(aranacak_u)
        if pencere < 4:
            return False
        for i in range(len(metin) - pencere + 1):
            dilim = metin[i:i + pencere]
            oran  = SequenceMatcher(None, aranacak_u, dilim).ratio()
            if oran >= self.fuzzy_esik:
                return True
        return False

    # KUSAT belgesi için veto eşiği — bu puana ulaşırsa diğer sınıflar baskılanır
    KUSAT_VETO_ESIGI = 80

    def siniflandir(self, metin: str) -> tuple[str, int, dict[str, int]]:
        """
        Metni sınıflandırır.

        Döner
        -----
        (belge_turu, en_yuksek_puan, {tur: puan}) — tüm puanlar için

        Özel kural — KUSAT veto:
        Küşat belgesi içinde 46A satırlarında pek çok belge türünün anahtar
        kelimeleri (PACKING LIST, GROSS WEIGHT vb.) geçebilir. KUSAT puanı
        KUSAT_VETO_ESIGI değerini aşarsa, diğer sınıfların puanları yarıya
        indirilir ve KUSAT kazanır.
        """
        if not metin:
            return ("DIGER", 0, {})

        metin_u = metin.upper()
        puanlar: dict[str, int] = {}

        for tur, anahtar_listesi in SINIFLANDIRMA_TABLOSU.items():
            toplam = 0
            for anahtar, puan in anahtar_listesi:
                if len(anahtar) >= 6:
                    if self._fuzzy_icerir_mi(metin_u, anahtar):
                        toplam += puan
                        log.debug("  Eşleşme [%s]: '%s' (+%d)", tur, anahtar, puan)
                else:
                    if anahtar in metin_u:
                        toplam += puan
            puanlar[tur] = toplam

        # KUSAT veto: küşat puanı yüksekse diğerlerini baskıla
        if puanlar.get("KUSAT", 0) >= self.KUSAT_VETO_ESIGI:
            for tur in puanlar:
                if tur != "KUSAT":
                    puanlar[tur] = puanlar[tur] // 2
            log.debug("  KUSAT veto uygulandı (KUSAT=%d)", puanlar["KUSAT"])

        en_iyi_tur  = max(puanlar, key=lambda k: puanlar[k])
        en_iyi_puan = puanlar[en_iyi_tur]

        if en_iyi_puan < 20:
            return ("DIGER", en_iyi_puan, puanlar)

        return (en_iyi_tur, en_iyi_puan, puanlar)


# ===========================================================================
# Ana Sınıf
# ===========================================================================
class YapayZekaDisTicaretDenetleyici:
    """UCP 600 / ISBP 821 uyumlu profesyonel akreditif belge denetleme motoru v7.0"""

    def __init__(self, ana_dizin: str = "DisTicaretRepo") -> None:
        self.base_dir        = ana_dizin
        self.yuklenenler_dir = os.path.join(self.base_dir, "YuklenenDosyalar")
        self.raporlar_dir    = os.path.join(self.base_dir, "Raporlar")

        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir,    exist_ok=True)

        self.siniflandirici = BelgeSiniflandirici()

        self.depo:             dict[str, Any] = self._bos_depo()
        self.analiz_verisi:    dict[str, Any] = {}
        self.risk_puani:       int            = 0
        self.uyumluluk_puani:  int            = 100
        self.mt700_alanlari:   dict[str, str] = {}

        self._aktif_rezerv_kategorileri: list[str] = []
        self._banka_kabul_olasiligi:     int        = 100

        # BUG-05 FIX: 3 kademeli belge durum takibi
        # Her dosya için: {"dosya": str, "ocr": bool, "sinif": str | None, "puan": int}
        self._dosya_durum_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Depo yardımcıları
    # ------------------------------------------------------------------
    @staticmethod
    def _bos_depo() -> dict[str, Any]:
        return {
            "KUSAT":          None,
            "FATURA":         None,
            "KONSIMENTO":     None,
            "CEKI_LISTESI":   None,
            "SIGORTA":        None,
            "DIGER_BELGELER": [],
        }

    def _depo_metin(self, anahtar: str) -> str:
        """
        BUG-02 FIX: depo[anahtar] dict veya None olabilir.
        .upper() doğrudan dict üzerinde çağrılmaz; metin alanı çıkarılır.
        """
        kayit = self.depo.get(anahtar)
        if not kayit or not isinstance(kayit, dict):
            return ""
        metin = kayit.get("metin")
        return metin if isinstance(metin, str) else ""

    # ------------------------------------------------------------------
    # Metin ayıklama
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu: str) -> tuple[str, bool]:
        """
        Dosyadan metin çıkarır.
        Döner: (metin, ocr_basarili_mi)
        ocr_basarili_mi=False → metin boş veya hata mesajı
        """
        if not dosya_yolu or not os.path.isfile(dosya_yolu):
            return ("", False)

        ext   = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""

        try:
            if ext == ".pdf":
                if PdfReader is None:
                    return ("[Hata: pypdf yüklü değil]", False)
                reader = PdfReader(dosya_yolu)
                for i, sayfa in enumerate(reader.pages):
                    try:
                        txt = sayfa.extract_text()
                        if txt:
                            metin += txt + "\n"
                    except Exception as e:
                        metin += f"[Sayfa {i+1} okuma hatası: {e}]\n"

            elif ext in [".docx", ".doc"]:
                if docx is None:
                    return ("[Hata: python-docx yüklü değil]", False)
                d = docx.Document(dosya_yolu)
                for p in d.paragraphs:
                    if p.text:
                        metin += p.text + "\n"
                for table in d.tables:
                    for row in table.rows:
                        hucre = " ".join(c.text for c in row.cells if c.text)
                        if hucre.strip():
                            metin += hucre + "\n"

            elif ext in [".xlsx", ".xls"]:
                if openpyxl is None:
                    return ("[Hata: openpyxl yüklü değil]", False)
                wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
                for s in wb.sheetnames:
                    ws = wb[s]
                    for r in ws.iter_rows(values_only=True):
                        satir = " ".join(str(c) for c in r if c is not None)
                        if satir.strip():
                            metin += satir + "\n"

            elif ext in [".png", ".jpg", ".jpeg"]:
                if pytesseract is None or Image is None:
                    return ("[Hata: pytesseract / Pillow yüklü değil]", False)
                img = Image.open(dosya_yolu)
                try:
                    metin = pytesseract.image_to_string(img, lang="eng+tur") or ""
                except Exception:
                    try:
                        metin = pytesseract.image_to_string(img, lang="eng") or ""
                        log.warning("%s: Türkçe dil paketi yok, yalnızca 'eng' kullanıldı.",
                                    os.path.basename(dosya_yolu))
                    except Exception as e2:
                        return (f"[OCR Hatası: {e2}]", False)

            elif ext == ".txt":
                with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
                    metin = f.read()
            else:
                return (f"[Desteklenmeyen format: {ext}]", False)

        except Exception as e:
            log.error("Dosya okuma hatası [%s]: %s", dosya_yolu, e)
            return (f"[Dosya okuma hatası: {e}]", False)

        metin = (metin
                 .replace("\xa0", " ")
                 .replace("\u200b", "")
                 .replace("\r\n", "\n"))

        ocr_basarili = bool(metin.strip()) and not metin.startswith("[")
        return (metin, ocr_basarili)

    # ------------------------------------------------------------------
    # MT700 ayrıştırıcı
    # ------------------------------------------------------------------
    def mt700_ayristir(self, metin: str) -> dict[str, str]:
        if not metin:
            return {}

        hedef_alanlar = [
            "20", "31C", "31D", "32B", "39A", "40A",
            "43P", "43T", "44C", "44E", "44F",
            "45A", "46A", "47A", "48", "49", "71B", "78",
        ]
        cok_satirli = {"45A", "46A", "47A"}
        sonuc: dict[str, str] = {}
        sonraki = r'(?=(?:\n[ \t]*:?\d{2,3}[A-Z]{0,2}[:\s]|\Z))'

        for alan in hedef_alanlar:
            desenler = [
                rf':{re.escape(alan)}:\s*(.+?){sonraki}',
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[ \t]+(.+?){sonraki}',
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[ \t]*\n(.+?){sonraki}',
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[:\-]?[ \t]*(.+?){sonraki}',
            ]
            if alan == "46A":
                desenler.insert(0,
                    r'(?:DOCUMENTS?\s+REQUIRED|REQUIRED\s+DOCUMENTS?)[:\s]*\n(.+?)' + sonraki)
            if alan == "45A":
                desenler.insert(0,
                    r'(?:DESCRIPTION\s+OF\s+GOODS?|GOODS?\s+DESCRIPTION)[:\s]*\n(.+?)' + sonraki)
                desenler.insert(1,
                    r'(?:DESCRIPTION\s+OF\s+GOODS?|GOODS?\s+DESCRIPTION)[:\s]+(.+?)' + sonraki)

            for desen in desenler:
                try:
                    m = re.search(desen, metin, re.DOTALL | re.MULTILINE | re.IGNORECASE)
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
                            log.debug("MT700 alan %s tespit edildi: %s…", alan, deger[:40])
                            break
                except re.error:
                    continue

        # 44C fallback
        if "44C" not in sonuc:
            m2 = re.search(
                r'(?:LATEST\s+(?:DATE\s+(?:OF\s+)?)?SHIPMENT|SON\s+Y[UÜ]KLEME)'
                r'[:\s]*([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'
                r'|[\d]{1,2}\s+[A-Za-z]{3,9}\s+[\d]{4}'
                r'|[\d]{4}-[\d]{2}-[\d]{2})',
                metin, re.IGNORECASE
            )
            if m2:
                sonuc["44C"] = m2.group(1).strip()

        return sonuc

    # ------------------------------------------------------------------
    # Depo tarama — BUG-01 FIX (içerik tabanlı sınıflandırma)
    # ------------------------------------------------------------------
    def depoyu_tara_ve_analiz_et(self) -> bool:
        self.depo                 = self._bos_depo()
        self.risk_puani           = 0
        self.uyumluluk_puani      = 100
        self.mt700_alanlari       = {}
        self._dosya_durum_log     = []
        self._aktif_rezerv_kategorileri = []
        self._banka_kabul_olasiligi     = 100

        if not os.path.exists(self.yuklenenler_dir):
            log.warning("YuklenenDosyalar dizini bulunamadı: %s", self.yuklenenler_dir)
            return False

        dosyalar = [
            os.path.join(self.yuklenenler_dir, f)
            for f in os.listdir(self.yuklenenler_dir)
            if os.path.isfile(os.path.join(self.yuklenenler_dir, f))
        ]
        if not dosyalar:
            log.info("YuklenenDosyalar dizini boş.")
            return False

        for d_yolu in dosyalar:
            dosya_adi = os.path.basename(d_yolu)
            log.debug("[DEBUG] Dosya bulundu: %s", dosya_adi)

            durum_kaydi: dict[str, Any] = {
                "dosya":        dosya_adi,
                "dosya_bulundu": True,
                "ocr_basarili": False,
                "sinif":        None,
                "puan":         0,
                "puanlar":      {},
            }

            # ── Adım 1: Metin çıkar (OCR / parse)
            metin, ocr_ok = self.metin_ayikla(d_yolu)
            durum_kaydi["ocr_basarili"] = ocr_ok

            if not ocr_ok:
                log.warning("[UYARI] %s — OCR/parse başarısız: %s", dosya_adi, metin[:80])
                durum_kaydi["sinif"]  = None
                durum_kaydi["hata"]   = metin[:200]
                self._dosya_durum_log.append(durum_kaydi)
                continue

            log.debug("[DEBUG] OCR tamamlandı: %s (%d karakter)", dosya_adi, len(metin))

            # ── Adım 2: İçerik tabanlı sınıflandırma (BUG-01 FIX)
            tur, puan, puanlar = self.siniflandirici.siniflandir(metin)
            durum_kaydi["sinif"]   = tur
            durum_kaydi["puan"]    = puan
            durum_kaydi["puanlar"] = puanlar

            log.debug("[DEBUG] Belge tipi = %s (puan: %d) — %s", tur, puan, dosya_adi)

            # ── Adım 3: Depoya yerleştir
            if tur in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]:
                if self.depo[tur] is None:
                    self.depo[tur] = {"ad": dosya_adi, "metin": metin, "sinif_puan": puan}
                    log.debug("  → Depo[%s] = %s", tur, dosya_adi)
                else:
                    # Aynı türde birden fazla dosya varsa yüksek puanlı ana depoya girer;
                    # düşük puanlı yedek olarak DIGER_BELGELER'e eklenir (içerik kaybolmaz)
                    mevcut_puan = self.depo[tur].get("sinif_puan", 0)
                    if puan > mevcut_puan:
                        log.debug("  → Depo[%s] üzerine yazıldı: %s (puan %d > %d)",
                                  tur, dosya_adi, puan, mevcut_puan)
                        # Eski kaydı yedekle
                        self.depo["DIGER_BELGELER"].append(self.depo[tur])
                        self.depo[tur] = {"ad": dosya_adi, "metin": metin, "sinif_puan": puan}
                    else:
                        log.debug("  → Depo[%s] korundu (mevcut puan %d ≥ %d)",
                                  tur, mevcut_puan, puan)
                        # Düşük puanlı ikinci belgeyi yedekle — içerik kaybolmasın
                        self.depo["DIGER_BELGELER"].append(
                            {"ad": dosya_adi, "metin": metin, "sinif_puan": puan, "sinif_yedek": tur}
                        )
            else:
                self.depo["DIGER_BELGELER"].append(
                    {"ad": dosya_adi, "metin": metin, "sinif_puan": puan}
                )
                log.debug("  → DIGER_BELGELER: %s", dosya_adi)

            self._dosya_durum_log.append(durum_kaydi)

        # MT700 ayrıştır
        kusat_metni = self._depo_metin("KUSAT")
        if kusat_metni:
            self.mt700_alanlari = self.mt700_ayristir(kusat_metni)
            log.debug("[DEBUG] MT700 alanları çıkarıldı: %s", list(self.mt700_alanlari.keys()))

        return True

    # ------------------------------------------------------------------
    # Sayısal yardımcılar
    # ------------------------------------------------------------------
    def kilo_bul(self, metin: str) -> Optional[float]:
        """BUG-03 FIX: Alan bazli kilo parser -- naive r"(digit+)" kullanilmaz."""
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

    # ------------------------------------------------------------------
    # BUG-01 FIX: Tutar normalleştirme
    # 23,940 / 23.940 / 23,940.00 / 23.940,00 / USD 23,940 → 23940.0
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_tutar(metin: str) -> Optional[float]:
        """
        Fatura veya LC'den gelen herhangi bir tutar string'ini float'a çevirir.

        Desteklenen formatlar:
          23940        → 23940.0
          23,940       → 23940.0  (binlik virgül, Anglo)
          23.940       → 23940.0  (binlik nokta, Avrupa)
          23,940.00    → 23940.0
          23.940,00    → 23940.0
          USD 23,940   → 23940.0
        """
        if not metin:
            return None
        s = re.sub(r'[A-Za-z$€£ \t]', '', str(metin)).strip()
        if not s:
            return None
        try:
            virgul_say = s.count(',')
            nokta_say  = s.count('.')

            if virgul_say == 0 and nokta_say == 0:
                # Saf rakam: 23940
                return float(s)

            son_virgul = s.rfind(',')
            son_nokta  = s.rfind('.')

            if virgul_say == 1 and nokta_say == 0:
                # 23,940 veya 23,94 — virgülden sonra kaç karakter?
                ondalik_kisim = s[son_virgul+1:]
                if len(ondalik_kisim) == 3:
                    # binlik ayraç: 23,940 → 23940
                    s = s.replace(',', '')
                else:
                    # ondalık: 23,94 → 23.94
                    s = s.replace(',', '.')

            elif nokta_say == 1 and virgul_say == 0:
                # 23.940 veya 23.94
                ondalik_kisim = s[son_nokta+1:]
                if len(ondalik_kisim) == 3:
                    # binlik ayraç: 23.940 → 23940
                    s = s.replace('.', '')
                # else: gerçek ondalık → bırak

            elif son_virgul > son_nokta:
                # Avrupa: 23.940,00
                s = s.replace('.', '').replace(',', '.')

            else:
                # Anglo: 23,940.00
                s = s.replace(',', '')

            return float(s) if s else None
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # BUG-01 FIX: CIF fatura ayrıştırıcı
    # Goods Value / Freight / Insurance / TOTAL CIF VALUE ayrı çıkarılır
    # LC karşılaştırması cif_total ile yapılır, goods_value ile DEĞİL
    # ------------------------------------------------------------------
    def invoice_tutarlari_ayristir(self, metin: str) -> dict[str, Optional[float]]:
        """
        Faturadaki ayrıntılı tutar bileşenlerini çıkarır.

        Döner:
        {
          "goods_value": float | None,
          "freight":     float | None,
          "insurance":   float | None,
          "cif_total":   float | None,   # LC ile karşılaştırılacak değer bu
          "invoice_total": float | None, # TOTAL AMOUNT / INVOICE VALUE
        }
        LC karşılaştırmasında öncelik sırası:
          cif_total > invoice_total > goods_value
        """
        if not metin:
            return {"goods_value": None, "freight": None,
                    "insurance": None, "cif_total": None, "invoice_total": None}

        def _bul(desenler: list[str]) -> Optional[float]:
            for d in desenler:
                m = re.search(d, metin, re.IGNORECASE)
                if m:
                    v = self.normalize_tutar(m.group(1))
                    if v is not None:
                        return v
            return None

        goods = _bul([
            r'(?:GOODS?\s+VALUE|CARGO\s+VALUE|FOB\s+VALUE|FOB\s+AMOUNT)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:FOB)[:\s]+([\d,\.]+)',
        ])
        freight = _bul([
            r'(?:FREIGHT|OCEAN\s+FREIGHT|SEA\s+FREIGHT)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        ])
        insurance_amt = _bul([
            r'(?:INSURANCE\s+PREMIUM|INSURANCE\s+AMOUNT|INS\.?)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        ])
        cif_total = _bul([
            r'(?:TOTAL\s+CIF\s+(?:VALUE|AMOUNT)|CIF\s+(?:TOTAL|VALUE|AMOUNT)'
            r'|CIF\s+PRICE\s+TOTAL|TOTAL\s+CIF)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:C\.I\.F\.?\s+(?:TOTAL|VALUE|AMOUNT))'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
        ])
        invoice_total = _bul([
            r'(?:TOTAL\s+INVOICE\s+(?:VALUE|AMOUNT)|INVOICE\s+(?:TOTAL|AMOUNT|VALUE)'
            r'|TOTAL\s+AMOUNT\s+DUE|AMOUNT\s+DUE|GRAND\s+TOTAL|TOTAL\s+VALUE)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
            r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)(?=\s*$)',
        ])

        # CIF toplam yoksa ama bileşenler varsa hesapla
        if cif_total is None and goods is not None:
            computed = goods + (freight or 0) + (insurance_amt or 0)
            if computed > goods:
                cif_total = computed
                log.debug("CIF toplam hesaplandı: %.2f + %.2f + %.2f = %.2f",
                          goods, freight or 0, insurance_amt or 0, computed)

        return {
            "goods_value":   goods,
            "freight":       freight,
            "insurance":     insurance_amt,
            "cif_total":     cif_total,
            "invoice_total": invoice_total,
        }

    def lc_karsilastirma_tutari(self, fatura_tutarlari: dict) -> Optional[float]:
        """
        LC ile karşılaştırılacak doğru fatura tutarını seçer.
        Öncelik: cif_total > invoice_total > goods_value
        Bu sayede Goods Value (21,600) ile CIF Total (23,940) karışmaz.
        """
        return (fatura_tutarlari.get("cif_total") or
                fatura_tutarlari.get("invoice_total") or
                fatura_tutarlari.get("goods_value"))

    # ------------------------------------------------------------------
    # BUG-02 FIX: Gelişmiş B/L tarih parser
    # ------------------------------------------------------------------
    def bl_tarihi_bul(self, konsimento_text: str) -> Optional[str]:
        """
        Konşimentodaki yükleme tarihini çıkarır.
        Desteklenen önekler: SHIPPED ON BOARD, ON BOARD DATE, DATE OF SHIPMENT,
        LOADED ON BOARD, VESSEL LOADED, SHIPPED, ON BOARD
        Desteklenen tarih formatları: DD.MM.YYYY / DD/MM/YYYY / YYYY-MM-DD /
        DD MON YYYY / DD MONTH YYYY / DD-MON-YYYY
        """
        if not konsimento_text:
            return None

        tarih_grup = (
            r'([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'        # 20.06.2026
            r'|[\d]{4}-[\d]{2}-[\d]{2}'                       # 2026-06-20
            r'|[\d]{1,2}[-\s][A-Z]{3,9}[-\s][\d]{4}'        # 20-JUN-2026 / 20 JUN 2026
            r'|[\d]{1,2}\s+[A-Z][a-z]{2,8}\s+[\d]{4})'      # 20 June 2026
        )

        desenler = [
            rf'SHIPPED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{tarih_grup}',
            rf'ON\s+BOARD\s+DATE\s*[:\-]?\s*{tarih_grup}',
            rf'DATE\s+OF\s+SHIPMENT\s*[:\-]?\s*{tarih_grup}',
            rf'LOADED\s+ON\s+BOARD\s*(?:DATE\s*[:\-]?)?\s*{tarih_grup}',
            rf'VESSEL\s+LOADED\s*[:\-]?\s*{tarih_grup}',
            # "SHIPPED ON BOARD\n20 JUN 2026" — sonraki satırda tarih
            rf'SHIPPED\s+ON\s+BOARD\s*\n\s*{tarih_grup}',
            rf'ON\s+BOARD\s*\n\s*{tarih_grup}',
            # Fallback: ON BOARD tek başına
            rf'ON\s+BOARD\s*[:\-]?\s*{tarih_grup}',
        ]

        for desen in desenler:
            try:
                m = re.search(desen, konsimento_text, re.IGNORECASE | re.MULTILINE)
                if m:
                    tarih_str = m.group(1).strip()
                    log.debug("B/L tarihi tespit edildi: '%s'", tarih_str)
                    return tarih_str
            except re.error:
                continue
        return None

    # ------------------------------------------------------------------
    # Origin (menşe) analizi
    # ------------------------------------------------------------------
    def origin_analizi_yap(
        self,
        kusat_text: str,
        fatura_text: str,
        depo: dict,
    ) -> dict[str, Any]:
        """
        Belgelerdeki menşe (origin) bilgisini analiz eder.
        Certificate of Origin belgesi ile Invoice origin declaration arasındaki
        hukuki farkı ayırt eder — ikincisi birincinin yerine geçmez.

        Döner: {"durum": str, "detay": str, "rezerv_gerekli": bool}
        """
        lc_co_istiyor = any(
            k in kusat_text.upper()
            for k in ["CERTIFICATE OF ORIGIN", "ORIGIN CERTIFICATE", "CO REQUIRED"]
        )

        # Tüm depo metinlerini güvenli şekilde birleştir
        tum_metin = " ".join(
            self._depo_metin(k)
            for k in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]
        ).upper()
        for d in (depo.get("DIGER_BELGELER") or []):
            if isinstance(d, dict):
                tum_metin += " " + d.get("metin", "").upper()

        co_belgesi_var = any(k in tum_metin for k in CERTIFICATE_OF_ORIGIN_IFADELERI)

        # Invoice'da menşe beyanı var mı?
        invoice_origin_beyan = any(
            k in fatura_text.upper() for k in ORIGIN_IFADELERI
        ) if fatura_text else False

        if not lc_co_istiyor:
            return {
                "durum":           "BİLGİ",
                "detay":           "LC'de Certificate of Origin şartı tespit edilmedi.",
                "rezerv_gerekli":  False,
            }

        if co_belgesi_var:
            return {
                "durum":          "UYUMLU",
                "detay":          "Certificate of Origin belgesi mevcut ve LC şartını karşılıyor.",
                "rezerv_gerekli": False,
            }

        if invoice_origin_beyan and not co_belgesi_var:
            return {
                "durum":          "UYARI",
                "detay":          (
                    "Invoice'da menşe beyanı ('goods are of Turkish origin') mevcut, "
                    "ancak bu ifade Certificate of Origin belgesi yerine GEÇMEZ. "
                    "LC şartını karşılamak için ayrı CO belgesi ibraz edilmesi gerekir."
                ),
                "rezerv_gerekli": True,   # MAJOR DISCREPANCY
            }

        return {
            "durum":          "MAJOR DISCREPANCY",
            "detay":          "LC Certificate of Origin istiyor ancak hiçbir kanıt bulunamadı.",
            "rezerv_gerekli": True,
        }

    # ------------------------------------------------------------------
    # 46A Packing List içerik şart kontrolü
    # ------------------------------------------------------------------
    def packing_list_icerik_kontrol(self, ceki_text: str) -> dict[str, Any]:
        """
        46A'da talep edilen Packing List alanlarının (gross weight, net weight,
        CBM, measurement vb.) belgede mevcut olup olmadığını kontrol eder.
        """
        if not ceki_text:
            return {"durum": "EKSİK", "bulunan": [], "eksik": PACKING_LIST_BEKLENEN_ALANLAR}
        metin_u = ceki_text.upper()
        bulunan = [alan for alan in PACKING_LIST_BEKLENEN_ALANLAR if alan in metin_u]
        eksik   = [alan for alan in PACKING_LIST_BEKLENEN_ALANLAR if alan not in metin_u]
        # En az 3 alan bulunursa uyumlu say
        if len(bulunan) >= 3:
            durum = "UYUMLU"
        elif len(bulunan) >= 1:
            durum = "KISMİ UYUM - MANUEL KONTROL"
        else:
            durum = "EKSİK ALAN"
        return {"durum": durum, "bulunan": bulunan, "eksik": eksik}

    # ------------------------------------------------------------------
    # Kanıt puanı hesaplama — yanlış rezerv filtresi
    # ------------------------------------------------------------------
    @staticmethod
    def kanit_puani(
        dosya_mevcut: bool,
        ocr_basarili: bool,
        sinif_belirlendi: bool,
        alan_bulundu: bool = True,
    ) -> int:
        """
        Rezerv üretmeden önce kanıt gücünü ölçer.
        100 = kesin kanıt | 0 = hiç kanıt yok
        KANIT_ESIK_MAJOR (60) altında MAJOR REZERV üretilmez.
        """
        if not dosya_mevcut:
            return 100  # Dosya gerçekten yok → tam kanıt
        if not ocr_basarili:
            return 30   # Dosya var ama okunamadı → belirsiz
        if not sinif_belirlendi:
            return 15   # OCR tamam ama sınıf belli değil → çok belirsiz
        if not alan_bulundu:
            return 20   # Sınıf tamam ama alan bulunamadı → belirsiz
        return 100      # Her şey tamam, alan da var → tam kanıt

    def para_tutari_bul(self, metin: str) -> Optional[float]:
        if not metin:
            return None
        desenler = [
            r'32B[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            r'(?:TOTAL\s+AMOUNT|INVOICE\s+(?:VALUE|AMOUNT)|TOTAL\s+VALUE|AMOUNT\s+DUE)'
            r'\s*[:\-]?\s*(?:[A-Z]{3})?\s*([\d,\.]+)',
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
            ay = AY_ISIMLERI.get(m.group(2).upper()[:9])
            if ay:
                try:
                    return datetime(int(m.group(3)), ay, int(m.group(1)))
                except ValueError:
                    pass
        return None

    def tarih_bul(self, metin: str, desenler: list[str]) -> Optional[str]:
        if not metin:
            return None
        for desen in desenler:
            try:
                m = re.search(desen, metin, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            except re.error:
                continue
        return None

    def mal_tanimi_bul(self, metin: str) -> Optional[str]:
        if not metin:
            return None
        if "45A" in self.mt700_alanlari:
            ham = self.mt700_alanlari["45A"].split("\n")[0].strip()
            if ham:
                return re.sub(r'\s+', ' ', ham)[:200]
        desenler = [
            r'45A[:\s]+(.+?)(?:\n[4-9]\d[A-Z]|\Z)',
            r'(?:DESCRIPTION\s+OF\s+GOODS?|GOODS?\s+DESCRIPTION)[:\s]+(.+?)(?:\n|$)',
        ]
        for desen in desenler:
            try:
                m = re.search(desen, metin, re.IGNORECASE | re.DOTALL)
                if m:
                    ham = m.group(1).split("\n")[0].strip()
                    return re.sub(r'\s+', ' ', ham)[:200]
            except re.error:
                continue
        return None

    @staticmethod
    def _metin_normalize(metin: str) -> str:
        if not metin:
            return ""
        metin = metin.upper()
        metin = re.sub(r'[^\w\s]', ' ', metin)
        return re.sub(r'\s+', ' ', metin).strip()

    def mal_tanimi_benzerlik(self, kaynak: str, hedef: str) -> float:
        n_k = self._metin_normalize(kaynak)
        n_h = self._metin_normalize(hedef)
        k_w = set(w for w in n_k.split() if len(w) >= 4)
        h_w = set(w for w in n_h.split() if len(w) >= 4)
        if not k_w:
            return 0.0
        return len(k_w & h_w) / len(k_w)

    # ------------------------------------------------------------------
    # Risk puanı yönetimi
    # ------------------------------------------------------------------
    def _risk_puani_ekle(self, kategori: str) -> None:
        bilgi = REZERV_KATEGORILERI.get(kategori)
        if bilgi:
            self.risk_puani += bilgi["puan"]
            kat = bilgi["kategori"]
            if "MAJOR" in kat:
                self._banka_kabul_olasiligi = max(0, self._banka_kabul_olasiligi - 25)
            elif "MEDIUM" in kat:
                self._banka_kabul_olasiligi = max(0, self._banka_kabul_olasiligi - 10)
            else:
                self._banka_kabul_olasiligi = max(0, self._banka_kabul_olasiligi - 5)
        else:
            self.risk_puani += RISK_PUANLARI.get(kategori, 0)
        if kategori not in self._aktif_rezerv_kategorileri:
            self._aktif_rezerv_kategorileri.append(kategori)

    def _uyumluluk_duş(self, miktar: int) -> None:
        self.uyumluluk_puani = max(0, self.uyumluluk_puani - miktar)

    def _risk_sinifi(self) -> str:
        for alt, ust, sinif in RISK_SINIFLANDIRMASI:
            if alt <= self.risk_puani <= ust:
                return sinif
        return "YÜKSEK RİSK"

    # ------------------------------------------------------------------
    # UCP 600 Kural Motoru
    # ------------------------------------------------------------------
    def ucp600_kural_motoru(self) -> None:
        log.debug("[DEBUG] Çapraz kontrol başladı.")

        kusat_text      = self._depo_metin("KUSAT")
        fatura_text     = self._depo_metin("FATURA")
        konsimento_text = self._depo_metin("KONSIMENTO")
        ceki_text       = self._depo_metin("CEKI_LISTESI")
        sigorta_text    = self._depo_metin("SIGORTA")

        combined = (kusat_text + " " + fatura_text + " " +
                    konsimento_text + " " + sigorta_text).upper()

        sonuclar: dict[str, Any] = {
            "vade_analizi":           [],
            "finansal_durum":         [],
            "incoterms":              [],
            "capraz_kontrol":         [],
            "zorunlu_alanlar":        [],
            "ucp_tablosu":            [],
            "risk_ozeti":             [],
            "rezerv_ozeti":           [],
            "belge_46a":              [],
            "isbp_tablosu":           [],
            "uzman_onerileri":        [],
            "eksik_belgeler":         [],
            "mt700_alan_analizi":     [],
            "tarih_zinciri":          [],
            "rezerv_swift_metinleri": [],
            "yonetici_ozeti":         {},
            "rezerv_detay_listesi":   [],
            # BUG-05 FIX: dosya durum raporu
            "dosya_durum_raporu":     self._dosya_durum_log,
        }

        # ── 1. Vade Analizi ──────────────────────────────────────────────
        lc_44c_str = self.mt700_alanlari.get("44C") or self.tarih_bul(kusat_text, [
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{2}[.\-/][\d]{2}[.\-/][\d]{4})',
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
        ])
        sonuclar["vade_analizi"].append(
            f"En Geç Yükleme Tarihi (44C): **{lc_44c_str}**" if lc_44c_str
            else "En Geç Yükleme Tarihi (44C): Belgeden tespit edilemedi — manuel kontrol."
        )

        ibraz = re.search(r'(\d+)\s*DAYS?\s*(?:AFTER|FOR\s+PRESENTATION)', combined, re.IGNORECASE)
        if ibraz:
            gun = int(ibraz.group(1))
            sonuclar["vade_analizi"].append(
                f"İbraz Süresi: **{gun} gün** (UCP Art 14c — max 21 gün)"
            )
            if gun > 21:
                self._risk_puani_ekle("ibraz_suresi_belirsiz")
                self._uyumluluk_duş(10)
        else:
            sonuclar["vade_analizi"].append(
                "İbraz Süresi: Tespit edilemedi — UCP Art 14c varsayılan 21 gün uygulanır."
            )
            self._risk_puani_ekle("ibraz_suresi_belirsiz")
            self._uyumluluk_duş(5)

        # ── 2. Ödeme Vadesi ──────────────────────────────────────────────
        if any(x in combined for x in ["AT SIGHT", "SIGHT PAYMENT", "GÖRÜLDÜĞÜNDE"]):
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: **At Sight** — Uyumlu ibrazda anında ödeme (UCP Art 15b)."
            )
        elif any(x in combined for x in ["DAYS AFTER", "DEFERRED PAYMENT", "VADELİ"]):
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: **Vadeli/Kabul Kredili** — Poliçe vade takvimini kontrol edin."
            )
        else:
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: Tespit edilemedi — manuel kontrol önerilir."
            )

        # ── 3. Incoterms & Sigorta (Art 28) ──────────────────────────────
        incoterm_var: Optional[str] = None
        for term in ["EXW","FCA","CPT","CIP","DAP","DPU","DDP","FAS","FOB","CFR","CIF"]:
            if term in combined:
                incoterm_var = term
                sonuclar["incoterms"].append(f"Incoterms: **{term} (ICC 2020)**")
                break
        if not incoterm_var:
            sonuclar["incoterms"].append("Incoterms: Tespit edilemedi — manuel kontrol.")

        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                sonuclar["incoterms"].append(
                    f"[TAMAM] {incoterm_var} teslimde Sigorta Poliçesi mevcut (Art 28 uyumlu)."
                )
            else:
                sonuclar["incoterms"].append(
                    f"[REZERV] {incoterm_var} teslimde Sigorta Poliçesi BULUNAMADI!"
                )
                self._risk_puani_ekle("sigorta_eksik")
                self._uyumluluk_duş(20)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Sigorta belgesi eksik ({incoterm_var} / Art 28)"
                )
                sonuclar["eksik_belgeler"].append("Sigorta Poliçesi (CIF/CIP zorunlu)")

        # ── 4. Çapraz Kontroller ──────────────────────────────────────────
        # 4a. Tutar — BUG-01 FIX: CIF toplam vs LC, goods_value değil
        # invoice_tutarlari_ayristir() bileşenleri ayrıştırır;
        # lc_karsilastirma_tutari() doğru değeri seçer (cif_total öncelikli)
        fatura_tutarlari = self.invoice_tutarlari_ayristir(fatura_text)
        fatura_tutari    = self.lc_karsilastirma_tutari(fatura_tutarlari)
        log.debug("Fatura tutar bileşenleri: %s", fatura_tutarlari)
        lc_32b_str    = self.mt700_alanlari.get("32B")
        lc_tutari: Optional[float] = None
        if lc_32b_str:
            # BUG-01 FIX: normalize_tutar ile 23,940 / 23.940 / 23940 hepsini çöz
            lc_tutari = self.normalize_tutar(lc_32b_str)
        if lc_tutari is None:
            lc_tutari = self.normalize_tutar(
                self.para_tutari_bul(kusat_text) and str(self.para_tutari_bul(kusat_text))
            ) or self.para_tutari_bul(kusat_text)

        if fatura_tutari and lc_tutari:
            about_var  = any(x in kusat_text.upper() for x in ["ABOUT", "APPROXIMATELY"])
            tolerans   = 10 if about_var else 5
            sapma_y    = (fatura_tutari - lc_tutari) / lc_tutari * 100
            uyumlu     = abs(sapma_y) <= tolerans

            # CIF bileşen detayı
            cif_detay = ""
            if fatura_tutarlari.get("goods_value"):
                cif_detay = (
                    f" [Goods: {fatura_tutarlari['goods_value']:,.2f}"
                    f" + Freight: {fatura_tutarlari.get('freight') or 0:,.2f}"
                    f" + Ins: {fatura_tutarlari.get('insurance') or 0:,.2f}"
                    f" = CIF: {fatura_tutari:,.2f}]"
                )
            detay = (f"LC: {lc_tutari:,.2f} | Fatura CIF Toplam: {fatura_tutari:,.2f}"
                     f"{cif_detay} | Sapma: {sapma_y:+.1f}% | Tolerans: ±%{tolerans}")
            if uyumlu:
                sonuclar["capraz_kontrol"].append(
                    {"belge": "Fatura vs LC Tutarı (Art 30)", "detay": detay, "durum": "UYUMLU"})
            else:
                sonuclar["capraz_kontrol"].append(
                    {"belge": "Fatura vs LC Tutarı (Art 30)", "detay": detay,
                     "durum": "REZERV RİSKİ - TUTAR UYUŞMAZLIĞI"})
                self._risk_puani_ekle("tutar_uyusmazligi")
                self._uyumluluk_duş(20)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Tutar sapması %{abs(sapma_y):.1f} > %{tolerans} (Art 30)"
                )
        else:
            eksik_t = [k for k, v in [("Fatura", fatura_tutari), ("LC (32B)", lc_tutari)] if not v]
            sonuclar["capraz_kontrol"].append(
                {"belge": "Fatura vs LC Tutarı (Art 30)",
                 "detay": f"Tespit edilemedi: {', '.join(eksik_t)}", "durum": "MANUEL KONTROL"})

        # 4b. Kilo (BUG-03 FIX: alan bazlı parser)
        fatura_kilo = self.kilo_bul(fatura_text)
        bl_kilo     = self.kilo_bul(konsimento_text)
        ceki_kilo   = self.kilo_bul(ceki_text)

        if fatura_kilo is not None and bl_kilo is not None:
            if abs(fatura_kilo - bl_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append(
                    {"belge": "Fatura vs B/L Kilo (Art 14)",
                     "detay": f"Eşleşti: {fatura_kilo:,.2f} KG", "durum": "UYUMLU"})
            else:
                sonuclar["capraz_kontrol"].append(
                    {"belge": "Fatura vs B/L Kilo (Art 14)",
                     "detay": f"Fatura: {fatura_kilo:,.2f} | B/L: {bl_kilo:,.2f} KG",
                     "durum": "REZERV RİSKİ - KILO UYUŞMAZLIĞI"})
                self._risk_puani_ekle("kilo_uyusmazligi")
                self._uyumluluk_duş(10)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Kilo uyumsuzluğu: Fatura {fatura_kilo:,.2f} / B/L {bl_kilo:,.2f} KG"
                )
        else:
            eksik_k = [k for k, v in [("Fatura", fatura_kilo), ("B/L", bl_kilo)] if v is None]
            sonuclar["capraz_kontrol"].append(
                {"belge": "Fatura vs B/L Kilo (Art 14)",
                 "detay": f"Kilo tespit edilemedi: {', '.join(eksik_k)}", "durum": "MANUEL KONTROL"})

        # 4c. Mal Tanımı (Art 18c)
        fatura_mal = self.mal_tanimi_bul(fatura_text)
        kusat_mal  = self.mal_tanimi_bul(kusat_text)
        if fatura_mal and kusat_mal:
            oran = self.mal_tanimi_benzerlik(kusat_mal, fatura_mal)
            if oran >= 0.8:
                durum_mal = "UYUMLU"
            elif oran >= 0.5:
                durum_mal = "DÜŞÜK BENZERLİK - MANUEL KONTROL"
                self._risk_puani_ekle("mal_tanimi_uyusmazligi")
                self._uyumluluk_duş(15)
            else:
                durum_mal = "REZERV RİSKİ - MAL TANIMI UYUŞMAZLIĞI"
                self._risk_puani_ekle("mal_tanimi_kritik")
                self._uyumluluk_duş(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Mal tanımı uyuşmazlığı: örtüşme %{oran*100:.0f} (Art 18c)"
                )
            sonuclar["capraz_kontrol"].append(
                {"belge": "Mal Tanımı vs Küşat (Art 18c)",
                 "detay": f"Küşat: '{kusat_mal[:60]}' | Fatura: '{fatura_mal[:60]}' | "
                          f"Benzerlik: %{oran*100:.0f}",
                 "durum": durum_mal})
        else:
            eksik_m = [k for k, v in [("Fatura", fatura_mal), ("Küşat 45A", kusat_mal)] if not v]
            sonuclar["capraz_kontrol"].append(
                {"belge": "Mal Tanımı vs Küşat (Art 18c)",
                 "detay": f"Tespit edilemedi: {', '.join(eksik_m)}", "durum": "MANUEL KONTROL"})

        # 4d. Yükleme Tarihi (Art 20 / 44C) — BUG-02 FIX: gelişmiş B/L tarih parser
        bl_tarih_str = self.bl_tarihi_bul(konsimento_text)   # çok desen, çok format
        lc_tarih_str = lc_44c_str or self.tarih_bul(kusat_text, [
            r'44C[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
            r'44C[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
        ])
        bl_dt = self.tarih_ayristir(bl_tarih_str) if bl_tarih_str else None
        lc_dt = self.tarih_ayristir(lc_tarih_str) if lc_tarih_str else None

        if bl_dt and lc_dt:
            if bl_dt <= lc_dt:
                sonuclar["capraz_kontrol"].append(
                    {"belge": "B/L Tarihi vs 44C (Art 20)",
                     "detay": f"{bl_tarih_str} ≤ {lc_tarih_str}", "durum": "UYUMLU"})
            else:
                sonuclar["capraz_kontrol"].append(
                    {"belge": "B/L Tarihi vs 44C (Art 20)",
                     "detay": f"B/L: {bl_tarih_str} > 44C: {lc_tarih_str} — GEÇ YÜKLEME!",
                     "durum": "REZERV RİSKİ - GEÇ YÜKLEME"})
                self._risk_puani_ekle("gec_yukleme")
                self._uyumluluk_duş(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — GEÇ YÜKLEME: B/L {bl_tarih_str} > 44C {lc_tarih_str} (Art 20)"
                )
        else:
            eksik_t2 = [k for k, v in [("B/L tarihi", bl_tarih_str), ("44C", lc_tarih_str)] if not v]
            sonuclar["capraz_kontrol"].append(
                {"belge": "B/L Tarihi vs 44C (Art 20)",
                 "detay": f"Tespit edilemedi: {', '.join(eksik_t2)}", "durum": "MANUEL KONTROL"})
            if not bl_tarih_str and konsimento_text:
                self._risk_puani_ekle("yukleme_tarihi_ihlali")
                self._uyumluluk_duş(15)
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — Konşimento yükleme tarihi tespit edilemedi (Art 20)"
                )

        # 4e. Sigorta teminatı ≥ Fatura × %110 (Art 28f-ii)
        if incoterm_var in ["CIF", "CIP"] and self.depo["SIGORTA"]:
            sig_tutar = self.para_tutari_bul(sigorta_text)
            if sig_tutar and fatura_tutari:
                min_teminat = fatura_tutari * 1.10
                if sig_tutar >= min_teminat:
                    sonuclar["capraz_kontrol"].append(
                        {"belge": "Sigorta ≥ Fatura×110% (Art 28f-ii)",
                         "detay": f"Sigorta: {sig_tutar:,.2f} | Min: {min_teminat:,.2f}",
                         "durum": "UYUMLU"})
                else:
                    sonuclar["capraz_kontrol"].append(
                        {"belge": "Sigorta ≥ Fatura×110% (Art 28f-ii)",
                         "detay": f"Sigorta: {sig_tutar:,.2f} < Min: {min_teminat:,.2f}",
                         "durum": "REZERV RİSKİ - YETERSİZ TEMİNAT"})
                    self._risk_puani_ekle("sigorta_eksik")
                    self._uyumluluk_duş(20)
                    sonuclar["rezerv_ozeti"].append(
                        f"REZERV — Sigorta teminatı yetersiz: {sig_tutar:,.2f} < {min_teminat:,.2f}"
                    )

        # ── 5. Konşimento (Art 20, Art 27) ───────────────────────────────
        if not konsimento_text:
            sonuclar["zorunlu_alanlar"].append(
                "[REZERV] Konşimento belgesi depoda bulunamadı!"
            )
            self._risk_puani_ekle("konsimento_eksik")
            self._uyumluluk_duş(30)
            sonuclar["rezerv_ozeti"].append(
                "REZERV — Konşimento belgesi ibraz edilmemiş (Art 20)"
            )
            sonuclar["eksik_belgeler"].append("Konşimento (Bill of Lading)")
        else:
            bl_u = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[REZERV] Konşimentoda 'Shipped on Board' şerhi bulunamadı!"
                )
                self._risk_puani_ekle("konsimento_eksik")
                self._uyumluluk_duş(20)
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — 'Shipped on Board' şerhi eksik (Art 20a-ii)"
                )
            kirli = [k for k in KIRLI_BL_IFADELERI if k in bl_u]
            if kirli:
                sonuclar["zorunlu_alanlar"].append(
                    f"[REZERV] Klozlu konşimento: {', '.join(kirli)} (Art 27 ihlali!)"
                )
                self._risk_puani_ekle("temiz_bl_sorunu")
                self._uyumluluk_duş(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Klozlu konşimento: {', '.join(kirli)} (Art 27)"
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Kirli/klozlu konşimento ifadesi bulunamadı (Art 27 uyumlu)."
                )

        # ── 6. Eksik Temel Belge Özeti — BUG-03 FIX: kanıt puanı ile filtrele
        for key, ad in [("KUSAT", "Küşat (MT700)"), ("FATURA", "Ticari Fatura"),
                        ("CEKI_LISTESI", "Çeki Listesi")]:
            if not self.depo[key]:
                # Dosya durum logunda bu tip için kayıt var mı kontrol et
                ilgili_log = [d for d in self._dosya_durum_log
                              if d.get("sinif") == key]
                if ilgili_log:
                    # Dosya var ama sınıflandırma ya da OCR sorunu
                    en_iyi = max(ilgili_log, key=lambda x: x.get("puan", 0))
                    kp = self.kanit_puani(
                        dosya_mevcut=True,
                        ocr_basarili=en_iyi.get("ocr_basarili", False),
                        sinif_belirlendi=en_iyi.get("sinif") is not None,
                    )
                    if kp < KANIT_ESIK_MAJOR:
                        sonuclar["eksik_belgeler"].append(
                            f"{ad} — Dosya mevcut ancak OCR/sınıflama belirsiz "
                            f"(kanıt: {kp}/100) — MANUEL KONTROL"
                        )
                    # Kanıt yeterli ama yanlış sınıfa girmiş olabilir; eklemedik
                else:
                    # Gerçekten dosya yok
                    sonuclar["eksik_belgeler"].append(ad)

        # ── 6b. Packing List 46A içerik kontrolü
        if self.depo.get("CEKI_LISTESI"):
            pl_kontrol = self.packing_list_icerik_kontrol(ceki_text)
            sonuclar["belge_46a"].append({
                "sart":  "Packing List İçerik Şartları",
                "detay": f"Bulunan: {', '.join(pl_kontrol['bulunan']) or '—'} | "
                         f"Eksik: {', '.join(pl_kontrol['eksik']) or '—'}",
                "durum": pl_kontrol["durum"],
            })

        # ── 6c. Origin (Menşe) Analizi
        origin_sonuc = self.origin_analizi_yap(kusat_text, fatura_text, self.depo)
        sonuclar["capraz_kontrol"].append({
            "belge":  "Menşe (Origin) Analizi",
            "detay":  origin_sonuc["detay"],
            "durum":  origin_sonuc["durum"],
        })
        if origin_sonuc["rezerv_gerekli"]:
            self._risk_puani_ekle("46a_belge_eksigi")
            self._uyumluluk_duş(15)
            sonuclar["rezerv_ozeti"].append(
                f"REZERV — Menşe: {origin_sonuc['detay'][:120]}"
            )

        # ── 7. 46A Belge Şartları ─────────────────────────────────────────
        alan_46a = self.mt700_alanlari.get("46A", "")
        if alan_46a:
            kontroller = [
                ("COMMERCIAL INVOICE", "FATURA",       "Ticari Fatura"),
                ("INVOICE",            "FATURA",       "Ticari Fatura"),
                ("BILL OF LADING",     "KONSIMENTO",   "Konşimento"),
                ("PACKING LIST",       "CEKI_LISTESI", "Packing List"),
                ("INSURANCE",          "SIGORTA",      "Sigorta Poliçesi"),
            ]
            for sart, depo_k, ad in kontroller:
                if sart.upper() in alan_46a.upper():
                    var = self.depo.get(depo_k) is not None
                    if not var:
                        self._risk_puani_ekle("46a_belge_eksigi")
                        self._uyumluluk_duş(10)
                        sonuclar["rezerv_ozeti"].append(
                            f"REZERV — 46A gereği '{ad}' belgesi eksik"
                        )
                    sonuclar["belge_46a"].append(
                        {"sart": ad, "detay": "46A'da talep edildi.",
                         "durum": "VAR" if var else "EKSİK"}
                    )
        else:
            sonuclar["belge_46a"].append(
                {"sart": "46A", "detay": "MT700 46A tespit edilemedi.",
                 "durum": "MANUEL KONTROL"}
            )

        # ── 8. Risk Özeti ─────────────────────────────────────────────────
        risk_sinifi = self._risk_sinifi()
        sonuclar["risk_ozeti"].append(
            f"Risk Puanı: **{self.risk_puani}** — {risk_sinifi}"
        )
        sonuclar["risk_ozeti"].append(
            f"Uyumluluk Skoru: **%{self.uyumluluk_puani}**"
        )
        for i, r in enumerate(sonuclar["rezerv_ozeti"], 1):
            sonuclar["risk_ozeti"].append(f"{i}. {r}")

        # ── 9. MT700 Alan Analizi ─────────────────────────────────────────
        mt_analiz = []
        for kod, aciklama in MT700_ALAN_ACIKLAMALARI.items():
            deger = self.mt700_alanlari.get(kod)
            if deger:
                mt_analiz.append({"alan": kod, "aciklama": aciklama,
                                   "deger": deger[:120], "durum": "✔ TESPİT EDİLDİ"})
            elif kod in {"20", "31D", "32B", "40A", "44C", "45A", "46A"}:
                mt_analiz.append({"alan": kod, "aciklama": aciklama,
                                   "deger": "—", "durum": "⚠ TESPİT EDİLEMEDİ"})
        sonuclar["mt700_alan_analizi"] = mt_analiz

        # ── 10. ISBP 821 Tablosu ──────────────────────────────────────────
        isbp_t = []
        for kayit in sonuclar["capraz_kontrol"]:
            belge = kayit.get("belge", "")
            for madde, isbp in ISBP_ESLESTIRME.items():
                if madde.replace("Art ", "") in belge:
                    isbp_t.append({
                        "ucp_maddesi":  madde,
                        "isbp_prensibi": isbp["prensip"],
                        "bulgu":         f"{belge}: {kayit.get('durum','')}",
                        "oneri":         isbp["oneri"],
                    })
        isbp_t.append({
            "ucp_maddesi":  "Art 14",
            "isbp_prensibi": ISBP_ESLESTIRME["Art 14"]["prensip"],
            "bulgu":         "21 günlük ibraz süresi kontrolü uygulandı.",
            "oneri":         ISBP_ESLESTIRME["Art 14"]["oneri"],
        })
        sonuclar["isbp_tablosu"] = isbp_t

        # ── 11. Rezerv Detay Listesi ──────────────────────────────────────
        detaylar = []
        for kat_key in self._aktif_rezerv_kategorileri:
            bilgi = REZERV_KATEGORILERI.get(kat_key, {})
            detaylar.append({
                "kategori_kodu": kat_key,
                "kategori":      bilgi.get("kategori", "?"),
                "puan":          str(bilgi.get("puan", "?")),
                "tahmini_sure":  bilgi.get("sure", "?"),
            })
        sonuclar["rezerv_detay_listesi"] = detaylar

        # ── 12. SWIFT Simülatör ───────────────────────────────────────────
        swift_list = [
            REZERV_SWIFT_SABLONLARI[k]
            for k in self._aktif_rezerv_kategorileri
            if k in REZERV_SWIFT_SABLONLARI
        ]
        sonuclar["rezerv_swift_metinleri"] = swift_list

        # ── 13. Hukuk Motoru Entegrasyonu ────────────────────────────────
        if HUKUK_MOTORU_AKTIF and hukuk_motoru_analiz_et:
            try:
                motor_sonuc = hukuk_motoru_analiz_et(self.depo)
                if isinstance(motor_sonuc, list):
                    sonuclar["ucp_tablosu"] = motor_sonuc
                    log.debug("hukuk_motoru entegrasyonu başarılı: %d kayıt", len(motor_sonuc))
            except Exception as e:
                log.warning("hukuk_motoru hatası: %s — dahili motor kullanılıyor.", e)
                log.debug(traceback.format_exc())

        # ── 14. Yönetici Özeti ────────────────────────────────────────────
        mevcut = [k for k in ["KUSAT","FATURA","KONSIMENTO","CEKI_LISTESI","SIGORTA"]
                  if self.depo.get(k)]
        major  = sum(1 for k in self._aktif_rezerv_kategorileri
                     if REZERV_KATEGORILERI.get(k, {}).get("kategori") == "MAJOR DISCREPANCY")
        sonuclar["yonetici_ozeti"] = {
            "toplam_belge":          len(mevcut),
            "mevcut_belgeler":       mevcut,
            "eksik_belgeler":        sonuclar["eksik_belgeler"],
            "toplam_rezerv":         len(sonuclar["rezerv_ozeti"]),
            "major_rezerv":          major,
            "uyumluluk_skoru":       self.uyumluluk_puani,
            "risk_puani":            self.risk_puani,
            "risk_sinifi":           risk_sinifi,
            "banka_kabul_olasiligi": self._banka_kabul_olasiligi,
        }

        self.analiz_verisi = sonuclar

    # ------------------------------------------------------------------
    # Markdown raporu
    # ------------------------------------------------------------------
    def markdown_raporu_olustur(self) -> None:
        v = self.analiz_verisi
        if not v:
            return

        md_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")
        s = []
        s.append("# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU\n\n")
        s.append(f"**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M')} | "
                 "**Motor:** UCP 600 & ISBP 821 v7.0\n\n---\n\n")

        # Dosya Durum Raporu (BUG-05 FIX)
        s.append("## 📁 DOSYA DURUM RAPORU\n\n")
        s.append("| Dosya | Bulundu | OCR | Sınıf | Puan |\n| :--- | :--- | :--- | :--- | :--- |\n")
        for d in v.get("dosya_durum_raporu", []):
            s.append(
                f"| {d.get('dosya','')} | "
                f"{'✔' if d.get('dosya_bulundu') else '✖'} | "
                f"{'✔' if d.get('ocr_basarili') else '✖'} | "
                f"{d.get('sinif') or ('⚠ Sınıflandırılamadı' if d.get('ocr_basarili') else '—')} | "
                f"{d.get('puan','—')} |\n"
            )
        s.append("\n---\n\n")

        # Yönetici Özeti
        oz = v.get("yonetici_ozeti", {})
        if oz:
            s.append("## 🏦 YÖNETİCİ ÖZETİ\n\n")
            s.append("| Metrik | Değer |\n| :--- | :--- |\n")
            s.append(f"| Belgeler | {', '.join(oz.get('mevcut_belgeler',[]))} |\n")
            s.append(f"| Tespit Edilen Rezerv | {oz.get('toplam_rezerv',0)} |\n")
            s.append(f"| MAJOR Discrepancy | {oz.get('major_rezerv',0)} |\n")
            s.append(f"| Uyumluluk Skoru | **%{oz.get('uyumluluk_skoru','?')}** |\n")
            s.append(f"| Banka Kabul Olasılığı | **%{oz.get('banka_kabul_olasiligi','?')}** |\n")
            s.append(f"| Risk Sınıfı | {oz.get('risk_sinifi','?')} |\n")
            s.append("\n---\n\n")

        # MT700
        s.append("## 📡 MT700 ALAN ANALİZİ\n\n")
        s.append("| Alan | Açıklama | Değer | Durum |\n| :--- | :--- | :--- | :--- |\n")
        for a in v.get("mt700_alan_analizi", []):
            s.append(f"| **{a['alan']}** | {a['aciklama']} | `{a['deger']}` | {a['durum']} |\n")
        s.append("\n---\n\n")

        s.append("## 1. Vade Analizi\n")
        for x in v.get("vade_analizi", []): s.append(f"* {x}\n")

        s.append("\n## 2. Ödeme Vadesi\n")
        for x in v.get("finansal_durum", []): s.append(f"* {x}\n")

        s.append("\n## 3. Incoterms & Sigorta\n")
        for x in v.get("incoterms", []): s.append(f"* {x}\n")

        s.append("\n## 4. Çapraz Kontroller\n")
        s.append("| Belgeler | Detay | Durum |\n| :--- | :--- | :--- |\n")
        for c in v.get("capraz_kontrol", []):
            s.append(f"| {c['belge']} | {c['detay']} | **{c['durum']}** |\n")

        s.append("\n## 5. Konşimento Kontrolü\n")
        for x in v.get("zorunlu_alanlar", []): s.append(f"* {x}\n")

        s.append("\n## 6. 46A Belge Şartları\n")
        s.append("| Belge | Detay | Durum |\n| :--- | :--- | :--- |\n")
        for b in v.get("belge_46a", []):
            s.append(f"| {b['sart']} | {b['detay']} | **{b['durum']}** |\n")

        s.append("\n## 7. ISBP 821 Tablosu\n")
        s.append("| UCP | ISBP Prensibi | Bulgu | Öneri |\n| :--- | :--- | :--- | :--- |\n")
        for i in v.get("isbp_tablosu", []):
            s.append(f"| **{i['ucp_maddesi']}** | {i['isbp_prensibi']} | "
                     f"{i['bulgu']} | {i['oneri']} |\n")

        s.append("\n## 8. Tespit Edilen Rezervler\n")
        for r in v.get("rezerv_ozeti", []):
            s.append(f"* ⚠ {r}\n")
        if not v.get("rezerv_ozeti"):
            s.append("* ✅ Kritik rezerv tespit edilmedi.\n")

        s.append("\n## 9. Rezerv Kategorileri\n")
        s.append("| Kategori | Sınıf | Puan | Süre |\n| :--- | :--- | :--- | :--- |\n")
        for d in v.get("rezerv_detay_listesi", []):
            s.append(f"| {d['kategori_kodu']} | **{d['kategori']}** | "
                     f"{d['puan']} | {d['tahmini_sure']} |\n")

        s.append("\n## 10. Risk Değerlendirmesi\n")
        for x in v.get("risk_ozeti", []): s.append(f"* {x}\n")

        swift = v.get("rezerv_swift_metinleri", [])
        if swift:
            s.append("\n## 🏛 SWIFT Rezerv Simülatörü\n\n")
            for i, mt in enumerate(swift, 1):
                s.append(f"### Ret Metni {i}\n```\n{mt}\n```\n\n")

        with open(md_yolu, "w", encoding="utf-8") as f:
            f.writelines(s)
        print("[+] Markdown Raporu oluşturuldu.")

    # ------------------------------------------------------------------
    # HTML raporu
    # ------------------------------------------------------------------
    def html_raporu_olustur(self) -> None:
        v = self.analiz_verisi
        if not v:
            return

        html_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.html")

        def li_list(anahtar: str) -> str:
            return "".join(f"<li>{x}</li>" for x in v.get(anahtar, []))

        capraz_html = "".join(
            f"<tr><td><b>{r['belge']}</b></td><td>{r['detay']}</td>"
            f"<td><b>{r['durum']}</b></td></tr>"
            for r in v.get("capraz_kontrol", [])
        )
        dosya_durum_html = "".join(
            f"<tr>"
            f"<td>{d.get('dosya','')}</td>"
            f"<td>{'✔' if d.get('dosya_bulundu') else '✖'}</td>"
            f"<td>{'✔' if d.get('ocr_basarili') else '✖'}</td>"
            f"<td>{d.get('sinif') or ('⚠' if d.get('ocr_basarili') else '—')}</td>"
            f"<td>{d.get('puan','—')}</td>"
            f"</tr>"
            for d in v.get("dosya_durum_raporu", [])
        )
        mt_html = "".join(
            f"<tr><td><b>{a['alan']}</b></td><td>{a['aciklama']}</td>"
            f"<td><code>{a['deger']}</code></td><td>{a['durum']}</td></tr>"
            for a in v.get("mt700_alan_analizi", [])
        )
        belge_46a_html = "".join(
            f"<tr><td>{b['sart']}</td><td>{b['detay']}</td>"
            f"<td><b>{b['durum']}</b></td></tr>"
            for b in v.get("belge_46a", [])
        )
        isbp_html = "".join(
            f"<tr><td><b>{i['ucp_maddesi']}</b></td><td>{i['isbp_prensibi']}</td>"
            f"<td>{i['bulgu']}</td><td>{i['oneri']}</td></tr>"
            for i in v.get("isbp_tablosu", [])
        )
        rezerv_html = "".join(
            f"<li>⚠ {r}</li>" for r in v.get("rezerv_ozeti", [])
        ) or "<li>✅ Kritik rezerv tespit edilmedi.</li>"
        kat_html = "".join(
            f"<tr><td>{d['kategori_kodu']}</td><td><b>{d['kategori']}</b></td>"
            f"<td>{d['puan']}</td><td>{d['tahmini_sure']}</td></tr>"
            for d in v.get("rezerv_detay_listesi", [])
        )
        swift_html = "".join(
            f'<div class="swift-box"><b>Ret Metni {i}</b><pre>{mt}</pre></div>'
            for i, mt in enumerate(v.get("rezerv_swift_metinleri", []), 1)
        ) or '<p style="color:#276749">✅ SWIFT ret metni oluşturulmadı.</p>'

        oz = v.get("yonetici_ozeti", {})
        krenk = ("#276749" if oz.get("banka_kabul_olasiligi", 0) >= 70
                 else "#d69e2e" if oz.get("banka_kabul_olasiligi", 0) >= 40 else "#c53030")

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Akreditif Analiz Raporu v7.0</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',sans-serif;background:#f0f4f8;color:#2d3748;padding:20px}}
    .wrap{{background:#fff;padding:36px;border-radius:14px;
           box-shadow:0 4px 20px rgba(0,0,0,.08);max-width:1280px;margin:0 auto}}
    h1{{color:#1a365d;border-bottom:4px solid #3182ce;padding-bottom:14px;font-size:1.4em}}
    h2{{color:#2b6cb0;margin:28px 0 10px;border-left:5px solid #3182ce;
        padding-left:10px;font-size:1.05em}}
    table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:.88em}}
    th,td{{border:1px solid #e2e8f0;padding:8px 11px;text-align:left;vertical-align:top}}
    th{{background:#ebf8ff;color:#2b6cb0;font-weight:600}}
    tr:nth-child(even){{background:#f7fafc}}
    ul{{padding-left:18px;margin-top:8px}}
    li{{margin-bottom:5px;line-height:1.7}}
    .meta{{color:#718096;font-size:.88em;margin-bottom:16px}}
    .exec{{background:linear-gradient(135deg,#ebf8ff,#f0fff4);
           border:2px solid #3182ce;border-radius:12px;padding:20px;margin-bottom:24px}}
    .grid{{display:flex;flex-wrap:wrap;gap:12px;margin-top:14px}}
    .card{{background:#fff;border:1px solid #bee3f8;border-radius:8px;
           padding:12px 18px;min-width:160px;text-align:center}}
    .lbl{{font-size:.78em;color:#718096;margin-bottom:4px}}
    .val{{font-size:1.35em;font-weight:700;color:#2b6cb0}}
    code{{background:#edf2f7;padding:2px 6px;border-radius:4px;font-size:.85em}}
    .swift-box{{background:#1a202c;color:#f6e05e;border-radius:8px;
                padding:16px;margin:8px 0;font-family:monospace;font-size:.87em}}
    .swift-box pre{{white-space:pre-wrap;margin-top:8px;color:#e2e8f0}}
  </style>
</head>
<body>
<div class="wrap">
  <h1>📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU</h1>
  <p class="meta">
    <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} &nbsp;|&nbsp;
    <b>Motor:</b> UCP 600 &amp; ISBP 821 v7.0
  </p>

  <div class="exec">
    <h2>🏦 YÖNETİCİ ÖZETİ</h2>
    <div class="grid">
      <div class="card"><div class="lbl">Belgeler</div>
        <div class="val">{oz.get('toplam_belge','?')}</div></div>
      <div class="card"><div class="lbl">Rezerv Sayısı</div>
        <div class="val" style="color:#c53030">{oz.get('toplam_rezerv',0)}</div></div>
      <div class="card"><div class="lbl">MAJOR</div>
        <div class="val" style="color:#c53030">{oz.get('major_rezerv',0)}</div></div>
      <div class="card"><div class="lbl">Uyumluluk</div>
        <div class="val" style="color:#276749">%{oz.get('uyumluluk_skoru','?')}</div></div>
      <div class="card"><div class="lbl">Banka Kabul</div>
        <div class="val" style="color:{krenk}">%{oz.get('banka_kabul_olasiligi','?')}</div></div>
      <div class="card"><div class="lbl">Risk</div>
        <div class="val" style="font-size:1em">{oz.get('risk_sinifi','?')}</div></div>
    </div>
  </div>

  <h2>📁 Dosya Durum Raporu</h2>
  <table>
    <tr><th>Dosya</th><th>Bulundu</th><th>OCR</th><th>Sınıf</th><th>Puan</th></tr>
    {dosya_durum_html}
  </table>

  <h2>📡 MT700 Alan Analizi</h2>
  <table><tr><th>Alan</th><th>Açıklama</th><th>Değer</th><th>Durum</th></tr>{mt_html}</table>

  <h2>1. Vade Analizi</h2><ul>{li_list("vade_analizi")}</ul>
  <h2>2. Ödeme Vadesi</h2><ul>{li_list("finansal_durum")}</ul>
  <h2>3. Incoterms &amp; Sigorta</h2><ul>{li_list("incoterms")}</ul>

  <h2>4. Çapraz Kontroller</h2>
  <table><tr><th>Belgeler</th><th>Detay</th><th>Durum</th></tr>{capraz_html}</table>

  <h2>5. Konşimento Kontrolü</h2><ul>{li_list("zorunlu_alanlar")}</ul>

  <h2>6. 46A Belge Şartları</h2>
  <table><tr><th>Belge</th><th>Detay</th><th>Durum</th></tr>{belge_46a_html}</table>

  <h2>7. ISBP 821 Tablosu</h2>
  <table><tr><th>UCP</th><th>ISBP Prensibi</th><th>Bulgu</th><th>Öneri</th></tr>{isbp_html}</table>

  <h2>8. Tespit Edilen Rezervler</h2><ul>{rezerv_html}</ul>

  <h2>9. Rezerv Kategorileri</h2>
  <table><tr><th>Kategori</th><th>Sınıf</th><th>Puan</th><th>Tahmini Süre</th></tr>{kat_html}</table>

  <h2>10. Risk Değerlendirmesi</h2><ul>{li_list("risk_ozeti")}</ul>

  <h2>🏛 SWIFT Rezerv Simülatörü</h2>
  {swift_html}
</div>
</body>
</html>"""

        with open(html_yolu, "w", encoding="utf-8") as f:
            f.write(html)
        print("[+] HTML Raporu oluşturuldu.")

    # ------------------------------------------------------------------
    # Ana akış
    # ------------------------------------------------------------------
    def baslat(self) -> None:
        print("[BİLGİ] Akreditif denetim sistemi v7.0 başlatılıyor...")
        if self.depoyu_tara_ve_analiz_et():
            print(
                f"[BİLGİ] Belgeler yüklendi: "
                f"KUŞAT={'VAR' if self.depo['KUSAT'] else 'YOK'} | "
                f"FATURA={'VAR' if self.depo['FATURA'] else 'YOK'} | "
                f"KONŞİMENTO={'VAR' if self.depo['KONSIMENTO'] else 'YOK'} | "
                f"ÇEKİ={'VAR' if self.depo['CEKI_LISTESI'] else 'YOK'} | "
                f"SİGORTA={'VAR' if self.depo['SIGORTA'] else 'YOK'}"
            )
            self.ucp600_kural_motoru()
            self.markdown_raporu_olustur()
            self.html_raporu_olustur()
            print(
                f"[SONUÇ] Risk Puanı: {self.risk_puani} — {self._risk_sinifi()} | "
                f"Uyumluluk: %{self.uyumluluk_puani} | "
                f"Banka Kabul: %{self._banka_kabul_olasiligi}"
            )
            print("[SONUÇ] Tüm raporlar üretildi.")
        else:
            print("[BİLGİ] Yüklenmiş belge bulunamadı.")


if __name__ == "__main__":
    motor = YapayZekaDisTicaretDenetleyici()
    motor.baslat()
