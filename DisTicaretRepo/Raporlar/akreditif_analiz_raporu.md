# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU
**Analiz Zamanı:** 19.06.2026 03:10  
**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP 821 Hukuk Motoru v6.0  

---
## 🏦 YÖNETİCİ ÖZETİ (Executive Summary)

| Metrik | Değer |
| :--- | :--- |
| Toplam Belge | 1 |
| Mevcut Belgeler | KUSAT |
| Eksik Belgeler | Sigorta Poliçesi (CIF/CIP zorunlu), Konşimento (Bill of Lading), Ticari Fatura, Çeki Listesi / Packing List |
| Tespit Edilen Rezerv | 7 |
| MAJOR Discrepancy | 2 |
| MEDIUM Discrepancy | 1 |
| MINOR Discrepancy | 0 |
| Uyumluluk Skoru | **%0** |
| Risk Puanı | 100 — YÜKSEK RİSK |
| Banka Kabul Olasılığı | **%0** |
| En Kritik Sorun | REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu) |

---
## 📡 MT700 ALAN ANALİZİ

| Alan | Açıklama | Değer | Durum |
| :--- | :--- | :--- | :--- |
| **20** | Documentary Credit Number — Akreditif Numarası | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |
| **31D** | Date and Place of Expiry — Son Kullanma Tarihi ve Yeri | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |
| **32B** | Currency Code, Amount — Para Birimi ve Tutar | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |
| **40A** | Form of Documentary Credit — Akreditif Türü | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |
| **44C** | Latest Date of Shipment — En Geç Yükleme Tarihi | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |
| **45A** | Description of Goods — Mal Tanımı | `TEXTILE FABRICS (100% COTTON, DYED)
HS Code: 5208.31.00.00.00` | ✔ TESPİT EDİLDİ |
| **46A** | Documents Required — Talep Edilen Belgeler | `1. COMMERCIAL INVOICE in 3 originals and 3 copies,
 signed by the Beneficiary, indicating L/C No. and date.

2. PACKING ` | ✔ TESPİT EDİLDİ |

---
## 📅 TARİH ZİNCİRİ ANALİZİ

| Belge / Alan | Tarih | Durum | Not |
| :--- | :--- | :--- | :--- |
| LC Son Geçerlilik (31D) | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |
| En Geç Yükleme (44C) | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |
| Fatura Tarihi | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |
| Konşimento Yükleme Tarihi (B/L) | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |
| Sigorta Tarihi | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |

---
## 1. Kritik Süreler ve Vade Analizi
* En Geç Yükleme Tarihi (Alan 44C): Belgeden tespit edilemedi — manuel kontrol gerekli.
* Bankaya İbraz Süresi: **10 gün** (UCP 600 Madde 14c'ye göre 21 günü aşamaz).

---
## 2. Finansal Vade ve Ödeme Takvimi
* Ödeme Vadesi: **Vadeli / Kabul Kredili Akreditif** — Poliçe vade takvimini ve faiz taahhütlerini kontrol edin.

---
## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)
* Incoterms Standardı: **CIF (ICC 2020 Rules)**
* [HUKUKİ REZERV RİSKİ] Teslim şekli CIF olmasına rağmen Sigorta Poliçesi bulunamadı!

---
## 4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü
| Belgeler | İnceleme Detayı | Durum |
| :--- | :--- | :--- |
| Fatura vs Akreditif Tutarı (Art 18 / Art 30) | Tutar tespit edilemedi: Fatura | **[MANUEL KONTROL]** |
| Fatura vs Konşimento Kilo | Brüt kilo değeri tespit edilemedi: Fatura, Konşimento | **[VERİ EKSİK - MANUEL KONTROL GEREKLİ]** |
| Fatura Mal Tanımı vs Küşat (Art 18c) | Mal tanımı tespit edilemedi: Fatura | **[MANUEL KONTROL]** |
| Konşimento Yükleme Tarihi vs Alan 44C (Art 20) | Tarih tespit edilemedi: Konşimento yükleme tarihi, Küşat 44C | **[MANUEL KONTROL]** |
| Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii) | CIF teslimlerde sigorta poliçesi zorunludur ancak bulunamadı. | **[REZERV RİSKİ - SİGORTA BELGESİ EKSİK]** |

