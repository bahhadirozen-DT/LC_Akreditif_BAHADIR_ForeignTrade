# isbp_veritabani.py

ISBP_KURALLARI = {
    "Art 4": {
        "kapsam": "Akreditiflerin Bağımsızlığı",
        "yorum": "Akreditifler temel satış sözleşmelerinden bağımsızdır. Banka sadece belgelere bakar."
    },
    "Art 18": {
        "kapsam": "Ticari Fatura",
        "yorum": "Mal tanımı, küşat metniyle tam uyumlu olmalı ve ISBP 821 Bölüm C gereği alıcı/satıcı bilgileri çelişmemelidir."
    },
    "Art 20": {
        "kapsam": "Konşimento",
        "yorum": "ISBP 821 Bölüm K uyarınca; taşıyıcı kaşesi, 'Shipped on Board' şerhi ve ciro silsilesi hukuken tamamlanmış olmalıdır."
    },
    "Art 28": {
        "kapsam": "Sigorta",
        "yorum": "ISBP uyarınca sigorta belgesi, fatura tutarının en az %110'unu kapsamalı ve tüm riskleri içermelidir."
    }
}

def isbp_yorumu_al(madde):
    return ISBP_KURALLARI.get(madde, {"kapsam": "Genel Kural", "yorum": "UCP 600 ve ISBP 821 genel standartları uygulanır."})
