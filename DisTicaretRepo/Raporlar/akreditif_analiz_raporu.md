# AKREDİTİF GELİŞMİŞ HUKUKİ VE SAYISAL UZMAN DENETİM RAPORU v9.0

**Tarih:** 27.06.2026 23:04 | Motor: UCP 600 & ISBP 821

---

## Dosya Durum Raporu

| Dosya | Var | OCR | Sınıf | Parse | Puan |
|:---|:---|:---|:---|:---|:---|
| Kusat.txt | V | V | KUSAT | V | 999 |
| BILL OF LADING.txt | V | V | KONSIMENTO | V | 999 |
| slinecek.txt | V | X | - | X | 0 |
| COMMERCIAL INVOICE.txt | V | V | FATURA | V | 999 |
| insurance certificate.txt | V | V | SIGORTA | V | 999 |
| PACKING LIST.txt | V | V | CEKI_LISTESI | V | 999 |

---

## Yönetici Özeti

| Metrik | Değer |
|:---|:---|
| LC No | **LC-AMEX-2026-7890** |
| Belgeler | KUSAT, FATURA, KONSIMENTO, CEKI_LISTESI, SIGORTA |
| Rezerv | 1 (MAJOR: 1) |
| Uyumluluk | **%70** |
| Banka Kabul | **%65** |
| Risk | ORTA RİSK |

---

## MT700 Alan Analizi

| Alan | Açıklama | Değer | Durum |
|:---|:---|:---|:---|
| **20** | Documentary Credit Number | `LC-AMEX-2026-7890` | TESPİT EDİLDİ |
| **31D** | Expiry Date | `15.07.2026 / TURKEY` | TESPİT EDİLDİ |
| **32B** | Amount | `USD 23.940,00` | TESPİT EDİLDİ |
| **40A** | Form | `IRREVOCABLE` | TESPİT EDİLDİ |
| **44C** | Latest Shipment | `05.07.2026` | TESPİT EDİLDİ |
| **45A** | Description of Goods | `TEXTILE FABRICS (100% COTTON, DYED) HS Code: 5208.31.00.00.00` | TESPİT EDİLDİ |
| **46A** | Documents Required | `1. COMMERCIAL INVOICE in 3 originals and 3 copies, signed by the Beneficiary, indicating L/C No. and` | TESPİT EDİLDİ |

---

## Vade Analizi

* En Geç Yükleme (44C): **05.07.2026**
* İbraz Süresi: **10 gün** (max 21)

## Ödeme Vadesi

* Ödeme: **Vadeli** — poliçe takvimi kontrol edilmeli.

## Incoterms & Sigorta

* Incoterms: **CIF (ICC 2020)**
* [TAMAM] CIF — Sigorta belgesi mevcut.


## MT700 Hukuki Değerlendirme

### Alan 20 — Documentary Credit Number

**Bulunan Değer:** `LC-AMEX-2026-7890`

**Açıklama:** Akreditifin benzersiz referans numarasıdır.

**UCP/ISBP Yorumu:** Tüm ibraz belgelerinde (fatura, konşimento, sigorta poliçesi) aynı LC referansının kullanılması banka uygulamasında tavsiye edilir. Farklı referans kullanımı Art 14(a) kapsamında inceleme gerektirebilir.

**İlgili Madde:** UCP 600 Art 14(a)

**Risk / Sonuç:** **BİLGİ**

---

### Alan 31D — Expiry Date & Place

**Bulunan Değer:** `15.07.2026 / TURKEY`

**Açıklama:** Akreditifin son geçerlilik tarihi ve yeridir.

**UCP/ISBP Yorumu:** UCP 600 Art 6(d)(i): Bu tarihten sonra yapılan belgeli ibrazlar banka tarafından reddedilebilir. Geçerlilik yeri, ibrazın nerede yapılacağını belirler. Art 29(a): Son gün resmi tatile gelirse bir sonraki iş gününe uzar.

**İlgili Madde:** UCP 600 Art 6 / Art 29

**Risk / Sonuç:** **BİLGİ**

---

### Alan 32B — Currency & Amount

**Bulunan Değer:** `USD 23.940,00`

**Açıklama:** Akreditifin para birimi ve tutarıdır.

**UCP/ISBP Yorumu:** UCP 600 Art 30(b) uyarınca akreditif tutarında %5 tolerans uygulanabilir. Akreditifte 'ABOUT' veya 'APPROXIMATELY' ifadesi varsa tolerans %10'a çıkar. Art 18(a)(iii): Fatura akreditifle aynı para biriminde düzenlenmelidir. Eşitlik durumu (sapma = 0) her koşulda uyumludur.

**İlgili Madde:** UCP 600 Art 18 / Art 30

**Karşılaştırma:** LC Tutarı: 23,940.00 | Fatura CIF: 23,940.00 | Sapma: %+0.00

**Risk / Sonuç:** **✓ UYUMLU**

---

### Alan 40A — Form of Documentary Credit

