# AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0

**Tarih:** 24.06.2026 02:44 | Motor: UCP 600 & ISBP 821

---

## Dosya Durum Raporu

| Dosya | Var | OCR | Sınıf | Parse | Puan |
|:---|:---|:---|:---|:---|:---|
| Fatura.txt | V | V | FATURA | V | 999 |
| slinecek.txt | V | X | - | X | 0 |
| Küşat.txt | V | V | KUSAT | V | 999 |
| packing list.txt | V | V | CEKI_LISTESI | V | 999 |
| Bill of lading.txt | V | V | KONSIMENTO | V | 999 |
| insurance certificate.txt | V | V | SIGORTA | V | 999 |

---

## Yönetici Özeti

| Metrik | Değer |
|:---|:---|
| LC No | **LC-AMEX-2026-7890** |
| Belgeler | KUSAT, FATURA, KONSIMENTO, CEKI_LISTESI, SIGORTA |
| Rezerv | 0 (MAJOR: 0) |
| Uyumluluk | **%100** |
| Banka Kabul | **%100** |
| Risk | DÜŞÜK RİSK |

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
* İbraz Süresi: **10 gün** (max 21)

## Ödeme Vadesi

* Ödeme: **Vadeli** — poliçe takvimi kontrol edilmeli.

## Incoterms & Sigorta

* Incoterms: **CIF (ICC 2020)**
* [TAMAM] CIF — Sigorta belgesi mevcut.


## Çapraz Kontroller

| Belgeler | Detay | Durum |
|:---|:---|:---|
| Tutar LC vs Fatura (Art 30) | LC:23,940.00 | Fatura CIF:23,940.00 | Sapma:+0.0% | Tolerans:±%5 | **UYUMLU** |
| Kilo: Fatura vs B/L | Tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Kilo: Fatura vs Packing List | Tespit edilemedi: Fatura, Packing List | **MANUEL KONTROL** |
| Kilo: Packing List vs B/L | Tespit edilemedi: Packing List | **MANUEL KONTROL** |
| Mal Tanımı LC vs Fatura (Art 18c) | Tespit edilemedi: 45A  | **MANUEL KONTROL** |
| B/L Tarihi vs 44C (Art 20) | B/L:20.06.2026 | 44C:- | **MANUEL KONTROL** |
| Sigorta ≥ CIF × 110% (Art 28f-ii) | CIF:23,940.00 | Min(×110%):26,334.00 | Sigorta:26,334.00 | **UYUMLU** |
| Menşe (Origin) Analizi | Origin: TÜRKİYE | Kaynak: Commercial Invoice | Ayrı CO belgesi ibraz edilmedi; fatura beyanı kabul edildi. | **UYUMLU** |

## UCP 600 Hukuki Kontroller

### Art 14 — Belge İnceleme Standardı

**BULGU:** Belgeler yüz değerinden incelendi.

**HUKUKİ DEĞERLENDİRME:**

Belge inceleme standardı. İbraz süresi belirtilmemişse en fazla 21 gündür.

UCP 600 Art 14(a): Banka, belgeler temelinde uygun ibraz olup olmadığını belirlemek için sunumu inceler. Art 14(b): İnceleme için en fazla 5 iş günü bulunmaktadır. Art 14(d): Belgeler arasındaki veriler çelişmemelidir; ancak birebir aynı olmak zorunda değildir.

**SONUÇ: ⚠ BİLGİ**

---

### Art 30 — Tutar Toleransı

**BULGU:** CIF: 23,940.00 | LC: 23,940.00 | Sapma: %+0.0

**HUKUKİ DEĞERLENDİRME:**

Miktar, tutar ve birim fiyattaki +/- %5 ve %10 tolerans kuralları (:39A:).

UCP 600 Art 30(b) gereği akreditif tutarında standart %5 tolerans uygulanır. Fatura CIF değeri 23,940.00, LC tutarı 23,940.00 olarak tespit edilmiştir. Sapma %0.0 olup tolerans sınırı içinde kaldığından rezerv oluşmamıştır.

**SONUÇ: ✓ UYUMLU**

---

### Art 27 — Temiz Konşimento

**BULGU:** Olumsuz kloz veya hasar şerhi tespit edilmedi.

**HUKUKİ DEĞERLENDİRME:**

Temiz taşıma belgesi (Clean Bill of Lading) şartı. Malda hasar ibaresi olmamalı.

UCP 600 Art 27: Konşimentoda malın veya ambalajın hasarlı durumunu belirten herhangi bir kloz veya şerh bulunmamaktadır. Belge temiz konşimento niteliğini taşımaktadır.

**SONUÇ: ✓ UYUMLU**

---

### Art 20 — Shipped on Board Şerhi

**BULGU:** On Board şerhi konşimentoda mevcut.

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

UCP 600 Art 20(a)(ii): Konşimenton malların gemiye yüklendiğini 'Shipped on Board' şerhi veya ön baskı ile göstermesi zorunludur. Yükleme tarihi bu şerhin tarihi sayılır.

**SONUÇ: ✓ UYUMLU**

---

### Art 20 — Yükleme Tarihi

**BULGU:** Tespit edilemedi: 44C

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

UCP 600 Art 20 kapsamındaki yükleme tarihi kontrolü için konşimendo On Board tarihi ve LC 44C alanı gereklidir. Manuel doğrulama yapılmalıdır.

**SONUÇ: ⚠ MANUEL KONTROL**

---

### Art 30 — Kilo

**BULGU:** Tespit edilemedi: Fatura Kilo

**HUKUKİ DEĞERLENDİRME:**

Miktar, tutar ve birim fiyattaki +/- %5 ve %10 tolerans kuralları (:39A:).

Ağırlık karşılaştırması yapılamadı. Belgelerde kilo bilgisi farklı formatta veya eksik olabilir.

**SONUÇ: ⚠ MANUEL KONTROL**

---

### Art 28(f)(ii) — Sigorta Teminatı

**BULGU:** CIF: 23,940.00 | Min (×110%): 26,334.00 | Poliçe: 26,334.00

**HUKUKİ DEĞERLENDİRME:**

UCP 600 Art 28(f)(ii) gereği akreditifte farklı bir oran belirtilmemişse sigorta teminatı CIF/CIP değerinin en az %%110'u olmalıdır. Belgelerde CIF değerinin 23,940.00 ve sigorta teminatının 26,334.00 olduğu görülmüştür. Teminat tutarı asgari gerekliliği karşıladığından rezerv oluşmamıştır.

**SONUÇ: ✓ UYUMLU**

---


## Konşimento

* [TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii).
* [TAMAM] Kirli/klozlu ifade bulunamadı (Art 27 uyumlu).

## 46A Belge Şartları

| Belge Şartı | Detay | Durum |
|:---|:---|:---|
| 46A | MT700 46A tespit edilemedi. | **MANUEL KONTROL** |
| Packing List İçerik | Bulunan: GROSS WEIGHT, NET WEIGHT, CBM, PACKAGE DETAILS, NUMBER OF PACKAGES, PALLET, MARKS, PACKING LIST | Eksik: MEASUREMENT, CARTON | **UYUMLU** |

## Tespit Edilen Rezervler

* Kritik rezerv tespit edilmedi.

## Rezerv Kategorileri

| Kod | Kategori | Puan | Süre |
|:---|:---|:---|:---|

## Risk Değerlendirmesi

* Risk Puanı: **0** — DÜŞÜK RİSK
* Uyumluluk: **%100**
