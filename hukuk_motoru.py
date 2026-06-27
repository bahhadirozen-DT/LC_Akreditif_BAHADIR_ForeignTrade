"""
hukuk_motoru.py - UCP 600 / ISBP 821 Hukuki Yorum Motoru v10.1
================================================================
Yenilikler v10.1:
  - knowledge_base/ klasöründen PDF indeksi yüklenir
  - Muhakeme zinciri: veri yok ≠ rezerv
  - CO (Certificate of Origin) sıkı kuralı: 46A'da istenmişse rezerv
  - Fatura kilo kuralı: Art 18 kilo zorunlu kılmaz → BİLGİ
  - BULGU / HUKUKİ DEĞERLENDİRME / DAYANAK / SONUÇ formatı
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

# ── Knowledge Base Loader ────────────────────────────────────────────────────
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
    """
    UCP 600 kontrolleri — BULGU / HUKUKİ DEĞERLENDİRME / DAYANAK / SONUÇ formatı.
    Muhakeme zinciri: veri yok ≠ rezerv (Talimat #3).
    """
    knowledge_base_yukle()
    log.debug("[DEBUG] ucp_kurallari_uygula() başladı.")
    rapor: list[dict] = []

    def ekle(madde, aciklama, durum, bulgu, degerlendirme, dayanak="", kaynak="UCP 600 Text.pdf"):
        json_ac = _kural_aciklama(madde)
        if json_ac and json_ac not in degerlendirme:
            degerlendirme = f"{json_ac}\n\n{degerlendirme}".strip()
        _dayanak = dayanak if dayanak else madde
        rapor.append({
            "madde":          madde,
            "aciklama":       aciklama,
            "durum":          durum,
            "detay":          bulgu,
            "hukuki_yorum":   degerlendirme,
            "dayanak":        _dayanak,
            "kaynak":         _kb_kaynak_notu(kaynak),
        })

    fatura_tutar    = parsed.get("fatura_tutar")
    lc_tutar        = parsed.get("lc_tutar")
    incoterm        = parsed.get("incoterm")
    bl_tarih_str    = parsed.get("bl_tarih_str")
    alan_44c        = parsed.get("alan_44c", "")
    fat_kilo        = parsed.get("fat_kilo")
    bl_kilo         = parsed.get("bl_kilo")
    sigorta_tutari  = parsed.get("sigorta_tutari")
    kusat_text      = parsed.get("kusat_text", "")
    konsimento_text = parsed.get("konsimento_text", "")
    alan_46a        = parsed.get("mt700_alanlari", {}).get("46A", "")

    # ── Art 14: Belge İnceleme (Bilgilendirme) ────────────────────────────────
    ekle("Art 14", "Belge İnceleme Standardı", "BİLGİ",
         "Belgeler UCP 600 Art 14 kapsamında yüz değerinden incelendi.",
         "UCP 600 Art 14(b): İnceleme süresi en fazla 5 iş günüdür. "
         "Art 14(d): Belgeler arasındaki veriler çelişmemelidir; birebir aynı olmak zorunda değildir. "
         "NOT: Bu satır bilgilendirme amaçlıdır; sistem gerçek zamanlı banka incelemesi yapmaz.",
         "UCP 600 Art 14(b) / Art 14(d)",
         "UCP 600 Text.pdf")

    # ── Art 18 / Art 30: Tutar ────────────────────────────────────────────────
    try:
        if fatura_tutar and lc_tutar and lc_tutar > 0:
            about    = any(x in kusat_text.upper() for x in ["ABOUT","APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma    = (fatura_tutar - lc_tutar) / lc_tutar * 100
            t_aciklama = "'ABOUT/APPROXIMATELY' nedeniyle %10" if about else "standart %5"
            if abs(sapma) <= tolerans:
                ekle("Art 30", "Tutar Toleransı", "UYUMLU",
                     f"CIF: {fatura_tutar:,.2f} | LC: {lc_tutar:,.2f} | Sapma: %{sapma:+.1f}",
                     f"UCP 600 Art 30(b) kapsamında {t_aciklama} tolerans uygulanır. "
                     f"Fatura CIF {fatura_tutar:,.2f}, LC tutarı {lc_tutar:,.2f}. "
                     f"Sapma %{abs(sapma):.1f} tolerans sınırı içindedir. Rezerv oluşmamıştır.",
                     "UCP 600 Art 30(b)")
            else:
                ekle("Art 18/30", "Tutar Uyumsuzluğu", "REZERV",
                     f"CIF: {fatura_tutar:,.2f} | LC: {lc_tutar:,.2f} | Sapma: %{sapma:+.1f}",
                     f"Fatura tutarı {t_aciklama} toleransı aşmaktadır. "
                     f"Sapma: %{abs(sapma):.1f}. Bu durum Art 18 / Art 30 kapsamında rezerv sebebidir.",
                     "UCP 600 Art 18 / Art 30")
        else:
            eksik = [k for k,v in [("Fatura CIF",fatura_tutar),("LC 32B",lc_tutar)] if not v]
            ekle("Art 30", "Tutar", "MANUEL KONTROL",
                 f"Tespit edilemedi: {', '.join(eksik)}",
                 "Tutar karşılaştırması için fatura CIF ve LC 32B değerleri gereklidir. "
                 "Veri eksikliği tek başına rezerv sebebi değildir (Muhakeme Talimatı #3). "
                 "Manuel doğrulama yapılmalıdır.",
                 "UCP 600 Art 30")
    except Exception as e:
        ekle("Art 30", "Tutar", "HATA", str(e), "", "UCP 600 Art 30")

    # ── Art 18: Fatura Kilo — Muhakeme Zinciri (Talimat #4) ─────────────────
    if fat_kilo is None:
        ekle("Art 18", "Fatura Ağırlık Bilgisi", "BİLGİ",
             "Faturada gross weight ifadesi bulunamadı.",
             "UCP 600 Art 18, commercial invoice için ağırlık bilgisini zorunlu kılmaz. "
             "Kilo bilgisi Packing List ve Bill of Lading üzerinden doğrulanabiliyorsa "
             "faturada bulunmaması rezerv sebebi değildir. "
             "Muhakeme: veri yok ≠ rezerv (Talimat #4).",
             "UCP 600 Art 18")

    # ── Art 27: Temiz Konşimento ──────────────────────────────────────────────
    if konsimento_text:
        kirli = [k for k in KIRLI_BL if k in konsimento_text.upper()]
        if kirli:
            ekle("Art 27", "Temiz Konşimento", "REZERV",
                 f"Kirli ifade: {', '.join(kirli)}",
                 "UCP 600 Art 27: Bankalar yalnızca temiz taşıma belgelerini kabul eder. "
                 f"Tespit edilen olumsuz kloz: {', '.join(kirli)}. "
                 "Bu ifadeler doğrudan ret sebebidir.",
                 "UCP 600 Art 27")
        else:
            ekle("Art 27", "Temiz Konşimento", "UYUMLU",
                 "Konşimentoda olumsuz kloz veya hasar şerhi bulunamadı.",
                 "UCP 600 Art 27: Konşimentoda malın veya ambalajın hasarlı durumunu "
                 "belirten herhangi bir kloz bulunmamaktadır. Temiz konşimento şartı karşılanmıştır.",
                 "UCP 600 Art 27")

    # ── Art 20: Shipped on Board ──────────────────────────────────────────────
    if konsimento_text:
        bl_u = konsimento_text.upper()
        if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u or "CLEAN ON BOARD" in bl_u:
            ekle("Art 20", "Shipped on Board Şerhi", "UYUMLU",
                 "On Board şerhi konşimentoda mevcut.",
                 "UCP 600 Art 20(a)(ii): Konşimenton 'Shipped on Board' şerhi veya "
                 "ön baskı ile yüklemeyi göstermesi zorunludur. Şart karşılanmıştır.",
                 "UCP 600 Art 20(a)(ii)")
        else:
            ekle("Art 20", "Shipped on Board Şerhi", "REZERV",
                 "On Board şerhi konşimentoda bulunamadı.",
                 "UCP 600 Art 20(a)(ii): 'Shipped on Board' şerhi zorunludur. "
                 "Bu eksiklik doğrudan ret sebebidir.",
                 "UCP 600 Art 20(a)(ii)")

    # ── Art 20 / 44C: Yükleme Tarihi ─────────────────────────────────────────
    if bl_tarih_str and alan_44c:
        bl_dt = _tarih(bl_tarih_str)
        lc_dt = _tarih(alan_44c)
        if bl_dt and lc_dt:
            if bl_dt <= lc_dt:
                ekle("Art 20", "Yükleme Tarihi", "UYUMLU",
                     f"B/L On Board: {bl_tarih_str} ≤ 44C: {alan_44c}",
                     f"UCP 600 Art 14(c) ve Art 20(a)(ii) kapsamında konşimento yükleme tarihi "
                     f"({bl_tarih_str}), LC 44C son yükleme tarihi ({alan_44c}) ile uyumludur. "
                     f"Geç yükleme rezervi oluşmamıştır.",
                     "UCP 600 Art 14(c) / Art 20(a)(ii)")
            else:
                ekle("Art 20", "Yükleme Tarihi — GEÇ YÜKLEME", "REZERV",
                     f"B/L: {bl_tarih_str} > 44C: {alan_44c}",
                     f"UCP 600 Art 14(c): Konşimento yükleme tarihi LC 44C değerini aşmaktadır. "
                     f"Bu durum MAJOR DISCREPANCY sebebidir.",
                     "UCP 600 Art 14(c) / Art 20")
        else:
            ekle("Art 20", "Yükleme Tarihi", "MANUEL KONTROL",
                 f"B/L: {bl_tarih_str} | 44C: {alan_44c} — format tanınamadı.",
                 "Tarih formatı standart değil. Muhakeme: veri yok ≠ rezerv. Manuel doğrulama.",
                 "UCP 600 Art 20")
    else:
        eksik = [n for n,v in [("B/L Tarihi",bl_tarih_str),("44C",alan_44c or None)] if not v]
        ekle("Art 20", "Yükleme Tarihi", "MANUEL KONTROL",
             f"Tespit edilemedi: {', '.join(eksik)}",
             "Veri eksikliği tek başına rezerv sebebi değildir. "
             "44C ve B/L tarihi manuel doğrulanmalıdır.",
             "UCP 600 Art 20")

    # ── Art 30: Kilo ──────────────────────────────────────────────────────────
    try:
        if bl_kilo is not None:
            if fat_kilo is not None and abs(fat_kilo - bl_kilo) < 1.0:
                ekle("Art 30", "Kilo (Fatura vs B/L)", "UYUMLU",
                     f"Eşleşti: {fat_kilo:,.2f} KG",
                     f"UCP 600 Art 14(d): Fatura ve konşimento ağırlıkları uyumludur. "
                     f"Çelişki tespit edilmemiştir.",
                     "UCP 600 Art 14(d)")
            elif fat_kilo is None:
                ekle("Art 18", "Kilo (B/L Bilgisi)", "BİLGİ",
                     f"B/L Gross Weight: {bl_kilo:,.2f} KG (Fatura kilo içermiyor — Art 18 zorunlu kılmaz)",
                     f"UCP 600 Art 18 faturada kilo bilgisi zorunlu kılmaz. "
                     f"B/L ağırlığı {bl_kilo:,.2f} KG olarak tespit edildi. "
                     f"Packing List ile karşılaştırma yapılabiliyorsa yeterlidir.",
                     "UCP 600 Art 18")
    except Exception as e:
        ekle("Art 30", "Kilo", "HATA", str(e), "", "UCP 600 Art 30")

    # ── Art 28(f)(ii): Sigorta ────────────────────────────────────────────────
    if incoterm in ["CIF","CIP"]:
        if sigorta_tutari and fatura_tutar and fatura_tutar > 0:
            min_t   = round(fatura_tutar * 1.10, 2)
            sig_t_r = round(sigorta_tutari, 2)
            if _celiski_denetle(sig_t_r, min_t, ">="):
                ekle("Art 28(f)(ii)", "Sigorta Teminatı", "UYUMLU",
                     f"CIF: {fatura_tutar:,.2f} | Minimum (×110%): {min_t:,.2f} | Poliçe: {sig_t_r:,.2f}",
                     f"UCP 600 Art 28(f)(ii) gereği sigorta teminatı CIF/CIP değerinin "
                     f"en az %%110'u olmalıdır. Belgelerde CIF değeri {fatura_tutar:,.2f} "
                     f"ve sigorta teminatı {sig_t_r:,.2f} olarak tespit edilmiştir. "
                     f"Teminat asgari gerekliliği karşıladığından rezerv oluşmamıştır.",
                     "UCP 600 Art 28(f)(ii)",
                     "UCP 600 Text.pdf")
            else:
                ekle("Art 28(f)(ii)", "Sigorta Teminatı — YETERSİZ", "REZERV",
                     f"Poliçe: {sig_t_r:,.2f} < Minimum: {min_t:,.2f}",
                     f"UCP 600 Art 28(f)(ii): CIF ×110% olan {min_t:,.2f} minimum tutarı "
                     f"karşılanmamaktadır. Poliçe: {sig_t_r:,.2f}. MAJOR DISCREPANCY.",
                     "UCP 600 Art 28(f)(ii)")
        elif sigorta_tutari:
            ekle("Art 28(f)(ii)", "Sigorta Teminatı", "MANUEL KONTROL",
                 f"Sigorta: {sigorta_tutari:,.2f} | CIF tespit edilemedi.",
                 "CIF belirlenemediğinden %%110 kontrolü yapılamadı. "
                 "Veri eksikliği rezerv değildir — manuel doğrulama gerekli.",
                 "UCP 600 Art 28(f)(ii)")
        else:
            ekle("Art 28(f)(ii)", "Sigorta Teminatı", "MANUEL KONTROL",
                 "Sigorta tutarı poliçeden tespit edilemedi.",
                 "Art 28(f)(i): Sigorta belgesi teminat tutarını göstermelidir. "
                 "Tutarın okunamaması durumunda manuel inceleme zorunludur. "
                 "Veri eksikliği tek başına rezerv sebebi değildir.",
                 "UCP 600 Art 28(f)(i)")

    # ── Art 16: Rezerv Bildirimi ──────────────────────────────────────────────
    rezervler = [r for r in rapor if r["durum"] == "REZERV"]
    if rezervler:
        ozet = "\n".join(f"  [{r['madde']}] {r['detay']}" for r in rezervler)
        ekle("Art 16", "Rezerv Bildirimi", "UYARI",
             f"Tespit edilen rezerv: {len(rezervler)} adet",
             f"UCP 600 Art 16(c): Banka uygunsuz ibrazı reddetme hakkına sahiptir. "
             f"Ret bildirimi en geç 5. iş günü sonuna kadar yapılmalıdır (Art 16(d)). "
             f"Bildirim ret kararını, her uyumsuzluğu ve belgelerin akıbetini içermelidir.\n\n"
             f"Uyumsuzluklar:\n{ozet}",
             "UCP 600 Art 16(c) / Art 16(d)")

    log.debug("[DEBUG] ucp_kurallari_uygula: %d kayıt.", len(rapor))
    return rapor


# ── Uzman Görüşü ─────────────────────────────────────────────────────────────
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