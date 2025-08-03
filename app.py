import json
from pathlib import Path
import pandas as pd
import streamlit as st
from modules.poa_extractor import extract_poa
from modules.tax_extractor import extract_tax


st.set_page_config(page_title="Estate & Tax Document Analyzer",
                   layout="centered")
st.title("Estate & Tax Document Analyzer")


# Helper functions to format the results
def render_poa(data: dict) -> None:
    """
    Output the extracted Power of Attorney data.
    """
    data = data.copy()                           
    summary = data.pop("Summary of the document content", "")

    df = (pd.Series(data)
          .rename_axis("Field")
          .reset_index(name="Value"))
    st.dataframe(df, hide_index=True, use_container_width=True)

    if summary:
        st.markdown("#### Document summary")
        st.write(summary)


def render_tax(data: dict) -> None:
    """
    Output the extracted Tax Return data.
    """
    df = (pd.Series(data, dtype="int64")
          .map(lambda x: f"${x:,.0f}")
          .rename_axis("ID")
          .reset_index(name="Amount"))
    st.dataframe(df, hide_index=True, use_container_width=True)


category = st.radio("Document type:",
    ("Estate", "Tax Return"),
    index=0)

docs_dir = Path("docs/estate" if category == "Estate" else "docs/tax")
pdf_paths = sorted(docs_dir.glob("*.pdf"))

if not pdf_paths:
    st.error(f"No PDF files found in `{docs_dir}`.")
    st.stop()

file_chosen = st.selectbox(
    "Select a PDF:",
    pdf_paths,
    format_func=lambda p: p.name)

if st.button("Extract information"):
    with st.spinner("Processing…"):
        try:
            data = (extract_poa(file_chosen)
                    if category == "Estate"
                    else extract_tax(str(file_chosen)))
        except Exception as e:
            st.error(f"Error while processing the document: {e}")
            st.stop()

    st.success("Done!")

    # output
    render_poa(data) if category == "Estate" else render_tax(data)

    # download the results in JSON
    st.download_button(
        "Download JSON",
        data=json.dumps(data, indent=2),
        file_name=f"{file_chosen.stem}_extracted.json",
        mime="application/json",
    )
