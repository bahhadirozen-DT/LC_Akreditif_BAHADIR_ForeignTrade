"""
hukuk_motoru.py - UCP 600 / ISBP 821 Hukuki Yorum Motoru v11.0
================================================================
v11 yenilikleri:
  - bilgi_motoru.py entegrasyonu: KB indeks, kaynak yönlendirme, KararIzi
  - İşlem tipi algılama: DOCUMENTARY_CREDIT / COLLECTION / E_PRESENTATION
  - eUCP/eURC yalnızca gereken işlem tipinde devreye girer
  - OCR güven skoru: skor < 80 → rezerv değil, manuel doğrulama
  - "Bulunamadı ≠ Yok": 3 aşamalı arama
  - Her rezerve düzeltme önerisi (oneri alanı)
  - KararIzi: her kontrolün karar adımları raporda görünür
  - Kaynak çatışması çözümü: MT700 > UCP > ISBP > ICC > Incoterms
  - Çapraz belge önceliği: başka belgede varsa rezerv üretme
"""
from __future__ import annotations
import json, logging, os, re
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger("hukuk_motoru")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] hukuk_motoru: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.DEBUG)

# bilgi_motoru entegrasyonu
try:
    from bilgi_motoru import (
        kb_hazirla, kaynak_sec, kaynak_notu, kaynak_guven_goster,
        ucp_madde_al, incoterm_al,
        islem_tipi_algiла as _islem_tipi,
        KararIzi, BulamadıMotoru, ocr_guven_hesapla, oneri_uret,
    )
    BILGI_MOTORU_OK = True
    log.debug("[DEBUG] bilgi_motoru yüklendi.")
except ImportError as _e:
    BILGI_MOTORU_OK = False
    log.warning("[UYARI] bilgi_motoru yüklenemedi: %s", _e)
    # Stub'lar
    def kb_hazirla(d): return False
    def kaynak_sec(t, i="DOCUMENTARY_CREDIT"): return ["ucp600"]
    def kaynak_notu(t): return t
    def kaynak_guven_goster(l): return ""
    def ucp_madde_al(m): return ""
    def incoterm_al(k): return ""
    def _islem_tipi(k, m): return "DOCUMENTARY_CREDIT"
    def oneri_uret(k, e=""): return ""
    def ocr_guven_hesapla(m, d=""): return {"skor":90,"seviye":"İYİ","oneri":""}
    class KararIzi:
        def __init__(self, n): self.kontrol_adi=n; self.adimlar=[]; self.kullanilan_kaynaklar=[]; self.sonuc=""
        def adim(self, m): pass
        def kaynak_kullan(self, k): pass
        def sonucla(self, d): self.sonuc=d
        def metni(self): return f"KararIzi: {self.kontrol_adi} → {self.sonuc}"
    class BulamadıMotoru:
        def __init__(self, a, k): self.durum="TESPIT_EDILEMEDI"; self.ozet=""
        def asama1_regex(self, b, k=""): return b
        def asama2_capraz(self, b, k=""): return b
        def asama3_kb(self, z, d=""): return not z

AY_MAP = {
    "JAN":1,"JANUARY":1,"FEB":2,"FEBRUARY":2,"MAR":3,"MARCH":3,
    "APR":4,"APRIL":4,"MAY":5,"JUN":6,"JUNE":6,"JUL":7,"JULY":7,
    "AUG":8,"AUGUST":8,"SEP":9,"SEPTEMBER":9,"OCT":10,"OCTOBER":10,
    "NOV":11,"NOVEMBER":11,"DEC":12,"DECEMBER":12,
}

KIRLI_BL = [
    "CLAUSED","DAMAGED","TORN","WET CARGO","INSUFFICIENT PACKING",
    "PARTLY DAMAGED","RUSTED","LEAKING","STAINED","BROKEN",
]

# Önbellek
_KB_CACHE: dict = {}

def knowledge_base_yukle(kb_dizin: str = "") -> dict:

    """
    knowledge_base/ klasöründeki PDF dosyalarının varlığını kontrol eder
    ve bir indeks sözlüğü oluşturur. PDF içerikleri çalışma zamanında
    sorgulanabilir. kurallar.json da yüklenir.
    """
    global _KB_CACHE
    if _KB_CACHE:
        return _KB_CACHE

    aradiginiz = [
        kb_dizin,
        os.path.join(os.path.dirname(__file__), "knowledge_base"),
        "knowledge_base",
    ]

    kb: dict = {
        "pdf_dosyalari": {},
        "kurallar": {},
        "kaynak_onceligi": [
            "UCP 600 Text.pdf",
            "ISBP yorum örnek.pdf",
            "ICC Banking Opinions 2019 & 2020 - 11 Dec 2020.pdf",
            "mt700 swift_solutions_advanceinformation.pdf",
            "incoterms2020.pdf",
            "eUCP_TR_Çeviri Eylül Son.pdf",
            "eURC_TR_Çeviri Eylül Son.pdf",
        ]
    }

    for dizin in aradiginiz:
        if dizin and os.path.isdir(dizin):
            for dosya in os.listdir(dizin):
                if dosya.endswith(".pdf"):
                    tam_yol = os.path.join(dizin, dosya)
                    kb["pdf_dosyalari"][dosya] = tam_yol
                    log.debug("[DEBUG] KB PDF: %s", dosya)
            break

    # kurallar.json yükle
    for json_yolu in [
        os.path.join(os.path.dirname(__file__), "kurallar.json"),
        "kurallar.json",
    ]:
        if os.path.isfile(json_yolu):
            try:
                with open(json_yolu, encoding="utf-8") as f:
                    kb["kurallar"] = json.load(f)
                log.debug("[DEBUG] kurallar.json yüklendi: %s", json_yolu)
            except Exception as e:
                log.warning("[UYARI] kurallar.json okunamadı: %s", e)
            break

    pdf_say = len(kb["pdf_dosyalari"])
    log.debug("[DEBUG] Knowledge Base hazır: %d PDF, kurallar=%s",
              pdf_say, bool(kb["kurallar"]))
    _KB_CACHE = kb
    return kb


# Geriye dönük uyumluluk
def kurallar_yukle(json_yolu: str = "") -> dict:
    kb = knowledge_base_yukle()
    return kb.get("kurallar", {})

def _kural_aciklama(madde: str) -> str:
    k = kurallar_yukle()
    for item in k.get("kritik_kontroller", []):
        if item.get("madde", "") == madde:
            return item.get("aciklama", "")
    return ""

