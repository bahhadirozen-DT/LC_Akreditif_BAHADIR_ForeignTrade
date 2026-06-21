# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU

**Tarih:** 21.06.2026 15:17 | **Motor:** UCP 600 & ISBP 821 v7.0

---

## 📁 DOSYA DURUM RAPORU

| Dosya | Bulundu | OCR | Sınıf | Puan |
| :--- | :--- | :--- | :--- | :--- |
| Fatura.txt | ✔ | ✔ | FATURA | 140 |
| slinecek.txt | ✔ | ✖ | — | 0 |
| Küşat.txt | ✔ | ✔ | CEKI_LISTESI | 155 |
| packing list.txt | ✔ | ✔ | CEKI_LISTESI | 240 |
| Bill of lading.txt | ✔ | ✔ | KONSIMENTO | 180 |
| insurance certificate.txt | ✔ | ✔ | SIGORTA | 85 |

---

## 🏦 YÖNETİCİ ÖZETİ

| Metrik | Değer |
| :--- | :--- |
| Belgeler | FATURA, KONSIMENTO, CEKI_LISTESI, SIGORTA |
| Tespit Edilen Rezerv | 1 |
| MAJOR Discrepancy | 1 |
| Uyumluluk Skoru | **%75** |
| Banka Kabul Olasılığı | **%70** |
| Risk Sınıfı | ORTA RİSK |

---

## 📡 MT700 ALAN ANALİZİ

| Alan | Açıklama | Değer | Durum |
| :--- | :--- | :--- | :--- |
| **20** | Documentary Credit Number | `—` | ⚠ TESPİT EDİLEMEDİ |
| **31D** | Date and Place of Expiry | `—` | ⚠ TESPİT EDİLEMEDİ |
| **32B** | Currency Code, Amount | `—` | ⚠ TESPİT EDİLEMEDİ |
| **40A** | Form of Documentary Credit | `—` | ⚠ TESPİT EDİLEMEDİ |
| **44C** | Latest Date of Shipment | `—` | ⚠ TESPİT EDİLEMEDİ |
| **45A** | Description of Goods | `—` | ⚠ TESPİT EDİLEMEDİ |
| **46A** | Documents Required | `—` | ⚠ TESPİT EDİLEMEDİ |

---

## 1. Vade Analizi
* En Geç Yükleme Tarihi (44C): Belgeden tespit edilemedi — manuel kontrol.
* İbraz Süresi: Tespit edilemedi — UCP Art 14c varsayılan 21 gün uygulanır.

## 2. Ödeme Vadesi
* Ödeme Vadesi: Tespit edilemedi — manuel kontrol önerilir.

## 3. Incoterms & Sigorta
* Incoterms: **CIF (ICC 2020)**
* [TAMAM] CIF teslimde Sigorta Poliçesi mevcut (Art 28 uyumlu).

## 4. Çapraz Kontroller
| Belgeler | Detay | Durum |
| :--- | :--- | :--- |
| Fatura vs LC Tutarı (Art 30) | Tespit edilemedi: LC (32B) | **MANUEL KONTROL** |
| Fatura vs B/L Kilo (Art 14) | Kilo tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Mal Tanımı vs Küşat (Art 18c) | Tespit edilemedi: Küşat 45A | **MANUEL KONTROL** |
| B/L Tarihi vs 44C (Art 20) | Tespit edilemedi: 44C | **MANUEL KONTROL** |
| Sigorta ≥ Fatura×110% (Art 28f-ii) | Sigorta: 23.94 < Min: 26,334.00 | **REZERV RİSKİ - YETERSİZ TEMİNAT** |
| Menşe (Origin) Analizi | LC'de Certificate of Origin şartı tespit edilmedi. | **BİLGİ** |

## 5. Konşimento Kontrolü
* [TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii uyumlu).
* [TAMAM] Kirli/klozlu konşimento ifadesi bulunamadı (Art 27 uyumlu).

## 6. 46A Belge Şartları
| Belge | Detay | Durum |
| :--- | :--- | :--- |
| Packing List İçerik Şartları | Bulunan: CBM, PACKAGE DETAILS, PALLET, MARKS | Eksik: GROSS WEIGHT, NET WEIGHT, MEASUREMENT, PACKING DETAILS, NUMBER OF PACKAGES, CARTON | **UYUMLU** |
| 46A | MT700 46A tespit edilemedi. | **MANUEL KONTROL** |

## 7. ISBP 821 Tablosu
| UCP | ISBP Prensibi | Bulgu | Öneri |
| :--- | :--- | :--- | :--- |
| **Art 30** | ISBP 821 § B14 — Miktar ve Tutar Tolerans | Fatura vs LC Tutarı (Art 30): MANUEL KONTROL | Fatura tutarının akreditif tutarıyla %5 sapma sınırı içinde kaldığını doğrulayın. |
| **Art 14** | ISBP 821 § A1-A7 — Belge İnceleme Prensipleri | Fatura vs B/L Kilo (Art 14): MANUEL KONTROL | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |
| **Art 18** | ISBP 821 § C1-C23 — Ticari Fatura | Mal Tanımı vs Küşat (Art 18c): MANUEL KONTROL | Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. |
| **Art 20** | ISBP 821 § E1-E30 — Konşimento | B/L Tarihi vs 44C (Art 20): MANUEL KONTROL | Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisini doğrulayın. |
| **Art 28** | ISBP 821 § K1-K15 — Sigorta Belgesi | Sigorta ≥ Fatura×110% (Art 28f-ii): REZERV RİSKİ - YETERSİZ TEMİNAT | Sigorta poliçesinin döviz cinsini, teminat tutarını ve kapsamı akreditifle karşılaştırın. |
| **Art 14** | ISBP 821 § A1-A7 — Belge İnceleme Prensipleri | 21 günlük ibraz süresi kontrolü uygulandı. | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |

## 8. Tespit Edilen Rezervler
* ⚠ REZERV — Sigorta teminatı yetersiz: 23.94 < 26,334.00

## 9. Rezerv Kategorileri
| Kategori | Sınıf | Puan | Süre |
| :--- | :--- | :--- | :--- |
| ibraz_suresi_belirsiz | **MINOR DISCREPANCY** | 5 | Aynı Gün |
| sigorta_eksik | **MAJOR DISCREPANCY** | 25 | 2-3 Gün |

## 10. Risk Değerlendirmesi
* Risk Puanı: **30** — ORTA RİSK
* Uyumluluk Skoru: **%75**
* 1. REZERV — Sigorta teminatı yetersiz: 23.94 < 26,334.00

## 🏛 SWIFT Rezerv Simülatörü

### Ret Metni 1
```
DOCUMENTS REJECTED.

INSURANCE DOCUMENT AS REQUIRED BY FIELD 46A
OF THE CREDIT HAS NOT BEEN PRESENTED.
UCP 600 ARTICLE 28.
```

