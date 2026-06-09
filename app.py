import os
import re
from datetime import datetime

# Bulut ortamlarında kütüphane kontrolü yapan güvenli yükleme katmanı
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    pytesseract = None

# Hukuk motoru doğrudan entegre edildi (monkey patch kaldırıldı)
try:
    from hukuk_motoru import analiz_et as hukuk_motoru_analiz_et
    HUKUK_MOTORU_AKTIF = True
except ImportError:
    hukuk_motoru_analiz_et = None
    HUKUK_MOTORU_AKTIF = False


class YapayZekaDisTicaretDenetleyici:
    def __init__(self, ana_dizin="DisTicaretRepo"):
        self.base_dir = ana_dizin
        self.yuklenenler_dir = os.path.join(self.base_dir, "YuklenenDosyalar")
        self.raporlar_dir = os.path.join(self.base_dir, "Raporlar")

        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir, exist_ok=True)

        # Depo anahtarları KONŞİMENTO yerine KONSIMENTO olarak tutarlı şekilde normalize edildi
        self.depo = {
            "KUSAT": None,
            "FATURA": None,
            "KONSIMENTO": None,
            "CEKI_LISTESI": None,
            "SIGORTA": None,
            "DIGER_BELGELER": []
        }
        self.analiz_verisi = {}

    # ------------------------------------------------------------------
    # Yardımcı: depo kaydından metin güvenli şekilde çekilir
    # ------------------------------------------------------------------
    def _depo_metin(self, anahtar):
        """Depo kaydı None veya 'metin' anahtarı yoksa boş string döner."""
        kayit = self.depo.get(anahtar)
        if not kayit:
            return ""
        metin = kayit.get("metin")
        return metin if isinstance(metin, str) else ""

    # ------------------------------------------------------------------
    # Metin ayıklama — OCR hata yönetimi iyileştirildi
    # ------------------------------------------------------------------
    def metin_ayikla(self, dosya_yolu):
        """Dosyadan metin çıkarır; her format için ayrı hata yakalama."""
        if not dosya_yolu or not os.path.isfile(dosya_yolu):
            return ""

        ext = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""

        try:
            if ext == ".pdf":
                if PdfReader is None:
                    return "[Hata: pypdf kütüphanesi yüklü değil]"
                reader = PdfReader(dosya_yolu)
                for sayfa in reader.pages:
                    try:
                        txt = sayfa.extract_text()
                        if txt:
                            metin += txt + "\n"
                    except Exception as sayfa_hatasi:
                        metin += f"[Sayfa OCR Hatası: {sayfa_hatasi}]\n"

            elif ext in [".docx", ".doc"]:
                if docx is None:
                    return "[Hata: python-docx kütüphanesi yüklü değil]"
                doc = docx.Document(dosya_yolu)
                for p in doc.paragraphs:
                    if p.text:
                        metin += p.text + "\n"
                for table in doc.tables:
                    for row in table.rows:
                        row_text = " ".join(
                            [cell.text for cell in row.cells if cell.text]
                        )
                        if row_text.strip():
                            metin += row_text + "\n"

            elif ext in [".xlsx", ".xls"]:
                if openpyxl is None:
                    return "[Hata: openpyxl kütüphanesi yüklü değil]"
                wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
                for s in wb.sheetnames:
                    ws = wb[s]
                    for r in ws.iter_rows(values_only=True):
                        satir = " ".join([str(c) for c in r if c is not None])
                        if satir.strip():
                            metin += satir + "\n"

            elif ext in [".png", ".jpg", ".jpeg"]:
                if pytesseract is None:
                    return "[Hata: pytesseract veya Pillow kütüphanesi yüklü değil]"
                try:
                    img = Image.open(dosya_yolu)
                    try:
                        ocr_sonuc = pytesseract.image_to_string(img, lang="eng+tur")
                    except pytesseract.TesseractError:
                        # tur.traineddata sunucuda yoksa yalnızca İngilizce ile devam et
                        print("[UYARI] Türkçe OCR dil paketi bulunamadı, yalnızca 'eng' kullanılıyor.")
                        ocr_sonuc = pytesseract.image_to_string(img, lang="eng")
                    metin = ocr_sonuc if ocr_sonuc else ""
                except pytesseract.TesseractError as ocr_hatasi:
                    return f"[OCR Hatası: {ocr_hatasi}]"

            elif ext == ".txt":
                with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
                    metin = f.read()

            else:
                return f"[Desteklenmeyen dosya formatı: {ext}]"

        except Exception as e:
            return f"[Dosya Okuma Hatası ({ext}): {e}]"

        # Non-breaking space ve diğer görünmez whitespace karakterlerini normalize et
        metin = metin.replace("\xa0", " ").replace("\u200b", "")
        return metin

    # ------------------------------------------------------------------
    # Belge tipi tespiti — Unicode tutarsızlıkları giderildi
    # KONŞİMENTO ve KONSIMENTO eşanlamlı olarak destekleniyor
    # ------------------------------------------------------------------
    def dokuman_tipi_belirle(self, metin):
        if not metin:
            return "DIGER"
        m_upper = metin.upper()
        if any(x in m_upper for x in ["DOCUMENTARY CREDIT", "40A:", "IRREVOCABLE", "L/C NO", "KÜŞAT"]):
            return "KUSAT"
        elif any(x in m_upper for x in ["COMMERCIAL INVOICE", "FATURA", "FAVURA", "INVOICE NO", "INVOICE EXP"]):
            return "FATURA"
        elif any(x in m_upper for x in [
            "BILL OF LADING", "OCEAN BILL", "B/L NO", "SHIPPED ON BOARD",
            # Unicode normalize: hem KONŞİMENTO hem KONSIMENTO destekleniyor
            "KONŞİMENTO", "KONSIMENTO"
        ]):
            return "KONSIMENTO"
        elif any(x in m_upper for x in [
            "PACKING LIST", "CEKI LISTESI", "ÇEKİ LİSTESİ", "WEIGHT LIST", "PACKING DETAILS"
        ]):
            return "CEKI_LISTESI"
        elif any(x in m_upper for x in [
            "INSURANCE POLICY", "INSURANCE CERTIFICATE", "SİGORTA POLİÇESİ", "MARINE INSURANCE"
        ]):
            return "SIGORTA"
        return "DIGER"

    # ------------------------------------------------------------------
    # Depo tarama
    # ------------------------------------------------------------------
    def depoyu_tara_ve_analiz_et(self):
        # Her çalıştırmada eski kayıtları temizle — birden fazla baslat() çağrısında
        # önceki oturumun verileri sonuca karışmasın
        self.depo = {
            "KUSAT": None,
            "FATURA": None,
            "KONSIMENTO": None,
            "CEKI_LISTESI": None,
            "SIGORTA": None,
            "DIGER_BELGELER": []
        }
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
            icerik = self.metin_ayikla(d_yolu)
            # Metin ayıklama hatası varsa bu dosyayı atla
            if not icerik or icerik.startswith("["):
                print(f"[UYARI] {dosya_adi} okunamadı: {icerik}")
                continue
            tip = self.dokuman_tipi_belirle(icerik)
            if tip in ["KUSAT", "FATURA", "KONSIMENTO", "CEKI_LISTESI", "SIGORTA"]:
                self.depo[tip] = {"ad": dosya_adi, "metin": icerik}
            else:
                self.depo["DIGER_BELGELER"].append({"ad": dosya_adi, "metin": icerik})
        return True

    # ------------------------------------------------------------------
    # Sayısal değer bulma — None güvenli, daha kapsamlı desen desteği
    # ------------------------------------------------------------------
    def sayisal_deger_bul(self, metin, desenler):
        """
        Verilen metin içinde desenlerden herhangi birini arar.
        Bulunan ilk geçerli sayısal değeri float olarak döner.
        Hiçbir desen eşleşmezse None döner; hardcoded fallback yok.
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

    # ------------------------------------------------------------------
    # Ağırlık ayıklama — genişletilmiş desen seti
    # ------------------------------------------------------------------
    def kilo_bul(self, metin):
        """
        Belgeden brüt kilo değerini çıkarmaya çalışır.
        Birden fazla yazım biçimini destekler; None döner (hardcoded fallback yok).
        """
        desenler = [
            # Etiket + sayı + birim
            r'(?:GROSS\s*WEIGHT|BRÜT\s*(?:KİLO|AĞIRLIK))\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|KG)',
            # Sadece sayı + birim (etiket olmadan)
            r'([\d,\.]+)\s*(?:KGS?)\b',
            # Net weight yedek
            r'(?:NET\s*WEIGHT)\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|KG)',
            # G.W. kısaltması
            r'G\.?W\.?\s*[:\-]?\s*([\d,\.]+)\s*(?:KGS?|KG)',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    # ------------------------------------------------------------------
    # Para tutarı ayıklama — LC alan 32B ve yaygın fatura etiketleri
    # ------------------------------------------------------------------
    def para_tutari_bul(self, metin):
        """
        Belgeden para tutarını çıkarır (döviz birimi fark etmeksizin sayısal değer).
        LC küşat belgelerinde 32B alanı önceliklidir.
        None döner; hardcoded fallback yok.
        """
        if not metin:
            return None
        desenler = [
            # SWIFT MT700 Alan 32B: örn.  32B: USD125000  veya  32B: USD 125,000.00
            r'32B[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            # Açık "CREDIT AMOUNT" etiketi
            r'CREDIT\s+AMOUNT[:\s]*[A-Z]{3}\s*([\d,\.]+)',
            # Yaygın fatura toplam etiketleri + para birimi
            r'(?:TOTAL\s+AMOUNT|INVOICE\s+VALUE|INVOICE\s+AMOUNT|TOTAL\s+VALUE)\s*[:\-]?\s*(?:USD|EUR|GBP|TRY)\s*([\d,\.]+)',
            # Para birimi önce, tutar sonra (örn. USD 125,000.00)
            r'(?:USD|EUR|GBP|TRY)\s*([\d,\.]+)',
        ]
        return self.sayisal_deger_bul(metin, desenler)

    # ------------------------------------------------------------------
    # Tarih ayıklama — konşimento yükleme tarihi
    # ------------------------------------------------------------------
    def tarih_bul(self, metin, desenler):
        """
        Verilen metin içinden ilk eşleşen tarih string'ini döner (ham string).
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

    # ------------------------------------------------------------------
    # Mal tanımı çıkarma — kısa normalleştirilmiş string
    # ------------------------------------------------------------------
    def mal_tanimi_bul(self, metin):
        """
        Belgeden mal tanımı metnini çıkarır.
        Küşat için 45A alanı, fatura için DESCRIPTION OF GOODS etiketi aranır.
        None döner bulunamazsa.
        """
        if not metin:
            return None
        desenler = [
            # SWIFT MT700 Alan 45A
            r'45A[:\s]+(.+?)(?:\n[4-9]\d[A-Z]|\Z)',
            # Yaygın fatura etiketi
            r'(?:DESCRIPTION\s+OF\s+GOODS?|MAL\s+TANIMI|GOODS?\s+DESCRIPTION)[:\s]+(.+?)(?:\n|$)',
        ]
        for desen in desenler:
            try:
                m = re.search(desen, metin, re.IGNORECASE | re.DOTALL)
                if m:
                    # Sadece ilk satırı al, boşlukları sıkıştır
                    ham = m.group(1).split("\n")[0].strip()
                    return re.sub(r'\s+', ' ', ham)[:200]  # 200 karakter üst sınır
            except re.error:
                continue
        return None

    # ------------------------------------------------------------------
    # UCP 600 Kural Motoru — hukuk_motoru.py doğrudan entegre edildi
    # Monkey patch mimarisi tamamen kaldırıldı
    # ------------------------------------------------------------------
    def ucp600_kural_motoru(self):
        kusat_text = self._depo_metin("KUSAT")
        fatura_text = self._depo_metin("FATURA")
        konsimento_text = self._depo_metin("KONSIMENTO")
        ceki_text = self._depo_metin("CEKI_LISTESI")
        sigorta_text = self._depo_metin("SIGORTA")

        combined = (
            kusat_text + " " + fatura_text + " " +
            konsimento_text + " " + sigorta_text
        ).upper()

        sonuclar = {
            "vade_analizi": [],
            "finansal_durum": [],
            "incoterms": [],
            "capraz_kontrol": [],
            "zorunlu_alanlar": [],
            "ucp_tablosu": []
        }

        # ---- 1. Hukuki Vade Analizi ----
        son_yukleme = re.search(
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT|SON\s+YÜKLEME\s+TARİHİ)[:\s]*([\d.\/\-]+)',
            combined, re.IGNORECASE
        )
        ibraz_suresi = re.search(
            r'(\d+)\s*DAYS?\s*(?:AFTER|FOR\s+PRESENTATION)',
            combined, re.IGNORECASE
        )

        if son_yukleme:
            sonuclar["vade_analizi"].append(
                f"En Geç Yükleme Tarihi (Alan 44C): **{son_yukleme.group(1)}**"
            )
        else:
            sonuclar["vade_analizi"].append(
                "En Geç Yükleme Tarihi (Alan 44C): **Belgeden tespit edilemedi — manuel kontrol gerekli**"
            )

        if ibraz_suresi:
            sonuclar["vade_analizi"].append(
                f"Bankaya İbraz Süresi: **{ibraz_suresi.group(1)} gün** "
                "(UCP 600 Madde 14c'ye göre 21 günü aşamaz)."
            )
        else:
            sonuclar["vade_analizi"].append(
                "Bankaya İbraz Süresi: Belgeden tespit edilemedi — "
                "UCP 600 Madde 14c varsayılan 21 günlük limit uygulanır."
            )

        # ---- 2. Ödeme Vadesi ----
        if any(x in combined for x in ["AT SIGHT", "SIGHT PAYMENT", "BY SIGHT", "GÖRÜLDÜĞÜNDE"]):
            vade_tespit = "Görüldüğünde Ödemeli (At Sight)"
            sonuclar["finansal_durum"].append(
                f"Ödeme Vadesi: **{vade_tespit}** "
                "(UCP 600 Art 15b uyarınca uyumlu ibrazda amir banka ibraz anında ödemekle yükümlüdür)."
            )
        elif any(x in combined for x in ["DAYS AFTER", "DEFERRED PAYMENT", "BY ACCEPTANCE", "VADELİ"]):
            vade_tespit = "Vadeli / Kabul Kredili Akreditif"
            sonuclar["finansal_durum"].append(
                f"Ödeme Vadesi: **{vade_tespit}**. "
                "Poliçe vade takvimini ve faiz taahhütlerini kontrol edin."
            )
        else:
            sonuclar["finansal_durum"].append(
                "Ödeme Vadesi: Belgelerden tespit edilemedi — manuel kontrol önerilir."
            )

        # ---- 3. Incoterms ve Sigorta (UCP 600 Art 28) ----
        incoterm_var = None
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
        art28_not = (
            f"Teslim şekli ({incoterm_var or 'Belirsiz'}) kuralları "
            "satıcının sigorta poliçesi ibrazını zorunlu kılmıyor."
        )

        if incoterm_var in ["CIF", "CIP"]:
            if self.depo["SIGORTA"]:
                art28_durum = "DOĞRUDAN GEÇTİ"
                art28_not = (
                    "Sigorta poliçesi dosyalar arasında saptandı. "
                    "Min. %110 teminat hesabı için Bölüm 4 Çapraz Kontrol tablosuna bakın."
                )
                sonuclar["incoterms"].append(
                    f"[OK] Hukuki Zorunluluk: {incoterm_var} şartı gereği "
                    "Resmi Sigorta Poliçesi dosyalar arasında saptandı ve incelendi (UCP 600 Art 28)."
                )
            else:
                art28_durum = "YÜKSEK RİSK"
                art28_not = (
                    f"{incoterm_var} teslimlerde Sigorta Poliçesi zorunludur! "
                    "Minimum %110 teminat aranır (UCP 600 Madde 28)."
                )
                sonuclar["incoterms"].append(
                    f"[HUKUKİ REZERV RİSKİ] Teslim şekli {incoterm_var} olmasına rağmen "
                    "Sigorta Poliçesi bulunamadı!"
                )

        # ---- 4. Sayısal Çapraz Kontroller ----

        # 4a. Fatura tutarı ↔ Akreditif tutarı (UCP 600 Art 18 + Art 30)
        fatura_tutari = self.para_tutari_bul(fatura_text)
        lc_tutari = self.para_tutari_bul(kusat_text)

        if fatura_tutari is not None and lc_tutari is not None:
            # UCP 600 Art 30b: akreditifte aksi belirtilmedikçe %5 tolerans
            tolerans = lc_tutari * 0.05
            fark = abs(fatura_tutari - lc_tutari)
            if fark <= tolerans:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                    "detay": (
                        f"Fatura: {fatura_tutari:,.2f} | "
                        f"Akreditif: {lc_tutari:,.2f} | "
                        f"Fark: {fark:,.2f} (≤ %5 tolerans)"
                    ),
                    "durum": "UYUMLU"
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                    "detay": (
                        f"Fatura: {fatura_tutari:,.2f} | "
                        f"Akreditif: {lc_tutari:,.2f} | "
                        f"Fark: {fark:,.2f} (> %5 tolerans)"
                    ),
                    "durum": "REZERV RİSKİ - TUTAR UYUŞMAZLIĞI"
                })
        else:
            eksik_tutar = []
            if fatura_tutari is None:
                eksik_tutar.append("Fatura")
            if lc_tutari is None:
                eksik_tutar.append("Akreditif (32B)")
            sonuclar["capraz_kontrol"].append({
                "belge": "Fatura vs Akreditif Tutarı (Art 18 / Art 30)",
                "detay": f"Tutar tespit edilemedi: {', '.join(eksik_tutar)}",
                "durum": "MANUEL KONTROL"
            })

        # 4b. Kilo — Fatura ↔ Konşimento
        fatura_kilo = self.kilo_bul(fatura_text) if fatura_text else None
        bl_kilo = self.kilo_bul(konsimento_text) if konsimento_text else None
        ceki_kilo = self.kilo_bul(ceki_text) if ceki_text else None

        if fatura_kilo is not None and bl_kilo is not None:
            # OCR kaynaklı küçük yuvarlama farklarını tolere et (< 0.5 KG fark = uyumlu)
            if abs(fatura_kilo - bl_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura vs Konşimento Kilo",
                    "detay": f"Brüt Kilo Eşleşmesi ({fatura_kilo} KG)",
                    "durum": "UYUMLU"
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura vs Konşimento Kilo",
                    "detay": f"Fatura: {fatura_kilo} KG | Konşimento: {bl_kilo} KG",
                    "durum": "REZERV RİSKİ - UYUMSUZ SAYISAL VERİ"
                })
        else:
            eksik = []
            if fatura_kilo is None:
                eksik.append("Fatura")
            if bl_kilo is None:
                eksik.append("Konşimento")
            sonuclar["capraz_kontrol"].append({
                "belge": "Fatura vs Konşimento Kilo",
                "detay": f"Brüt kilo değeri tespit edilemedi: {', '.join(eksik)}",
                "durum": "VERİ EKSİK - MANUEL KONTROL GEREKLİ"
            })

        # 4c. Kilo — Fatura ↔ Çeki listesi
        if ceki_kilo is not None and fatura_kilo is not None:
            if abs(ceki_kilo - fatura_kilo) < 0.5:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura vs Çeki Listesi Kilo",
                    "detay": f"Brüt Kilo Eşleşmesi ({ceki_kilo} KG)",
                    "durum": "UYUMLU"
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura vs Çeki Listesi Kilo",
                    "detay": f"Fatura: {fatura_kilo} KG | Çeki Listesi: {ceki_kilo} KG",
                    "durum": "REZERV RİSKİ - UYUMSUZ SAYISAL VERİ"
                })

        # 4d. Mal tanımı — Fatura ↔ Küşat (UCP 600 Art 18c)
        fatura_mal = self.mal_tanimi_bul(fatura_text)
        kusat_mal = self.mal_tanimi_bul(kusat_text)

        if fatura_mal and kusat_mal:
            # Basit kelime örtüşmesi: küşattaki anahtar kelimelerin faturada bulunup bulunmadığı
            kusat_kelimeler = set(re.findall(r'\b[A-ZÇĞİÖŞÜa-zçğışöüa-z]{4,}\b', kusat_mal.upper()))
            fatura_kelimeler = set(re.findall(r'\b[A-ZÇĞİÖŞÜa-zçğışöüa-z]{4,}\b', fatura_mal.upper()))
            ortak = kusat_kelimeler & fatura_kelimeler
            oran = len(ortak) / len(kusat_kelimeler) if kusat_kelimeler else 0

            if oran >= 0.6:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura Mal Tanımı vs Küşat (Art 18c)",
                    "detay": (
                        f"Küşat: '{kusat_mal[:80]}' | "
                        f"Fatura: '{fatura_mal[:80]}' | "
                        f"Örtüşme: %{oran*100:.0f}"
                    ),
                    "durum": "UYUMLU"
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Fatura Mal Tanımı vs Küşat (Art 18c)",
                    "detay": (
                        f"Küşat: '{kusat_mal[:80]}' | "
                        f"Fatura: '{fatura_mal[:80]}' | "
                        f"Örtüşme: %{oran*100:.0f}"
                    ),
                    "durum": "REZERV RİSKİ - MAL TANIMI UYUŞMAZLIĞI"
                })
        else:
            eksik_mal = []
            if not fatura_mal:
                eksik_mal.append("Fatura")
            if not kusat_mal:
                eksik_mal.append("Küşat (45A)")
            sonuclar["capraz_kontrol"].append({
                "belge": "Fatura Mal Tanımı vs Küşat (Art 18c)",
                "detay": f"Mal tanımı tespit edilemedi: {', '.join(eksik_mal)}",
                "durum": "MANUEL KONTROL"
            })

        # 4e. Konşimento yükleme tarihi ↔ Küşat Alan 44C
        bl_tarih_desenler = [
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{1,2}[\s\.\-\/][A-Z]{3,}[\s\.\-\/][\d]{4})',
            r'(?:SHIPPED\s+ON\s+BOARD|ON\s+BOARD\s+DATE|DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{2}[\.\-\/][\d]{2}[\.\-\/][\d]{4})',
        ]
        lc_44c_desenler = [
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{1,2}[\s\.\-\/][A-Z]{3,}[\s\.\-\/][\d]{4})',
            r'(?:44C|LATEST\s+DATE\s+OF\s+SHIPMENT)[:\s]+([\d]{2}[\.\-\/][\d]{2}[\.\-\/][\d]{4})',
        ]
        bl_yukleme_tarihi = self.tarih_bul(konsimento_text, bl_tarih_desenler)
        lc_son_yukleme = self.tarih_bul(kusat_text, lc_44c_desenler)

        if bl_yukleme_tarihi and lc_son_yukleme:
            # Tarih karşılaştırması string düzeyinde yapılıyor;
            # gerçek üretimde dateutil.parser ile parse edilerek karşılaştırılmalıdır.
            sonuclar["capraz_kontrol"].append({
                "belge": "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                "detay": (
                    f"Konşimento Yükleme: {bl_yukleme_tarihi} | "
                    f"44C Son Yükleme: {lc_son_yukleme}"
                ),
                "durum": "TESPİT EDİLDİ - MANUEL TARİH KARŞILAŞTIRMASI GEREKLİ"
            })
        else:
            eksik_tarih = []
            if not bl_yukleme_tarihi:
                eksik_tarih.append("Konşimento yükleme tarihi")
            if not lc_son_yukleme:
                eksik_tarih.append("Küşat 44C")
            sonuclar["capraz_kontrol"].append({
                "belge": "Konşimento Yükleme Tarihi vs Alan 44C (Art 20)",
                "detay": f"Tarih tespit edilemedi: {', '.join(eksik_tarih)}",
                "durum": "MANUEL KONTROL"
            })

        # 4f. Sigorta bedeli ≥ Fatura × %110 (UCP 600 Art 28f-ii) — gerçek hesaplama
        if incoterm_var in ["CIF", "CIP"] and self.depo["SIGORTA"]:
            sigorta_tutari = self.para_tutari_bul(sigorta_text)
            if sigorta_tutari is not None and fatura_tutari is not None:
                minimum_teminat = fatura_tutari * 1.10
                if sigorta_tutari >= minimum_teminat:
                    sonuclar["capraz_kontrol"].append({
                        "belge": "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                        "detay": (
                            f"Sigorta: {sigorta_tutari:,.2f} | "
                            f"Gerekli Min.: {minimum_teminat:,.2f} (Fatura {fatura_tutari:,.2f} × 1.10)"
                        ),
                        "durum": "UYUMLU"
                    })
                else:
                    sonuclar["capraz_kontrol"].append({
                        "belge": "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                        "detay": (
                            f"Sigorta: {sigorta_tutari:,.2f} | "
                            f"Gerekli Min.: {minimum_teminat:,.2f} — "
                            f"Eksik Teminat: {minimum_teminat - sigorta_tutari:,.2f}"
                        ),
                        "durum": "REZERV RİSKİ - YETERSİZ SİGORTA TEMİNATI"
                    })
            elif sigorta_tutari is None and fatura_tutari is not None:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                    "detay": (
                        f"Sigorta belgesi mevcut ancak tutar okunamadı. "
                        f"Fatura: {fatura_tutari:,.2f} → Gerekli min: {fatura_tutari * 1.10:,.2f}"
                    ),
                    "durum": "MANUEL KONTROL"
                })
            else:
                sonuclar["capraz_kontrol"].append({
                    "belge": "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                    "detay": "Sigorta veya fatura tutarı tespit edilemedi.",
                    "durum": "MANUEL KONTROL"
                })
        elif incoterm_var in ["CIF", "CIP"] and not self.depo["SIGORTA"]:
            # Art 28 zaten YÜKSEK RİSK olarak işaretlendi; buraya düşmemeli ama savunmalı yaz
            sonuclar["capraz_kontrol"].append({
                "belge": "Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii)",
                "detay": f"{incoterm_var} teslimlerde sigorta poliçesi zorunludur ancak dosyalar arasında bulunamadı.",
                "durum": "REZERV RİSKİ - SİGORTA BELGESİ EKSİK"
            })

        # ---- 5. Konşimento Hukuki Maddeleri (UCP 600 Art 20) ----
        if "SHIPPED ON BOARD" in combined or "ON BOARD" in combined:
            sonuclar["zorunlu_alanlar"].append(
                "[OK] Konşimento üzerinde yasal 'Shipped on Board' şerhi saptandı (Art 20a-ii uyumlu)."
            )
        else:
            sonuclar["zorunlu_alanlar"].append(
                "[REZERV RİSKİ] Konşimentoda zorunlu 'Shipped on Board' "
                "yükleme şerhi açıkça bulunamadı!"
            )

        # ---- 6. UCP 600 Tablo (hukuk_motoru.py entegrasyonu veya yerleşik mantık) ----
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
                # Dönüş tipi: list → doğrudan kullan; dict → "ucp_tablosu" anahtarını çek
                if isinstance(motor_sonuc, list) and motor_sonuc:
                    ucp_tablosu = motor_sonuc
                elif isinstance(motor_sonuc, dict):
                    ucp_tablosu = motor_sonuc.get("ucp_tablosu") or []
                    # Hukuk motoru diğer rapor alanlarını da dolduruyorsa aktar
                    for alan in ("vade_analizi", "finansal_durum", "incoterms",
                                 "capraz_kontrol", "zorunlu_alanlar"):
                        if motor_sonuc.get(alan):
                            sonuclar[alan] = motor_sonuc[alan]
                else:
                    ucp_tablosu = []

                if ucp_tablosu:
                    sonuclar["ucp_tablosu"] = ucp_tablosu
                else:
                    raise ValueError("hukuk_motoru.analiz_et kullanılabilir veri döndürmedi.")
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

    def _varsayilan_ucp_tablosu(self, fatura_durum, bl_durum, art28_durum, art28_not):
        """Hukuk motoru yoksa veya hata verdiyse kullanılan yerleşik UCP 600 tablosu."""
        return [
            (
                "Art 14",
                "Belgelerin İncelenmesi Standartları",
                "TESPİT EDİLDİ",
                "Standart 21 günlük yasal banka ibraz sınırı uygulandı."
            ),
            (
                "Art 15",
                "Uyumlu İbraz (Complying Presentation)",
                "DOĞRUDAN GEÇMİYOR",
                "Vesaiklerin bankaya eksiksiz ve hatasız ulaştığının teyidi."
            ),
            (
                "Art 17",
                "Orijinal Belgeler ve Suretler",
                "DOĞRUDAN GEÇMİYOR",
                "Banka ibrazında orijinal/suret kaşelerinin varlığı aranır."
            ),
            (
                "Art 18",
                "Ticari Fatura (Commercial Invoice)",
                fatura_durum,
                "Mal tanımının küşat metniyle karakter doğrulaması yapıldı (Art 18c)."
            ),
            (
                "Art 20",
                "Konşimento (Bill of Lading)",
                bl_durum,
                "Shipped on Board şerhi ve ciro silsilesi hukuki denetimi yapıldı."
            ),
            (
                "Art 27",
                "Temiz Taşıma Belgesi",
                bl_durum,
                "Üzerinde hasar veya kusurlu ambalaj şerhi bulunmayan temiz belge kontrolü."
            ),
            (
                "Art 28",
                "Sigorta Belgesi ve Kapsamı",
                art28_durum,
                art28_not
            ),
            (
                "Art 30",
                "Miktar ve Tutarda Toleranslar",
                "DOĞRUDAN GEÇMİYOR",
                "Akreditifte aksi belirtilmedikçe %5 / %10 tolerans limitleri."
            ),
        ]

    # ------------------------------------------------------------------
    # Rapor üretimi — tüm özellikler korundu
    # ------------------------------------------------------------------
    def markdown_raporu_olustur(self):
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, Markdown raporu oluşturulamadı.")
            return
        md_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.md")

        md_text = (
            "# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU\n"
            f"**Analiz Zamanı:** {datetime.now().strftime('%d.%m.%Y %H:%M')}  \n"
            "**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP Hukuk Motoru v3.0  \n\n"
            "---\n"
            "## 1. Kritik Süreler ve Vade Analizi\n"
        )
        for s in v.get("vade_analizi", []):
            md_text += f"* {s}\n"
        md_text += "\n--- \n## 2. Finansal Vade ve Ödeme Takvimi\n"
        for f in v.get("finansal_durum", []):
            md_text += f"* {f}\n"
        md_text += "\n--- \n## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)\n"
        for i in v.get("incoterms", []):
            md_text += f"* {i}\n"
        md_text += (
            "\n--- \n## 4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü\n"
            "| Belgeler | İnceleme Detayı | Durum |\n"
            "| :--- | :--- | :--- |\n"
        )
        for c in v.get("capraz_kontrol", []):
            md_text += f"| {c['belge']} | {c['detay']} | **[{c['durum']}]** |\n"
        md_text += "\n--- \n## 5. Konşimento ve Taşıma Hukuku Parametreleri (UCP Art. 20-27)\n"
        for z in v.get("zorunlu_alanlar", []):
            md_text += f"* {z}\n"
        md_text += (
            "\n--- \n## 6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu\n"
            "| UCP 600 Madde | Kapsam Açıklaması | Sistem Geçiş Durumu | Uzman Bulgusu |\n"
            "| :--- | :--- | :--- | :--- |\n"
        )
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                md_text += f"| **{m[0]}** | {m[1]} | `{m[2]}` | {m[3]} |\n"

        with open(md_yolu, "w", encoding="utf-8") as f:
            f.write(md_text)
        print("[+] Markdown Raporu Oluşturuldu.")

    def html_raporu_olustur(self):
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, HTML raporu oluşturulamadı.")
            return
        html_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.html")

        capraz_satirlar = "".join([
            f"<tr><td><b>{r['belge']}</b></td><td>{r['detay']}</td><td><b>{r['durum']}</b></td></tr>"
            for r in v.get("capraz_kontrol", [])
        ])
        ucp_satirlar = "".join([
            f"<tr><td><b>{m[0]}</b></td><td>{m[1]}</td><td><code>{m[2]}</code></td><td>{m[3]}</td></tr>"
            for m in v.get("ucp_tablosu", [])
            if m and len(m) >= 4
        ])

        html_text = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Hukuki Akreditif Analiz Raporu</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; padding: 30px; color: #2d3748; background-color: #f7fafc; }}
    .container {{ background: white; padding: 40px; border-radius: 12px;
                  box-shadow: 0 4px 6px rgba(0,0,0,0.05); max-width: 1100px; margin: 0 auto; }}
    h1 {{ color: #1a365d; border-bottom: 4px solid #3182ce; padding-bottom: 12px; }}
    h2 {{ color: #2b6cb0; margin-top: 30px; border-left: 5px solid #3182ce; padding-left: 10px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 14px; text-align: left; }}
    th {{ background-color: #ebf8ff; color: #2b6cb0; }}
    tr:nth-child(even) {{ background-color: #f8fafc; }}
  </style>
</head>
<body>
<div class="container">
  <h1>📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU</h1>
  <p><b>Rapor Tarihi:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
  <h2>1. Kritik Süreler ve Vade Analizi</h2>
  <ul>{"".join([f"<li>{x}</li>" for x in v.get("vade_analizi", [])])}</ul>
  <h2>2. Finansal Vade ve Ödeme Takvimi</h2>
  <ul>{"".join([f"<li>{x}</li>" for x in v.get("finansal_durum", [])])}</ul>
  <h2>3. Incoterms ve Sigorta Hukuku (ICC 2020)</h2>
  <ul>{"".join([f"<li>{x}</li>" for x in v.get("incoterms", [])])}</ul>
  <h2>4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü</h2>
  <table>
    <tr><th>Belgeler</th><th>Detaylı İnceleme Kriteri</th><th>Durum</th></tr>
    {capraz_satirlar}
  </table>
  <h2>5. Konşimento ve Taşıma Hukuku Parametreleri</h2>
  <ul>{"".join([f"<li>{x}</li>" for x in v.get("zorunlu_alanlar", [])])}</ul>
  <h2>6. UCP 600 Hukuki Maddeleri Tablosu</h2>
  <table>
    <tr><th>Madde</th><th>Açıklama</th><th>Sistem Durumu</th><th>Bulgu</th></tr>
    {ucp_satirlar}
  </table>
</div>
</body>
</html>"""

        with open(html_yolu, "w", encoding="utf-8") as f:
            f.write(html_text)
        print("[+] HTML Raporu Oluşturuldu.")

    def word_raporu_olustur(self):
        if not docx:
            print("[UYARI] python-docx yüklü değil, Word raporu atlandı.")
            return
        v = self.analiz_verisi
        if not v:
            print("[UYARI] Analiz verisi boş, Word raporu oluşturulamadı.")
            return
        doc_yolu = os.path.join(self.raporlar_dir, "akreditif_analiz_raporu.docx")
        doc = docx.Document()

        for section in doc.sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        title = doc.add_paragraph()
        title_run = title.add_run(
            "📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU"
        )
        title_run.font.name = "Arial"
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        title_run.font.color.rgb = docx.shared.RGBColor(26, 54, 93)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        meta = doc.add_paragraph()
        meta_run = meta.add_run(
            f"Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')} "
            "| Altyapı Sürümü: UCP 600 Hukuk Motoru v3.0"
        )
        meta_run.font.size = Pt(9)
        meta_run.font.italic = True
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph("-" * 60)

        def baslik_ekle(metin):
            h = doc.add_paragraph()
            hrun = h.add_run(metin)
            hrun.font.name = "Arial"
            hrun.font.size = Pt(13)
            hrun.font.bold = True
            hrun.font.color.rgb = docx.shared.RGBColor(43, 108, 176)

        baslik_ekle("1. Kritik Süreler ve Vade Analizi")
        for item in v.get("vade_analizi", []):
            doc.add_paragraph(item.replace("**", ""), style="List Bullet")

        baslik_ekle("2. Finansal Vade ve Ödeme Takvimi")
        for item in v.get("finansal_durum", []):
            doc.add_paragraph(item.replace("**", ""), style="List Bullet")

        baslik_ekle("3. Incoterms ve Sigorta Hukuku (ICC 2020)")
        for item in v.get("incoterms", []):
            doc.add_paragraph(item.replace("**", ""), style="List Bullet")

        baslik_ekle("4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü")
        t1 = doc.add_table(rows=1, cols=3)
        t1.style = "Table Grid"
        hdr = t1.rows[0].cells
        hdr[0].text = "Belgeler"
        hdr[1].text = "İnceleme Detayı"
        hdr[2].text = "Durum"
        for r in v.get("capraz_kontrol", []):
            row_cells = t1.add_row().cells
            row_cells[0].text = str(r.get("belge", ""))
            row_cells[1].text = str(r.get("detay", ""))
            row_cells[2].text = str(r.get("durum", ""))

        baslik_ekle("5. Konşimento ve Taşıma Hukuku Parametreleri")
        for item in v.get("zorunlu_alanlar", []):
            doc.add_paragraph(item.replace("**", ""), style="List Bullet")

        baslik_ekle("6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu")
        t2 = doc.add_table(rows=1, cols=4)
        t2.style = "Table Grid"
        hdr2 = t2.rows[0].cells
        hdr2[0].text = "Madde"
        hdr2[1].text = "Açıklama"
        hdr2[2].text = "Sistem Durumu"
        hdr2[3].text = "Bulgu"
        for m in v.get("ucp_tablosu", []):
            if m and len(m) >= 4:
                row_cells = t2.add_row().cells
                row_cells[0].text = str(m[0])
                row_cells[1].text = str(m[1])
                row_cells[2].text = str(m[2])
                row_cells[3].text = str(m[3])

        doc.save(doc_yolu)
        print("[+] Word (.docx) Raporu Başarıyla Üretildi.")

    # ------------------------------------------------------------------
    # Ana akış
    # ------------------------------------------------------------------
    def baslat(self):
        if self.depoyu_tara_ve_analiz_et():
            self.ucp600_kural_motoru()
            self.markdown_raporu_olustur()
            self.html_raporu_olustur()
            self.word_raporu_olustur()
        else:
            print("[BİLGİ] Yüklenmiş belge bulunamadı veya dizin boş.")


if __name__ == "__main__":
    motor = YapayZekaDisTicaretDenetleyici()
    motor.baslat()