def _kb_kaynak_notu(dosya_adi: str) -> str:
    """Raporlarda 'Kaynak: knowledge_base/UCP 600 Text.pdf' notu üretir."""
    kb = knowledge_base_yukle()
    if dosya_adi in kb.get("pdf_dosyalari", {}):
        return f"knowledge_base/{dosya_adi}"
    return dosya_adi


# ── normalize_tutar ──────────────────────────────────────────────────────────
def normalize_tutar(metin: str) -> Optional[float]:
    """3.420,00 / 23,940 / 23.940 → doğru float (23.94 üretmez)"""
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
    """Float precision fix: round(26334.000000000004, 2) == 26334.0"""
    if a is None or b is None:
        return False
    a2, b2 = round(a, 2), round(b, 2)
    if iliski == ">=": return a2 >= b2
    if iliski == "<=": return a2 <= b2
    if iliski == "==": return abs(a2-b2) < 0.01
    return False


# ── MT700 Alan Metadata ──────────────────────────────────────────────────────
MT700_META: dict[str, dict] = {
    "20": {
        "ad": "Documentary Credit Number",
        "aciklama": "Akreditifin benzersiz referans numarasıdır.",
        "yorum": (
            "Tüm ibraz belgelerinde (fatura, konşimento, sigorta) aynı LC referansının "
            "kullanılması banka uygulamasında tavsiye edilir. UCP 600 Art 14(a) kapsamında "
            "farklı referans varlığı inceleme gerektirebilir."
        ),
        "madde": "UCP 600 Art 14(a)",
        "kaynak": "UCP 600 Text.pdf",
    },
    "31D": {
        "ad": "Expiry Date & Place",
        "aciklama": "Akreditifin son geçerlilik tarihi ve yeridir.",
        "yorum": (
            "UCP 600 Art 6(d)(i): Bu tarihten sonra yapılan ibrazlar reddedilebilir. "
            "Art 29(a): Son gün resmi tatile gelirse bir sonraki iş gününe uzar. "
            "Geçerlilik yeri ibrazın yapılacağı bankayı belirler."
        ),
        "madde": "UCP 600 Art 6 / Art 29",
        "kaynak": "UCP 600 Text.pdf",
    },
    "32B": {
        "ad": "Currency & Amount",
        "aciklama": "Akreditifin para birimi ve tutarıdır.",
        "yorum": (
            "UCP 600 Art 30(b): Akreditif tutarında %5 tolerans uygulanabilir. "
            "'ABOUT/APPROXIMATELY' ifadesi varsa %10 tolerans geçerlidir. "
            "Art 18(a)(iii): Fatura aynı para biriminde düzenlenmelidir. "
            "Sapma = 0 durumu her koşulda uyumludur."
        ),
        "madde": "UCP 600 Art 18 / Art 30",
        "kaynak": "UCP 600 Text.pdf",
    },
    "40A": {
        "ad": "Form of Documentary Credit",
        "aciklama": "Akreditifin türüdür (IRREVOCABLE, TRANSFERABLE vb.).",
        "yorum": (
            "UCP 600 Art 3: Akreditif aksine hüküm olmadıkça gayrikabili rücudur. "
            "Art 10: IRREVOCABLE akreditif tüm tarafların onayı olmadan değiştirilemez. "
            "Art 38: TRANSFERABLE akreditif devredebilir; devir yalnızca bir kez yapılabilir."
        ),
        "madde": "UCP 600 Art 3 / Art 10 / Art 38",
        "kaynak": "UCP 600 Text.pdf",
    },
    "44C": {
        "ad": "Latest Date of Shipment",
        "aciklama": "Malların en geç yüklenebileceği tarihtir.",
        "yorum": (
            "UCP 600 Art 20(a)(ii): Konşimentodaki 'Shipped on Board' tarihi bu tarihi geçemez. "
            "Art 14(c): Geç yükleme MAJOR DISCREPANCY sebebidir. "
            "ISBP 821 E5: Tarih çelişkisi varsa en erken tarih esas alınır. "
            "Art 29(c): Son yükleme tarihi, geçerlilik tarihi uzamasından etkilenmez."
        ),
        "madde": "UCP 600 Art 14(c) / Art 20 / ISBP 821 E5",
        "kaynak": "UCP 600 Text.pdf",
    },
    "45A": {
        "ad": "Description of Goods",
        "aciklama": "LC'nin mal tanımıdır.",
        "yorum": (
            "UCP 600 Art 18(c): Faturadaki mal tanımı LC'deki tanımla uyumlu olmalıdır; "
            "daha genel ifade kabul edilir, çelişkili ifade kabul edilmez. "
            "Art 14(e): Diğer belgeler (B/L, PL) genel terimler kullanabilir. "
            "ISBP 821 C3: Kısaltmalar kabul edilir."
        ),
        "madde": "UCP 600 Art 18(c) / Art 14(e) / ISBP 821 C3",
        "kaynak": "UCP 600 Text.pdf",
    },
    "46A": {
        "ad": "Documents Required",
        "aciklama": "İbraz edilmesi zorunlu belgeler listesidir.",
        "yorum": (
            "UCP 600 Art 14(a): Bu alanda talep edilen her belgenin eksiksiz ibrazı zorunludur; "
            "eksik belge doğrudan ret sebebidir. "
            "Art 17(a): Her belgeden en az bir orijinal sunulmalıdır. "
            "ISBP 821 A21: Belge sayısı belirtilmişse o kadar orijinal gerekir. "
            "Özel not: 46A'da 'Certificate of Origin issued by Chamber of Commerce' "
            "yazıyorsa fatura beyanı YETERLİ DEĞİLDİR; ayrı CO ibrazı zorunludur."
        ),
        "madde": "UCP 600 Art 14(a) / Art 17(a) / ISBP 821 A21",
        "kaynak": "UCP 600 Text.pdf",
    },
    "47A": {
        "ad": "Additional Conditions",
        "aciklama": "LC'nin ek şartları ve özel koşullarıdır.",
        "yorum": (
            "UCP 600 Art 5: Belirsiz koşullar görmezden gelinebilir. "
            "Art 14(h): Belge gösterilmeden konulan koşul belirtilmemiş sayılır. "
            "Art 16: Somut koşullar karşılanmazsa ret bildirimi gündeme gelebilir."
        ),
        "madde": "UCP 600 Art 5 / Art 14(h) / Art 16",
        "kaynak": "UCP 600 Text.pdf",
    },
    "48": {
        "ad": "Period for Presentation",
        "aciklama": "Yükleme tarihinden sonra ibraz için verilen süredir.",
        "yorum": (
            "UCP 600 Art 14(c): Belirtilmemişse 21 takvim günü uygulanır. "
            "Bu süre geçerlilik tarihini aşamaz. "
            "Art 29(a): Son gün tatile gelirse bir sonraki iş gününe uzar."
        ),
        "madde": "UCP 600 Art 14(c) / Art 29",
        "kaynak": "UCP 600 Text.pdf",
    },
}


