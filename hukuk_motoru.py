import json
import re
from datetime import datetime, timedelta

def analiz_et(depo):
    # 1. Birleştirilmiş kural kütüphanesini yükle
    try:
        with open('kurallar.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        return [("SİSTEM", "Hata", "KRİTİK", "kurallar.json dosyası okunamadı!")]
    
    rapor = []
    
    # 2. Kritik Kontrolleri (Art 1-39) Analiz Et
    for kural in data["kritik_kontroller"]:
        for evrak_tipi, icerik in depo.items():
            if kural["anahtar"] in icerik["metin"].upper():
                rapor.append((kural["madde"], kural["aciklama"], "OK", f"Doğrulandı: {kural['aciklama']}"))

    # 3. Pratik İşleyiş Detaylarını (Operasyonel Mantık) Uygula
    # İbraz Süresi Kontrolü
    if depo.get("KUSAT"):
        tarih_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", depo["KUSAT"]["metin"])
        if tarih_match:
            yukleme_tarihi = datetime.strptime(tarih_match.group(1), "%d.%m.%Y")
            ibraz_son = yukleme_tarihi + timedelta(days=21)
            rapor.append(("Art 14", "İbraz Süresi", "BİLGİ", data["pratik_isleyis_detaylari"]["vesaik_ibraz_suresi"] + f" (Son tarih: {ibraz_son.strftime('%d.%m.%Y')})"))

    # Tolerans Kontrolü
    if depo.get("FATURA"):
        rapor.append(("Art 30", "Tolerans", "BİLGİ", data["pratik_isleyis_detaylari"]["miktar_ve_tutar_toleransi"]))

    # 4. Banka Süreçleri ve Uyarılar
    if "REZERV" in str(rapor): # Eğer bir hata yakalandıysa
        rapor.append(("Art 16", "Rezerv Uygulaması", "UYARI", data["banka_surecleri"]["rezerv_uygulamasi"]))

    return rapor
