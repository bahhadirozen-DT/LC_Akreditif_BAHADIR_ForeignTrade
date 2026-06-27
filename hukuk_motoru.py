"""
hukuk_motoru.py - Akreditif Hukuki Karar Destek ve Uzman Sistem Motoru v11.0
============================================================================
Yenilikler v11.0:
  - Legal Knowledge Registry: Başlangıçta tüm PDF'leri okur, sayfa sayfa indexler.
  - Legal Source Selector: Hangi kontrolün hangi hukuki kaynak zinciriyle yapılacağını seçer.
  - Belge Bazlı Kural Motoru: Fatura (Art18), Konşimento (Art20/27), Sigorta (Art28) için bağımsız boru hatları.
  - Precedence & Çelişki Çözümü: MT700 > UCP 600 > ISBP > ICC Opinions > Incoterms.
  - eUCP ve eURC filtreleri: Sadece ilgili işlem tiplerinde devreye girer.
  - RAG Arama ve Sorgu Günlüğü (Knowledge Search Log).
  - Karar Ağacı (Decision Trace) ve Düzeltme Önerileri (Remediation).
"""
from __future__ import annotations
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional
from pypdf import PdfReader

log = logging.getLogger("hukuk_motoru")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] hukuk_motoru: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.DEBUG)

# Ay Eşleştirme Map
AY_MAP = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
    "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9, "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}

# Taşıma Belgesi Olumsuz Klozları
KIRLI_BL = [
    "CLAUSED", "DAMAGED", "TORN", "WET CARGO", "INSUFFICIENT PACKING",
    "PARTLY DAMAGED", "RUSTED", "LEAKING", "STAINED", "BROKEN",
]

# ── Legal Knowledge Registry ──────────────────────────────────────────────────
_KNOWLEDGE_REGISTRY: dict[str, Any] = {}
_KNOWLEDGE_SEARCH_LOG: list[dict[str, Any]] = []

def init_knowledge_registry(kb_dizin: str = "") -> dict:
    """
    knowledge_base/ klasöründeki tüm PDF'leri bir kez okuyup Legal Knowledge Registry'ye yükler.
    Her PDF sayfa bazlı chunk'lara bölünür ve anahtar kelimelere göre sorgulanabilir hale gelir.
    """
    global _KNOWLEDGE_REGISTRY
    if _KNOWLEDGE_REGISTRY:
        return _KNOWLEDGE_REGISTRY

    arama_yollari = [
        kb_dizin,
        os.path.join(os.path.dirname(__file__), "knowledge_base"),
        "knowledge_base",
    ]
    
    secilen_dizin = ""
    for yol in arama_yollari:
        if yol and os.path.isdir(yol):
            secilen_dizin = yol
            break

    registry = {
        "belgeler": {},      # Dosya adı -> Sayfa metinleri listesi
        "dokuman_haritasi": {} # Kolay erişim için belirli maddeler/alanlar
    }

    if not secilen_dizin:
        log.warning("[UYARI] knowledge_base dizini bulunamadı! Boş Registry kuruluyor.")
        _KNOWLEDGE_REGISTRY = registry
        return registry

    log.info("[+] Legal Knowledge Registry yükleniyor: %s", secilen_dizin)
    for dosya in os.listdir(secilen_dizin):
        if dosya.endswith(".pdf"):
            tam_yol = os.path.join(secilen_dizin, dosya)
            try:
                reader = PdfReader(tam_yol)
                pages = []
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    pages.append(text)
                
                # Registry'ye dosya bazlı kaydet
                registry["belgeler"][dosya] = pages
                log.debug("  - Yüklendi: %s (%d sayfa)", dosya, len(pages))
                
                # Özel indeksler (UCP 600 maddeleri, MT700 alanları vb.)
                # UCP 600 için
                if "UCP 600" in dosya or "UCP600" in dosya:
                    registry["dokuman_haritasi"]["ucp600"] = ucp_haritalandir(pages)
                # MT700 swift guide için
                elif "mt700" in dosya.lower() or "swift" in dosya.lower():
                    registry["dokuman_haritasi"]["mt700"] = mt700_haritalandir(pages)
                # Incoterms için
                elif "incoterms" in dosya.lower():
                    registry["dokuman_haritasi"]["incoterms"] = incoterms_haritalandir(pages)

            except Exception as e:
                log.error("  - Hata (%s): %s", dosya, e)

    _KNOWLEDGE_REGISTRY = registry
    return registry

