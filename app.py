import os
import re
from datetime import datetime

# Kütüphane kontrolleri
try: from pypdf import PdfReader
except ImportError: PdfReader = None
try:
    import docx
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError: docx = None
try: import openpyxl
except ImportError: openpyxl = None
try:
    from PIL import Image
    import pytesseract
except ImportError: pytesseract = None

class YapayZekaDisTicaretDenetleyici:
    def __init__(self, ana_dizin="DisTicaretRepo"):
        self.base_dir = ana_dizin
        self.yuklenenler_dir = os.path.join(self.base_dir, "YuklenenDosyalar")
        self.raporlar_dir = os.path.join(self.base_dir, "Raporlar")
        os.makedirs(self.yuklenenler_dir, exist_ok=True)
        os.makedirs(self.raporlar_dir, exist_ok=True)
        
        self.depo = {
            "KUSAT": None, "FATURA": None, "KONSIMENTO": None, 
            "CEKI_LISTESI": None, "SIGORTA": None, "DIGER_BELGELER": []
        }
        # HATA ÇÖZÜMÜ: Sözlük yapısı burada tam olarak tanımlandı
        self.analiz_verisi = {
            "vade_analizi": [], "finansal_durum": [], "incoterms": [], 
            "capraz_kontrol": [], "zorunlu_alanlar": [], "ucp_tablosu": []
        }

    def metin_ayıkla(self, dosya_yolu):
        ext = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""
        try:
            if ext == ".pdf" and PdfReader:
                reader = PdfReader(dosya_yolu)
                for sayfa in reader.pages:
                    txt = sayfa.extract_text()
                    if txt: metin += txt + "\n"
            elif ext in [".docx", ".doc"] and docx:
                doc = docx.Document(dosya_yolu)
                for p in doc.paragraphs:
                    if p.text: metin += p.text + "\n"
                for table in doc.tables:
                    for row in table.rows:
                        row_text = " ".join([cell.text for cell in row.cells if cell.text])
                        if row_text.strip(): metin += row_text + "\n"
            elif ext in [".xlsx", ".xls"] and openpyxl:
                wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
                for s in wb.sheetnames:
                    ws = wb[s]
                    for r in ws.iter_rows(values_only=True):
                        metin += " ".join([str(c) for c in r if c is not None]) + "\n"
            elif ext in [".png", ".jpg", ".jpeg"] and pytesseract:
                img = Image.open(dosya_yolu)
                metin = pytesseract.image_to_string(img, lang='eng+tur')
            elif ext == ".txt":
                with open(dosya_yolu, "r", encoding="utf-8", errors="ignore") as f:
                    metin = f.read()
        except Exception as e: metin = f"[Hata: {str(e)}]"
        return metin.replace('\xa0', ' ')

    def dokuman_tipi_belirle(self, metin):
        m_upper = metin.upper()
        if any(x in m_upper for x in ["DOCUMENTARY CREDIT", "40A:", "IRREVOCABLE", "KÜŞAT"]): return "KUSAT"
        if any(x in m_upper for x in ["COMMERCIAL INVOICE", "FATURA", "INVOICE"]): return "FATURA"
        if any(x in m_upper for x in ["BILL OF LADING", "SHIPPED ON BOARD"]): return "KONSIMENTO"
        if any(x in m_upper for x in ["PACKING LIST", "ÇEKİ LİSTESİ"]): return "CEKI_LISTESI"
        if any(x in m_upper for x in ["INSURANCE POLICY", "SİGORTA"]): return "SIGORTA"
        return "DIGER"

    def depoyu_tara_ve_analiz_et(self):
        if not os.path.exists(self.yuklenenler_dir): return False
        dosyalar = [os.path.join(self.yuklenenler_dir, f) for f in os.listdir(self.yuklenenler_dir) if os.path.isfile(os.path.join(self.yuklenenler_dir, f))]
        for d_yolu in dosyalar:
            dosya_adi = os.path.basename(d_yolu)
            icerik = self.metin_ayıkla(d_yolu)
            tip = self.dokuman_tipi_belirle(icerik)
            if tip in self.depo: self.depo[tip] = {"ad": dosya_adi, "metin": icerik}
        return True

    def ucp600_kural_motoru(self):
        # Yama yok, doğrudan sınıf metodu olarak çalışıyor
        try:
            from hukuk_motoru import analiz_et
            # Hukuk motoruna tüm depo sözlüğünü gönderiyoruz. 
            # hukuk_motoru.py içinde icerik.upper() hatası alıyorsanız, 
            # orada sadece fatura metnini işleyecek bir kontrol eklemelisiniz.
            self.analiz_verisi["ucp_tablosu"] = analiz_et(self.depo)
        except Exception as e:
            self.analiz_verisi["ucp_tablosu"] = [("SİSTEM", "Hukuk Motoru", "HATA", str(e))]

    def markdown_raporu_olustur(self):
        v = self.analiz_verisi
        with open(os.path.join(self.raporlar_dir, "rapor.md"), "w", encoding="utf-8") as f:
            f.write("# Akreditif Analiz Raporu\n\n")
            for m in v["ucp_tablosu"]:
                f.write(f"- **{m[0]}**: {m[1]} | Durum: {m[2]} | Not: {m[3]}\n")

    def baslat(self):
        if self.depoyu_tara_ve_analiz_et():
            self.ucp600_kural_motoru()
            self.markdown_raporu_olustur()
            print("Analiz tamamlandı, rapor oluşturuldu.")

if __name__ == "__main__":
    motor = YapayZekaDisTicaretDenetleyici()
    motor.baslat()
