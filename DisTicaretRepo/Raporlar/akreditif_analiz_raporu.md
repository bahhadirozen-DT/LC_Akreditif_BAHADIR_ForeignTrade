# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU

**Tarih:** 19.06.2026 17:31 | **Motor:** UCP 600 & ISBP 821 v7.0

---

## 📁 DOSYA DURUM RAPORU

| Dosya | Bulundu | OCR | Sınıf | Puan |
| :--- | :--- | :--- | :--- | :--- |
| Fatura.txt | ✔ | ✔ | FATURA | 140 |
| slinecek.txt | ✔ | ✖ | — | 0 |
| Küşat.txt | ✔ | ✔ | KUSAT | 150 |
| packing list.txt | ✔ | ✔ | FATURA | 90 |
| Bill of lading.txt | ✔ | ✔ | KONSIMENTO | 180 |
| insurance certificate.txt | ✔ | ✔ | SIGORTA | 85 |

---

## 🏦 YÖNETİCİ ÖZETİ

| Metrik | Değer |
| :--- | :--- |
| Belgeler | KUSAT, FATURA, KONSIMENTO, SIGORTA |
| Tespit Edilen Rezerv | 3 |
| MAJOR Discrepancy | 2 |
| Uyumluluk Skoru | **%55** |
| Banka Kabul Olasılığı | **%40** |
| Risk Sınıfı | YÜKSEK RİSK |

---

## 📡 MT700 ALAN ANALİZİ

| Alan | Açıklama | Değer | Durum |
| :--- | :--- | :--- | :--- |
| **20** | Documentary Credit Number | `—` | ⚠ TESPİT EDİLEMEDİ |
| **31D** | Date and Place of Expiry | `—` | ⚠ TESPİT EDİLEMEDİ |
| **32B** | Currency Code, Amount | `—` | ⚠ TESPİT EDİLEMEDİ |
| **40A** | Form of Documentary Credit | `—` | ⚠ TESPİT EDİLEMEDİ |
| **44C** | Latest Date of Shipment | `—` | ⚠ TESPİT EDİLEMEDİ |
| **45A** | Description of Goods | `TEXTILE FABRICS (100% COTTON, DYED)
HS Code: 5208.31.00.00.00` | ✔ TESPİT EDİLDİ |
| **46A** | Documents Required | `1. COMMERCIAL INVOICE in 3 originals and 3 copies,
 signed by the Beneficiary, indicating L/C No. and date.

2. PACKING ` | ✔ TESPİT EDİLDİ |

---

## 1. Vade Analizi
* En Geç Yükleme Tarihi (44C): Belgeden tespit edilemedi — manuel kontrol.
* İbraz Süresi: **10 gün** (UCP Art 14c — max 21 gün)

## 2. Ödeme Vadesi
* Ödeme Vadesi: **Vadeli/Kabul Kredili** — Poliçe vade takvimini kontrol edin.

## 3. Incoterms & Sigorta
* Incoterms: **CIF (ICC 2020)**
* [TAMAM] CIF teslimde Sigorta Poliçesi mevcut (Art 28 uyumlu).

## 4. Çapraz Kontroller
| Belgeler | Detay | Durum |
| :--- | :--- | :--- |
| Fatura vs LC Tutarı (Art 30) | LC: 23.94 | Fatura: 21.60 | Sapma: -9.8% | Tolerans: ±%5 | **REZERV RİSKİ - TUTAR UYUŞMAZLIĞI** |
| Fatura vs B/L Kilo (Art 14) | Kilo tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Mal Tanımı vs Küşat (Art 18c) | Küşat: 'TEXTILE FABRICS (100% COTTON, DYED)' | Fatura: 'TEXTILE FABRICS (100% COTTON, DYED)' | Benzerlik: %100 | **UYUMLU** |
| B/L Tarihi vs 44C (Art 20) | Tespit edilemedi: B/L tarihi, 44C | **MANUEL KONTROL** |
| Sigorta ≥ Fatura×110% (Art 28f-ii) | Sigorta: 23.94 | Min: 23.76 | **UYUMLU** |

