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
    rezerv_satirlari = []
    
    # 2. Kritik Kontroller
    for kural in data["kritik_kontroller"]:
        for evrak_tipi, icerik in depo.items():
            if kural["anahtar"] in icerik.upper():
                rapor.append((kural["madde"], kural["aciklama"], "OK", f"Doğrulandı: {kural['aciklama']}"))

    # 3. Sayısal Kontrol
    if "FATURA" in depo and "KONSİMENTO" in depo:
        fat = re.search(r"(\d+)", depo["FATURA"])
        kon = re.search(r"(\d+)", depo["KONSİMENTO"])
        if fat and kon and fat.group(1) != kon.group(1):
            msg = f"Fatura: {fat.group(1)} KG - Konşimento: {kon.group(1)} KG uyumsuz!"
            rapor.append(("Art 30", "Ağırlık Kontrolü", "REZERV", msg))
            rezerv_satirlari.append(msg)

    # 4. MEKTUP EKLEME (Rapor listesine doğrudan mektup bloğunu string olarak ekle)
    if rezerv_satirlari:
        mektup = (
            "\n[DİKKAT: UCP 600 MADDE 16 GEREĞİ BİLDİRİM]\n"
            "İbraz edilen belgelerde aşağıdaki uyumsuzluklar saptanmıştır:\n" + 
            "\n".join([f"- {s}" for s in rezerv_satirlari]) +
            "\n\nUYARI: Bu durum rezerv teşkil eder. Lütfen 5 iş günü içinde düzeltme yapınız."
        )
        # Raporun en sonuna özel bir "Mektup" satırı ekliyoruz
        rapor.append(("Art 16", "REZERVE BİLDİRİMİ", "UYARI", mektup))

    return rapor
