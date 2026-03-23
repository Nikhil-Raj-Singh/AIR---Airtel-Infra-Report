# ==========================================================
# app.py — AIR V2: Dynamic Infra-Health Dashboard 
# RUN USING: python app.py
# ==========================================================

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

st.set_page_config(page_title="AIR Command Center", layout="wide", initial_sidebar_state="expanded")

# ==========================================================
# CUSTOM CSS (To mimic the GLIMPSE Dashboard Cards)
# ==========================================================
st.markdown("""
<style>
    /* Style the metric cards to look like dashboard panels */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #d3d3d3;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        text-align: center;
    }
    div[data-testid="metric-container"] > label {
        font-weight: bold;
        color: #555555;
        font-size: 1.1rem;
    }
    div[data-testid="metric-container"] > div > div {
        font-size: 2rem !important;
        color: #1f77b4;
    }
    /* Top Filter Bar styling */
    .stSelectbox label {
        font-weight: 600;
        color: #e63946;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE INITIALIZATION
# ==========================================================
if 'custom_rules' not in st.session_state:
    st.session_state.custom_rules = []

# ==========================================================
# FAST DATA LOADER (Cached for 1M+ Records)
# ==========================================================
@st.cache_data(show_spinner=False)
def load_and_clean_data(file):
    if file.name.endswith(".csv"):
        df = pd.read_csv(file, engine="python", encoding="utf-8")
    else:
        df = pd.read_excel(file)
    
    # Clean column names for speed and uniqueness
    def normalize(col):
        return re.sub(r"\s+", " ", str(col).replace("\n", " ")).strip()
    
    seen = {}
    result = []
    for c in df.columns:
        c = normalize(c)
        if c not in seen:
            seen[c] = 0
            result.append(c)
        else:
            seen[c] += 1
            result.append(f"{c}__{seen[c]}")
            
    df.columns = result
    
    # Pre-optimize data types for speed
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
            
    return df

# ==========================================================
# SIDEBAR: SETUP & RULE BUILDER
# ==========================================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Airtel_logo.svg/512px-Airtel_logo.svg.png", width=150)
    st.title("⚙️ Data & Rules Setup")
    
    uploaded_file = st.file_uploader("Upload Telecom Data (CSV/Excel)", type=["xlsx", "xls", "csv"])
    
    if not uploaded_file:
        st.info("Please upload your dataset to begin processing.")
        st.stop()

# Load data into memory (Fast Cache)
with st.spinner("Processing 1M+ Records into memory..."):
    raw_df = load_and_clean_data(uploaded_file)

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🗺️ 1. Define Hierarchy")
    cols = ["None"] + raw_df.columns.tolist()
    
    # Dynamic Hierarchy mapping
    geo_l1 = st.selectbox("Top Level (e.g., State)", cols, index=0)
    geo_l2 = st.selectbox("Mid Level (e.g., District)", cols, index=0)
    geo_l3 = st.selectbox("Base Level (e.g., Cluster)", cols, index=0)
    
    hierarchy_cols = [c for c in [geo_l1, geo_l2, geo_l3] if c != "None"]

    st.markdown("---")
    st.markdown("### 🚨 2. Dynamic KPI Rule Builder")
    st.caption("Define conditions that mark a site as 'FAIL'")
    
    with st.expander("➕ Add New Rule", expanded=True):
        rule_name = st.text_input("Rule Name (e.g., 'Low Battery')")
        rule_col = st.selectbox("Target Column", raw_df.columns.tolist())
        rule_op = st.selectbox("Condition", ["==", "!=", ">", "<", ">=", "<=", "Contains (Text)"])
        rule_val = st.text_input("Value / Threshold")
        
        if st.button("Save Rule", use_container_width=True):
            if rule_name and rule_val:
                st.session_state.custom_rules.append({
                    "name": rule_name, "col": rule_col, "op": rule_op, "val": rule_val
                })
                st.rerun()
            else:
                st.warning("Please provide a name and value.")

    # Show active rules
    if st.session_state.custom_rules:
        st.markdown("**Active Rules (FAIL Conditions):**")
        for i, r in enumerate(st.session_state.custom_rules):
            c1, c2 = st.columns([8, 2])
            c1.caption(f"**{r['name']}**: {r['col']} {r['op']} {r['val']}")
            if c2.button("❌", key=f"del_{i}"):
                st.session_state.custom_rules.pop(i)
                st.rerun()

# ==========================================================
# VECTORIZED RULE ENGINE (Runs instantly on 1M rows)
# ==========================================================
@st.cache_data(show_spinner=False)
def apply_rules(_df, rules):
    df = _df.copy()
    fail_columns = []
    
    for r in rules:
        col, op, val = r['col'], r['op'], r['val']
        fail_col_name = f"FAIL_{r['name']}"
        fail_columns.append(fail_col_name)
        
        try:
            if op == "==":
                df[fail_col_name] = df[col].astype(str).str.lower().str.strip() == str(val).lower().strip()
            elif op == "!=":
                df[fail_col_name] = df[col].astype(str).str.lower().str.strip() != str(val).lower().strip()
            elif op == "Contains (Text)":
                df[fail_col_name] = df[col].astype(str).str.lower().str.contains(str(val).lower().strip(), na=False)
            else:
                # Numeric comparisons
                numeric_col = pd.to_numeric(df[col], errors='coerce')
                num_val = float(val)
                if op == ">": df[fail_col_name] = numeric_col > num_val
                elif op == "<": df[fail_col_name] = numeric_col < num_val
                elif op == ">=": df[fail_col_name] = numeric_col >= num_val
                elif op == "<=": df[fail_col_name] = numeric_col <= num_val
        except Exception:
            # Fallback if conversion fails
            df[fail_col_name] = False 
            
    if fail_columns:
        df["_TOTAL_FAILS"] = df[fail_columns].sum(axis=1)
        df["_IS_OK"] = df["_TOTAL_FAILS"] == 0
    else:
        df["_TOTAL_FAILS"] = 0
        df["_IS_OK"] = True
        
    return df, fail_columns

# Apply rules efficiently
processed_df, active_fail_cols = apply_rules(raw_df, st.session_state.custom_rules)

# ==========================================================
# TOP FILTER BAR (Dynamic Drilldown)
# ==========================================================
st.markdown("### 🔍 Actionable Filters")
filter_cols = st.columns(len(hierarchy_cols) if hierarchy_cols else 1)

fdf = processed_df.copy()

# Dynamic cascade filtering
for i, h_col in enumerate(hierarchy_cols):
    with filter_cols[i]:
        options = ["All"] + sorted(fdf[h_col].dropna().unique().tolist())
        selection = st.selectbox(f"{h_col}", options, key=f"filter_{h_col}")
        if selection != "All":
            fdf = fdf[fdf[h_col] == selection]

# ==========================================================
# DASHBOARD CARDS (Like GLIMPSE UI)
# ==========================================================
st.markdown("<br>", unsafe_allow_html=True)
card_cols = st.columns(4)

total_sites = len(fdf)
ok_sites = fdf["_IS_OK"].sum() if total_sites > 0 else 0
not_ok_sites = total_sites - ok_sites

card_cols[0].metric("📡 Total Sites", f"{total_sites:,}")
card_cols[1].metric("✅ 100% OK Sites", f"{ok_sites:,}")
card_cols[2].metric("🚨 Sites w/ Alarms", f"{not_ok_sites:,}")

# Find worst performing KPI
if active_fail_cols and total_sites > 0:
    worst_kpi = fdf[active_fail_cols].sum().idxmax().replace("FAIL_", "")
    worst_count = fdf[active_fail_cols].sum().max()
    card_cols[3].metric(f"📉 Worst KPI: {worst_kpi}", f"{int(worst_count):,} Fails")
else:
    card_cols[3].metric("📉 Worst KPI", "No Rules Set")

st.markdown("<hr style='margin: 10px 0px 30px 0px'>", unsafe_allow_html=True)

# ==========================================================
# MAIN DASHBOARD PANELS
# ==========================================================
col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.markdown("#### 📊 KPI Failure Distribution")
    if active_fail_cols:
        # Sum all failures and plot
        fail_counts = fdf[active_fail_cols].sum().rename(index=lambda x: x.replace("FAIL_", ""))
        st.bar_chart(fail_counts, use_container_width=True)
    else:
        st.info("Add KPI Rules in the sidebar to see failure distribution.")

with col_right:
    st.markdown("#### 🗺️ Geographic Bifurcation")
    if hierarchy_cols and not fdf.empty:
        # Group by the deepest selected hierarchy level
        deepest_level = hierarchy_cols[-1]
        for col in reversed(hierarchy_cols):
            if st.session_state[f"filter_{col}"] == "All":
                deepest_level = col
        
        geo_fails = fdf[~fdf['_IS_OK']][deepest_level].value_counts().head(10)
        st.bar_chart(geo_fails, use_container_width=True)
    else:
        st.info("Map Hierarchy in the sidebar to view geographical impact.")

# ==========================================================
# ACTIONABLE DATA TABLE (Lazy Loaded for Speed)
# ==========================================================
st.markdown("#### 🛠️ Actionable Sites (Not OK)")

if active_fail_cols:
    action_view = st.radio("View Mode", ["Show Only Failed Sites", "Show All Sites"], horizontal=True)
    
    view_df = fdf[~fdf['_IS_OK']] if action_view == "Show Only Failed Sites" else fdf
    view_df = view_df.sort_values(by="_TOTAL_FAILS", ascending=False)
    
    # Drop internal helper columns for clean view, but keep actual fail flags
    display_cols = [c for c in view_df.columns if not c.startswith("_")]
    
    # Add a download button for fast extraction
    csv_data = view_df[display_cols].to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Current View to CSV", data=csv_data, file_name="Actionable_Sites.csv", mime="text/csv")
    
    st.dataframe(view_df[display_cols].head(1000), use_container_width=True)
    st.caption(f"Showing top 1000 records for performance. Export to see all {len(view_df):,} rows.")
else:
    st.dataframe(fdf.head(1000), use_container_width=True)
