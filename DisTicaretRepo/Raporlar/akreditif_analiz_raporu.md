# AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0

**Tarih:** 30.06.2026 23:48 | Motor: UCP 600 & ISBP 821

---

## Dosya Durum Raporu

| Dosya | Var | OCR | Sınıf | Parse | Puan |
|:---|:---|:---|:---|:---|:---|
| insurance certificate.docx | V | V | SIGORTA | V | 999 |
| slinecek.txt | V | X | - | X | 0 |
| commercial invoice.docx | V | V | FATURA | V | 999 |
| certificate of origin.docx | V | V | FATURA | V | 60 |
| Kusat.docx | V | V | KUSAT | V | 999 |
| BILL OF LADING.docx | V | V | KONSIMENTO | V | 999 |
| packing list.docx | V | V | CEKI_LISTESI | V | 999 |

---

## Yönetici Özeti

| Metrik | Değer |
|:---|:---|
| LC No | **LC-AMEX-2026-7890** |
| Belgeler | KUSAT, FATURA, KONSIMENTO, CEKI_LISTESI, SIGORTA |
| Rezerv | 2 (MAJOR: 2) |
| Uyumluluk | **%60** |
| Banka Kabul | **%45** |
| Risk | YÜKSEK RİSK |

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

* Incoterms: **FOB (ICC 2020)**


## Çapraz Kontroller

| Belgeler | Detay | Durum |
|:---|:---|:---|
| Tutar LC vs Fatura (Art 30) | LC:25,000.00 | Fatura CIF:14,700.00 | Sapma:-41.2% | Tolerans:±%5 | **REZERV - TUTAR UYUMSUZLUĞU** |
| Kilo: Fatura vs B/L | Tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Kilo: Fatura vs Packing List | Tespit edilemedi: Fatura, Packing List | **MANUEL KONTROL** |
| Kilo: Packing List vs B/L | Tespit edilemedi: Packing List | **MANUEL KONTROL** |
| Mal Tanımı LC vs Fatura (Art 18c) | Tespit edilemedi: 45A  | **MANUEL KONTROL** |
| B/L Tarihi vs 44C (Art 20) | B/L:- | 44C:- | **MANUEL KONTROL** |
| Menşe (Origin) Analizi | Certificate of Origin belgesi mevcut. | **UYUMLU** |

## UCP 600 Hukuki Kontroller

### Art 14 — Belge İnceleme Standardı

**BULGU:** Belgeler UCP 600 Art 14 kapsamında yüz değerinden incelendi.

**HUKUKİ DEĞERLENDİRME:**

Belge inceleme standardı. İbraz süresi belirtilmemişse en fazla 21 gündür.

UCP 600 Art 14(b): İnceleme süresi en fazla 5 iş günüdür. Art 14(d): Belgeler arasındaki veriler çelişmemelidir; birebir aynı olmak zorunda değildir. NOT: Bu satır bilgilendirme amaçlıdır; sistem gerçek zamanlı banka incelemesi yapmaz.

**SONUÇ: ⚠ BİLGİ**

---

### Art 18/30 — Tutar Uyumsuzluğu

**BULGU:** CIF: 14,700.00 | LC: 25,000.00 | Sapma: %-41.2

**HUKUKİ DEĞERLENDİRME:**

Fatura tutarı standart %5 toleransı aşmaktadır. Sapma: %41.2. Bu durum Art 18 / Art 30 kapsamında rezerv sebebidir.

**SONUÇ: ✗ REZERV**

---

### Art 18 — Fatura Ağırlık Bilgisi

**BULGU:** Faturada gross weight ifadesi bulunamadı.

**HUKUKİ DEĞERLENDİRME:**

Ticari fatura lehtar adına düzenlenmeli ve akreditif döviz cinsinden olmalıdır.

