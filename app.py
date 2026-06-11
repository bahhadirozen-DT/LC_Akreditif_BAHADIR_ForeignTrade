"""
Yapay Zeka Destekli Dış Ticaret Akreditif Denetleme Sistemi
UCP 600 / ISBP 821 Uyumlu | Üretim Ortamı Sürümü v6.0

Bağımlılıklar (opsiyonel):
    pypdf, python-docx, openpyxl, Pillow, pytesseract
    hukuk_motoru.py, kurallar.json
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Opsiyonel kütüphane yüklemeleri
# ---------------------------------------------------------------------------
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt
except ImportError:
    docx = None  # type: ignore

try:
    import openpyxl
except ImportError:
    openpyxl = None  # type: ignore

try:
    from PIL import Image
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore
    Image = None  # type: ignore

# ---------------------------------------------------------------------------
# hukuk_motoru.py — doğrudan entegrasyon; monkey patch kullanılmaz
# ---------------------------------------------------------------------------
try:
    from hukuk_motoru import analiz_et as hukuk_motoru_analiz_et
    HUKUK_MOTORU_AKTIF = True
except ImportError:
    hukuk_motoru_analiz_et = None  # type: ignore
    HUKUK_MOTORU_AKTIF = False

# ---------------------------------------------------------------------------
# Risk motoru sabitleri — bulgu ağırlığına göre puanlandırma
# ---------------------------------------------------------------------------
RISK_PUANLARI: dict[str, int] = {
    "sigorta_eksik":          30,
    "tutar_uyusmazligi":      40,
    "yukleme_tarihi_ihlali":  40,
    "konsimento_eksik":       50,
    "mal_tanimi_uyusmazligi": 35,
    "mal_tanimi_kritik":      50,
    "kilo_uyusmazligi":       20,
    "ibraz_suresi_belirsiz":  10,
    "temiz_bl_sorunu":        45,
    "46a_belge_eksigi":       25,
    "gec_yukleme":            40,
}

RISK_SINIFLANDIRMASI: list[tuple[int, int, str]] = [
    (0,   20, "DÜŞÜK RİSK"),
    (21,  50, "ORTA RİSK"),
    (51, 999, "YÜKSEK RİSK"),
]

# ---------------------------------------------------------------------------
# Kirli konşimento ifadeleri (Art 27)
# ---------------------------------------------------------------------------
KIRLI_BL_IFADELERI: list[str] = [
    "CLAUSED", "DAMAGED", "TORN", "WET CARGO",
    "INSUFFICIENT PACKING", "PARTLY DAMAGED",
    "RUSTED", "LEAKING", "STAINED", "BROKEN",
]

# ---------------------------------------------------------------------------
# Birim normalleştirme haritası
# ---------------------------------------------------------------------------
BIRIM_NORMALIZASYON: dict[str, str] = {
    "KG":      "KG",   "KGS":     "KG",
    "TON":     "TON",  "TONS":    "TON",  "MT":  "TON",
    "PCS":     "PCS",  "PIECES":  "PCS",  "PIECE": "PCS",
    "CTN":     "CTN",  "CARTON":  "CTN",  "CARTONS": "CTN",
    "BOX":     "BOX",  "BOXES":   "BOX",
    "SET":     "SET",  "SETS":    "SET",
    "UNIT":    "UNIT", "UNITS":   "UNIT",
}

# ---------------------------------------------------------------------------
# Ay isimleri — tarih ayrıştırma
# ---------------------------------------------------------------------------
AY_ISIMLERI: dict[str, int] = {
    "JAN": 1, "JANUARY": 1,   "FEB": 2, "FEBRUARY": 2,
    "MAR": 3, "MARCH": 3,     "APR": 4, "APRIL": 4,
    "MAY": 5,                  "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7,      "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPTEMBER": 9, "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,"DEC": 12, "DECEMBER": 12,
}

# ---------------------------------------------------------------------------
# ISBP 821 eşleştirme tablosu — paragraf düzeyinde referans
# ---------------------------------------------------------------------------
ISBP_ESLESTIRME: dict[str, dict[str, str]] = {
    "Art 14": {
        "prensip":    "ISBP 821 Paragraf A1-A7 — Belge İnceleme Prensipleri",
        "aciklama":   "Banka, belgeleri ibraz tarihinden itibaren en fazla 5 iş günü içinde inceler. Belgelerin yüzeyde uyumlu görünmesi yeterlidir.",
        "oneri":      "İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır.",
        "paragraf":   "ISBP 821 § A1, § A3, § A6",
    },
    "Art 18": {
        "prensip":    "ISBP 821 Paragraf C1-C23 — Ticari Fatura Prensipleri",
        "aciklama":   "Faturadaki mal tanımı, akreditifte yer alan ifadeyle birebir uyumlu olmalıdır. Kısaltma ve parantez içi açıklamalar kabul görmeyebilir.",
        "oneri":      "Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. Fazla açıklama eklemeyin.",
        "paragraf":   "ISBP 821 § C5, § C7, § C14",
    },
    "Art 20": {
        "prensip":    "ISBP 821 Paragraf E1-E30 — Konşimento Prensipleri",
        "aciklama":   "'Shipped on Board' şerhi yükleme tarihini açıkça göstermelidir. Kaptan, acente veya taşıyıcı imzası zorunludur.",
        "oneri":      "Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisinin ayrıca yer aldığından emin olun.",
        "paragraf":   "ISBP 821 § E4, § E11, § E14",
    },
    "Art 27": {
        "prensip":    "ISBP 821 Paragraf E26-E27 — Temiz Taşıma Belgesi Prensipleri",
        "aciklama":   "Konşimento üzerinde malın durumuna ilişkin herhangi bir olumsuz kaydın bulunmaması gerekir. 'CLEAN' ifadesi olmasa dahi kloz içermemesi temiz kabul edilir.",
        "oneri":      "Konşimentonun taşıyıcı tarafından 'clean' olarak düzenlendiğini teyit edin; hasar notu varsa düzeltilmiş yeni konşimento talep edin.",
        "paragraf":   "ISBP 821 § E26, § E27",
    },
    "Art 28": {
        "prensip":    "ISBP 821 Paragraf K1-K15 — Sigorta Belgesi Prensipleri",
        "aciklama":   "Sigorta belgesi en az fatura bedelinin %110'unu teminat altına almalı ve akreditif para birimiyle düzenlenmelidir.",
        "oneri":      "Sigorta poliçesinin döviz cinsini, teminat tutarını ve kapsam tarihini akreditifle karşılaştırın.",
        "paragraf":   "ISBP 821 § K3, § K8, § K12",
    },
    "Art 30": {
        "prensip":    "ISBP 821 Paragraf B14 — Miktar ve Tutar Tolerans Prensipleri",
        "aciklama":   "Akreditifte 'about' veya 'approximately' ifadesi varsa %10 tolerans uygulanır. Aksi hâlde %5 tolerans geçerlidir.",
        "oneri":      "Fatura tutarının akreditif tutarıyla %5 sapma sınırı içinde kaldığını doğrulayın.",
        "paragraf":   "ISBP 821 § B14",
    },
}

# ---------------------------------------------------------------------------
# Rezerv kategorileri — bankacı standardı
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# MT700 tüm alan listesi ve açıklamaları
# ---------------------------------------------------------------------------
MT700_ALAN_ACIKLAMALARI: dict[str, str] = {
    "20":  "Documentary Credit Number — Akreditif Numarası",
    "31C": "Date of Issue — Düzenlenme Tarihi",
    "31D": "Date and Place of Expiry — Son Kullanma Tarihi ve Yeri",
    "32B": "Currency Code, Amount — Para Birimi ve Tutar",
    "39A": "Percentage Credit Amount Tolerance — Yüzde Tolerans",
    "39B": "Maximum Credit Amount — Azami Tutar",
    "40A": "Form of Documentary Credit — Akreditif Türü",
    "41A": "Available With — Kullanım Yeri",
    "42C": "Drafts at — Poliçe Vadesi",
    "42P": "Deferred Payment Details — Vadeli Ödeme Detayı",
    "43P": "Partial Shipments — Kısmi Sevkiyat",
    "43T": "Transhipment — Aktarma",
    "44A": "Place of Taking in Charge — Teslim Alım Yeri",
    "44B": "Place of Final Destination — Varış Yeri",
    "44C": "Latest Date of Shipment — En Geç Yükleme Tarihi",
    "44D": "Shipment Period — Yükleme Dönemi",
    "45A": "Description of Goods — Mal Tanımı",
    "46A": "Documents Required — Talep Edilen Belgeler",
    "47A": "Additional Conditions — Ek Şartlar",
    "48":  "Period for Presentation — İbraz Süresi (gün)",
    "49":  "Confirmation Instructions — Teyit Talimatı",
    "53A": "Reimbursement Bank — Rambursman Bankası",
    "57A": "Advising Bank — İhbar Bankası",
    "71B": "Charges — Masraflar",
    "78":  "Instructions to the Paying Bank — Ödeme Bankasına Talimat",
}

# ---------------------------------------------------------------------------
# Rezerv simülatörü — SWIFT mesaj şablonları
# ---------------------------------------------------------------------------
REZERV_SWIFT_SABLONLARI: dict[str, str] = {
    "sigorta_eksik": (
        "DOCUMENTS REJECTED.\n\n"
        "INSURANCE DOCUMENT AS REQUIRED BY FIELD 46A\n"
        "OF THE CREDIT HAS NOT BEEN PRESENTED.\n"
        "UCP 600 ARTICLE 28."
    ),
    "tutar_uyusmazligi": (
        "DOCUMENTS REJECTED.\n\n"
        "INVOICE AMOUNT EXCEEDS THE CREDIT AMOUNT.\n"
        "UCP 600 ARTICLE 18 / ARTICLE 30."
    ),
    "kilo_uyusmazligi": (
        "DOCUMENTS REJECTED.\n\n"
        "GROSS WEIGHT AS SHOWN ON COMMERCIAL INVOICE\n"
        "DOES NOT CORRESPOND WITH THAT SHOWN ON\n"
        "BILL OF LADING.\n"
        "UCP 600 ARTICLE 14 / ISBP 821 § C10."
    ),
    "mal_tanimi_kritik": (
        "DOCUMENTS REJECTED.\n\n"
        "DESCRIPTION OF GOODS ON COMMERCIAL INVOICE\n"
        "DOES NOT CORRESPOND WITH THAT STATED IN\n"
        "THE CREDIT.\n"
        "UCP 600 ARTICLE 18(C) / ISBP 821 § C5."
    ),
    "konsimento_eksik": (
        "DOCUMENTS REJECTED.\n\n"
        "FULL SET OF ORIGINAL BILLS OF LADING\n"
        "AS REQUIRED BY THE CREDIT HAS NOT\n"
        "BEEN PRESENTED.\n"
        "UCP 600 ARTICLE 20."
    ),
    "gec_yukleme": (
        "DOCUMENTS REJECTED.\n\n"
        "SHIPMENT DATE AS EVIDENCED BY BILL OF LADING\n"
        "IS LATER THAN THE LATEST DATE OF SHIPMENT\n"
        "STIPULATED IN FIELD 44C OF THE CREDIT.\n"
        "UCP 600 ARTICLE 14(C) / ARTICLE 20."
    ),
    "temiz_bl_sorunu": (
        "DOCUMENTS REJECTED.\n\n"
        "BILL OF LADING BEARS CLAUSE(S) OR NOTATION(S)\n"
        "ADVERSELY COMMENTING ON THE CONDITION OF\n"
        "THE GOODS AND/OR PACKAGING.\n"
        "UCP 600 ARTICLE 27 / ISBP 821 § E26."
    ),
    "46a_belge_eksigi": (
        "DOCUMENTS REJECTED.\n\n"
        "ONE OR MORE DOCUMENTS AS REQUIRED BY FIELD 46A\n"
        "OF THE CREDIT HAVE NOT BEEN PRESENTED.\n"
        "UCP 600 ARTICLE 14(A) / ARTICLE 16."
    ),
}


# ===========================================================================
# Ana sınıf
# ===========================================================================
class YapayZekaDisTicaretDenetleyici:
    """UCP 600 / ISBP 821 uyumlu profesyonel akreditif belge denetleme motoru."""

    def __init__(self, ana_dizin: str = "DisTicaretRepo") -> None:
        self.base_dir        = ana_dizin
        self.yuklenenler_dir = os.path.join(self.base_dir, "YuklenenDosyalar")
        self.raporlar_dir    = os.path.join(self.base_dir, "Raporlar")

        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir,    exist_ok=True)

        self.depo:              dict[str, Any] = self._bos_depo()
        self.analiz_verisi:     dict[str, Any] = {}
        self.risk_puani:        int            = 0
        self.uyumluluk_puani:   int            = 100
        self.mt700_alanlari:    dict[str, str] = {}
        # v6.0 — yeni durum alanları
        self._aktif_rezerv_kategorileri: list[str] = []   # kategori anahtarları listesi
        self._banka_kabul_olasiligi:     int        = 100  # 0–100 %

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
        kayit = self.depo.get(anahtar)
        if not kayit or not isinstance(kayit, dict):
            return ""
        metin = kayit.get("metin")
        return metin if isinstance(metin, str) else ""

    # ------------------------------------------------------------------
    # MT700 ayrıştırıcısı — çok formatlı, OCR toleranslı
    # ------------------------------------------------------------------
    def mt700_ayristir(self, metin: str) -> dict[str, str]:
        """
        SWIFT MT700 formatındaki küşat metninden standart alanları çıkarır.
        Desteklenen formatlar:
            :32B:USD100000
            :32B: USD 100,000.00
            32B USD100000
            44C\n15 JUN 2026
            44C 15 JUN 2026
            DESCRIPTION OF GOODS\n<içerik>
        OCR bozulmaları ve satır sonu varyasyonlarına toleranslıdır.
        45A/46A/47A için çok satırlı içerik korunur.
        """
        if not metin:
            return {}

        hedef_alanlar = ["20", "31D", "32B", "40A", "44C", "45A", "46A", "47A", "71B"]
        # Çok satırlı içerik gereken alanlar
        cok_satirli = {"45A", "46A", "47A"}
        sonuc: dict[str, str] = {}

        # Sonraki alan etiketi için lookahead deseni
        sonraki_alan = r'(?=(?:\n[ \t]*:?\d{2,3}[A-Z]{0,2}[:\s]|\Z))'

        for alan in hedef_alanlar:
            desenler = [
                # :32B:USD100000  veya  :32B: USD 100,000.00
                rf':{re.escape(alan)}:\s*(.+?){sonraki_alan}',
                # 32B USD100000  (iki nokta üst üste olmadan, aynı satırda değer var)
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[ \t]+(.+?){sonraki_alan}',
                # 32B\nUSD100000  (alan adından sonra satır sonu, değer sonraki satırda)
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[ \t]*\n(.+?){sonraki_alan}',
                # OCR toleranslı: alan adının etrafında fazladan boşluk/karakter olabilir
                rf'(?:^|\n)[ \t]*{re.escape(alan)}[:\-]?[ \t]*(.+?){sonraki_alan}',
            ]

            # 46A için ek insan okunur başlık eşleştirmesi
            if alan == "46A":
                desenler.insert(0,
                    r'(?:DOCUMENTS?\s+REQUIRED|REQUIRED\s+DOCUMENTS?)[:\s]*\n(.+?)' + sonraki_alan
                )
            # 45A için mal tanımı başlığı eşleştirmesi
            if alan == "45A":
                desenler.insert(0,
                    r'(?:DESCRIPTION\s+OF\s+GOODS?|GOODS?\s+DESCRIPTION)[:\s]*\n(.+?)' + sonraki_alan
                )
                desenler.insert(1,
                    r'(?:DESCRIPTION\s+OF\s+GOODS?|GOODS?\s+DESCRIPTION)[:\s]+(.+?)' + sonraki_alan
                )

            for desen in desenler:
                try:
                    m = re.search(desen, metin, re.DOTALL | re.MULTILINE | re.IGNORECASE)
                    if m:
                        ham = m.group(1).strip()
                        if not ham:
                            continue
                        if alan in cok_satirli:
                            # Çok satırlı alanlarda iç satır sonlarını koru,
                            # sadece aşırı boşlukları temizle
                            deger = re.sub(r'[ \t]{2,}', ' ', ham)[:2000]
                        else:
                            deger = re.sub(r'\s+', ' ', ham)[:500]
                        if deger:
                            sonuc[alan] = deger
                            break
                except re.error:
                    continue

        # 44C alanı için ek fallback: tarih desenlerini doğrudan ara
        if "44C" not in sonuc:
            tarih_fallback = re.search(
                r'(?:LATEST\s+(?:DATE\s+(?:OF\s+)?)?SHIPMENT|SON\s+Y[UÜ]KLEME\s+TAR[Iİ]H[Iİ])'
                r'[:\s]*([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4}'
                r'|[\d]{1,2}\s+[A-Za-z]{3,9}\s+[\d]{4}'
                r'|[\d]{4}-[\d]{2}-[\d]{2})',
                metin, re.IGNORECASE
            )
            if tarih_fallback:
                sonuc["44C"] = tarih_fallback.group(1).strip()

        return sonuc

    # ------------------------------------------------------------------
    # Metin ayıklama
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu: str) -> str:
        if not dosya_yolu or not os.path.isfile(dosya_yolu):
            return ""

        ext   = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""

        try:
            if ext == ".pdf":
                if PdfReader is None:
                    return "[Hata: pypdf kütüphanesi yüklü değil]"
                reader = PdfReader(dosya_yolu)
                for i, sayfa in enumerate(reader.pages):
                    try:
                        txt = sayfa.extract_text()
                        if txt:
                            metin += txt + "\n"
                    except Exception as e:
                        metin += f"[Sayfa {i+1} Okuma Hatası: {e}]\n"

            elif ext in [".docx", ".doc"]:
                if docx is None:
                    return "[Hata: python-docx kütüphanesi yüklü değil]"
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
                    return "[Hata: openpyxl kütüphanesi yüklü değil]"
                wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
                for s in wb.sheetnames:
                    ws = wb[s]
                    for r in ws.iter_rows(values_only=True):
                        satir = " ".join(str(c) for c in r if c is not None)
                        if satir.strip():
                            metin += satir + "\n"

            elif ext in [".png", ".jpg", ".jpeg"]:
                if pytesseract is None or Image is None:
                    return "[Hata: pytesseract veya Pillow kütüphanesi yüklü değil]"
                try:
                    img = Image.open(dosya_yolu)
                    try:
                        ocr_sonuc = pytesseract.image_to_string(img, lang="eng+tur")
                    except pytesseract.TesseractError:
                        print(
                            f"[UYARI] Türkçe OCR dil paketi bulunamadı — "
                            f"'{os.path.basename(dosya_yolu)}' için yalnızca 'eng' kullanılıyor."
                        )
                        ocr_sonuc = pytesseract.image_to_string(img, lang="eng")
                    metin = ocr_sonuc or ""
                except pytesseract.TesseractError as e:
                    return f"[OCR Hatası: {e}]"

            elif ext == ".txt":
                with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
                    metin = f.read()
            else:
                return f"[Desteklenmeyen dosya formatı: {ext}]"

        except Exception as e:
            return f"[Dosya Okuma Hatası ({ext}): {e}]"

        metin = metin.replace("\xa0", " ").replace("\u200b", "").replace("\r\n", "\n")
        return metin

    # ------------------------------------------------------------------
    # Belge türü tespiti
    # ------------------------------------------------------------------
    def dokuman_tipi_belirle(self, metin: str) -> str:
        if not metin:
            return "DIGER"
        m = metin.upper()
        if any(x in m for x in ["DOCUMENTARY CREDIT", "40A:", "IRREVOCABLE", "L/C NO", "KÜŞAT", ":32B:"]):
            return "KUSAT"
        if any(x in m for x in ["COMMERCIAL INVOICE", "FATURA", "INVOICE NO", "INVOICE EXP"]):
            return "FATURA"
        if any(x in m for x in [
            "BILL OF LADING", "OCEAN BILL", "B/L NO", "SHIPPED ON BOARD",
            "KONŞİMENTO", "KONSIMENTO",
        ]):
            return "KONSIMENTO"
        if any(x in m for x in [
            "PACKING LIST", "CEKI LISTESI", "ÇEKİ LİSTESİ", "WEIGHT LIST", "PACKING DETAILS",
        ]):
            return "CEKI_LISTESI"
        if any(x in m for x in [
            "INSURANCE POLICY", "INSURANCE CERTIFICATE", "SİGORTA POLİÇESİ", "MARINE INSURANCE",
        ]):
            return "SIGORTA"
        return "DIGER"

    # ------------------------------------------------------------------
    # Depo tarama
    # ------------------------------------------------------------------
    def depoyu_tara_ve_analiz_et(self) -> bool:
        self.depo            = self._bos_depo()
        self.risk_puani      = 0
        self.uyumluluk_puani = 100
        self.mt700_alanlari  = {}

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
            dosya_adi = os.path.basename(d_yolu)
            icerik    = self.metin_ayikla(d_yolu)
            if not icerik or icerik.startswith("["):
                print(f"[UYARI] {dosya_adi} okunamadı veya boş: {icerik}")
                continue
            tip = self.dokuman_tipi_belirle(icerik)
            if tip in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]:
                self.depo[tip] = {"ad": dosya_adi, "metin": icerik}
            else:
                self.depo["DIGER_BELGELER"].append({"ad": dosya_adi, "metin": icerik})

        kusat_metni = self._depo_metin("KUSAT")
        if kusat_metni:
            self.mt700_alanlari = self.mt700_ayristir(kusat_metni)

        return True

    # ------------------------------------------------------------------
    # Sayısal değer çıkarma
    # ------------------------------------------------------------------
    def sayisal_deger_bul(self, metin: str, desenler: list[str]) -> Optional[float]:
        if not metin or not desenler:
            return None
        for desen in desenler:
            try:
                bulunan = re.findall(desen, metin, re.IGNORECASE)
                if bulunan:
                    val_str = str(bulunan[0]).replace(",", "").strip()
                    if val_str:
                        return float(val_str)
            except (ValueError, TypeError, re.error):
                continue
        return None

    def kilo_bul(self, metin: str) -> Optional[float]:
        if not metin:
            return None
        desenler = [
            r'(?:GROSS\s*WEIGHT|BRÜT\s*(?:KİLO|AĞIRLIK)|G\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT|TON)',
            r'(?:NET\s*WEIGHT|N\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT|TON)',
            r'([\d,\.]+)\s*KGS\b',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    def miktar_bul(self, metin: str) -> Optional[tuple[float, str]]:
        """Miktar ve birimi çıkarır; birim normalleştirme uygulanır."""
        if not metin:
            return None
        desen = r'([\d,\.]+)\s*(PCS|PIECES?|PIECE|KGS?|MT|TONS?|BOX(?:ES)?|CTNS?|CARTONS?|SETS?|UNITS?)\b'
        try:
            m = re.search(desen, metin, re.IGNORECASE)
            if m:
                deger = float(m.group(1).replace(",", ""))
                ham_birim = m.group(2).upper()
                birim = BIRIM_NORMALIZASYON.get(ham_birim, ham_birim)
                return (deger, birim)
        except (ValueError, re.error):
            pass
        return None

    def para_tutari_bul(self, metin: str) -> Optional[float]:
        if not metin:
            return None
        desenler = [
            r'32B[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            r'CREDIT\s+AMOUNT[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            r'(?:TOTAL\s+AMOUNT|INVOICE\s+VALUE|INVOICE\s+AMOUNT|TOTAL\s+VALUE)'
            r'\s*[:\-]?\s*(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)',
            r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    # ------------------------------------------------------------------
    # Tarih ayrıştırma — gerçek datetime dönüşümü
    # ------------------------------------------------------------------
    def tarih_ayristir(self, metin: str) -> Optional[datetime]:
        """
        Metindeki tarihi datetime nesnesine dönüştürür.
        Desteklenen formatlar:
            15.06.2026 | 15/06/2026 | 15-06-2026
            15 JUN 2026 | 15 JUNE 2026
            2026-06-15
        """
        if not metin:
            return None

        # DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY
        m = re.search(r'(\d{1,2})[.\-/](\d{2})[.\-/](\d{4})', metin)
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass

        # YYYY-MM-DD (ISO)
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', metin)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        # DD MON YYYY / DD MONTH YYYY
        m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', metin)
        if m:
            ay_str = m.group(2).upper()[:9]
            ay_no  = AY_ISIMLERI.get(ay_str)
            if ay_no:
                try:
                    return datetime(int(m.group(3)), ay_no, int(m.group(1)))
                except ValueError:
                    pass

        return None

    def tarih_bul(self, metin: str, desenler: list[str]) -> Optional[str]:
        """Ham tarih string'ini döner (geriye dönük uyumluluk için korundu)."""
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

    # ------------------------------------------------------------------
    # Mal tanımı çıkarma ve karşılaştırma
    # ------------------------------------------------------------------
    def mal_tanimi_bul(self, metin: str) -> Optional[str]:
        if not metin:
            return None
        if "45A" in self.mt700_alanlari:
            ham = self.mt700_alanlari["45A"].split("\n")[0].strip()
            if ham:
                return re.sub(r'\s+', ' ', ham)[:200]
        desenler = [
            r'45A[:\s]+(.+?)(?:\n[4-9]\d[A-Z]|\Z)',
            r'(?:DESCRIPTION\s+OF\s+GOODS?|MAL\s+TANIMI|GOODS?\s+DESCRIPTION)[:\s]+(.+?)(?:\n|$)',
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
        """Mal tanımı karşılaştırması için normalleştirme: büyük harf, noktalama temizliği."""
        if not metin:
            return ""
        metin = metin.upper()
        metin = re.sub(r'[^\w\s]', ' ', metin)   # noktalama → boşluk
        metin = re.sub(r'\s+', ' ', metin).strip()
        return metin

    def mal_tanimi_benzerlik(self, kaynak: str, hedef: str) -> float:
        """
        İki mal tanımı metni arasında kelime örtüşme oranı hesaplar.
        Normalleştirme uygulandıktan sonra 4+ karakterli kelimelere göre skoru döner.
        Döner: 0.0 – 1.0
        """
        n_kaynak = self._metin_normalize(kaynak)
        n_hedef  = self._metin_normalize(hedef)
        k_kelimeler = set(w for w in n_kaynak.split() if len(w) >= 4)
        h_kelimeler = set(w for w in n_hedef.split()  if len(w) >= 4)
        if not k_kelimeler:
            return 0.0
        ortak = k_kelimeler & h_kelimeler
        return len(ortak) / len(k_kelimeler)

    # ------------------------------------------------------------------
    # 46A Belge Şartları Motoru
    # ------------------------------------------------------------------
    def _46a_belge_sartlari_kontrol(self, sonuclar: dict[str, Any]) -> None:
        """
        MT700 Alan 46A içeriğini depodaki belgelerle karşılaştırır.
        Sonuçları sonuclar['belge_46a'] listesine yazar.
        """
        alan_46a = self.mt700_alanlari.get("46A", "")
        if not alan_46a:
            sonuclar["belge_46a"].append({
                "sart":  "Alan 46A",
                "detay": "MT700 Alan 46A tespit edilemedi.",
                "durum": "MANUEL KONTROL",
            })
            return

        # Tanınan belge türü kalıpları ve depodaki karşılıkları
        # Her tuple: (aranacak_ifade, depo_anahtari, gösterim_adı)
        kontrol_listesi = [
            ("COMMERCIAL INVOICE",                "FATURA",       "Ticari Fatura"),
            ("INVOICE",                           "FATURA",       "Ticari Fatura"),
            ("BILL OF LADING",                    "KONSIMENTO",   "Konşimento (B/L)"),
            ("PACKING LIST",                      "CEKI_LISTESI", "Çeki Listesi"),
            ("INSURANCE",                         "SIGORTA",      "Sigorta Poliçesi"),
        ]

        eslesmis_satirlar: set[str] = set()

        for sart_anahtar, depo_anahtari, gosterim_adi in kontrol_listesi:
            if sart_anahtar.upper() in alan_46a.upper():
                var_mi = self.depo.get(depo_anahtari) is not None
                durum  = "VAR" if var_mi else "EKSİK"
                if durum == "EKSİK":
                    self._risk_puani_ekle("46a_belge_eksigi")
                    self._uyumluluk_duş(10)
                    sonuclar["rezerv_ozeti"].append(
                        f"REZERV — 46A gereği '{gosterim_adi}' belgesi depoda bulunamadı"
                    )
                sonuclar["belge_46a"].append({
                    "sart":  gosterim_adi,
                    "detay": "Akreditif 46A'da talep edilmiş.",
                    "durum": durum,
                })
                eslesmis_satirlar.add(sart_anahtar.upper())

        # 46A'yı satır ve eğik çizgi ayraçlarıyla böl (çok satırlı OCR çıktısı dahil)
        separatörler = re.split(r'[\n/]+', alan_46a)
        for satir in separatörler:
            satir = satir.strip()
            if not satir:
                continue
            # Daha önce eşleştirilen kalıplar içeriyor mu?
            if any(k in satir.upper() for k in eslesmis_satirlar):
                continue
            # Hiçbir bilinen kalıpla eşleşmiyorsa manuel kontrol
            sonuclar["belge_46a"].append({
                "sart":  satir[:100],
                "detay": "Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli.",
                "durum": "MANUEL KONTROL",
            })

    # ------------------------------------------------------------------
    # ISBP 821 yorumlama katmanı
    # ------------------------------------------------------------------
    def _isbp_tablosu_olustur(self, sonuclar: dict[str, Any]) -> None:
        """
        Mevcut analiz bulgularına dayalı ISBP 821 yorum tablosunu oluşturur.
        Her rezerv hem UCP hem ISBP açısından yorumlanır.
        """
        tablo = sonuclar.get("isbp_tablosu", [])

        # Capraz kontrol ve zorunlu alanlardan ISBP eşleştirmesi yap
        for kayit in sonuclar.get("capraz_kontrol", []):
            durum = kayit.get("durum", "")
            belge = kayit.get("belge", "")

            if "Mal Tanımı" in belge or "Art 18" in belge:
                isbp = ISBP_ESLESTIRME["Art 18"]
                tablo.append({
                    "ucp_maddesi": "Art 18",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": f"{belge}: {durum}",
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })
            elif "Konşimento Yükleme" in belge or "Art 20" in belge:
                isbp = ISBP_ESLESTIRME["Art 20"]
                tablo.append({
                    "ucp_maddesi": "Art 20",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": f"{belge}: {durum}",
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })
            elif "Sigorta" in belge or "Art 28" in belge:
                isbp = ISBP_ESLESTIRME["Art 28"]
                tablo.append({
                    "ucp_maddesi": "Art 28",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": f"{belge}: {durum}",
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })
            elif "Tutar" in belge or "Art 30" in belge:
                isbp = ISBP_ESLESTIRME["Art 30"]
                tablo.append({
                    "ucp_maddesi": "Art 30",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": f"{belge}: {durum}",
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })

        for kayit in sonuclar.get("zorunlu_alanlar", []):
            kayit_u = kayit.upper()
            if "ART 27" in kayit_u or "TEMİZ" in kayit_u or "CLEAN" in kayit_u or "KLO" in kayit_u:
                isbp = ISBP_ESLESTIRME["Art 27"]
                tablo.append({
                    "ucp_maddesi": "Art 27",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": kayit,
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })
            elif "SHIPPED ON BOARD" in kayit_u or "ON BOARD" in kayit_u:
                isbp = ISBP_ESLESTIRME["Art 20"]
                tablo.append({
                    "ucp_maddesi": "Art 20",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": kayit,
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })

        # Geç yükleme rezervleri → Art 20
        for rezerv in sonuclar.get("rezerv_ozeti", []):
            if "GEÇ YÜKLEME" in rezerv.upper():
                isbp = ISBP_ESLESTIRME["Art 20"]
                tablo.append({
                    "ucp_maddesi": "Art 20",
                    "isbp_prensibi": isbp["prensip"],
                    "bulgu": rezerv,
                    "aciklama": isbp["aciklama"],
                    "oneri": isbp["oneri"],
                })
                break

        # 46A eksikliği → Art 14
        for rezerv in sonuclar.get("rezerv_ozeti", []):
            if "46A" in rezerv:
                isbp14 = ISBP_ESLESTIRME["Art 14"]
                tablo.append({
                    "ucp_maddesi": "Art 14",
                    "isbp_prensibi": isbp14["prensip"],
                    "bulgu": rezerv,
                    "aciklama": isbp14["aciklama"],
                    "oneri": isbp14["oneri"],
                })
                break

        # İbraz süresi her zaman Art 14 için ekle (genel kural)
        isbp14 = ISBP_ESLESTIRME["Art 14"]
        tablo.append({
            "ucp_maddesi": "Art 14",
            "isbp_prensibi": isbp14["prensip"],
            "bulgu": "Belge inceleme süresi uygulandı (UCP Art 14c — en fazla 21 iş günü).",
            "aciklama": isbp14["aciklama"],
            "oneri": isbp14["oneri"],
        })

        sonuclar["isbp_tablosu"] = tablo

    # ------------------------------------------------------------------
    # Uzman yardımcısı — rezerv başına çözüm önerisi
    # ------------------------------------------------------------------
    def _uzman_onerileri_olustur(self, sonuclar: dict[str, Any]) -> None:
        """Her rezerv için risk, banka itirazı, UCP/ISBP maddesi ve düzeltme önerisi üretir."""
        oneriler = []
        for rezerv in sonuclar.get("rezerv_ozeti", []):
            oneri: dict[str, str] = {"rezerv": rezerv}

            if "Sigorta belgesi eksik" in rezerv or "SİGORTA BELGESİ EKSİK" in rezerv:
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Banka, sigorta poliçesi ibraz edilmeden ödeme yapmayı reddedecektir.",
                    "ucp_maddesi":   "UCP 600 Art 28",
                    "isbp_prensibi": "ISBP 821 § K3, § K8",
                    "duzeltme":      "CIF/CIP teslimde orijinal sigorta poliçesini en az fatura bedelinin %110'u için temin edin.",
                    "tahmini_sure":  "2-3 Gün",
                })
            elif "Sigorta teminatı yetersiz" in rezerv:
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Banka, %110 altında teminat içeren sigorta belgesini reddedebilir.",
                    "ucp_maddesi":   "UCP 600 Art 28f-ii",
                    "isbp_prensibi": "ISBP 821 § K8",
                    "duzeltme":      "Sigorta şirketinden ek teminat endorsmanı alın veya poliçeyi yeniden düzenletin.",
                    "tahmini_sure":  "1-2 Gün",
                })
            elif "Tutar" in rezerv and "sapıyor" in rezerv:
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Fatura tutarı akreditif limitini aştığından banka ödeme yapmayacaktır.",
                    "ucp_maddesi":   "UCP 600 Art 18 / Art 30",
                    "isbp_prensibi": "ISBP 821 § B14",
                    "duzeltme":      "Akreditif tutarını artırın (amir nezdinde değişiklik) veya fatura tutarını tolerans sınırına çekin.",
                    "tahmini_sure":  "1-2 Gün",
                })
            elif "Kilo uyumsuzluğu" in rezerv:
                oneri.update({
                    "risk":          "ORTA",
                    "kategori":      "MEDIUM DISCREPANCY",
                    "banka_itiraz":  "Banka, belgelerdeki kilo uyumsuzluğunu rezerv olarak bildirebilir.",
                    "ucp_maddesi":   "UCP 600 Art 14 / Art 18",
                    "isbp_prensibi": "ISBP 821 § C10",
                    "duzeltme":      "Fatura ve konşimentodaki kilo değerlerini düzelterek eşleştirin.",
                    "tahmini_sure":  "1 Gün",
                })
            elif "Mal tanımı uyuşmazlığı" in rezerv:
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Banka, mal tanımı uyuşmazlığını UCP Art 18c kapsamında rezerv gerekçesi olarak kullanacaktır.",
                    "ucp_maddesi":   "UCP 600 Art 18c",
                    "isbp_prensibi": "ISBP 821 § C5, § C7",
                    "duzeltme":      "Faturadaki mal tanımını akreditifteki 45A alanıyla birebir eşleştirin.",
                    "tahmini_sure":  "1-2 Gün",
                })
            elif "GEÇ YÜKLEME" in rezerv or "yükleme tarihi" in rezerv.lower():
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Geç yükleme nedeniyle konşimento akreditifle uyumsuz sayılacak, ödeme reddedilebilir.",
                    "ucp_maddesi":   "UCP 600 Art 20 / Art 14c",
                    "isbp_prensibi": "ISBP 821 § E4, § E14",
                    "duzeltme":      "Akreditifin 44C alanında değişiklik talep edin veya yüklemeyi öne alın.",
                    "tahmini_sure":  "Akreditif değişikliği",
                })
            elif "Shipped on Board" in rezerv:
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "'Shipped on Board' şerhi olmayan konşimento, banka tarafından geçersiz sayılacaktır.",
                    "ucp_maddesi":   "UCP 600 Art 20a-ii",
                    "isbp_prensibi": "ISBP 821 § E11",
                    "duzeltme":      "Yükleme tarihini açıkça gösteren 'Shipped on Board' şerhini taşıyıcıdan talep edin.",
                    "tahmini_sure":  "1-3 Gün",
                })
            elif "Konşimento belgesi ibraz edilmemiş" in rezerv:
                oneri.update({
                    "risk":          "KRİTİK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Temel taşıma belgesi olmadan ödeme kesinlikle yapılmayacaktır.",
                    "ucp_maddesi":   "UCP 600 Art 20",
                    "isbp_prensibi": "ISBP 821 § E1, § E4",
                    "duzeltme":      "Tam set orijinal konşimentoyu (genellikle 3/3) bankaya ibraz edin.",
                    "tahmini_sure":  "3-5 Gün",
                })
            elif "temiz" in rezerv.lower() or "CLEAN" in rezerv:
                oneri.update({
                    "risk":          "YÜKSEK",
                    "kategori":      "MAJOR DISCREPANCY",
                    "banka_itiraz":  "Klozlu konşimento bankaca reddedilir.",
                    "ucp_maddesi":   "UCP 600 Art 27",
                    "isbp_prensibi": "ISBP 821 § E26, § E27",
                    "duzeltme":      "Taşıyıcıdan klozlar kaldırılmış temiz konşimento talep edin; gerekirse mal paketlemesini yenileyin.",
                    "tahmini_sure":  "3-7 Gün",
                })
            elif "46A" in rezerv:
                oneri.update({
                    "risk":          "ORTA",
                    "kategori":      "MEDIUM DISCREPANCY",
                    "banka_itiraz":  "Akreditifte talep edilen belgelerden biri eksik olduğundan banka ödemeyi reddedecektir.",
                    "ucp_maddesi":   "UCP 600 Art 14 / Art 16",
                    "isbp_prensibi": "ISBP 821 § A4, § A6",
                    "duzeltme":      "Eksik belgeyi temin ederek tam ibraz yapın.",
                    "tahmini_sure":  "1-2 Gün",
                })
            else:
                oneri.update({
                    "risk":          "BELİRSİZ",
                    "kategori":      "INFORMATIONAL",
                    "banka_itiraz":  "Tespit edilen sorunun banka tarafından rezerv olarak değerlendirilmesi mümkündür.",
                    "ucp_maddesi":   "UCP 600 Art 14-16",
                    "isbp_prensibi": "ISBP 821 § A1-A7",
                    "duzeltme":      "Belgeleri akreditif şartlarıyla karşılaştırarak manuel inceleme yapın.",
                    "tahmini_sure":  "Değişken",
                })

            oneriler.append(oneri)

        sonuclar["uzman_onerileri"] = oneriler

    # ------------------------------------------------------------------
    # Risk ve uyumluluk puan yönetimi — dinamik, kategori ağırlıklı
    # ------------------------------------------------------------------
    def _risk_puani_ekle(self, kategori: str) -> None:
        """Kategori ağırlığını kullanarak risk puanı ekler; banka kabul olasılığını günceller."""
        bilgi = REZERV_KATEGORILERI.get(kategori)
        if bilgi:
            self.risk_puani += bilgi["puan"]
            # MAJOR = -25%, MEDIUM = -10%, MINOR = -5%
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
    # Rezerv simülatörü — muhtemel SWIFT banka reddi metni
    # ------------------------------------------------------------------
    def _rezerv_simulatoru_olustur(self, sonuclar: dict[str, Any]) -> None:
        """
        Tespit edilen rezervler için bankanın yazacağı muhtemel SWIFT
        reddi mesajlarını üretir. sonuclar['rezerv_swift_metinleri'] listesine yazar.
        """
        swift_metinleri: list[str] = []
        for kategori in self._aktif_rezerv_kategorileri:
            sablon = REZERV_SWIFT_SABLONLARI.get(kategori)
            if sablon:
                swift_metinleri.append(sablon)

        # Kilo uyumsuzluğu ayrıca kontrol (kategori adı farklı olabilir)
        for r in sonuclar.get("rezerv_ozeti", []):
            if "kilo" in r.lower() and not any("kilo" in k for k in self._aktif_rezerv_kategorileri):
                swift_metinleri.append(REZERV_SWIFT_SABLONLARI.get("kilo_uyusmazligi", ""))

        sonuclar["rezerv_swift_metinleri"] = [t for t in swift_metinleri if t]

    # ------------------------------------------------------------------
    # MT700 tam alan analizi raporu
    # ------------------------------------------------------------------
    def _mt700_alan_analizi_olustur(self, sonuclar: dict[str, Any]) -> None:
        """
        Ayrıştırılan MT700 alanlarını okunabilir bir analizle raporlar.
        sonuclar['mt700_alan_analizi'] listesine yazar.
        """
        analiz: list[dict[str, str]] = []
        for alan_kodu, aciklama in MT700_ALAN_ACIKLAMALARI.items():
            deger = self.mt700_alanlari.get(alan_kodu)
            if deger:
                # 48 (ibraz süresi) özel kontrolü
                if alan_kodu == "48":
                    try:
                        gun = int(re.sub(r'[^0-9]', '', deger))
                        durum = "✔ UYGUN" if gun <= 21 else "⚠ UYARI — 21 GÜN SINIRINI AŞIYOR"
                    except ValueError:
                        gun = -1
                        durum = "? Ayrıştırılamadı"
                elif alan_kodu == "43P":
                    izin_verildi = any(x in deger.upper() for x in ["ALLOWED", "PERMITTED", "IZIN"])
                    yasak = any(x in deger.upper() for x in ["NOT ALLOWED", "PROHIBITED", "YASAK"])
                    durum = "✔ İZİNLİ" if izin_verildi else ("✖ YASAK" if yasak else "? İncelenmeli")
                elif alan_kodu == "43T":
                    izin_verildi = any(x in deger.upper() for x in ["ALLOWED", "PERMITTED"])
                    yasak = any(x in deger.upper() for x in ["NOT ALLOWED", "PROHIBITED"])
                    durum = "✔ İZİNLİ" if izin_verildi else ("✖ YASAK" if yasak else "? İncelenmeli")
                else:
                    durum = "✔ TESPİT EDİLDİ"
                analiz.append({
                    "alan":      alan_kodu,
                    "aciklama":  aciklama,
                    "deger":     deger[:120],
                    "durum":     durum,
                })
            else:
                # Zorunlu alanlar için uyarı
                zorunlu = {"20", "31D", "32B", "40A", "44C", "45A", "46A"}
                if alan_kodu in zorunlu:
                    analiz.append({
                        "alan":     alan_kodu,
                        "aciklama": aciklama,
                        "deger":    "—",
                        "durum":    "⚠ TESPİT EDİLEMEDİ — Manuel Kontrol",
                    })
        sonuclar["mt700_alan_analizi"] = analiz

    # ------------------------------------------------------------------
    # Tarih zinciri analizi
    # ------------------------------------------------------------------
    def _tarih_zinciri_olustur(self, sonuclar: dict[str, Any]) -> None:
        """
        Tüm belgelerdeki tarihleri çekerek kronolojik tutarlılık zinciri kurar.
        sonuclar['tarih_zinciri'] listesine yazar.
        """
        zincir: list[dict[str, str]] = []

        def tarih_karti(etiket: str, ham: Optional[str], dt: Optional[datetime],
                        referans_dt: Optional[datetime] = None,
                        referans_adi: str = "", gecmemeli: bool = True) -> dict[str, str]:
            if not ham:
                return {"etiket": etiket, "deger": "—",
                        "durum": "⚠ TESPİT EDİLEMEDİ",
                        "not": "OCR veya format sorunu olabilir — manuel doğrulama önerilir."}
            if not dt:
                return {"etiket": etiket, "deger": ham,
                        "durum": "? FORMAT TANINAMADI",
                        "not": f"Tarih metni okundu ancak datetime'a çevrilemedi: '{ham}'"}
            bilgi = {"etiket": etiket, "deger": dt.strftime("%d.%m.%Y"), "not": ""}
            if referans_dt and referans_adi:
                if gecmemeli:
                    if dt <= referans_dt:
                        bilgi["durum"] = f"✔ UYUMLU ({referans_adi}: {referans_dt.strftime('%d.%m.%Y')})"
                    else:
                        bilgi["durum"] = f"✖ REZERV — {referans_adi} aşıldı ({referans_dt.strftime('%d.%m.%Y')})"
                        bilgi["not"] = "Banka bu tarihi geç sevkiyat/ibraz gerekçesiyle reddedebilir."
                else:
                    if dt >= referans_dt:
                        bilgi["durum"] = f"✔ UYUMLU ({referans_adi}: {referans_dt.strftime('%d.%m.%Y')})"
                    else:
                        bilgi["durum"] = f"✖ REZERV — {referans_adi} öncesinde"
            else:
                bilgi["durum"] = "✔ TESPİT EDİLDİ"
            return bilgi

        kusat_text      = self._depo_metin("KUSAT")
        fatura_text     = self._depo_metin("FATURA")
        konsimento_text = self._depo_metin("KONSIMENTO")
        sigorta_text    = self._depo_metin("SIGORTA")

        # LC Son Geçerlilik Tarihi (31D)
        lc_31d_str = self.mt700_alanlari.get("31D")
        lc_31d_dt  = self.tarih_ayristir(lc_31d_str) if lc_31d_str else None
        zincir.append(tarih_karti("LC Son Geçerlilik (31D)", lc_31d_str, lc_31d_dt))

        # En Geç Yükleme Tarihi (44C)
        lc_44c_str = self.mt700_alanlari.get("44C")
        lc_44c_dt  = self.tarih_ayristir(lc_44c_str) if lc_44c_str else None
        zincir.append(tarih_karti("En Geç Yükleme (44C)", lc_44c_str, lc_44c_dt))

        # Fatura Tarihi
        fatura_tarih_str = self.tarih_bul(fatura_text, [
            r'(?:INVOICE\s+DATE|DATE\s+OF\s+INVOICE|DÜZENLEME\s+TARİHİ)[:\s]+'
            r'([\d]{1,2}[.\-/ ][A-Za-z\d]{2,9}[.\-/ ][\d]{4})',
            r'DATE[:\s]+([\d]{1,2}[.\-/][\d]{2}[.\-/][\d]{4})',
        ])
        fatura_tarih_dt = self.tarih_ayristir(fatura_tarih_str) if fatura_tarih_str else None
        zincir.append(tarih_karti(
            "Fatura Tarihi", fatura_tarih_str, fatura_tarih_dt,
            lc_31d_dt, "LC Geçerlilik", gecmemeli=True
        ))

        # Konşimento / Yükleme Tarihi
        bl_tarih_str = self.tarih_bul(konsimento_text, [
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}[.\-/][A-Z]{3,}[.\-/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE)[:\s]+'
            r'([\d]{2}[.\-/][\d]{2}[.\-/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE)[:\s]+'
            r'([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
        ])
        bl_tarih_dt = self.tarih_ayristir(bl_tarih_str) if bl_tarih_str else None
        zincir.append(tarih_karti(
            "Konşimento Yükleme Tarihi (B/L)", bl_tarih_str, bl_tarih_dt,
            lc_44c_dt, "44C Son Yükleme", gecmemeli=True
        ))

        # Sigorta Başlangıç Tarihi
        sig_tarih_str = self.tarih_bul(sigorta_text, [
            r'(?:DATE\s+OF\s+ISSUE|INSURANCE\s+DATE|COVERAGE\s+FROM)[:\s]+'
            r'([\d]{1,2}[.\-/ ][A-Za-z\d]{2,9}[.\-/ ][\d]{4})',
        ]) if sigorta_text else None
        sig_tarih_dt = self.tarih_ayristir(sig_tarih_str) if sig_tarih_str else None
        # Sigorta tarihi yükleme tarihinden geç olmamalı
        zincir.append(tarih_karti(
            "Sigorta Tarihi", sig_tarih_str, sig_tarih_dt,
            bl_tarih_dt, "Yükleme Tarihi", gecmemeli=False
        ))

        sonuclar["tarih_zinciri"] = zincir

    # ------------------------------------------------------------------
    # Tolerans hesaplama — dinamik (Art 30)
    # ------------------------------------------------------------------
    def _tolerans_hesapla(self, lc_miktar: Optional[float], fatura_miktar: Optional[float],
                          lc_metni: str = "") -> dict[str, Any]:
        """
        UCP 600 Art 30 uyarınca toleransı hesaplar.
        'about'/'approximately' varsa %10, yoksa %5 tolerans uygulanır.
        """
        if lc_miktar is None or fatura_miktar is None or lc_miktar == 0:
            return {"durum": "VERİ EKSİK", "sapma_yuzde": None, "tolerans": None}

        about_var = any(x in lc_metni.upper() for x in ["ABOUT", "APPROXIMATELY", "YAKLAŞIK"])
        tolerans_yuzde = 10 if about_var else 5
        sapma = fatura_miktar - lc_miktar
        sapma_yuzde = (sapma / lc_miktar) * 100

        sinir = lc_miktar * (tolerans_yuzde / 100)
        uyumlu = abs(sapma) <= sinir

        return {
            "lc_miktar":        lc_miktar,
            "fatura_miktar":    fatura_miktar,
            "sapma":            sapma,
            "sapma_yuzde":      round(sapma_yuzde, 2),
            "tolerans_yuzde":   tolerans_yuzde,
            "tolerans_tipi":    "±%10 (ABOUT/APPROXIMATELY)" if about_var else "±%5 (Standart)",
            "durum":            "UYUMLU" if uyumlu else "REZERV RİSKİ — TOLERANS AŞILDI",
        }

    # ------------------------------------------------------------------
    # OCR güven tahmini (heuristik)
    # ------------------------------------------------------------------
    @staticmethod
    def _ocr_guven_tahmini(metin: str, alan_adi: str) -> dict[str, Any]:
        """
        Metnin kalitesini basit heuristiklerle tahmin eder.
        Gerçek OCR güven skoru pytesseract'tan gelmiyorsa bu yöntem kullanılır.
        """
        if not metin:
            return {"guven": 0, "seviye": "YOK", "not": "Belge veya alan tespit edilemedi."}
        uzunluk = len(metin.strip())
        # Heuristik: çok kısa metin veya aşırı özel karakter
        ozel_oran = len(re.findall(r'[^\w\s.,;:\-\/()%\'\"@#]', metin)) / max(uzunluk, 1)
        if uzunluk < 10:
            guven, seviye = 30, "DÜŞÜK"
            not_ = "Çok kısa içerik — OCR atlaması veya format uyumsuzluğu olabilir."
        elif ozel_oran > 0.15:
            guven, seviye = 45, "DÜŞÜK"
            not_ = f"Yüksek özel karakter oranı (%{ozel_oran*100:.0f}) — OCR bozulması şüphesi."
        elif uzunluk < 30:
            guven, seviye = 60, "ORTA"
            not_ = "Kısa içerik — manuel doğrulama önerilir."
        else:
            guven, seviye = 85, "YÜKSEK"
            not_ = "İçerik yeterli uzunlukta ve makul karakter dağılımında."
        return {"guven": guven, "seviye": seviye, "not": not_, "alan": alan_adi}

    # ------------------------------------------------------------------
    # Yönetici özeti (Executive Summary)
    # ------------------------------------------------------------------
    def _yonetici_ozeti_olustur(self, sonuclar: dict[str, Any]) -> None:
        """
        Raporun en üstüne eklenecek yönetici özetini üretir.
        sonuclar['yonetici_ozeti'] sözlüğüne yazar.
        """
        rezervler = sonuclar.get("rezerv_ozeti", [])
        major_sayisi  = sum(1 for k in self._aktif_rezerv_kategorileri
                           if REZERV_KATEGORILERI.get(k, {}).get("kategori") == "MAJOR DISCREPANCY")
        medium_sayisi = sum(1 for k in self._aktif_rezerv_kategorileri
                           if REZERV_KATEGORILERI.get(k, {}).get("kategori") == "MEDIUM DISCREPANCY")
        minor_sayisi  = sum(1 for k in self._aktif_rezerv_kategorileri
                           if REZERV_KATEGORILERI.get(k, {}).get("kategori") == "MINOR DISCREPANCY")

        mevcut_belgeler = [k for k in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]
                           if self.depo.get(k)]
        toplam_belge = len(mevcut_belgeler)

        # En kritik sorun
        kritik_sorun = "Tespit edilmedi"
        if rezervler:
            for r in rezervler:
                if any(k in r.upper() for k in ["SİGORTA", "KONŞİMENTO", "GEÇ YÜKLEME", "TUTAR"]):
                    kritik_sorun = r[:120]
                    break
            if kritik_sorun == "Tespit edilmedi":
                kritik_sorun = rezervler[0][:120]

        sonuclar["yonetici_ozeti"] = {
            "toplam_belge":          toplam_belge,
            "mevcut_belgeler":       mevcut_belgeler,
            "eksik_belgeler":        sonuclar.get("eksik_belgeler", []),
            "toplam_rezerv":         len(rezervler),
            "major_rezerv":          major_sayisi,
            "medium_rezerv":         medium_sayisi,
            "minor_rezerv":          minor_sayisi,
            "uyumluluk_skoru":       self.uyumluluk_puani,
            "risk_puani":            self.risk_puani,
            "risk_sinifi":           self._risk_sinifi(),
            "banka_kabul_olasiligi": self._banka_kabul_olasiligi,
            "kritik_sorun":          kritik_sorun,
        }

    # ------------------------------------------------------------------
    # UCP tablosunu analiz sonuçlarından türet (dinamik)
    # ------------------------------------------------------------------
    def _dinamik_ucp_tablosu_olustur(self, sonuclar: dict[str, Any]) -> list[tuple[str, str, str, str]]:
        """
        UCP 600 tablosunu capraz_kontrol ve zorunlu_alanlar bulgularından türetir.
        Statik varsayımlara dayanmaz; her madde gerçek analiz sonucuyla eşlenir.
        """
        # Capraz kontrol sonuçlarından arama için indeks oluştur
        cc_durumlar: dict[str, str] = {}
        for kayit in sonuclar.get("capraz_kontrol", []):
            cc_durumlar[kayit.get("belge", "")] = kayit.get("durum", "")

        def cc_durum_bul(anahtar_listesi: list[str]) -> str:
            for anahtar in anahtar_listesi:
                for belge_adi, durum in cc_durumlar.items():
                    if anahtar.lower() in belge_adi.lower():
                        # Rezerv varsa kısa form
                        if "REZERV" in durum:
                            return "REZERV RİSKİ"
                        if "MANUEL" in durum:
                            return "MANUEL KONTROL"
                        if "UYUMLU" in durum or "TESPİT" in durum:
                            return "DOĞRUDAN GEÇTİ"
                        return durum
            return "DOĞRUDAN GEÇMİYOR"

        # Zorunlu alanlardan konşimento ve temiz B/L durumu
        bl_onboard_durum = "DOĞRUDAN GEÇMİYOR"
        art27_durum      = "DOĞRUDAN GEÇMİYOR"
        for satir in sonuclar.get("zorunlu_alanlar", []):
            satir_u = satir.upper()
            if "SHIPPED ON BOARD" in satir_u:
                bl_onboard_durum = "REZERV RİSKİ" if "REZERV" in satir_u else "DOĞRUDAN GEÇTİ"
            if "CLEAN" in satir_u or "TEMİZ" in satir_u or "KLO" in satir_u:
                if "REZERV" in satir_u:
                    art27_durum = "REZERV RİSKİ"
                elif "TAMAM" in satir_u:
                    art27_durum = "DOĞRUDAN GEÇTİ"
                else:
                    art27_durum = "MANUEL KONTROL"

        art18_durum = cc_durum_bul(["Mal Tanımı", "Akreditif Tutarı"])
        art20_durum = cc_durum_bul(["Konşimento Yükleme", "Konşimento Kilo"])
        if bl_onboard_durum != "DOĞRUDAN GEÇMİYOR":
            art20_durum = bl_onboard_durum
        art28_durum = cc_durum_bul(["Sigorta"])
        art30_durum = cc_durum_bul(["Akreditif Tutarı", "Miktar"])

        # İbraz süresi — vade_analizi'nden kontrol
        art14_durum = "DOĞRUDAN GEÇTİ"
        for satir in sonuclar.get("vade_analizi", []):
            if "tespit edilemedi" in satir.lower():
                art14_durum = "MANUEL KONTROL"
                break

        tablo: list[tuple[str, str, str, str]] = [
            ("Art 14", "Belgelerin İncelenmesi Standartları",
             art14_durum, "21 günlük banka ibraz süresi kısıtlaması uygulandı (Madde 14c)."),
            ("Art 15", "Uyumlu İbraz (Complying Presentation)",
             "MANUEL KONTROL", "Uyumlu ibrazın teyidi için bankayla doğrulama gerekir."),
            ("Art 17", "Orijinal Belgeler ve Suretler",
             "MANUEL KONTROL", "Banka ibrazında orijinal/suret kaşelerinin varlığı aranır."),
            ("Art 18", "Ticari Fatura (Commercial Invoice)",
             art18_durum, "Mal tanımı ve tutar uyumu analiz edildi (Art 18c)."),
            ("Art 20", "Konşimento (Bill of Lading)",
             art20_durum, "Shipped on Board şerhi, yükleme tarihi ve kilo denetimi yapıldı."),
            ("Art 27", "Temiz Taşıma Belgesi",
             art27_durum, "Kirli konşimento ifadeleri tarandı (Art 27)."),
            ("Art 28", "Sigorta Belgesi ve Kapsamı",
             art28_durum, "%110 teminat hesabı dahil sigorta uyumu analiz edildi."),
            ("Art 30", "Miktar ve Tutarda Toleranslar",
             art30_durum, "%5 tolerans kuralı uygulandı (Art 30b)."),
        ]

        # kurallar.json varsa zorunlu_kurallar ile zenginleştir
        try:
            with open("kurallar.json", "r", encoding="utf-8") as f:
                veri = json.load(f)
            mevcut = {row[0] for row in tablo}
            for kural in veri.get("zorunlu_kurallar", []):
                madde = kural.get("madde", "")
                if madde and madde not in mevcut:
                    tablo.append((
                        madde,
                        kural.get("aciklama", ""),
                        "ZORUNLU KURAL",
                        kural.get("anahtar", ""),
                    ))
                    mevcut.add(madde)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

        return tablo

    # ------------------------------------------------------------------
    # UCP 600 Kural Motoru
    # ------------------------------------------------------------------
    def ucp600_kural_motoru(self) -> None:
        """
        Depodaki belgeler üzerinde UCP 600 / ISBP 821 kurallarını uygular.
        UCP tablosu artık statik değil; analiz bulgularından dinamik olarak türetilir.
        """
        kusat_text      = self._depo_metin("KUSAT")
        fatura_text     = self._depo_metin("FATURA")
        konsimento_text = self._depo_metin("KONSIMENTO")
        ceki_text       = self._depo_metin("CEKI_LISTESI")
        sigorta_text    = self._depo_metin("SIGORTA")

        combined = (
            kusat_text + " " + fatura_text + " " +
            konsimento_text + " " + sigorta_text
        ).upper()

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
            # v6.0 yeni alanlar
            "mt700_alan_analizi":     [],
            "tarih_zinciri":          [],
            "rezerv_swift_metinleri": [],
            "yonetici_ozeti":         {},
            "rezerv_detay_listesi":   [],
        }

        # ================================================================
        # 1. Kritik Süreler ve Vade Analizi
        # ================================================================
        lc_44c_str: Optional[str] = self.mt700_alanlari.get("44C") or self.tarih_bul(
            kusat_text,
            [
                r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT|SON\s+YÜKLEME\s+TARİHİ)'
                r'[:\s]*([\d]{2}[.\-/][\d]{2}[.\-/][\d]{4})',
                r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT|SON\s+YÜKLEME\s+TARİHİ)'
                r'[:\s]*([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
            ],
        )

        if lc_44c_str:
            sonuclar["vade_analizi"].append(
                f"En Geç Yükleme Tarihi (Alan 44C): **{lc_44c_str}**"
            )
        else:
            sonuclar["vade_analizi"].append(
                "En Geç Yükleme Tarihi (Alan 44C): Belgeden tespit edilemedi — manuel kontrol gerekli."
            )

        ibraz_suresi = re.search(
            r'(\d+)\s*DAYS?\s*(?:AFTER|FOR\s+PRESENTATION)', combined, re.IGNORECASE
        )
        if ibraz_suresi:
            gun = int(ibraz_suresi.group(1))
            sonuclar["vade_analizi"].append(
                f"Bankaya İbraz Süresi: **{gun} gün** "
                "(UCP 600 Madde 14c'ye göre 21 günü aşamaz)."
            )
            if gun > 21:
                self._risk_puani_ekle("ibraz_suresi_belirsiz")
                self._uyumluluk_duş(10)
        else:
            sonuclar["vade_analizi"].append(
                "Bankaya İbraz Süresi: Belgeden tespit edilemedi — "
                "UCP 600 Madde 14c varsayılan 21 günlük limit uygulanır."
            )
            self._risk_puani_ekle("ibraz_suresi_belirsiz")
            self._uyumluluk_duş(5)

        # ================================================================
        # 2. Ödeme Vadesi
        # ================================================================
        if any(x in combined for x in ["AT SIGHT", "SIGHT PAYMENT", "BY SIGHT", "GÖRÜLDÜĞÜNDE"]):
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: **Görüldüğünde Ödemeli (At Sight)** — "
                "UCP 600 Art 15b uyarınca uyumlu ibrazda amir banka anında ödemekle yükümlüdür."
            )
        elif any(x in combined for x in ["DAYS AFTER", "DEFERRED PAYMENT", "BY ACCEPTANCE", "VADELİ"]):
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: **Vadeli / Kabul Kredili Akreditif** — "
                "Poliçe vade takvimini ve faiz taahhütlerini kontrol edin."
            )
        else:
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: Belgelerden tespit edilemedi — manuel kontrol önerilir."
            )

        # ================================================================
        # 3. Incoterms ve Sigorta Varlığı (UCP 600 Art 28)
        # ================================================================
        incoterm_var: Optional[str] = None
        for term in ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"]:
            if term in combined:
                incoterm_var = term
                sonuclar["incoterms"].append(
                    f"Incoterms Standardı: **{term} (ICC 2020 Rules)**"
                )
                break

        if incoterm_var is None:
            sonuclar["incoterms"].append(
                "Incoterms Standardı: Metinden tespit edilemedi — manuel kontrol önerilir."
            )

        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                sonuclar["incoterms"].append(
                    f"[TAMAM] {incoterm_var} şartı gereği Resmi Sigorta Poliçesi saptandı (UCP 600 Art 28)."
                )
            else:
                sonuclar["incoterms"].append(
                    f"[HUKUKİ REZERV RİSKİ] Teslim şekli {incoterm_var} olmasına rağmen "
                    "Sigorta Poliçesi bulunamadı!"
                )
                self._risk_puani_ekle("sigorta_eksik")
                self._uyumluluk_duş(20)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Sigorta belgesi eksik ({incoterm_var} teslimde Art 28 zorunluluğu)"
                )
                sonuclar["eksik_belgeler"].append("Sigorta Poliçesi (CIF/CIP zorunlu)")

        # ================================================================
        # 4. Sayısal ve Evrak Çapraz Kontrolleri
        # ================================================================

        # --- 4a. Fatura Tutarı ↔ Akreditif Tutarı ---
        fatura_tutari: Optional[float] = self.para_tutari_bul(fatura_text)
        lc_32b_str = self.mt700_alanlari.get("32B")
        lc_tutari: Optional[float] = None
        if lc_32b_str:
            try:
                temiz = re.sub(r'[^0-9\.]', '', lc_32b_str.replace(",", ""))
                lc_tutari = float(temiz) if temiz else None
            except ValueError:
                lc_tutari = None
        if lc_tutari is None:
            lc_tutari = self.para_tutari_bul(kusat_text)

        if fatura_tutari is not None and lc_tutari is not None:
            tol = self._tolerans_hesapla(lc_tutari, fatura_tutari, kusat_text)
            detay = (
                f"LC: {lc_tutari:,.2f} | Fatura: {fatura_tutari:,.2f} | "
                f"Sapma: {tol['sapma_yuzde']:+.1f}% | "
                f"Tolerans: {tol['tolerans_tipi']}"
            )
            if tol["durum"] == "UYUMLU":
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                    "detay": detay,
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                    "detay": detay,
                    "durum": "REZERV RİSKİ - TUTAR UYUŞMAZLIĞI",
                })
                self._risk_puani_ekle("tutar_uyusmazligi")
                self._uyumluluk_duş(20)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Fatura tutarı ({fatura_tutari:,.2f}) akreditif tutarından "
                    f"({lc_tutari:,.2f}) {abs(tol['sapma']):,.2f} sapıyor, "
                    f"{tol['tolerans_tipi']} aşıyor (Art 30)"
                )
        else:
            eksik_t = [k for k, v in [("Fatura", fatura_tutari), ("Akreditif (32B)", lc_tutari)] if v is None]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                "detay": f"Tutar tespit edilemedi: {', '.join(eksik_t)}",
                "durum": "MANUEL KONTROL",
            })

        # --- 4b. Kilo — Fatura ↔ Konşimento ---
        fatura_kilo: Optional[float] = self.kilo_bul(fatura_text)
        bl_kilo:     Optional[float] = self.kilo_bul(konsimento_text)
        ceki_kilo:   Optional[float] = self.kilo_bul(ceki_text)

        if fatura_kilo is not None and bl_kilo is not None:
            if abs(fatura_kilo - bl_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Konşimento Kilo",
                    "detay": f"Brüt Kilo Eşleşmesi: {fatura_kilo:,.2f} KG",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Konşimento Kilo",
                    "detay": f"Fatura: {fatura_kilo:,.2f} KG | Konşimento: {bl_kilo:,.2f} KG",
                    "durum": "REZERV RİSKİ - UYUMSUZ SAYISAL VERİ",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")
                self._uyumluluk_duş(10)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Kilo uyumsuzluğu: Fatura {fatura_kilo:,.2f} KG / Konşimento {bl_kilo:,.2f} KG"
                )
        else:
            eksik = [k for k, v in [("Fatura", fatura_kilo), ("Konşimento", bl_kilo)] if v is None]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura vs Konşimento Kilo",
                "detay": f"Brüt kilo değeri tespit edilemedi: {', '.join(eksik)}",
                "durum": "VERİ EKSİK - MANUEL KONTROL GEREKLİ",
            })

        # --- 4c. Kilo — Fatura ↔ Çeki Listesi ---
        if ceki_kilo is not None and fatura_kilo is not None:
            if abs(ceki_kilo - fatura_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Çeki Listesi Kilo",
                    "detay": f"Brüt Kilo Eşleşmesi: {ceki_kilo:,.2f} KG",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Çeki Listesi Kilo",
                    "detay": f"Fatura: {fatura_kilo:,.2f} KG | Çeki Listesi: {ceki_kilo:,.2f} KG",
                    "durum": "REZERV RİSKİ - UYUMSUZ SAYISAL VERİ",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")
                self._uyumluluk_duş(8)

        # --- 4d. Miktar — Fatura ↔ Çeki Listesi (birim normalleştirme ile) ---
        fatura_miktar = self.miktar_bul(fatura_text)
        ceki_miktar   = self.miktar_bul(ceki_text)

        if fatura_miktar and ceki_miktar:
            f_deger, f_birim = fatura_miktar
            c_deger, c_birim = ceki_miktar
            # Normalleştirilmiş birim karşılaştırması
            f_birim_n = BIRIM_NORMALIZASYON.get(f_birim, f_birim)
            c_birim_n = BIRIM_NORMALIZASYON.get(c_birim, c_birim)
            if f_birim_n == c_birim_n and abs(f_deger - c_deger) < 1:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Çeki Listesi Miktar",
                    "detay": f"Miktar Eşleşmesi: {f_deger:,.0f} {f_birim_n}",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Çeki Listesi Miktar",
                    "detay": f"Fatura: {f_deger:,.0f} {f_birim_n} | Çeki: {c_deger:,.0f} {c_birim_n}",
                    "durum": "REZERV RİSKİ - MİKTAR UYUŞMAZLIĞI",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")
                self._uyumluluk_duş(8)

        # --- 4e. Mal Tanımı — Fatura ↔ Küşat (Art 18c) — geliştirilmiş benzerlik ---
        fatura_mal: Optional[str] = self.mal_tanimi_bul(fatura_text)
        kusat_mal:  Optional[str] = self.mal_tanimi_bul(kusat_text)

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
                    f"REZERV — Mal tanımı uyuşmazlığı: Örtüşme %{oran*100:.0f} (Art 18c)"
                )

            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura Mal Tanımı vs Küşat (Art 18c)",
                "detay": (
                    f"Küşat: '{kusat_mal[:80]}' | "
                    f"Fatura: '{fatura_mal[:80]}' | "
                    f"Benzerlik: %{oran*100:.0f}"
                ),
                "durum": durum_mal,
            })
        else:
            eksik_mal = [k for k, v in [("Fatura", fatura_mal), ("Küşat (45A)", kusat_mal)] if not v]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura Mal Tanımı vs Küşat (Art 18c)",
                "detay": f"Mal tanımı tespit edilemedi: {', '.join(eksik_mal)}",
                "durum": "MANUEL KONTROL",
            })

        # --- 4f. Konşimento Yükleme Tarihi ↔ Alan 44C — gerçek tarih karşılaştırması ---
        bl_tarih_desenler = [
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}[.\-/][A-Z]{3,}[.\-/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{2}[.\-/][\d]{2}[.\-/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
        ]
        lc_44c_desenler = [
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}[.\-/][A-Z]{3,}[.\-/][\d]{4})',
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{2}[.\-/][\d]{2}[.\-/][\d]{4})',
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}\s+[A-Z]{3,}\s+[\d]{4})',
        ]

        bl_tarih_str   = self.tarih_bul(konsimento_text, bl_tarih_desenler)
        lc_tarih_str   = lc_44c_str or self.tarih_bul(kusat_text, lc_44c_desenler)
        bl_tarih_dt    = self.tarih_ayristir(bl_tarih_str) if bl_tarih_str else None
        lc_tarih_dt    = self.tarih_ayristir(lc_tarih_str) if lc_tarih_str else None

        if bl_tarih_dt and lc_tarih_dt:
            if bl_tarih_dt <= lc_tarih_dt:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                    "detay": f"Konşimento: {bl_tarih_str} ≤ 44C: {lc_tarih_str}",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                    "detay": f"Konşimento: {bl_tarih_str} > 44C: {lc_tarih_str} — GEÇ YÜKLEME!",
                    "durum": "REZERV RİSKİ - GEÇ YÜKLEME",
                })
                self._risk_puani_ekle("gec_yukleme")
                self._uyumluluk_duş(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — GEÇ YÜKLEME: Konşimento tarihi ({bl_tarih_str}) "
                    f"44C son yükleme tarihini ({lc_tarih_str}) aşıyor (Art 20)"
                )
        elif bl_tarih_str and lc_tarih_str:
            # Ayrıştırma başarısız, ham string göster
            sonuclar["capraz_kontrol"].append({
                "belge":  "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                "detay": f"Konşimento: {bl_tarih_str} | 44C: {lc_tarih_str} — Tarih formatı tanınamadı",
                "durum": "MANUEL KONTROL",
            })
        else:
            eksik_t2 = [
                k for k, v in [
                    ("Konşimento yükleme tarihi", bl_tarih_str),
                    ("Küşat 44C", lc_tarih_str),
                ] if not v
            ]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                "detay": f"Tarih tespit edilemedi: {', '.join(eksik_t2)}",
                "durum": "MANUEL KONTROL",
            })
            if not bl_tarih_str and konsimento_text:
                self._risk_puani_ekle("yukleme_tarihi_ihlali")
                self._uyumluluk_duş(15)
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — Konşimento yükleme tarihi tespit edilemedi (Art 20)"
                )

        # --- 4g. Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii) ---
        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                sigorta_tutari = self.para_tutari_bul(sigorta_text)
                if sigorta_tutari is not None and fatura_tutari is not None:
                    minimum_teminat = fatura_tutari * 1.10
                    if sigorta_tutari >= minimum_teminat:
                        sonuclar["capraz_kontrol"].append({
                            "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                            "detay": f"Sigorta: {sigorta_tutari:,.2f} | Gerekli Min.: {minimum_teminat:,.2f}",
                            "durum": "UYUMLU",
                        })
                    else:
                        eksik_teminat = minimum_teminat - sigorta_tutari
                        sonuclar["capraz_kontrol"].append({
                            "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                            "detay": (
                                f"Sigorta: {sigorta_tutari:,.2f} | "
                                f"Gerekli Min.: {minimum_teminat:,.2f} | "
                                f"Eksik: {eksik_teminat:,.2f}"
                            ),
                            "durum": "REZERV RİSKİ - YETERSİZ SİGORTA TEMİNATI",
                        })
                        self._risk_puani_ekle("sigorta_eksik")
                        self._uyumluluk_duş(20)
                        sonuclar["rezerv_ozeti"].append(
                            f"REZERV — Sigorta teminatı yetersiz: {sigorta_tutari:,.2f} < "
                            f"gerekli {minimum_teminat:,.2f} (Art 28f-ii)"
                        )
                elif fatura_tutari is not None:
                    sonuclar["capraz_kontrol"].append({
                        "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                        "detay": f"Sigorta belgesi mevcut ancak tutar okunamadı. Gerekli min: {fatura_tutari * 1.10:,.2f}",
                        "durum": "MANUEL KONTROL",
                    })
                else:
                    sonuclar["capraz_kontrol"].append({
                        "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                        "detay": "Sigorta veya fatura tutarı tespit edilemedi.",
                        "durum": "MANUEL KONTROL",
                    })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                    "detay": f"{incoterm_var} teslimlerde sigorta poliçesi zorunludur ancak bulunamadı.",
                    "durum": "REZERV RİSKİ - SİGORTA BELGESİ EKSİK",
                })

        # ================================================================
        # 5. Konşimento Hukuki Maddeleri — Art 20 ve Art 27 (geliştirilmiş)
        # ================================================================
        if not konsimento_text:
            sonuclar["zorunlu_alanlar"].append(
                "[REZERV RİSKİ] Konşimento belgesi depoda bulunamadı!"
            )
            self._risk_puani_ekle("konsimento_eksik")
            self._uyumluluk_duş(30)
            sonuclar["rezerv_ozeti"].append(
                "REZERV — Konşimento belgesi ibraz edilmemiş (Art 20)"
            )
            sonuclar["eksik_belgeler"].append("Konşimento (Bill of Lading)")
        else:
            bl_upper = konsimento_text.upper()

            # Art 20 — Shipped on Board
            if "SHIPPED ON BOARD" in bl_upper or "ON BOARD" in bl_upper:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Konşimento üzerinde 'Shipped on Board' şerhi saptandı (Art 20a-ii uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[REZERV RİSKİ] Konşimentoda zorunlu 'Shipped on Board' yükleme şerhi bulunamadı!"
                )
                self._risk_puani_ekle("konsimento_eksik")
                self._uyumluluk_duş(20)
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — 'Shipped on Board' şerhi tespit edilemedi (Art 20a-ii)"
                )

            # Art 27 — Temiz konşimento: kirli ifade taraması
            kirli_ifade_bulunan = [
                ifade for ifade in KIRLI_BL_IFADELERI
                if ifade in bl_upper
            ]
            if kirli_ifade_bulunan:
                sonuclar["zorunlu_alanlar"].append(
                    f"[REZERV RİSKİ] Konşimentoda kirli/klozlu ifade tespit edildi: "
                    f"{', '.join(kirli_ifade_bulunan)} — Art 27 Temiz Taşıma Belgesi şartı ihlali!"
                )
                self._risk_puani_ekle("temiz_bl_sorunu")
                self._uyumluluk_duş(25)
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Klozlu konşimento tespit edildi ({', '.join(kirli_ifade_bulunan)}) (Art 27)"
                )
            elif "CLEAN" in bl_upper:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] 'CLEAN' şerhi saptandı — Temiz Taşıma Belgesi (Art 27 uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[BİLGİ] 'CLEAN' ibaresi bulunamadı ancak kirli konşimento ifadesi de yok — "
                    "Art 27 kapsamında TEMİZ KONŞİMENTO - MANUEL DOĞRULAMA önerilir."
                )

        # Eksik temel belgeler özeti
        for anahtar, ad in [
            ("KUSAT",       "Küşat (MT700 Akreditif)"),
            ("FATURA",      "Ticari Fatura"),
            ("CEKI_LISTESI","Çeki Listesi / Packing List"),
        ]:
            if not self.depo[anahtar]:
                sonuclar["eksik_belgeler"].append(ad)

        # ================================================================
        # 6. 46A Belge Şartları Kontrolü
        # ================================================================
        self._46a_belge_sartlari_kontrol(sonuclar)

        # ================================================================
        # 7. Risk Özeti ve Uyumluluk Skoru
        # ================================================================
        risk_sinifi = self._risk_sinifi()
        sonuclar["risk_ozeti"].append(
            f"Toplam Risk Puanı: **{self.risk_puani}** — Risk Sınıfı: **{risk_sinifi}**"
        )
        sonuclar["risk_ozeti"].append(
            f"Uyumluluk Skoru: **%{self.uyumluluk_puani}**"
        )
        if not sonuclar["rezerv_ozeti"]:
            sonuclar["risk_ozeti"].append(
                "Sistem tarafından tespit edilen kritik rezerv bulunamadı."
            )
        else:
            for i, rezerv in enumerate(sonuclar["rezerv_ozeti"], 1):
                sonuclar["risk_ozeti"].append(f"{i}. {rezerv}")

        # ================================================================
        # 8. UCP 600 Tablosu — dinamik türetme
        # ================================================================
        if HUKUK_MOTORU_AKTIF and hukuk_motoru_analiz_et is not None:
            try:
                motor_sonuc = hukuk_motoru_analiz_et(self.depo)
                if isinstance(motor_sonuc, list) and motor_sonuc:
                    sonuclar["ucp_tablosu"] = motor_sonuc
                elif isinstance(motor_sonuc, dict):
                    ucp_t = motor_sonuc.get("ucp_tablosu") or []
                    for alan in ("vade_analizi", "finansal_durum", "incoterms",
                                 "capraz_kontrol", "zorunlu_alanlar"):
                        if motor_sonuc.get(alan):
                            sonuclar[alan] = motor_sonuc[alan]
                    if ucp_t:
                        sonuclar["ucp_tablosu"] = ucp_t
                    else:
                        raise ValueError("hukuk_motoru 'ucp_tablosu' anahtarı boş döndürdü.")
                else:
                    raise ValueError("hukuk_motoru tanımsız tip döndürdü.")
            except Exception as e:
                print(f"[UYARI] Hukuk motoru hatası, dinamik tablo kullanılıyor: {e}")
                sonuclar["ucp_tablosu"] = self._dinamik_ucp_tablosu_olustur(sonuclar)
        else:
            if not HUKUK_MOTORU_AKTIF:
                print("[BİLGİ] hukuk_motoru.py bulunamadı, dinamik UCP tablosu kullanılıyor.")
            sonuclar["ucp_tablosu"] = self._dinamik_ucp_tablosu_olustur(sonuclar)

        # ================================================================
        # 9. ISBP 821 Katmanı ve Uzman Önerileri
        # ================================================================
        self._isbp_tablosu_olustur(sonuclar)
        self._uzman_onerileri_olustur(sonuclar)

        # ================================================================
        # 10. v6.0 — MT700 Alan Analizi
        # ================================================================
        self._mt700_alan_analizi_olustur(sonuclar)

        # ================================================================
        # 11. v6.0 — Tarih Zinciri Analizi
        # ================================================================
        self._tarih_zinciri_olustur(sonuclar)

        # ================================================================
        # 12. v6.0 — Rezerv Kategorileri ve Detay Listesi
        # ================================================================
        rezerv_detaylar: list[dict[str, str]] = []
        for kat_key in self._aktif_rezerv_kategorileri:
            kat_bilgi = REZERV_KATEGORILERI.get(kat_key, {})
            rezerv_detaylar.append({
                "kategori_kodu": kat_key,
                "kategori":      kat_bilgi.get("kategori", "BELİRSİZ"),
                "puan":          str(kat_bilgi.get("puan", "?")),
                "tahmini_sure":  kat_bilgi.get("sure", "?"),
            })
        sonuclar["rezerv_detay_listesi"] = rezerv_detaylar

        # ================================================================
        # 13. v6.0 — Rezerv Simülatörü (SWIFT Banka Metinleri)
        # ================================================================
        self._rezerv_simulatoru_olustur(sonuclar)

        # ================================================================
        # 14. v6.0 — Yönetici Özeti (Executive Summary)
        # ================================================================
        self._yonetici_ozeti_olustur(sonuclar)

        self.analiz_verisi = sonuclar

    # ------------------------------------------------------------------
    # Rapor yardımcıları — ortak HTML tablo oluşturucu
    # ------------------------------------------------------------------
    @staticmethod
    def _html_tablo(basliklar: list[str], satirlar: list[list[str]]) -> str:
        th = "".join(f"<th>{b}</th>" for b in basliklar)
        gövde = "".join(
            "<tr>" + "".join(f"<td>{h}</td>" for h in satir) + "</tr>"
            for satir in satirlar
        )
        return f"<table><tr>{th}</tr>{gövde}</table>"

    # ------------------------------------------------------------------
    # Markdown raporu
    # ------------------------------------------------------------------
    def markdown_raporu_olustur(self) -> None:
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, Markdown raporu oluşturulamadı.")
            return

        md_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")
        s = []
        s.append("# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU\n")
        s.append(f"**Analiz Zamanı:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  \n")
        s.append("**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP 821 Hukuk Motoru v6.0  \n\n")
        s.append("---\n")

        # ---- Yönetici Özeti ----
        oz = v.get("yonetici_ozeti", {})
        if oz:
            s.append("## 🏦 YÖNETİCİ ÖZETİ (Executive Summary)\n\n")
            s.append(f"| Metrik | Değer |\n| :--- | :--- |\n")
            s.append(f"| Toplam Belge | {oz.get('toplam_belge', '?')} |\n")
            s.append(f"| Mevcut Belgeler | {', '.join(oz.get('mevcut_belgeler', []))} |\n")
            eksik_list = oz.get('eksik_belgeler', [])
            s.append(f"| Eksik Belgeler | {', '.join(eksik_list) if eksik_list else '—'} |\n")
            s.append(f"| Tespit Edilen Rezerv | {oz.get('toplam_rezerv', 0)} |\n")
            s.append(f"| MAJOR Discrepancy | {oz.get('major_rezerv', 0)} |\n")
            s.append(f"| MEDIUM Discrepancy | {oz.get('medium_rezerv', 0)} |\n")
            s.append(f"| MINOR Discrepancy | {oz.get('minor_rezerv', 0)} |\n")
            s.append(f"| Uyumluluk Skoru | **%{oz.get('uyumluluk_skoru', '?')}** |\n")
            s.append(f"| Risk Puanı | {oz.get('risk_puani', '?')} — {oz.get('risk_sinifi', '?')} |\n")
            s.append(f"| Banka Kabul Olasılığı | **%{oz.get('banka_kabul_olasiligi', '?')}** |\n")
            s.append(f"| En Kritik Sorun | {oz.get('kritik_sorun', '—')} |\n")
            s.append("\n---\n")

        # ---- MT700 Alan Analizi ----
        mt_analiz = v.get("mt700_alan_analizi", [])
        if mt_analiz:
            s.append("## 📡 MT700 ALAN ANALİZİ\n\n")
            s.append("| Alan | Açıklama | Değer | Durum |\n| :--- | :--- | :--- | :--- |\n")
            for a in mt_analiz:
                s.append(
                    f"| **{a.get('alan','')}** | {a.get('aciklama','')} | "
                    f"`{a.get('deger','')}` | {a.get('durum','')} |\n"
                )
            s.append("\n---\n")

        # ---- Tarih Zinciri ----
        tarih_z = v.get("tarih_zinciri", [])
        if tarih_z:
            s.append("## 📅 TARİH ZİNCİRİ ANALİZİ\n\n")
            s.append("| Belge / Alan | Tarih | Durum | Not |\n| :--- | :--- | :--- | :--- |\n")
            for t in tarih_z:
                s.append(
                    f"| {t.get('etiket','')} | {t.get('deger','—')} | "
                    f"**{t.get('durum','')}** | {t.get('not','')} |\n"
                )
            s.append("\n---\n")

        s.append("## 1. Kritik Süreler ve Vade Analizi\n")
        for x in v.get("vade_analizi", []):   s.append(f"* {x}\n")

        s.append("\n---\n## 2. Finansal Vade ve Ödeme Takvimi\n")
        for x in v.get("finansal_durum", []): s.append(f"* {x}\n")

        s.append("\n---\n## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)\n")
        for x in v.get("incoterms", []):      s.append(f"* {x}\n")

        s.append(
            "\n---\n## 4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü\n"
            "| Belgeler | İnceleme Detayı | Durum |\n| :--- | :--- | :--- |\n"
        )
        for c in v.get("capraz_kontrol", []):
            s.append(f"| {c.get('belge','')} | {c.get('detay','')} | **[{c.get('durum','')}]** |\n")

        s.append("\n---\n## 5. Konşimento ve Taşıma Hukuku Parametreleri (UCP Art. 20-27)\n")
        for x in v.get("zorunlu_alanlar", []): s.append(f"* {x}\n")

        s.append("\n---\n## 6. 46A Belge Şartları Kontrolü\n")
        s.append("| Talep Edilen Belge | Detay | Durum |\n| :--- | :--- | :--- |\n")
        for b in v.get("belge_46a", []):
            s.append(f"| {b.get('sart','')} | {b.get('detay','')} | **[{b.get('durum','')}]** |\n")

        s.append(
            "\n---\n## 7. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu\n"
            "| UCP 600 Madde | Kapsam Açıklaması | Sistem Geçiş Durumu | Uzman Bulgusu |\n"
            "| :--- | :--- | :--- | :--- |\n"
        )
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                s.append(f"| **{m[0]}** | {m[1]} | `{m[2]}` | {m[3]} |\n")

        s.append("\n---\n## 8. ISBP 821 Yorum Tablosu\n")
        s.append("| UCP Maddesi | ISBP Prensibi (Paragraf) | Bulgu | Öneri |\n| :--- | :--- | :--- | :--- |\n")
        for i in v.get("isbp_tablosu", []):
            s.append(
                f"| **{i.get('ucp_maddesi','')}** | {i.get('isbp_prensibi','')} | "
                f"{i.get('bulgu','')} | {i.get('oneri','')} |\n"
            )

        s.append("\n---\n## 9. Tespit Edilen Kritik Rezervler ve Uzman Önerileri\n")
        for o in v.get("uzman_onerileri", []):
            s.append(f"\n### Rezerv: {o.get('rezerv','')}\n")
            s.append(f"* **Kategori:** {o.get('kategori','')}\n")
            s.append(f"* **Risk Seviyesi:** {o.get('risk','')}\n")
            s.append(f"* **Muhtemel Banka İtirazı:** {o.get('banka_itiraz','')}\n")
            s.append(f"* **İlgili UCP Maddesi:** {o.get('ucp_maddesi','')}\n")
            s.append(f"* **İlgili ISBP Prensibi:** {o.get('isbp_prensibi','')}\n")
            s.append(f"* **Düzeltme Önerisi:** {o.get('duzeltme','')}\n")
            s.append(f"* **Tahmini Çözüm Süresi:** {o.get('tahmini_sure','')}\n")

        # ---- Rezerv Kategorileri ----
        detaylar = v.get("rezerv_detay_listesi", [])
        if detaylar:
            s.append("\n---\n## 10. Rezerv Kategorileri\n\n")
            s.append("| Kategori | Sınıf | Risk Puanı | Tahmini Çözüm Süresi |\n| :--- | :--- | :--- | :--- |\n")
            for d in detaylar:
                s.append(
                    f"| {d.get('kategori_kodu','')} | **{d.get('kategori','')}** | "
                    f"{d.get('puan','')} | {d.get('tahmini_sure','')} |\n"
                )

        s.append("\n---\n## 11. Eksik Belgeler Özeti\n")
        eksik = v.get("eksik_belgeler", [])
        if eksik:
            for e in eksik: s.append(f"* ❌ {e}\n")
        else:
            s.append("* ✅ Zorunlu belgeler sistemde mevcut.\n")

        s.append("\n---\n## 12. Risk Değerlendirmesi ve Uyumluluk Skoru\n")
        for x in v.get("risk_ozeti", []): s.append(f"* {x}\n")

        # ---- Rezerv Simülatörü ----
        swift_metinleri = v.get("rezerv_swift_metinleri", [])
        if swift_metinleri:
            s.append("\n---\n## 🏛 REZERV SİMÜLATÖRÜ — Muhtemel Banka SWIFT Ret Metinleri\n\n")
            s.append("> Aşağıdaki metinler, bankanın MT734/MT750 mesajında yazabileceği\n")
            s.append("> muhtemel rezerv ifadelerini simüle etmektedir.\n\n")
            for i, mt in enumerate(swift_metinleri, 1):
                s.append(f"### Simüle Edilen Ret Metni {i}\n\n```\n{mt}\n```\n\n")

        with open(md_yolu, "w", encoding="utf-8") as f:
            f.writelines(s)
        print("[+] Markdown Raporu Oluşturuldu.")

    # ------------------------------------------------------------------
    # HTML raporu
    # ------------------------------------------------------------------
    def html_raporu_olustur(self) -> None:
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, HTML raporu oluşturulamadı.")
            return

        html_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.html")

        def li(anahtar: str) -> str:
            return "".join(f"<li>{x}</li>" for x in v.get(anahtar, []))

        capraz = "".join(
            f"<tr><td><b>{r.get('belge','')}</b></td>"
            f"<td>{r.get('detay','')}</td>"
            f"<td><b>{r.get('durum','')}</b></td></tr>"
            for r in v.get("capraz_kontrol", [])
        )
        belge_46a = "".join(
            f"<tr><td>{b.get('sart','')}</td>"
            f"<td>{b.get('detay','')}</td>"
            f"<td><b>{b.get('durum','')}</b></td></tr>"
            for b in v.get("belge_46a", [])
        )
        ucp_s = "".join(
            f"<tr><td><b>{m[0]}</b></td><td>{m[1]}</td>"
            f"<td><code>{m[2]}</code></td><td>{m[3]}</td></tr>"
            for m in v.get("ucp_tablosu", []) if m and len(m) >= 4
        )
        isbp_s = "".join(
            f"<tr><td><b>{i.get('ucp_maddesi','')}</b></td>"
            f"<td>{i.get('isbp_prensibi','')}</td>"
            f"<td>{i.get('bulgu','')}</td>"
            f"<td>{i.get('oneri','')}</td></tr>"
            for i in v.get("isbp_tablosu", [])
        )
        uzman_s = "".join(
            f"<tr><td>{o.get('rezerv','')[:60]}</td>"
            f"<td>{o.get('kategori','')}</td>"
            f"<td>{o.get('risk','')}</td>"
            f"<td>{o.get('banka_itiraz','')}</td>"
            f"<td>{o.get('ucp_maddesi','')}</td>"
            f"<td>{o.get('isbp_prensibi','')}</td>"
            f"<td>{o.get('duzeltme','')}</td>"
            f"<td>{o.get('tahmini_sure','')}</td></tr>"
            for o in v.get("uzman_onerileri", [])
        )
        eksik_s = "".join(
            f"<li>❌ {e}</li>" for e in v.get("eksik_belgeler", [])
        ) or "<li>✅ Zorunlu belgeler sistemde mevcut.</li>"

        # Yönetici özeti HTML bloğu
        oz = v.get("yonetici_ozeti", {})
        kabul_renk = "#276749" if oz.get("banka_kabul_olasiligi", 0) >= 70 else \
                     "#d69e2e" if oz.get("banka_kabul_olasiligi", 0) >= 40 else "#c53030"
        oz_html = ""
        if oz:
            oz_html = f"""
  <div class="exec-summary">
    <h2>🏦 YÖNETİCİ ÖZETİ</h2>
    <div class="exec-grid">
      <div class="exec-card"><div class="exec-label">Toplam Belge</div>
        <div class="exec-val">{oz.get('toplam_belge','?')}</div></div>
      <div class="exec-card"><div class="exec-label">Tespit Edilen Rezerv</div>
        <div class="exec-val badge-high">{oz.get('toplam_rezerv',0)}</div></div>
      <div class="exec-card"><div class="exec-label">MAJOR Discrepancy</div>
        <div class="exec-val badge-high">{oz.get('major_rezerv',0)}</div></div>
      <div class="exec-card"><div class="exec-label">MEDIUM Discrepancy</div>
        <div class="exec-val" style="color:#d69e2e">{oz.get('medium_rezerv',0)}</div></div>
      <div class="exec-card"><div class="exec-label">Uyumluluk Skoru</div>
        <div class="exec-val score">%{oz.get('uyumluluk_skoru','?')}</div></div>
      <div class="exec-card"><div class="exec-label">Banka Kabul Olasılığı</div>
        <div class="exec-val score" style="color:{kabul_renk}">
          %{oz.get('banka_kabul_olasiligi','?')}</div></div>
      <div class="exec-card"><div class="exec-label">Risk Sınıfı</div>
        <div class="exec-val badge-high">{oz.get('risk_sinifi','?')}</div></div>
    </div>
    <div style="margin-top:10px;font-size:.9em;">
      <b>En Kritik Sorun:</b> {oz.get('kritik_sorun','—')}
    </div>
  </div>"""

        # MT700 alan analizi HTML
        mt_html = "".join(
            f"<tr><td><b>{a.get('alan','')}</b></td><td>{a.get('aciklama','')}</td>"
            f"<td><code>{a.get('deger','')}</code></td><td>{a.get('durum','')}</td></tr>"
            for a in v.get("mt700_alan_analizi", [])
        )

        # Tarih zinciri HTML
        tarih_html = "".join(
            f"<tr><td><b>{t.get('etiket','')}</b></td><td>{t.get('deger','—')}</td>"
            f"<td><b>{t.get('durum','')}</b></td><td>{t.get('not','')}</td></tr>"
            for t in v.get("tarih_zinciri", [])
        )

        # Rezerv kategorileri
        kat_html = "".join(
            f"<tr><td>{d.get('kategori_kodu','')}</td><td><b>{d.get('kategori','')}</b></td>"
            f"<td>{d.get('puan','')}</td><td>{d.get('tahmini_sure','')}</td></tr>"
            for d in v.get("rezerv_detay_listesi", [])
        )

        # SWIFT simülatör HTML
        swift_html = ""
        for i, mt in enumerate(v.get("rezerv_swift_metinleri", []), 1):
            swift_html += f'<div class="swift-box"><b>Simüle Edilen Ret Metni {i}</b><pre>{mt}</pre></div>'

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Akreditif Analiz Raporu v6.0</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'Segoe UI',sans-serif;background:#f0f4f8;color:#2d3748;padding:20px;}}
    .container{{background:#fff;padding:36px;border-radius:14px;
                box-shadow:0 4px 20px rgba(0,0,0,.08);max-width:1260px;margin:0 auto;}}
    h1{{color:#1a365d;border-bottom:4px solid #3182ce;padding-bottom:14px;font-size:1.4em;}}
    h2{{color:#2b6cb0;margin:28px 0 10px;border-left:5px solid #3182ce;
        padding-left:10px;font-size:1.1em;}}
    table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:.9em;}}
    th,td{{border:1px solid #e2e8f0;padding:9px 11px;text-align:left;vertical-align:top;}}
    th{{background:#ebf8ff;color:#2b6cb0;font-weight:600;}}
    tr:nth-child(even){{background:#f7fafc;}}
    ul{{padding-left:18px;margin-top:8px;}}
    li{{margin-bottom:5px;line-height:1.65;}}
    .risk-box{{background:#fff5f5;border-left:5px solid #e53e3e;
               padding:16px;border-radius:8px;margin-top:12px;}}
    .exec-summary{{background:linear-gradient(135deg,#ebf8ff,#f0fff4);
                   border:2px solid #3182ce;border-radius:12px;padding:20px;margin-bottom:24px;}}
    .exec-grid{{display:flex;flex-wrap:wrap;gap:12px;margin-top:14px;}}
    .exec-card{{background:#fff;border:1px solid #bee3f8;border-radius:8px;
                padding:12px 18px;min-width:150px;text-align:center;}}
    .exec-label{{font-size:.78em;color:#718096;margin-bottom:4px;}}
    .exec-val{{font-size:1.4em;font-weight:700;color:#2b6cb0;}}
    .score{{color:#276749;}}
    .badge-high{{color:#c53030;}}
    .badge-ok{{color:#276749;}}
    .meta{{color:#718096;font-size:.88em;margin-bottom:16px;}}
    code{{background:#edf2f7;padding:2px 6px;border-radius:4px;font-size:.85em;}}
    .swift-box{{background:#1a202c;color:#f6e05e;border-radius:8px;
                padding:16px;margin:8px 0;font-family:monospace;font-size:.88em;}}
    .swift-box pre{{white-space:pre-wrap;margin-top:8px;color:#e2e8f0;}}
    .swift-box b{{color:#f6e05e;}}
  </style>
</head>
<body>
<div class="container">
  <h1>📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU</h1>
  <p class="meta">
    <b>Rapor Tarihi:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} &nbsp;|&nbsp;
    <b>Altyapı:</b> UCP 600 &amp; ISBP 821 Hukuk Motoru v6.0
  </p>

  {oz_html}

  <h2>📡 MT700 Alan Analizi</h2>
  <table><tr><th>Alan</th><th>Açıklama</th><th>Değer</th><th>Durum</th></tr>{mt_html}</table>

  <h2>📅 Tarih Zinciri Analizi</h2>
  <table><tr><th>Belge / Alan</th><th>Tarih</th><th>Durum</th><th>Not</th></tr>{tarih_html}</table>

  <h2>1. Kritik Süreler ve Vade Analizi</h2><ul>{li("vade_analizi")}</ul>
  <h2>2. Finansal Vade ve Ödeme Takvimi</h2><ul>{li("finansal_durum")}</ul>
  <h2>3. Incoterms ve Sigorta Hukuku (ICC 2020)</h2><ul>{li("incoterms")}</ul>

  <h2>4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü</h2>
  <table><tr><th>Belgeler</th><th>Detaylı İnceleme Kriteri</th><th>Durum</th></tr>{capraz}</table>

  <h2>5. Konşimento ve Taşıma Hukuku Parametreleri</h2><ul>{li("zorunlu_alanlar")}</ul>

  <h2>6. 46A Belge Şartları Kontrolü</h2>
  <table><tr><th>Talep Edilen Belge</th><th>Detay</th><th>Durum</th></tr>{belge_46a}</table>

  <h2>7. UCP 600 Hukuki Maddeleri Tablosu</h2>
  <table><tr><th>Madde</th><th>Açıklama</th><th>Sistem Durumu</th><th>Bulgu</th></tr>{ucp_s}</table>

  <h2>8. ISBP 821 Yorum Tablosu (Paragraf Düzeyinde)</h2>
  <table><tr><th>UCP Maddesi</th><th>ISBP Prensibi</th><th>Bulgu</th><th>Öneri</th></tr>{isbp_s}</table>

  <h2>9. Tespit Edilen Kritik Rezervler ve Uzman Önerileri</h2>
  <table>
    <tr><th>Rezerv</th><th>Kategori</th><th>Risk</th><th>Banka İtirazı</th>
        <th>UCP</th><th>ISBP Paragraf</th><th>Düzeltme</th><th>Süre</th></tr>
    {uzman_s}
  </table>

  <h2>10. Rezerv Kategorileri</h2>
  <table><tr><th>Kategori Kodu</th><th>Sınıf</th><th>Risk Puanı</th><th>Tahmini Çözüm</th></tr>
  {kat_html}</table>

  <h2>11. Eksik Belgeler Özeti</h2><ul>{eksik_s}</ul>

  <h2>12. Risk Değerlendirmesi ve Uyumluluk Skoru</h2>
  <div class="risk-box"><ul>{li("risk_ozeti")}</ul></div>

  <h2>🏛 Rezerv Simülatörü — Muhtemel Banka SWIFT Ret Metinleri</h2>
  <p style="margin:8px 0;font-size:.9em;color:#718096;">
    Aşağıdaki metinler bankanın MT734/MT750 mesajında yazabileceği muhtemel rezerv ifadelerini simüle etmektedir.
  </p>
  {swift_html if swift_html else '<p style="color:#276749">✅ Simüle edilecek SWIFT ret metni bulunmuyor.</p>'}
</div>
</body>
</html>"""

        with open(html_yolu, "w", encoding="utf-8") as f:
            f.write(html)
        print("[+] HTML Raporu Oluşturuldu.")

    # ------------------------------------------------------------------
    # Word raporu
    # ------------------------------------------------------------------
    def word_raporu_olustur(self) -> None:
        if not docx:
            print("[UYARI] python-docx yüklü değil, Word raporu atlandı.")
            return
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, Word raporu oluşturulamadı.")
            return

        doc_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.docx")
        belge    = docx.Document()

        for section in belge.sections:
            section.top_margin    = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin   = Inches(1)
            section.right_margin  = Inches(1)

        title_p = belge.add_paragraph()
        title_r = title_p.add_run(
            "AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU"
        )
        title_r.font.name      = "Arial"
        title_r.font.size      = Pt(15)
        title_r.font.bold      = True
        title_r.font.color.rgb = docx.shared.RGBColor(26, 54, 93)
        title_p.alignment      = WD_ALIGN_PARAGRAPH.CENTER

        meta_p = belge.add_paragraph()
        meta_r = meta_p.add_run(
            f"Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')} "
            "| Altyapı: UCP 600 & ISBP 821 Hukuk Motoru v5.0"
        )
        meta_r.font.size   = Pt(9)
        meta_r.font.italic = True
        meta_p.alignment   = WD_ALIGN_PARAGRAPH.CENTER
        belge.add_paragraph("-" * 70)

        def baslik_ekle(metin: str) -> None:
            h  = belge.add_paragraph()
            hr = h.add_run(metin)
            hr.font.name      = "Arial"
            hr.font.size      = Pt(12)
            hr.font.bold      = True
            hr.font.color.rgb = docx.shared.RGBColor(43, 108, 176)

        def madde_ekle(metinler: list[str]) -> None:
            for item in metinler:
                belge.add_paragraph(item.replace("**", ""), style="List Bullet")

        def tablo_3_sutun(sutunlar: list[str], satirlar: list[dict], anahtarlar: list[str]) -> None:
            t = belge.add_table(rows=1, cols=len(sutunlar))
            t.style = "Table Grid"
            for i, ad in enumerate(sutunlar):
                t.rows[0].cells[i].text = ad
            for satir in satirlar:
                h = t.add_row().cells
                for i, k in enumerate(anahtarlar):
                    h[i].text = str(satir.get(k, "")) if isinstance(satir, dict) else str(satir[i] if i < len(satir) else "")

        baslik_ekle("1. Kritik Süreler ve Vade Analizi")
        madde_ekle(v.get("vade_analizi", []))

        baslik_ekle("2. Finansal Vade ve Ödeme Takvimi")
        madde_ekle(v.get("finansal_durum", []))

        baslik_ekle("3. Incoterms ve Sigorta Hukuku (ICC 2020)")
        madde_ekle(v.get("incoterms", []))

        baslik_ekle("4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü")
        tablo_3_sutun(
            ["Belgeler", "İnceleme Detayı", "Durum"],
            v.get("capraz_kontrol", []),
            ["belge", "detay", "durum"],
        )

        baslik_ekle("5. Konşimento ve Taşıma Hukuku Parametreleri")
        madde_ekle(v.get("zorunlu_alanlar", []))

        baslik_ekle("6. 46A Belge Şartları Kontrolü")
        tablo_3_sutun(
            ["Talep Edilen Belge", "Detay", "Durum"],
            v.get("belge_46a", []),
            ["sart", "detay", "durum"],
        )

        baslik_ekle("7. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu")
        t_ucp = belge.add_table(rows=1, cols=4)
        t_ucp.style = "Table Grid"
        for i, ad in enumerate(["Madde", "Açıklama", "Sistem Durumu", "Bulgu"]):
            t_ucp.rows[0].cells[i].text = ad
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                h = t_ucp.add_row().cells
                for i in range(4):
                    h[i].text = str(m[i])

        baslik_ekle("8. ISBP 821 Yorum Tablosu")
        t_isbp = belge.add_table(rows=1, cols=4)
        t_isbp.style = "Table Grid"
        for i, ad in enumerate(["UCP Maddesi", "ISBP Prensibi", "Bulgu", "Öneri"]):
            t_isbp.rows[0].cells[i].text = ad
        for item in v.get("isbp_tablosu", []):
            h = t_isbp.add_row().cells
            h[0].text = str(item.get("ucp_maddesi", ""))
            h[1].text = str(item.get("isbp_prensibi", ""))
            h[2].text = str(item.get("bulgu", ""))
            h[3].text = str(item.get("oneri", ""))

        baslik_ekle("9. Tespit Edilen Kritik Rezervler ve Uzman Önerileri")
        t_uzman = belge.add_table(rows=1, cols=5)
        t_uzman.style = "Table Grid"
        for i, ad in enumerate(["Rezerv", "Risk", "Banka İtirazı", "UCP Maddesi", "Düzeltme"]):
            t_uzman.rows[0].cells[i].text = ad
        for o in v.get("uzman_onerileri", []):
            h = t_uzman.add_row().cells
            h[0].text = str(o.get("rezerv", ""))[:80]
            h[1].text = str(o.get("risk", ""))
            h[2].text = str(o.get("banka_itiraz", ""))
            h[3].text = str(o.get("ucp_maddesi", ""))
            h[4].text = str(o.get("duzeltme", ""))

        baslik_ekle("10. Eksik Belgeler Özeti")
        eksik = v.get("eksik_belgeler", [])
        if eksik:
            madde_ekle([f"EKSIK: {e}" for e in eksik])
        else:
            belge.add_paragraph("Zorunlu belgeler sistemde mevcut.", style="List Bullet")

        baslik_ekle("11. Risk Değerlendirmesi ve Uyumluluk Skoru")
        madde_ekle(v.get("risk_ozeti", []))

        belge.save(doc_yolu)
        print("[+] Word (.docx) Raporu Başarıyla Üretildi.")

    # ------------------------------------------------------------------
    # Ana akış
    # ------------------------------------------------------------------
    def baslat(self) -> None:
        """Sistemi başlatır: belgeleri tarar, analiz eder ve tüm raporları üretir."""
        print("[BİLGİ] Akreditif denetim sistemi v5.0 başlatılıyor...")
        if self.depoyu_tara_ve_analiz_et():
            print(
                f"[BİLGİ] Belgeler yüklendi: "
                f"KUŞAT={'VAR' if self.depo['KUSAT']       else 'YOK'} | "
                f"FATURA={'VAR' if self.depo['FATURA']      else 'YOK'} | "
                f"KONŞİMENTO={'VAR' if self.depo['KONSIMENTO'] else 'YOK'} | "
                f"ÇEKİ={'VAR' if self.depo['CEKI_LISTESI'] else 'YOK'} | "
                f"SİGORTA={'VAR' if self.depo['SIGORTA']     else 'YOK'}"
            )
            self.ucp600_kural_motoru()
            self.markdown_raporu_olustur()
            self.html_raporu_olustur()
            self.word_raporu_olustur()
            print(
                f"[SONUÇ] Risk Puanı: {self.risk_puani} — {self._risk_sinifi()} | "
                f"Uyumluluk Skoru: %{self.uyumluluk_puani}"
            )
            print("[SONUÇ] Tüm raporlar oluşturuldu.")
        else:
            print("[BİLGİ] Yüklenmiş belge bulunamadı veya dizin boş.")


# ===========================================================================
# Giriş noktası
# ===========================================================================
if __name__ == "__main__":
    motor = YapayZekaDisTicaretDenetleyici()
    motor.baslat()
