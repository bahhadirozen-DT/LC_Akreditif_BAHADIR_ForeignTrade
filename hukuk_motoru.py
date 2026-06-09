import json
import re
from datetime import datetime, timedelta

def analiz_et(depo):
    # 1. Kural kütüphanesini yükle
    try:
        with open('kurallar.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [("SİSTEM", "Hata", "KRİTİK", f"JSON okunamadı: {e}")]
    
    rapor = []
    rezerv_var_mi = False
    
    # 2. Kritik Kontrolleri Analiz Et
    for kural in data["kritik_kontroller"]:
        for evrak_tipi, icerik in depo.items():
            if kural["anahtar"] in icerik.upper():
                rapor.append((kural["madde"], kural["aciklama"], "OK", f"Doğrulandı: {kural['aciklama']}"))

    # 3. Sayısal/Mantıksal Çapraz Kontrol (Örn: Ağırlık)
    if "FATURA" in depo and "KONSİMENTO" in depo:
        fat_agirlik = re.search(r"(\d+)", depo["FATURA"])
        kon_agirlik = re.search(r"(\d+)", depo["KONSİMENTO"])
        
        if fat_agirlik and kon_agirlik and fat_agirlik.group(1) != kon_agirlik.group(1):
            rapor.append(("Art 30", "Ağırlık Kontrolü", "REZERV", 
                         f"Fatura: {fat_agirlik.group(1)} KG - Konşimento: {kon_agirlik.group(1)} KG uyuşmuyor!"))
            rezerv_var_mi = True

    # 4. Rezerv Bildirim Mektubu (Art 16)
    if rezerv_var_mi:
        mektup = f"\n--- REZERV BİLDİRİM MEKTUBU (Art 16) ---\n"
        mektup += f"Konu: UCP 600 Madde 16 gereği rezerv bildirimi.\n"
        mektup += f"İnceleme sonucunda belgelerde uyumsuzluk saptanmıştır.\n"
        mektup += f"Söz konusu rezervler: {[r[3] for r in rapor if r[2] == 'REZERV']}\n"
        mektup += f"5 iş günü içerisinde düzeltme yapılmalıdır.\n"
        mektup += f"------------------------------------------\n"
        rapor.append(("Art 16", "Bildirim", "UYARI", mektup))

    return rapor