UCP 600 Art 18, commercial invoice için ağırlık bilgisini zorunlu kılmaz. Kilo bilgisi Packing List ve Bill of Lading üzerinden doğrulanabiliyorsa faturada bulunmaması rezerv sebebi değildir. Muhakeme: veri yok ≠ rezerv (Talimat #4).

**SONUÇ: ⚠ BİLGİ**

---

### Art 27 — Temiz Konşimento

**BULGU:** Konşimentoda olumsuz kloz veya hasar şerhi bulunamadı.

**HUKUKİ DEĞERLENDİRME:**

Temiz taşıma belgesi (Clean Bill of Lading) şartı. Malda hasar ibaresi olmamalı.

UCP 600 Art 27: Konşimentoda malın veya ambalajın hasarlı durumunu belirten herhangi bir kloz bulunmamaktadır. Temiz konşimento şartı karşılanmıştır.

**SONUÇ: ✓ UYUMLU**

---

### Art 20 — Shipped on Board Şerhi

**BULGU:** On Board şerhi konşimentoda mevcut.

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

UCP 600 Art 20(a)(ii): Konşimenton 'Shipped on Board' şerhi veya ön baskı ile yüklemeyi göstermesi zorunludur. Şart karşılanmıştır.

**SONUÇ: ✓ UYUMLU**

---

### Art 20 — Yükleme Tarihi

**BULGU:** Tespit edilemedi: B/L Tarihi, 44C

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

Veri eksikliği tek başına rezerv sebebi değildir. 44C ve B/L tarihi manuel doğrulanmalıdır.

**SONUÇ: ⚠ MANUEL KONTROL**

---

### Art 18 — Kilo (B/L Bilgisi)

**BULGU:** B/L Gross Weight: 2,000.00 KG (Fatura kilo içermiyor — Art 18 zorunlu kılmaz)

**HUKUKİ DEĞERLENDİRME:**

Ticari fatura lehtar adına düzenlenmeli ve akreditif döviz cinsinden olmalıdır.

UCP 600 Art 18 faturada kilo bilgisi zorunlu kılmaz. B/L ağırlığı 2,000.00 KG olarak tespit edildi. Packing List ile karşılaştırma yapılabiliyorsa yeterlidir.

**SONUÇ: ⚠ BİLGİ**

---

### Art 16 — Rezerv Bildirimi

**BULGU:** Tespit edilen rezerv: 1 adet

**HUKUKİ DEĞERLENDİRME:**

Rezervli belgelerin reddedilme bildirimi kuralları (en geç 5 iş günü).

UCP 600 Art 16(c): Banka uygunsuz ibrazı reddetme hakkına sahiptir. Ret bildirimi en geç 5. iş günü sonuna kadar yapılmalıdır (Art 16(d)). Bildirim ret kararını, her uyumsuzluğu ve belgelerin akıbetini içermelidir.

Uyumsuzluklar:
  [Art 18/30] CIF: 14,700.00 | LC: 25,000.00 | Sapma: %-41.2

**SONUÇ: ⚠ UYARI**

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

* REZERV — Tutar sapması %41.2 > %5 (Art 30)
* REZERV — B/L yükleme tarihi tespit edilemedi (Art 20)

## Rezerv Kategorileri

| Kod | Kategori | Puan | Süre |
|:---|:---|:---|:---|
| ibraz_suresi_belirsiz | **MINOR DISCREPANCY** | 5 | Aynı Gün |
| tutar_uyusmazligi | **MAJOR DISCREPANCY** | 25 | 1-2 Gün |
| yukleme_tarihi_ihlali | **MAJOR DISCREPANCY** | 25 | Akreditif değişikliği |

## Risk Değerlendirmesi

* Risk Puanı: **55** — YÜKSEK RİSK
* Uyumluluk: **%60**
* 1. REZERV — Tutar sapması %41.2 > %5 (Art 30)
* 2. REZERV — B/L yükleme tarihi tespit edilemedi (Art 20)

## SWIFT Rezerv Simülatörü

### Ret Metni 1

```
DOCUMENTS REJECTED.
INVOICE AMOUNT EXCEEDS CREDIT AMOUNT.
UCP 600 ART 18/30.
```

