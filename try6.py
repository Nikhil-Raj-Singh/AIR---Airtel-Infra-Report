# ==========================================================
# app.py — Airtel Infra-Health Dashboard (Corporate Safe)
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
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Airtel_logo.svg/512px-Airtel_logo.svg.png", width=100) # Optional branding
    st.title("⚙ Control Center")

    uploaded_file = st.file_uploader("Upload Excel / CSV", type=["xlsx", "xls", "csv"])

if not uploaded_file:
    st.info("Upload your KPI Excel / CSV file to generate the dashboard.")
    st.stop()

# ==========================================================
# LOAD & CLEAN DATA
# ==========================================================
try:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, engine="python", encoding="utf-8")
    else:
        df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Error loading file: {e}")
    st.stop()

def normalize(col):
    return re.sub(r"\s+", " ", str(col).replace("\n", " ")).strip()

def make_unique(cols):
    seen = {}
    result = []
    for c in cols:
        c = normalize(c)
        if c not in seen:
            seen[c] = 0
            result.append(c)
        else:
            seen[c] += 1
            result.append(f"{c}__{seen[c]}")
    return result

df.columns = make_unique(df.columns)

# ==========================================================
# SMART AUTO COLUMN MAPPING
# ==========================================================
def find_col(pattern):
    for c in df.columns:
        if re.search(pattern, c.lower()):
            return c
    return df.columns[0] # Failsafe to prevent "None" errors

AUTO_MAP = {
    "Site ID": find_col(r"site.*id"),
    "Cluster": find_col(r"cluster"),
    "Town/District": find_col(r"town|district|city"),
    "TOCO": find_col(r"toco"),
    "Battery Backup (Hrs)": find_col(r"battery.*backup.*hrs|bb.*hrs"),
    "DG Automation": find_col(r"dg.*automation|dg.*status"),
    "SNMP Communicated": find_col(r"snmp"),
    "RM Count": find_col(r"rm.*count|rm.*n\+1"),
}

with st.sidebar:
    with st.expander("🔗 Geography & Hierarchy Mapping", expanded=False):
        def pick(label, default):
            cols = df.columns.tolist()
            idx = cols.index(default) if default in cols else 0
            return st.selectbox(label, cols, index=idx)

        COL_SITE    = pick("Site ID", AUTO_MAP["Site ID"])
        COL_CLUSTER = pick("Cluster Column", AUTO_MAP["Cluster"])
        COL_TOWN    = pick("Town/District Column", AUTO_MAP["Town/District"])
        COL_TOCO    = pick("TOCO Column", AUTO_MAP["TOCO"])

    with st.expander("🔗 KPI Column Mapping", expanded=False):
        COL_BB      = pick("Battery Backup (Hrs)", AUTO_MAP["Battery Backup (Hrs)"])
        COL_DG      = pick("DG Automation Status", AUTO_MAP["DG Automation"])
        COL_SNMP    = pick("SNMP Communicated", AUTO_MAP["SNMP Communicated"])
        COL_RM      = pick("RM Count (N+1)", AUTO_MAP["RM Count"])

# ==========================================================
# SMART DYNAMIC KPI LOGIC (No Hardcoded "Yes/No")
# ==========================================================
with st.sidebar:
    st.markdown("---")
    st.markdown("### ✅ Define Failure Conditions")
    st.caption("Select what constitutes a FAILURE for each KPI.")

    USE_BB = st.checkbox("Check Battery Backup", True)
    if USE_BB:
        BB_THRESHOLD = st.number_input("Fail if Battery (Hrs) is Less Than:", value=4.0, step=0.5)

    # Function to auto-guess failure words just to help pre-populate the dropdown
    def get_fail_defaults(col):
        opts = df[col].astype(str).unique().tolist()
        return [x for x in opts if any(k in x.lower() for k in ["fail", "no", "degraded", "not", "timeout"])]

    USE_DG = st.checkbox("Check DG Automation", True)
    if USE_DG:
        DG_FAIL_STATES = st.multiselect(
            "DG Failure Statuses:", 
            options=df[COL_DG].astype(str).unique().tolist(),
            default=get_fail_defaults(COL_DG)
        )

    USE_SNMP = st.checkbox("Check SNMP", True)
    if USE_SNMP:
        SNMP_FAIL_STATES = st.multiselect(
            "SNMP Failure Statuses:", 
            options=df[COL_SNMP].astype(str).unique().tolist(),
            default=get_fail_defaults(COL_SNMP)
        )

    USE_RM = st.checkbox("Check RM Count", True)
    if USE_RM:
        RM_FAIL_STATES = st.multiselect(
            "RM Failure Statuses:", 
            options=df[COL_RM].astype(str).unique().tolist(),
            default=get_fail_defaults(COL_RM)
        )

