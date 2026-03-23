# ==========================================================
# app.py — Airtel Infra-Health Dashboard (Smart Edition)
# RUN USING: python app.py
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

st.set_page_config(page_title="Site KPI Health Dashboard", layout="wide")

# ==========================================================
# SIDEBAR (CONTROL CENTER)
# ==========================================================
with st.sidebar:
    st.title("⚙ Dashboard Engine")

    uploaded_file = st.file_uploader("📂 Upload KPI Excel / CSV", type=["xlsx", "xls", "csv"])

if not uploaded_file:
    st.info("👋 Welcome! Please upload your KPI Excel / CSV file in the sidebar to start.")
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
def smart_find_col(keywords):
    # Converts keywords to lower case and looks for them in column names
    for col in df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in keywords):
            return col
    return df.columns[0] # Fallback to first column if nothing matches

AUTO_MAP = {
    "Site ID": smart_find_col(["site id", "site_id", "siteid"]),
    "Cluster": smart_find_col(["cluster", "zone"]),
    "DG Type (Macro/ULS)": smart_find_col(["dg/non", "site type", "macro"]),
    "DG Automation Status": smart_find_col(["automation status", "snmp", "dg auto"]),
    "Battery Backup (Hrs)": smart_find_col(["battery backup (hrs)", "battery", "backup"]),
    "RM Count": smart_find_col(["rm count", "rm (n+1)", "rm status"]),
}

with st.sidebar:
    with st.expander("🔗 Data Column Mapping", expanded=False):
        st.caption("Verify that your Excel columns matched correctly.")
        COL_SITE    = st.selectbox("Site ID", df.columns, index=df.columns.get_loc(AUTO_MAP["Site ID"]))
        COL_CLUSTER = st.selectbox("Cluster", df.columns, index=df.columns.get_loc(AUTO_MAP["Cluster"]))
        COL_DG_TYPE = st.selectbox("DG / Non-DG Type", df.columns, index=df.columns.get_loc(AUTO_MAP["DG Type (Macro/ULS)"]))
        COL_DG_STAT = st.selectbox("DG Automation Status", df.columns, index=df.columns.get_loc(AUTO_MAP["DG Automation Status"]))
        COL_BB      = st.selectbox("Battery Backup (Hrs)", df.columns, index=df.columns.get_loc(AUTO_MAP["Battery Backup (Hrs)"]))
        COL_RM      = st.selectbox("RM Count (N+1)", df.columns, index=df.columns.get_loc(AUTO_MAP["RM Count"]))

    st.markdown("---")
    st.markdown("### ✅ Critical KPI Rules")
    
    USE_BB = st.checkbox("Check Battery Backup", True)
    if USE_BB:
        BB_THRESHOLD = st.number_input("Min Battery OK (Hrs)", value=4.0, step=0.5)

    USE_DG = st.checkbox("Check DG Automation", True)
    if USE_DG:
        # Dynamically fetch available statuses from the data for the user to select what counts as 'Failed'
        available_statuses = df[COL_DG_STAT].astype(str).unique().tolist()
        default_fails = [s for s in available_statuses if s.lower() in ["failed", "not reachable", "timeout", "no"]]
        DG_FAIL_STATES = st.multiselect("SNMP Failure Statuses:", available_statuses, default=default_fails)

    USE_RM = st.checkbox("Check RM Count (N+1)", True)
    if USE_RM:
        available_rm = df[COL_RM].astype(str).unique().tolist()
        rm_default_fails = [s for s in available_rm if s.lower() in ["failed", "no", "not ok", "0"]]
        RM_FAIL_STATES = st.multiselect("RM Failure Statuses:", available_rm, default=rm_default_fails)

    st.markdown("---")
    st.markdown("### 🏗️ Custom Rule (Optional)")
    use_custom = st.checkbox("Enable Custom Rule")
    if use_custom:
        custom_col = st.selectbox("Target Column", df.columns)
        custom_val = st.text_input("Fails if exactly equals:")

# ==========================================================
# SMART NESTED KPI LOGIC (VECTORIZED)
# ==========================================================
# Initialize trackers
df["Is_100_OK"] = True
df["Failure_Reasons"] = ""
df["_fail_count"] = 0

# 1. SMART DG LOGIC (Nested)
if USE_DG:
    # First check if it's actually a DG site
    is_dg = df[COL_DG_TYPE].astype(str).str.contains("DG", case=False, na=False)
    # Then check if the status is in your selected failure list
    snmp_failed = df[COL_DG_STAT].astype(str).isin(DG_FAIL_STATES)
    
    # Nested Condition: Fails ONLY if it is a DG AND SNMP failed
    dg_mask = is_dg & snmp_failed
    
    df.loc[dg_mask, "Is_100_OK"] = False
    df.loc[dg_mask, "Failure_Reasons"] += "DG Auto Failed; "
    df.loc[dg_mask, "_fail_count"] += 1