# ── MT700 Hukuki Yorum Motoru ────────────────────────────────────────────────
def mt700_hukuki_yorum(parsed: dict[str, Any]) -> list[dict]:
    """
    Her MT700 alanı için BULGU / HUKUKİ DEĞERLENDİRME / DAYANAK / SONUÇ üretir.
    """
    knowledge_base_yukle()  # KB'yi hazır tut

    mt700        = parsed.get("mt700_alanlari", {})
    fatura_tutar = parsed.get("fatura_tutar")
    lc_tutar     = parsed.get("lc_tutar")
    bl_tarih_str = parsed.get("bl_tarih_str")
    sigorta_t    = parsed.get("sigorta_tutari")
    incoterm     = parsed.get("incoterm", "")
    alan_44c     = parsed.get("alan_44c", "")

    sonuclar: list[dict] = []

    for alan, meta in MT700_META.items():
        deger = mt700.get(alan)
        if not deger:
            continue

        karsilastirma = ""
        sonuc         = "BİLGİ"

        if alan == "32B":
            if fatura_tutar and lc_tutar and lc_tutar > 0:
                sapma = (fatura_tutar - lc_tutar) / lc_tutar * 100
                karsilastirma = (
                    f"LC Tutarı: {lc_tutar:,.2f} | "
                    f"Fatura CIF: {fatura_tutar:,.2f} | Sapma: %{sapma:+.2f}"
                )
                sonuc = "✓ UYUMLU" if abs(sapma) <= 5 else "⚠ REZERV RİSKİ"

        elif alan == "44C":
            if bl_tarih_str and alan_44c:
                bl_dt = _tarih(bl_tarih_str)
                lc_dt = _tarih(alan_44c)
                if bl_dt and lc_dt:
                    karsilastirma = f"B/L On Board: {bl_tarih_str} | 44C Son Yükleme: {alan_44c}"
                    sonuc = ("✓ UYUMLU" if bl_dt <= lc_dt
                             else "⚠ GEÇ YÜKLEME — MAJOR DISCREPANCY")
                elif alan_44c:
                    karsilastirma = f"Son Yükleme: {alan_44c} | B/L tarihi henüz tespit edilemedi."
                    sonuc = "MANUEL KONTROL"
            else:
                sonuc = "MANUEL KONTROL"

        elif alan == "45A":
            mal = parsed.get("mal_tanimi_oran")
            if mal is not None:
                karsilastirma = f"Fatura mal tanımı örtüşme oranı: %{mal*100:.0f}"
                sonuc = ("✓ UYUMLU" if mal >= 0.8
                         else "⚠ DÜŞÜK BENZERLİK" if mal >= 0.5
                         else "⚠ REZERV RİSKİ")
            else:
                sonuc = "MANUEL KONTROL"

        elif alan == "46A":
            eksik = parsed.get("eksik_belgeler_46a", [])
            bulunan = parsed.get("bulunan_belgeler_46a", [])
            if eksik:
                karsilastirma = (
                    f"İbraz edilen: {', '.join(b for b in bulunan if b)} | "
                    f"EKSİK: {', '.join(eksik)}"
                )
                sonuc = "⚠ EKSİK BELGE — REZERV"
            else:
                karsilastirma = f"İbraz edilen: {', '.join(b for b in bulunan if b)}" if bulunan else ""
                sonuc = "✓ UYUMLU"

        kaynak_notu = _kb_kaynak_notu(meta.get("kaynak", ""))
        sonuclar.append({
            "alan":          alan,
            "ad":            meta["ad"],
            "deger":         deger[:200],
            "aciklama":      meta["aciklama"],
            "yorum":         meta["yorum"],
            "madde":         meta["madde"],
            "kaynak":        kaynak_notu,
            "karsilastirma": karsilastirma,
            "sonuc":         sonuc,
        })

    log.debug("[DEBUG] mt700_hukuki_yorum: %d alan yorumlandı.", len(sonuclar))
    return sonuclar


