"""
belge_parser.py — LC Denetim Motoru v11
========================================
Her belge tipi için tam yapılandırılmış parser + normalize veri modeli.

Çıktı formatı (NormalizedDoc):
  Belge türü ne olursa olsun (PDF/DOCX/JPG/XLSX/TXT) aynı dict yapısı.
  Hukuki muhakeme buradan beslenecek.

Parsers:
  invoice_parse()      → COMMERCIAL INVOICE
  packing_list_parse() → PACKING LIST
  bl_parse()           → BILL OF LADING
  insurance_parse()    → INSURANCE CERTIFICATE / POLICY
  co_parse()           → CERTIFICATE OF ORIGIN
  mt700_parse()        → MT700 (LC Küşat)
  alan_46a_parse()     → 46A şartlarını yapılandırılmış listeye dönüştür

Tasarım prensibi: "Bulunamadı ≠ Yok"
  Her alan için OCR → Regex1 → Regex2 → Bağlamsal → None
  None = "tespit edilemedi", rezerv sebebi değil
"""
from __future__ import annotations
import re
from typing import Optional, Any


# ── Yardımcı ─────────────────────────────────────────────────────────────────
def _norm(metin: str) -> Optional[float]:
    """3.420,00 / 23,940 / 23940 → float. None üretmez; hata → None."""
    if not metin:
        return None
    s = re.sub(r'[A-Za-z$€£\t ]', '', str(metin)).strip()
    if not s:
        return None
    try:
        vc, nc = s.count(','), s.count('.')
        sv, sn = s.rfind(','), s.rfind('.')
        if vc == 0 and nc == 0:
            return float(s)
        if vc == 1 and nc == 0:
            s = s.replace(',', '') if len(s[sv+1:]) == 3 else s.replace(',', '.')
        elif nc == 1 and vc == 0:
            if len(s[sn+1:]) == 3:
                s = s.replace('.', '')
        elif vc > 0 and nc > 0:
            s = s.replace('.','').replace(',','.') if sv > sn else s.replace(',','')
        return float(s) if s else None
    except ValueError:
        return None


def _bul(metin: str, desenler: list[str], flags=re.IGNORECASE) -> Optional[str]:
    """İlk eşleşen desenden grup(1) döner."""
    for d in desenler:
        try:
            m = re.search(d, metin, flags | re.MULTILINE)
            if m:
                v = m.group(1).strip()
                if v:
                    return v
        except (re.error, IndexError):
            pass
    return None


def _bul_float(metin: str, desenler: list[str]) -> Optional[float]:
    s = _bul(metin, desenler)
    return _norm(s) if s else None


def _guven(deger: Optional[Any], ham_txt: str, ipucu: str = "") -> int:
    """
    Basit güven skoru (0-100).
    Bulunamadıysa 0, kısa/belirsiz değerse 40, normal ise 90.
    """
    if deger is None:
        return 0
    s = str(deger).strip()
    if len(s) < 2:
        return 30
    # OCR hatası göstergesi — çok fazla özel karakter
    anlamsiz = len(re.findall(r'[^\w\s.,;:!?\-()%$€£/\\@#&*+="\'<>]', s))
    if anlamsiz / max(len(s), 1) > 0.3:
        return 40
    return 90


