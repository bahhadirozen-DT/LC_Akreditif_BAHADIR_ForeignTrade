# AKREDITIF GELISMIS HUKUKI VE SAYISAL UZMAN DENETiM RAPORU
**Analiz Zamani:** 09.06.2026 17:04  
**Altyapi Sistemi:** Yapay Zeka UCP 600 & ISBP Hukuk Motoru v4.0  

---
## 1. Kritik Sureler ve Vade Analizi
* En Gec Yukleme Tarihi (Alan 44C): Belgeden tespit edilemedi — manuel kontrol gerekli.
* Bankaya Ibraz Suresi: Tespit edilemedi — UCP 600 Art 14c varsayilan 21 gun uygulanir.

---
## 2. Finansal Vade ve Odeme Takvimi
* Odeme Vadesi: Belgelerden tespit edilemedi — manuel kontrol onerilir.

---
## 3. Incoterms ve Sigorta Hukuku (ICC 2020 / UCP Art. 28)
* Incoterms Standardi: **CIF (ICC 2020 Rules)**
* [HUKUKi REZERV RiSKi] Teslim sekli CIF olmasina ragmen Sigorta Policesi bulunamadi!

---
## 4. Sayisal ve Capraz Evrak Uyumluluk Kontrolu
| Belgeler | inceleme Detayi | Durum |
| :--- | :--- | :--- |
| Fatura vs Akreditif Tutari (Art 18 / Art 30) | Tutar tespit edilemedi: Fatura, Akreditif (32B) | **[MANUEL KONTROL]** |
| Fatura vs Konsimento Kilo | Fatura: 1,470.00 KG | Konsimento: 2,400.00 KG | **[REZERV RiSKi - UYUMSUZ SAYISAL VERi]** |
| Fatura Mal Tanimi vs Kusat (Art 18c) | Mal tanimi tespit edilemedi: Fatura, Kusat (45A) | **[MANUEL KONTROL]** |
| Konsimento Yukleme Tarihi vs Alan 44C (Art 20) | Tarih tespit edilemedi: Kusat 44C | **[MANUEL KONTROL]** |
| Sigorta Bedeli >= Fatura x %110 (Art 28f-ii) | CIF teslimlerde sigorta policesi zorunludur ancak dosyalar arasinda bulunamadi. | **[REZERV RiSKi - SiGORTA BELGESi EKSiK]** |

---
## 5. Konsimento ve Tasima Hukuku Parametreleri (UCP Art. 20-27)
* [TAMAM] Konsimento uzerinde 'Shipped on Board' serhi saptandi (Art 20a-ii uyumlu).
* [BiLGi] Konsimentoda 'CLEAN' ibaresi bulunamadi — Art 27 kapsaminda manuel kontrol onerilir.

