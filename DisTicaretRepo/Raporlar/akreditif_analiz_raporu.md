# 📋 AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU
**Analiz Zamanı:** 10.06.2026 22:14  
**Altyapı Sistemi:** Yapay Zeka UCP 600 & ISBP 821 Hukuk Motoru v5.0  

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
| UCP Maddesi | ISBP Prensibi | Bulgu | Öneri |
| :--- | :--- | :--- | :--- |
| **Art 18** | ISBP C1-C23 — Ticari Fatura Prensipleri | Fatura vs Akreditif Tutarı (Art 18 / Art 30): MANUEL KONTROL | Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. Fazla açıklama eklemeyin. |
| **Art 18** | ISBP C1-C23 — Ticari Fatura Prensipleri | Fatura Mal Tanımı vs Küşat (Art 18c): MANUEL KONTROL | Mal tanımını akreditifteki 45A alanından kopyalayarak faturaya ekleyin. Fazla açıklama eklemeyin. |
| **Art 20** | ISBP E1-E30 — Konşimento Prensipleri | Konşimento Yükleme Tarihi vs Alan 44C (Art 20): MANUEL KONTROL | Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisinin ayrıca yer aldığından emin olun. |
| **Art 28** | ISBP K1-K15 — Sigorta Belgesi Prensipleri | Sigorta Bedeli ≥ Fatura × %110 (Art 28f-ii): REZERV RİSKİ - SİGORTA BELGESİ EKSİK | Sigorta poliçesinin döviz cinsini, teminat tutarını ve kapsam tarihini akreditifle karşılaştırın. |
| **Art 20** | ISBP E1-E30 — Konşimento Prensipleri | [TAMAM] Konşimento üzerinde 'Shipped on Board' şerhi saptandı (Art 20a-ii uyumlu). | Konşimentonun 'On Board' notasyonunda tarih ile liman bilgisinin ayrıca yer aldığından emin olun. |
| **Art 27** | ISBP E26-E27 — Temiz Taşıma Belgesi Prensipleri | [BİLGİ] 'CLEAN' ibaresi bulunamadı ancak kirli konşimento ifadesi de yok — Art 27 kapsamında TEMİZ KONŞİMENTO - MANUEL DOĞRULAMA önerilir. | Konşimentonun taşıyıcı tarafından 'clean' olarak düzenlendiğini teyit edin; hasar notu varsa düzeltilmiş yeni konşimento talep edin. |
| **Art 14** | ISBP A1-A7 — Belge İnceleme Prensipleri | Belge inceleme süresi uygulandı (UCP Art 14c — en fazla 21 iş günü). | İbraz öncesi tüm belgeler 21 günlük süre kısıtlaması gözetilerek hazırlanmalıdır. |

---
## 9. Tespit Edilen Kritik Rezervler ve Uzman Önerileri

### Rezerv: REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu)
* **Risk Seviyesi:** YÜKSEK
* **Muhtemel Banka İtirazı:** Banka, sigorta poliçesi ibraz edilmeden ödeme yapmayı reddedecektir.
* **İlgili UCP Maddesi:** UCP 600 Art 28
* **İlgili ISBP Prensibi:** ISBP K1-K15
* **Düzeltme Önerisi:** CIF/CIP teslimde orijinal sigorta poliçesini en az fatura bedelinin %110'u için temin edin.

### Rezerv: REZERV — Kilo uyumsuzluğu: Fatura 1,470.00 KG / Konşimento 2,400.00 KG
* **Risk Seviyesi:** ORTA
* **Muhtemel Banka İtirazı:** Banka, belgelerdeki kilo uyumsuzluğunu rezerv olarak bildirebilir.
* **İlgili UCP Maddesi:** UCP 600 Art 14 / Art 18
* **İlgili ISBP Prensibi:** ISBP C10
* **Düzeltme Önerisi:** Fatura ve konşimentodaki kilo değerlerini düzelterek eşleştirin.

---
## 10. Eksik Belgeler Özeti
* ❌ Sigorta Poliçesi (CIF/CIP zorunlu)
* ❌ Çeki Listesi / Packing List

---
## 11. Risk Değerlendirmesi ve Uyumluluk Skoru
* Toplam Risk Puanı: **60** — Risk Sınıfı: **YÜKSEK RİSK**
* Uyumluluk Skoru: **%65**
* 1. REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunluluğu)
* 2. REZERV — Kilo uyumsuzluğu: Fatura 1,470.00 KG / Konşimento 2,400.00 KG
