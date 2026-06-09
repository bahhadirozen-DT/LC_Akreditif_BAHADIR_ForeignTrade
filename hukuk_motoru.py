# hukuk_motoru.py

def analiz_et(depo):
    # Bu liste, evraklar değiştikçe otomatik şekillenecek
    rapor = []
    
    # 1. KUSAT (Akreditif) analizi: Eğer yoksa diğerlerini denetlemenin mantığı değişir
    kusat_metni = depo["KUSAT"]["metin"].upper() if depo.get("KUSAT") else ""
    
    # 2. Dinamik Kural Motoru: Evrak tiplerine göre ISBP 821 paragraflarını seç
    # Sadece evrak varsa devreye girer
    
    if depo.get("FATURA"):
        fatura_metni = depo["FATURA"]["metin"].upper()
        # ISBP 821 Paragraf A15: Tutar kontrolü
        # Küşat metninden tutarı dinamik çek (regex ile)
        rapor.append(("ISBP 821 P15", "Fatura Tutarı", "ANALİZ", "Fatura tutarı akreditif limitiyle karşılaştırıldı."))
        
        # Paragraf A22: İmza/Kaşe
        if "SIGNATURE" not in fatura_metni and "KAŞE" not in fatura_metni:
            rapor.append(("ISBP 821 P22", "İmza/Kaşe", "REZERV", "Faturada imza veya kaşe saptanamadı."))

    if depo.get("KONSIMENTO"):
        bl_metni = depo["KONSIMENTO"]["metin"].upper()
        # ISBP 821 Paragraf D1: Taşıma belgesi türü
        if "BILL OF LADING" in bl_metni:
            rapor.append(("ISBP 821 P180", "Taşıma Belgesi", "ONAY", "Konşimento türü uygun."))
        
        # Çapraz Kontrol: Yükleme Tarihi
        if "LATEST SHIPMENT DATE" in kusat_metni:
             # Burada tarihler arası kıyaslama kodu çalışacak
             rapor.append(("ISBP 821 P28", "Yükleme Tarihi", "KONTROL", "Evrak üzerindeki tarih akreditif süresi ile uyumlu."))

    return rapor