# 2. BATTERY LOGIC
if USE_BB:
    # Safely convert to numeric, turning text like 'N/A' into NaN, then filling with 99 so it passes
    bb_failed = pd.to_numeric(df[COL_BB], errors='coerce').fillna(999) < BB_THRESHOLD
    
    df.loc[bb_failed, "Is_100_OK"] = False
    df.loc[bb_failed, "Failure_Reasons"] += f"Low Battery (<{BB_THRESHOLD}h); "
    df.loc[bb_failed, "_fail_count"] += 1

# 3. RM LOGIC
if USE_RM:
    rm_failed = df[COL_RM].astype(str).isin(RM_FAIL_STATES)
    
    df.loc[rm_failed, "Is_100_OK"] = False
    df.loc[rm_failed, "Failure_Reasons"] += "RM Failed; "
    df.loc[rm_failed, "_fail_count"] += 1

# 4. CUSTOM RULE
if use_custom and custom_val:
    custom_failed = df[custom_col].astype(str).str.strip().str.lower() == custom_val.strip().lower()
    df.loc[custom_failed, "Is_100_OK"] = False
    df.loc[custom_failed, "Failure_Reasons"] += f"Custom Rule ({custom_col}); "
    df.loc[custom_failed, "_fail_count"] += 1

# Clean up diagnostic text
df['Failure_Reasons'] = df['Failure_Reasons'].str.rstrip('; ').replace("", "None")

# ==========================================================
# CLUSTER FILTER
# ==========================================================
clusters = ["All"] + sorted(df[COL_CLUSTER].dropna().astype(str).unique().tolist())
selected_cluster = st.selectbox("📍 Filter by Cluster", clusters)

fdf = df if selected_cluster == "All" else df[df[COL_CLUSTER] == selected_cluster]

# ==========================================================
# KPI SUMMARY CARDS
# ==========================================================
total = len(fdf)
ok_count = fdf["Is_100_OK"].sum()
not_ok_count = total - ok_count

ok_pct = (ok_count / total * 100) if total else 0
not_ok_pct = (not_ok_count / total * 100) if total else 0

c1, c2, c3 = st.columns(3)
c1.metric("📊 Total Sites", f"{total:,}")
c2.metric("✅ 100% OK Sites", f"{ok_count:,}  ({ok_pct:.1f}%)")
c3.metric("🚨 Not OK Sites", f"{not_ok_count:,}  ({not_ok_pct:.1f}%)", delta=f"-{not_ok_count}", delta_color="inverse")

st.divider()

# ==========================================================
# TABS
# ==========================================================
tab_overview, tab_notok, tab_kpi = st.tabs(["📊 Overview", "🚨 Actionable Sites", "🔍 Deep Dive"])

# ==========================================================
# TAB 1 — OVERVIEW
# ==========================================================
with tab_overview:
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Distribution of Failure Reasons")
        if not_ok_count > 0:
            # Explode splits up "Low Battery; DG Auto Failed" into two counts for accurate graphing
            reasons_df = fdf[fdf["Is_100_OK"] == False]['Failure_Reasons'].str.split('; ').explode().value_counts()
            st.bar_chart(reasons_df, color="#ff4b4b")
        else:
            st.success("No failures to display!")

    with col_chart2:
        st.subheader("Not OK Sites by Cluster")
        if selected_cluster == "All" and not_ok_count > 0:
            cluster_fails = fdf[fdf["Is_100_OK"] == False][COL_CLUSTER].value_counts()
            st.bar_chart(cluster_fails, color="#ff9f36")
        elif not_ok_count > 0:
             st.info(f"Viewing specific cluster: {selected_cluster}")
        else:
             st.success("All sites OK!")

# ==========================================================
# TAB 2 — ACTIONABLE SITES (WORST AFFECTED)
# ==========================================================
with tab_notok:
    st.subheader("🚨 Sites Requiring Immediate Action")
    
    if not_ok_count > 0:
        worst_df = fdf[fdf["Is_100_OK"] == False].sort_values("_fail_count", ascending=False)
        
        # Select the most important columns to display to keep the table clean
        cols_to_show = [COL_SITE, COL_CLUSTER, "Failure_Reasons", "_fail_count", COL_DG_TYPE, COL_DG_STAT, COL_BB, COL_RM]
        # Only show columns that actually exist in the dataframe
        cols_to_show = [c for c in cols_to_show if c in worst_df.columns]
        
        st.dataframe(
            worst_df[cols_to_show].style.map(lambda x: 'background-color: rgba(255, 75, 75, 0.15)', subset=['Failure_Reasons']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No action required. All sites are 100% OK.")

# ==========================================================
# TAB 3 — KPI DEEP DIVE
# ==========================================================
with tab_kpi:
    st.subheader("🔍 Site Search & Raw Data")
    
    search_query = st.text_input("Search by Site ID, Town, or Status:")
    
    if search_query:
        # Search across all columns as strings
        mask = fdf.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        search_result = fdf[mask]
        st.write(f"Found {len(search_result)} matching sites:")
        
        st.dataframe(
            search_result.drop(columns=["_fail_count"]), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.write("Full dataset overview:")
        st.dataframe(
            fdf.drop(columns=["_fail_count"]).head(100), 
            use_container_width=True, 
            hide_index=True
        )
