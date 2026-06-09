# 📋 AKREDİTİF GELİŞMİŞ UZMAN DENETİM RAPORU
**Analiz Zamanı:** 09.06.2026 00:36  
**Altyapı Sistemi:** Yapay Zeka UCP 600 Kural Motoru v2.1  

---
## 1. Kritik Süreler ve Vade Analizi
* En Geç Yükleme Tarihi (Alan 44C): **15.07.2026**
* Bankaya İbraz Süresi: **05.08.2026** (UCP 600 Madde 14c'ye tam uyumlu).

--- 
## 2. Finansal Vade ve Ödeme Takvimi
* <span style='color:#742a2a; font-weight:bold;'>[KRİTİK UYARI]</span> Akreditif metninde ödeme vadesi alanı tetiklenemedi. Manuel poliçe/vade kontrolü gereklidir.

--- 
## 3. Incoterms ve Sigorta Denetimi
* Teslim Şekli Doğrulandı: **CIF**

--- 
## 4. Çapraz Evrak Uyumluluk Kontrolü
| Belgeler | İnceleme Detayı | Durum |
| :--- | :--- | :--- |
| Fatura vs Küşat | Mal tanımı karakter bazlı eşleşme testi yapıldı. | **[UYUMLU]** |

--- 
## 5. Zorunlu UCP 600 Parametreleri
* <span style='color:red;'>[RİSK]</span> 'UCP 600' tabi kural metni Swift mesajında açıkça saptanamadı.

--- 
## 6. UCP 600 Maddeleri ve Uzman Yorum Tablosu
| UCP 600 Madde | Kapsam Açıklaması | Sistem Geçiş Durumu | Uzman Bulgusu |
| :--- | :--- | :--- | :--- |
| **Art 14** | Belgelerin İncelenmesi Standartları | `TESPİT EDİLDİ` | 21 günlük ibraz sınırı uygulandı. |
| **Art 15** | Uyumlu İbraz (Complying Presentation) | `DOĞRUDAN GEÇMİYOR` | Manuel evrak doğrulaması önerilir. |
| **Art 17** | Orijinal Belgeler ve Suretler | `DOĞRUDAN GEÇMİYOR` | Orijinal kaşe/ıslak imza kontrolü yapılmalı. |
| **Art 18** | Ticari Fatura (Commercial Invoice) | `DOĞRUDAN GEÇMİYOR` | Mal tanımının uyumu kritiktir. |
| **Art 20** | Konşimento (Bill of Lading) | `DOĞRUDAN GEÇMİYOR` | Shipped on Board ibaresini arayın. |
| **Art 27** | Temiz Taşıma Belgesi | `DOĞRUDAN GEÇMİYOR` | Hasar veya kirli şerhi bulunmamalı. |
| **Art 30** | Miktar ve Tutarda Toleranslar | `DOĞRUDAN GEÇMİYOR` | %5/%10 tolerans limitlerini kontrol edin. |

> 💡 *Not: Bu rapor otomatik kural eşleştirmeleriyle üretilmiştir. Güvenli dış ticaret için nihai evrak ibrazından önce manuel gözden geçirme tavsiye edilir.*