# Apply Logic Safely
df["_bb_fail"]   = (pd.to_numeric(df[COL_BB], errors="coerce").fillna(99) < BB_THRESHOLD) if USE_BB else False
df["_dg_fail"]   = df[COL_DG].astype(str).isin(DG_FAIL_STATES) if USE_DG else False
df["_snmp_fail"] = df[COL_SNMP].astype(str).isin(SNMP_FAIL_STATES) if USE_SNMP else False
df["_rm_fail"]   = df[COL_RM].astype(str).isin(RM_FAIL_STATES) if USE_RM else False

df["_fail_count"] = df[["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]].sum(axis=1)
df["_any_fail"] = df["_fail_count"] > 0

# ==========================================================
# MAIN DASHBOARD (GLIMPSE STYLE)
# ==========================================================
st.title("📊 Network Diagnostics & KPI Dashboard")

# Top Level Filter
clusters = ["All"] + sorted(df[COL_CLUSTER].dropna().astype(str).unique().tolist())
selected_cluster = st.selectbox("📍 Filter Dataset by Cluster (e.g., BH_PATNA)", clusters)

fdf = df if selected_cluster == "All" else df[df[COL_CLUSTER] == selected_cluster]

total = len(fdf)
ok_count = int((~fdf["_any_fail"]).sum())
not_ok_count = int(fdf["_any_fail"].sum())
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
    
    # Map selection to actual column
    dim_col = COL_CLUSTER if analysis_dim == "Cluster" else (COL_TOWN if analysis_dim == "Town/District" else COL_TOCO)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ❌ High-Level Failure Summary")
    summary_data = {
        "Battery": int(fdf["_bb_fail"].sum()),
        "DG Automation": int(fdf["_dg_fail"].sum()),
        "SNMP": int(fdf["_snmp_fail"].sum()),
        "RM (N+1)": int(fdf["_rm_fail"].sum()),
    }
    st.dataframe(pd.DataFrame(list(summary_data.items()), columns=["KPI Category", "Sites Failed"]).set_index("KPI Category"), use_container_width=True)


with col_chart:
    st.subheader(f"📈 Degraded Sites Distribution (by {analysis_dim})")
    
    # Create data for the Stacked Bar Chart
    if not_ok_count > 0:
        # Group by selected dimension and sum the failure flags
        chart_data = fdf[fdf["_any_fail"]].groupby(dim_col)[["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]].sum()
        
        # Rename columns for the chart legend
        chart_data.columns = ["Battery Issue", "DG Issue", "SNMP Issue", "RM Issue"]
        
        # Streamlit's native bar_chart automatically stacks when provided multiple columns!
        st.bar_chart(chart_data)
    else:
        st.success("No degraded sites to display for current filter.")

# ==========================================================
# ACTIONABLE DATA TABLE
# ==========================================================
st.markdown("---")
st.subheader("📋 Actionable Sites List (Filtered to Degraded)")

if not_ok_count > 0:
    # Build a clean view of just the failed sites
    worst_df = fdf[fdf["_any_fail"]].sort_values("_fail_count", ascending=False)
    
    # Create a dynamic "Failure Reason" text column for easier reading
    worst_df["Failure Summary"] = ""
    worst_df.loc[worst_df["_bb_fail"], "Failure Summary"] += "Battery; "
    worst_df.loc[worst_df["_dg_fail"], "Failure Summary"] += "DG; "
    worst_df.loc[worst_df["_snmp_fail"], "Failure Summary"] += "SNMP; "
    worst_df.loc[worst_df["_rm_fail"], "Failure Summary"] += "RM; "
    
    display_cols = [COL_SITE, COL_CLUSTER, COL_TOWN, COL_TOCO, "Failure Summary", COL_BB, COL_DG, COL_SNMP, COL_RM]
    
    # Ensure columns exist before displaying
    display_cols = [c for c in display_cols if c in worst_df.columns]
    
    st.dataframe(
        worst_df[display_cols].style.map(lambda x: 'background-color: rgba(255, 75, 75, 0.1)', subset=['Failure Summary']),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("All sites are communicating and 100% OK.")
