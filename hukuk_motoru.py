import json
import re

def analiz_et(depo):
    # 1. JSON Kuralları Yükle
    try:
        with open('kurallar.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return [("SİSTEM", "Hata", "KRİTİK", f"Kurallar okunamadı: {e}")]
    
    rapor = []
    
    # 2. Kritik Kontrolleri Analiz Et
    for kural in data["kritik_kontroller"]:
        for evrak_tipi, icerik in depo.items():
            if kural["anahtar"] in icerik.upper():
                rapor.append((kural["madde"], kural["aciklama"], "OK", f"Doğrulandı: {kural['aciklama']}"))

    # 3. Sayısal Kontrol (Fatura vs Konşimento)
    if "FATURA" in depo and "KONSİMENTO" in depo:
        fat = re.search(r"(\d+)", depo["FATURA"])
        kon = re.search(r"(\d+)", depo["KONSİMENTO"])
        if fat and kon and fat.group(1) != kon.group(1):
            rapor.append(("Art 30", "Ağırlık Kontrolü", "REZERV", 
                         f"Fatura: {fat.group(1)} KG - Konşimento: {kon.group(1)} KG uyumsuz!"))

    # 4. Mektup Ekleme (Her türlü REZERV satırını raporda tara)
    if any(r[2] == "REZERV" for r in rapor):
        rezerv_detaylari = [r[3] for r in rapor if r[2] == "REZERV"]
        mektup = (
            "\n--- REZERV BİLDİRİM MEKTUBU (Art 16) ---\n"
            "Konu: UCP 600 Madde 16 gereği uyumsuzluk bildirimi.\n"
            f"Saptanan Uyumsuzluklar: {', '.join(rezerv_detaylari)}\n"
            "Belgelerin en geç 5 iş günü içinde düzeltilmesi gerekmektedir.\n"
            "------------------------------------------\n"
        )
        rapor.append(("Art 16", "Bildirim Taslağı", "UYARI", mektup))

    return rapor
