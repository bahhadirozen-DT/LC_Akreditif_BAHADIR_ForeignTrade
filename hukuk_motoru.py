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
    
    # 2. Kritik Kontroller (DÖNGÜ DÜZELTİLDİ)
    for kural in data["kritik_kontroller"]:
        for evrak_tipi, veri in depo.items():
            # 'veri' burada bir sözlük olabilir (örneğin {'ad': '...', 'metin': '...'})
            # Eğer veri bir sözlükse metin içeriğine, değilse doğrudan kendine eriş
            icerik = veri["metin"] if isinstance(veri, dict) and "metin" in veri else str(veri)
            
            if kural["anahtar"] in icerik.upper():
                rapor.append((kural["madde"], kural["aciklama"], "OK", f"Doğrulandı: {kural['aciklama']}"))

    # 3. Sayısal Kontrol (DÖNGÜ DÜZELTİLDİ)
    # Metinlere güvenli erişim sağlıyoruz
    def metin_al(tip):
        veri = depo.get(tip)
        return veri["metin"] if isinstance(veri, dict) and "metin" in veri else str(veri)

    fat_metin = metin_al("FATURA")
    kon_metin = metin_al("KONSIMENTO")

    if fat_metin and kon_metin:
        fat = re.search(r"(\d+)", fat_metin)
        kon = re.search(r"(\d+)", kon_metin)
        if fat and kon and fat.group(1) != kon.group(1):
            msg = f"Fatura: {fat.group(1)} KG - Konşimento: {kon.group(1)} KG uyumsuz!"
            rapor.append(("Art 30", "Ağırlık Kontrolü", "REZERV", msg))
            rezerv_satirlari.append(msg)

    # 4. MEKTUP EKLEME
    if rezerv_satirlari:
        mektup = (
            "\n[DİKKAT: UCP 600 MADDE 16 GEREĞİ BİLDİRİM]\n"
            "İbraz edilen belgelerde aşağıdaki uyumsuzluklar saptanmıştır:\n" + 
            "\n".join([f"- {s}" for s in rezerv_satirlari]) +
            "\n\nUYARI: Bu durum rezerv teşkil eder. Lütfen 5 iş günü içinde düzeltme yapınız."
        )
        rapor.append(("Art 16", "REZERVE BİLDİRİMİ", "UYARI", mektup))

    return rapor
