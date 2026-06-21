# AKREDITIF ANALIZ RAPORU v8.0

**Tarih:** 21.06.2026 23:02 | Motor: UCP 600 & ISBP 821

---

## Dosya Durum Raporu

| Dosya | Var | OCR | Sinif | Parse | Puan |
|:---|:---|:---|:---|:---|:---|
| Fatura.txt | V | V | FATURA | V | 999 |
| slinecek.txt | V | X | - | X | 0 |
| Küşat.txt | V | V | KUSAT | V | 999 |
| packing list.txt | V | V | CEKI_LISTESI | V | 999 |
| Bill of lading.txt | V | V | KONSIMENTO | V | 999 |
| insurance certificate.txt | V | V | SIGORTA | V | 999 |

---

## Yonetici Ozeti

| Metrik | Deger |
|:---|:---|
| Belgeler | KUSAT, FATURA, KONSIMENTO, CEKI_LISTESI, SIGORTA |
| Rezerv | 1 (MAJOR: 1) |
| Uyumluluk | **%80** |
| Banka Kabul | **%75** |
| Risk | ORTA RİSK |

---

## MT700 Alan Analizi

| Alan | Aciklama | Deger | Durum |
|:---|:---|:---|:---|
| **20** | Documentary Credit Number | `—` | TESPIT EDILEMEDI |
| **31D** | Expiry Date | `—` | TESPIT EDILEMEDI |
| **32B** | Amount | `—` | TESPIT EDILEMEDI |
| **40A** | Form | `—` | TESPIT EDILEMEDI |
| **44C** | Latest Shipment | `—` | TESPIT EDILEMEDI |
| **45A** | Description of Goods | `—` | TESPIT EDILEMEDI |
| **46A** | Documents Required | `—` | TESPIT EDILEMEDI |

---

## Vade Analizi

* En Gec Yukleme (44C): Tespit edilemedi — manuel kontrol.
* Ibraz Suresi: **10 gun** (max 21)

## Odeme Vadesi

* Odeme: **Vadeli** — poliçe takvimi kontrol edilmeli.

## Incoterms & Sigorta

* Incoterms: **CIF (ICC 2020)**
* [TAMAM] CIF — Sigorta belgesi mevcut.

## Capraz Kontroller

| Belgeler | Detay | Durum |
|:---|:---|:---|
| Tutar LC vs Fatura (Art 30) | LC:23,940.00 | Fatura CIF:23,940.00 | Sapma:+0.0% | Tolerans:±%5 | **UYUMLU** |
| Kilo: Fatura vs B/L | Tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Kilo: Fatura vs Packing List | Tespit edilemedi: Fatura, Packing List | **MANUEL KONTROL** |
| Kilo: Packing List vs B/L | Tespit edilemedi: Packing List | **MANUEL KONTROL** |
| Mal Tanimi LC vs Fatura (Art 18c) | Tespit edilemedi: 45A  | **MANUEL KONTROL** |
| B/L Tarihi vs 44C (Art 20) | B/L:20.06.2026 | 44C:- | **MANUEL KONTROL** |
| Sigorta >= CIF x 110% (Art 28f-ii) | Sigorta:26,334.00 < Min:26,334.00 | **REZERV - YETERSIZ TEMINAT** |
| Mense (Origin) Analizi | Certificate of Origin belgesi mevcut. | **UYUMLU** |

## Konsimento

* [TAMAM] 'Shipped on Board' serhi mevcut (Art 20a-ii).
* [TAMAM] Kirli/klozlu ifade bulunamadi (Art 27 uyumlu).

## 46A Belge Sartlari

| Belge | Detay | Durum |
|:---|:---|:---|
| 46A | MT700 46A tespit edilemedi. | **MANUEL KONTROL** |
| Packing List Icerik | Bulunan: CBM, PACKAGE DETAILS, PALLET, MARKS, PACKING LIST | Eksik: GROSS WEIGHT, NET WEIGHT, MEASUREMENT, NUMBER OF PACKAGES, CARTON | **UYUMLU** |

## Tespit Edilen Rezervler

* REZERV — Sigorta yetersiz: 26,334.00 < 26,334.00

## Rezerv Kategorileri

| Kod | Kategori | Puan | Sure |
|:---|:---|:---|:---|
| sigorta_eksik | **MAJOR DISCREPANCY** | 25 | 2-3 Gun |

## Risk Degerlendirmesi

* Risk Puani: **25** — ORTA RİSK
* Uyumluluk: **%80**
* 1. REZERV — Sigorta yetersiz: 26,334.00 < 26,334.00

## SWIFT Rezerv Simulatoru

### Ret Metni 1

```
DOCUMENTS REJECTED.
INSURANCE DOCUMENT NOT PRESENTED.
UCP 600 ART 28.
```

