# ==========================================================
# app.py — Airtel Infra-Health Dashboard (Dynamic Logic)
# RUN USING: python app.py
# ==========================================================

import os, sys, subprocess
import re
import pandas as pd
import streamlit as st

# ------------------ Auto Streamlit Launcher ----------------
def _inside_streamlit():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False

if not _inside_streamlit():
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)],
        check=False
    )
    sys.exit(0)

# ------------------ Page Configuration ------------------
st.set_page_config(page_title="Site KPI Health Dashboard", layout="wide")

# ==========================================================
# SIDEBAR: DATA UPLOAD
# ==========================================================
with st.sidebar:
    st.title("⚙ Control Center")
    uploaded_file = st.file_uploader("Upload Excel / CSV", type=["xlsx", "xls", "csv"])

if not uploaded_file:
    st.info("Upload your KPI Excel / CSV file to generate the dashboard.")
    st.stop()

# ==========================================================
# LOAD & CLEAN DATA (Fixing the Float Error)
# ==========================================================
try:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, engine="python", encoding="utf-8")
    else:
        df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Error loading file: {e}")
    st.stop()

# CRITICAL FIX: Convert all column headers to strings to prevent "Float has no attribute lower"
df.columns = df.columns.astype(str).str.strip()

def make_unique(cols):
    seen = {}
    result = []
    for c in cols:
        c_clean = re.sub(r"\s+", " ", str(c).replace("\n", " ")).strip()
        if c_clean not in seen:
            seen[c_clean] = 0
            result.append(c_clean)
        else:
            seen[c_clean] += 1
            result.append(f"{c_clean}__{seen[c_clean]}")
    return result

df.columns = make_unique(df.columns)

# ==========================================================
# STEP 1: COLUMN MAPPING UI
# ==========================================================
def find_col(pattern):
    for c in df.columns:
        # Cast c to string here as an extra layer of protection
        if re.search(pattern, str(c).lower()):
            return c
    return df.columns[0] # Failsafe

AUTO_MAP = {
    "Site ID": find_col(r"site.*id"),
    "Cluster": find_col(r"cluster"),
    "Town/District": find_col(r"town|district|city"),
    "TOCO": find_col(r"toco"),
    "Battery Backup": find_col(r"battery.*backup|bb.*hrs"),
    "DG Automation": find_col(r"dg.*automation|dg.*status"),
    "SNMP Communicated": find_col(r"snmp"),
    "RM Count": find_col(r"rm.*count|rm.*n\+1"),
}

with st.sidebar:
    st.markdown("---")
    st.header("1. Column Mapping")
    st.caption("Verify or change where the data is coming from.")
    
    def pick(label, default):
        cols = df.columns.tolist()
        idx = cols.index(default) if default in cols else 0
        return st.selectbox(label, cols, index=idx)

    # Base Dimensions
    with st.expander("📍 Dimensions Mapping", expanded=False):
        COL_SITE    = pick("Site ID Column", AUTO_MAP["Site ID"])
        COL_CLUSTER = pick("Cluster Column", AUTO_MAP["Cluster"])
        COL_TOWN    = pick("Town/District Column", AUTO_MAP["Town/District"])
        COL_TOCO    = pick("TOCO Column", AUTO_MAP["TOCO"])

    # KPI Columns
    with st.expander("📊 KPI Mapping", expanded=True):
        COL_BB      = pick("Battery Backup Column", AUTO_MAP["Battery Backup"])
        COL_DG      = pick("DG Automation Column", AUTO_MAP["DG Automation"])
        COL_SNMP    = pick("SNMP Column", AUTO_MAP["SNMP Communicated"])
        COL_RM      = pick("RM Count Column", AUTO_MAP["RM Count"])


# ==========================================================
# STEP 2: LOGIC BUILDING UI (100% User-Selected)
# ==========================================================
with st.sidebar:
    st.markdown("---")
    st.header("2. Logic Building")
    st.caption("Select the exact values that equal a FAILURE.")

    USE_BB = st.checkbox("Evaluate Battery Backup", True)
    if USE_BB:
        BB_THRESHOLD = st.number_input(f"Fail if '{COL_BB}' is Less Than:", value=4.0, step=0.5)

    USE_DG = st.checkbox("Evaluate DG Automation", True)
    if USE_DG:
        # Fetch actual unique values from the mapped column, dropping blanks
        dg_opts = sorted(df[COL_DG].dropna().astype(str).unique().tolist())
        DG_FAIL_STATES = st.multiselect(f"Select Failure Statuses for '{COL_DG}':", options=dg_opts, default=[])

    USE_SNMP = st.checkbox("Evaluate SNMP", True)
    if USE_SNMP:
        snmp_opts = sorted(df[COL_SNMP].dropna().astype(str).unique().tolist())
        SNMP_FAIL_STATES = st.multiselect(f"Select Failure Statuses for '{COL_SNMP}':", options=snmp_opts, default=[])

    USE_RM = st.checkbox("Evaluate RM Count", True)
    if USE_RM:
        rm_opts = sorted(df[COL_RM].dropna().astype(str).unique().tolist())
        RM_FAIL_STATES = st.multiselect(f"Select Failure Statuses for '{COL_RM}':", options=rm_opts, default=[])

