# app.py
import streamlit as st
import io, re, json, zipfile
import pandas as pd
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract

st.set_page_config(page_title="Batch PDF Invoice Extractor", layout="wide")
st.title("Batch PDF Invoice Extractor")
st.caption("Upload multiple invoices → parse fields + line items → download a single CSV and a ZIP of per-invoice files.")

# ---------- Sidebar settings ----------
force_ocr = st.sidebar.checkbox("Force OCR for all files (for scanned PDFs)", value=False)
ocr_lang = st.sidebar.text_input("OCR language codes (e.g., eng or hin+eng)", value="eng")
show_preview = st.sidebar.checkbox("Show first 100 rows preview", value=True)

st.sidebar.info(
    "Note: OCR needs Poppler (pdf2image) and Tesseract installed on the host. "
    "Streamlit Cloud may not support these binaries."
)

# ---------- File uploader ----------
uploaded_files = st.file_uploader("Upload PDF invoices (multiple allowed)", type=["pdf"], accept_multiple_files=True)

# ---------- Regex helpers ----------
DATE_RE   = re.compile(r'(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b)|(\b\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\b)')
GSTIN_RE  = re.compile(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b', re.I)
INVNO_RE  = re.compile(r'(?i)(invoice\s*(no|number|#)[:\s]*)([A-Z0-9\-/]+)')
INVTYPE_RE= re.compile(r'(?i)\b(Tax Invoice|Credit Note|Debit Note|Bill of Supply)\b')

def extract_with_pdfplumber(bytes_io: io.BytesIO):
    texts, tables_meta = [], []
    with pdfplumber.open(bytes_io) as pdf:
        for pageno, page in enumerate(pdf.pages, start=1):
            texts.append(page.extract_text() or "")
            tbs = page.extract_tables()
            if tbs:
                for t in tbs:
                    tables_meta.append({"page": pageno, "table": t})
    return "\n\n".join(texts).strip(), tables_meta

def ocr_text_from_pdf(pdf_bytes: bytes, lang="eng"):
    imgs = convert_from_bytes(pdf_bytes)
    buf = []
    for im in imgs:
        buf.append(pytesseract.image_to_string(im, lang=lang))
    return "\n\n".join(buf)

def parse_invoice_header(text: str, filename: str):
    out = {
        "source_file": filename,
        "invoice_number": "",
        "invoice_date": "",
        "invoice_type": "",
        "supplier_gstin": "",
        "customer_gstin": ""
    }
    m = INVNO_RE.search(text)
    out["invoice_number"] = (m.group(3).strip() if m else filename.rsplit(".",1)[0])
    md = DATE_RE.search(text)
    out["invoice_date"] = md.group(0) if md else ""
    mt = INVTYPE_RE.search(text)
    out["invoice_type"] = mt.group(1) if mt else ""
    g = GSTIN_RE.findall(text)
    if g:
        out["supplier_gstin"] = g[0]
        if len(g) > 1: out["customer_gstin"] = g[1]
    return out

def table_has_items(table):
    if not table or not table[0]:
        return False
    header = " ".join([str(c).lower() for c in table[0] if c])
    keys = ["description", "item", "hsn", "qty", "quantity", "rate", "amount", "taxable", "value"]
    return any(k in header for k in keys)

def normalize_table(table):
    return [[("" if c is None else str(c).strip()) for c in row] for row in table]

def map_table_to_items(table):
    """Best-effort mapping. Customize per vendor as needed."""
    t = normalize_table(table)
    header = [h.lower() for h in t[0]]
    # crude column guesses
    # try to locate common columns by fuzzy match
    def find_col(*names):
        joined = [("".join(n.split())).lower() for n in names]
        for i, col in enumerate(header):
            jr = ("".join(col.split())).lower()
            if any(name in jr for name in joined):
                return i
        return None

    col_desc = find_col("description", "item", "particular")
    col_qty  = find_col("qty", "quantity")
    col_rate = find_col("rate", "unitprice", "price")
    col_taxv = find_col("taxable value", "value", "amount")

    items = []
    for row in t[1:]:
        if not any(row): 
            continue
        items.append({
            "item_description": row[col_desc] if col_desc is not None and col_desc < len(row) else (row[1] if len(row)>1 else ""),
            "quantity":         row[col_qty]  if col_qty  is not None and col_qty  < len(row) else "",
            "unit_price":       row[col_rate] if col_rate is not None and col_rate < len(row) else "",
            "taxable_value":    row[col_taxv] if col_taxv is not None and col_taxv < len(row) else ""
        })
    if not items:
        items = [{"item_description":"", "quantity":"", "unit_price":"", "taxable_value":""}]
    return items

if uploaded_files:
    rows = []
    per_invoice_payloads = {}
    progress = st.progress(0.0)
    status   = st.empty()

    for idx, up in enumerate(uploaded_files, start=1):
        fname = up.name
        status.info(f"Processing {idx}/{len(uploaded_files)}: {fname}")
        bytes_data = up.read()

        text, tables_meta = "", []
        # 1) Machine extraction (pdfplumber)
        if not force_ocr:
            try:
                text, tables_meta = extract_with_pdfplumber(io.BytesIO(bytes_data))
            except Exception as e:
                st.warning(f"{fname}: pdfplumber failed — {e}")

        # 2) OCR fallback
        if (not text or len(text) < 20) or force_ocr:
            try:
                text = ocr_text_from_pdf(bytes_data, lang=ocr_lang)
            except Exception as e:
                st.error(f"{fname}: OCR failed — {e}")
                text = text or ""  # keep whatever we had

        # 3) Parse header
        header = parse_invoice_header(text, fname)

        # 4) Parse items (prefer tables from pdfplumber)
        items = []
        if tables_meta:
            for tmeta in tables_meta:
                t = tmeta["table"]
                if table_has_items(t):
                    items = map_table_to_items(t)
                    break
        if not items:
            # basic OCR line heuristic for items (very naive)
            line_items = []
            for line in text.splitlines():
                if re.search(r'\d+\s+[\w\s]{3,}\s+\d+(?:\.\d{1,2})?\s+\d+(?:\.\d{1,2})?', line):
                    line_items.append(line)
            for ln in line_items:
                parts = re.split(r'\s{2,}', ln.strip())
                if len(parts) >= 3:
                    items.append({
                        "item_description": parts[0],
                        "quantity": parts[1],
                        "unit_price": parts[2],
                        "taxable_value": parts[3] if len(parts) > 3 else ""
                    })
        if not items:
            items = [{"item_description":"", "quantity":"", "unit_price":"", "taxable_value":""}]

        # 5) Collect rows
        for it in items:
            rows.append({
                "source_file": header["source_file"],
                "invoice_number": header["invoice_number"],
                "invoice_date": header["invoice_date"],
                "invoice_type": header["invoice_type"],
                "supplier_gstin": header["supplier_gstin"],
                "customer_gstin": header["customer_gstin"],
                "item_description": it.get("item_description",""),
                "quantity": it.get("quantity",""),
                "unit_price": it.get("unit_price",""),
                "taxable_value": it.get("taxable_value","")
            })

        # Per-invoice payload for ZIP (summary + items CSV)
        per_invoice_payloads[fname] = {
            "summary": header,
            "items": items,
            "raw_text_snippet": "\n".join(text.splitlines()[:30])
        }

        progress.progress(idx/len(uploaded_files))

    status.success("Done.")

    # ---------- Consolidated CSV ----------
    df = pd.DataFrame(rows)
    if show_preview:
        st.subheader("Preview (first 100 rows)")
        st.dataframe(df.head(100), use_container_width=True)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download consolidated CSV (all invoices together)",
        data=csv_bytes,
        file_name="invoices_consolidated.csv",
        mime="text/csv"
    )

    # ---------- Per-invoice ZIP (JSON + items CSV per invoice) ----------
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, payload in per_invoice_payloads.items():
            base = fname.rsplit(".",1)[0]
            # summary JSON
            zf.writestr(f"{base}_summary.json", json.dumps(payload["summary"], indent=2, ensure_ascii=False))
            # items CSV
            items_df = pd.DataFrame(payload["items"])
            zf.writestr(f"{base}_items.csv", items_df.to_csv(index=False))
            # raw text (optional)
            zf.writestr(f"{base}_raw.txt", payload["raw_text_snippet"])
    zip_buf.seek(0)
    st.download_button(
        "Download per-invoice ZIP (summary JSON + items CSV + raw snippet)",
        data=zip_buf,
        file_name="per_invoice_outputs.zip",
        mime="application/zip"
    )

else:
    st.info("Upload multiple PDF invoices above to extract in one go.")
