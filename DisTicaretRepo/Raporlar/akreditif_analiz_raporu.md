# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU
**Analiz Zamanı:** 11.06.2026 05:38  
**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP 821 Hukuk Motoru v6.0  

---
## 🏦 YÖNETİCİ ÖZETİ (Executive Summary)

| Metrik | Değer |
| :--- | :--- |
| Toplam Belge | 3 |
| Mevcut Belgeler | KUSAT, FATURA, KONSIMENTO |
| Eksik Belgeler | Sigorta Poliçesi (CIF/CIP zorunlu), Çeki Listesi / Packing List |
| Tespit Edilen Rezerv | 2 |
| MAJOR Discrepancy | 1 |
| MEDIUM Discrepancy | 1 |
| MINOR Discrepancy | 1 |
| Uyumluluk Skoru | **%65** |
| Risk Puanı | 40 — ORTA RİSK |
| Banka Kabul Olasılığı | **%60** |
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
| **45A** | Description of Goods — Mal Tanımı | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |
| **46A** | Documents Required — Talep Edilen Belgeler | `—` | ⚠ TESPİT EDİLEMEDİ — Manuel Kontrol |

---
## 📅 TARİH ZİNCİRİ ANALİZİ

| Belge / Alan | Tarih | Durum | Not |
| :--- | :--- | :--- | :--- |
| LC Son Geçerlilik (31D) | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |
| En Geç Yükleme (44C) | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |
| Fatura Tarihi | 01.07.2026 | **✔ TESPİT EDİLDİ** |  |
| Konşimento Yükleme Tarihi (B/L) | 10.07.2026 | **✔ TESPİT EDİLDİ** |  |
| Sigorta Tarihi | — | **⚠ TESPİT EDİLEMEDİ** | OCR veya format sorunu olabilir — manuel doğrulama önerilir. |

---
## 1. Kritik Süreler ve Vade Analizi
* En Geç Yükleme Tarihi (Alan 44C): Belgeden tespit edilemedi — manuel kontrol gerekli.
* Bankaya İbraz Süresi: Belgeden tespit edilemedi — UCP 600 Madde 14c varsayılan 21 günlük limit uygulanır.

---
## 2. Finansal Vade ve Ödeme Takvimi
* Ödeme Vadesi: Belgelerden tespit edilemedi — manuel kontrol önerilir.

---
## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)
* Incoterms Standardı: **CIF (ICC 2020 Rules)**
* [HUKUKİ REZERV RİSKİ] Teslim şekli CIF olmasına rağmen Sigorta Poliçesi bulunamadı!

---
## 4. Sayısal ve Çapraz Evrak Uyumluluk Kontrolü
| Belgeler | İnceleme Detayı | Durum |
| :--- | :--- | :--- |
| Fatura vs Akreditif Tutarı (Art 18 / Art 30) | Tutar tespit edilemedi: Fatura, Akreditif (32B) | **[MANUEL KONTROL]** |
| Fatura vs Konşimento Kilo | Fatura: 1,470.00 KG | Konşimento: 2,400.00 KG | **[REZERV RİSKİ - UYUMSUZ SAYISAL VERİ]** |
| Fatura Mal Tanımı vs Küşat (Art 18c) | Mal tanımı tespit edilemedi: Fatura, Küşat (45A) | **[MANUEL KONTROL]** |
| Konşimento Yükleme Tarihi vs Alan 44C (Art 20) | Tarih tespit edilemedi: Küşat 44C | **[MANUEL KONTROL]** |
| Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii) | CIF teslimlerde sigorta poliçesi zorunludur ancak bulunamadı. | **[REZERV RİSKİ - SİGORTA BELGESİ EKSİK]** |

---
## 5. Konşimento ve Taşıma Hukuku Parametreleri (UCP Art. 20-27)
* [TAMAM] Konşimento üzerinde 'Shipped on Board' şerhi saptandı (Art 20a-ii uyumlu).
* [BİLGİ] 'CLEAN' ibaresi bulunamadı ancak kirli konşimento ifadesi de yok — Art 27 kapsamında TEMİZ KONŞİMENTO - MANUEL DOĞRULAMA önerilir.

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
| **Art 20** | Konşimento (Bill of Lading) | `DOĞRUDAN GEÇTİ` | Shipped on Board şerhi, yükleme tarihi ve kilo denetimi yapıldı. |
| **Art 27** | Temiz Taşıma Belgesi | `MANUEL KONTROL` | Kirli konşimento ifadeleri tarandı (Art 27). |
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
| **Art 20** | ISBP 821 Paragraf E1-E30 — Konşimento Prensipleri | [TAMAM] Konşimento üzerinde 'Shipped on Board' şerhi saptandı (Art 20a-ii uyumlu). | Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisinin ayrıca yer aldığından emin olun. |
| **Art 27** | ISBP 821 Paragraf E26-E27 — Temiz Taşıma Belgesi Prensipleri | [BİLGİ] 'CLEAN' ibaresi bulunamadı ancak kirli konşimento ifadesi de yok — Art 27 kapsamında TEMİZ KONŞİMENTO - MANUEL DOĞRULAMA önerilir. | Konşimentonun taşıyıcı tarafından 'clean' olarak düzenlendiğini teyit edin; hasar notu varsa düzeltilmiş yeni konşimento talep edin. |
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

### Rezerv: REZERV — Kilo uyumsuzluğu: Fatura 1,470.00 KG / Konşimento 2,400.00 KG
* **Kategori:** MEDIUM DISCREPANCY
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Banka, belgelerdeki kilo uyumsuzluğunu rezerv olarak bildirebilir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 18
* **İlgili ISBP Prensibi:** ISBP 821 § C10
* **Düzeltme Önerisi:** Fatura ve konşimentodaki kilo değerlerini düzelterek eşleştirin.
* **Tahmini Çözüm Süresi:** 1 Gün

---
## 10. Rezerv Kategorileri

| Kategori | Sınıf | Risk Puanı | Tahmini Çözüm Süresi |
| :--- | :--- | :--- | :--- |
| ibraz_suresi_belirsiz | **MINOR DISCREPANCY** | 5 | Aynı Gün |
| sigorta_eksik | **MAJOR DISCREPANCY** | 25 | 2-3 Gün |
| kilo_uyusmazligi | **MEDIUM DISCREPANCY** | 10 | 1 Gün |

---
## 11. Eksik Belgeler Özeti
* ❌ Sigorta Poliçesi (CIF/CIP zorunlu)
* ❌ Çeki Listesi / Packing List

---
## 12. Risk Değerlendirmesi ve Uyumluluk Skoru
* Toplam Risk Puanı: **40** — Risk Sınıfı: **ORTA RİSK**
* Uyumluluk Skoru: **%65**
* 1. REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu)
* 2. REZERV — Kilo uyumsuzluğu: Fatura 1,470.00 KG / Konşimento 2,400.00 KG

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

GROSS WEIGHT AS SHOWN ON COMMERCIAL INVOICE
DOES NOT CORRESPOND WITH THAT SHOWN ON
BILL OF LADING.
UCP 600 ARTICLE 14 / ISBP 821 § C10.
```

