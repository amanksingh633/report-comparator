"""Streamlit front end. Run with:  streamlit run app.py"""

from pathlib import Path

import pandas as pd
import streamlit as st

from report_comparator import ReportError, compare_reports, render_markdown

SAMPLE = Path(__file__).parent / "sample_data"

st.set_page_config(page_title="Report Comparator", layout="wide")
st.title("Report Comparator")
st.caption("Compare two report exports by key and see exactly what changed.")


def read_upload(file) -> pd.DataFrame:
    return pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)


use_sample = st.sidebar.checkbox("Use built-in sample data", value=False)
if use_sample:
    baseline = pd.read_csv(SAMPLE / "baseline.csv")
    candidate = pd.read_csv(SAMPLE / "candidate.csv")
else:
    col_a, col_b = st.columns(2)
    up_a = col_a.file_uploader("Baseline (known good)", type=["csv", "xlsx"])
    up_b = col_b.file_uploader("Candidate (to validate)", type=["csv", "xlsx"])
    if not (up_a and up_b):
        st.info("Upload both files, or tick 'Use built-in sample data' in the sidebar.")
        st.stop()
    baseline, candidate = read_upload(up_a), read_upload(up_b)

shared = [c for c in baseline.columns if c in candidate.columns]
default_key = ["invoice_id"] if use_sample else shared[:1]
keys = st.sidebar.multiselect("Key column(s)", shared, default=default_key)
ignore = st.sidebar.multiselect(
    "Ignore columns", shared, default=["generated_at"] if use_sample else []
)
abs_tol = st.sidebar.number_input(
    "Absolute tolerance", min_value=0.0, value=0.01 if use_sample else 0.0, step=0.01, format="%.4f"
)
rel_tol = st.sidebar.number_input(
    "Relative tolerance", min_value=0.0, value=0.0, step=0.0001, format="%.4f"
)

if not keys:
    st.warning("Pick at least one key column.")
    st.stop()

try:
    result = compare_reports(
        baseline, candidate, keys, abs_tol=abs_tol, rel_tol=rel_tol, ignore_columns=ignore
    )
except ReportError as exc:
    st.error(str(exc))
    st.stop()

(st.success if result.passed else st.error)(
    "PASS: reports match" if result.passed else "FAIL: reports differ"
)

m = st.columns(4)
m[0].metric("Rows compared", result.rows_compared)
m[1].metric("Missing in candidate", len(result.missing_in_candidate))
m[2].metric("Extra in candidate", len(result.extra_in_candidate))
m[3].metric("Mismatched cells", result.mismatched_cells)

tab_diff, tab_missing, tab_extra = st.tabs(["Mismatches", "Missing rows", "Extra rows"])
with tab_diff:
    if result.mismatches.empty:
        st.write("No value mismatches.")
    else:
        st.bar_chart(result.column_mismatch_counts())
        st.dataframe(result.mismatches, use_container_width=True)
with tab_missing:
    st.dataframe(result.missing_in_candidate, use_container_width=True)
with tab_extra:
    st.dataframe(result.extra_in_candidate, use_container_width=True)

st.download_button(
    "Download Markdown report", render_markdown(result), "report.md", "text/markdown"
)
st.download_button(
    "Download mismatches CSV", result.mismatches.to_csv(index=False), "mismatches.csv", "text/csv"
)