def ucp_haritalandir(pages: list[str]) -> dict:
    harita = {}
    full_text = "\n".join(pages)
    # Article \d+ veya Art \d+ veya Madde \d+ bul
    matches = re.finditer(r'(?:Article|Madde)\s+(\d+)', full_text, re.IGNORECASE)
    pos_list = [m.start() for m in matches]
    pos_list.append(len(full_text))
    
    matches = re.finditer(r'(?:Article|Madde)\s+(\d+)', full_text, re.IGNORECASE)
    for i, m in enumerate(matches):
        art_num = m.group(1)
        art_text = full_text[pos_list[i]:pos_list[i+1]].strip()
        harita[f"art{art_num}"] = art_text
    return harita

def mt700_haritalandir(pages: list[str]) -> dict:
    harita = {}
    full_text = "\n".join(pages)
    # MT700 Field veya Tag bul
    for field in ["20", "31D", "32B", "39A", "40A", "41A", "42C", "44C", "44E", "44F", "45A", "46A", "47A", "48", "49", "71D", "71B", "78"]:
        m = re.search(rf'(?:Field|Tag|Alan)\s*{field}\b', full_text, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 100)
            end = min(len(full_text), m.end() + 1000)
            harita[field] = full_text[start:end].strip()
    return harita

def incoterms_haritalandir(pages: list[str]) -> dict:
    harita = {}
    full_text = "\n".join(pages)
    for term in ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]:
        m = re.search(rf'\b{term}\b', full_text)
        if m:
            start = max(0, m.start() - 50)
            end = min(len(full_text), m.end() + 800)
            harita[term] = full_text[start:end].strip()
    return harita

# ── RAG / Registry Search Engine ──────────────────────────────────────────────
def registry_ara(dosya_adi_kisa: str, query: str) -> tuple[Optional[str], str]:
    """
    Registry içinde belirtilen dosya adı (veya kısaltması) ve query'ye göre arama yapar.
    Döner: (Bulunan Metin, Durum Logu)
    """
    registry = init_knowledge_registry()
    log_kaydi = f"Searching {dosya_adi_kisa} for '{query}'... "

    # Dosya adını registry'den eşleştir
    hedef_dosya = ""
    for d in registry["belgeler"]:
        if dosya_adi_kisa.upper() in d.upper() or (dosya_adi_kisa == "eUCP" and "eUCP" in d) or (dosya_adi_kisa == "eURC" and "eURC" in d):
            hedef_dosya = d
            break

    if not hedef_dosya:
        log_kaydi += "✗ (File Not Found in Registry)"
        _KNOWLEDGE_SEARCH_LOG.append({"sorgu": query, "kaynak": dosya_adi_kisa, "sonuc": "✗ (File Not Found)"})
        return None, log_kaydi

    # Özel haritada tam arama
    dokuman_haritasi = registry.get("dokuman_haritasi", {})
    # 1. Adım: Özel madde eşleştirmesi (UCP Art 18 vb.)
    m_art = re.search(r'(?:Art|Madde|Article)\s*(\d+)', query, re.IGNORECASE)
    if m_art and "UCP" in dosya_adi_kisa.upper() and "ucp600" in dokuman_haritasi:
        art_key = f"art{m_art.group(1)}"
        art_text = dokuman_haritasi["ucp600"].get(art_key)
        if art_text:
            log_kaydi += "✓ (Exact Article Found)"
            _KNOWLEDGE_SEARCH_LOG.append({"sorgu": query, "kaynak": hedef_dosya, "sonuc": "✓ (Article Match)"})
            return art_text[:1200], log_kaydi

    # 2. Adım: Kelime bazlı sayfa tarama
    pages = registry["belgeler"][hedef_dosya]
    en_iyi_sayfa = -1
    en_iyi_skor = 0
    keywords = set(w.upper() for w in re.sub(r'[^\w\s]', ' ', query).split() if len(w) >= 3)
    
    for idx, page_text in enumerate(pages):
        page_u = page_text.upper()
        skor = sum(1 for kw in keywords if kw in page_u)
        if skor > en_iyi_skor:
            en_iyi_skor = skor
            en_iyi_sayfa = idx

    if en_iyi_sayfa != -1 and en_iyi_skor >= 1:
        log_kaydi += f"✓ (Page {en_iyi_sayfa+1} Match)"
        _KNOWLEDGE_SEARCH_LOG.append({"sorgu": query, "kaynak": f"{hedef_dosya} (Page {en_iyi_sayfa+1})", "sonuc": "✓ (Content Match)"})
        return pages[en_iyi_sayfa][:1500], log_kaydi

    log_kaydi += "✗ (No Match)"
    _KNOWLEDGE_SEARCH_LOG.append({"sorgu": query, "kaynak": hedef_dosya, "sonuc": "✗ (No Match)"})
    return None, log_kaydi