# ==========================================================
# APPLY DYNAMIC KPI LOGIC
# ==========================================================
df["_bb_fail"]   = False
df["_dg_fail"]   = False
df["_snmp_fail"] = False
df["_rm_fail"]   = False
df["Failure Summary"] = ""

if USE_BB:
    # Convert safely to numeric, blanks become 999 so they don't trigger "low battery" false positives
    df["_bb_fail"] = pd.to_numeric(df[COL_BB], errors="coerce").fillna(999) < BB_THRESHOLD
    df.loc[df["_bb_fail"], "Failure Summary"] += "Battery; "

if USE_DG and len(DG_FAIL_STATES) > 0:
    df["_dg_fail"] = df[COL_DG].astype(str).isin(DG_FAIL_STATES)
    df.loc[df["_dg_fail"], "Failure Summary"] += "DG; "

if USE_SNMP and len(SNMP_FAIL_STATES) > 0:
    df["_snmp_fail"] = df[COL_SNMP].astype(str).isin(SNMP_FAIL_STATES)
    df.loc[df["_snmp_fail"], "Failure Summary"] += "SNMP; "

if USE_RM and len(RM_FAIL_STATES) > 0:
    df["_rm_fail"] = df[COL_RM].astype(str).isin(RM_FAIL_STATES)
    df.loc[df["_rm_fail"], "Failure Summary"] += "RM; "

df["_fail_count"] = df[["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]].sum(axis=1)
df["_any_fail"] = df["_fail_count"] > 0


# ==========================================================
# MAIN DASHBOARD (GLIMPSE STYLE)
# ==========================================================
st.title("📊 Network Diagnostics & KPI Dashboard")

# Top Level Filter
clusters = ["All"] + sorted(df[COL_CLUSTER].dropna().astype(str).unique().tolist())
selected_cluster = st.selectbox("📍 Filter Dataset by Cluster", clusters)

fdf = df if selected_cluster == "All" else df[df[COL_CLUSTER].astype(str) == selected_cluster]

total = len(fdf)
not_ok_count = int(fdf["_any_fail"].sum())
ok_count = total - not_ok_count
ok_pct = (ok_count / total * 100) if total else 0

# Styled Metrics UI
c1, c2, c3, c4 = st.columns(4)
c1.metric("🌐 Total Sites", f"{total:,}")
c2.metric("✅ 100% OK Sites", f"{ok_count:,}", f"{ok_pct:.1f}%")
c3.metric("⚠️ Degraded Sites", f"{not_ok_count:,}", f"-{(100-ok_pct):.1f}%", delta_color="inverse")
c4.metric("🚨 Critical (3+ Fails)", f"{len(fdf[fdf['_fail_count'] >= 3]):,}")

st.markdown("---")

# ==========================================================
# INTERACTIVE ANALYSIS SECTION
# ==========================================================
col_view, col_chart = st.columns([1, 2])

with col_view:
    st.subheader("⚙️ Analysis Dimension")
    st.caption("Change the X-Axis of the chart.")
    analysis_dim = st.radio(
        "Analyze Distribution By:",
        options=["Cluster", "Town/District", "TOCO"],
        index=0
    )
    
    dim_col = COL_CLUSTER if analysis_dim == "Cluster" else (COL_TOWN if analysis_dim == "Town/District" else COL_TOCO)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ❌ High-Level Failure Summary")
    summary_data = {
        "Battery Issue": int(fdf["_bb_fail"].sum()),
        "DG Issue": int(fdf["_dg_fail"].sum()),
        "SNMP Issue": int(fdf["_snmp_fail"].sum()),
        "RM Issue": int(fdf["_rm_fail"].sum()),
    }
    st.dataframe(pd.DataFrame(list(summary_data.items()), columns=["KPI Category", "Sites Failed"]).set_index("KPI Category"), use_container_width=True)

with col_chart:
    st.subheader(f"📈 Degraded Sites Distribution (by {analysis_dim})")
    
    if not_ok_count > 0:
        # Group by selected dimension and sum the failure flags
        chart_data = fdf[fdf["_any_fail"]].groupby(dim_col)[["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]].sum()
        chart_data.columns = ["Battery Issue", "DG Issue", "SNMP Issue", "RM Issue"]
        
        # Native Streamlit Stacked Bar Chart
        st.bar_chart(chart_data)
    else:
        st.success("No degraded sites to display for current filter.")

# ==========================================================
# ACTIONABLE DATA TABLE
# ==========================================================
st.markdown("---")
st.subheader("📋 Actionable Sites List (Filtered to Degraded)")

if not_ok_count > 0:
    worst_df = fdf[fdf["_any_fail"]].sort_values("_fail_count", ascending=False).copy()
    
    # Clean up the Failure Summary text for the table
    worst_df["Failure Summary"] = worst_df["Failure Summary"].str.rstrip("; ")
    
    display_cols = [COL_SITE, COL_CLUSTER, COL_TOWN, COL_TOCO, "Failure Summary", COL_BB, COL_DG, COL_SNMP, COL_RM]
    display_cols = [c for c in display_cols if c in worst_df.columns]
    
    st.dataframe(
        worst_df[display_cols].style.map(lambda x: 'background-color: rgba(255, 75, 75, 0.1)', subset=['Failure Summary']),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("All sites are communicating and 100% OK.")