**Bulunan Değer:** `IRREVOCABLE`

**Açıklama:** Akreditifin türüdür (IRREVOCABLE, TRANSFERABLE vb.).

**UCP/ISBP Yorumu:** UCP 600 Art 3: Akreditif aksine hüküm olmadıkça gayrikabili rücudur. Art 10: IRREVOCABLE akreditif tüm tarafların onayı olmadan değiştirilemez. Art 38: TRANSFERABLE akreditif birinci lehdar tarafından devredebilir; devir yalnızca bir kez yapılabilir.

**İlgili Madde:** UCP 600 Art 3 / Art 10 / Art 38

**Risk / Sonuç:** **BİLGİ**

---

### Alan 44C — Latest Date of Shipment

**Bulunan Değer:** `05.07.2026`

**Açıklama:** Malların en geç yüklenebileceği tarihtir.

**UCP/ISBP Yorumu:** UCP 600 Art 20(a)(ii): Konşimentodaki 'Shipped on Board' tarihi bu tarihi geçemez. Art 14(c): Geç yükleme doğrudan MAJOR DISCREPANCY sebebidir. ISBP 821 E5: Tarih çelişkisi varsa en erken tarih esas alınır. Art 29(c): Son yükleme tarihi, geçerlilik tarihi uzamasından etkilenmez.

**İlgili Madde:** UCP 600 Art 14(c) / Art 20 / ISBP 821 E5

**Karşılaştırma:** Son Yükleme: 05.07.2026 | B/L tarihi tespit edilemedi.

**Risk / Sonuç:** **MANUEL KONTROL**

---

### Alan 45A — Description of Goods

**Bulunan Değer:** `TEXTILE FABRICS (100% COTTON, DYED) HS Code: 5208.31.00.00.00`

**Açıklama:** LC'nin mal tanımıdır.

**UCP/ISBP Yorumu:** UCP 600 Art 18(c): Ticari faturadaki mal tanımı LC'deki tanımla uyumlu olmalıdır; daha genel ifade kullanılabilir ancak çelişkili ifade kullanılamaz. Art 14(e): Diğer belgelerde (B/L, PL) mal tanımı LC ile çelişmemelidir; genel terimler kabul edilir. ISBP 821 C3: Kısaltmalar kabul edilir.

**İlgili Madde:** UCP 600 Art 18(c) / Art 14(e) / ISBP 821 C3

**Karşılaştırma:** Fatura mal tanımı örtüşme oranı: %67

**Risk / Sonuç:** **⚠ DÜŞÜK BENZERLİK**

---

### Alan 46A — Documents Required

**Bulunan Değer:** `1. COMMERCIAL INVOICE in 3 originals and 3 copies, signed by the Beneficiary, indicating L/C No. and date.
2. PACKING LIST in 3 originals and 3 copies, showing gross weight, net weight, measurement an`

**Açıklama:** İbraz edilmesi zorunlu belgeler listesidir.

**UCP/ISBP Yorumu:** UCP 600 Art 14(a): Bu alanda talep edilen her belgenin eksiksiz ibraz edilmesi zorunludur; eksik belge doğrudan ret sebebidir. Art 17(a): Her belgeden en az bir orijinal sunulmalıdır. ISBP 821 A21: Belge sayısı belirtilmişse o kadar orijinal sunulmalıdır. Art 14(f): Belge türü belirtilmiş ancak içeriği tarif edilmemişse, işlevini yerine getiren her belge kabul edilir.

**İlgili Madde:** UCP 600 Art 14(a) / Art 17(a) / ISBP 821 A21

**Risk / Sonuç:** **✓ UYUMLU**

---


## Çapraz Kontroller

| Belgeler | Detay | Durum |
|:---|:---|:---|
| Tutar LC vs Fatura (Art 30) | LC:23,940.00 | Fatura CIF:23,940.00 | Sapma:+0.0% | Tolerans:±%5 | **UYUMLU** |
| Kilo: Fatura vs B/L | Tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Kilo: Fatura vs Packing List | Tespit edilemedi: Fatura | **MANUEL KONTROL** |
| Kilo: Packing List vs B/L | Eşleşti: 3,420.00 KG | **UYUMLU** |
| Mal Tanımı LC vs Fatura (Art 18c) | LC:TEXTILE FABRICS (100% COTTON, DYED) HS Code: 5208.31.00.00.0 | Fatura:12 PALLETS TEXTILE FABRICS (100% COTTON, DYED) | %67 | **DÜŞÜK BENZERLİK - MANUEL KONTROL** |
| B/L Tarihi vs 44C (Art 20) | B/L:- | 44C:05.07.2026 | **MANUEL KONTROL** |
| Sigorta ≥ CIF × 110% (Art 28f-ii) | CIF:23,940.00 | Min(×110%):26,334.00 | Sigorta:26,334.00 | **UYUMLU** |
| Menşe (Origin) Analizi | Origin: TÜRKİYE | Kaynak: Commercial Invoice | Ayrı CO belgesi ibraz edilmedi; fatura beyanı kabul edildi. | **UYUMLU** |

