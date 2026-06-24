"""
hukuk_motoru.py - UCP 600 / ISBP 821 Hukuki Yorum Motoru v10.0
================================================================
Görev:
  - UCP 600 / ISBP 821 referanslı uzman yorumu üret
  - Her kontrol için: SONUÇ + HUKUKİ DEĞERLENDİRME + UCP/ISBP REFERANSI
  - kurallar.json'dan kural metinlerini oku (sabit açıklama YOK)
  - Finansal hesap YAPMAZ, belge parse ETMEZ, analysis_result yorumlar

Export edilenler:
  normalize_tutar()       — paylaşılan normalizer
  mt700_hukuki_yorum()    — MT700 alan yorumları
  ucp_kurallari_uygula()  — UCP kontrol listesi
  uzman_gorusu_uret()     — Rapor sonu hukuki uzman görüşü
  kurallar_yukle()        — kurallar.json loader
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


# ── UCP Kuralları — Her kontrol için uzman yorumu ────────────────────────────
def ucp_kurallari_uygula(parsed: dict[str, Any]) -> list[dict]:
    """
    UCP 600 kontrollerini uygular.
    Her kayıt: { madde, aciklama, durum, detay, hukuki_yorum }
    Yeni hesaplama yapmaz.
    """
    log.debug("[DEBUG] ucp_kurallari_uygula() başladı.")
    rapor: list[dict] = []

    def ekle(madde: str, aciklama: str, durum: str, detay: str, yorum: str = ""):
        # kurallar.json'dan varsa açıklamayı zenginleştir
        json_aciklama = _kural_aciklama(madde)
        tam_yorum = yorum
        if json_aciklama and json_aciklama not in tam_yorum:
            tam_yorum = f"{json_aciklama}\n\n{yorum}".strip() if yorum else json_aciklama
        rapor.append({
            "madde":        madde,
            "aciklama":     aciklama,
            "durum":        durum,
            "detay":        detay,
            "hukuki_yorum": tam_yorum,
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

    # ── Art 14: Belge İnceleme Standardı ─────────────────────────────────────
    ekle("Art 14", "Belge İnceleme Standardı", "BİLGİ",
         "Belgeler yüz değerinden incelendi.",
         "UCP 600 Art 14(a): Banka, belgeler temelinde uygun ibraz olup olmadığını "
         "belirlemek için sunumu inceler. Art 14(b): İnceleme için en fazla 5 iş günü "
         "bulunmaktadır. Art 14(d): Belgeler arasındaki veriler çelişmemelidir; "
         "ancak birebir aynı olmak zorunda değildir.")

    # ── Art 18 / Art 30: Tutar Toleransı ─────────────────────────────────────
    try:
        if fatura_tutar and lc_tutar and lc_tutar > 0:
            about    = any(x in kusat_text.upper() for x in ["ABOUT", "APPROXIMATELY"])
            tolerans = 10 if about else 5
            sapma    = (fatura_tutar - lc_tutar) / lc_tutar * 100
            tolerans_aciklama = "'ABOUT/APPROXIMATELY' nedeniyle %10" if about else "standart %5"
            if abs(sapma) <= tolerans:
                ekle("Art 30", "Tutar Toleransı", "UYUMLU",
                     f"CIF: {fatura_tutar:,.2f} | LC: {lc_tutar:,.2f} | Sapma: %{sapma:+.1f}",
                     f"UCP 600 Art 30(b) gereği akreditif tutarında {tolerans_aciklama} tolerans "
                     f"uygulanır. Fatura CIF değeri {fatura_tutar:,.2f}, LC tutarı {lc_tutar:,.2f} "
                     f"olarak tespit edilmiştir. Sapma %{abs(sapma):.1f} olup tolerans sınırı "
                     f"içinde kaldığından rezerv oluşmamıştır.")
            else:
                ekle("Art 18/30", "Tutar Uyumsuzluğu", "REZERV",
                     f"CIF: {fatura_tutar:,.2f} | LC: {lc_tutar:,.2f} | Sapma: %{sapma:+.1f}",
                     f"UCP 600 Art 18(a)(iii) ve Art 30(b) kapsamında fatura tutarının "
                     f"LC tutarını {tolerans_aciklama} tolerans sınırını aşacak biçimde "
                     f"geçmesi rezerv sebebidir. Sapma %{abs(sapma):.1f} tespit edilmiştir.")
        else:
            eksik = [k for k,v in [("Fatura CIF", fatura_tutar),("LC 32B", lc_tutar)] if not v]
            ekle("Art 30", "Tutar", "MANUEL KONTROL",
                 f"Tespit edilemedi: {', '.join(eksik)}",
                 "UCP 600 Art 30 kapsamındaki tutar kontrolü için fatura CIF ve LC "
                 "32B alanının her ikisi de gereklidir. Manuel doğrulama yapılmalıdır.")
    except Exception as e:
        ekle("Art 30", "Tutar", "HATA", str(e), "")

    # ── Art 27: Temiz Konşimento ──────────────────────────────────────────────
    if konsimento_text:
        kirli = [k for k in KIRLI_BL if k in konsimento_text.upper()]
        if kirli:
            ekle("Art 27", "Temiz Konşimento", "REZERV",
                 f"Kirli ifade tespit edildi: {', '.join(kirli)}",
                 "UCP 600 Art 27: Bankalar yalnızca temiz taşıma belgelerini kabul eder. "
                 "Malın veya ambalajın hasarlı durumunu açıkça belirten kloz veya şerh "
                 "içeren konşimento 'kirli' sayılır ve ret sebebidir.")
        else:
            ekle("Art 27", "Temiz Konşimento", "UYUMLU",
                 "Olumsuz kloz veya hasar şerhi tespit edilmedi.",
                 "UCP 600 Art 27: Konşimentoda malın veya ambalajın hasarlı durumunu "
                 "belirten herhangi bir kloz veya şerh bulunmamaktadır. "
                 "Belge temiz konşimento niteliğini taşımaktadır.")

    # ── Art 20: Shipped on Board ──────────────────────────────────────────────
    if konsimento_text:
        bl_u = konsimento_text.upper()
        if "SHIPPED ON BOARD" in bl_u or "ON BOARD" in bl_u:
            ekle("Art 20", "Shipped on Board Şerhi", "UYUMLU",
                 "On Board şerhi konşimentoda mevcut.",
                 "UCP 600 Art 20(a)(ii): Konşimenton malların gemiye yüklendiğini "
                 "'Shipped on Board' şerhi veya ön baskı ile göstermesi zorunludur. "
                 "Yükleme tarihi bu şerhin tarihi sayılır.")
        else:
            ekle("Art 20", "Shipped on Board Şerhi", "REZERV",
                 "On Board şerhi konşimentoda bulunamadı.",
                 "UCP 600 Art 20(a)(ii): Konşimentoda malların gemiye yüklendiğine dair "
                 "'Shipped on Board' şerhi veya tarihi bulunmamaktadır. "
                 "Bu eksiklik doğrudan ret sebebidir.")

    # ── Art 20 / 44C: Yükleme Tarihi ─────────────────────────────────────────
    if bl_tarih_str and alan_44c:
        bl_dt = _tarih(bl_tarih_str)
        lc_dt = _tarih(alan_44c)
        if bl_dt and lc_dt:
            if bl_dt <= lc_dt:
                ekle("Art 20", "Yükleme Tarihi", "UYUMLU",
                     f"B/L On Board: {bl_tarih_str} ≤ 44C Son Yükleme: {alan_44c}",
                     f"UCP 600 Art 14(c) ve Art 20(a)(ii) kapsamında konşimentodaki "
                     f"yükleme tarihi ({bl_tarih_str}), LC'nin 44C alanında belirtilen "
                     f"son yükleme tarihi ({alan_44c}) ile uyumludur. "
                     f"Geç yükleme rezervi oluşmamıştır.")
            else:
                ekle("Art 20", "Yükleme Tarihi — GEÇ YÜKLEME", "REZERV",
                     f"B/L: {bl_tarih_str} > 44C: {alan_44c}",
                     f"UCP 600 Art 14(c): Konşimentodaki yükleme tarihi ({bl_tarih_str}), "
                     f"LC 44C alanındaki son yükleme tarihini ({alan_44c}) aşmaktadır. "
                     f"Bu durum MAJOR DISCREPANCY sebebidir ve akreditif değişikliği "
                     f"yapılmadan belge kabul edilemez.")
        else:
            ekle("Art 20", "Yükleme Tarihi", "MANUEL KONTROL",
                 f"B/L: {bl_tarih_str} | 44C: {alan_44c} — Tarih formatı tanınamadı.",
                 "Yükleme tarihi karşılaştırması için tarih formatı standart değil. "
                 "Manuel doğrulama gereklidir.")
    else:
        eksik = [n for n,v in [("B/L Tarihi", bl_tarih_str), ("44C", alan_44c or None)] if not v]
        ekle("Art 20", "Yükleme Tarihi", "MANUEL KONTROL",
             f"Tespit edilemedi: {', '.join(eksik)}",
             "UCP 600 Art 20 kapsamındaki yükleme tarihi kontrolü için konşimendo "
             "On Board tarihi ve LC 44C alanı gereklidir. Manuel doğrulama yapılmalıdır.")

    # ── Art 30: Kilo Karşılaştırması ──────────────────────────────────────────
    try:
        if fat_kilo and bl_kilo:
            fark = abs(fat_kilo - bl_kilo)
            if fark < 1.0:
                ekle("Art 30", "Kilo Uyumu (Fatura vs B/L)", "UYUMLU",
                     f"Eşleşti: {fat_kilo:,.2f} KG",
                     f"UCP 600 Art 14(d) kapsamında fatura ({fat_kilo:,.2f} KG) ile "
                     f"konşimento ({bl_kilo:,.2f} KG) ağırlık bilgileri uyumludur. "
                     f"Belgeler arasında çelişki tespit edilmemiştir.")
            else:
                ekle("Art 30", "Kilo Uyumsuzluğu (Fatura vs B/L)", "REZERV",
                     f"Fatura: {fat_kilo:,.2f} KG | B/L: {bl_kilo:,.2f} KG | Fark: {fark:,.2f} KG",
                     f"UCP 600 Art 14(d): Fatura ve konşimento arasındaki ağırlık farkı "
                     f"{fark:,.2f} KG olup bu veri çelişkisi rezerv sebebidir.")
        else:
            eksik = [n for n,v in [("Fatura Kilo",fat_kilo),("B/L Kilo",bl_kilo)] if not v]
            ekle("Art 30", "Kilo", "MANUEL KONTROL",
                 f"Tespit edilemedi: {', '.join(eksik)}",
                 "Ağırlık karşılaştırması yapılamadı. Belgelerde kilo bilgisi "
                 "farklı formatta veya eksik olabilir.")
    except Exception as e:
        ekle("Art 30", "Kilo", "HATA", str(e), "")

    # ── Art 28(f)(ii): Sigorta Teminatı ──────────────────────────────────────
    if incoterm in ["CIF", "CIP"]:
        if sigorta_tutari and fatura_tutar and fatura_tutar > 0:
            min_t   = round(fatura_tutar * 1.10, 2)
            sig_t_r = round(sigorta_tutari, 2)
            if _celiski_denetle(sig_t_r, min_t, ">="):
                ekle("Art 28(f)(ii)", "Sigorta Teminatı", "UYUMLU",
                     f"CIF: {fatura_tutar:,.2f} | Min (×110%): {min_t:,.2f} | Poliçe: {sig_t_r:,.2f}",
                     f"UCP 600 Art 28(f)(ii) gereği akreditifte farklı bir oran "
                     f"belirtilmemişse sigorta teminatı CIF/CIP değerinin en az "
                     f"%%110'u olmalıdır. Belgelerde CIF değerinin {fatura_tutar:,.2f} "
                     f"ve sigorta teminatının {sig_t_r:,.2f} olduğu görülmüştür. "
                     f"Teminat tutarı asgari gerekliliği karşıladığından "
                     f"rezerv oluşmamıştır.")
            else:
                ekle("Art 28(f)(ii)", "Sigorta Teminatı — YETERSİZ", "REZERV",
                     f"Poliçe: {sig_t_r:,.2f} < Min: {min_t:,.2f}",
                     f"UCP 600 Art 28(f)(ii): Sigorta teminatı CIF değerinin %%110'u "
                     f"olan {min_t:,.2f} minimum tutarını karşılamamaktadır. "
                     f"Poliçe tutarı {sig_t_r:,.2f} olarak tespit edilmiştir. "
                     f"Bu eksiklik MAJOR DISCREPANCY sebebidir.")
        elif sigorta_tutari:
            ekle("Art 28(f)(ii)", "Sigorta Teminatı", "MANUEL KONTROL",
                 f"Sigorta: {sigorta_tutari:,.2f} | CIF tutarı tespit edilemedi.",
                 "CIF tutarı belirlenemediğinden %%110 hesabı yapılamıyor. "
                 "Manuel doğrulama gereklidir.")
        else:
            ekle("Art 28(f)(ii)", "Sigorta Teminatı", "MANUEL KONTROL",
                 "Sigorta tutarı poliçeden tespit edilemedi.",
                 "UCP 600 Art 28(f)(i): Sigorta belgesi sigorta teminat tutarını "
                 "göstermelidir. Tutarın okunamadığı durumlarda manuel inceleme zorunludur.")

    # ── Art 16: Rezerv Bildirimi ──────────────────────────────────────────────
    rezervler = [r for r in rapor if r["durum"] == "REZERV"]
    if rezervler:
        ozet = "\n".join(f"  - [{r['madde']}] {r['detay']}" for r in rezervler)
        ekle("Art 16", "Rezerv Bildirimi", "UYARI",
             f"Tespit edilen rezerv sayısı: {len(rezervler)}",
             f"UCP 600 Art 16(c): Banka uygunsuz ibrazı reddetme hakkına sahiptir. "
             f"Ret bildirimi en geç 5. iş günü sonuna kadar (Art 16(d)) yapılmalıdır. "
             f"Ret bildirimi şunları içermelidir: reddetme kararı, her bir uyumsuzluk "
             f"ve belgelerin akıbeti (iade, bekleme veya uygulamacı talimatı).\n\n"
             f"Tespit edilen uyumsuzluklar:\n{ozet}")

    log.debug("[DEBUG] ucp_kurallari_uygula: %d kayıt.", len(rapor))
    return rapor


# ── Hukuki Uzman Görüşü ──────────────────────────────────────────────────────
def uzman_gorusu_uret(parsed: dict[str, Any], ucp_sonuclari: list[dict]) -> str:
    """
    Rapor sonu için UCP 600 referanslı hukuki uzman görüşü üretir.
    Tek bir metin string döner — raporda "HUKUKİ UZMAN GÖRÜŞÜ" bölümünde kullanılır.
    """
    rezervler   = [r for r in ucp_sonuclari if r.get("durum") == "REZERV"]
    major_sayisi = len(rezervler)
    incoterm     = parsed.get("incoterm", "")
    fatura_tutar = parsed.get("fatura_tutar")
    lc_tutar     = parsed.get("lc_tutar")
    sigorta_t    = parsed.get("sigorta_tutari")
    bl_tarih_str = parsed.get("bl_tarih_str")
    alan_44c     = parsed.get("alan_44c", "")
    lc_no        = parsed.get("lc_no", "")

    satirlar = []
    tarih_str = datetime.now().strftime("%d.%m.%Y")

    satirlar.append(f"Değerlendirme Tarihi: {tarih_str}")
    if lc_no and lc_no != "Tespit edilemedi":
        satirlar.append(f"LC Referans: {lc_no}")
    satirlar.append("")

    # Genel değerlendirme
    if major_sayisi == 0:
        satirlar.append(
            "Bu ibraz dosyasında UCP 600 kapsamında kritik rezerv tespit edilmemiştir. "
            "Art 14(a) kapsamında yapılan belge uyumluluk incelemesinde belgeler arasında "
            "esaslı çelişki görülmemiştir."
        )
    else:
        satirlar.append(
            f"Bu ibraz dosyasında UCP 600 kapsamında {major_sayisi} adet uyumsuzluk "
            f"tespit edilmiştir. Art 16(c) uyarınca banka ret bildirimi yapma hakkına "
            f"sahip olup bildirim en geç 5. iş günü sonuna kadar yapılmalıdır."
        )
    satirlar.append("")

    # Sigorta
    if incoterm in ["CIF", "CIP"] and fatura_tutar and sigorta_t:
        min_t   = round(fatura_tutar * 1.10, 2)
        sig_t_r = round(sigorta_t, 2)
        if _celiski_denetle(sig_t_r, min_t, ">="):
            satirlar.append(
                f"Sigorta teminatı Art 28(f)(ii) gerekliliklerini karşılamaktadır. "
                f"CIF değeri {fatura_tutar:,.2f}, minimum sigorta tutarı {min_t:,.2f}, "
                f"ibraz edilen poliçe tutarı {sig_t_r:,.2f} olarak belirlenmiştir."
            )
        else:
            satirlar.append(
                f"Sigorta teminatı Art 28(f)(ii) gerekliliklerini karşılamamaktadır. "
                f"Minimum {min_t:,.2f} tutarında teminat gerekli; poliçe {sig_t_r:,.2f}."
            )
        satirlar.append("")

    # Tutar
    if fatura_tutar and lc_tutar:
        sapma = abs((fatura_tutar - lc_tutar) / lc_tutar * 100)
        if sapma <= 5:
            satirlar.append(
                f"Fatura CIF tutarı ({fatura_tutar:,.2f}) ile LC tutarı ({lc_tutar:,.2f}) "
                f"arasındaki sapma %{sapma:.1f} olup Art 30 tolerans sınırı içindedir."
            )
            satirlar.append("")

    # MT700 eksikliği uyarısı
    mt700 = parsed.get("mt700_alanlari", {})
    if not mt700.get("44C") or not mt700.get("46A"):
        eksik_alanlar = [a for a in ["44C", "46A"] if not mt700.get(a)]
        satirlar.append(
            f"MT700 metninden {', '.join(eksik_alanlar)} alanları tespit edilemediğinden "
            f"bu alanlara ilişkin kontroller manuel doğrulanmalıdır."
        )
        satirlar.append("")

    # Genel kanaat
    banka_kabul = parsed.get("banka_kabul", 100)
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
    satirlar.append(kanaat)

    # Yasal uyarı
    satirlar.append("")
    satirlar.append(
        "Bu rapor bilgilendirme amaçlıdır. Kesin hukuki görüş için akreditif uzmanına "
        "danışılması tavsiye edilir. UCP 600, ICC tarafından yayımlanmış özel sektör "
        "kurallarıdır; uygulanabilirliği akreditif metninde açıkça belirtilmiş olmasına bağlıdır."
    )

    return "\n".join(satirlar)


def analiz_et(depo: dict) -> list:
    """Kullanım dışı — geriye dönük uyumluluk."""
    log.warning("analiz_et() deprecated. ucp_kurallari_uygula() kullanın.")
    return []