# ── UCP Kuralları — Muhakeme Zinciri ─────────────────────────────────────────
def ucp_kurallari_uygula(parsed: dict[str, Any]) -> list[dict]:
    """v11: İşlem tipi, KararIzi, Bulunamadı≠Yok, düzeltme önerileri."""
    knowledge_base_yukle()
    log.debug("[DEBUG] ucp_kurallari_uygula() başladı.")
    rapor: list[dict] = []

    def ekle(madde, aciklama, durum, bulgu, degerl,
             dayanak="", kaynak="UCP 600 Text.pdf", oneri="", karar_izi=None):
        jac = _kural_aciklama(madde)
        if jac and jac not in degerl:
            degerl = f"{jac}\n\n{degerl}".strip()
        rapor.append({
            "madde": madde, "aciklama": aciklama, "durum": durum,
            "detay": bulgu, "hukuki_yorum": degerl,
            "dayanak": dayanak or madde, "kaynak": _kb_kaynak_notu(kaynak),
            "oneri": oneri, "karar_izi": karar_izi.metni() if karar_izi else "",
        })

    ft  = parsed.get("fatura_tutar");  lct = parsed.get("lc_tutar")
    inc = parsed.get("incoterm");       bls = parsed.get("bl_tarih_str")
    c44 = parsed.get("alan_44c", "");  fk  = parsed.get("fat_kilo")
    bk  = parsed.get("bl_kilo");       st  = parsed.get("sigorta_tutari")
    kt  = parsed.get("kusat_text", ""); bt  = parsed.get("konsimento_text", "")
    m7  = parsed.get("mt700_alanlari", {})

    # İşlem Tipi
    islem = _islem_tipi(kt, m7) if BILGI_MOTORU_OK else "DOCUMENTARY_CREDIT"
    log.debug("[DEBUG] İşlem tipi: %s", islem)
    if islem == "E_PRESENTATION":
        ekle("eUCP", "Elektronik İbraz", "BİLGİ",
             "Elektronik ibraz tespit edildi.",
             "eUCP hükümleri uygulanır; normal kağıt akreditif kontrollerinden farklıdır.",
             "eUCP", "eUCP_TR_#U00c7eviri Eyl#U00fcl Son.pdf",
             oneri="eUCP uyumlu format kullanılmalıdır.")
    elif islem == "COLLECTION":
        ekle("URC 522", "Tahsil İşlemi", "BİLGİ",
             "Collection tespit edildi. UCP 600 birincil kaynak değildir.",
             "URC 522 / eURC geçerlidir.",
             "URC 522", "urc 522 dis-ticarette-bankacilik-islemleri-5369.pdf")

    # Art 14: Bilgilendirme
    iz = KararIzi("Art 14"); iz.kaynak_kullan("ucp600")
    iz.adim("Belgeler yüz değerinden inceleniyor."); iz.sonucla("BİLGİ")
    ekle("Art 14", "Belge İnceleme Standardı", "BİLGİ",
         "Belgeler UCP 600 Art 14 kapsamında incelendi.",
         "Art 14(b): 5 iş günü. Art 14(d): Çelişki olmamalı; birebir aynı olmak zorunda değil.",
         "UCP 600 Art 14(b)/Art 14(d)", "UCP 600 Text.pdf", oneri="", karar_izi=iz)

    # Art 30: Tutar
    try:
        iz = KararIzi("Art 30 Tutar"); iz.kaynak_kullan("ucp600")
        if ft and lct and lct > 0:
            about    = any(x in kt.upper() for x in ["ABOUT","APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma    = (ft - lct) / lct * 100
            ta       = "ABOUT→%10" if about else "standart %5"
            iz.adim(f"CIF:{ft:,.2f} | LC:{lct:,.2f} | tolerans:{tolerans}% | sapma:{sapma:+.1f}%")
            if abs(sapma) <= tolerans:
                iz.sonucla("UYUMLU")
                ekle("Art 30", "Tutar Toleransı", "UYUMLU",
                     f"CIF:{ft:,.2f} | LC:{lct:,.2f} | Sapma:%{sapma:+.1f}",
                     f"Art 30(b) {ta}. Sapma %{abs(sapma):.1f} ≤ %{tolerans}. Rezerv yok.",
                     "UCP 600 Art 30(b)", "UCP 600 Text.pdf", oneri="", karar_izi=iz)
            else:
                iz.sonucla("REZERV")
                ekle("Art 18/30", "Tutar Uyumsuzluğu", "REZERV",
                     f"CIF:{ft:,.2f} | LC:{lct:,.2f} | Sapma:%{sapma:+.1f}",
                     f"Tolerans aşıldı: %{abs(sapma):.1f} > %{tolerans}. MAJOR DISCREPANCY.",
                     "UCP 600 Art 18/Art 30", "UCP 600 Text.pdf",
                     oneri=oneri_uret("tutar_uyusmazligi"), karar_izi=iz)
        else:
            eksik = [k for k,v in [("CIF",ft),("LC 32B",lct)] if not v]
            bm = BulamadıMotoru("Tutar","tutar"); bm.asama1_regex(False,""); bm.asama3_kb(False,"")
            iz.adim(f"Bulunamadı≠Yok: {bm.ozet}"); iz.sonucla("MANUEL KONTROL")
            ekle("Art 30","Tutar","MANUEL KONTROL",f"Tespit edilemedi: {', '.join(eksik)}",
                 "Veri eksikliği rezerv değil. Bulunamadı≠Yok. Manuel doğrulama.",
                 "UCP 600 Art 30","UCP 600 Text.pdf",
                 oneri="Fatura CIF ve LC tutarları manuel karşılaştırılmalıdır.", karar_izi=iz)
    except Exception as e:
        ekle("Art 30","Tutar","HATA",str(e),"")

    # Art 18: Fatura Kilo — Bulunamadı≠Yok
    if fk is None:
        iz = KararIzi("Art 18 Fatura Kilo"); iz.kaynak_kullan("ucp600")
        iz.adim("[1] REGEX: Faturada gross weight bulunamadı.")
        iz.adim(f"[2] ÇAPRAZ: PL/BL kilo = {parsed.get('pl_kilo') or bk}.")
        iz.adim("[3] KB: UCP Art 18 faturada kilo zorunlu kılmaz → BİLGİ.")
        iz.sonucla("BİLGİ")
        ekle("Art 18","Fatura Ağırlık","BİLGİ",
             "Faturada gross weight bulunamadı.",
             "Art 18 faturada kilo zorunlu kılmaz. PL/BL doğrulaması yeterli. Bulunamadı≠Yok.",
             "UCP 600 Art 18","UCP 600 Text.pdf", oneri="", karar_izi=iz)

    # Art 27: Temiz Konşimento
    if bt:
        iz = KararIzi("Art 27"); iz.kaynak_kullan("ucp600"); iz.kaynak_kullan("isbp")
        kirli = [k for k in KIRLI_BL if k in bt.upper()]
        if kirli:
            iz.adim(f"Kirli ifade: {kirli}"); iz.sonucla("REZERV")
            ekle("Art 27","Temiz Konşimento","REZERV",f"Kirli ifade: {', '.join(kirli)}",
                 f"Art 27: {', '.join(kirli)} → ret sebebi.",
                 "UCP 600 Art 27","UCP 600 Text.pdf",
                 oneri=oneri_uret("temiz_bl_sorunu"), karar_izi=iz)
        else:
            iz.adim("Kirli ifade yok."); iz.sonucla("UYUMLU")
            ekle("Art 27","Temiz Konşimento","UYUMLU","Olumsuz kloz bulunamadı.",
                 "Art 27 şartı karşılandı.","UCP 600 Art 27","UCP 600 Text.pdf",
                 oneri="", karar_izi=iz)

    # Art 20: Shipped on Board
    if bt:
        iz = KararIzi("Art 20 On Board"); iz.kaynak_kullan("ucp600")
        if any(k in bt.upper() for k in ["SHIPPED ON BOARD","ON BOARD","CLEAN ON BOARD"]):
            iz.sonucla("UYUMLU")
            ekle("Art 20","Shipped on Board","UYUMLU","On Board şerhi mevcut.",
                 "Art 20(a)(ii): Şart karşılandı.",
                 "UCP 600 Art 20(a)(ii)","UCP 600 Text.pdf", oneri="", karar_izi=iz)
        else:
            iz.sonucla("REZERV")
            ekle("Art 20","Shipped on Board","REZERV","On Board şerhi bulunamadı.",
                 "Art 20(a)(ii): Zorunlu şerh eksik.",
                 "UCP 600 Art 20(a)(ii)","UCP 600 Text.pdf",
                 oneri=oneri_uret("on_board_eksik"), karar_izi=iz)

    # Art 20/44C: Yükleme Tarihi
    iz = KararIzi("Art 20 Yükleme Tarihi"); iz.kaynak_kullan("ucp600")
    iz.adim(f"B/L:{bls or '-'} | 44C:{c44 or '-'}")
    if bls and c44:
        bd = _tarih(bls); ld = _tarih(c44)
        if bd and ld:
            if bd <= ld:
                iz.sonucla("UYUMLU")
                ekle("Art 20","Yükleme Tarihi","UYUMLU",f"B/L:{bls} ≤ 44C:{c44}",
                     "Art 14(c)/Art 20(a)(ii): Geç yükleme yok.",
                     "UCP 600 Art 14(c)/Art 20(a)(ii)","UCP 600 Text.pdf",oneri="",karar_izi=iz)
            else:
                iz.sonucla("REZERV")
                ekle("Art 20","Yükleme Tarihi — GEÇ","REZERV",f"B/L:{bls} > 44C:{c44}",
                     "Art 14(c): MAJOR DISCREPANCY.",
                     "UCP 600 Art 14(c)/Art 20","UCP 600 Text.pdf",
                     oneri=oneri_uret("gec_yukleme"), karar_izi=iz)
        else:
            iz.adim("Tarih formatı tanınamadı. Bulunamadı≠Yok."); iz.sonucla("MANUEL KONTROL")
            ekle("Art 20","Yükleme Tarihi","MANUEL KONTROL",
                 f"B/L:{bls} | 44C:{c44} — format tanınamadı.",
                 "Bulunamadı≠Yok. Manuel doğrulama.",
                 "UCP 600 Art 20","UCP 600 Text.pdf",
                 oneri="Tarih formatı doğrulanarak kontrol tekrarlanmalıdır.", karar_izi=iz)
    else:
        eksik = [n for n,v in [("B/L Tarihi",bls),("44C",c44 or None)] if not v]
        iz.adim(f"Tespit edilemedi: {eksik}"); iz.sonucla("MANUEL KONTROL")
        ekle("Art 20","Yükleme Tarihi","MANUEL KONTROL",f"Tespit edilemedi: {', '.join(eksik)}",
             "Veri eksikliği rezerv değil. Manuel doğrulama.",
             "UCP 600 Art 20","UCP 600 Text.pdf",
             oneri="44C ve B/L tarihi manuel karşılaştırılmalıdır.", karar_izi=iz)

    # Art 14d: Kilo — Çapraz Belge Önceliği
    try:
        if bk is not None:
            iz = KararIzi("Art 14d Kilo"); iz.kaynak_kullan("ucp600")
            if fk is not None and abs(fk - bk) < 1.0:
                iz.sonucla("UYUMLU")
                ekle("Art 30","Kilo (Fatura vs B/L)","UYUMLU",f"Eşleşti: {fk:,.2f} KG",
                     "Art 14(d): Ağırlık uyumlu.",
                     "UCP 600 Art 14(d)","UCP 600 Text.pdf", oneri="", karar_izi=iz)
            elif fk is None:
                iz.adim(f"Fatura kilo yok (Art 18 zorunlu kılmaz). B/L:{bk:,.2f} KG.")
                iz.sonucla("BİLGİ")
                ekle("Art 18","Kilo (B/L)","BİLGİ",
                     f"B/L Gross Weight:{bk:,.2f} KG (Fatura kilo içermiyor)",
                     "Art 18 faturada kilo zorunlu kılmaz. B/L referans alındı.",
                     "UCP 600 Art 18","UCP 600 Text.pdf", oneri="", karar_izi=iz)
    except Exception as e:
        ekle("Art 30","Kilo","HATA",str(e),"")

    # Art 28(f)(ii): Sigorta
    if inc in ["CIF","CIP"]:
        iz = KararIzi("Art 28 Sigorta")
        iz.kaynak_kullan("ucp600"); iz.kaynak_kullan("incoterms")
        iz.adim(f"Incoterm:{inc} → Art 28 + Incoterms 2020 birlikte.")
        if st and ft and ft > 0:
            min_t = round(ft * 1.10, 2); sr = round(st, 2)
            iz.adim(f"CIF:{ft:,.2f} | Min:{min_t:,.2f} | Poliçe:{sr:,.2f} | round() uygulandı.")
            if _celiski_denetle(sr, min_t, ">="):
                iz.sonucla("UYUMLU")
                ekle("Art 28(f)(ii)","Sigorta Teminatı","UYUMLU",
                     f"CIF:{ft:,.2f} | Min:{min_t:,.2f} | Poliçe:{sr:,.2f}",
                     f"Art 28(f)(ii): CIF×110% karşılandı. Incoterms 2020 {inc}: satıcı yükümlüsü. Rezerv yok.",
                     "UCP 600 Art 28(f)(ii)/Incoterms 2020","UCP 600 Text.pdf",
                     oneri="", karar_izi=iz)
            else:
                iz.sonucla("REZERV")
                ekle("Art 28(f)(ii)","Sigorta — YETERSİZ","REZERV",
                     f"Poliçe:{sr:,.2f} < Min:{min_t:,.2f}",
                     f"Art 28(f)(ii): CIF×110%={min_t:,.2f} karşılanmadı.",
                     "UCP 600 Art 28(f)(ii)","UCP 600 Text.pdf",
                     oneri=oneri_uret("sigorta_eksik", f"Gerekli:{min_t:,.2f}"),
                     karar_izi=iz)
        elif st:
            iz.adim("CIF tespit edilemedi. Bulunamadı≠Yok."); iz.sonucla("MANUEL KONTROL")
            ekle("Art 28(f)(ii)","Sigorta Teminatı","MANUEL KONTROL",
                 f"Sigorta:{st:,.2f} | CIF tespit edilemedi.",
                 "CIF belirlenemedi. Veri eksikliği rezerv değil.",
                 "UCP 600 Art 28(f)(ii)","UCP 600 Text.pdf",
                 oneri="CIF belirlenerek kontrol tekrarlanmalıdır.", karar_izi=iz)
        else:
            iz.adim("Sigorta tutarı tespit edilemedi. OCR düşük olabilir."); iz.sonucla("MANUEL KONTROL")
            ekle("Art 28(f)(ii)","Sigorta Teminatı","MANUEL KONTROL",
                 "Sigorta tutarı tespit edilemedi.",
                 "Bulunamadı≠Yok. OCR hatası olabilir. Manuel doğrulama.",
                 "UCP 600 Art 28(f)(i)","UCP 600 Text.pdf",
                 oneri="Sigorta poliçesi manuel incelenmeli.", karar_izi=iz)

    # Art 16: Rezerv Bildirimi
    rezervler = [r for r in rapor if r["durum"] == "REZERV"]
    if rezervler:
        ozet = "\n".join(f"  [{r['madde']}] {r['detay']}" for r in rezervler)
        oneriler = "\n".join(
            f"  • {r['madde']}: {r.get('oneri','')}"
            for r in rezervler if r.get("oneri")
        )
        ekle("Art 16","Rezerv Bildirimi","UYARI",
             f"Rezerv: {len(rezervler)} adet",
             f"Art 16(c): Ret hakkı. Bildirim 5. iş günü sonuna kadar (Art 16(d)).\n\n"
             f"Uyumsuzluklar:\n{ozet}\n\nDüzeltme Önerileri:\n{oneriler}",
             "UCP 600 Art 16(c)/Art 16(d)","UCP 600 Text.pdf",
             oneri="5 iş günü içinde düzeltme veya waiver talep edilmelidir.")

    log.debug("[DEBUG] ucp_kurallari_uygula: %d kayıt.", len(rapor))
    return rapor


def uzman_gorusu_uret(parsed: dict[str, Any], ucp_sonuclari: list[dict]) -> str:
    """
    BANKA UZMANI NİHAİ GÖRÜŞÜ — rapor sonu bölümü.
    Talimat #6: knowledge_base kaynaklarını referans gösterir.
    """
    knowledge_base_yukle()
    rezervler    = [r for r in ucp_sonuclari if r.get("durum") == "REZERV"]
    major_sayisi = len(rezervler)
    fatura_tutar = parsed.get("fatura_tutar")
    lc_tutar     = parsed.get("lc_tutar")
    sigorta_t    = parsed.get("sigorta_tutari")
    incoterm     = parsed.get("incoterm","")
    lc_no        = parsed.get("lc_no","")
    mt700        = parsed.get("mt700_alanlari", {})

    s = []
    tarih = datetime.now().strftime("%d.%m.%Y")
    s.append(f"Değerlendirme Tarihi: {tarih}")
    if lc_no and lc_no != "Tespit edilemedi":
        s.append(f"LC Referans: {lc_no}")
    s.append(f"Hukuki Dayanak: {_kb_kaynak_notu('UCP 600 Text.pdf')} | kurallar.json")
    s.append("")

    if major_sayisi == 0:
        s.append(
            "Belgeler genel olarak UCP 600 ve ISBP 821 ile uyumludur. "
            "UCP 600 Art 14(a) kapsamında yapılan incelemede belgeler arasında "
            "esaslı çelişki görülmemiştir. Kritik rezerv tespit edilmemiştir."
        )
    else:
        rezerv_listesi = "\n".join(f"  • [{r['madde']}] {r['detay']}" for r in rezervler)
        s.append(
            f"Bu ibraz dosyasında {major_sayisi} adet uyumsuzluk tespit edilmiştir. "
            f"UCP 600 Art 16(c) uyarınca banka ret bildirimi yapma hakkına sahip olup "
            f"bildirim en geç 5. iş günü sonuna kadar yapılmalıdır.\n\n"
            f"Tespit edilen uyumsuzluklar:\n{rezerv_listesi}"
        )
    s.append("")

    # Sigorta değerlendirmesi
    if incoterm in ["CIF","CIP"] and fatura_tutar and sigorta_t:
        min_t   = round(fatura_tutar * 1.10, 2)
        sig_t_r = round(sigorta_t, 2)
        if _celiski_denetle(sig_t_r, min_t, ">="):
            s.append(
                f"Sigorta teminatı Art 28(f)(ii) gerekliliklerini karşılamaktadır. "
                f"CIF: {fatura_tutar:,.2f} | Minimum: {min_t:,.2f} | Poliçe: {sig_t_r:,.2f}."
            )
            s.append("")

    # Tutar değerlendirmesi
    if fatura_tutar and lc_tutar:
        sapma = abs((fatura_tutar - lc_tutar) / lc_tutar * 100)
        if sapma <= 5:
            s.append(
                f"Fatura CIF ({fatura_tutar:,.2f}) ile LC tutarı ({lc_tutar:,.2f}) "
                f"arasındaki sapma %{sapma:.1f} olup Art 30 tolerans sınırı içindedir."
            )
            s.append("")

    # MT700 eksiklik uyarısı
    eksik_mt = [a for a in ["44C","46A","45A"] if not mt700.get(a)]
    if eksik_mt:
        s.append(
            f"MT700 metninden {', '.join(eksik_mt)} alanları tespit edilemediğinden "
            f"bu alanlara ilişkin kontroller manuel doğrulanmalıdır."
        )
        s.append("")

    # Genel kanaat
    if major_sayisi == 0:
        kanaat = (
            "Genel kanaat: Belgelerin büyük ölçüde UCP 600 standartlarıyla uyumlu olduğu "
            "değerlendirilmektedir. Banka kabul olasılığı yüksektir."
        )
    elif major_sayisi <= 2:
        kanaat = (
            "Genel kanaat: Tespit edilen uyumsuzluklar giderilebilir niteliktedir. "
            "Düzeltmeler yapıldıktan sonra kabul olasılığı artacaktır."
        )
    else:
        kanaat = (
            "Genel kanaat: Birden fazla esaslı uyumsuzluk tespit edilmiştir. "
            "Belgelerin revize edilmesi veya amir onayı (waiver) alınması önerilmektedir."
        )
    s.append(kanaat)
    s.append("")
    s.append(
        "Bu rapor bilgilendirme amaçlıdır. UCP 600 ICC tarafından yayımlanmış özel sektör "
        "kurallarıdır; uygulanabilirliği akreditif metninde açıkça belirtilmesine bağlıdır. "
        "Kesin hukuki görüş için akreditif uzmanına danışılması tavsiye edilir."
    )
    return "\n".join(s)


def analiz_et(depo: dict) -> list:
    """Kullanım dışı — geriye dönük uyumluluk."""
    log.warning("analiz_et() deprecated.")
    return []
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] hukuk_motoru: %(message)s"))
    log.addHandler(h)
log.setLevel(logging.DEBUG)

AY_MAP = {
    "JAN":1,"JANUARY":1,"FEB":2,"FEBRUARY":2,"MAR":3,"MARCH":3,
    "APR":4,"APRIL":4,"MAY":5,"JUN":6,"JUNE":6,"JUL":7,"JULY":7,
    "AUG":8,"AUGUST":8,"SEP":9,"SEPTEMBER":9,"OCT":10,"OCTOBER":10,
    "NOV":11,"NOVEMBER":11,"DEC":12,"DECEMBER":12,
}

KIRLI_BL = [
    "CLAUSED","DAMAGED","TORN","WET CARGO","INSUFFICIENT PACKING",
    "PARTLY DAMAGED","RUSTED","LEAKING","STAINED","BROKEN",
]

# ── kurallar.json yükleyici ──────────────────────────────────────────────────
_KURALLAR_CACHE: dict = {}

def kurallar_yukle(json_yolu: str = "") -> dict:
    """
    kurallar.json'u yükler ve önbelleğe alır.
    Bulunamazsa boş dict döner — sistem çalışmaya devam eder.
    """
    global _KURALLAR_CACHE
    if _KURALLAR_CACHE:
        return _KURALLAR_CACHE
    aradiginiz = [
        json_yolu,
        os.path.join(os.path.dirname(__file__), "kurallar.json"),
        "kurallar.json",
    ]
    for yol in aradiginiz:
        if yol and os.path.isfile(yol):
            try:
                with open(yol, encoding="utf-8") as f:
                    _KURALLAR_CACHE = json.load(f)
                log.debug("[DEBUG] kurallar.json yüklendi: %s", yol)
                return _KURALLAR_CACHE
            except Exception as e:
                log.warning("[UYARI] kurallar.json okunamadı: %s", e)
    log.warning("[UYARI] kurallar.json bulunamadı — varsayılan açıklamalar kullanılacak.")
    return {}

def _kural_aciklama(madde: str) -> str:
    """kurallar.json'dan madde açıklamasını döner."""
    k = kurallar_yukle()
    for item in k.get("kritik_kontroller", []):
        if item.get("madde", "") == madde:
            return item.get("aciklama", "")
    return ""

# ── MT700 alan metadata (kurallar.json'dan öncelik; fallback sabit) ──────────
MT700_META: dict[str, dict] = {
    "20": {
        "ad":       "Documentary Credit Number",
        "aciklama": "Akreditifin benzersiz referans numarasıdır.",
        "yorum": (
            "Tüm ibraz belgelerinde (fatura, konşimento, sigorta poliçesi) aynı LC "
            "referansının kullanılması banka uygulamasında tavsiye edilir. Farklı "
            "referans kullanımı Art 14(a) kapsamında inceleme gerektirebilir."
        ),
        "madde": "UCP 600 Art 14(a)",
    },
    "31D": {
        "ad":       "Expiry Date & Place",
        "aciklama": "Akreditifin son geçerlilik tarihi ve yeridir.",
        "yorum": (
            "UCP 600 Art 6(d)(i): Bu tarihten sonra yapılan belgeli ibrazlar banka "
            "tarafından reddedilebilir. Geçerlilik yeri, ibrazın nerede yapılacağını "
            "belirler. Art 29(a): Son gün resmi tatile gelirse bir sonraki iş gününe uzar."
        ),
        "madde": "UCP 600 Art 6 / Art 29",
    },
    "32B": {
        "ad":       "Currency & Amount",
        "aciklama": "Akreditifin para birimi ve tutarıdır.",
        "yorum": (
            "UCP 600 Art 30(b) uyarınca akreditif tutarında %5 tolerans uygulanabilir. "
            "Akreditifte 'ABOUT' veya 'APPROXIMATELY' ifadesi varsa tolerans %10'a çıkar. "
            "Art 18(a)(iii): Fatura akreditifle aynı para biriminde düzenlenmelidir. "
            "Eşitlik durumu (sapma = 0) her koşulda uyumludur."
        ),
        "madde": "UCP 600 Art 18 / Art 30",
    },
    "40A": {
        "ad":       "Form of Documentary Credit",
        "aciklama": "Akreditifin türüdür (IRREVOCABLE, TRANSFERABLE vb.).",
        "yorum": (
            "UCP 600 Art 3: Akreditif aksine hüküm olmadıkça gayrikabili rücudur. "
            "Art 10: IRREVOCABLE akreditif tüm tarafların onayı olmadan değiştirilemez. "
            "Art 38: TRANSFERABLE akreditif birinci lehdar tarafından devredebilir; "
            "devir yalnızca bir kez yapılabilir."
        ),
        "madde": "UCP 600 Art 3 / Art 10 / Art 38",
    },
    "44C": {
        "ad":       "Latest Date of Shipment",
        "aciklama": "Malların en geç yüklenebileceği tarihtir.",
        "yorum": (
            "UCP 600 Art 20(a)(ii): Konşimentodaki 'Shipped on Board' tarihi bu tarihi "
            "geçemez. Art 14(c): Geç yükleme doğrudan MAJOR DISCREPANCY sebebidir. "
            "ISBP 821 E5: Tarih çelişkisi varsa en erken tarih esas alınır. "
            "Art 29(c): Son yükleme tarihi, geçerlilik tarihi uzamasından etkilenmez."
        ),
        "madde": "UCP 600 Art 14(c) / Art 20 / ISBP 821 E5",
    },
    "44E": {
        "ad":       "Port of Loading / Airport of Departure",
        "aciklama": "Yükleme limanı veya kalkış havalimanıdır.",
        "yorum": (
            "Konşimentodaki yükleme limanı bu değerle uyumlu olmalıdır. "
            "Farklı liman gösterimi ISBP 821 E10 kapsamında rezerv sebebi olabilir. "
            "UCP 600 Art 20(a)(iii): B/L yükleme limanı LC'de belirtilen liman olmalıdır."
        ),
        "madde": "UCP 600 Art 20 / ISBP 821 E10",
    },
    "44F": {
        "ad":       "Port of Discharge / Airport of Destination",
        "aciklama": "Boşaltma limanı veya varış havalimanıdır.",
        "yorum": (
            "Konşimentodaki varış limanı bu alanla uyumlu olmalıdır. "
            "ISBP 821 E11: Varış limanı uyuşmazlığı rezerv sebebidir. "
            "UCP 600 Art 20(a)(iii): B/L, LC'de belirtilen tahliye limanını göstermelidir."
        ),
        "madde": "UCP 600 Art 20 / ISBP 821 E11",
    },
    "45A": {
        "ad":       "Description of Goods",
        "aciklama": "LC'nin mal tanımıdır.",
        "yorum": (
            "UCP 600 Art 18(c): Ticari faturadaki mal tanımı LC'deki tanımla uyumlu olmalıdır; "
            "daha genel ifade kullanılabilir ancak çelişkili ifade kullanılamaz. "
            "Art 14(e): Diğer belgelerde (B/L, PL) mal tanımı LC ile çelişmemelidir; "
            "genel terimler kabul edilir. ISBP 821 C3: Kısaltmalar kabul edilir."
        ),
        "madde": "UCP 600 Art 18(c) / Art 14(e) / ISBP 821 C3",
    },
    "46A": {
        "ad":       "Documents Required",
        "aciklama": "İbraz edilmesi zorunlu belgeler listesidir.",
        "yorum": (
            "UCP 600 Art 14(a): Bu alanda talep edilen her belgenin eksiksiz ibraz "
            "edilmesi zorunludur; eksik belge doğrudan ret sebebidir. "
            "Art 17(a): Her belgeden en az bir orijinal sunulmalıdır. "
            "ISBP 821 A21: Belge sayısı belirtilmişse o kadar orijinal sunulmalıdır. "
            "Art 14(f): Belge türü belirtilmiş ancak içeriği tarif edilmemişse, "
            "işlevini yerine getiren her belge kabul edilir."
        ),
        "madde": "UCP 600 Art 14(a) / Art 17(a) / ISBP 821 A21",
    },
    "47A": {
        "ad":       "Additional Conditions",
        "aciklama": "LC'nin ek şartları ve özel koşullarıdır.",
        "yorum": (
            "UCP 600 Art 5: Bankalar yalnızca belgelerle ilgilenir; belirsiz koşullar "
            "görmezden gelinebilir. Art 14(h): Belge gösterilmeden konulan koşul "
            "belirtilmemiş sayılır. Art 16: Somut koşullar karşılanmazsa ret bildirimi "
            "gündeme gelebilir."
        ),
        "madde": "UCP 600 Art 5 / Art 14(h) / Art 16",
    },
    "48": {
        "ad":       "Period for Presentation",
        "aciklama": "Yükleme tarihinden sonra ibraz için verilen süredir.",
        "yorum": (
            "UCP 600 Art 14(c): Belirtilmemişse 21 takvim günü uygulanır. "
            "Bu süre, geçerlilik tarihini aşamaz. Art 29(a): Son gün resmi tatile "
            "gelirse bir sonraki iş gününe uzar. Süre aşıldığında belgeler reddedilebilir."
        ),
        "madde": "UCP 600 Art 14(c) / Art 29",
    },
}

# ── Yardımcılar ──────────────────────────────────────────────────────────────
def normalize_tutar(metin: str) -> Optional[float]:
    """23,940 / 23.940 / 23.940,00 → 23940.0  (23.94 üretmez)"""
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
    """Float precision fix: round(26334.000000000004, 2) == 26334.0 → True"""
    if a is None or b is None:
        return False
    a2, b2 = round(a, 2), round(b, 2)
    if iliski == ">=": return a2 >= b2
    if iliski == "<=": return a2 <= b2
    if iliski == "==": return abs(a2-b2) < 0.01
    return False


# ── MT700 Akıllı Yorum Motoru ────────────────────────────────────────────────
def mt700_hukuki_yorum(parsed: dict[str, Any]) -> list[dict]:
    """
    MT700 alanları için UCP 600 referanslı uzman yorumu üretir.
    Yeni hesaplama yapmaz — parsed_data'daki mevcut verileri kullanır.

    Döner: list[dict]
      { alan, ad, deger, aciklama, yorum, madde, karsilastirma, sonuc }
    """
    mt700        = parsed.get("mt700_alanlari", {})
    fatura_tutar = parsed.get("fatura_tutar")
    lc_tutar     = parsed.get("lc_tutar")
    bl_tarih_str = parsed.get("bl_tarih_str")
    sigorta_t    = parsed.get("sigorta_tutari")
    incoterm     = parsed.get("incoterm", "")
    alan_44c     = parsed.get("alan_44c", "")

    sonuclar: list[dict] = []

    for alan, meta in MT700_META.items():
        deger = mt700.get(alan)
        if not deger:
            continue

        karsilastirma = ""
        sonuc         = "BİLGİ"

        if alan == "32B":
            if fatura_tutar and lc_tutar and lc_tutar > 0:
                sapma = (fatura_tutar - lc_tutar) / lc_tutar * 100
                karsilastirma = (
                    f"LC Tutarı: {lc_tutar:,.2f} | "
                    f"Fatura CIF: {fatura_tutar:,.2f} | "
                    f"Sapma: %{sapma:+.2f}"
                )
                sonuc = "✓ UYUMLU" if abs(sapma) <= 5 else "⚠ REZERV RİSKİ"

        elif alan == "44C":
            if bl_tarih_str and alan_44c:
                bl_dt = _tarih(bl_tarih_str)
                lc_dt = _tarih(alan_44c)
                if bl_dt and lc_dt:
                    karsilastirma = (
                        f"B/L On Board: {bl_tarih_str} | 44C Son Yükleme: {alan_44c}"
                    )
                    sonuc = ("✓ UYUMLU" if bl_dt <= lc_dt
                             else "⚠ GEÇ YÜKLEME — MAJOR DISCREPANCY")
            elif alan_44c:
                karsilastirma = f"Son Yükleme: {alan_44c} | B/L tarihi tespit edilemedi."
                sonuc = "MANUEL KONTROL"

        elif alan == "45A":
            mal = parsed.get("mal_tanimi_oran")
            if mal is not None:
                karsilastirma = f"Fatura mal tanımı örtüşme oranı: %{mal*100:.0f}"
                sonuc = ("✓ UYUMLU" if mal >= 0.8
                         else "⚠ DÜŞÜK BENZERLİK" if mal >= 0.5
                         else "⚠ REZERV RİSKİ")
            else:
                sonuc = "MANUEL KONTROL"

        elif alan == "46A":
            eksik = parsed.get("eksik_belgeler_46a", [])
            if eksik:
                karsilastirma = f"Eksik: {', '.join(eksik)}"
                sonuc = "⚠ EKSİK BELGE — REZERV"
            else:
                bulunan = parsed.get("bulunan_belgeler_46a", [])
                karsilastirma = f"İbraz edilen: {', '.join(bulunan)}" if bulunan else ""
                sonuc = "✓ UYUMLU"

        sonuclar.append({
            "alan":          alan,
            "ad":            meta["ad"],
            "deger":         deger[:200],
            "aciklama":      meta["aciklama"],
            "yorum":         meta["yorum"],
            "madde":         meta["madde"],
            "karsilastirma": karsilastirma,
            "sonuc":         sonuc,
        })

    log.debug("[DEBUG] mt700_hukuki_yorum: %d alan yorumlandı.", len(sonuclar))
    return sonuclar


def analiz_et(depo: dict) -> list:
    """Kullanım dışı — geriye dönük uyumluluk."""
    log.warning("analiz_et() deprecated. ucp_kurallari_uygula() kullanın.")
    return []