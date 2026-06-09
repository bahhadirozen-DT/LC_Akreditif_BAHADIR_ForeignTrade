# hukuk_kutuphanesi.py

# Hukuk kurallarını dinamik olarak tutan sözlük
HUKUK_KUTUPHANESI = {
    "FATURA": [
        {
            "id": "fatura_tutari_kontrol",
            "kaynak": "ISBP 821",
            "kural": lambda data: data['tutar'] > data['kredi_tutari'],
            "mesaj": "Fatura tutarı kredi limitini aşıyor.",
            "madde": "ISBP 821, Paragraf A15"
        },
        {
            "id": "fatura_imza_kontrol",
            "kaynak": "UCP 600",
            "kural": lambda data: not data['imza_varmi'],
            "mesaj": "Fatura imzalanmamış.",
            "madde": "UCP 600, Madde 18(a)(ii)"
        }
    ],
    "KONSIMENTO": [
        {
            "id": "konşimento_tarih_kontrol",
            "kaynak": "UCP 600",
            "kural": lambda data: data['yükleme_tarihi'] > data['vade_tarihi'],
            "mesaj": "Yükleme tarihi vadeyi geçmiş.",
            "madde": "UCP 600, Madde 20"
        }
    ]
}