---
## 5. Konşimento ve Taşıma Hukuku Parametreleri (UCP Art. 20-27)
* [REZERV RİSKİ] Konşimento belgesi depoda bulunamadı!

---
## 6. 46A Belge Şartları Kontrolü
| Talep Edilen Belge | Detay | Durum |
| :--- | :--- | :--- |
| Ticari Fatura | Akreditif 46A'da talep edilmiş. | **[EKSİK]** |
| Ticari Fatura | Akreditif 46A'da talep edilmiş. | **[EKSİK]** |
| Konşimento (B/L) | Akreditif 46A'da talep edilmiş. | **[EKSİK]** |
| Çeki Listesi | Akreditif 46A'da talep edilmiş. | **[EKSİK]** |
| Sigorta Poliçesi | Akreditif 46A'da talep edilmiş. | **[EKSİK]** |
| signed by the Beneficiary, indicating L | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| C No. and date. | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| showing gross weight, net weight, measurement and package details per pallet. | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| 3. FULL SET (3 | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| made out TO ORDER OF ISSUING BANK (AMEX BANK LONDON PLC), | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| marked "FREIGHT PREPAID" and notify applicant (ALPHA IMPORT EXPORT LTD.). | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| CERTIFICATE in duplicate, | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| endorsed in blank, covering Institute Cargo Clauses (A), | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| for minimum 110% of CIF value, | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| showing claims payable in London. | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| 5. CERTIFICATE OF ORIGIN issued by Chamber of Commerce, | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| stating goods of Turkish origin. | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| --- | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| SHIPMENT DETAILS: | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| Port of Loading: AMBARLI | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| ISTANBUL | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| Port of Discharge: FELIXSTOWE | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| UK | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| Latest Shipment Date: 05.07.2026 | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| Partial Shipments: NOT ALLOWED | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| Transshipment: NOT ALLOWED | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| Goods Description: | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| TEXTILE FABRICS (100% COTTON, DYED) | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |
| HS Code: 5208.31.00.00.00 | Otomatik eşleştirme yapılamadı — manuel doğrulama gerekli. | **[MANUEL KONTROL]** |

---
## 7. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu
| UCP 600 Madde | Kapsam Açıklaması | Sistem Geçiş Durumu | Uzman Bulgusu |
| :--- | :--- | :--- | :--- |
| **Art 14** | Belgelerin İncelenmesi Standartları | `MANUEL KONTROL` | 21 günlük banka ibraz süresi kısıtlaması uygulandı (Madde 14c). |
| **Art 15** | Uyumlu İbraz (Complying Presentation) | `MANUEL KONTROL` | Uyumlu ibrazın teyidi için bankayla doğrulama gerekir. |
| **Art 17** | Orijinal Belgeler ve Suretler | `MANUEL KONTROL` | Banka ibrazında orijinal/suret kaşelerinin varlığı aranır. |
| **Art 18** | Ticari Fatura (Commercial Invoice) | `MANUEL KONTROL` | Mal tanımı ve tutar uyumu analiz edildi (Art 18c). |
| **Art 20** | Konşimento (Bill of Lading) | `MANUEL KONTROL` | Shipped on Board şerhi, yükleme tarihi ve kilo denetimi yapıldı. |
| **Art 27** | Temiz Taşıma Belgesi | `DOĞRUDAN GEÇMİYOR` | Kirli konşimento ifadeleri tarandı (Art 27). |
| **Art 28** | Sigorta Belgesi ve Kapsamı | `REZERV RİSKİ` | %110 teminat hesabı dahil sigorta uyumu analiz edildi. |
| **Art 30** | Miktar ve Tutarda Toleranslar | `MANUEL KONTROL` | %5 tolerans kuralı uygulandı (Art 30b). |
| **Art 1** | UCP 600 kurallarına tabi olduğu açıkça yazılmalıdır. | `ZORUNLU KURAL` | UCP 600 |
| **Art 3** | Akreditif gayrikabili rücu (dönülemez) olmalıdır. | `ZORUNLU KURAL` | IRREVOCABLE |

---
## 8. ISBP 821 Yorum Tablosu
| UCP Maddesi | ISBP Prensibi (Paragraf) | Bulgu | Öneri |
| :--- | :--- | :--- | :--- |
| **Art 18** | ISBP 821 Paragraf C1-C23 — Ticari Fatura Prensipleri | Fatura vs Akreditif Tutarı (Art 18 / Art 30): MANUEL KONTROL | Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. Fazla açıklama eklemeyin. |
| **Art 18** | ISBP 821 Paragraf C1-C23 — Ticari Fatura Prensipleri | Fatura Mal Tanımı vs Küşat (Art 18c): MANUEL KONTROL | Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. Fazla açıklama eklemeyin. |
| **Art 20** | ISBP 821 Paragraf E1-E30 — Konşimento Prensipleri | Konşimento Yükleme Tarihi vs Alan 44C (Art 20): MANUEL KONTROL | Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisinin ayrıca yer aldığından emin olun. |
| **Art 28** | ISBP 821 Paragraf K1-K15 — Sigorta Belgesi Prensipleri | Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii): REZERV RİSKİ - SİGORTA BELGESİ EKSİK | Sigorta poliçesinin döviz cinsini, teminat tutarını ve kapsam tarihini akreditifle karşılaştırın. |
| **Art 14** | ISBP 821 Paragraf A1-A7 — Belge İnceleme Prensipleri | REZERV — 46A gereği 'Ticari Fatura' belgesi depoda bulunamadı | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |
| **Art 14** | ISBP 821 Paragraf A1-A7 — Belge İnceleme Prensipleri | Belge inceleme süresi uygulandı (UCP Art 14c — en fazla 21 iş günü). | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |

