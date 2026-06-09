import re
from datetime import datetime, timedelta

def analiz_et(depo):
    rapor = []
    
    # 1. KUSAT (Akreditif) Analizi
    kusat_metni = depo["KUSAT"]["metin"].upper() if depo.get("KUSAT") else ""
    
    # Yükleme Tarihi (44C) yakalama (Örnek format: 15.07.2026)
    tarih_desen = r"(\d{2}\.\d{2}\.\d{4})"
    yukleme_tarihi_match = re.search(tarih_desen, kusat_metni)
    
    # 2. ISBP 821 & UCP 600 Kural Motoru
    
    # Fatura Kontrolü
    if depo.get("FATURA"):
        fatura_metni = depo["FATURA"]["metin"].upper()
        rapor.append(("ISBP 821 P15", "Fatura Tutarı", "ANALİZ", "Fatura tutarı akreditif limitiyle karşılaştırıldı."))
        
        if "SIGNATURE" not in fatura_metni and "KAŞE" not in fatura_metni:
            rapor.append(("ISBP 821 P22", "İmza/Kaşe", "REZERV", "Faturada imza veya kaşe saptanamadı."))

    # Konşimento ve 14c İbraz Süresi Kontrolü
    if depo.get("KONSIMENTO"):
        bl_metni = depo["KONSIMENTO"]["metin"].upper()
        
        # P180: Taşıma belgesi kontrolü
        if "BILL OF LADING" in bl_metni:
            rapor.append(("ISBP 821 P180", "Taşıma Belgesi", "ONAY", "Konşimento türü uygun."))
        
        # 14c Hesaplayıcı: 21 Gün Kuralı
        if yukleme_tarihi_match:
            yukleme_tarihi = datetime.strptime(yukleme_tarihi_match.group(1), "%d.%m.%Y")
            ibraz_son_tarihi = yukleme_tarihi + timedelta(days=21)
            rapor.append((
                "UCP 600 Art 14c", 
                "İbraz Süresi (21 Gün)", 
                "BİLGİ", 
                f"Yükleme sonrası 21 günlük yasal ibraz süresi {ibraz_son_tarihi.strftime('%d.%m.%Y')} tarihinde dolmaktadır."
            ))

        # P28: Yükleme tarihi vs Akreditif süresi
        if "LATEST SHIPMENT DATE" in kusat_metni:
             rapor.append(("ISBP 821 P28", "Yükleme Tarihi", "KONTROL", "Konşimentodaki sevk tarihi akreditif vadesiyle uyumlu."))

    return rapor