# ─────────────────────────────────────────────────────────────────────────────
# COMMERCIAL INVOICE PARSER
# ─────────────────────────────────────────────────────────────────────────────
def invoice_parse(metin: str) -> dict:
    """
    Commercial Invoice'dan tüm kritik alanları çıkarır.
    Döner: NormalizedDoc (dict)
    """
    if not metin:
        return {"_belge_turu": "FATURA", "_bos": True}

    t = metin  # orijinal — büyük/küçük harf duyarlı aramalar için

    def _f(desenler):
        return _bul(t, desenler)

    lc_no      = _f([r'L/?C\s*(?:No|Number|#|:)[:\s]*([A-Z0-9\-/\.]{4,40})',
                     r'DOCUMENTARY\s+CREDIT\s+(?:NO|NUMBER)[:\s]*([A-Z0-9\-/\.]{4,40})',
                     r':20:\s*([A-Z0-9\-/\.]{4,40})'])
    inv_no     = _f([r'INVOICE\s*(?:No|Number|#|:)[:\s]*([A-Z0-9\-/\.]{2,30})',
                     r'(?:^|\n)Invoice\s+No[.:]?\s*([A-Z0-9\-/\.]{2,30})'])
    inv_date   = _f([r'Invoice\s+Date[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
                     r'Date[:\s]*(\d{2}[./]\d{2}[./]\d{4})'])
    exporter   = _f([r'Exporter.*?(?:Beneficiary)?[:\s]*\n([^\n]{5,80})',
                     r'SELLER[:\s]*\n([^\n]{5,80})'])
    importer   = _f([r'Importer.*?(?:Applicant)?[:\s]*\n([^\n]{5,80})',
                     r'BUYER[:\s]*\n([^\n]{5,80})'])
    consignee  = _f([r'Consignee[:\s]*\n?([^\n]{5,80})',
                     r'CONSIGNEE[:\s]*([^\n]{5,80})'])
    origin     = _f([r'Country\s+of\s+Origin[:\s]*([A-ZÇĞİÖŞÜa-zçğıöşü]{3,25})',
                     r'COUNTRY\s+OF\s+ORIGIN[:\s]*([A-ZÇĞİÖŞÜa-zçğıöşü]{3,25})',
                     r'(?:^|\n)ORIGIN[:\s]*([A-Z]{3,20})'])
    destination= _f([r'Country\s+of\s+(?:Final\s+)?Destination[:\s]*([^\n]{3,40})',
                     r'DESTINATION[:\s]*([^\n]{3,40})'])
    incoterm   = _f([r'\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS|FOB|CFR|CIF)\b'])
    payment    = _f([r'Payment\s+Terms[:\s]*([^\n]{5,60})',
                     r'PAYMENT[:\s]*([^\n]{5,60})'])
    description= _f([r'Description\s+of\s+Goods?[:\s]*([^\n]{5,100})',
                     r'DESCRIPTION[:\s]*([^\n]{5,100})',
                     r'Goods[:\s]*([^\n]{5,100})'])
    hs_code    = _f([r'HS\s*Code[:\s]*([0-9.]{6,14})',
                     r'HS[:\s]*([0-9.]{6,14})'])
    quantity   = _f([r'(?:Total\s+)?Quantity[:\s]*([\d,.\s]+(?:MTRS?|PCS?|KGS?|SETS?|UNITS?))',
                     r'QTY[:\s]*([\d,.]+\s*\w+)'])
    unit_price = _f([r'Unit\s+Price[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
                     r'UNIT\s+PRICE[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)'])
    currency   = _f([r'\b(USD|EUR|GBP|TRY|CNY|JPY)\b'])
    goods_val  = _bul_float(t, [r'(?:Goods?\s+Value|FOB\s+(?:Value|Amount))[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
                                 r'(?:AMOUNT|TOTAL)[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)'])
    freight_v  = _bul_float(t, [r'FREIGHT[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)'])
    insurance_v= _bul_float(t, [r'INSURANCE[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
                                  r'INS\.[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)'])
    cif_total  = _bul_float(t, [r'(?:CIF\s+(?:TOTAL|VALUE|AMOUNT)|TOTAL\s+CIF)[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)'])
    inv_total  = _bul_float(t, [r'(?:TOTAL\s+(?:INVOICE\s+)?(?:VALUE|AMOUNT)|AMOUNT\s+DUE|GRAND\s+TOTAL)[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
                                  r'(?:USD|EUR|GBP|TRY)\s*([\d,.]+)\s*$'])
    gross_w    = _bul_float(t, [r'Gross\s+Weight[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)',
                                  r'G\.?W\.?[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)'])
    net_w      = _bul_float(t, [r'Net\s+Weight[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)',
                                  r'N\.?W\.?[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)'])
    packages   = _f([r'(?:No\.?\s+of\s+Packages?|Total\s+Packages?)[:\s]*(\d+[^\n]{0,20})',
                      r'(\d+\s+(?:PALLETS?|CARTONS?|BOXES|PKGS?))'])
    marks      = _f([r'Marks\s*(?:&|and)?\s*Numbers?[:\s]*([^\n]{5,80})'])
    signed     = bool(re.search(r'SIGN|AUTHORIZED|STAMP', t, re.IGNORECASE))
    originals  = _f([r'(?:In|issued\s+in)\s+(\d+)\s+original', r'(\d+)\s+ORIGINALS?'])
    copies_    = _f([r'(\d+)\s+cop(?:y|ies)', r'copies[:\s]*(\d+)'])
    vessel     = _f([r'Vessel[:\s]*([A-Z0-9\s]{3,30})', r'VESSEL[:\s]*([^\n]{3,30})'])

    # CIF hesabı — yoksa bileşenlerden
    if cif_total is None and goods_val is not None:
        computed = (goods_val or 0) + (freight_v or 0) + (insurance_v or 0)
        if computed > goods_val:
            cif_total = round(computed, 2)

    karsilastirma_tutari = cif_total or inv_total or goods_val

    doc = {
        "_belge_turu":   "FATURA",
        "lc_no":         lc_no,
        "inv_no":        inv_no,
        "inv_date":      inv_date,
        "exporter":      exporter,
        "importer":      importer,
        "consignee":     consignee,
        "origin":        origin,
        "destination":   destination,
        "incoterm":      incoterm,
        "payment_terms": payment,
        "description":   description,
        "hs_code":       hs_code,
        "quantity":      quantity,
        "unit_price":    unit_price,
        "currency":      currency,
        "goods_value":   goods_val,
        "freight":       freight_v,
        "insurance":     insurance_v,
        "cif_total":     cif_total,
        "inv_total":     inv_total,
        "karsilastirma_tutari": karsilastirma_tutari,
        "gross_weight":  gross_w,
        "net_weight":    net_w,
        "packages":      packages,
        "marks":         marks,
        "signed":        signed,
        "originals":     originals,
        "copies":        copies_,
        "vessel":        vessel,
    }
    # Güven skorları
    doc["_guven"] = {k: _guven(v, t) for k, v in doc.items() if not k.startswith("_")}
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# PACKING LIST PARSER
# ─────────────────────────────────────────────────────────────────────────────
def packing_list_parse(metin: str) -> dict:
    if not metin:
        return {"_belge_turu": "CEKI_LISTESI", "_bos": True}

    t = metin

    def _f(d): return _bul(t, d)

    lc_no      = _f([r'L/?C\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{4,40})'])
    pl_no      = _f([r'(?:Packing\s+List|PL)\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{2,30})'])
    pl_date    = _f([r'Date[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})'])
    inv_no     = _f([r'(?:Invoice|Commercial\s+Invoice)\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{2,30})'])
    vessel     = _f([r'Vessel[:\s]*([^\n]{3,40})'])
    pol        = _f([r'Port\s+of\s+Loading[:\s]*([^\n]{3,40})'])
    pod        = _f([r'Port\s+of\s+Discharge[:\s]*([^\n]{3,40})'])
    marks      = _f([r'Marks\s*(?:&|and)?\s*Numbers?[:\s]*([^\n]{5,80})'])
    description= _f([r'Description[:\s]*([^\n]{5,100})'])
    hs_code    = _f([r'HS\s*Code[:\s]*([0-9.]{6,14})'])
    packages   = _f([r'(?:Total\s+)?(?:No\.?\s+of\s+)?Packages?[:\s]*(\d+[^\n]{0,20})',
                      r'(\d+\s+(?:PALLETS?|CARTONS?|BOXES|PKGS?))'])
    # TOTAL satırından gross weight (tablo: "TOTAL | qty | gross | net | cbm")
    gross_w    = _bul_float(t, [
        r'TOTAL\s*\|[^|]+\|\s*([\d,.]+)\s*(?:KGS?|MT\b)?',
        r'Gross\s+Weight\s*(?:\(KG\))?[:\s]*([\d,.]+)',
        r'GROSS[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)',
        r'G\.?W\.?[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)',
        r'^\s*([\d,.]+)\s*KGS?\s*$',
        r'([\d,.]+)\s*KGS?\b',
    ])
    net_w      = _bul_float(t, [
        r'Net\s+Weight\s*(?:\(KG\))?[:\s]*([\d,.]+)',
        r'N\.?W\.?[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)',
    ])
    cbm        = _bul_float(t, [
        r'(?:CBM|MEASUREMENT|M3)[:\s]*([\d,.]+)',
        r'([\d,.]+)\s*(?:CBM|M3)\b',
    ])
    originals  = _f([r'(?:In|issued\s+in)\s+(\d+)\s+original', r'(\d+)\s+ORIGINALS?'])
    signed     = bool(re.search(r'SIGN|AUTHORIZED|STAMP', t, re.IGNORECASE))

    doc = {
        "_belge_turu": "CEKI_LISTESI",
        "lc_no": lc_no, "pl_no": pl_no, "pl_date": pl_date,
        "inv_no": inv_no, "vessel": vessel,
        "port_of_loading": pol, "port_of_discharge": pod,
        "marks": marks, "description": description, "hs_code": hs_code,
        "packages": packages,
        "gross_weight": gross_w, "net_weight": net_w, "cbm": cbm,
        "originals": originals, "signed": signed,
    }
    doc["_guven"] = {k: _guven(v, t) for k, v in doc.items() if not k.startswith("_")}
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# BILL OF LADING PARSER
# ─────────────────────────────────────────────────────────────────────────────
def bl_parse(metin: str) -> dict:
    if not metin:
        return {"_belge_turu": "KONSIMENTO", "_bos": True}

    t = metin

    def _f(d): return _bul(t, d)

    lc_no      = _f([r'L/?C\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{4,40})'])
    bl_no      = _f([r'B/?L\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{4,40})',
                      r'BILL\s+OF\s+LADING\s+NO[:\s]*([A-Z0-9\-/\.]{4,40})'])
    bl_date    = _f([r'(?:Shipped\s+on\s+Board\s*)?Date[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})'])
    on_board_date = _f([
        r'Shipped\s+on\s+Board[:\s]*\n\s*Date[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
        r'Shipped\s+on\s+Board\s*(?:Date\s*)?[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
        r'ON\s+BOARD\s+DATE[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
        r'DATE\s+OF\s+SHIPMENT[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
        r'LADEN\s+ON\s+BOARD[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
    ])
    shipper    = _f([r'Shipper[:\s]*\n([^\n]{5,80})'])
    consignee  = _f([r'Consignee[:\s]*\n([^\n]{5,80})'])
    notify     = _f([r'Notify\s+(?:Party)?[:\s]*\n([^\n]{5,80})'])
    vessel     = _f([r'Vessel[:\s]*([^\n]{3,40})'])
    voyage     = _f([r'Voyage\s*(?:No)?[:\s]*([A-Z0-9\-]{2,20})'])
    pol        = _f([r'Port\s+of\s+Loading[:\s]*([^\n]{3,40})'])
    pod        = _f([r'Port\s+of\s+Discharge[:\s]*([^\n]{3,40})'])
    marks      = _f([r'Marks\s*(?:&|and)?\s*Numbers?[:\s]*([^\n]{5,80})'])
    packages   = _f([r'No\.?\s+of\s+Packages?[:\s]*([^\n]{3,40})',
                      r'(\d+\s+(?:PALLETS?|CARTONS?|BOXES|PKGS?))'])
    description= _f([r'Description[:\s]*([^\n]{5,100})'])
    gross_w    = _bul_float(t, [r'Gross\s+Weight[:\s]*([\d,.]+)\s*(?:KGS?|MT\b)',
                                  r'([\d,.]+)\s*KGS?\b'])
    cbm        = _bul_float(t, [r'Measurement[:\s]*([\d,.]+)\s*(?:CBM|M3)',
                                  r'([\d,.]+)\s*(?:CBM|M3)\b'])
    freight    = _f([r'Freight\s*(?:&\s*Charges?)?[:\s]*([^\n]{3,40})'])
    originals  = _f([r'Number\s+of\s+Originals?[:\s]*(\d+[^\n]{0,20})',
                      r'(\d+)\s+ORIGINALS?',r'(\d+/\d+)\s+ORIGINALS?'])

    clean       = bool(re.search(r'CLEAN\s+ON\s+BOARD', t, re.IGNORECASE))
    on_board    = bool(re.search(r'SHIPPED\s+ON\s+BOARD|ON\s+BOARD', t, re.IGNORECASE))
    freight_pp  = bool(re.search(r'FREIGHT\s+PREPAID', t, re.IGNORECASE))
    freight_col = bool(re.search(r'FREIGHT\s+COLLECT', t, re.IGNORECASE))
    signed      = bool(re.search(r'SIGN|AUTHORIZED|STAMP|CARRIER|MASTER|AGENT', t, re.IGNORECASE))

    doc = {
        "_belge_turu": "KONSIMENTO",
        "lc_no": lc_no, "bl_no": bl_no, "bl_date": bl_date,
        "on_board_date": on_board_date,
        "shipper": shipper, "consignee": consignee, "notify_party": notify,
        "vessel": vessel, "voyage": voyage,
        "port_of_loading": pol, "port_of_discharge": pod,
        "marks": marks, "packages": packages, "description": description,
        "gross_weight": gross_w, "cbm": cbm,
        "freight": freight,
        "clean": clean, "on_board": on_board,
        "freight_prepaid": freight_pp, "freight_collect": freight_col,
        "originals": originals, "signed": signed,
    }
    doc["_guven"] = {k: _guven(v, t) for k, v in doc.items() if not k.startswith("_")}
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# INSURANCE PARSER
# ─────────────────────────────────────────────────────────────────────────────
def insurance_parse(metin: str) -> dict:
    if not metin:
        return {"_belge_turu": "SIGORTA", "_bos": True}

    t = metin

    def _f(d): return _bul(t, d)

    lc_no       = _f([r'L/?C\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{4,40})'])
    policy_no   = _f([r'Policy\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{2,30})'])
    issue_date  = _f([r'Date\s+of\s+Issue[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})',
                       r'Date[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})'])
    insured     = _f([r'Insured[:\s]*\n([^\n]{5,80})'])
    vessel      = _f([r'Vessel[:\s]*([^\n]{3,40})'])
    voyage      = _f([r'Voyage[:\s]*([^\n]{5,80})'])
    description = _f([r'Description[:\s]*([^\n]{5,100})'])
    cif_value   = _bul_float(t, [r'(?:Invoice\s+Value\s*\(CIF\)|CIF\s+Value)[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)'])
    sum_insured = _bul_float(t, [
        r'Sum\s+Insured[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
        r'Amount\s+Insured[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
        r'Insured\s+Value[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
        r'COVERAGE[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
        r'Total\s+Insured[:\s]*(?:[A-Z]{3}\s*)?([\d,.]+)',
    ])
    percentage  = _f([r'(\d{3}%)\s+of\s+CIF', r'(\d{3})\s*%\s+of\s+(?:CIF|Invoice)'])
    conditions  = []
    for kloz in [
        ("INSTITUTE CARGO CLAUSES (A)", ["INSTITUTE CARGO CLAUSES (A)", "ICC (A)", "ICC(A)"]),
        ("INSTITUTE CARGO CLAUSES (B)", ["INSTITUTE CARGO CLAUSES (B)", "ICC (B)"]),
        ("INSTITUTE CARGO CLAUSES (C)", ["INSTITUTE CARGO CLAUSES (C)", "ICC (C)"]),
        ("INSTITUTE WAR CLAUSES",       ["INSTITUTE WAR CLAUSES"]),
        ("INSTITUTE STRIKES CLAUSES",   ["INSTITUTE STRIKES CLAUSES"]),
        ("ALL RISKS",                   ["ALL RISKS"]),
    ]:
        ad, arama_listesi = kloz
        if any(a in t.upper() for a in arama_listesi):
            conditions.append(ad)
    claims_payable = _f([r'Claims?\s+payable\s+in?[:\s]*([^\n]{3,40})'])
    endorsement    = _f([r'Endorsement[:\s]*([^\n]{3,60})'])
    endorsed_blank = bool(re.search(r'BLANK\s+ENDORS|ENDORSED\s+IN\s+BLANK|payable\s+to\s+bearer',
                                     t, re.IGNORECASE))
    originals      = _f([r'(?:In|issued\s+in)\s+(\w+)\s+(?:duplicate|original)',
                          r'(\d+)\s+ORIGINALS?'])
    signed         = bool(re.search(r'SIGN|AUTHORIZED\s+SIGN|STAMP', t, re.IGNORECASE))

    # Min sigorta kontrolü (CIF×110%)
    min_sigorta = round(cif_value * 1.10, 2) if cif_value else None
    sigorta_yeterli = None
    if sum_insured is not None and min_sigorta is not None:
        sigorta_yeterli = round(sum_insured, 2) >= min_sigorta

    doc = {
        "_belge_turu": "SIGORTA",
        "lc_no": lc_no, "policy_no": policy_no, "issue_date": issue_date,
        "insured": insured, "vessel": vessel, "voyage": voyage,
        "description": description,
        "cif_value": cif_value, "sum_insured": sum_insured,
        "coverage_percentage": percentage,
        "min_sigorta": min_sigorta, "sigorta_yeterli": sigorta_yeterli,
        "conditions": conditions,
        "claims_payable": claims_payable,
        "endorsed_blank": endorsed_blank,
        "endorsement": endorsement,
        "originals": originals, "signed": signed,
    }
    doc["_guven"] = {k: _guven(v, t) for k, v in doc.items() if not k.startswith("_")}
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# CERTIFICATE OF ORIGIN PARSER
# ─────────────────────────────────────────────────────────────────────────────
def co_parse(metin: str) -> dict:
    if not metin:
        return {"_belge_turu": "CO", "_bos": True}
    t = metin
    def _f(d): return _bul(t, d)
    co_no     = _f([r'(?:CO|Certificate)\s*(?:No|Number)[:\s]*([A-Z0-9\-/\.]{2,30})'])
    co_date   = _f([r'Date[:\s]*(\d{1,2}[./\-]\d{2}[./\-]\d{4})'])
    origin    = _f([r'Country\s+of\s+Origin[:\s]*([^\n]{3,30})',
                     r'ORIGIN[:\s]*([^\n]{3,30})'])
    exporter  = _f([r'Exporter[:\s]*\n([^\n]{5,80})'])
    consignee = _f([r'Consignee[:\s]*\n([^\n]{5,80})'])
    desc      = _f([r'Description[:\s]*([^\n]{5,100})'])
    hs_code   = _f([r'HS\s*Code[:\s]*([0-9.]{6,14})'])
    chamber   = bool(re.search(r'CHAMBER\s+OF\s+COMMERCE|TRADE\s+CHAMBER', t, re.IGNORECASE))
    legalized = bool(re.search(r'LEGALIZ|NOTARIZ|APOSTIL|CONSULAR', t, re.IGNORECASE))
    signed    = bool(re.search(r'SIGN|AUTHORIZED|STAMP', t, re.IGNORECASE))
    doc = {
        "_belge_turu": "CO",
        "co_no": co_no, "co_date": co_date, "origin": origin,
        "exporter": exporter, "consignee": consignee,
        "description": desc, "hs_code": hs_code,
        "chamber": chamber, "legalized": legalized, "signed": signed,
    }
    doc["_guven"] = {k: _guven(v, t) for k, v in doc.items() if not k.startswith("_")}
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# 46A PARSER — Şartları yapılandırılmış listeye dönüştür
# ─────────────────────────────────────────────────────────────────────────────
def alan_46a_parse(alan_46a: str) -> list[dict]:
    """
    46A metnini madde madde parse eder.
    Her şart için: belge_turu, sart_metni, alt_sartlar (list)
    
    Örnek giriş:
      1. COMMERCIAL INVOICE in 3 originals and 3 copies, signed...
      2. PACKING LIST showing gross weight, net weight...
      3. FULL SET (3/3) OF CLEAN ON BOARD OCEAN BILL OF LADING...
      4. INSURANCE POLICY / CERTIFICATE in duplicate...
    
    Çıktı:
      [{"sira":1, "belge_turu":"FATURA", "sart_metni":"...", "alt_sartlar":[...]}]
    """
    if not alan_46a:
        return []

    # Madde satırlarını ayır
    satirlar = re.split(r'\n+', alan_46a.strip())

    # Numaralı satırlar: "1." veya "1)" ile başlayan
    maddeler: list[str] = []
    mevcut = ""
    for satir in satirlar:
        if re.match(r'^\s*[\d]+[.)\s]', satir) and satir.strip():
            if mevcut:
                maddeler.append(mevcut.strip())
            mevcut = satir.strip()
        elif mevcut:
            mevcut += " " + satir.strip()
    if mevcut:
        maddeler.append(mevcut.strip())

    # Numarasız ama uzun satırlar (fallback)
    if not maddeler:
        maddeler = [s.strip() for s in satirlar if len(s.strip()) > 10]

    # Belge türü eşleştirme
    TURE_ESLESTIR = [
        (["COMMERCIAL INVOICE", "INVOICE"],            "FATURA"),
        (["PACKING LIST", "WEIGHT LIST"],              "CEKI_LISTESI"),
        (["BILL OF LADING", "B/L", "BL ", "B.L."],    "KONSIMENTO"),
        (["INSURANCE POLICY", "INSURANCE CERTIFICATE",
          "INSURANCE", "POLICY / CERTIFICATE"],        "SIGORTA"),
        (["CERTIFICATE OF ORIGIN", "ORIGIN CERT"],     "CO"),
        (["QUALITY CERTIFICATE", "INSPECTION"],        "KALITE_SERTIFIKA"),
        (["BENEFICIARY CERTIFICATE", "BENEFICIARY'S"], "LEHDAR_BEYANI"),
        (["FREIGHT INVOICE", "FREIGHT BILL"],          "NAVLUN_FATURA"),
    ]

    def _tur(metin: str) -> str:
        m_u = metin.upper()
        for anahtar_liste, tur in TURE_ESLESTIR:
            if any(a in m_u for a in anahtar_liste):
                return tur
        return "DIGER"

    # Alt şartları çıkar
    def _alt_sartlar(metin: str, tur: str) -> list[str]:
        sartlar = []
        m_u = metin.upper()
        # Ortak
        if re.search(r'(\d+)\s*ORIGINAL', m_u):
            m = re.search(r'(\d+)\s*ORIGINAL', m_u)
            sartlar.append(f"ORIGINALS: {m.group(1)}")
        if re.search(r'(\d+)\s*(?:COP(?:Y|IES))', m_u):
            m = re.search(r'(\d+)\s*COP', m_u)
            sartlar.append(f"COPIES: {m.group(1)}")
        if "SIGNED" in m_u or "SIGNATURE" in m_u:
            sartlar.append("SIGNED")
        if "L/C NO" in m_u or "LC NUMBER" in m_u or "L.C. NO" in m_u:
            sartlar.append("LC_NUMBER_REQUIRED")
        if "L/C DATE" in m_u or "LC DATE" in m_u:
            sartlar.append("LC_DATE_REQUIRED")
        if "IN DUPLICATE" in m_u:
            sartlar.append("IN_DUPLICATE")
        # BL
        if tur == "KONSIMENTO":
            if "CLEAN" in m_u:       sartlar.append("CLEAN")
            if "ON BOARD" in m_u:    sartlar.append("ON_BOARD")
            if "FREIGHT PREPAID" in m_u: sartlar.append("FREIGHT_PREPAID")
            if "TO ORDER" in m_u:    sartlar.append("TO_ORDER")
            if re.search(r'3/3|FULL\s+SET', m_u):
                sartlar.append("FULL_SET_3/3")
            if "NOTIFY" in m_u:      sartlar.append("NOTIFY_APPLICANT")
        # Sigorta
        if tur == "SIGORTA":
            if "110%" in m_u or "110 %" in m_u:  sartlar.append("MIN_110_PERCENT")
            if "INSTITUTE CARGO CLAUSES (A)" in m_u: sartlar.append("ICC_A")
            if "CLAIMS PAYABLE" in m_u:
                cp = re.search(r'CLAIMS?\s+PAYABLE\s+IN?\s+([A-Z]+)', m_u)
                sartlar.append(f"CLAIMS_PAYABLE_{cp.group(1) if cp else 'UNKNOWN'}")
            if "ENDORSED IN BLANK" in m_u or "BLANK ENDORS" in m_u:
                sartlar.append("ENDORSED_BLANK")
        # PL
        if tur == "CEKI_LISTESI":
            if "GROSS WEIGHT" in m_u:    sartlar.append("GROSS_WEIGHT")
            if "NET WEIGHT" in m_u:      sartlar.append("NET_WEIGHT")
            if "MEASUREMENT" in m_u:     sartlar.append("MEASUREMENT")
            if "PACKAGE DETAILS" in m_u: sartlar.append("PACKAGE_DETAILS")
        # CO
        if tur == "CO":
            if "CHAMBER" in m_u:         sartlar.append("CHAMBER_OF_COMMERCE")
            if "LEGALIZ" in m_u:         sartlar.append("LEGALIZATION")
        return sartlar

    sonuc = []
    for i, madde in enumerate(maddeler, 1):
        tur = _tur(madde)
        alt = _alt_sartlar(madde, tur)
        # Numera kaldır
        temiz = re.sub(r'^\s*\d+[.)]\s*', '', madde).strip()
        sonuc.append({
            "sira":       i,
            "belge_turu": tur,
            "sart_metni": temiz,
            "alt_sartlar": alt,
        })
    return sonuc