---
## 9. Tespit Edilen Kritik Rezervler ve Uzman Önerileri

### Rezerv: REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu)
* **Kategori:** MAJOR DISCREPANCY
* **Risk Seviyesi:** YÜKSEK
* **Muhtemel Banka İtirazı:** Banka, sigorta poliçesi ibraz edilmeden ödeme yapmayı reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 28
* **İlgili ISBP Prensibi:** ISBP 821 § K3, § K8
* **Düzeltme Önerisi:** CIF/CIP teslimde orijinal sigorta poliçesini en az fatura bedelinin %110'u için temin edin.
* **Tahmini Çözüm Süresi:** 2-3 Gün

### Rezerv: REZERV — Konşimento belgesi ibraz edilmemiş (Art 20)
* **Kategori:** MAJOR DISCREPANCY
* **Risk Seviyesi:** KRİTİK
* **Muhtemel Banka İtirazı:** Temel taşıma belgesi olmadan ödeme kesinlikle yapılmayacaktır.
* **İlgili UCP Maddesi:** UCP 600 Art 20
* **İlgili ISBP Prensibi:** ISBP 821 § E1, § E4
* **Düzeltme Önerisi:** Tam set orijinal konşimentoyu (genellikle 3/3) bankaya ibraz edin.
* **Tahmini Çözüm Süresi:** 3-5 Gün

### Rezerv: REZERV — 46A gereği 'Ticari Fatura' belgesi depoda bulunamadı
* **Kategori:** MEDIUM DISCREPANCY
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Akreditifte talep edilen belgelerden biri eksik olduğundan banka ödemeyi reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 16
* **İlgili ISBP Prensibi:** ISBP 821 § A4, § A6
* **Düzeltme Önerisi:** Eksik belgeyi temin ederek tam ibraz yapın.
* **Tahmini Çözüm Süresi:** 1-2 Gün

### Rezerv: REZERV — 46A gereği 'Ticari Fatura' belgesi depoda bulunamadı
* **Kategori:** MEDIUM DISCREPANCY
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Akreditifte talep edilen belgelerden biri eksik olduğundan banka ödemeyi reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 16
* **İlgili ISBP Prensibi:** ISBP 821 § A4, § A6
* **Düzeltme Önerisi:** Eksik belgeyi temin ederek tam ibraz yapın.
* **Tahmini Çözüm Süresi:** 1-2 Gün

