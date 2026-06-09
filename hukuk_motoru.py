# hukuk_motoru.py

def analiz_et(depo):
    tablo_verisi = []
    
    # Örnek 1: Konşimento kontrolü
    if depo.get("KONSIMENTO"):
        metin = depo["KONSIMENTO"]["metin"].upper()
        if "SHIPPED ON BOARD" not in metin:
            tablo_verisi.append(("Art 20", "Konşimento", "REZERV", "Shipped on Board şerhi eksik."))
            
    # Örnek 2: Fatura kontrolü
    if depo.get("FATURA"):
        tablo_verisi.append(("Art 18", "Ticari Fatura", "OK", "Fatura formatı uyumlu."))
        
    return tablo_verisi