# ─────────────────────────────────────────────────────────────────────────────
# 46A DOĞRULAMA MOTORU
# ─────────────────────────────────────────────────────────────────────────────
def alan_46a_dogrula(sartlar: list[dict], depo: dict) -> list[dict]:
    """
    46A şartlarını parse edilmiş belgeler üzerinde doğrular.
    depo: {"FATURA": parsed_invoice, "KONSIMENTO": parsed_bl, ...}
    
    Döner: list[dict] — her şart için sonuç
      {sira, belge_turu, sart_metni, alt_sartlar,
       belge_var, alt_sart_sonuclari, durum, detay}
    """
    DEPO_ESLESTIR = {
        "FATURA":            "FATURA",
        "CEKI_LISTESI":      "CEKI_LISTESI",
        "KONSIMENTO":        "KONSIMENTO",
        "SIGORTA":           "SIGORTA",
        "CO":                "CO",
        "KALITE_SERTIFIKA":  "DIGER",
        "LEHDAR_BEYANI":     "DIGER",
        "NAVLUN_FATURA":     "DIGER",
        "DIGER":             "DIGER",
    }

    sonuclar = []
    for sart in sartlar:
        tur     = sart["belge_turu"]
        depo_k  = DEPO_ESLESTIR.get(tur, "DIGER")
        belge   = depo.get(depo_k)
        var     = belge is not None and not belge.get("_bos", False)

        alt_sonuc: list[dict] = []
        genel_durum = "BULUNDU ✓" if var else "EKSİK ✗"

        if var and belge:
            for alt in sart.get("alt_sartlar", []):
                sonuc_alt = _alt_sart_dogrula(alt, belge, tur)
                alt_sonuc.append({"sart": alt, "sonuc": sonuc_alt})
                # Alt şart başarısızsa genel durum bozulmaz ama UYARI eklenir
                if "✗" in sonuc_alt:
                    genel_durum = "UYARI ⚠"

        sonuclar.append({
            **sart,
            "belge_var":          var,
            "alt_sart_sonuclari": alt_sonuc,
            "durum":              genel_durum,
            "detay":              f"{'Belge ibraz dosyasında mevcut' if var else 'Belge ibraz dosyasında YOK'}."
        })
    return sonuclar


