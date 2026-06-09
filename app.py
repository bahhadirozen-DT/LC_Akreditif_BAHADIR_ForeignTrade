bash

cat > /mnt/user-data/outputs/app.py << 'ENDOFFILE'
"""
Yapay Zeka Destekli Dış Ticaret Akreditif Denetleme Sistemi
UCP 600 / ISBP 821 Uyumlu | Üretim Ortamı Sürümü v4.0

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
# Risk motoru sabitleri
# ---------------------------------------------------------------------------
RISK_PUANLARI: dict[str, int] = {
    "sigorta_eksik":          30,
    "tutar_uyusmazligi":      40,
    "yukleme_tarihi_ihlali":  40,
    "konsimento_eksik":       50,
    "mal_tanimi_uyusmazligi": 35,
    "kilo_uyusmazligi":       20,
    "ibraz_suresi_belirsiz":  10,
}

RISK_SINIFLANDIRMASI: list[tuple[int, int, str]] = [
    (0,   20, "DÜŞÜK RİSK"),
    (21,  50, "ORTA RİSK"),
    (51, 999, "YÜKSEK RİSK"),
]


# ===========================================================================
# Ana sınıf
# ===========================================================================
class YapayZekaDisTicaretDenetleyici:
    """UCP 600 / ISBP 821 uyumlu akreditif belge denetleme motoru."""

    def __init__(self, ana_dizin: str = "DisTicaretRepo") -> None:
        self.base_dir = ana_dizin
        self.yuklenenler_dir = os.path.join(self.base_dir, "YuklenenDosyalar")
        self.raporlar_dir    = os.path.join(self.base_dir, "Raporlar")

        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir,    exist_ok=True)

        self.depo:          dict[str, Any] = self._bos_depo()
        self.analiz_verisi: dict[str, Any] = {}
        self.risk_puani:    int            = 0
        self.mt700_alanlari: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Depo yardımcıları
    # ------------------------------------------------------------------
    @staticmethod
    def _bos_depo() -> dict[str, Any]:
        """Temiz, boş bir depo sözlüğü döner."""
        return {
            "KUSAT":          None,
            "FATURA":         None,
            "KONSIMENTO":     None,   # Tek iç anahtar; KONŞİMENTO da bu anahtara eşlenir
            "CEKI_LISTESI":   None,
            "SIGORTA":        None,
            "DIGER_BELGELER": [],
        }

    def _depo_metin(self, anahtar: str) -> str:
        """Depo kaydındaki metni döner; kayıt yoksa veya hatalıysa boş string."""
        kayit = self.depo.get(anahtar)
        if not kayit or not isinstance(kayit, dict):
            return ""
        metin = kayit.get("metin")
        return metin if isinstance(metin, str) else ""

    # ------------------------------------------------------------------
    # MT700 ayrıştırıcısı
    # ------------------------------------------------------------------
    def mt700_ayristir(self, metin: str) -> dict[str, str]:
        """
        SWIFT MT700 formatındaki küşat metninden standart alanları çıkarır.
        Döner: {"20": "...", "31D": "...", "32B": "...", "44C": "...", ...}
        """
        if not metin:
            return {}
        hedef_alanlar = ["20", "31D", "32B", "40A", "44C", "45A", "46A", "47A", "71B"]
        sonuc: dict[str, str] = {}
        for alan in hedef_alanlar:
            desen = rf'(?:^|:){re.escape(alan)}[:\s]+(.+?)(?=(?:^|:)\d{{2,3}}[A-Z]{{0,1}}[:\s]|\Z)'
            try:
                m = re.search(desen, metin, re.MULTILINE | re.DOTALL | re.IGNORECASE)
                if m:
                    deger = re.sub(r'\s+', ' ', m.group(1).strip())[:500]
                    sonuc[alan] = deger
            except re.error:
                continue
        return sonuc

    # ------------------------------------------------------------------
    # Metin ayıklama
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu: str) -> str:
        """
        Desteklenen formatlardaki dosyadan düz metin çıkarır.
        Hata durumunda '[Hata: ...]' formatında açıklayıcı string döner.
        Her sayfa / satır kendi try/except bloğunda yönetilir.
        """
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
                    except Exception as sayfa_hatasi:
                        metin += f"[Sayfa {i + 1} Okuma Hatası: {sayfa_hatasi}]\n"

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
                except pytesseract.TesseractError as ocr_hatasi:
                    return f"[OCR Hatası: {ocr_hatasi}]"

            elif ext == ".txt":
                with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
                    metin = f.read()

            else:
                return f"[Desteklenmeyen dosya formatı: {ext}]"

        except Exception as genel_hata:
            return f"[Dosya Okuma Hatası ({ext}): {genel_hata}]"

        metin = metin.replace("\xa0", " ").replace("\u200b", "").replace("\r\n", "\n")
        return metin

    # ------------------------------------------------------------------
    # Belge türü tespiti
    # ------------------------------------------------------------------
    def dokuman_tipi_belirle(self, metin: str) -> str:
        """
        Metin içeriğine göre belge türünü tespit eder.
        Hem KONŞİMENTO hem KONSIMENTO desteklenir;
        her ikisi de 'KONSIMENTO' iç anahtarına eşlenir.
        """
        if not metin:
            return "DIGER"
        m = metin.upper()

        if any(x in m for x in ["DOCUMENTARY CREDIT", "40A:", "IRREVOCABLE", "L/C NO", "KÜŞAT", ":32B:"]):
            return "KUSAT"
        if any(x in m for x in ["COMMERCIAL INVOICE", "FATURA", "FAVURA", "INVOICE NO", "INVOICE EXP"]):
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
        """
        YuklenenDosyalar dizinindeki tüm dosyaları okur, türlerini tespit eder
        ve depoya kaydeder. Her çalıştırmada depo sıfırlanır.
        """
        self.depo            = self._bos_depo()
        self.risk_puani      = 0
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
    # Sayısal değer çıkarma yardımcıları
    # ------------------------------------------------------------------
    def sayisal_deger_bul(self, metin: str, desenler: list[str]) -> Optional[float]:
        """
        Verilen metin içinde desenleri sırayla dener; ilk geçerli float değeri döner.
        Eşleşme yoksa None döner. Hardcoded fallback yoktur.
        """
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
        """
        Belgeden brüt ağırlık değerini çıkarır.
        Gross Weight, Net Weight, G.W., N.W., KGS biçimlerini destekler.
        """
        if not metin:
            return None
        desenler = [
            r'(?:GROSS\s*WEIGHT|BRÜT\s*(?:KİLO|AĞIRLIK)|G\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT|TON)',
            r'(?:NET\s*WEIGHT|N\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT|TON)',
            r'([\d,\.]+)\s*(?:KGS)\b',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    def miktar_bul(self, metin: str) -> Optional[tuple[float, str]]:
        """
        Belgeden miktar ve birimini çıkarır.
        Desteklenen birimler: PCS, KG, MT, TON, BOX, CTN, SET, UNIT.
        (deger, birim) tuple döner; bulunamazsa None.
        """
        if not metin:
            return None
        desen = r'([\d,\.]+)\s*(PCS|PIECES?|KGS?|MT|TONS?|BOX(?:ES)?|CTNS?|CARTONS?|SETS?|UNITS?)\b'
        try:
            m = re.search(desen, metin, re.IGNORECASE)
            if m:
                deger = float(m.group(1).replace(",", ""))
                birim = m.group(2).upper()
                return (deger, birim)
        except (ValueError, re.error):
            pass
        return None

    def para_tutari_bul(self, metin: str) -> Optional[float]:
        """
        Belgeden para tutarını çıkarır.
        MT700 Alan 32B önceliklidir; ardından yaygın fatura etiketleri aranır.
        Döviz birimi fark etmeksizin sayısal değer döner.
        """
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

    def tarih_bul(self, metin: str, desenler: list[str]) -> Optional[str]:
        """
        Verilen metin içinden ilk eşleşen tarih string'ini döner.
        Format normalleştirmesi yapılmaz; None döner eşleşme yoksa.
        """
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
        """
        Belgeden mal tanımı metnini çıkarır.
        MT700 Alan 45A (küşat) ve DESCRIPTION OF GOODS (fatura/konşimento) desteklenir.
        """
        if not metin:
            return None
        # Küşat ise MT700 ayrıştırıcısından önce dene
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

    # ------------------------------------------------------------------
    # Risk motoru
    # ------------------------------------------------------------------
    def _risk_puani_ekle(self, kategori: str) -> None:
        """Belirtilen kategorinin risk puanını toplam puana ekler."""
        self.risk_puani += RISK_PUANLARI.get(kategori, 0)

    def _risk_sinifi(self) -> str:
        """Toplam risk puanına göre risk sınıfını döner."""
        for alt, ust, sinif in RISK_SINIFLANDIRMASI:
            if alt <= self.risk_puani <= ust:
                return sinif
        return "YÜKSEK RİSK"

    # ------------------------------------------------------------------
    # UCP 600 Kural Motoru
    # ------------------------------------------------------------------
    def ucp600_kural_motoru(self) -> None:
        """
        Depodaki belgeler üzerinde UCP 600 / ISBP 821 kurallarını uygular.
        Sonuçları self.analiz_verisi sözlüğüne yazar.
        hukuk_motoru.py varsa UCP tablosu için entegre edilir;
        yoksa veya hata verirse yerleşik tablo kullanılır.
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
            "vade_analizi":    [],
            "finansal_durum":  [],
            "incoterms":       [],
            "capraz_kontrol":  [],
            "zorunlu_alanlar": [],
            "ucp_tablosu":     [],
            "risk_ozeti":      [],
            "rezerv_ozeti":    [],
        }

        # ================================================================
        # 1. Kritik Süreler ve Vade Analizi
        # ================================================================
        lc_44c_str: Optional[str] = self.mt700_alanlari.get("44C") or self.tarih_bul(
            kusat_text,
            [
                r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT|SON\s+YÜKLEME\s+TARİHİ)'
                r'[:\s]*([\d]{2}[\.\-\/][\d]{2}[\.\-\/][\d]{4})',
                r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT|SON\s+YÜKLEME\s+TARİHİ)'
                r'[:\s]*([\d]{1,2}[\s\.\-\/][A-Z]{3,}[\s\.\-\/][\d]{4})',
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
        else:
            sonuclar["vade_analizi"].append(
                "Bankaya İbraz Süresi: Belgeden tespit edilemedi — "
                "UCP 600 Madde 14c varsayılan 21 günlük limit uygulanır."
            )
            self._risk_puani_ekle("ibraz_suresi_belirsiz")

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

        art28_durum = "UYGULANMAZ"
        art28_not   = (
            f"Teslim şekli ({incoterm_var or 'Belirsiz'}) "
            "satıcının sigorta ibrazını zorunlu kılmıyor."
        )

        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                art28_durum = "DOĞRUDAN GEÇTİ"
                art28_not   = (
                    "Sigorta poliçesi dosyalar arasında saptandı. "
                    "Min. %110 teminat hesabı için Bölüm 4 Çapraz Kontrol tablosuna bakın."
                )
                sonuclar["incoterms"].append(
                    f"[TAMAM] {incoterm_var} şartı gereği Resmi Sigorta Poliçesi saptandı (UCP 600 Art 28)."
                )
            else:
                art28_durum = "YÜKSEK RİSK"
                art28_not   = (
                    f"{incoterm_var} teslimlerde Sigorta Poliçesi zorunludur! "
                    "Minimum %110 teminat aranır (UCP 600 Madde 28)."
                )
                sonuclar["incoterms"].append(
                    f"[HUKUKİ REZERV RİSKİ] Teslim şekli {incoterm_var} olmasına rağmen "
                    "Sigorta Poliçesi bulunamadı!"
                )
                self._risk_puani_ekle("sigorta_eksik")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Sigorta belgesi eksik ({incoterm_var} teslimde Art 28 zorunluluğu)"
                )

        # ================================================================
        # 4. Sayısal ve Evrak Çapraz Kontrolleri
        # ================================================================

        # --- 4a. Fatura Tutarı ↔ Akreditif Tutarı (UCP Art 18 + Art 30) ---
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
            tolerans = lc_tutari * 0.05
            fark     = abs(fatura_tutari - lc_tutari)
            if fark <= tolerans:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                    "detay": (
                        f"Fatura: {fatura_tutari:,.2f} | "
                        f"Akreditif: {lc_tutari:,.2f} | "
                        f"Fark: {fark:,.2f} (≤ %5 tolerans)"
                    ),
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                    "detay": (
                        f"Fatura: {fatura_tutari:,.2f} | "
                        f"Akreditif: {lc_tutari:,.2f} | "
                        f"Fark: {fark:,.2f} (> %5 tolerans)"
                    ),
                    "durum": "REZERV RİSKİ - TUTAR UYUŞMAZLIĞI",
                })
                self._risk_puani_ekle("tutar_uyusmazligi")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Fatura tutarı ({fatura_tutari:,.2f}) akreditif tutarından "
                    f"({lc_tutari:,.2f}) {fark:,.2f} sapıyor, %5 toleransı aşıyor (Art 30)"
                )
        else:
            eksik_tutar = []
            if fatura_tutari is None:
                eksik_tutar.append("Fatura")
            if lc_tutari is None:
                eksik_tutar.append("Akreditif (32B)")
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                "detay": f"Tutar tespit edilemedi: {', '.join(eksik_tutar)}",
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
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Kilo uyumsuzluğu: Fatura {fatura_kilo:,.2f} KG / "
                    f"Konşimento {bl_kilo:,.2f} KG"
                )
        else:
            eksik = []
            if fatura_kilo is None:
                eksik.append("Fatura")
            if bl_kilo is None:
                eksik.append("Konşimento")
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

        # --- 4d. Miktar — Fatura ↔ Çeki Listesi ---
        fatura_miktar = self.miktar_bul(fatura_text)
        ceki_miktar   = self.miktar_bul(ceki_text)

        if fatura_miktar and ceki_miktar:
            f_deger, f_birim = fatura_miktar
            c_deger, c_birim = ceki_miktar
            if f_birim == c_birim and abs(f_deger - c_deger) < 1:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Çeki Listesi Miktar",
                    "detay": f"Miktar Eşleşmesi: {f_deger:,.0f} {f_birim}",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Çeki Listesi Miktar",
                    "detay": f"Fatura: {f_deger:,.0f} {f_birim} | Çeki: {c_deger:,.0f} {c_birim}",
                    "durum": "REZERV RİSKİ - MİKTAR UYUŞMAZLIĞI",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")

        # --- 4e. Mal Tanımı — Fatura ↔ Küşat (UCP 600 Art 18c) ---
        fatura_mal: Optional[str] = self.mal_tanimi_bul(fatura_text)
        kusat_mal:  Optional[str] = self.mal_tanimi_bul(kusat_text)

        if fatura_mal and kusat_mal:
            kusat_kelimeler  = set(re.findall(r'\b\w{4,}\b', kusat_mal.upper()))
            fatura_kelimeler = set(re.findall(r'\b\w{4,}\b', fatura_mal.upper()))
            ortak = kusat_kelimeler & fatura_kelimeler
            oran  = len(ortak) / len(kusat_kelimeler) if kusat_kelimeler else 0.0

            if oran >= 0.6:
                durum_mal = "UYUMLU"
            elif oran >= 0.3:
                durum_mal = "DÜŞÜK BENZERLİK - MANUEL KONTROL"
                self._risk_puani_ekle("mal_tanimi_uyusmazligi")
            else:
                durum_mal = "REZERV RİSKİ - MAL TANIMI UYUŞMAZLIĞI"
                self._risk_puani_ekle("mal_tanimi_uyusmazligi")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Mal tanımı uyuşmazlığı: Örtüşme %{oran * 100:.0f} (Art 18c)"
                )

            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura Mal Tanımı vs Küşat (Art 18c)",
                "detay": (
                    f"Küşat: '{kusat_mal[:80]}' | "
                    f"Fatura: '{fatura_mal[:80]}' | "
                    f"Örtüşme: %{oran * 100:.0f}"
                ),
                "durum": durum_mal,
            })
        else:
            eksik_mal = []
            if not fatura_mal:
                eksik_mal.append("Fatura")
            if not kusat_mal:
                eksik_mal.append("Küşat (45A)")
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura Mal Tanımı vs Küşat (Art 18c)",
                "detay": f"Mal tanımı tespit edilemedi: {', '.join(eksik_mal)}",
                "durum": "MANUEL KONTROL",
            })

        # --- 4f. Konşimento Yükleme Tarihi ↔ Alan 44C ---
        bl_tarih_desenler = [
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}[\s\.\-\/][A-Z]{3,}[\s\.\-\/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{2}[\.\-\/][\d]{2}[\.\-\/][\d]{4})',
        ]
        lc_44c_desenler = [
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{1,2}[\s\.\-\/][A-Z]{3,}[\s\.\-\/][\d]{4})',
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)'
            r'[:\s]+([\d]{2}[\.\-\/][\d]{2}[\.\-\/][\d]{4})',
        ]
        bl_yukleme_tarihi = self.tarih_bul(konsimento_text, bl_tarih_desenler)
        lc_son_yukleme    = lc_44c_str or self.tarih_bul(kusat_text, lc_44c_desenler)

        if bl_yukleme_tarihi and lc_son_yukleme:
            sonuclar["capraz_kontrol"].append({
                "belge":  "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                "detay": (
                    f"Konşimento Yükleme: {bl_yukleme_tarihi} | "
                    f"44C Son Yükleme: {lc_son_yukleme}"
                ),
                "durum": "TESPİT EDİLDİ - MANUEL TARİH KARŞILAŞTIRMASI GEREKLİ",
            })
        else:
            eksik_tarih = []
            if not bl_yukleme_tarihi:
                eksik_tarih.append("Konşimento yükleme tarihi")
            if not lc_son_yukleme:
                eksik_tarih.append("Küşat 44C")
            sonuclar["capraz_kontrol"].append({
                "belge":  "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                "detay": f"Tarih tespit edilemedi: {', '.join(eksik_tarih)}",
                "durum": "MANUEL KONTROL",
            })
            if not bl_yukleme_tarihi and konsimento_text:
                self._risk_puani_ekle("yukleme_tarihi_ihlali")
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — Konşimento yükleme tarihi tespit edilemedi (Art 20)"
                )

        # --- 4g. Sigorta Bedeli ≥ Fatura × %110 (UCP 600 Art 28f-ii) ---
        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                sigorta_tutari = self.para_tutari_bul(sigorta_text)
                if sigorta_tutari is not None and fatura_tutari is not None:
                    minimum_teminat = fatura_tutari * 1.10
                    if sigorta_tutari >= minimum_teminat:
                        sonuclar["capraz_kontrol"].append({
                            "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                            "detay": (
                                f"Sigorta: {sigorta_tutari:,.2f} | "
                                f"Gerekli Min.: {minimum_teminat:,.2f} "
                                f"(Fatura {fatura_tutari:,.2f} × 1.10)"
                            ),
                            "durum": "UYUMLU",
                        })
                    else:
                        eksik_teminat = minimum_teminat - sigorta_tutari
                        sonuclar["capraz_kontrol"].append({
                            "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                            "detay": (
                                f"Sigorta: {sigorta_tutari:,.2f} | "
                                f"Gerekli Min.: {minimum_teminat:,.2f} | "
                                f"Eksik Teminat: {eksik_teminat:,.2f}"
                            ),
                            "durum": "REZERV RİSKİ - YETERSİZ SİGORTA TEMİNATI",
                        })
                        self._risk_puani_ekle("sigorta_eksik")
                        sonuclar["rezerv_ozeti"].append(
                            f"REZERV — Sigorta teminatı yetersiz: {sigorta_tutari:,.2f} < "
                            f"gerekli {minimum_teminat:,.2f} (Art 28f-ii)"
                        )
                elif fatura_tutari is not None:
                    sonuclar["capraz_kontrol"].append({
                        "belge":  "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                        "detay": (
                            f"Sigorta belgesi mevcut ancak tutar okunamadı. "
                            f"Fatura: {fatura_tutari:,.2f} → Gerekli min: {fatura_tutari * 1.10:,.2f}"
                        ),
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
                    "detay": (
                        f"{incoterm_var} teslimlerde sigorta poliçesi zorunludur "
                        "ancak dosyalar arasında bulunamadı."
                    ),
                    "durum": "REZERV RİSKİ - SİGORTA BELGESİ EKSİK",
                })

        # ================================================================
        # 5. Konşimento Hukuki Maddeleri (UCP 600 Art 20-27)
        # ================================================================
        if not konsimento_text:
            sonuclar["zorunlu_alanlar"].append(
                "[REZERV RİSKİ] Konşimento belgesi depoda bulunamadı!"
            )
            self._risk_puani_ekle("konsimento_eksik")
            sonuclar["rezerv_ozeti"].append(
                "REZERV — Konşimento belgesi ibraz edilmemiş (Art 20)"
            )
        else:
            bl_upper = konsimento_text.upper()
            if "SHIPPED ON BOARD" in bl_upper or "ON BOARD" in bl_upper:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Konşimento üzerinde 'Shipped on Board' şerhi saptandı (Art 20a-ii uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[REZERV RİSKİ] Konşimentoda zorunlu 'Shipped on Board' "
                    "yükleme şerhi açıkça bulunamadı!"
                )
                self._risk_puani_ekle("konsimento_eksik")
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — 'Shipped on Board' şerhi tespit edilemedi (Art 20a-ii)"
                )

            if "CLEAN" in bl_upper:
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Temiz taşıma belgesi (Clean B/L) şerhi saptandı (Art 27 uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[BİLGİ] Konşimentoda 'CLEAN' ibaresi bulunamadı — "
                    "Art 27 kapsamında manuel kontrol önerilir."
                )

        # ================================================================
        # 6. Risk Özeti
        # ================================================================
        risk_sinifi = self._risk_sinifi()
        sonuclar["risk_ozeti"].append(
            f"Toplam Risk Puanı: **{self.risk_puani}** — Risk Sınıfı: **{risk_sinifi}**"
        )
        if not sonuclar["rezerv_ozeti"]:
            sonuclar["risk_ozeti"].append(
                "Sistem tarafından tespit edilen kritik rezerv bulunamadı."
            )
        else:
            for i, rezerv in enumerate(sonuclar["rezerv_ozeti"], 1):
                sonuclar["risk_ozeti"].append(f"{i}. {rezerv}")

        # ================================================================
        # 7. UCP 600 Tablosu
        # ================================================================
        fatura_durum = (
            "DOĞRUDAN GEÇTİ"
            if ("INVOICE" in combined or "FATURA" in combined)
            else "DOĞRUDAN GEÇMİYOR"
        )
        bl_durum = (
            "TESPİT EDİLDİ"
            if ("BILL OF LADING" in combined or "SHIPPED ON BOARD" in combined)
            else "DOĞRUDAN GEÇMİYOR"
        )

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
                        raise ValueError(
                            "hukuk_motoru dict döndürdü ancak 'ucp_tablosu' anahtarı boş."
                        )
                else:
                    raise ValueError("hukuk_motoru.analiz_et tanımsız bir tip döndürdü.")
            except Exception as motor_hatasi:
                print(f"[UYARI] Hukuk motoru hatası, yerleşik tablo kullanılıyor: {motor_hatasi}")
                sonuclar["ucp_tablosu"] = self._varsayilan_ucp_tablosu(
                    fatura_durum, bl_durum, art28_durum, art28_not
                )
        else:
            if not HUKUK_MOTORU_AKTIF:
                print("[BİLGİ] hukuk_motoru.py bulunamadı, yerleşik UCP tablosu kullanılıyor.")
            sonuclar["ucp_tablosu"] = self._varsayilan_ucp_tablosu(
                fatura_durum, bl_durum, art28_durum, art28_not
            )

        self.analiz_verisi = sonuclar

    # ------------------------------------------------------------------
    # Yerleşik UCP 600 tablosu
    # ------------------------------------------------------------------
    def _varsayilan_ucp_tablosu(
        self,
        fatura_durum: str,
        bl_durum: str,
        art28_durum: str,
        art28_not: str,
    ) -> list[tuple[str, str, str, str]]:
        """
        hukuk_motoru.py yoksa veya hata verirse kullanılan yerleşik UCP 600 tablosu.
        kurallar.json varsa zorunlu_kurallar ile zenginleştirilir.
        """
        tablo: list[tuple[str, str, str, str]] = [
            ("Art 14", "Belgelerin İncelenmesi Standartları",
             "TESPİT EDİLDİ",     "Standart 21 günlük yasal banka ibraz sınırı uygulandı."),
            ("Art 15", "Uyumlu İbraz (Complying Presentation)",
             "DOĞRUDAN GEÇMİYOR", "Vesaiklerin bankaya eksiksiz ve hatasız ulaştığının teyidi."),
            ("Art 17", "Orijinal Belgeler ve Suretler",
             "DOĞRUDAN GEÇMİYOR", "Banka ibrazında orijinal/suret kaşelerinin varlığı aranır."),
            ("Art 18", "Ticari Fatura (Commercial Invoice)",
             fatura_durum,         "Mal tanımının küşat metniyle karakter doğrulaması yapıldı (Art 18c)."),
            ("Art 20", "Konşimento (Bill of Lading)",
             bl_durum,             "Shipped on Board şerhi ve ciro silsilesi hukuki denetimi yapıldı."),
            ("Art 27", "Temiz Taşıma Belgesi",
             bl_durum,             "Üzerinde hasar veya kusurlu ambalaj şerhi bulunmayan temiz belge kontrolü."),
            ("Art 28", "Sigorta Belgesi ve Kapsamı",
             art28_durum,          art28_not),
            ("Art 30", "Miktar ve Tutarda Toleranslar",
             "DOĞRUDAN GEÇMİYOR", "Akreditifte aksi belirtilmedikçe %5 / %10 tolerans limitleri."),
        ]

        # kurallar.json varsa zorunlu_kurallar tabloyu zenginleştirir
        try:
            with open("kurallar.json", "r", encoding="utf-8") as f:
                veri = json.load(f)
            mevcut_maddeler = {row[0] for row in tablo}
            for kural in veri.get("zorunlu_kurallar", []):
                madde    = kural.get("madde", "")
                aciklama = kural.get("aciklama", "")
                anahtar  = kural.get("anahtar", "")
                if madde and madde not in mevcut_maddeler:
                    tablo.append((madde, aciklama, "ZORUNLU KURAL", anahtar))
                    mevcut_maddeler.add(madde)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass  # kurallar.json yoksa veya bozuksa sessizce devam et

        return tablo

    # ------------------------------------------------------------------
    # Rapor üretimi — Markdown
    # ------------------------------------------------------------------
    def markdown_raporu_olustur(self) -> None:
        """Analiz sonuçlarını Markdown formatında üretir."""
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, Markdown raporu oluşturulamadı.")
            return

        md_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")
        satirlar = [
            "# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU\n",
            f"**Analiz Zamanı:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  \n",
            "**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP Hukuk Motoru v4.0  \n\n",
            "---\n",
            "## 1. Kritik Süreler ve Vade Analizi\n",
        ]
        for s in v.get("vade_analizi", []):
            satirlar.append(f"* {s}\n")

        satirlar.append("\n---\n## 2. Finansal Vade ve Ödeme Takvimi\n")
        for s in v.get("finansal_durum", []):
            satirlar.append(f"* {s}\n")

        satirlar.append("\n---\n## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)\n")
        for s in v.get("incoterms", []):
            satirlar.append(f"* {s}\n")

        satirlar.append(
            "\n---\n## 4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü\n"
            "| Belgeler | İnceleme Detayı | Durum |\n"
            "| :--- | :--- | :--- |\n"
        )
        for c in v.get("capraz_kontrol", []):
            satirlar.append(
                f"| {c.get('belge', '')} | {c.get('detay', '')} | "
                f"**[{c.get('durum', '')}]** |\n"
            )

        satirlar.append(
            "\n---\n## 5. Konşimento ve Taşıma Hukuku Parametreleri (UCP Art. 20-27)\n"
        )
        for s in v.get("zorunlu_alanlar", []):
            satirlar.append(f"* {s}\n")

        satirlar.append(
            "\n---\n## 6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu\n"
            "| UCP 600 Madde | Kapsam Açıklaması | Sistem Geçiş Durumu | Uzman Bulgusu |\n"
            "| :--- | :--- | :--- | :--- |\n"
        )
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                satirlar.append(f"| **{m[0]}** | {m[1]} | `{m[2]}` | {m[3]} |\n")

        satirlar.append("\n---\n## 7. Risk Değerlendirmesi ve Rezerv Özeti\n")
        for s in v.get("risk_ozeti", []):
            satirlar.append(f"* {s}\n")

        with open(md_yolu, "w", encoding="utf-8") as f:
            f.writelines(satirlar)
        print("[+] Markdown Raporu Oluşturuldu.")

    # ------------------------------------------------------------------
    # Rapor üretimi — HTML
    # ------------------------------------------------------------------
    def html_raporu_olustur(self) -> None:
        """Analiz sonuçlarını tarayıcıda görüntülenebilir HTML formatında üretir."""
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, HTML raporu oluşturulamadı.")
            return

        html_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.html")

        def li_listesi(anahtar: str) -> str:
            return "".join(f"<li>{x}</li>" for x in v.get(anahtar, []))

        capraz_satirlar = "".join(
            f"<tr>"
            f"<td><b>{r.get('belge', '')}</b></td>"
            f"<td>{r.get('detay', '')}</td>"
            f"<td><b>{r.get('durum', '')}</b></td>"
            f"</tr>"
            for r in v.get("capraz_kontrol", [])
        )
        ucp_satirlar = "".join(
            f"<tr>"
            f"<td><b>{m[0]}</b></td><td>{m[1]}</td>"
            f"<td><code>{m[2]}</code></td><td>{m[3]}</td>"
            f"</tr>"
            for m in v.get("ucp_tablosu", [])
            if m and len(m) >= 4
        )

        html_text = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hukuki Akreditif Analiz Raporu</title>
  <style>
    body {{font-family:'Segoe UI',sans-serif;padding:30px;color:#2d3748;background:#f7fafc;}}
    .container {{background:#fff;padding:40px;border-radius:12px;
                 box-shadow:0 4px 6px rgba(0,0,0,.05);max-width:1100px;margin:0 auto;}}
    h1 {{color:#1a365d;border-bottom:4px solid #3182ce;padding-bottom:12px;}}
    h2 {{color:#2b6cb0;margin-top:30px;border-left:5px solid #3182ce;padding-left:10px;}}
    table {{width:100%;border-collapse:collapse;margin-top:15px;}}
    th,td {{border:1px solid #e2e8f0;padding:14px;text-align:left;}}
    th {{background:#ebf8ff;color:#2b6cb0;}}
    tr:nth-child(even) {{background:#f8fafc;}}
    ul {{margin-top:8px;}}
    li {{margin-bottom:6px;line-height:1.6;}}
    .risk-box {{background:#fff5f5;border-left:5px solid #e53e3e;
                padding:16px;border-radius:6px;margin-top:12px;}}
  </style>
</head>
<body>
<div class="container">
  <h1>📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU</h1>
  <p>
    <b>Rapor Tarihi:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} &nbsp;|&nbsp;
    <b>Altyapı:</b> UCP 600 &amp; ISBP Hukuk Motoru v4.0
  </p>

  <h2>1. Kritik Süreler ve Vade Analizi</h2>
  <ul>{li_listesi("vade_analizi")}</ul>

  <h2>2. Finansal Vade ve Ödeme Takvimi</h2>
  <ul>{li_listesi("finansal_durum")}</ul>

  <h2>3. Incoterms ve Sigorta Hukuku (ICC 2020)</h2>
  <ul>{li_listesi("incoterms")}</ul>

  <h2>4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü</h2>
  <table>
    <tr><th>Belgeler</th><th>Detaylı İnceleme Kriteri</th><th>Durum</th></tr>
    {capraz_satirlar}
  </table>

  <h2>5. Konşimento ve Taşıma Hukuku Parametreleri</h2>
  <ul>{li_listesi("zorunlu_alanlar")}</ul>

  <h2>6. UCP 600 Hukuki Maddeleri Tablosu</h2>
  <table>
    <tr><th>Madde</th><th>Açıklama</th><th>Sistem Durumu</th><th>Bulgu</th></tr>
    {ucp_satirlar}
  </table>

  <h2>7. Risk Değerlendirmesi ve Rezerv Özeti</h2>
  <div class="risk-box">
    <ul>{li_listesi("risk_ozeti")}</ul>
  </div>
</div>
</body>
</html>"""

        with open(html_yolu, "w", encoding="utf-8") as f:
            f.write(html_text)
        print("[+] HTML Raporu Oluşturuldu.")

    # ------------------------------------------------------------------
    # Rapor üretimi — Word
    # ------------------------------------------------------------------
    def word_raporu_olustur(self) -> None:
        """Analiz sonuçlarını biçimlendirilmiş Word (.docx) belgesi olarak üretir."""
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

        # Ana başlık
        title_p = belge.add_paragraph()
        title_r = title_p.add_run(
            "📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU"
        )
        title_r.font.name      = "Arial"
        title_r.font.size      = Pt(16)
        title_r.font.bold      = True
        title_r.font.color.rgb = docx.shared.RGBColor(26, 54, 93)
        title_p.alignment      = WD_ALIGN_PARAGRAPH.CENTER

        meta_p = belge.add_paragraph()
        meta_r = meta_p.add_run(
            f"Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')} "
            "| Altyapı Sürümü: UCP 600 Hukuk Motoru v4.0"
        )
        meta_r.font.size      = Pt(9)
        meta_r.font.italic    = True
        meta_p.alignment      = WD_ALIGN_PARAGRAPH.CENTER
        belge.add_paragraph("-" * 60)

        # Bölüm başlığı yardımcısı
        def baslik_ekle(metin: str) -> None:
            h  = belge.add_paragraph()
            hr = h.add_run(metin)
            hr.font.name      = "Arial"
            hr.font.size      = Pt(13)
            hr.font.bold      = True
            hr.font.color.rgb = docx.shared.RGBColor(43, 108, 176)

        # Madde işaretli liste yardımcısı
        def madde_ekle(metinler: list[str]) -> None:
            for item in metinler:
                belge.add_paragraph(item.replace("**", ""), style="List Bullet")

        # Bölüm 1-3 (liste)
        baslik_ekle("1. Kritik Süreler ve Vade Analizi")
        madde_ekle(v.get("vade_analizi", []))

        baslik_ekle("2. Finansal Vade ve Ödeme Takvimi")
        madde_ekle(v.get("finansal_durum", []))

        baslik_ekle("3. Incoterms ve Sigorta Hukuku (ICC 2020)")
        madde_ekle(v.get("incoterms", []))

        # Bölüm 4 — çapraz kontrol tablosu
        baslik_ekle("4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü")
        t1 = belge.add_table(rows=1, cols=3)
        t1.style = "Table Grid"
        for i, ad in enumerate(["Belgeler", "İnceleme Detayı", "Durum"]):
            t1.rows[0].cells[i].text = ad
        for r in v.get("capraz_kontrol", []):
            hcrler = t1.add_row().cells
            hcrler[0].text = str(r.get("belge", ""))
            hcrler[1].text = str(r.get("detay", ""))
            hcrler[2].text = str(r.get("durum", ""))

        # Bölüm 5
        baslik_ekle("5. Konşimento ve Taşıma Hukuku Parametreleri")
        madde_ekle(v.get("zorunlu_alanlar", []))

        # Bölüm 6 — UCP tablosu
        baslik_ekle("6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu")
        t2 = belge.add_table(rows=1, cols=4)
        t2.style = "Table Grid"
        for i, ad in enumerate(["Madde", "Açıklama", "Sistem Durumu", "Bulgu"]):
            t2.rows[0].cells[i].text = ad
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                hcrler = t2.add_row().cells
                for i in range(4):
                    hcrler[i].text = str(m[i])

        # Bölüm 7 — risk özeti
        baslik_ekle("7. Risk Değerlendirmesi ve Rezerv Özeti")
        madde_ekle(v.get("risk_ozeti", []))

        belge.save(doc_yolu)
        print("[+] Word (.docx) Raporu Başarıyla Üretildi.")

    # ------------------------------------------------------------------
    # Ana akış
    # ------------------------------------------------------------------
    def baslat(self) -> None:
        """Sistemi başlatır: belgeleri tarar, analiz eder ve tüm raporları üretir."""
        print("[BİLGİ] Akreditif denetim sistemi başlatılıyor...")
        if self.depoyu_tara_ve_analiz_et():
            print(
                f"[BİLGİ] Belgeler yüklendi: "
                f"KUŞAT={'VAR' if self.depo['KUSAT']        else 'YOK'} | "
                f"FATURA={'VAR' if self.depo['FATURA']       else 'YOK'} | "
                f"KONŞİMENTO={'VAR' if self.depo['KONSIMENTO']  else 'YOK'} | "
                f"ÇEKİ={'VAR' if self.depo['CEKI_LISTESI']  else 'YOK'} | "
                f"SİGORTA={'VAR' if self.depo['SIGORTA']      else 'YOK'}"
            )
            self.ucp600_kural_motoru()
            self.markdown_raporu_olustur()
            self.html_raporu_olustur()
            self.word_raporu_olustur()
            print(f"[SONUÇ] Risk Puanı: {self.risk_puani} — {self._risk_sinifi()}")
            print("[SONUÇ] Tüm raporlar oluşturuldu.")
        else:
            print("[BİLGİ] Yüklenmiş belge bulunamadı veya dizin boş.")


# ===========================================================================
# Giriş noktası
# ===========================================================================
if __name__ == "__main__":
    motor = YapayZekaDisTicaretDenetleyici()
    motor.baslat()
ENDOFFILE
echo "OK"
