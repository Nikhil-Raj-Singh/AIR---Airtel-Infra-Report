# ==========================================================
# app.py — Airtel Infra-Health Dashboard (Corporate Safe)
# ==========================================================

# ------------------ Auto Streamlit Launcher ----------------
import os, sys, subprocess

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

# ------------------ Imports ------------------
import re
import pandas as pd
import streamlit as st
import numpy as np

st.set_page_config(
    page_title="Site KPI Health Dashboard",
    layout="wide"
)

# ==========================================================
# SIDEBAR (CONTROL CENTER)
# ==========================================================
with st.sidebar:
    st.title("⚙ Controls")

    uploaded_file = st.file_uploader(
        "Upload Excel / CSV",
        type=["xlsx", "xls", "csv"]
    )

if not uploaded_file:
    st.info("Upload KPI Excel / CSV file to start")
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
    st.error(f"Error reading file: {e}")
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
    return df.columns[0] # SAFE FALLBACK: Return first col instead of None

# Expanded regex to catch more variations based on typical telecom data
AUTO_MAP = {
    "Site ID": find_col(r"site.*id"),
    "Cluster": find_col(r"cluster"),
    "Site Type (DG/Non-DG)": find_col(r"dg.*non|site.*type|macro"), # Need this for smart logic
    "Battery Backup (Hrs)": find_col(r"battery.*backup|bb.*hrs"),
    "DG Automation": find_col(r"dg.*automation|dg.*status"),
    "SNMP Communicated": find_col(r"snmp"),
    "RM Count": find_col(r"rm.*count|rm.*n\+1"),
}

with st.sidebar:
    st.markdown("---")
    
    with st.expander("🔗 Column Mapping (Auto-detected)", expanded=False):
        def pick(label, default):
            cols = df.columns.tolist()
            # Failsafe index lookup
            idx = cols.index(default) if default in cols else 0
            return st.selectbox(label, cols, index=idx)

        COL_SITE    = pick("Site ID", AUTO_MAP["Site ID"])
        COL_CLUSTER = pick("Cluster", AUTO_MAP["Cluster"])
        COL_TYPE    = pick("Site Type (DG/Non-DG)", AUTO_MAP["Site Type (DG/Non-DG)"])
        COL_BB      = pick("Battery Backup (Hrs)", AUTO_MAP["Battery Backup (Hrs)"])
        COL_DG      = pick("DG Automation Status", AUTO_MAP["DG Automation"])
        COL_SNMP    = pick("SNMP Communicated", AUTO_MAP["SNMP Communicated"])
        COL_RM      = pick("RM Count (N+1)", AUTO_MAP["RM Count"])

    # KPI Configuration UI
    st.markdown("### ✅ Configure 100% OK Rules")
    
    USE_BB = st.checkbox("Battery Backup Rule", True)
    if USE_BB:
        BB_THRESHOLD = st.number_input("Min Battery (Hrs) for OK", value=4.0, step=0.5)
        
    USE_DG = st.checkbox("DG Automation Rule", True)
    if USE_DG:
        # Smart: Let user pick what "Failure" actually is from their data
        dg_opts = df[COL_DG].astype(str).unique().tolist()
        default_fails = [x for x in dg_opts if "fail" in x.lower() or "no" in x.lower() or "not" in x.lower()]
        DG_FAIL_STATES = st.multiselect("Statuses that mean DG Failed:", dg_opts, default=default_fails)
        
    USE_SNMP = st.checkbox("SNMP Rule", True)
    if USE_SNMP:
        snmp_opts = df[COL_SNMP].astype(str).unique().tolist()
        snmp_fails = [x for x in snmp_opts if "fail" in x.lower() or "no" in x.lower()]
        SNMP_FAIL_STATES = st.multiselect("Statuses that mean SNMP Failed:", snmp_opts, default=snmp_fails)

    USE_RM = st.checkbox("RM Count Rule", True)
    if USE_RM:
        rm_opts = df[COL_RM].astype(str).unique().tolist()
        rm_fails = [x for x in rm_opts if "fail" in x.lower() or "no" in x.lower() or "degrade" in x.lower()]
        RM_FAIL_STATES = st.multiselect("Statuses that mean RM Failed:", rm_opts, default=rm_fails)


