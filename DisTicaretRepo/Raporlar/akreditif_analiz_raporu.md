# AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0

**Tarih:** 23.06.2026 06:09 | Motor: UCP 600 & ISBP 821

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
| Rezerv | 1 (MAJOR: 1) |
| Uyumluluk | **%80** |
| Banka Kabul | **%75** |
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
| Sigorta ≥ CIF × 110% (Art 28f-ii) | Sigorta:26,334.00 < Min:26,334.00 | **REZERV - YETERSİZ TEMİNAT** |
| Menşe (Origin) Analizi | Certificate of Origin belgesi mevcut. | **UYUMLU** |

## Konşimento

* [TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii).
* [TAMAM] Kirli/klozlu ifade bulunamadı (Art 27 uyumlu).

## 46A Belge Şartları

| Belge | Detay | Durum |
|:---|:---|:---|
| 46A | MT700 46A tespit edilemedi. | **MANUEL KONTROL** |
| Packing List İçerik | Bulunan: GROSS WEIGHT, NET WEIGHT, CBM, PACKAGE DETAILS, NUMBER OF PACKAGES, PALLET, MARKS, PACKING LIST | Eksik: MEASUREMENT, CARTON | **UYUMLU** |

## Tespit Edilen Rezervler

* REZERV — Sigorta yetersiz: 26,334.00 < 26,334.00

## Rezerv Kategorileri

| Kod | Kategori | Puan | Süre |
|:---|:---|:---|:---|
| sigorta_eksik | **MAJOR DISCREPANCY** | 25 | 2-3 Gün |

## Risk Değerlendirmesi

* Risk Puanı: **25** — ORTA RİSK
* Uyumluluk: **%80**
* 1. REZERV — Sigorta yetersiz: 26,334.00 < 26,334.00
