"""
bilgi_motoru.py — LC Denetim Motoru v11
Knowledge Base İndeksleme + Kaynak Yönlendirme + Karar İzi Modülü

MİMARİ KARAR NOTU:
  FAISS/ChromaDB/embedding gerektirmez — PDF'ler küçük (22-330 sayfa),
  regex+madde indexi anlık, deterministik ve denetlenebilir.
  Gelecekte embedding katmanı eklenirse bu modül arayüz sağlar.

PDF ROLLER:
  UCP 600 Text.pdf          → Birincil hukuk kaynağı (tüm kontroller)
  mt700 swift_...pdf        → MT700 alan yorumları
  ICC Banking Opinions...pdf → Destekleyici yorum (bağlayıcı değil)
  ISBP yorum örnek.pdf      → ISBP uygulama örnekleri
  incoterms2020.pdf         → Teslim şekli yorumları (CIF/FOB/CIP)
  eUCP_TR...pdf             → YALNIZCA elektronik ibraz durumunda
  eURC_TR...pdf             → YALNIZCA Collection (URC 522) durumunda
  urc 522...pdf             → YALNIZCA Collection durumunda
  ICC-URDTT-102T-ebook.pdf  → Dijital ticaret — ileride kullanım
"""
from __future__ import annotations
import logging, os, re
from typing import Optional

try:
    from pypdf import PdfReader
    PYPDF_OK = True
except ImportError:
    PYPDF_OK = False

log = logging.getLogger("bilgi_motoru")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] bilgi_motoru: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.DEBUG)


# ── Kaynak yönlendirme tablosu ───────────────────────────────────────────────
# Her kontrol türü için öncelikli PDF listesi (sıra önemli)
KAYNAK_YONLENDIRME: dict[str, list[str]] = {
    # MT700 alanları
    "mt700":       ["mt700", "ucp600", "isbp", "icc_opinions"],
    "alan_46a":    ["mt700", "ucp600", "isbp"],
    "alan_45a":    ["mt700", "ucp600", "isbp", "icc_opinions"],
    "alan_32b":    ["ucp600", "mt700"],
    "alan_44c":    ["ucp600", "mt700", "isbp"],

    # Belge türleri
    "fatura":      ["ucp600_art18", "isbp", "icc_opinions"],
    "konsimento":  ["ucp600_art20", "ucp600_art27", "isbp", "icc_opinions"],
    "sigorta":     ["ucp600_art28", "incoterms", "icc_opinions"],
    "packing":     ["ucp600_art14", "isbp", "mt700"],
    "co":          ["ucp600_art14", "isbp"],

    # Özel konular
    "incoterm_cif":   ["incoterms", "ucp600_art28", "icc_opinions"],
    "incoterm_fob":   ["incoterms", "ucp600"],
    "incoterm_cip":   ["incoterms", "ucp600_art28"],
    "yazip_farki":    ["isbp", "icc_opinions"],
    "kisaltma":       ["isbp", "icc_opinions"],
    "tutar":          ["ucp600_art30", "ucp600_art18"],
    "kilo":           ["ucp600_art14", "isbp"],
    "tarih":          ["ucp600_art20", "ucp600_art14c"],

    # Koşullu kaynaklar (yalnızca işlem tipi gerektiriyorsa)
    "e_ibraz":        ["eucp", "ucp600"],        # Yalnızca elektronik ibraz
    "collection":     ["eurc", "urc522"],         # Yalnızca Collection
}

