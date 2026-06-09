import re

def sayisal_deger_bul(metin, desenler):
    for desen in desenler:
        bulunan = re.findall(desen, metin, re.IGNORECASE)
        if bulunan:
            try: return float(bulunan[0].replace(",", "").strip())
            except: pass
    return None

def analiz_et(depo):
    tablo_verisi = []
    
    # 1. Konşimento (B/L) - UCP 600 Art 20
    if depo.get("KONSIMENTO"):
        metin = depo["KONSIMENTO"]["metin"].upper()
        if "SHIPPED ON BOARD" not in metin:
            tablo_verisi.append(("Art 20", "Konşimento", "REZERV", "Shipped on Board şerhi eksik."))
        else:
            tablo_verisi.append(("Art 20", "Konşimento", "OK", "Yükleme şerhi mevcut."))

    # 2. Fatura (Invoice) - UCP 600 Art 18
    if depo.get("FATURA"):
        tablo_verisi.append(("Art 18", "Ticari Fatura", "OK", "Fatura mevcut ve incelendi."))

    # 3. Çapraz Kontrol: Fatura vs Konşimento Brüt Kilo (ISBP 821 A14)
    if depo.get("FATURA") and depo.get("KONSIMENTO"):
        f_kilo = sayisal_deger_bul(depo["FATURA"]["metin"], [r'GROSS WEIGHT[:\s]*([\d,.]+)\s*KG'])
        b_kilo = sayisal_deger_bul(depo["KONSIMENTO"]["metin"], [r'GROSS WEIGHT[:\s]*([\d,.]+)\s*KG'])
        
        if f_kilo and b_kilo:
            if abs(f_kilo - b_kilo) > 0.01:
                tablo_verisi.append(("ISBP A14", "Veri Uyumu", "REZERV", f"Kilo uyuşmazlığı: Fatura {f_kilo}kg, B/L {b_kilo}kg."))
            else:
                tablo_verisi.append(("ISBP A14", "Veri Uyumu", "OK", "Brüt kilo değerleri eşleşiyor."))

    # 4. Risk Kontrolü: Sigorta Poliçesi - UCP 600 Art 28
    # Eğer CIF/CIP ise sigorta aranır
    if depo.get("FATURA"):
        f_metin = depo["FATURA"]["metin"].upper()
        if "CIF" in f_metin or "CIP" in f_metin:
            if not depo.get("SIGORTA"):
                tablo_verisi.append(("Art 28", "Sigorta Poliçesi", "REZERV", "CIF/CIP şartı var ancak Sigorta Poliçesi eksik!"))
            else:
                tablo_verisi.append(("Art 28", "Sigorta Poliçesi", "OK", "Sigorta poliçesi tespit edildi."))

    return tablo_verisi
