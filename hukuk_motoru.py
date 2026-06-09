import json
import re
from datetime import datetime, timedelta

def analiz_et(depo):
    # 1. Kural kütüphanesini yükle
    try:
        with open('kurallar.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {"kritik_kontroller": []}
    
    rapor = []
    
    # 2. JSON Tabanlı Denetim ve Uzman Yorumu
    for kural in data["kritik_kontroller"]:
        for evrak_tipi, icerik in depo.items():
            if kural["anahtar"] in icerik["metin"].upper():
                rapor.append((kural["madde"], kural["aciklama"], "OK", f"Doğrulandı: {kural['aciklama']}"))

    # 3. Hibrit Python Hesaplamaları (Art 14c ve Kilo)
    if depo.get("KUSAT"):
        tarih_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", depo["KUSAT"]["metin"])
        if tarih_match:
            yukleme_tarihi = datetime.strptime(tarih_match.group(1), "%d.%m.%Y")
            ibraz_son = yukleme_tarihi + timedelta(days=21)
            rapor.append(("Art 14c", "21 Gün Kuralı", "BİLGİ", f"Yasal ibraz son tarih: {ibraz_son.strftime('%d.%m.%Y')}"))

    if depo.get("FATURA") and depo.get("KONSIMENTO"):
        f_kilo = re.search(r"(\d+)\s*KG", depo["FATURA"]["metin"].upper())
        b_kilo = re.search(r"(\d+)\s*KG", depo["KONSIMENTO"]["metin"].upper())
        if f_kilo and b_kilo and f_kilo.group(1) != b_kilo.group(1):
            rapor.append(("ISBP A14", "Veri Uyumu", "REZERV", "Fatura ve Konşimento kilo uyuşmazlığı saptandı!"))

    return rapor