---
## 6. UCP 600 Hukuki Maddeleri ve Uzman Yorum Tablosu
| UCP 600 Madde | Kapsam Aciklamasi | Sistem Gecis Durumu | Uzman Bulgusu |
| :--- | :--- | :--- | :--- |
| **Art 14** | Belgelerin incelenmesi Standartlari | `TESPiT EDiLDi` | Standart 21 gunluk yasal banka ibraz siniri uygulandı. |
| **Art 15** | Uyumlu ibraz (Complying Presentation) | `DOGRUDAN GECMIYOR` | Vesaiklerin bankaya eksiksiz ve hatasiz ulastiginin teyidi. |
| **Art 17** | Orijinal Belgeler ve Suretler | `DOGRUDAN GECMIYOR` | Banka ibrazinda orijinal/suret kaselerinin varligi aranir. |
| **Art 18** | Ticari Fatura (Commercial Invoice) | `DOGRUDAN GECTI` | Mal tariminın kusat metniyle karakter dogrulamasi yapildi (Art 18c). |
| **Art 20** | Konsimento (Bill of Lading) | `TESPiT EDiLDi` | Shipped on Board serhi ve ciro silsilesi hukuki denetimi yapildi. |
| **Art 27** | Temiz Tasima Belgesi | `TESPiT EDiLDi` | Uzerinde hasar veya kusurlu ambalaj serhi bulunmayan temiz belge kontrolu. |
| **Art 28** | Sigorta Belgesi ve Kapsami | `YUKSEK RISK` | CIF teslimlerde Sigorta Policesi zorunludur! Minimum %110 teminat aranir (UCP 600 Madde 28). |
| **Art 30** | Miktar ve Tutarda Toleranslar | `DOGRUDAN GECMIYOR` | Akreditifte aksi belirtilmedikce %5 / %10 tolerans limitleri. |
| **Art 1** | UCP 600 kurallarına tabi olduğu açıkça yazılmalıdır. | `KURAL LISTESI` | UCP 600 |
| **Art 3** | Akreditif gayrikabili rücu (dönülemez) olmalıdır. | `KURAL LISTESI` | IRREVOCABLE |
| **Art 2** | İhbar bankası tanımı eksiksiz olmalıdır. | `KURAL LISTESI` | ADVISING BANK |
| **Art 4** | Akreditif satış sözleşmesinden bağımsız bir işlemdir. | `KURAL LISTESI` | CONTRACT |
| **Art 5** | Bankalar mallarla değil, sadece belgelerle ilgilenir. | `KURAL LISTESI` | DOCUMENTS |
| **Art 6** | Akreditifin geçerli olduğu banka ve ödeme/iştira şekli. | `KURAL LISTESI` | :41A: |
| **Art 7** | Amir bankanın kesin ödeme yükümlülüğü. | `KURAL LISTESI` | ISSUING BANK |
| **Art 8** | Teyit bankasının sorumlulukları ve teyit talimatı (:49:). | `KURAL LISTESI` | CONFIRMING BANK |
| **Art 9** | Değişikliklerin lehtar onayı olmadan yürürlüğe girememe kuralı. | `KURAL LISTESI` | AMENDMENT |
| **Art 10** | Değişikliklerin ihbar edilme usulleri. | `KURAL LISTESI` | ADVISING AMENDMENTS |
| **Art 11** | Teleks/SWIFT mesajlarının ön talimat ve asıl metin ilişkisi. | `KURAL LISTESI` | TELETRANSMITTED |
| **Art 12** | Görevlendirilen bankanın yetki sınırları. | `KURAL LISTESI` | NOMINATED BANK |
| **Art 13** | Bankalar arası rücu ve ramisment anlaşmaları. | `KURAL LISTESI` | REIMBURSEMENT |
| **Art 16** | Rezervli belgelerin reddedilme bildirimi kuralları (en geç 5 iş günü). | `KURAL LISTESI` | DISCREPANT DOCUMENTS |
| **Art 19** | En az iki farklı taşıma modunu kapsayan taşıma belgesi kuralları. | `KURAL LISTESI` | MULTIMODAL |
| **Art 21** | Ciro edilemez deniz yolu taşıma senedi kuralları. | `KURAL LISTESI` | NON-NEGOTIABLE SEA WAYBILL |
| **Art 22** | Kiralık gemi konşimentosu kabul şartları. | `KURAL LISTESI` | CHARTER PARTY |
| **Art 23** | Hava yolu taşıma senedi (Air Waybill) imza ve asıl nüsha kuralları. | `KURAL LISTESI` | AIR TRANSPORT |
| **Art 24** | Karayolu (CMR), demiryolu veya iç su yolu taşıma belgeleri. | `KURAL LISTESI` | ROAD RAIL INLAND |
| **Art 25** | Kurye ve posta alındıları, makbuz tarihleri. | `KURAL LISTESI` | COURIER POST |
| **Art 26** | Gemi güvertesine yükleme (On Deck) ve 'Shipper's load and count' ibareleri. | `KURAL LISTESI` | DECK |
| **Art 29** | Kapanış tarihinin resmi tatile gelmesi durumunda uzama kuralları. | `KURAL LISTESI` | EXPIRY DATE |
| **Art 31** | Kısmi yükleme ve aktarma (Partial Shipments / Transshipments) kuralları. | `KURAL LISTESI` | PARTIAL |
| **Art 32** | Dönemsel/parti parti yüklemelerde bir dönemin kaçırılması durumunda akreditifin hükümsüz kalması. | `KURAL LISTESI` | INSTALMENT |
| **Art 33** | Bankaların çalışma saatleri dışında belge kabul etmeme hakkı. | `KURAL LISTESI` | HOURS |
| **Art 34** | Belgelerin doğruluğu ve hukuki geçerliliği konusunda bankaların sorumsuzluğu. | `KURAL LISTESI` | DISCLAIMER DOCUMENTS |
| **Art 35** | Belgelerin postada kaybolması veya gecikmesi durumunda bankaların sorumsuzluğu. | `KURAL LISTESI` | TRANSMISSION |
| **Art 36** | Mücbir sebep (grev, afet, savaş) durumunda bankaların sorumluluktan muafiyeti. | `KURAL LISTESI` | FORCE MAJEURE |
| **Art 37** | Masrafların kime ait olduğu (:71D:) ve yabancı banka masrafları sorumluluğu. | `KURAL LISTESI` | USER CHARGES |
| **Art 38** | Devredilebilir akreditifler (Transferable L/C) ve birinci/ikinci lehtar ilişkileri. | `KURAL LISTESI` | TRANSFERABLE |
| **Art 39** | Akreditif alacağının temliki (hukuki devri) hakları. | `KURAL LISTESI` | ASSIGNMENT |

---
## 7. Risk Degerlendirmesi ve Rezerv Ozeti
* Toplam Risk Puani: **60** — Risk Sinifi: **YUKSEK RISK**
* 1. REZERV — Sigorta belgesi eksik (CIF teslimde Art 28 zorunlulugu)
* 2. REZERV — Kilo uyumsuzlugu: Fatura 1,470.00 KG / Konsimento 2,400.00 KG