# PDF dosya tanımlayıcı → gerçek dosya adı eşleştirmesi
PDF_TANIMLAYICI: dict[str, str] = {
    "ucp600":       "UCP 600 Text.pdf",
    "ucp600_art14": "UCP 600 Text.pdf",
    "ucp600_art18": "UCP 600 Text.pdf",
    "ucp600_art20": "UCP 600 Text.pdf",
    "ucp600_art27": "UCP 600 Text.pdf",
    "ucp600_art28": "UCP 600 Text.pdf",
    "ucp600_art30": "UCP 600 Text.pdf",
    "ucp600_art14c":"UCP 600 Text.pdf",
    "mt700":        "mt700 swift_solutions_advanceinformation.pdf",
    "icc_opinions": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf",
    "isbp":         "ISBP yorum #U00f6rnek.pdf",
    "incoterms":    "incoterms2020.pdf",
    "eucp":         "eUCP_TR_#U00c7eviri Eyl#U00fcl Son.pdf",
    "eurc":         "eURC_TR_#U00c7eviri Eyl#U00fcl Son.pdf",
    "urc522":       "urc 522 dis-ticarette-bankacilik-islemleri-5369.pdf",
    "urdtt":        "ICC-URDTT-102T-ebook.pdf",
}

# İşlem tipi → devreye giren ek kaynaklar
ISLEM_TIPI_KAYNAK: dict[str, list[str]] = {
    "DOCUMENTARY_CREDIT":  ["ucp600", "mt700", "isbp", "incoterms"],
    "STANDBY_LC":          ["ucp600", "isbp"],
    "COLLECTION":          ["urc522", "eurc"],
    "E_PRESENTATION":      ["eucp", "ucp600"],
}

# Kaynak güven seviyeleri (bağlayıcılık)
KAYNAK_GUVEN: dict[str, dict] = {
    "ucp600":       {"seviye": 5, "etiket": "Birincil (Bağlayıcı)", "yildiz": "★★★★★"},
    "mt700":        {"seviye": 5, "etiket": "İşleme Özgü (Bağlayıcı)", "yildiz": "★★★★★"},
    "isbp":         {"seviye": 4, "etiket": "Uygulama Standardı", "yildiz": "★★★★☆"},
    "incoterms":    {"seviye": 4, "etiket": "Teslim Şekli (Bağlayıcı)", "yildiz": "★★★★☆"},
    "icc_opinions": {"seviye": 3, "etiket": "Destekleyici Yorum (Bağlayıcı Değil)", "yildiz": "★★★☆☆"},
    "eucp":         {"seviye": 4, "etiket": "Elektronik İbraz Kuralı", "yildiz": "★★★★☆"},
    "eurc":         {"seviye": 4, "etiket": "Tahsil Kuralı", "yildiz": "★★★★☆"},
    "urc522":       {"seviye": 4, "etiket": "Collection Kuralı", "yildiz": "★★★★☆"},
}


# ── UCP Madde Metinleri (PDF'den parse) ─────────────────────────────────────
_UCP_MADDE_CACHE: dict[str, str] = {}
_INCOTERM_CACHE:  dict[str, str] = {}
_KB_YUKLU = False


def kb_hazirla(kb_dizin: str) -> bool:
    """
    Program başlangıcında bir kez çalışır.
    PDF'leri parse eder, madde bazlı indeks oluşturur.
    Yeniden okuma yapmaz — önbellek kullanır.
    """
    global _KB_YUKLU
    if _KB_YUKLU:
        return True
    if not PYPDF_OK:
        log.warning("[UYARI] pypdf yok — KB indeks oluşturulamadı.")
        return False

    log.debug("[DEBUG] KB indeks başlatılıyor: %s", kb_dizin)

    # UCP 600 madde indeksi
    ucp_pdf = os.path.join(kb_dizin, "UCP 600 Text.pdf")
    if os.path.isfile(ucp_pdf):
        _parse_ucp600(ucp_pdf)

    # Incoterms indeksi
    inc_pdf = os.path.join(kb_dizin, "incoterms2020.pdf")
    if os.path.isfile(inc_pdf):
        _parse_incoterms(inc_pdf)

    _KB_YUKLU = True
    log.debug("[DEBUG] KB indeks hazır: %d UCP madde, %d Incoterm",
              len(_UCP_MADDE_CACHE), len(_INCOTERM_CACHE))
    return True


