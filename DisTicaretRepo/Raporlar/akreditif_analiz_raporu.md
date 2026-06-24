# AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0

**Tarih:** 24.06.2026 03:51 | Motor: UCP 600 & ISBP 821

---

## Dosya Durum Raporu

| Dosya | Var | OCR | Sınıf | Parse | Puan |
|:---|:---|:---|:---|:---|:---|
| slinecek.txt | V | X | - | X | 0 |
| packing list.txt | V | V | CEKI_LISTESI | V | 999 |

---

## Yönetici Özeti

| Metrik | Değer |
|:---|:---|
| LC No | **Tespit edilemedi** |
| Belgeler | CEKI_LISTESI |
| Rezerv | 1 (MAJOR: 1) |
| Uyumluluk | **%65** |
| Banka Kabul | **%70** |
| Risk | ORTA RİSK |

---

## MT700 Alan Analizi

| Alan | Açıklama | Değer | Durum |
|:---|:---|:---|:---|
| **20** | Documentary Credit Number | `—` | MANUEL KONTROL |
| **31D** | Expiry Date | `—` | MANUEL KONTROL |
| **32B** | Amount | `—` | MANUEL KONTROL |
| **40A** | Form | `—` | MANUEL KONTROL |
| **44C** | Latest Shipment | `—` | MANUEL KONTROL |
| **45A** | Description of Goods | `—` | MANUEL KONTROL |
| **46A** | Documents Required | `—` | MANUEL KONTROL |

---

## Vade Analizi

* En Geç Yükleme (44C): Tespit edilemedi — manuel kontrol.
* İbraz Süresi: Tespit edilemedi — UCP Art 14c 21 gün uygulanır.

## Ödeme Vadesi

* Ödeme: Tespit edilemedi — manuel kontrol.

## Incoterms & Sigorta

* Incoterms: Tespit edilemedi.


## Çapraz Kontroller

| Belgeler | Detay | Durum |
|:---|:---|:---|
| Tutar LC vs Fatura (Art 30) | Tespit edilemedi: Fatura, LC 32B | **MANUEL KONTROL** |
| Kilo: Fatura vs B/L | Tespit edilemedi: Fatura, B/L | **MANUEL KONTROL** |
| Kilo: Fatura vs Packing List | Tespit edilemedi: Fatura, Packing List | **MANUEL KONTROL** |
| Kilo: Packing List vs B/L | Tespit edilemedi: Packing List, B/L | **MANUEL KONTROL** |
| Mal Tanımı LC vs Fatura (Art 18c) | Tespit edilemedi: 45A Fatura | **MANUEL KONTROL** |
| B/L Tarihi vs 44C (Art 20) | B/L:- | 44C:- | **MANUEL KONTROL** |
| Menşe (Origin) Analizi | LC'de CO şartı tespit edilmedi. | **BİLGİ** |

## UCP 600 Hukuki Kontroller

### Art 14 — Belge İnceleme Standardı

**BULGU:** Belgeler yüz değerinden incelendi.

**HUKUKİ DEĞERLENDİRME:**

Belge inceleme standardı. İbraz süresi belirtilmemişse en fazla 21 gündür.

UCP 600 Art 14(a): Banka, belgeler temelinde uygun ibraz olup olmadığını belirlemek için sunumu inceler. Art 14(b): İnceleme için en fazla 5 iş günü bulunmaktadır. Art 14(d): Belgeler arasındaki veriler çelişmemelidir; ancak birebir aynı olmak zorunda değildir.

**SONUÇ: ⚠ BİLGİ**

---

### Art 30 — Tutar

**BULGU:** Tespit edilemedi: Fatura CIF, LC 32B

**HUKUKİ DEĞERLENDİRME:**

Miktar, tutar ve birim fiyattaki +/- %5 ve %10 tolerans kuralları (:39A:).

UCP 600 Art 30 kapsamındaki tutar kontrolü için fatura CIF ve LC 32B alanının her ikisi de gereklidir. Manuel doğrulama yapılmalıdır.

**SONUÇ: ⚠ MANUEL KONTROL**

---

### Art 20 — Yükleme Tarihi

**BULGU:** Tespit edilemedi: B/L Tarihi, 44C

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

UCP 600 Art 20 kapsamındaki yükleme tarihi kontrolü için konşimendo On Board tarihi ve LC 44C alanı gereklidir. Manuel doğrulama yapılmalıdır.

**SONUÇ: ⚠ MANUEL KONTROL**

---

### Art 30 — Kilo

**BULGU:** Tespit edilemedi: Fatura Kilo, B/L Kilo

**HUKUKİ DEĞERLENDİRME:**

Miktar, tutar ve birim fiyattaki +/- %5 ve %10 tolerans kuralları (:39A:).

Ağırlık karşılaştırması yapılamadı. Belgelerde kilo bilgisi farklı formatta veya eksik olabilir.

**SONUÇ: ⚠ MANUEL KONTROL**

---


## Konşimento

* [REZERV] Konşimento belgesi yok!

## 46A Belge Şartları

| Belge Şartı | Detay | Durum |
|:---|:---|:---|
| 46A | MT700 46A tespit edilemedi. | **MANUEL KONTROL** |
| Packing List İçerik | Bulunan: GROSS WEIGHT, NET WEIGHT, CBM, PACKAGE DETAILS, NUMBER OF PACKAGES, PALLET, MARKS, PACKING LIST | Eksik: MEASUREMENT, CARTON | **UYUMLU** |

## Tespit Edilen Rezervler

* REZERV — Konşimento ibraz edilmemiş (Art 20)

## Rezerv Kategorileri

| Kod | Kategori | Puan | Süre |
|:---|:---|:---|:---|
| ibraz_suresi_belirsiz | **MINOR DISCREPANCY** | 5 | Aynı Gün |
| konsimento_eksik | **MAJOR DISCREPANCY** | 25 | 3-5 Gün |

## Risk Değerlendirmesi

* Risk Puanı: **30** — ORTA RİSK
* Uyumluluk: **%65**
* 1. REZERV — Konşimento ibraz edilmemiş (Art 20)

## SWIFT Rezerv Simülatörü

### Ret Metni 1

```
DOCUMENTS REJECTED.
FULL SET ORIGINAL B/L NOT PRESENTED.
UCP 600 ART 20.
```

