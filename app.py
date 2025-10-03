import streamlit as st
import pandas as pd
import json
from extractor import extract_from_pdf

st.set_page_config(page_title="AI Extractor", layout="wide")

st.title("📄 AI Extractor for Financial Documents")
st.write("Upload a PDF invoice and get structured output (CSV / JSON).")

uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])

if uploaded_file is not None:
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.read())

    data = extract_from_pdf("temp.pdf")

    if data:
        df = pd.DataFrame([data])
        st.subheader("Extracted Data")
        st.dataframe(df)

        with st.expander("Raw text preview", expanded=False):
            st.text(data.get("Raw_Text_Extracted", ""))

        with st.expander("JSON preview", expanded=False):
            st.code(json.dumps(data, indent=2), language="json")

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "output.csv", "text/csv")

        json_str = json.dumps(data, indent=4)
        st.download_button("⬇️ Download JSON", json_str, "output.json", "application/json")
    else:
        st.warning("⚠️ No data extracted.")
