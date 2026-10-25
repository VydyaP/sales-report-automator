"""Web page for the demo: upload sales files, download the finished report.

Run locally:   streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from report_automator import ConfigError, InputFileError, NoValidRowsError, load_config, run_report  # noqa: E402
from report_automator.cleaner import CHECK, FIXED, REMOVED  # noqa: E402

SAMPLE_DIR = ROOT / "sample_data"
SAMPLE_CONFIG = ROOT / "configs" / "demo_store.yaml"

st.set_page_config(page_title="Sales Report Automator", page_icon="📊", layout="wide")

st.title("Sales Report Automator")
st.write(
    "Upload your monthly sales exports (Excel or CSV, from any billing software). "
    "Get back a clean Excel report and a one-page PDF in seconds, plus a list of "
    "every row that was fixed or removed and why."
)

with st.sidebar:
    st.header("Settings")
    business_name = st.text_input("Business name (shown on the report)", value="")
    settings_file = st.file_uploader("Settings file (optional, .yaml)", type=["yaml", "yml"])
    st.caption(
        "The settings file lets the tool understand a client's own column names and "
        "product spellings. Without it, common names like Date, Bill No, Item Name, "
        "Qty, Rate and Amount are recognised automatically."
    )
    st.divider()
    st.caption("Files are processed in memory for this session only and are not stored.")

uploads = st.file_uploader("Sales files", type=["xlsx", "xlsm", "csv"], accept_multiple_files=True)
use_sample = st.button("No files handy? Try the demo store's messy sample data")

if use_sample:
    st.session_state["use_sample"] = True
if uploads:
    st.session_state["use_sample"] = False

sources = None
config_source = None
if uploads:
    sources = [(f.name, f) for f in uploads]
elif st.session_state.get("use_sample"):
    sources = sorted(SAMPLE_DIR.glob("*.xlsx")) + sorted(SAMPLE_DIR.glob("*.csv"))
    config_source = SAMPLE_CONFIG
    st.info(
        "Using three months of **fictional** sales from a demo store, exported in three "
        "different messy layouts: " + ", ".join(p.name for p in sources)
    )

if not sources:
    st.stop()

try:
    if settings_file is not None:
        config = load_config(settings_file.getvalue().decode("utf-8"))
    else:
        config = load_config(config_source)
    if business_name.strip():
        config.business_name = business_name.strip()
    with st.spinner("Cleaning data and building your report..."):
        result = run_report(sources, config)
except (ConfigError, InputFileError) as exc:
    st.error(str(exc))
    st.stop()
except NoValidRowsError as exc:
    st.warning(str(exc))
    st.stop()
except UnicodeDecodeError:
    st.error("The settings file must be plain text (UTF-8).")
    st.stop()

c, s = result.cleaned, result.summary
st.success(f"Report ready: {s.business_name}, {s.period_label}")

col1, col2 = st.columns(2)
col1.download_button("⬇ Download Excel report", result.excel_bytes, file_name=f"{result.base_name}.xlsx",
                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     width="stretch", type="primary")
col2.download_button("⬇ Download PDF summary", result.pdf_bytes, file_name=f"{result.base_name}.pdf",
                     mime="application/pdf", width="stretch")

st.subheader("Key numbers")
kpis = s.kpis()
for row_start in range(0, len(kpis), 4):
    cols = st.columns(4)
    for col, (label, value) in zip(cols, kpis[row_start:row_start + 4]):
        col.metric(label, value)

st.subheader("What stands out")
for line in s.insights:
    st.markdown(f"- {line}")

left, right = st.columns(2)
with left:
    st.markdown("**Top products by sales**")
    st.bar_chart(s.by_product.head(10).set_index("product")["revenue"], horizontal=True)
with right:
    st.markdown("**Daily sales**")
    st.line_chart(s.by_day.set_index("date")["revenue"])

st.subheader("Data quality")
q1, q2, q3, q4 = st.columns(4)
q1.metric("Rows read", f"{c.rows_read:,}")
q2.metric("Rows used", f"{c.rows_kept:,}")
q3.metric("Automatic corrections", c.count(FIXED))
q4.metric("To double-check", c.count(CHECK))

issues = c.issues_frame()
if issues.empty:
    st.write("No problems found in the data.")
else:
    pick = st.multiselect("Show", [REMOVED, CHECK, FIXED], default=[REMOVED, CHECK])
    shown = issues[issues["severity"].isin(pick)]
    st.dataframe(shown, width="stretch", hide_index=True,
                 column_config={"row": st.column_config.NumberColumn("row", format="%d")})

with st.expander("How each file was read"):
    for f in c.files:
        mapped = ", ".join(f"{orig} → {canon}" for canon, orig in f.mapping.items())
        extra = f" Ignored columns: {', '.join(f.ignored_columns)}." if f.ignored_columns else ""
        st.markdown(f"**{f.name}**: headers found on row {f.header_row}. {mapped}.{extra}")
