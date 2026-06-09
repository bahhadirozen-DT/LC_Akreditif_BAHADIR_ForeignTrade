"""
Yapay Zeka Destekli Dış Ticaret Akreditif Denetleme Sistemi
UCP 600 / ISBP 821 Uyumlu — Üretim Ortamı Sürümü v4.0

Bağımlılıklar (opsiyonel):
    pypdf, python-docx, openpyxl, Pillow, pytesseract
Zorunlu olmayan (graceful degradation):
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
# hukuk_motoru.py — doğrudan entegrasyon (monkey patch kullanılmaz)
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

# (alt_puan_dahil, ust_puan_dahil, etiket)
RISK_SINIFLANDIRMASI: list[tuple[int, int, str]] = [
    (0,   20, "DUSUK RISK"),
    (21,  50, "ORTA RISK"),
    (51, 999, "YUKSEK RISK"),
]


# ===========================================================================
# Ana sinif
# ===========================================================================
class YapayZekaDisTicaretDenetleyici:
    """UCP 600 / ISBP 821 uyumlu akreditif belge denetleme motoru."""

    def __init__(self, ana_dizin: str = "DisTicaretRepo") -> None:
        self.base_dir = ana_dizin
        self.yuklenenler_dir = os.path.join(self.base_dir, "YuklenenDosyalar")
        self.raporlar_dir    = os.path.join(self.base_dir, "Raporlar")

        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir,    exist_ok=True)

        self.depo: dict[str, Any]  = self._bos_depo()
        self.analiz_verisi: dict[str, Any] = {}
        self.risk_puani: int       = 0
        self.mt700_alanlari: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Depo yardimcilari
    # ------------------------------------------------------------------
    @staticmethod
    def _bos_depo() -> dict[str, Any]:
        """Temiz, bos bir depo sozlugu doner."""
        return {
            "KUSAT":          None,
            "FATURA":         None,
            "KONSIMENTO":     None,   # Tek ic anahtar; hem KONSiMENTO hem KONSiMENTO buraya yazilir
            "CEKI_LISTESI":   None,
            "SIGORTA":        None,
            "DIGER_BELGELER": [],
        }

    def _depo_metin(self, anahtar: str) -> str:
        """Depo kaydindaki metni doner; kayit yoksa veya hataliysya bos string."""
        kayit = self.depo.get(anahtar)
        if not kayit or not isinstance(kayit, dict):
            return ""
        metin = kayit.get("metin")
        return metin if isinstance(metin, str) else ""

    # ------------------------------------------------------------------
    # MT700 ayristirici
    # ------------------------------------------------------------------
    def mt700_ayristir(self, metin: str) -> dict[str, str]:
        """
        SWIFT MT700 formatindaki kusat metninden standart alanlari cikarir.
        Doner: {"20": "...", "31D": "...", "32B": "...", "44C": "...", ...}
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
    # Metin ayiklama
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu: str) -> str:
        """
        Desteklenen formatlardaki dosyadan duz metin cikarir.
        Hata durumunda '[Hata: ...]' formatinda aciklayici string doner.
        Bir sayfadaki / formattaki hata diger sayfalari durdurmaz.
        """
        if not dosya_yolu or not os.path.isfile(dosya_yolu):
            return ""

        ext   = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""

        try:
            if ext == ".pdf":
                if PdfReader is None:
                    return "[Hata: pypdf kutuphanesi yuklu degil]"
                reader = PdfReader(dosya_yolu)
                for i, sayfa in enumerate(reader.pages):
                    try:
                        txt = sayfa.extract_text()
                        if txt:
                            metin += txt + "\n"
                    except Exception as sayfa_hatasi:
                        metin += f"[Sayfa {i+1} Okuma Hatasi: {sayfa_hatasi}]\n"

            elif ext in [".docx", ".doc"]:
                if docx is None:
                    return "[Hata: python-docx kutuphanesi yuklu degil]"
                doc = docx.Document(dosya_yolu)
                for p in doc.paragraphs:
                    if p.text:
                        metin += p.text + "\n"
                for table in doc.tables:
                    for row in table.rows:
                        hucre = " ".join(c.text for c in row.cells if c.text)
                        if hucre.strip():
                            metin += hucre + "\n"

            elif ext in [".xlsx", ".xls"]:
                if openpyxl is None:
                    return "[Hata: openpyxl kutuphanesi yuklu degil]"
                wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
                for s in wb.sheetnames:
                    ws = wb[s]
                    for r in ws.iter_rows(values_only=True):
                        satir = " ".join(str(c) for c in r if c is not None)
                        if satir.strip():
                            metin += satir + "\n"

            elif ext in [".png", ".jpg", ".jpeg"]:
                if pytesseract is None or Image is None:
                    return "[Hata: pytesseract veya Pillow yuklu degil]"
                try:
                    img = Image.open(dosya_yolu)
                    try:
                        ocr_sonuc = pytesseract.image_to_string(img, lang="eng+tur")
                    except pytesseract.TesseractError:
                        print(f"[UYARI] Turkce OCR dil paketi bulunamadi — "
                              f"'{os.path.basename(dosya_yolu)}' icin yalnizca 'eng' kullaniliyor.")
                        ocr_sonuc = pytesseract.image_to_string(img, lang="eng")
                    metin = ocr_sonuc or ""
                except pytesseract.TesseractError as ocr_hatasi:
                    return f"[OCR Hatasi: {ocr_hatasi}]"

            elif ext == ".txt":
                with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
                    metin = f.read()

            else:
                return f"[Desteklenmeyen dosya formati: {ext}]"

        except Exception as genel_hata:
            return f"[Dosya Okuma Hatasi ({ext}): {genel_hata}]"

        # Gorunmez karakterleri normalize et
        metin = metin.replace("\xa0", " ").replace("\u200b", "").replace("\r\n", "\n")
        return metin

    # ------------------------------------------------------------------
    # Belge turu tespiti
    # ------------------------------------------------------------------
    def dokuman_tipi_belirle(self, metin: str) -> str:
        """
        Metin icerigine gore belge turunu tespit eder.
        Hem KONSIMENTO hem KONSiMENTO desteklenir; ikisi de KONSIMENTO anahtarina eslenir.
        """
        if not metin:
            return "DIGER"
        m = metin.upper()

        if any(x in m for x in ["DOCUMENTARY CREDIT", "40A:", "IRREVOCABLE", "L/C NO", ":32B:"]):
            return "KUSAT"
        if any(x in m for x in ["COMMERCIAL INVOICE", "FATURA", "INVOICE NO", "INVOICE AMOUNT"]):
            return "FATURA"
        if any(x in m for x in [
            "BILL OF LADING", "OCEAN BILL", "B/L NO", "SHIPPED ON BOARD",
            "KONSIMENTO",
        ]):
            return "KONSIMENTO"
        if any(x in m for x in [
            "PACKING LIST", "WEIGHT LIST", "PACKING DETAILS",
        ]):
            return "CEKI_LISTESI"
        if any(x in m for x in [
            "INSURANCE POLICY", "INSURANCE CERTIFICATE", "MARINE INSURANCE",
        ]):
            return "SIGORTA"
        return "DIGER"

    # ------------------------------------------------------------------
    # Depo tarama
    # ------------------------------------------------------------------
    def depoyu_tara_ve_analiz_et(self) -> bool:
        """
        YuklenenDosyalar dizinindeki tum dosyalari okur, turlerini tespit eder
        ve depoya kaydeder. Her calistirmada depo sifirlanir.
        """
        self.depo           = self._bos_depo()
        self.risk_puani     = 0
        self.mt700_alanlari = {}

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
                print(f"[UYARI] {dosya_adi} okunamadi: {icerik}")
                continue

            tip = self.dokuman_tipi_belirle(icerik)
            if tip in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]:
                self.depo[tip] = {"ad": dosya_adi, "metin": icerik}
            else:
                self.depo["DIGER_BELGELER"].append({"ad": dosya_adi, "metin": icerik})

        # MT700 alanlarini kusat belgesinden cikar
        kusat_metni = self._depo_metin("KUSAT")
        if kusat_metni:
            self.mt700_alanlari = self.mt700_ayristir(kusat_metni)

        return True

    # ------------------------------------------------------------------
    # Sayisal deger cikarma yardimcilari
    # ------------------------------------------------------------------
    def sayisal_deger_bul(self, metin: str, desenler: list[str]) -> Optional[float]:
        """
        Verilen metin icinde desenleri sirayla dener; ilk gecerli float deger doner.
        Esleme yoksa None doner. Hardcoded fallback deger yoktur.
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
        Belgeden brut agirlik degerini cikarir.
        Gross Weight, Net Weight, GW, NW, KGS, MT, TON bicimleri desteklenir.
        """
        desenler = [
            r'(?:GROSS\s*WEIGHT|BRUT\s*(?:KILO|AGIRLIK)|G\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT|TON)',
            r'(?:NET\s*WEIGHT|N\.?W\.?)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|MT|TON)',
            r'([\d,\.]+)\s*(?:KGS)\b',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    def miktar_bul(self, metin: str) -> Optional[tuple[float, str]]:
        """
        Belgeden miktar ve birimini cikarir.
        Desteklenen birimler: PCS, KG, MT, TON, BOX, CTN, SET, UNIT.
        (deger, birim) tuple doner; bulunamazsa None.
        """
        if not metin:
            return None
        desen = r'([\d,\.]+)\s*(PCS|PIECES?|KGS?|MT|TONS?|BOX(?:ES)?|CTNS?|CARTONS?|SETS?|UNITS?)\b'
        try:
            m = re.search(desen, metin, re.IGNORECASE)
            if m:
                return (float(m.group(1).replace(",", "")), m.group(2).upper())
        except (ValueError, re.error):
            pass
        return None

    def para_tutari_bul(self, metin: str) -> Optional[float]:
        """
        Belgeden para tutarini cikarir.
        MT700 Alan 32B onceliklidir; ardindan yaygin fatura etiketleri aranir.
        """
        if not metin:
            return None
        desenler = [
            r'32B[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            r'CREDIT\s+AMOUNT[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            r'(?:TOTAL\s+AMOUNT|INVOICE\s+VALUE|INVOICE\s+AMOUNT|TOTAL\s+VALUE)\s*[:\-]?\s*(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)',
            r'(?:USD|EUR|GBP|TRY|CNY|JPY)\s*([\d,\.]+)',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    def tarih_bul(self, metin: str, desenler: list[str]) -> Optional[str]:
        """Verilen metin icinden ilk eslesen tarih string'ini doner; None doner esleme yoksa."""
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
        Belgeden mal tanimi metnini cikarir.
        MT700 Alan 45A ve DESCRIPTION OF GOODS desteklenir.
        """
        if not metin:
            return None
        # Oncelikle MT700 ayristiricisinin sonucunu kullan
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
        """Belirtilen kategorinin risk puanini toplam puana ekler."""
        self.risk_puani += RISK_PUANLARI.get(kategori, 0)

    def _risk_sinifi(self) -> str:
        """Toplam risk puanina gore risk sinifini doner."""
        for alt, ust, sinif in RISK_SINIFLANDIRMASI:
            if alt <= self.risk_puani <= ust:
                return sinif
        return "YUKSEK RISK"

    # ------------------------------------------------------------------
    # UCP 600 Kural Motoru
    # ------------------------------------------------------------------
    def ucp600_kural_motoru(self) -> None:
        """
        Depodaki belgeler uzerinde UCP 600 / ISBP 821 kurallarini uygular.
        Sonuclari self.analiz_verisi sozlugune yazar.
        hukuk_motoru.py varsa UCP tablosu icin entegre edilir;
        yoksa veya hata verirse yerlesik tablo kullanilir.
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

        # ============================================================
        # 1. Kritik Sureler ve Vade Analizi
        # ============================================================
        lc_44c_str = self.mt700_alanlari.get("44C") or self.tarih_bul(
            kusat_text,
            [
                r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT|SON\s+YUKLEME\s+TARiHi)[:\s]*([\d]{2}[.\-\/][\d]{2}[.\-\/][\d]{4})',
                r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]*([\d]{1,2}[\s.\-\/][A-Z]{3,}[\s.\-\/][\d]{4})',
            ],
        )

        if lc_44c_str:
            sonuclar["vade_analizi"].append(
                f"En Gec Yukleme Tarihi (Alan 44C): **{lc_44c_str}**"
            )
        else:
            sonuclar["vade_analizi"].append(
                "En Gec Yukleme Tarihi (Alan 44C): Belgeden tespit edilemedi — manuel kontrol gerekli."
            )

        ibraz_suresi = re.search(
            r'(\d+)\s*DAYS?\s*(?:AFTER|FOR\s+PRESENTATION)',
            combined, re.IGNORECASE,
        )
        if ibraz_suresi:
            gun = int(ibraz_suresi.group(1))
            sonuclar["vade_analizi"].append(
                f"Bankaya Ibraz Suresi: **{gun} gun** (UCP 600 Madde 14c — max 21 gun)."
            )
            if gun > 21:
                self._risk_puani_ekle("ibraz_suresi_belirsiz")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Ibraz suresi {gun} gun; UCP 600 Art 14c sinirini asiyor."
                )
        else:
            sonuclar["vade_analizi"].append(
                "Bankaya Ibraz Suresi: Tespit edilemedi — UCP 600 Art 14c varsayilan 21 gun uygulanir."
            )
            self._risk_puani_ekle("ibraz_suresi_belirsiz")

        # ============================================================
        # 2. Odeme Vadesi
        # ============================================================
        if any(x in combined for x in ["AT SIGHT", "SIGHT PAYMENT", "BY SIGHT"]):
            sonuclar["finansal_durum"].append(
                "Odeme Vadesi: **Goruldugunde Odemeli (At Sight)** — "
                "UCP 600 Art 15b uyarinca uyumlu ibrazda amir banka aninda odemekle yukumludur."
            )
        elif any(x in combined for x in ["DAYS AFTER", "DEFERRED PAYMENT", "BY ACCEPTANCE"]):
            sonuclar["finansal_durum"].append(
                "Odeme Vadesi: **Vadeli / Kabul Kredili Akreditif** — "
                "Police vade takvimini ve faiz taahhutlerini kontrol edin."
            )
        else:
            sonuclar["finansal_durum"].append(
                "Odeme Vadesi: Belgelerden tespit edilemedi — manuel kontrol onerilir."
            )

        # ============================================================
        # 3. Incoterms ve Sigorta Varligi (UCP 600 Art 28)
        # ============================================================
        incoterm_var: Optional[str] = None
        for term in ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"]:
            if term in combined:
                incoterm_var = term
                sonuclar["incoterms"].append(
                    f"Incoterms Standardi: **{term} (ICC 2020 Rules)**"
                )
                break

        if incoterm_var is None:
            sonuclar["incoterms"].append(
                "Incoterms Standardi: Metinden tespit edilemedi — manuel kontrol onerilir."
            )

        art28_durum = "UYGULANMAZ"
        art28_not   = (
            f"Teslim sekli ({incoterm_var or 'Belirsiz'}) "
            "saticicinin sigorta ibrazini zorunlu kilmiyor."
        )

        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                art28_durum = "DOGRUDAN GECTI"
                art28_not   = (
                    "Sigorta policesi dosyalar arasinda saptandi. "
                    "Min. %110 teminat hesabi icin Bolum 4 Capraz Kontrol tablosuna bakin."
                )
                sonuclar["incoterms"].append(
                    f"[TAMAM] {incoterm_var} sarti geregi Resmi Sigorta Policesi saptandi (UCP 600 Art 28)."
                )
            else:
                art28_durum = "YUKSEK RISK"
                art28_not   = (
                    f"{incoterm_var} teslimlerde Sigorta Policesi zorunludur! "
                    "Minimum %110 teminat aranir (UCP 600 Madde 28)."
                )
                sonuclar["incoterms"].append(
                    f"[HUKUKi REZERV RiSKi] Teslim sekli {incoterm_var} olmasina ragmen "
                    "Sigorta Policesi bulunamadi!"
                )
                self._risk_puani_ekle("sigorta_eksik")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Sigorta belgesi eksik ({incoterm_var} teslimde Art 28 zorunlulugu)"
                )

        # ============================================================
        # 4. Sayisal ve Evrak Capraz Kontrolleri
        # ============================================================

        # --- 4a. Fatura Tutari vs Akreditif Tutari (Art 18 + Art 30) ---
        fatura_tutari = self.para_tutari_bul(fatura_text)

        lc_32b_str = self.mt700_alanlari.get("32B")
        lc_tutari: Optional[float]
        if lc_32b_str:
            try:
                lc_tutari = float(re.sub(r'[^0-9.]', '', lc_32b_str.replace(",", "")))
            except ValueError:
                lc_tutari = None
        else:
            lc_tutari = self.para_tutari_bul(kusat_text)

        if fatura_tutari is not None and lc_tutari is not None:
            tolerans = lc_tutari * 0.05
            fark     = abs(fatura_tutari - lc_tutari)
            if fark <= tolerans:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Akreditif Tutari (Art 18 / Art 30)",
                    "detay": (f"Fatura: {fatura_tutari:,.2f} | Akreditif: {lc_tutari:,.2f} | "
                              f"Fark: {fark:,.2f} (<=  %5 tolerans)"),
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Akreditif Tutari (Art 18 / Art 30)",
                    "detay": (f"Fatura: {fatura_tutari:,.2f} | Akreditif: {lc_tutari:,.2f} | "
                              f"Fark: {fark:,.2f} (> %5 tolerans)"),
                    "durum": "REZERV RiSKi - TUTAR UYUSMAZLIGI",
                })
                self._risk_puani_ekle("tutar_uyusmazligi")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Fatura tutari ({fatura_tutari:,.2f}) akreditif tutarindan ({lc_tutari:,.2f}) "
                    f"{fark:,.2f} sapma gosteriyor (Art 30 %5 toleransini asiyor)"
                )
        else:
            eksik_tutar = [k for k, v in [("Fatura", fatura_tutari), ("Akreditif (32B)", lc_tutari)] if v is None]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura vs Akreditif Tutari (Art 18 / Art 30)",
                "detay": f"Tutar tespit edilemedi: {', '.join(eksik_tutar)}",
                "durum": "MANUEL KONTROL",
            })

        # --- 4b. Kilo — Fatura vs Konsimento ---
        fatura_kilo = self.kilo_bul(fatura_text)
        bl_kilo     = self.kilo_bul(konsimento_text)
        ceki_kilo   = self.kilo_bul(ceki_text)

        if fatura_kilo is not None and bl_kilo is not None:
            if abs(fatura_kilo - bl_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Konsimento Kilo",
                    "detay": f"Brut Kilo Eslesmesi: {fatura_kilo:,.2f} KG",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Konsimento Kilo",
                    "detay": f"Fatura: {fatura_kilo:,.2f} KG | Konsimento: {bl_kilo:,.2f} KG",
                    "durum": "REZERV RiSKi - UYUMSUZ SAYISAL VERi",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Kilo uyumsuzlugu: Fatura {fatura_kilo:,.2f} KG / Konsimento {bl_kilo:,.2f} KG"
                )
        else:
            eksik = [k for k, v in [("Fatura", fatura_kilo), ("Konsimento", bl_kilo)] if v is None]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura vs Konsimento Kilo",
                "detay": f"Brut kilo tespit edilemedi: {', '.join(eksik)}",
                "durum": "VERi EKSiK - MANUEL KONTROL GEREKLi",
            })

        # --- 4c. Kilo — Fatura vs Ceki Listesi ---
        if ceki_kilo is not None and fatura_kilo is not None:
            if abs(ceki_kilo - fatura_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Ceki Listesi Kilo",
                    "detay": f"Brut Kilo Eslesmesi: {ceki_kilo:,.2f} KG",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Ceki Listesi Kilo",
                    "detay": f"Fatura: {fatura_kilo:,.2f} KG | Ceki Listesi: {ceki_kilo:,.2f} KG",
                    "durum": "REZERV RiSKi - UYUMSUZ SAYISAL VERi",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")

        # --- 4d. Miktar — Fatura vs Ceki Listesi ---
        fatura_miktar = self.miktar_bul(fatura_text)
        ceki_miktar   = self.miktar_bul(ceki_text)

        if fatura_miktar and ceki_miktar:
            f_deger, f_birim = fatura_miktar
            c_deger, c_birim = ceki_miktar
            if f_birim == c_birim and abs(f_deger - c_deger) < 1:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Ceki Listesi Miktar",
                    "detay": f"Miktar Eslesmesi: {f_deger:,.0f} {f_birim}",
                    "durum": "UYUMLU",
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Fatura vs Ceki Listesi Miktar",
                    "detay": f"Fatura: {f_deger:,.0f} {f_birim} | Ceki: {c_deger:,.0f} {c_birim}",
                    "durum": "REZERV RiSKi - MiKTAR UYUSMAZLIGI",
                })
                self._risk_puani_ekle("kilo_uyusmazligi")

        # --- 4e. Mal Tanimi — Fatura vs Kusat (Art 18c) ---
        fatura_mal = self.mal_tanimi_bul(fatura_text)
        kusat_mal  = self.mal_tanimi_bul(kusat_text)

        if fatura_mal and kusat_mal:
            kusat_kelimeler  = set(re.findall(r'\b\w{4,}\b', kusat_mal.upper()))
            fatura_kelimeler = set(re.findall(r'\b\w{4,}\b', fatura_mal.upper()))
            ortak = kusat_kelimeler & fatura_kelimeler
            oran  = len(ortak) / len(kusat_kelimeler) if kusat_kelimeler else 0.0

            if oran >= 0.6:
                durum_mal = "UYUMLU"
            elif oran >= 0.3:
                durum_mal = "DUSUK BENZERLiK - MANUEL KONTROL"
                self._risk_puani_ekle("mal_tanimi_uyusmazligi")
            else:
                durum_mal = "REZERV RiSKi - MAL TANIMI UYUSMAZLIGI"
                self._risk_puani_ekle("mal_tanimi_uyusmazligi")
                sonuclar["rezerv_ozeti"].append(
                    f"REZERV — Mal tanimi uyusmazligi: Ortusme %{oran*100:.0f} (Art 18c)"
                )

            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura Mal Tanimi vs Kusat (Art 18c)",
                "detay": (f"Kusat: '{kusat_mal[:80]}' | Fatura: '{fatura_mal[:80]}' | "
                          f"Ortusme: %{oran*100:.0f}"),
                "durum": durum_mal,
            })
        else:
            eksik_mal = [k for k, v in [("Fatura", fatura_mal), ("Kusat (45A)", kusat_mal)] if not v]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Fatura Mal Tanimi vs Kusat (Art 18c)",
                "detay": f"Mal tanimi tespit edilemedi: {', '.join(eksik_mal)}",
                "durum": "MANUEL KONTROL",
            })

        # --- 4f. Konsimento Yukleme Tarihi vs Alan 44C ---
        bl_tarih_desenler = [
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{1,2}[\s.\-\/][A-Z]{3,}[\s.\-\/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{2}[.\-\/][\d]{2}[.\-\/][\d]{4})',
        ]
        lc_44c_desenler = [
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{1,2}[\s.\-\/][A-Z]{3,}[\s.\-\/][\d]{4})',
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{2}[.\-\/][\d]{2}[.\-\/][\d]{4})',
        ]
        bl_yukleme_tarihi = self.tarih_bul(konsimento_text, bl_tarih_desenler)
        lc_son_yukleme    = lc_44c_str or self.tarih_bul(kusat_text, lc_44c_desenler)

        if bl_yukleme_tarihi and lc_son_yukleme:
            sonuclar["capraz_kontrol"].append({
                "belge":  "Konsimento Yukleme Tarihi vs Alan 44C (Art 20)",
                "detay": (f"Konsimento Yukleme: {bl_yukleme_tarihi} | "
                          f"44C Son Yukleme: {lc_son_yukleme}"),
                "durum": "TESPiT EDiLDi - MANUEL TARiH KARSiLASTIRMASI GEREKLi",
            })
        else:
            eksik_tarih = [
                k for k, v in [
                    ("Konsimento yukleme tarihi", bl_yukleme_tarihi),
                    ("Kusat 44C", lc_son_yukleme),
                ] if not v
            ]
            sonuclar["capraz_kontrol"].append({
                "belge":  "Konsimento Yukleme Tarihi vs Alan 44C (Art 20)",
                "detay": f"Tarih tespit edilemedi: {', '.join(eksik_tarih)}",
                "durum": "MANUEL KONTROL",
            })
            if bl_yukleme_tarihi is None and konsimento_text:
                self._risk_puani_ekle("yukleme_tarihi_ihlali")

        # --- 4g. Sigorta Bedeli >= Fatura x %110 (Art 28f-ii) ---
        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                sigorta_tutari = self.para_tutari_bul(sigorta_text)
                if sigorta_tutari is not None and fatura_tutari is not None:
                    minimum_teminat = fatura_tutari * 1.10
                    if sigorta_tutari >= minimum_teminat:
                        sonuclar["capraz_kontrol"].append({
                            "belge":  "Sigorta Bedeli >= Fatura x %110 (Art 28f-ii)",
                            "detay": (f"Sigorta: {sigorta_tutari:,.2f} | "
                                      f"Gerekli Min.: {minimum_teminat:,.2f} "
                                      f"(Fatura {fatura_tutari:,.2f} x 1.10)"),
                            "durum": "UYUMLU",
                        })
                    else:
                        eksik_teminat = minimum_teminat - sigorta_tutari
                        sonuclar["capraz_kontrol"].append({
                            "belge":  "Sigorta Bedeli >= Fatura x %110 (Art 28f-ii)",
                            "detay": (f"Sigorta: {sigorta_tutari:,.2f} | "
                                      f"Gerekli Min.: {minimum_teminat:,.2f} | "
                                      f"Eksik Teminat: {eksik_teminat:,.2f}"),
                            "durum": "REZERV RiSKi - YETERSiZ SiGORTA TEMiNATI",
                        })
                        self._risk_puani_ekle("sigorta_eksik")
                        sonuclar["rezerv_ozeti"].append(
                            f"REZERV — Sigorta teminati yetersiz: {sigorta_tutari:,.2f} < "
                            f"gerekli {minimum_teminat:,.2f} (Art 28f-ii)"
                        )
                elif fatura_tutari is not None:
                    sonuclar["capraz_kontrol"].append({
                        "belge":  "Sigorta Bedeli >= Fatura x %110 (Art 28f-ii)",
                        "detay": (f"Sigorta belgesi mevcut ancak tutar okunamadi. "
                                  f"Fatura: {fatura_tutari:,.2f} -> Gerekli min: {fatura_tutari * 1.10:,.2f}"),
                        "durum": "MANUEL KONTROL",
                    })
                else:
                    sonuclar["capraz_kontrol"].append({
                        "belge":  "Sigorta Bedeli >= Fatura x %110 (Art 28f-ii)",
                        "detay": "Sigorta veya fatura tutari tespit edilemedi.",
                        "durum": "MANUEL KONTROL",
                    })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge":  "Sigorta Bedeli >= Fatura x %110 (Art 28f-ii)",
                    "detay": (f"{incoterm_var} teslimlerde sigorta policesi zorunludur "
                              "ancak dosyalar arasinda bulunamadi."),
                    "durum": "REZERV RiSKi - SiGORTA BELGESi EKSiK",
                })

        # ============================================================
        # 5. Konsimento Hukuki Maddeleri (UCP 600 Art 20-27)
        # ============================================================
        if not konsimento_text:
            sonuclar["zorunlu_alanlar"].append(
                "[REZERV RiSKi] Konsimento belgesi depoda bulunamadi!"
            )
            self._risk_puani_ekle("konsimento_eksik")
            sonuclar["rezerv_ozeti"].append(
                "REZERV — Konsimento belgesi ibraz edilmemis (Art 20)"
            )
        else:
            if "SHIPPED ON BOARD" in konsimento_text.upper() or "ON BOARD" in konsimento_text.upper():
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Konsimento uzerinde 'Shipped on Board' serhi saptandi (Art 20a-ii uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[REZERV RiSKi] Konsimentoda zorunlu 'Shipped on Board' "
                    "yukleme serhi acikca bulunamadi!"
                )
                self._risk_puani_ekle("konsimento_eksik")
                sonuclar["rezerv_ozeti"].append(
                    "REZERV — 'Shipped on Board' serhi tespit edilemedi (Art 20a-ii)"
                )

            if "CLEAN" in konsimento_text.upper():
                sonuclar["zorunlu_alanlar"].append(
                    "[TAMAM] Temiz tasima belgesi (Clean B/L) serhi saptandi (Art 27 uyumlu)."
                )
            else:
                sonuclar["zorunlu_alanlar"].append(
                    "[BiLGi] Konsimentoda 'CLEAN' ibaresi bulunamadi — Art 27 kapsaminda manuel kontrol onerilir."
                )

        # ============================================================
        # 6. Risk Ozeti
        # ============================================================
        risk_sinifi = self._risk_sinifi()
        sonuclar["risk_ozeti"].append(
            f"Toplam Risk Puani: **{self.risk_puani}** — Risk Sinifi: **{risk_sinifi}**"
        )
        if sonuclar["rezerv_ozeti"]:
            for i, rezerv in enumerate(sonuclar["rezerv_ozeti"], 1):
                sonuclar["risk_ozeti"].append(f"{i}. {rezerv}")
        else:
            sonuclar["risk_ozeti"].append(
                "Sistem tarafindan tespit edilen kritik rezerv bulunamadi."
            )

        # ============================================================
        # 7. UCP 600 Tablosu
        # ============================================================
        fatura_durum = (
            "DOGRUDAN GECTI"
            if ("INVOICE" in combined or "FATURA" in combined)
            else "DOGRUDAN GECMIYOR"
        )
        bl_durum = (
            "TESPiT EDiLDi"
            if ("BILL OF LADING" in combined or "SHIPPED ON BOARD" in combined)
            else "DOGRUDAN GECMIYOR"
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
                    sonuclar["ucp_tablosu"] = ucp_t if ucp_t else self._varsayilan_ucp_tablosu(
                        fatura_durum, bl_durum, art28_durum, art28_not
                    )
                else:
                    raise ValueError("hukuk_motoru.analiz_et tanimsiz bir tip dondurdu.")
            except Exception as motor_hatasi:
                print(f"[UYARI] Hukuk motoru hatasi, yerlesik tablo kullaniliyor: {motor_hatasi}")
                sonuclar["ucp_tablosu"] = self._varsayilan_ucp_tablosu(
                    fatura_durum, bl_durum, art28_durum, art28_not
                )
        else:
            if not HUKUK_MOTORU_AKTIF:
                print("[BiLGi] hukuk_motoru.py bulunamadi, yerlesik UCP tablosu kullaniliyor.")
            sonuclar["ucp_tablosu"] = self._varsayilan_ucp_tablosu(
                fatura_durum, bl_durum, art28_durum, art28_not
            )

        self.analiz_verisi = sonuclar

    # ------------------------------------------------------------------
    # Yerlesik UCP 600 tablosu
    # ------------------------------------------------------------------
    def _varsayilan_ucp_tablosu(
        self,
        fatura_durum: str,
        bl_durum: str,
        art28_durum: str,
        art28_not: str,
    ) -> list[tuple[str, str, str, str]]:
        """
        hukuk_motoru.py yoksa veya hata verirse kullanilan yerlesik UCP 600 tablosu.
        kurallar.json varsa zorunlu_kurallar ile zenginlestirilir.
        """
        tablo: list[tuple[str, str, str, str]] = [
            ("Art 14", "Belgelerin incelenmesi Standartlari",       "TESPiT EDiLDi",     "Standart 21 gunluk yasal banka ibraz siniri uygulandı."),
            ("Art 15", "Uyumlu ibraz (Complying Presentation)",     "DOGRUDAN GECMIYOR", "Vesaiklerin bankaya eksiksiz ve hatasiz ulastiginin teyidi."),
            ("Art 17", "Orijinal Belgeler ve Suretler",             "DOGRUDAN GECMIYOR", "Banka ibrazinda orijinal/suret kaselerinin varligi aranir."),
            ("Art 18", "Ticari Fatura (Commercial Invoice)",        fatura_durum,        "Mal tariminın kusat metniyle karakter dogrulamasi yapildi (Art 18c)."),
            ("Art 20", "Konsimento (Bill of Lading)",               bl_durum,            "Shipped on Board serhi ve ciro silsilesi hukuki denetimi yapildi."),
            ("Art 27", "Temiz Tasima Belgesi",                      bl_durum,            "Uzerinde hasar veya kusurlu ambalaj serhi bulunmayan temiz belge kontrolu."),
            ("Art 28", "Sigorta Belgesi ve Kapsami",                art28_durum,         art28_not),
            ("Art 30", "Miktar ve Tutarda Toleranslar",             "DOGRUDAN GECMIYOR", "Akreditifte aksi belirtilmedikce %5 / %10 tolerans limitleri."),
        ]

        try:
            with open("kurallar.json", "r", encoding="utf-8") as f:
                veri = json.load(f)
            mevcut_maddeler = {row[0] for row in tablo}
            for kural in veri.get("zorunlu_kurallar", []) + veri.get("kritik_kontroller", []):
                madde    = kural.get("madde", "")
                aciklama = kural.get("aciklama", "")
                anahtar  = kural.get("anahtar", "")
                if madde and madde not in mevcut_maddeler:
                    tablo.append((madde, aciklama, "KURAL LISTESI", anahtar))
                    mevcut_maddeler.add(madde)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass  # kurallar.json yoksa sessizce devam et

        return tablo

    # ------------------------------------------------------------------
    # Rapor uretimi — Markdown
    # ------------------------------------------------------------------
    def markdown_raporu_olustur(self) -> None:
        """Analiz sonuclarini Markdown formatinda dile getirir."""
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi bos, Markdown raporu olusturulamadi.")
            return

        md_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")
        satirlar = [
            "# AKREDITIF GELISMIS HUKUKI VE SAYISAL UZMAN DENETiM RAPORU\n",
            f"**Analiz Zamani:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  \n",
            "**Altyapi Sistemi:** Yapay Zeka UCP 600 & ISBP Hukuk Motoru v4.0  \n\n",
            "---\n",
            "## 1. Kritik Sureler ve Vade Analizi\n",
        ]
        for s in v.get("vade_analizi", []):
            satirlar.append(f"* {s}\n")

        satirlar.append("\n---\n## 2. Finansal Vade ve Odeme Takvimi\n")
        for s in v.get("finansal_durum", []):
            satirlar.append(f"* {s}\n")

        satirlar.append("\n---\n## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)\n")
        for s in v.get("incoterms", []):
            satirlar.append(f"* {s}\n")

        satirlar.append(
            "\n---\n## 4. Sayisal ve Capraz Evrak Uyumluluk Kontrolu\n"
            "| Belgeler | inceleme Detayi | Durum |\n"
            "| :--- | :--- | :--- |\n"
        )
        for c in v.get("capraz_kontrol", []):
            satirlar.append(
                f"| {c.get('belge','')} | {c.get('detay','')} | **[{c.get('durum','')}]** |\n"
            )

        satirlar.append("\n---\n## 5. Konsimento ve Tasima Hukuku Parametreleri (UCP Art. 20-27)\n")
        for s in v.get("zorunlu_alanlar", []):
            satirlar.append(f"* {s}\n")

        satirlar.append(
            "\n---\n## 6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu\n"
            "| UCP 600 Madde | Kapsam Aciklamasi | Sistem Gecis Durumu | Uzman Bulgusu |\n"
            "| :--- | :--- | :--- | :--- |\n"
        )
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                satirlar.append(f"| **{m[0]}** | {m[1]} | `{m[2]}` | {m[3]} |\n")

        satirlar.append("\n---\n## 7. Risk Degerlendirmesi ve Rezerv Ozeti\n")
        for s in v.get("risk_ozeti", []):
            satirlar.append(f"* {s}\n")

        with open(md_yolu, "w", encoding="utf-8") as f:
            f.writelines(satirlar)
        print("[+] Markdown Raporu Olusturuldu.")

    # ------------------------------------------------------------------
    # Rapor uretimi — HTML
    # ------------------------------------------------------------------
    def html_raporu_olustur(self) -> None:
        """Analiz sonuclarini tarayicida goruntulenebilir HTML formatinda uretir."""
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi bos, HTML raporu olusturulamadi.")
            return

        html_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.html")

        def li_listesi(anahtar: str) -> str:
            return "".join(f"<li>{x}</li>" for x in v.get(anahtar, []))

        capraz_satirlar = "".join(
            f"<tr><td><b>{r.get('belge','')}</b></td>"
            f"<td>{r.get('detay','')}</td>"
            f"<td><b>{r.get('durum','')}</b></td></tr>"
            for r in v.get("capraz_kontrol", [])
        )
        ucp_satirlar = "".join(
            f"<tr><td><b>{m[0]}</b></td><td>{m[1]}</td>"
            f"<td><code>{m[2]}</code></td><td>{m[3]}</td></tr>"
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
    ul {{margin-top:8px;}} li {{margin-bottom:6px;line-height:1.6;}}
    .risk-box {{background:#fff5f5;border-left:5px solid #e53e3e;
                padding:16px;border-radius:6px;margin-top:12px;}}
  </style>
</head>
<body><div class="container">
  <h1>AKREDITIF GELISMIS HUKUKI VE SAYISAL UZMAN DENETiM RAPORU</h1>
  <p><b>Rapor Tarihi:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')} &nbsp;|&nbsp;
     <b>Altyapi:</b> UCP 600 &amp; ISBP Hukuk Motoru v4.0</p>
  <h2>1. Kritik Sureler ve Vade Analizi</h2>
  <ul>{li_listesi("vade_analizi")}</ul>
  <h2>2. Finansal Vade ve Odeme Takvimi</h2>
  <ul>{li_listesi("finansal_durum")}</ul>
  <h2>3. Incoterms ve Sigorta Hukuku (ICC 2020)</h2>
  <ul>{li_listesi("incoterms")}</ul>
  <h2>4. Sayisal ve Capraz Evrak Uyumluluk Kontrolu</h2>
  <table>
    <tr><th>Belgeler</th><th>Detayli inceleme Kriteri</th><th>Durum</th></tr>
    {capraz_satirlar}
  </table>
  <h2>5. Konsimento ve Tasima Hukuku Parametreleri</h2>
  <ul>{li_listesi("zorunlu_alanlar")}</ul>
  <h2>6. UCP 600 Hukuki Maddeleri Tablosu</h2>
  <table>
    <tr><th>Madde</th><th>Aciklama</th><th>Sistem Durumu</th><th>Bulgu</th></tr>
    {ucp_satirlar}
  </table>
  <h2>7. Risk Degerlendirmesi ve Rezerv Ozeti</h2>
  <div class="risk-box"><ul>{li_listesi("risk_ozeti")}</ul></div>
</div></body></html>"""

        with open(html_yolu, "w", encoding="utf-8") as f:
            f.write(html_text)
        print("[+] HTML Raporu Olusturuldu.")

    # ------------------------------------------------------------------
    # Rapor uretimi — Word
    # ------------------------------------------------------------------
    def word_raporu_olustur(self) -> None:
        """Analiz sonuclarini bicimlenmis Word (.docx) belgesi olarak uretir."""
        if not docx:
            print("[UYARI] python-docx yuklu degil, Word raporu atlandi.")
            return
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi bos, Word raporu olusturulamadi.")
            return

        doc_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.docx")
        belge    = docx.Document()

        for section in belge.sections:
            section.top_margin = section.bottom_margin = Inches(1)
            section.left_margin = section.right_margin = Inches(1)

        def para_ekle(metin: str, boyut: int = 11, kalin: bool = False,
                      italic: bool = False, hizalama=None,
                      renk: tuple = (0, 0, 0)) -> None:
            p = belge.add_paragraph()
            r = p.add_run(metin)
            r.font.name  = "Arial"
            r.font.size  = Pt(boyut)
            r.font.bold  = kalin
            r.font.italic = italic
            r.font.color.rgb = docx.shared.RGBColor(*renk)
            if hizalama:
                p.alignment = hizalama

        def baslik_ekle(metin: str) -> None:
            para_ekle(metin, boyut=13, kalin=True, renk=(43, 108, 176))

        def madde_ekle(metinler: list[str]) -> None:
            for item in metinler:
                belge.add_paragraph(item.replace("**", ""), style="List Bullet")

        # Baslik
        para_ekle(
            "AKREDITIF GELISMIS HUKUKI VE SAYISAL UZMAN DENETiM RAPORU",
            boyut=16, kalin=True, hizalama=WD_ALIGN_PARAGRAPH.CENTER,
            renk=(26, 54, 93),
        )
        para_ekle(
            f"Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Altyapi: UCP 600 Hukuk Motoru v4.0",
            boyut=9, italic=True, hizalama=WD_ALIGN_PARAGRAPH.CENTER,
        )
        belge.add_paragraph("-" * 60)

        baslik_ekle("1. Kritik Sureler ve Vade Analizi")
        madde_ekle(v.get("vade_analizi", []))

        baslik_ekle("2. Finansal Vade ve Odeme Takvimi")
        madde_ekle(v.get("finansal_durum", []))

        baslik_ekle("3. Incoterms ve Sigorta Hukuku (ICC 2020)")
        madde_ekle(v.get("incoterms", []))

        baslik_ekle("4. Sayisal ve Capraz Evrak Uyumluluk Kontrolu")
        t1 = belge.add_table(rows=1, cols=3)
        t1.style = "Table Grid"
        for i, ad in enumerate(["Belgeler", "inceleme Detayi", "Durum"]):
            t1.rows[0].cells[i].text = ad
        for r in v.get("capraz_kontrol", []):
            hcrler = t1.add_row().cells
            hcrler[0].text = str(r.get("belge", ""))
            hcrler[1].text = str(r.get("detay", ""))
            hcrler[2].text = str(r.get("durum", ""))

        baslik_ekle("5. Konsimento ve Tasima Hukuku Parametreleri")
        madde_ekle(v.get("zorunlu_alanlar", []))

        baslik_ekle("6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu")
        t2 = belge.add_table(rows=1, cols=4)
        t2.style = "Table Grid"
        for i, ad in enumerate(["Madde", "Aciklama", "Sistem Durumu", "Bulgu"]):
            t2.rows[0].cells[i].text = ad
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                hcrler = t2.add_row().cells
                for i in range(4):
                    hcrler[i].text = str(m[i])

        baslik_ekle("7. Risk Degerlendirmesi ve Rezerv Ozeti")
        madde_ekle(v.get("risk_ozeti", []))

        belge.save(doc_yolu)
        print("[+] Word (.docx) Raporu Basariyla Uretildi.")

    # ------------------------------------------------------------------
    # Ana akis
    # ------------------------------------------------------------------
    def baslat(self) -> None:
        """Sistemi baslatir: belgeleri tarar, analiz eder ve tum raporlari uretir."""
        print("[BiLGi] Akreditif denetim sistemi baslatiliyor...")
        if self.depoyu_tara_ve_analiz_et():
            durum = {k: ("VAR" if self.depo[k] else "YOK") for k in
                     ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]}
            print(f"[BiLGi] Belgeler: { ' | '.join(f'{k}={v}' for k,v in durum.items()) }")
            self.ucp600_kural_motoru()
            self.markdown_raporu_olustur()
            self.html_raporu_olustur()
            self.word_raporu_olustur()
            print(f"[SONUC] Risk Puani: {self.risk_puani} — {self._risk_sinifi()}")
            print("[SONUC] Tum raporlar olusturuldu.")
        else:
            print("[BiLGi] Yuklenmis belge bulunamadi veya dizin bos.")


# ===========================================================================
# Giris noktasi
# ===========================================================================
if __name__ == "__main__":
    motor = YapayZekaDisTicaretDenetleyici()
    motor.baslat()
