# 📄 AI Extractor for Financial Documents (Streamlit App)

## 📌 Overview
This project is a **Streamlit-based AI Extractor** for automating data extraction from financial PDFs (invoices, statements) into structured CSV/JSON.

---

## 🚀 Features
- Upload a financial PDF (invoice)
- Extracts key fields (Invoice No, GSTIN, Date, Value, HSN)
- Download structured results as CSV / JSON
- Simple UI with Streamlit

---

## ⚡ Quickstart

```bash
git clone <your-repo-url>
cd AI-Extractor
pip install -r requirements.txt
streamlit run app.py
```

---

## 📊 Demo Workflow
1. Open the app  
2. Upload `sample_invoice.pdf`  
3. Extracted table preview appears  
4. Download CSV/JSON  

---

## 📂 Repo Structure
```
├── app.py                 # Streamlit frontend
├── extractor.py           # Heuristic extraction logic (regex, multi-engine)
├── requirements.txt       # Dependencies
├── README.md              # Documentation
└── sample_files/
    ├── sample_invoice.pdf
    └── sample_output.json
```

---

## 📎 Example Output

```json
{
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
  "Invoice_Type": "Tax Invoice"
}
```

---

## 👤 Author
**CA Mamta Prakash Kothari**  
📧 shahmamta.789@gmail.com  
📱 +91 94093 49930
