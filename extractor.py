import pdfplumber

def extract_from_pdf(file_path):
    """
    Dummy extractor:
    Reads PDF (if possible) and returns structured invoice-like data.
    Currently returns sample static fields for demo.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text()
    except:
        text = ""

    data = {
        "Invoice_Number": "INV-2025-001",
        "GSTIN": "27ABCDE1234F1Z5",
        "Date": "2025-04-01",
        "Vendor_Name": "ABC Traders Pvt Ltd",
        "Buyer_Name": "XYZ Enterprises",
        "Taxable_Value": 50000,
        "CGST": 4500,
        "SGST": 4500,
        "IGST": 0,
        "Total_Invoice_Value": 59000,
        "HSN_Code": "9983",
        "Place_of_Supply": "Maharashtra",
        "Invoice_Type": "Tax Invoice",
        "Raw_Text_Extracted": text[:200]
    }

    return data