def _pdf_oku(yol: str, max_sayfa: int = 999) -> str:
    """PDF'den metin çıkarır."""
    if not PYPDF_OK or not os.path.isfile(yol):
        return ""
    try:
        r = PdfReader(yol)
        satirlar = []
        for i, sayfa in enumerate(r.pages):
            if i >= max_sayfa:
                break
            t = sayfa.extract_text()
            if t:
                satirlar.append(t)
        return "\n".join(satirlar)
    except Exception as e:
        log.warning("[UYARI] PDF okunamadı: %s — %s", yol, e)
        return ""


def _parse_ucp600(yol: str) -> None:
    """UCP 600 madde metinlerini önbelleğe alır."""
    global _UCP_MADDE_CACHE
    metin = _pdf_oku(yol)
    if not metin:
        return
    # "UCP 600 - Article N" bölümleri
    bolumler = re.split(r'(?=UCP 600 - Article \d+)', metin)
    for bolum in bolumler:
        m = re.match(r'UCP 600 - Article (\d+)', bolum)
        if m:
            no = m.group(1).zfill(2)
            _UCP_MADDE_CACHE[f"art{no}"] = bolum.strip()[:3000]
    log.debug("[DEBUG] UCP 600: %d madde parse edildi", len(_UCP_MADDE_CACHE))


def _parse_incoterms(yol: str) -> None:
    """Incoterms 2020 teslim şekli bloklarını önbelleğe alır."""
    global _INCOTERM_CACHE
    metin = _pdf_oku(yol, max_sayfa=15)
    if not metin:
        return
    for kisa in ["EXW","FCA","CPT","CIP","DAP","DPU","DDP","FAS","FOB","CFR","CIF"]:
        m = re.search(rf'{kisa}[^\n]*\n(.*?)(?=\b(?:EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS|FOB|CFR|CIF)\b|\Z)',
                      metin, re.DOTALL)
        if m:
            _INCOTERM_CACHE[kisa] = m.group(0).strip()[:1500]
    log.debug("[DEBUG] Incoterms: %d teslim şekli parse edildi", len(_INCOTERM_CACHE))


# ── Kaynak sorgulama ─────────────────────────────────────────────────────────
def ucp_madde_al(madde: str) -> str:
    """
    UCP 600 madde metnini döner.
    Örnek: ucp_madde_al("18") → Art 18 Commercial Invoice tam metni
    """
    no = madde.lstrip("AartRTiIcClLeE 0").zfill(2) if madde else ""
    return _UCP_MADDE_CACHE.get(f"art{no}", "")


def incoterm_al(kisa: str) -> str:
    """Incoterms teslim şekli bloğunu döner."""
    return _INCOTERM_CACHE.get(kisa.upper(), "")


def kaynak_sec(kontrol_turu: str, islem_tipi: str = "DOCUMENTARY_CREDIT") -> list[str]:
    """
    Kontrol türü ve işlem tipine göre kaynak listesi döner.
    eUCP: yalnızca E_PRESENTATION — diğer kontrollerle de birleşir
    eURC/URC: yalnızca Collection
    """
    kaynaklar = list(KAYNAK_YONLENDIRME.get(kontrol_turu, ["ucp600"]))

    # E_PRESENTATION: eucp tüm kontrollere eklenir
    if islem_tipi == "E_PRESENTATION" and "eucp" not in kaynaklar:
        kaynaklar.append("eucp")

    # Collection: eurc/urc tüm kontrollere eklenir
    if islem_tipi == "COLLECTION":
        for k in ["eurc", "urc522"]:
            if k not in kaynaklar:
                kaynaklar.append(k)

    # Normal DC'de eUCP/eURC çıkar
    if islem_tipi not in ("E_PRESENTATION",):
        kaynaklar = [k for k in kaynaklar if k != "eucp"]
    if islem_tipi not in ("COLLECTION",):
        kaynaklar = [k for k in kaynaklar if k not in ("eurc", "urc522")]

    # ICC Opinions — daima son
    if "icc_opinions" in kaynaklar:
        kaynaklar.remove("icc_opinions")
        kaynaklar.append("icc_opinions")

    return kaynaklar