## UCP 600 Hukuki Kontroller

### Art 14 — Belge İnceleme Standardı

**BULGU:** Belgeler UCP 600 Art 14 kapsamında incelendi.

**HUKUKİ DEĞERLENDİRME:**

Belge inceleme standardı. İbraz süresi belirtilmemişse en fazla 21 gündür.

Art 14(b): 5 iş günü. Art 14(d): Çelişki olmamalı; birebir aynı olmak zorunda değil.

**SONUÇ: ⚠ BİLGİ**

---

### Art 30 — Tutar Toleransı

**BULGU:** CIF:23,940.00 | LC:23,940.00 | Sapma:%+0.0

**HUKUKİ DEĞERLENDİRME:**

Miktar, tutar ve birim fiyattaki +/- %5 ve %10 tolerans kuralları (:39A:).

Art 30(b) standart %5. Sapma %0.0 ≤ %5. Rezerv yok.

**SONUÇ: ✓ UYUMLU**

---

### Art 18 — Fatura Ağırlık

**BULGU:** Faturada gross weight bulunamadı.

**HUKUKİ DEĞERLENDİRME:**

Ticari fatura lehtar adına düzenlenmeli ve akreditif döviz cinsinden olmalıdır.

Art 18 faturada kilo zorunlu kılmaz. PL/BL doğrulaması yeterli. Bulunamadı≠Yok.

**SONUÇ: ⚠ BİLGİ**

---

### Art 27 — Temiz Konşimento

**BULGU:** Olumsuz kloz bulunamadı.

**HUKUKİ DEĞERLENDİRME:**

Temiz taşıma belgesi (Clean Bill of Lading) şartı. Malda hasar ibaresi olmamalı.

Art 27 şartı karşılandı.

**SONUÇ: ✓ UYUMLU**

---

### Art 20 — Shipped on Board

**BULGU:** On Board şerhi mevcut.

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

Art 20(a)(ii): Şart karşılandı.

**SONUÇ: ✓ UYUMLU**

---

### Art 20 — Yükleme Tarihi

**BULGU:** Tespit edilemedi: B/L Tarihi

**HUKUKİ DEĞERLENDİRME:**

Deniz konşimentosu (Kaptan/Acente imzası, On Board notu).

Veri eksikliği rezerv değil. Manuel doğrulama.

**SONUÇ: ⚠ MANUEL KONTROL**

---

### Art 18 — Kilo (B/L)

**BULGU:** B/L Gross Weight:3,420.00 KG (Fatura kilo içermiyor)

**HUKUKİ DEĞERLENDİRME:**

Ticari fatura lehtar adına düzenlenmeli ve akreditif döviz cinsinden olmalıdır.

Art 18 faturada kilo zorunlu kılmaz. B/L referans alındı.

**SONUÇ: ⚠ BİLGİ**

---

### Art 28(f)(ii) — Sigorta Teminatı

**BULGU:** CIF:23,940.00 | Min:26,334.00 | Poliçe:26,334.00

**HUKUKİ DEĞERLENDİRME:**

Art 28(f)(ii): CIF×110% karşılandı. Incoterms 2020 CIF: satıcı yükümlüsü. Rezerv yok.

**SONUÇ: ✓ UYUMLU**

---


## Konşimento

* [TAMAM] 'Shipped on Board' şerhi mevcut (Art 20a-ii).
* [TAMAM] Kirli/klozlu ifade bulunamadı (Art 27 uyumlu).

## 46A Belge Şartları

| Belge Şartı | Detay | Durum |
|:---|:---|:---|
| Ticari Fatura | 46A'da talep edildi. | **VAR** |
| Ticari Fatura | 46A'da talep edildi. | **VAR** |
| Konşimento | 46A'da talep edildi. | **VAR** |
| Packing List | 46A'da talep edildi. | **VAR** |
| Sigorta Poliçesi | 46A'da talep edildi. | **VAR** |
| Packing List İçerik | Bulunan: GROSS WEIGHT, NET WEIGHT, CBM, PACKAGE DETAILS, NUMBER OF PACKAGES, PALLET, MARKS, PACKING LIST | Eksik: MEASUREMENT, CARTON | **UYUMLU** |

## Tespit Edilen Rezervler

* REZERV — B/L yükleme tarihi tespit edilemedi (Art 20)

## Rezerv Kategorileri

| Kod | Kategori | Puan | Süre |
|:---|:---|:---|:---|
| mal_tanimi_uyusmazligi | **MEDIUM DISCREPANCY** | 10 | 1 Gün |
| yukleme_tarihi_ihlali | **MAJOR DISCREPANCY** | 25 | Akreditif değişikliği |

## Risk Değerlendirmesi

* Risk Puanı: **35** — ORTA RİSK
* Uyumluluk: **%70**
* 1. REZERV — B/L yükleme tarihi tespit edilemedi (Art 20)
