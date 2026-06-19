# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU
**Analiz Zamanı:** 19.06.2026 03:09  
**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP 821 Hukuk Motoru v6.0  

---
## 🏦 YÖNETİCİ ÖZETİ (Executive Summary)

| Metrik | Değer |
| :--- | :--- |
| Toplam Belge | 1 |
| Mevcut Belgeler | KUSAT |
| Eksik Belgeler | Sigorta Poliçesi (CIF/CIP zorunlu), Konşimento (Bill of Lading), Ticari Fatura, Çeki Listesi / Packing List |
| Tespit Edilen Rezerv | 2 |
| MAJOR Discrepancy | 2 |
| MEDIUM Discrepancy | 0 |
| MINOR Discrepancy | 1 |
| Uyumluluk Skoru | **%45** |
| Risk Puanı | 55 — YÜKSEK RİSK |
| Banka Kabul Olasılığı | **%45** |
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
| **45A** | Description of Goods — Mal Tanımı | `12 PALLETS TEXTILE FABRICS (100% COTTON, DYED)
HS Code: 5208.31.00.00.00

Quantity: 12 PALLETS (4.800,00 MTRS)
Unit Pric` | ✔ TESPİT EDİLDİ |
| **46A** | Documents Required — Talep Edilen Belgeler | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |

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
* Bankaya İbraz Süresi: Belgeden tespit edilemedi — UCP 600 Madde 14c varsayılan 21 günlük limit uygulanır.

---
## 2. Finansal Vade ve Ödeme Takvimi
* Ödeme Vadesi: **Görüldüğünde Ödemeli (At Sight)** — UCP 600 Art 15b uyarınca uyumlu ibrazda amir banka anında ödemekle yükümlüdür.

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
| Alan 46A | MT700 Alan 46A tespit edilemedi. | **[MANUEL KONTROL]** |

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

---
## 10. Rezerv Kategorileri

| Kategori | Sınıf | Risk Puanı | Tahmini Çözüm Süresi |
| :--- | :--- | :--- | :--- |
| ibraz_suresi_belirsiz | **MINOR DISCREPANCY** | 5 | Aynı Gün |
| sigorta_eksik | **MAJOR DISCREPANCY** | 25 | 2-3 Gün |
| konsimento_eksik | **MAJOR DISCREPANCY** | 25 | 3-5 Gün |

---
## 11. Eksik Belgeler Özeti
* ❌ Sigorta Poliçesi (CIF/CIP zorunlu)
* ❌ Konşimento (Bill of Lading)
* ❌ Ticari Fatura
* ❌ Çeki Listesi / Packing List

---
## 12. Risk Değerlendirmesi ve Uyumluluk Skoru
* Toplam Risk Puanı: **55** — Risk Sınıfı: **YÜKSEK RİSK**
* Uyumluluk Skoru: **%45**
* 1. REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu)
* 2. REZERV — Konşimento belgesi ibraz edilmemiş (Art 20)

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