def kaynak_notu(tanimlayici: str) -> str:
    """'ucp600' → 'knowledge_base/UCP 600 Text.pdf' formatında döner."""
    dosya = PDF_TANIMLAYICI.get(tanimlayici, "")
    return f"knowledge_base/{dosya}" if dosya else tanimlayici


def kaynak_guven_goster(kaynaklar: list[str]) -> str:
    """
    Kullanılan kaynakları ve güven seviyelerini raporlayacak metin üretir.
    Örnek:
      ✓ UCP 600 Text.pdf (Birincil ★★★★★)
      ✓ MT700 Guide (İşleme Özgü ★★★★★)
      ~ ICC Banking Opinions (Destekleyici ★★★☆☆)
    """
    satirlar = []
    goruldu: set = set()
    for k in kaynaklar:
        dosya = PDF_TANIMLAYICI.get(k)
        if not dosya or dosya in goruldu:
            continue
        goruldu.add(dosya)
        g = KAYNAK_GUVEN.get(k, {})
        sembol = "~" if "Bağlayıcı Değil" in g.get("etiket", "") else "✓"
        satirlar.append(
            f"  {sembol} {dosya} — {g.get('etiket','?')} {g.get('yildiz','')}"
        )
    return "\n".join(satirlar) if satirlar else "  (kaynak bilgisi yok)"


# ── İşlem Tipi Algılama ──────────────────────────────────────────────────────
def islem_tipi_algiла(kusat_text: str, mt700_alanlari: dict) -> str:
    """
    Belge içeriğinden işlem tipini algılar.
    DOCUMENTARY_CREDIT / STANDBY_LC / COLLECTION / E_PRESENTATION

    eUCP: yalnızca elektronik ibraz bildirimi varsa
    eURC: yalnızca Collection/URC varsa
    """
    if not kusat_text:
        return "DOCUMENTARY_CREDIT"

    m_u = kusat_text.upper()

    # Elektronik ibraz
    if any(k in m_u for k in ["EUCP", "E-UCP", "ELECTRONIC PRESENTATION",
                                "XML", "DIGITAL DOCUMENT"]):
        return "E_PRESENTATION"

    # Collection
    if any(k in m_u for k in ["COLLECTION", "URC 522", "DOCUMENTARY COLLECTION",
                                "VESAIK MUKABİLİ", "D/P", "D/A"]):
        return "COLLECTION"

    # Standby
    if "STANDBY" in m_u or "ISBP" in m_u and "STANDBY" in m_u:
        return "STANDBY_LC"

    # MT700 40A
    form_40a = mt700_alanlari.get("40A", "").upper()
    if "STANDBY" in form_40a:
        return "STANDBY_LC"

    return "DOCUMENTARY_CREDIT"


# ── Karar İzi (Decision Trace) ───────────────────────────────────────────────
class KararIzi:
    """
    Her UCP kontrolünde çalışan muhakeme adımlarını kaydeder.
    Raporda 'Decision Trace' bölümü olarak gösterilir.
    """
    def __init__(self, kontrol_adi: str):
        self.kontrol_adi = kontrol_adi
        self.adimlar: list[str] = []
        self.kullanilan_kaynaklar: list[str] = []
        self.sonuc: str = ""

    def adim(self, metin: str) -> None:
        self.adimlar.append(metin)

    def kaynak_kullan(self, tanimlayici: str) -> None:
        if tanimlayici not in self.kullanilan_kaynaklar:
            self.kullanilan_kaynaklar.append(tanimlayici)

    def sonucla(self, durum: str) -> None:
        self.sonuc = durum
        self.adimlar.append(f"→ SONUÇ: {durum}")

    def metni(self) -> str:
        kaynaklar = kaynak_guven_goster(self.kullanilan_kaynaklar)
        adimlar   = "\n".join(f"  {i+1}. {a}" for i, a in enumerate(self.adimlar))
        return (
            f"**{self.kontrol_adi} — Karar İzi**\n\n"
            f"Kullanılan Kaynaklar:\n{kaynaklar}\n\n"
            f"Muhakeme Adımları:\n{adimlar}"
        )


