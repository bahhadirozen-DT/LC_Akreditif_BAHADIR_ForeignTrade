# check_pdf.py
import os
import re
from pypdf import PdfReader

def detect_language(text):
    if not text:
        return "Unknown"
    text_upper = text.upper()
    tr_chars = len(re.findall(r'[ŞIĞÇÖÜ]', text_upper))
    en_words = len(re.findall(r'\b(THE|AND|OF|ARTICLE|CREDIT|DOCUMENTARY)\b', text_upper))
    tr_words = len(re.findall(r'\b(VE|ILE|BIR|MADDE|AKREDITIF|TAHSIL)\b', text_upper))
    
    if tr_chars > 5 or tr_words > 5:
        if en_words > 5:
            return "Multilingual (TR/EN)"
        return "Turkish"
    elif en_words > 2:
        return "English"
    return "English (Default)"

def analyze_pdf(file_path):
    filename = os.path.basename(file_path)
    try:
        reader = PdfReader(file_path)
        pages_count = len(reader.pages)
        is_encrypted = "YES" if reader.is_encrypted else "NO"
        
        # Extract all text to calculate density
        total_text = ""
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t:
                    total_text += t + "\n"
            except Exception:
                pass
        
        total_chars = len(total_text.strip())
        text_density = round(total_chars / pages_count) if pages_count > 0 else 0
        ocr_needed = "YES" if text_density < 50 else "NO"
        language = detect_language(total_text)
        
        # Document Type classification based on filename / content
        doc_type = "Other"
        fn_upper = filename.upper()
        if "UCP 600" in fn_upper or "UCP600" in fn_upper:
            doc_type = "UCP 600"
        elif "INCOTERMS" in fn_upper:
            doc_type = "Incoterms 2020"
        elif "MT700" in fn_upper or "SWIFT" in fn_upper:
            doc_type = "MT700 SWIFT Guide"
        elif "OPINION" in fn_upper or "ICC" in fn_upper:
            doc_type = "ICC Banking Opinions"
        elif "ISBP" in fn_upper:
            doc_type = "ISBP Examples"
        elif "EUCP" in fn_upper:
            doc_type = "eUCP"
        elif "EURC" in fn_upper:
            doc_type = "eURC"
        elif "URC 522" in fn_upper or "URC522" in fn_upper:
            doc_type = "URC 522"
            
        print(f"| {filename:<45} | {doc_type:<20} | {pages_count:<5} | {is_encrypted:<10} | {ocr_needed:<10} | {text_density:<12} | {language:<20} |")
    except Exception as e:
        print(f"| {filename:<45} | Error: {str(e)[:50]:<58} |")

def main():
    kb_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base")
    print("\n" + "="*140)
    print(f"| {'File Name':<45} | {'Document Type':<20} | {'Pages':<5} | {'Encrypted':<10} | {'OCR Needed':<10} | {'Text Density':<12} | {'Language':<20} |")
    print("-"*140)
    if os.path.isdir(kb_dir):
        for f in sorted(os.listdir(kb_dir)):
            if f.endswith(".pdf"):
                analyze_pdf(os.path.join(kb_dir, f))
    else:
        print(f"Knowledge base directory not found at {kb_dir}")
    print("="*140 + "\n")

if __name__ == "__main__":
    main()