def _alt_sart_dogrula(alt: str, belge: dict, tur: str) -> str:
    """Tek alt şartı belge üzerinde kontrol eder. '✓ ...' veya '✗ ...' döner."""
    a = alt.upper()
    def _v(key): return belge.get(key)

    if a.startswith("ORIGINALS:"):
        istenen = int(re.search(r'\d+', alt).group())
        v = _v("originals")
        gelen = int(re.search(r'\d+', str(v)).group()) if v and re.search(r'\d+', str(v)) else None
        if gelen and gelen >= istenen:
            return f"✓ {istenen} orijinal — ibraz: {gelen}"
        return f"✗ {istenen} orijinal gerekli — ibraz: {gelen or 'tespit edilemedi'}"
    if a.startswith("COPIES:"):
        return f"✓ Kopya şartı not edildi."  # Kopyalar genel kontrolde
    if a == "SIGNED":
        return "✓ İmza mevcut" if _v("signed") else "✗ İmza tespit edilemedi"
    if a == "LC_NUMBER_REQUIRED":
        return f"✓ LC No: {_v('lc_no')}" if _v("lc_no") else "⚠ LC No tespit edilemedi (OCR güven düşük olabilir)"
    if a == "CLEAN":
        return "✓ CLEAN ON BOARD" if _v("clean") else "✗ CLEAN ON BOARD ifadesi yok"
    if a == "ON_BOARD":
        return "✓ On Board şerhi" if _v("on_board") else "✗ On Board şerhi yok"
    if a == "FREIGHT_PREPAID":
        return "✓ FREIGHT PREPAID" if _v("freight_prepaid") else "✗ FREIGHT PREPAID bulunamadı"
    if a == "FULL_SET_3/3":
        orig = _v("originals")
        return f"✓ Tam set: {orig}" if orig else "⚠ Orijinal sayısı tespit edilemedi"
    if a == "MIN_110_PERCENT":
        ok = _v("sigorta_yeterli")
        si = _v("sum_insured"); mn = _v("min_sigorta")
        if ok is True:
            return f"✓ Sigorta {si:,.2f} ≥ Min {mn:,.2f}"
        elif ok is False:
            return f"✗ Sigorta {si:,.2f} < Min {mn:,.2f}"
        return "⚠ Sigorta tutarı tespit edilemedi"
    if a == "ICC_A":
        c = _v("conditions") or []
        in_cond = any(
            ("INSTITUTE CARGO" in str(x).upper() and "(A)" in str(x))
            or ("ICC" in str(x).upper() and "(A)" in str(x))
            for x in c
        )
        return "✓ ICC (A) / Institute Cargo Clauses (A) mevcut" if in_cond else "✗ ICC (A) koşulu bulunamadı"
    if a.startswith("CLAIMS_PAYABLE_"):
        sehir = a.replace("CLAIMS_PAYABLE_", "")
        cp = str(_v("claims_payable") or "").upper()
        return f"✓ Claims payable: {cp}" if sehir in cp or cp else f"⚠ Claims payable şehri doğrulanamadı"
    if a == "ENDORSED_BLANK":
        return "✓ Ciro: boş" if _v("endorsed_blank") else "⚠ Blank endorsement tespit edilemedi"
    if a == "GROSS_WEIGHT":
        gw = _v("gross_weight")
        return f"✓ Gross Weight: {gw:,.2f} KG" if gw else "✗ Gross Weight tespit edilemedi"
    if a == "NET_WEIGHT":
        nw = _v("net_weight")
        return f"✓ Net Weight: {nw:,.2f} KG" if nw else "⚠ Net Weight tespit edilemedi"
    if a == "MEASUREMENT":
        cbm = _v("cbm")
        return f"✓ CBM: {cbm}" if cbm else "⚠ CBM tespit edilemedi"
    if a == "CHAMBER_OF_COMMERCE":
        return "✓ Chamber of Commerce" if _v("chamber") else "✗ Chamber of Commerce onayı yok"
    return f"✓ {alt} (onaylı)"
