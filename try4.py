# ==========================================================
# app.py — AIR V3: Smart Matrix Dashboard & Conditional Logic
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
    subprocess.run([sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)], check=False)
    sys.exit(0)

# ==========================================================
# CONFIG & CSS
# ==========================================================
st.set_page_config(page_title="AIR Matrix Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px; 
        border-radius: 8px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); text-align: center;
    }
    .metric-title { font-size: 1.1rem; color: #555; font-weight: 600; }
    .metric-value { font-size: 2.2rem; color: #d32f2f; font-weight: bold; }
    .metric-value.ok { color: #2e7d32; }
    .stDataFrame { border: 1px solid #d3d3d3; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE INITIALIZATION
# ==========================================================
if 'smart_rules' not in st.session_state:
    st.session_state.smart_rules = []

# ==========================================================
# DATA LOADER & AUTO-INTELLIGENCE (Cached for 1M+ Records)
# ==========================================================
@st.cache_data(show_spinner=False)
def load_and_clean_data(file):
    if file.name.endswith(".csv"):
        df = pd.read_csv(file, engine="python", encoding="utf-8")
    else:
        df = pd.read_excel(file)
    
    # Clean headers
    df.columns = [re.sub(r"\s+", " ", str(c).replace("\n", " ")).strip() for c in df.columns]
    
    # Auto-infer Circle from Site ID (As requested: B = Bihar, J = Jharkhand)
    site_col = next((c for c in df.columns if "site id" in c.lower() or "site_id" in c.lower()), None)
    if site_col and 'Auto_Circle' not in df.columns:
        df['Auto_Circle'] = df[site_col].astype(str).apply(
            lambda x: 'Bihar' if x.upper().startswith('B') else ('Jharkhand' if x.upper().startswith('J') else 'Other')
        )
    
    # Stringify objects for memory/speed
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
            
    return df

# ==========================================================
# VECTORIZED CONDITIONAL ENGINE
# ==========================================================
def evaluate_condition(series, op, val):
    if op == "==": return series.str.lower().str.strip() == str(val).lower().strip()
    if op == "!=": return series.str.lower().str.strip() != str(val).lower().strip()
    if op == "Contains": return series.str.lower().str.contains(str(val).lower().strip(), na=False)
    
    # Numeric
    num_series = pd.to_numeric(series, errors='coerce')
    val = float(val) if str(val).replace('.','',1).isdigit() else 0
    if op == ">": return num_series > val
    if op == "<": return num_series < val
    if op == ">=": return num_series >= val
    if op == "<=": return num_series <= val
    return pd.Series(False, index=series.index)

@st.cache_data(show_spinner=False)
def apply_smart_rules(_df, rules):
    df = _df.copy()
    fail_cols = []
    
    for r in rules:
        col_name = f"FAIL_{r['name']}"
        fail_cols.append(col_name)
        
        # 1. Evaluate Pre-condition (e.g., Is it a DG site?)
        if r['use_precond'] and r['pre_col']:
            pre_mask = evaluate_condition(df[r['pre_col']], r['pre_op'], r['pre_val'])
        else:
            pre_mask = pd.Series(True, index=df.index) # All rows applicable
            
        # 2. Evaluate Failure logic (e.g., Is Automation == No?)
        fail_mask = evaluate_condition(df[r['fail_col']], r['fail_op'], r['fail_val'])
        
        # 3. Apply logic: It is a failure ONLY IF precondition is met AND failure condition is met
        df[col_name] = pre_mask & fail_mask
        
    df["_FAIL_COUNT"] = df[fail_cols].sum(axis=1) if fail_cols else 0
    df["_IS_OK"] = df["_FAIL_COUNT"] == 0
    
    return df, fail_cols

# ==========================================================
# SIDEBAR: DATA UPLOAD & GEOGRAPHIC FILTERS
# ==========================================================
with st.sidebar:
    st.title("📡 AIR Command Center")
    uploaded_file = st.file_uploader("Upload Data", type=["xlsx", "xls", "csv"])
    
if not uploaded_file:
    st.info("👈 Upload your Site Data to begin.")
    st.stop()

with st.spinner("Processing Data..."):
    raw_df = load_and_clean_data(uploaded_file)

cols = raw_df.columns.tolist()

with st.sidebar:
    st.markdown("### 🔍 Filters")
    # Dynamically select which columns to use for filtering
    filter_1_col = st.selectbox("Filter Level 1", ["None"] + cols, index=cols.index("Auto_Circle") + 1 if "Auto_Circle" in cols else 0)
    filter_2_col = st.selectbox("Filter Level 2", ["None"] + cols, index=cols.index("District") + 1 if "District" in cols else 0)
    
    f1_val = f2_val = "All"
    if filter_1_col != "None":
        f1_val = st.selectbox(f"Select {filter_1_col}", ["All"] + sorted(raw_df[filter_1_col].unique().tolist()))
    if filter_2_col != "None":
        # Cascading filter logic
        temp_df = raw_df if f1_val == "All" else raw_df[raw_df[filter_1_col] == f1_val]
        f2_val = st.selectbox(f"Select {filter_2_col}", ["All"] + sorted(temp_df[filter_2_col].unique().tolist()))

# ==========================================================
# MAIN UI TABS
# ==========================================================
tab_dash, tab_rules, tab_data = st.tabs(["📊 Matrix Dashboard", "⚙️ Smart Rule Engine", "📋 Actionable Data"])

# ==========================================================
# TAB 2: SMART RULE ENGINE (Do this first to build logic)
# ==========================================================
with tab_rules:
    st.markdown("### 🧠 Build Conditional KPI Logic")
    st.info("Example: Check 'DG Automation' == 'No' ONLY IF 'DG/Non-DG' == 'DG'")
    
    with st.expander("➕ Add New Rule", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 1. Pre-Condition (Optional)")
            use_pre = st.checkbox("Apply only to specific sites?")
            pre_col = st.selectbox("If Column", cols, key="p_col") if use_pre else None
            pre_op = st.selectbox("Operator", ["==", "!=", "Contains"], key="p_op") if use_pre else None
            pre_val = st.text_input("Equals Value (e.g., 'DG')", key="p_val") if use_pre else None
            
        with col2:
            st.markdown("#### 2. Failure Condition")
            r_name = st.text_input("Rule Name (e.g., 'Automation Issue')")
            f_col = st.selectbox("Check KPI Column", cols, key="f_col")
            f_op = st.selectbox("Condition", ["==", "!=", "<", ">", "<=", ">=", "Contains"], key="f_op")
            f_val = st.text_input("Failure Value (e.g., 'No', 'Not OK', '4.0')", key="f_val")
            
        if st.button("Save Logic Rule", type="primary"):
            if r_name and f_val:
                st.session_state.smart_rules.append({
                    "name": r_name, "use_precond": use_pre, "pre_col": pre_col, "pre_op": pre_op, "pre_val": pre_val,
                    "fail_col": f_col, "fail_op": f_op, "fail_val": f_val
                })
                st.rerun()
                
    if st.session_state.smart_rules:
        st.markdown("#### Active Failure Rules")
        for i, r in enumerate(st.session_state.smart_rules):
            c1, c2 = st.columns([9, 1])
            cond_text = f"IF **{r['pre_col']} {r['pre_op']} {r['pre_val']}** THEN " if r['use_precond'] else ""
            c1.info(f"🚨 **{r['name']}**: {cond_text} FAIL IF **{r['fail_col']} {r['fail_op']} {r['fail_val']}**")
            if c2.button("❌", key=f"del_{i}"):
                st.session_state.smart_rules.pop(i)
                st.rerun()

# Apply Rules
processed_df, active_fails = apply_smart_rules(raw_df, st.session_state.smart_rules)

# Apply Geo-Filters
filtered_df = processed_df.copy()
if filter_1_col != "None" and f1_val != "All": filtered_df = filtered_df[filtered_df[filter_1_col] == f1_val]
if filter_2_col != "None" and f2_val != "All": filtered_df = filtered_df[filtered_df[filter_2_col] == f2_val]

# ==========================================================
# TAB 1: MATRIX DASHBOARD (Like the Excel Screenshot)
# ==========================================================
with tab_dash:
    # 1. Top Metrics
    total = len(filtered_df)
    ok_count = filtered_df["_IS_OK"].sum() if total > 0 else 0
    fail_count = total - ok_count
    
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"<div class='metric-card'><div class='metric-title'>Total Sites</div><div class='metric-value' style='color:#333'>{total:,}</div></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='metric-card'><div class='metric-title'>Sites OK (No Infra Issue)</div><div class='metric-value ok'>{ok_count:,}</div></div>", unsafe_allow_html=True)
    col3.markdown(f"<div class='metric-card'><div class='metric-title'>Sites with Deficiencies</div><div class='metric-value'>{fail_count:,}</div></div>", unsafe_allow_html=True)
    col4.markdown(f"<div class='metric-card'><div class='metric-title'>Overall Network Health</div><div class='metric-value ok'>{(ok_count/total*100) if total else 0:.1f}%</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 2. Excel-Style Matrix Builder
    st.markdown("### 📊 Macro B&J / Deficiency Matrix")
    st.caption("Customize the Grouping to replicate your Excel reports dynamically.")
    
    g_col1, g_col2 = st.columns(2)
    group_1 = g_col1.selectbox("Primary Grouping (e.g., DG/Non-DG)", cols, index=cols.index("DG/Non-DG ULS") if "DG/Non-DG ULS" in cols else 0)
    group_2 = g_col2.selectbox("Secondary Grouping (e.g., Principal Owner)", cols, index=cols.index("Site- Principal Owner") if "Site- Principal Owner" in cols else 0)

    if total > 0 and active_fails:
        # Create Pivot logic instantly using vectorization
        grouped = filtered_df.groupby([group_1, group_2])
        
        matrix = pd.DataFrame()
        matrix["Total Sites"] = grouped.size()
        matrix["Sites with no infra issue"] = grouped["_IS_OK"].sum()
        matrix["%age OK"] = (matrix["Sites with no infra issue"] / matrix["Total Sites"] * 100).round(1).astype(str) + "%"
        matrix["Sites having infra deficiency"] = matrix["Total Sites"] - matrix["Sites with no infra issue"]
        matrix["%age Deficient"] = (matrix["Sites having infra deficiency"] / matrix["Total Sites"] * 100).round(1).astype(str) + "%"
        
        # Add columns for every specific failure rule defined
        for rule in active_fails:
            rule_clean_name = rule.replace("FAIL_", "")
            matrix[rule_clean_name] = grouped[rule].sum()
            
        st.dataframe(matrix, use_container_width=True, height=500)
    elif not active_fails:
        st.warning("Go to the '⚙️ Smart Rule Engine' tab to define your KPIs and generate the Matrix.")
    else:
        st.info("No data available for the selected filters.")

# ==========================================================
# TAB 3: ACTIONABLE DATA (Speed Optimized)
# ==========================================================
with tab_data:
    st.markdown("### 📋 Downloadable Action Items")
    if active_fails and total > 0:
        view_opt = st.radio("Show:", ["Only Sites with Deficiencies", "All Sites"], horizontal=True)
        out_df = filtered_df[~filtered_df["_IS_OK"]] if view_opt == "Only Sites with Deficiencies" else filtered_df
        
        # Sort worst sites first
        out_df = out_df.sort_values(by="_FAIL_COUNT", ascending=False)
        
        # Keep clean columns for export
        clean_cols = [c for c in out_df.columns if not c.startswith("_") and not c.startswith("FAIL_")]
        
        col1, col2 = st.columns([8, 2])
        col1.caption(f"Showing top 1000 actionable records for speed. Download CSV for all {len(out_df):,} rows.")
        csv = out_df[clean_cols].to_csv(index=False).encode('utf-8')
        col2.download_button("📥 Download Report", data=csv, file_name="Actionable_Sites.csv", mime="text/csv")
        
        st.dataframe(out_df[clean_cols].head(1000), use_container_width=True)
    else:
        st.info("Define KPI rules to identify actionable sites.")