# ── "Bulunamadı ≠ Yok" Motoru ────────────────────────────────────────────────
class BulamadıMotoru:
    """
    Bir veri tespit edilemediğinde üç aşamalı kontrol yapar.
    Aşama 1: Regex (birincil)
    Aşama 2: Çapraz belge doğrulama
    Aşama 3: KB bilgisiyle zorunluluk kararı

    Yalnızca üç aşama da başarısız olursa "TESPIT_EDILEMEDI" kararı verir.
    Hiçbir zaman "YOK" demez.
    """
    ASAMALAR = ["REGEX", "CAPRAZ_BELGE", "KB_MUHAKEME"]

    def __init__(self, alan_adi: str, kontrol_turu: str):
        self.alan_adi     = alan_adi
        self.kontrol_turu = kontrol_turu
        self.sonuc_asama: Optional[str] = None
        self.log_satirlari: list[str]   = []

    def asama1_regex(self, bulunan: bool, kaynak: str = "") -> bool:
        if bulunan:
            self.sonuc_asama = "REGEX"
            self.log_satirlari.append(f"[1] REGEX: bulundu ({kaynak})")
            return True
        self.log_satirlari.append("[1] REGEX: bulunamadı")
        return False

    def asama2_capraz(self, bulunan: bool, kaynak_belge: str = "") -> bool:
        if bulunan:
            self.sonuc_asama = "CAPRAZ_BELGE"
            self.log_satirlari.append(f"[2] ÇAPRAZ BELGE: {kaynak_belge} üzerinde doğrulandı")
            return True
        self.log_satirlari.append(f"[2] ÇAPRAZ BELGE: {kaynak_belge or 'kontrol edildi'} — bulunamadı")
        return False

    def asama3_kb(self, zorunlu_mu: bool, dayanak: str = "") -> bool:
        if not zorunlu_mu:
            self.sonuc_asama = "KB_MUHAKEME_ZORUNLU_DEGIL"
            self.log_satirlari.append(f"[3] KB MUHAKEME: {dayanak} — zorunlu değil, BİLGİ")
            return True  # Zorunlu değilse sorun yok
        self.log_satirlari.append(f"[3] KB MUHAKEME: {dayanak} — zorunlu, tespit edilemedi")
        return False

    @property
    def durum(self) -> str:
        """BULUNDU / TESPIT_EDILEMEDI (YOK DEMEZ)"""
        if self.sonuc_asama:
            return "BULUNDU"
        return "TESPIT_EDILEMEDI"

    @property
    def ozet(self) -> str:
        return " | ".join(self.log_satirlari)