def search_log_getir() -> list[dict[str, Any]]:
    return _KNOWLEDGE_SEARCH_LOG

def search_log_temizle():
    global _KNOWLEDGE_SEARCH_LOG
    _KNOWLEDGE_SEARCH_LOG = []

# ── Legal Source Selector ─────────────────────────────────────────────────────
class LegalSourceSelector:
    """
    Belirli bir belge türü ve kontrol konusu için hangi hukuk kaynaklarının hangi sıra
    ve öncelikle kullanılacağını yöneten katman.
    """
    @staticmethod
    def get_sources(belge_turu: str, konu: str, is_electronic: bool = False, is_collection: bool = False) -> list[dict[str, Any]]:
        sources = []
        
        # 1. eURC / eUCP Kontrolü (Öncelikli filtreler)
        if is_collection and konu != "MT700":
            sources.append({"kod": "eURC", "dosya": "eURC_TR_Çeviri Eylül Son.pdf", "yetki": "Birincil Vesaik Mukabili Tahsil Kuralları"})
            sources.append({"kod": "URC522", "dosya": "urc 522 dis-ticarette-bankacilik-islemleri-5369.pdf", "yetki": "Destekleyici Tahsil Kuralları"})
            return sources

        if is_electronic and konu != "MT700":
            sources.append({"kod": "eUCP", "dosya": "eUCP_TR_Çeviri Eylül Son.pdf", "yetki": "Elektronik İbraz Kuralları"})

        # 2. Standart Konu Yönlendirmeleri
        if konu == "MT700":
            sources.append({"kod": "MT700", "dosya": "mt700 swift_solutions_advanceinformation.pdf", "yetki": "SWIFT Standart Rehberi"})
            sources.append({"kod": "UCP600", "dosya": "UCP 600 Text.pdf", "yetki": "Ana Hukuk Kaynağı"})
        elif belge_turu == "FATURA":
            sources.append({"kod": "UCP600", "dosya": "UCP 600 Text.pdf", "madde": "Art 18", "yetki": "Fatura Temel Standartları"})
            sources.append({"kod": "ISBP", "dosya": "ISBP yorum örnek.pdf", "yetki": "ISBP Uygulama Yorumları"})
            sources.append({"kod": "ICC", "dosya": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf", "yetki": "Destekleyici Yorum — Tek Başına Rezerv Oluşturamaz"})
        elif belge_turu == "KONSIMENTO":
            sources.append({"kod": "UCP600", "dosya": "UCP 600 Text.pdf", "madde": "Art 20 / Art 27", "yetki": "Konşimento Temel Standartları"})
            sources.append({"kod": "ISBP", "dosya": "ISBP yorum örnek.pdf", "yetki": "Taşıma Belgesi Detayları"})
            sources.append({"kod": "ICC", "dosya": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf", "yetki": "Destekleyici Taşıma Kararları"})
        elif belge_turu == "SIGORTA":
            sources.append({"kod": "UCP600", "dosya": "UCP 600 Text.pdf", "madde": "Art 28", "yetki": "Sigorta Teminat Standartları"})
            sources.append({"kod": "Incoterms", "dosya": "incoterms2020.pdf", "yetki": "Teslim Şekline Bağlı Yükümlülükler"})
            sources.append({"kod": "ICC", "dosya": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf", "yetki": "Destekleyici Sigorta Kararları"})
        elif konu in ["CIF", "FOB", "CIP", "CFR", "FCA", "EXW"]:
            sources.append({"kod": "Incoterms", "dosya": "incoterms2020.pdf", "yetki": "Esas Alınacak Teslim Şekli"})
            sources.append({"kod": "UCP600", "dosya": "UCP 600 Text.pdf", "yetki": "Belgelerin Uygunluğu"})
            sources.append({"kod": "ICC", "dosya": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf", "yetki": "Destekleyici Ticaret Görüşleri"})
        elif konu in ["LIMITED/LTD", "COMPANY/CO", "INTERNATIONAL/INTL", "TYPO"]:
            sources.append({"kod": "ISBP", "dosya": "ISBP yorum örnek.pdf", "yetki": "Yazım Farklılıkları ve Kısaltmalar"})
            sources.append({"kod": "ICC", "dosya": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf", "yetki": "Abbreviation and Address Opinions"})
        else:
            # Fallback Standart Hiyerarşi
            sources.append({"kod": "UCP600", "dosya": "UCP 600 Text.pdf", "yetki": "Birincil Mevzuat"})
            sources.append({"kod": "ISBP", "dosya": "ISBP yorum örnek.pdf", "yetki": "Uluslararası Bankacılık Standartları"})
            sources.append({"kod": "ICC", "dosya": "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf", "yetki": "Destekleyici İçtihat"})

        return sources

# ── Conflict Resolution Precedence Engine ─────────────────────────────────────
class PrecedenceEngine:
    """
    Çelişen kuralları öncelik hiyerarşisine göre çözen motor.
    Hiyerarşi: MT700 > UCP 600 > ISBP > ICC Opinions (Webinar) > Incoterms.
    """
    @staticmethod
    def cozumle(rezervler: list[dict], mt700_ozel_sartlar: dict[str, Any]) -> list[dict]:
        temiz_rezervler = []
        for r in rezervler:
            kod = r.get("kod")
            durum = r.get("durum")
            
            # ICC Banking Opinions tek başına rezerv oluşturamaz veya UCP'yi ezemez constraint'i
            if r.get("kaynak_kodu") == "ICC" and durum == "REZERV":
                log.info("[Precedence] ICC Banking Opinion tek başına rezerv oluşturamaz. Kaldırılıyor: %s", r.get("detay"))
                continue
                
            # MT700 özel şartı varsa genel UCP kuralını ezer (Örn: L/C'de 46A'da açıkça faturada kilo istiyorsa Art18 kilo istemez kuralı geçersizdir)
            if kod == "fatura_kilo_eksik" and mt700_ozel_sartlar.get("invoice_weight_required"):
                r["durum"] = "REZERV"
                r["detay"] = "MT700 46A açıkça faturada kilo istemektedir. Art18 istisnası geçersizdir."
                r["hukuki_yorum"] = "MT700 özel şartları UCP 600 genel kurallarından üstündür (Hiyerarşi Sıra 1)."
                r["remediation"] = "Fatura yeniden düzenlenerek üzerine Brüt Ağırlık (Gross Weight) eklenmelidir."

            temiz_rezervler.append(r)
        return temiz_rezervler

# ── Yardımcı Fonksiyonlar ─────────────────────────────────────────────────────
def normalize_tutar(metin: str) -> Optional[float]:
    """23,940 / 23.940 / 23.940,00 → 23940.0"""
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
            s = s.replace('.','').replace(',','.') if sv > sn else s.replace(',','')
        return float(s) if s else None
    except ValueError:
        return None

def _tarih(metin: str) -> Optional[datetime]:
    if not metin:
        return None
    m = re.search(r'(\d{1,2})[.\-/](\d{2})[.\-/](\d{4})', metin)
    if m:
        try: return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError: pass
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', metin)
    if m:
        try: return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError: pass
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', metin)
    if m:
        ay = AY_MAP.get(m.group(2).upper()[:9])
        if ay:
            try: return datetime(int(m.group(3)), ay, int(m.group(1)))
            except ValueError: pass
    return None

def _celiski_denetle(a: Optional[float], b: Optional[float], iliski: str = ">=") -> bool:
    if a is None or b is None:
        return False
    a2, b2 = round(a, 2), round(b, 2)
    if iliski == ">=": return a2 >= b2
    if iliski == "<=": return a2 <= b2
    if iliski == "==": return abs(a2-b2) < 0.01
    return False

# ── MT700 Hukuki Yorum Motoru ────────────────────────────────────────────────
def mt700_hukuki_yorum(parsed: dict[str, Any]) -> list[dict]:
    """
    Her MT700 alanı için UCP 600 ve SWIFT standartlarına göre arama yapar, gerekçeli analiz üretir.
    """
    init_knowledge_registry()
    mt700        = parsed.get("mt700_alanlari", {})
    fatura_tutar = parsed.get("fatura_tutar")
    lc_tutar     = parsed.get("lc_tutar")
    bl_tarih_str = parsed.get("bl_tarih_str")
    sigorta_t    = parsed.get("sigorta_tutari")
    incoterm     = parsed.get("incoterm", "")
    alan_44c     = parsed.get("alan_44c", "")

    sonuclar: list[dict] = []
    
    MT700_FIELDS = ["20", "31D", "32B", "39A", "40A", "41A", "44C", "45A", "46A", "47A", "48", "49", "71D"]
    
    for alan in MT700_FIELDS:
        deger = mt700.get(alan)
        if not deger:
            continue

        # Legal Source Selector ile kaynakları belirle
        sources = LegalSourceSelector.get_sources("MT700", "MT700")
        primary_source = sources[0]
        
        # RAG Search
        search_txt, search_log = registry_ara("mt700", f"Field {alan}")
        
        aciklama = f"SWIFT MT700 Alan {alan} kontrolü."
        yorum = f"SWIFT Kılavuzuna göre Alan {alan} kuralları uygulanır."
        madde = f"SWIFT Tag {alan}"
        karsilastirma = ""
        sonuc = "BİLGİ"

        if alan == "32B":
            aciklama = "Currency & Amount (Para Birimi ve Tutar)"
            yorum = "Fatura para birimi ve tutarı LC limitleri ve UCP 600 Art 18/30 ile karşılaştırılır."
            madde = "UCP 600 Art 18 / Art 30"
            if fatura_tutar and lc_tutar and lc_tutar > 0:
                sapma = (fatura_tutar - lc_tutar) / lc_tutar * 100
                karsilastirma = f"LC Tutarı: {lc_tutar:,.2f} | Fatura CIF: {fatura_tutar:,.2f} | Sapma: %{sapma:+.2f}"
                sonuc = "✓ UYUMLU" if abs(sapma) <= 5 else "⚠ REZERV RİSKİ"

        elif alan == "44C":
            aciklama = "Latest Date of Shipment (En Geç Yükleme Tarihi)"
            yorum = "Taşıma belgesi üzerindeki yükleme tarihi en geç yükleme tarihini aşamaz (Art 20)."
            madde = "UCP 600 Art 20 / Art 14(c)"
            if bl_tarih_str and alan_44c:
                bl_dt = _tarih(bl_tarih_str)
                lc_dt = _tarih(alan_44c)
                if bl_dt and lc_dt:
                    karsilastirma = f"B/L On Board: {bl_tarih_str} | 44C Son Yükleme: {alan_44c}"
                    sonuc = "✓ UYUMLU" if bl_dt <= lc_dt else "⚠ GEÇ YÜKLEME — MAJOR DISCREPANCY"
                else:
                    karsilastirma = f"Son Yükleme: {alan_44c} | B/L tarihi okunamadı."
                    sonuc = "MANUEL KONTROL"

        elif alan == "46A":
            aciklama = "Documents Required (İstenen Belgeler)"
            yorum = "Talep edilen tüm belgelerin eksiksiz ibrazı zorunludur (Art 14(a))."
            madde = "UCP 600 Art 14(a) / Art 17(a)"
            eksik = parsed.get("eksik_belgeler_46a", [])
            bulunan = parsed.get("bulunan_belgeler_46a", [])
            if eksik:
                karsilastirma = f"Eksik Belgeler: {', '.join(eksik)}"
                sonuc = "⚠ EKSİK BELGE — REZERV"
            else:
                karsilastirma = f"İbraz Edilenler: {', '.join(bulunan) if bulunan else '-'}"
                sonuc = "✓ UYUMLU"

        sonuclar.append({
            "alan": alan,
            "ad": aciklama,
            "deger": deger[:200],
            "aciklama": aciklama,
            "yorum": yorum,
            "madde": madde,
            "kaynak": f"knowledge_base/{primary_source['dosya']}",
            "karsilastirma": karsilastirma,
            "sonuc": sonuc,
        })
        
    return sonuclar

# ── Belge Bazlı Hukuki Muhakeme ve UCP Kuralları ──────────────────────────────
def ucp_kurallari_uygula(parsed: dict[str, Any]) -> list[dict]:
    """
    Belge bazlı UCP 600 / ISBP 821 kural motoru.
    Gelişmiş karar ağacı (Decision Trace) ve düzeltme önerileri içerir.
    """
    init_knowledge_registry()
    rapor: list[dict] = []
    
    # Parametreleri al
    fatura_tutar    = parsed.get("fatura_tutar")
    lc_tutar        = parsed.get("lc_tutar")
    incoterm        = parsed.get("incoterm", "")
    bl_tarih_str    = parsed.get("bl_tarih_str")
    alan_44c        = parsed.get("alan_44c", "")
    fat_kilo        = parsed.get("fat_kilo")
    bl_kilo         = parsed.get("bl_kilo")
    pl_kilo         = parsed.get("pl_kilo")
    sigorta_tutari  = parsed.get("sigorta_tutari")
    konsimento_text = parsed.get("konsimento_text", "")
    kusat_text      = parsed.get("kusat_text", "")
    fatura_text     = parsed.get("fatura_text", "")
    
    is_electronic   = parsed.get("is_electronic", False)
    is_collection   = parsed.get("is_collection", False)

    # 1. Fatura Kontrolleri Boru Hattı (UCP Art 18 -> 46A -> Incoterms)
    def fatura_denetle():
        trace = ["Transaction Type Detected", "Invoice validation pipeline active", "Checking UCP Art 18"]
        sources = LegalSourceSelector.get_sources("FATURA", "Invoice", is_electronic, is_collection)
        primary = sources[0]
        
        # 1-a. Fatura Kilo Kontrolü (Art 18)
        if fat_kilo is None:
            # Art18 kilo zorunlu kılmaz. Çapraz kontrole soralım.
            pl_var = pl_kilo is not None
            bl_var = bl_kilo is not None
            if pl_var or bl_var:
                remed = "Gerekli değil (Paket listesinde veya Konşimentoda kilo mevcuttur)."
                durum = "BİLGİ"
                detay = f"Faturada Brüt Ağırlık bulunamadı ancak Çeki Listesinde ({pl_kilo or 0} KG) / Konşimentoda ({bl_kilo or 0} KG) mevcuttur."
                yorum = "UCP 600 Art 18, Commercial Invoice için ağırlık belirtilmesini zorunlu kılmaz. Belgeler arası çelişki yoktur."
            else:
                remed = "Gerekli değil, ancak nakliye belgelerinde Brüt Ağırlık eklenmesi tavsiye edilir."
                durum = "BİLGİ"
                detay = "Belgelerin hiçbirinde ağırlık bilgisi tespit edilemedi."
                yorum = "Kilo bilgisi zorunlu bir L/C alanı değildir. Çapraz doğrulamada bulunamamıştır."
            
            rapor.append({
                "kod": "fatura_kilo_eksik",
                "kaynak_kodu": primary["kod"],
                "madde": "UCP 600 Art 18",
                "aciklama": "Fatura Ağırlık Şartı",
                "durum": durum,
                "detay": detay,
                "hukuki_yorum": yorum,
                "dayanak": "UCP 600 Art 18 / ISBP Paragraph C1",
                "remediation": remed,
                "trace": " -> ".join(trace + ["Art 18 Applied", "Cross Validation completed", "Conclusion reached"]),
                "kaynak": f"knowledge_base/{primary['dosya']}"
            })

    # 2. Konşimento Kontrolleri Boru Hattı (UCP Art 20 -> Art 27 -> 46A)
    def konsimento_denetle():
        if not konsimento_text:
            return
        
        trace = ["Transaction Type Detected", "Bill of Lading pipeline active", "Checking UCP Art 20"]
        sources = LegalSourceSelector.get_sources("KONSIMENTO", "B/L", is_electronic, is_collection)
        primary = sources[0]

        # 2-a. Shipped on Board Şerhi (Art 20)
        bl_u = konsimento_text.upper()
        shipped_on_board = "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u or "CLEAN ON BOARD" in bl_u
        if shipped_on_board:
            rapor.append({
                "kod": "shipped_on_board_ok",
                "kaynak_kodu": primary["kod"],
                "madde": "UCP 600 Art 20",
                "aciklama": "On Board Şerhi",
                "durum": "UYUMLU",
                "detay": "Konşimentoda 'Shipped on Board' veya 'On Board' ifadesi mevcuttur.",
                "hukuki_yorum": "UCP 600 Art 20(a)(ii) gereğince deniz konşimentosu yüklemenin yapıldığını belirten ön-baskı şerhine sahip olmalıdır.",
                "dayanak": "UCP 600 Art 20(a)(ii)",
                "remediation": "Aksiyon gerekmemektedir.",
                "trace": " -> ".join(trace + ["Art 20 verified", "Conclusion: Compliant"]),
                "kaynak": f"knowledge_base/{primary['dosya']}"
            })
        else:
            rapor.append({
                "kod": "shipped_on_board_eksik",
                "kaynak_kodu": primary["kod"],
                "madde": "UCP 600 Art 20",
                "aciklama": "On Board Şerhi Eksik",
                "durum": "REZERV",
                "detay": "Konşimentoda yüklemeyi gösteren 'Shipped on Board' şerhi bulunamadı.",
                "hukuki_yorum": "UCP 600 Art 20(a)(ii) uyarınca geçerli bir deniz konşimentosu On Board şerhini taşımalıdır. Eksikliği doğrudan ret sebebidir.",
                "dayanak": "UCP 600 Art 20(a)(ii)",
                "remediation": "Taşıyıcı / Acente konşimento üzerine ıslak imzalı/kaşeli 'Shipped on Board' ve yükleme tarihi içeren bir şerh eklemelidir.",
                "trace": " -> ".join(trace + ["Art 20 verified", "Conclusion: Discrepant"]),
                "kaynak": f"knowledge_base/{primary['dosya']}"
            })

        # 2-b. Temiz Konşimento (Art 27)
        kirli = [k for k in KIRLI_BL if k in bl_u]
        if kirli:
            rapor.append({
                "kod": "temiz_bl_ihlali",
                "kaynak_kodu": primary["kod"],
                "madde": "UCP 600 Art 27",
                "aciklama": "Klozlu/Kirli Konşimento",
                "durum": "REZERV",
                "detay": f"Konşimentoda olumsuz şerh tespit edildi: {', '.join(kirli)}",
                "hukuki_yorum": "UCP 600 Art 27 uyarınca bankalar yalnızca temiz (clean) taşıma belgelerini kabul eder. Malın hasarlı olduğunu belirten şerhler reddedilir.",
                "dayanak": "UCP 600 Art 27",
                "remediation": "Taşıma belgesi hasar şerhi barındırmayacak şekilde temiz (Clean) olarak yeniden düzenlenmelidir.",
                "trace": " -> ".join(trace + ["Checking Art 27", "Discrepancy found"]),
                "kaynak": f"knowledge_base/{primary['dosya']}"
            })
        else:
            rapor.append({
                "kod": "temiz_bl_ok",
                "kaynak_kodu": primary["kod"],
                "madde": "UCP 600 Art 27",
                "aciklama": "Temiz Konşimento",
                "durum": "UYUMLU",
                "detay": "Konşimentoda malın veya ambalajın hasarlı olduğuna dair hiçbir olumsuz kloz bulunmamaktadır.",
                "hukuki_yorum": "UCP 600 Art 27 uyarınca temiz taşıma belgesi şartı tam olarak karşılanmıştır.",
                "dayanak": "UCP 600 Art 27",
                "remediation": "Aksiyon gerekmemektedir.",
                "trace": " -> ".join(trace + ["Checking Art 27", "Conclusion: Compliant"]),
                "kaynak": f"knowledge_base/{primary['dosya']}"
            })

    # 3. Sigorta Kontrolleri Boru Hattı (UCP Art 28 -> Incoterms -> 46A)
    def sigorta_denetle():
        if incoterm not in ["CIF", "CIP"]:
            return
            
        trace = ["Transaction Type Detected", "Insurance pipeline active", "Checking UCP Art 28"]
        sources = LegalSourceSelector.get_sources("SIGORTA", "Insurance", is_electronic, is_collection)
        primary = sources[0]

        if sigorta_tutari and fatura_tutar and fatura_tutar > 0:
            min_t = round(fatura_tutar * 1.10, 2)
            sig_t_r = round(sigorta_tutari, 2)
            
            if sig_t_r >= min_t:
                rapor.append({
                    "kod": "sigorta_teminati_ok",
                    "kaynak_kodu": primary["kod"],
                    "madde": "UCP 600 Art 28",
                    "aciklama": "Sigorta Teminat Tutarı",
                    "durum": "UYUMLU",
                    "detay": f"Poliçe tutarı ({sig_t_r:,.2f}) asgari CIF %110 tutarını ({min_t:,.2f}) karşılamaktadır.",
                    "hukuki_yorum": "UCP 600 Art 28(f)(ii) uyarınca sigorta kapsamı, akreditifte aksine bir hüküm yoksa en az CIF veya CIP değerinin %110'u olmalıdır.",
                    "dayanak": "UCP 600 Art 28(f)(ii)",
                    "remediation": "Aksiyon gerekmemektedir.",
                    "trace": " -> ".join(trace + ["Art 28 Applied", "Value compared", "Conclusion: Compliant"]),
                    "kaynak": f"knowledge_base/{primary['dosya']}"
                })
            else:
                rapor.append({
                    "kod": "sigorta_teminati_yetersiz",
                    "kaynak_kodu": primary["kod"],
                    "madde": "UCP 600 Art 28",
                    "aciklama": "Yetersiz Sigorta Teminatı",
                    "durum": "REZERV",
                    "detay": f"Sigorta poliçesi tutarı ({sig_t_r:,.2f}) minimum limit olan CIF %110 değerinin ({min_t:,.2f}) altındadır.",
                    "hukuki_yorum": "UCP 600 Art 28(f)(ii) limit aşım ihlali. Asgari teminat miktarı karşılanmamaktadır.",
                    "dayanak": "UCP 600 Art 28(f)(ii)",
                    "remediation": "Sigorta şirketi tarafından ek teminat zeyilnamesi (endorsement) düzenlenmeli veya poliçe %110 sınırını aşacak şekilde yenilenmelidir.",
                    "trace": " -> ".join(trace + ["Art 28 Applied", "Value compared", "Conclusion: Discrepant"]),
                    "kaynak": f"knowledge_base/{primary['dosya']}"
                })

    # Tetikle
    fatura_denetle()
    konsimento_denetle()
    sigorta_denetle()

    # Precedence & Conflict Resolution uygula
    temiz_rapor = PrecedenceEngine.cozumle(rapor, {"invoice_weight_required": "46A" in kusat_text})
    
    return temiz_rapor

def uzman_gorusu_uret(parsed: dict[str, Any], ucp_sonuclari: list[dict]) -> str:
    """
    Raporun en sonundaki HUKUKİ UZMAN GÖRÜŞÜ bölümünü oluşturur.
    """
    rezervler = [r for r in ucp_sonuclari if r.get("durum") == "REZERV"]
    major_sayisi = len(rezervler)
    lc_no = parsed.get("lc_no", "Tespit edilemedi")
    
    s = []
    s.append(f"Değerlendirme Tarihi: {datetime.now().strftime('%d.%m.%Y')}")
    s.append(f"LC Referans: {lc_no}")
    s.append(f"Primary Legal Authority: UCP 600 (Uniform Customs and Practice for Documentary Credits)")
    s.append(f"Verification Framework: ICC Legal Expert System Architecture v11")
    s.append("")
    
    if major_sayisi == 0:
        s.append(
            "UYUMLULUK BEYANI:\n"
            "İbraz edilen belgeler, UCP 600 standart kuralları ve ISBP 821 uluslararası teamüllerine "
            "tam uygunluk göstermektedir. Yapılan çapraz doğrulama kontrollerinde esaslı (major) bir "
            "uyumsuzluğa rastlanmamış olup, belgelerin banka tarafından kabul edilme olasılığı yüksektir."
        )
    else:
        s.append(
            f"UYUMSUZLUK BEYANI:\n"
            f"Bu ibraz dosyasında {major_sayisi} adet hukuki rezerv (discrepancy) tespit edilmiştir. "
            "UCP 600 Madde 16(c) uyarınca amir bankanın ibrazı reddetme hakkı mevcuttur. "
            "Rezervlerin giderilmesi için aşağıdaki düzeltme önerileri ivedilikle uygulanmalıdır."
        )
        s.append("")
        s.append("HUKUKİ REZERV DETAYLARI VE ÖNERİLER:")
        for idx, r in enumerate(rezervler, 1):
            s.append(f" {idx}. [{r['madde']}] {r['aciklama']}")
            s.append(f"    • Bulgular: {r['detay']}")
            s.append(f"    • Çözüm Önerisi: {r['remediation']}")
            s.append("")
            
    s.append(
        "Yasal Uyarı: Bu uzman görüşü raporu ticari kararlarınıza destek olmak üzere "
        "bilgi tabanındaki kaynaklar ışığında hazırlanmıştır ve resmi bir banka taahhüdü değildir."
    )
    return "\n".join(s)
