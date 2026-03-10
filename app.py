# ==========================================================
# app.py — Airtel Infra-Health Dashboard (Corporate Safe)
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

    BB_THRESHOLD = st.number_input(
        "Battery Backup OK (Hrs)",
        value=4.0,
        step=0.5
    )

    st.markdown("---")
    st.markdown("### ✅ KPIs used for **100% OK** check")

    USE_BB   = st.checkbox("Battery Backup", True)
    USE_DG   = st.checkbox("DG Automation", True)
    USE_SNMP = st.checkbox("SNMP Communicated", True)
    USE_RM   = st.checkbox("RM Count (N+1)", True)

if not uploaded_file:
    st.info("Upload KPI Excel / CSV file to start")
    st.stop()

# ==========================================================
# LOAD DATA
# ==========================================================
if uploaded_file.name.endswith(".csv"):
    df = pd.read_csv(uploaded_file, engine="python", encoding="utf-8")
else:
    df = pd.read_excel(uploaded_file)

# ==========================================================
# CLEAN & MAKE COLUMNS UNIQUE (CRITICAL)
# ==========================================================
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
assert df.columns.is_unique

# ==========================================================
# SMART AUTO COLUMN MAPPING
# ==========================================================
def find_col(pattern):
    for c in df.columns:
        if re.search(pattern, c.lower()):
            return c
    return None

AUTO_MAP = {
    "Site ID": find_col(r"site.*id"),
    "Cluster": find_col(r"cluster"),
    "Battery Backup (Hrs)": find_col(r"battery.*backup.*hrs"),
    "DG Automation": find_col(r"dg.*automation"),
    "SNMP Communicated": find_col(r"snmp.*communicated"),
    "RM Count": find_col(r"rm.*count"),
}

# ==========================================================
# COLUMN MAPPING UI (COLLAPSIBLE)
# ==========================================================
with st.sidebar.expander("🔗 Column Mapping (Auto‑detected)", expanded=False):
    st.dataframe(
        pd.DataFrame(
            AUTO_MAP.items(),
            columns=["KPI", "Detected Column"]
        ),
        use_container_width=True
    )

    def pick(label, default):
        cols = df.columns.tolist()
        idx = cols.index(default) if default in cols else 0
        return st.selectbox(label, cols, index=idx)

    COL_SITE    = pick("Site ID", AUTO_MAP["Site ID"])
    COL_CLUSTER = pick("Cluster", AUTO_MAP["Cluster"])
    COL_BB      = pick("Battery Backup (Hrs)", AUTO_MAP["Battery Backup (Hrs)"])
    COL_DG      = pick("DG Automation Status", AUTO_MAP["DG Automation"])
    COL_SNMP    = pick("SNMP Communicated", AUTO_MAP["SNMP Communicated"])
    COL_RM      = pick("RM Count (N+1)", AUTO_MAP["RM Count"])

# ==========================================================
# KPI LOGIC
# ==========================================================
def is_yes(x):
    return str(x).strip().lower() in ["yes", "y", "true", "ok"]
def is_ok(x):
    return str(x).strip().lower() in ["OK", "y", "true", "ok"]
def is_no(x):
    return str(x).strip().lower() in ["no", "n", "false"]

df["_bb_fail"]   = USE_BB   & (pd.to_numeric(df[COL_BB], errors="coerce") < BB_THRESHOLD)
df["_dg_fail"]   = USE_DG   & (~df[COL_DG].apply(is_yes))
df["_snmp_fail"] = USE_SNMP & (~df[COL_SNMP].apply(is_yes))

# ✅ RM logic corrected: YES = OK, NO = FAIL
df["_rm_fail"] = USE_RM & df[COL_RM].apply(is_no)

df["_fail_count"] = df[["_bb_fail", "_dg_fail", "_snmp_fail", "_rm_fail"]].sum(axis=1)
df["_any_fail"] = df["_fail_count"] > 0