# ── OCR Güven Skoru ─────────────────────────────────────────────────────────
def ocr_guven_hesapla(metin: str, dosya_yolu: str = "") -> dict:
    """
    Mevcut metin kalitesinden OCR güven tahmini yapar.
    Pytesseract image_to_data() yoksa heuristic kullanır.
    """
    if not metin:
        return {"skor": 0, "seviye": "OKUNAMADI", "oneri": "Belge okunamadı."}

    toplam_kar = len(metin.replace(" ","").replace("\n",""))
    if toplam_kar == 0:
        return {"skor": 0, "seviye": "OKUNAMADI", "oneri": "Belge okunamadı."}

    # Heuristic: anlamsız karakter oranı
    anlamsiz = len(re.findall(r'[^\w\s.,;:!\?\-\(\)%$€£/\\@#&*+="\'<>]', metin))
    bosluk   = metin.count(" ") + metin.count("\n")
    rakam_harf = len(re.findall(r'[A-Za-z0-9]', metin))

    if rakam_harf == 0:
        skor = 10
    else:
        anlamsiz_oran = anlamsiz / max(toplam_kar, 1)
        bosluk_oran   = bosluk / max(len(metin), 1)
        skor = max(0, min(100, int((1 - anlamsiz_oran * 3) * 100)))
        if bosluk_oran < 0.05:  # Çok az boşluk → OCR hatası olabilir
            skor = min(skor, 60)

    if skor >= 90:
        seviye = "YÜKSEK"
        oneri  = ""
    elif skor >= 80:
        seviye = "İYİ"
        oneri  = ""
    elif skor >= 60:
        seviye = "ORTA — Manuel doğrulama önerilir"
        oneri  = "OCR orta güvenle okundu; kritik alanlar manuel doğrulanmalıdır."
    else:
        seviye = "DÜŞÜK — Rezerv kararı verilmeden önce manuel doğrulama zorunludur"
        oneri  = (
            "OCR düşük güvenle okundu. "
            "Veri eksikliği OCR kaynaklı olabilir; bu nedenle rezerv oluşturulmamıştır. "
            "Manuel doğrulama yapılmalıdır."
        )

    return {"skor": skor, "seviye": seviye, "oneri": oneri}


# ── Düzeltme Önerileri Veritabanı ───────────────────────────────────────────
REZERV_ONERI: dict[str, str] = {
    "sigorta_eksik":
        "Sigorta şirketi yeni poliçe veya sertifika düzenlemelidir. "
        "Teminat tutarı CIF değerinin en az %110'u olmalıdır.",
    "tutar_uyusmazligi":
        "Fatura CIF tutarı LC 32B alanındaki tutarla uyumlu olacak şekilde "
        "yeniden düzenlenmeli veya LC değişikliği talep edilmelidir.",
    "kilo_uyusmazligi":
        "Fatura, Packing List ve Konşimento üzerindeki ağırlık bilgileri "
        "tutarlı hale getirilmeli; gerekiyorsa Packing List revize edilmelidir.",
    "konsimento_eksik":
        "Taşıyıcıdan tam set orijinal konşimento temin edilmelidir. "
        "Konşimento 'Shipped on Board' şerhi ve tarihi içermelidir.",
    "gec_yukleme":
        "LC değişikliği ile 44C son yükleme tarihi uzatılmalı "
        "veya yeni konşimento düzenlenmelidir (mümkünse).",
    "temiz_bl_sorunu":
        "Taşıyıcı ile görüşülerek klozlu konşimentin değiştirilmesi talep edilmeli; "
        "hasarlı mal durumunda sigorta dosyası açılmalıdır.",
    "46a_belge_eksigi":
        "46A'da istenen eksik belge temin edilip ibraz dosyasına eklenmelidir.",
    "co_eksik":
        "Ticaret Odası'ndan Certificate of Origin temin edilmelidir. "
        "Fatura beyanı ayrı CO belgesi yerine geçmez.",
    "mal_tanimi_kritik":
        "Fatura mal tanımı LC 45A alanıyla uyumlu olacak şekilde revize edilmelidir. "
        "Daha genel ifade kullanılabilir; çelişkili ifade kullanılamaz.",
    "on_board_eksik":
        "Konşimento üzerine 'Shipped on Board' şerhi ve tarihi eklenmesi için "
        "taşıyıcıdan onaylı şerh alınmalıdır.",
    "ibraz_suresi":
        "LC ibraz süresi içinde (max 21 gün) belgeler bankaya ulaştırılmalıdır. "
        "Geç ibraz durumunda LC değişikliği talep edilmelidir.",
}


def oneri_uret(rezerv_kodu: str, ek_bilgi: str = "") -> str:
    """Her rezerv için somut düzeltme önerisi döner."""
    temel = REZERV_ONERI.get(rezerv_kodu, "Uzman görüşü alınmalıdır.")
    return f"{temel} {ek_bilgi}".strip()
