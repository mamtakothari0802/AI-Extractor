import re
from typing import Optional, Tuple, List

import pdfplumber
from PyPDF2 import PdfReader


def _read_pdf_text(file_path: str) -> str:
    """Read text from all pages using pdfplumber, fallback to PyPDF2."""
    # Try pdfplumber first
    try:
        with pdfplumber.open(file_path) as pdf:
            texts = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                texts.append(page_text)
            joined = "\n".join(texts).strip()
            if joined:
                return joined
    except Exception:
        pass

    # Fallback to PyPDF2
    try:
        reader = PdfReader(file_path)
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(texts).strip()
    except Exception:
        return ""


def _extract_first(patterns: List[str], text: str, flags: int = re.IGNORECASE) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            # Prefer the last captured group (typically the value) if present
            if match.lastindex:
                for i in range(match.lastindex, 0, -1):
                    group = match.group(i)
                    if group and group.strip():
                        return group.strip()
            return match.group(0).strip()
    return None


def _parse_amount(amount_str: str) -> Optional[float]:
    if amount_str is None:
        return None
    # Remove currency symbols and spaces, normalize commas
    cleaned = re.sub(r"[₹,\s]", "", amount_str)
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    try:
        return float(cleaned)
    except Exception:
        return None


def _extract_gstin(text: str) -> Optional[str]:
    # GSTIN pattern (common Indian GSTIN format)
    gstin_pattern = r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"
    return _extract_first([gstin_pattern], text)


def _extract_invoice_number(text: str) -> Optional[str]:
    patterns = [
        r"invoice\s*(no\.|number|#|:)\s*([A-Z0-9\-\/]+)",
        r"inv\s*(no\.|#|:)\s*([A-Z0-9\-\/]+)",
    ]
    return _extract_first(patterns, text)


def _extract_date(text: str) -> Optional[str]:
    # Support common formats: DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD
    patterns = [
        r"\b(\d{2}[\-/]\d{2}[\-/]\d{4})\b",
        r"\b(\d{4}[\-/]\d{2}[\-/]\d{2})\b",
    ]
    return _extract_first(patterns, text)


def _extract_names(text: str) -> Tuple[Optional[str], Optional[str]]:
    # Heuristics around labels
    vendor_patterns = [
        r"(?:supplier|vendor|from)\s*[:\-]\s*(.+)",
        r"\btax invoice\b\s*(.+)",
    ]
    buyer_patterns = [
        r"(?:buyer|bill\s*to|ship\s*to|deliver\s*to)\s*[:\-]\s*(.+)",
    ]

    vendor = _extract_first(vendor_patterns, text)
    buyer = _extract_first(buyer_patterns, text)

    # Post-process: trim to the end of the line
    if vendor:
        vendor = vendor.splitlines()[0].strip()
    if buyer:
        buyer = buyer.splitlines()[0].strip()
    return vendor, buyer


def _extract_tax_values(text: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    taxable = _extract_first([r"taxable\s*(amount|value)\s*[:\-]?\s*([₹\s,0-9.\-]+)"], text)
    cgst = _extract_first([r"cgst[^0-9]*([₹\s,0-9.\-]+)"], text)
    sgst = _extract_first([r"sgst[^0-9]*([₹\s,0-9.\-]+)"], text)
    igst = _extract_first([r"igst[^0-9]*([₹\s,0-9.\-]+)"], text)
    total = _extract_first([
        r"total\s*(invoice\s*)?(amount|value)\s*[:\-]?\s*([₹\s,0-9.\-]+)",
        r"grand\s*total\s*[:\-]?\s*([₹\s,0-9.\-]+)",
    ], text)

    return (
        _parse_amount(taxable),
        _parse_amount(cgst),
        _parse_amount(sgst),
        _parse_amount(igst) if igst is not None else None,
    ), _parse_amount(total)


def _extract_hsn(text: str) -> Optional[str]:
    return _extract_first([r"hsn(?:/sac)?\s*[:\-]?\s*(\d{4,8})"], text)


def _extract_place_of_supply(text: str) -> Optional[str]:
    return _extract_first([r"place\s*of\s*supply\s*[:\-]\s*([A-Za-z\s]+)"], text)


def _extract_invoice_type(text: str) -> Optional[str]:
    return _extract_first([
        r"\b(tax\s*invoice)\b",
        r"\b(retail\s*invoice)\b",
        r"\b(supply\s*invoice)\b",
    ], text)


def extract_from_pdf(file_path: str) -> dict:
    """Extract key invoice fields from a PDF using regex heuristics."""
    text = _read_pdf_text(file_path)

    (taxable_value, cgst_value, sgst_value, igst_value), total_value = _extract_tax_values(text)
    vendor_name, buyer_name = _extract_names(text)

    data = {
        "Invoice_Number": _extract_invoice_number(text) or "",
        "GSTIN": _extract_gstin(text) or "",
        "Date": _extract_date(text) or "",
        "Vendor_Name": vendor_name or "",
        "Buyer_Name": buyer_name or "",
        "Taxable_Value": taxable_value if taxable_value is not None else 0,
        "CGST": cgst_value if cgst_value is not None else 0,
        "SGST": sgst_value if sgst_value is not None else 0,
        "IGST": igst_value if igst_value is not None else 0,
        "Total_Invoice_Value": total_value if total_value is not None else 0,
        "HSN_Code": _extract_hsn(text) or "",
        "Place_of_Supply": _extract_place_of_supply(text) or "",
        "Invoice_Type": _extract_invoice_type(text) or "",
        # Keep a short preview for the UI table
        "Raw_Text_Extracted": (text[:200] + ("…" if len(text) > 200 else "")) if text else "",
    }

    return data