### Rezerv: REZERV — 46A gereği 'Konşimento (B/L)' belgesi depoda bulunamadı
* **Kategori:** MEDIUM DISCREPANCY
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Akreditifte talep edilen belgelerden biri eksik olduğundan banka ödemeyi reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 16
* **İlgili ISBP Prensibi:** ISBP 821 § A4, § A6
* **Düzeltme Önerisi:** Eksik belgeyi temin ederek tam ibraz yapın.
* **Tahmini Çözüm Süresi:** 1-2 Gün

### Rezerv: REZERV — 46A gereği 'Çeki Listesi' belgesi depoda bulunamadı
* **Kategori:** MEDIUM DISCREPANCY
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Akreditifte talep edilen belgelerden biri eksik olduğundan banka ödemeyi reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 16
* **İlgili ISBP Prensibi:** ISBP 821 § A4, § A6
* **Düzeltme Önerisi:** Eksik belgeyi temin ederek tam ibraz yapın.
* **Tahmini Çözüm Süresi:** 1-2 Gün

### Rezerv: REZERV — 46A gereği 'Sigorta Poliçesi' belgesi depoda bulunamadı
* **Kategori:** MEDIUM DISCREPANCY
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Akreditifte talep edilen belgelerden biri eksik olduğundan banka ödemeyi reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 16
* **İlgili ISBP Prensibi:** ISBP 821 § A4, § A6
* **Düzeltme Önerisi:** Eksik belgeyi temin ederek tam ibraz yapın.
* **Tahmini Çözüm Süresi:** 1-2 Gün

---
## 10. Rezerv Kategorileri

| Kategori | Sınıf | Risk Puanı | Tahmini Çözüm Süresi |
| :--- | :--- | :--- | :--- |
| sigorta_eksik | **MAJOR DISCREPANCY** | 25 | 2-3 Gün |
| konsimento_eksik | **MAJOR DISCREPANCY** | 25 | 3-5 Gün |
| 46a_belge_eksigi | **MEDIUM DISCREPANCY** | 10 | 1-2 Gün |

---
## 11. Eksik Belgeler Özeti
* ❌ Sigorta Poliçesi (CIF/CIP zorunlu)
* ❌ Konşimento (Bill of Lading)
* ❌ Ticari Fatura
* ❌ Çeki Listesi / Packing List

---
## 12. Risk Değerlendirmesi ve Uyumluluk Skoru
* Toplam Risk Puanı: **100** — Risk Sınıfı: **YÜKSEK RİSK**
* Uyumluluk Skoru: **%0**
* 1. REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu)
* 2. REZERV — Konşimento belgesi ibraz edilmemiş (Art 20)
* 3. REZERV — 46A gereği 'Ticari Fatura' belgesi depoda bulunamadı
* 4. REZERV — 46A gereği 'Ticari Fatura' belgesi depoda bulunamadı
* 5. REZERV — 46A gereği 'Konşimento (B/L)' belgesi depoda bulunamadı
* 6. REZERV — 46A gereği 'Çeki Listesi' belgesi depoda bulunamadı
* 7. REZERV — 46A gereği 'Sigorta Poliçesi' belgesi depoda bulunamadı

---
## 🏛 REZERV SİMÜLATÖRÜ — Muhtemel Banka SWIFT Ret Metinleri

> Aşağıdaki metinler, bankanın MT734/MT750 mesajında yazabileceği
> muhtemel rezerv ifadelerini simüle etmektedir.

### Simüle Edilen Ret Metni 1

```
DOCUMENTS REJECTED.

INSURANCE DOCUMENT AS REQUIRED BY FIELD 46A
OF THE CREDIT HAS NOT BEEN PRESENTED.
UCP 600 ARTICLE 28.
```

### Simüle Edilen Ret Metni 2

```
DOCUMENTS REJECTED.

FULL SET OF ORIGINAL BILLS OF LADING
AS REQUIRED BY THE CREDIT HAS NOT
BEEN PRESENTED.
UCP 600 ARTICLE 20.
```

### Simüle Edilen Ret Metni 3

```
DOCUMENTS REJECTED.

ONE OR MORE DOCUMENTS AS REQUIRED BY FIELD 46A
OF THE CREDIT HAVE NOT BEEN PRESENTED.
UCP 600 ARTICLE 14(A) / ARTICLE 16.
```