# ==========================================================
# FILTERS
# ==========================================================
clusters = ["All"] + sorted(df[COL_CLUSTER].dropna().unique().tolist())
selected_cluster = st.selectbox("📍 Select Cluster", clusters)

fdf = df if selected_cluster == "All" else df[df[COL_CLUSTER] == selected_cluster]

# ==========================================================
# KPI SUMMARY CARDS
# ==========================================================
import streamlit as st

total = len(fdf)
ok_count = int((~fdf["_any_fail"]).sum())
not_ok_count = int(fdf["_any_fail"].sum())

# Guard against divide-by-zero if fdf is empty
ok_pct = (ok_count / total * 100) if total else 0
not_ok_pct = (not_ok_count / total * 100) if total else 0

c1, c2, c3 = st.columns(3)

# Show count with percentage in the value
c1.metric("✅ 100% OK Sites", f"{ok_count}  ({ok_pct:.1f}%)")
c2.metric("❌ Not OK Sites", f"{not_ok_count}  ({not_ok_pct:.1f}%)")
c3.metric("📊 Total Sites", f"{total}  " if total else "0 ")

st.divider()

# ==========================================================
# TABS
# ==========================================================
tab_overview, tab_notok, tab_kpi = st.tabs(
    ["📊 Overview", "❌ Not OK Analysis", "🔍 KPI Deep Dive"]
)

# ==========================================================
# TAB 1 — OVERVIEW
# ==========================================================
with tab_overview:
    st.subheader("Failure Distribution")

    if selected_cluster == "All":
        # Cluster-wise view
        st.markdown("### ❌ Not OK Sites by Cluster")
        st.bar_chart(
            fdf[fdf["_any_fail"]][COL_CLUSTER].value_counts()
        )
    else:
        # KPI-wise view for single cluster
        st.markdown(f"### ❌ KPI Failures in {selected_cluster}")
        st.bar_chart({
            "Battery": int(fdf["_bb_fail"].sum()),
            "DG": int(fdf["_dg_fail"].sum()),
            "SNMP": int(fdf["_snmp_fail"].sum()),
            "RM": int(fdf["_rm_fail"].sum()),
        })

# ==========================================================
# TAB 2 — NOT OK ANALYSIS (WORST SITES)
# ==========================================================
with tab_notok:
    st.subheader("🚨 Worst Affected Sites")

    top_n = st.selectbox("Show Top N Sites", [10, 20, 50], index=0)

    worst_df = (
        fdf[fdf["_any_fail"]]
        .sort_values("_fail_count", ascending=False)
    )

    st.dataframe(
        worst_df.head(top_n).drop(
            columns=[c for c in worst_df.columns if c.startswith("_")]
        ),
        use_container_width=True
    )

# ==========================================================
# TAB 3 — KPI DEEP DIVE
# ==========================================================
with tab_kpi:
    st.subheader("🔍 KPI Deep Dive")

    kpi_choice = st.selectbox(
        "Select KPI",
        ["Battery Backup", "DG Automation", "SNMP Communicated", "RM Count"]
    )

    flag_map = {
        "Battery Backup": "_bb_fail",
        "DG Automation": "_dg_fail",
        "SNMP Communicated": "_snmp_fail",
        "RM Count": "_rm_fail",
    }

    sub = fdf[fdf[flag_map[kpi_choice]]]

    c1, c2 = st.columns(2)
    c1.metric("❌ Failed Sites", len(sub))
    c2.metric("📍 Clusters Impacted", sub[COL_CLUSTER].nunique())

    st.markdown("### 📊 Distribution")
    if selected_cluster == "All":
        st.bar_chart(sub[COL_CLUSTER].value_counts())
    else:
        st.bar_chart(sub["_fail_count"].value_counts())

    st.markdown("### 📋 Site Details (All Columns)")
    st.dataframe(
        sub.drop(columns=[c for c in sub.columns if c.startswith("_")]),
        use_container_width=True
    )