## 5. Konşimento Kontrolü
* [TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii uyumlu).
* [TAMAM] Kirli/klozlu konşimento ifadesi bulunamadı (Art 27 uyumlu).

## 6. 46A Belge Şartları
| Belge | Detay | Durum |
| :--- | :--- | :--- |
| Ticari Fatura | 46A'da talep edildi. | **VAR** |
| Ticari Fatura | 46A'da talep edildi. | **VAR** |
| Konşimento | 46A'da talep edildi. | **VAR** |
| Packing List | 46A'da talep edildi. | **EKSİK** |
| Sigorta Poliçesi | 46A'da talep edildi. | **VAR** |

## 7. ISBP 821 Tablosu
| UCP | ISBP Prensibi | Bulgu | Öneri |
| :--- | :--- | :--- | :--- |
| **Art 30** | ISBP 821 § B14 — Miktar ve Tutar Tolerans | Fatura vs LC Tutarı (Art 30): REZERV RİSKİ - TUTAR UYUŞMAZLIĞI | Fatura tutarının akreditif tutarıyla %5 sapma sınırı içinde kaldığını doğrulayın. |
| **Art 14** | ISBP 821 § A1-A7 — Belge İnceleme Prensipleri | Fatura vs B/L Kilo (Art 14): MANUEL KONTROL | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |
| **Art 18** | ISBP 821 § C1-C23 — Ticari Fatura | Mal Tanımı vs Küşat (Art 18c): UYUMLU | Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. |
| **Art 20** | ISBP 821 § E1-E30 — Konşimento | B/L Tarihi vs 44C (Art 20): MANUEL KONTROL | Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisini doğrulayın. |
| **Art 28** | ISBP 821 § K1-K15 — Sigorta Belgesi | Sigorta ≥ Fatura×110% (Art 28f-ii): UYUMLU | Sigorta poliçesinin döviz cinsini, teminat tutarını ve kapsamı akreditifle karşılaştırın. |
| **Art 14** | ISBP 821 § A1-A7 — Belge İnceleme Prensipleri | 21 günlük ibraz süresi kontrolü uygulandı. | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |

## 8. Tespit Edilen Rezervler
* ⚠ REZERV — Tutar sapması %9.8 > %5 (Art 30)
* ⚠ REZERV — Konşimento yükleme tarihi tespit edilemedi (Art 20)
* ⚠ REZERV — 46A gereği 'Packing List' belgesi eksik

## 9. Rezerv Kategorileri
| Kategori | Sınıf | Puan | Süre |
| :--- | :--- | :--- | :--- |
| tutar_uyusmazligi | **MAJOR DISCREPANCY** | 25 | 1-2 Gün |
| yukleme_tarihi_ihlali | **MAJOR DISCREPANCY** | 25 | Akreditif değişikliği |
| 46a_belge_eksigi | **MEDIUM DISCREPANCY** | 10 | 1-2 Gün |

## 10. Risk Değerlendirmesi
* Risk Puanı: **60** — YÜKSEK RİSK
* Uyumluluk Skoru: **%55**
* 1. REZERV — Tutar sapması %9.8 > %5 (Art 30)
* 2. REZERV — Konşimento yükleme tarihi tespit edilemedi (Art 20)
* 3. REZERV — 46A gereği 'Packing List' belgesi eksik

## 🏛 SWIFT Rezerv Simülatörü

### Ret Metni 1
```
DOCUMENTS REJECTED.

INVOICE AMOUNT EXCEEDS THE CREDIT AMOUNT.
UCP 600 ARTICLE 18 / ARTICLE 30.
```

### Ret Metni 2
```
DOCUMENTS REJECTED.

ONE OR MORE DOCUMENTS AS REQUIRED BY FIELD 46A
OF THE CREDIT HAVE NOT BEEN PRESENTED.
UCP 600 ARTICLE 14(A) / ARTICLE 16.
```