# ==========================================================
# SMART NESTED KPI LOGIC
# ==========================================================
# Initialize failure tracking columns
for flag in ["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]:
    df[flag] = False
df["Failure_Reasons"] = ""

# 1. Battery Logic
if USE_BB:
    bb_mask = pd.to_numeric(df[COL_BB], errors="coerce").fillna(99) < BB_THRESHOLD
    df.loc[bb_mask, "_bb_fail"] = True
    df.loc[bb_mask, "Failure_Reasons"] += f"Low BB (<{BB_THRESHOLD}h); "

# 2. SMART DG Logic (Only fails if it's actually a DG site)
if USE_DG:
    is_dg_site = df[COL_TYPE].astype(str).str.contains("DG", case=False, na=False)
    dg_status_failed = df[COL_DG].astype(str).isin(DG_FAIL_STATES)
    
    dg_mask = is_dg_site & dg_status_failed
    df.loc[dg_mask, "_dg_fail"] = True
    df.loc[dg_mask, "Failure_Reasons"] += "DG Auto Failed; "

# 3. SNMP Logic
if USE_SNMP:
    snmp_mask = df[COL_SNMP].astype(str).isin(SNMP_FAIL_STATES)
    df.loc[snmp_mask, "_snmp_fail"] = True
    df.loc[snmp_mask, "Failure_Reasons"] += "SNMP Failed; "

# 4. RM Logic
if USE_RM:
    rm_mask = df[COL_RM].astype(str).isin(RM_FAIL_STATES)
    df.loc[rm_mask, "_rm_fail"] = True
    df.loc[rm_mask, "Failure_Reasons"] += "RM (N+1) Failed; "

# Tally the results
df["_fail_count"] = df[["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]].sum(axis=1)
df["_any_fail"] = df["_fail_count"] > 0

# Clean up reason strings
df['Failure_Reasons'] = df['Failure_Reasons'].str.rstrip('; ').replace("", "100% OK")

# ==========================================================
# MAIN DASHBOARD UI
# ==========================================================
clusters = ["All"] + sorted(df[COL_CLUSTER].astype(str).dropna().unique().tolist())
selected_cluster = st.selectbox("📍 Filter by Cluster", clusters)

fdf = df if selected_cluster == "All" else df[df[COL_CLUSTER] == selected_cluster]

# Metrics
total = len(fdf)
ok_count = int((~fdf["_any_fail"]).sum())
not_ok_count = int(fdf["_any_fail"].sum())

ok_pct = (ok_count / total * 100) if total else 0
not_ok_pct = (not_ok_count / total * 100) if total else 0

c1, c2, c3 = st.columns(3)
c1.metric("✅ 100% OK Sites", f"{ok_count}  ({ok_pct:.1f}%)")
c2.metric("❌ Not OK Sites", f"{not_ok_count}  ({not_ok_pct:.1f}%)")
c3.metric("📊 Total Sites in View", f"{total:,}")

st.divider()

# Tabs
tab_overview, tab_notok, tab_kpi = st.tabs(["📊 Overview", "🚨 Actionable Sites", "🔍 KPI Deep Dive"])

with tab_overview:
    st.subheader("Failure Distribution")
    if selected_cluster == "All":
        st.bar_chart(fdf[fdf["_any_fail"]][COL_CLUSTER].value_counts(), color="#ff4b4b")
    else:
        st.bar_chart({
            "Battery": int(fdf["_bb_fail"].sum()),
            "DG": int(fdf["_dg_fail"].sum()),
            "SNMP": int(fdf["_snmp_fail"].sum()),
            "RM": int(fdf["_rm_fail"].sum()),
        }, color="#ff9f36")

with tab_notok:
    st.subheader("🚨 Sites Requiring Attention")
    
    # Create a cleaner view for the user
    display_cols = [COL_SITE, COL_CLUSTER, COL_TYPE, COL_BB, COL_DG, COL_SNMP, COL_RM, "Failure_Reasons"]
    worst_df = fdf[fdf["_any_fail"]].copy()
    
    st.dataframe(
        worst_df[display_cols].style.map(lambda x: 'background-color: rgba(255, 75, 75, 0.1)', subset=['Failure_Reasons']),
        use_container_width=True,
        hide_index=True
    )

with tab_kpi:
    st.subheader("🔍 KPI Deep Dive")
    kpi_choice = st.selectbox("Analyze Specific KPI Failure", ["Battery Backup", "DG Automation", "SNMP Communicated", "RM Count"])
    
    flag_map = {
        "Battery Backup": "_bb_fail",
        "DG Automation": "_dg_fail",
        "SNMP Communicated": "_snmp_fail",
        "RM Count": "_rm_fail",
    }
    
    sub = fdf[fdf[flag_map[kpi_choice]]]
    
    colA, colB = st.columns(2)
    colA.metric("❌ Sites Failed this KPI", len(sub))
    colB.metric("📍 Impacted Clusters", sub[COL_CLUSTER].nunique() if not sub.empty else 0)
    
    if not sub.empty:
        st.bar_chart(sub[COL_CLUSTER].value_counts())
        st.dataframe(sub[[COL_SITE, COL_CLUSTER, "Failure_Reasons"]], use_container_width=True, hide_index=True)
