# ==========================================================
# app.py — AIR V5: Ultimate Smart BI & KPI Deep Dive Engine
# ==========================================================

import os, sys, subprocess
import re
import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

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
# CONFIG & 3D NEUMORPHIC CSS
# ==========================================================
st.set_page_config(page_title="AIR Central BI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* 3D / Neumorphic Styling for a Futuristic Look */
    .stApp { background-color: #e0e5ec; }
    
    .card-3d {
        background: #e0e5ec;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 9px 9px 16px rgb(163,177,198,0.6), -9px -9px 16px rgba(255,255,255, 0.5);
        margin-bottom: 20px;
        text-align: center;
        transition: transform 0.2s;
    }
    .card-3d:hover { transform: translateY(-3px); }
    
    .card-title { color: #5c6b73; font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;}
    .card-value { font-size: 2.5rem; font-weight: 800; color: #2b2d42; }
    .val-alert { color: #d90429; text-shadow: 2px 2px 4px rgba(217,4,41,0.2); }
    .val-success { color: #2a9d8f; text-shadow: 2px 2px 4px rgba(42,157,143,0.2); }
    
    /* Clean Matrix Table */
    .stDataFrame { border-radius: 10px; box-shadow: 5px 5px 10px rgb(163,177,198,0.4); }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE: THE RULE ENGINE
# ==========================================================
# We store rules dynamically so the user can build them
if 'dynamic_rules' not in st.session_state:
    st.session_state.dynamic_rules = []

# ==========================================================
# CORE DATA ENGINE (CACHED)
# ==========================================================
@st.cache_data(show_spinner="Ingesting Master Data...")
def load_data(file):
    df = pd.read_csv(file, engine="python") if file.name.endswith(".csv") else pd.read_excel(file)
    df.columns = [re.sub(r"\s+", " ", str(c).replace("\n", " ")).strip() for c in df.columns]
    
    # Fast string conversion
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str)
        
    # Auto-infer Circle if missing
    site_col = next((c for c in df.columns if "site id" in c.lower()), None)
    if site_col and 'Auto_Circle' not in df.columns:
        df['Auto_Circle'] = np.where(df[site_col].str.upper().str.startswith('B'), 'Bihar',
                            np.where(df[site_col].str.upper().str.startswith('J'), 'Jharkhand', 'Other'))
    return df

def evaluate_cond(series, op, val):
    s_lower = series.str.lower().str.strip()
    v_lower = str(val).lower().strip()
    if op == "==": return s_lower == v_lower
    if op == "!=": return s_lower != v_lower
    if op == "Contains": return s_lower.str.contains(v_lower, na=False)
    
    num_s = pd.to_numeric(series, errors='coerce')
    v_num = float(val) if str(val).replace('.','',1).isdigit() else 0
    if op == ">": return num_s > v_num
    if op == "<": return num_s < v_num
    if op == ">=": return num_s >= v_num
    if op == "<=": return num_s <= v_num
    return pd.Series(False, index=series.index)

@st.cache_data(show_spinner="Evaluating Logic Matrix...")
def apply_rules(_df, rules):
    df = _df.copy()
    active_fails = []
    active_criticals = []
    
    for r in rules:
        col_name = f"FAIL_{r['name']}"
        crit_col_name = f"CRIT_{r['name']}"
        active_fails.append(col_name)
        
        if r['fail_col'] not in df.columns: continue
        
        # Pre-condition
        if r['use_pre'] and r['pre_col'] in df.columns:
            pre_mask = evaluate_cond(df[r['pre_col']], r['pre_op'], r['pre_val'])
        else: pre_mask = pd.Series(True, index=df.index)
            
        # Base Failure
        fail_mask = evaluate_cond(df[r['fail_col']], r['fail_op'], r['fail_val'])
        
        # Nested AND condition (Optional)
        if r['use_nested'] and r['nest_col'] in df.columns:
            nest_mask = evaluate_cond(df[r['nest_col']], r['nest_op'], r['nest_val'])
            fail_mask = fail_mask & nest_mask

        # Apply standard failure
        df[col_name] = pre_mask & fail_mask
        
        # Check Critical Severity
        if r['use_severe'] and r['sev_col'] in df.columns:
            sev_mask = evaluate_cond(df[r['sev_col']], r['sev_op'], r['sev_val'])
            df[crit_col_name] = df[col_name] & sev_mask
            active_criticals.append(crit_col_name)
        else:
            df[crit_col_name] = False # No critical rules defined for this KPI
            
    df["_TOTAL_FAILS"] = df[active_fails].sum(axis=1) if active_fails else 0
    df["_IS_OK"] = df["_TOTAL_FAILS"] == 0
    return df, active_fails, active_criticals

# ==========================================================
# SIDEBAR: DATA LOAD & GLOBAL FILTERS
# ==========================================================
with st.sidebar:
    st.markdown("### 📡 Central BI Command")
    uploaded_file = st.file_uploader("Upload Master Dataset", type=["xlsx", "xls", "csv"])

if not uploaded_file:
    st.info("👈 Upload your Site Data to begin building your intelligence platform.")
    st.stop()

raw_df = load_data(uploaded_file)
cols = raw_df.columns.tolist()

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🌍 Global Drill-Downs")
    
    # Global Filters Builder
    geo_col = "Auto_Circle" if "Auto_Circle" in cols else "None"
    macro_col = "Macro/ULS" if "Macro/ULS" in cols else "None"
    dist_col = "District" if "District" in cols else "None"
    town_col = "Town" if "Town" in cols else "None"
    cluster_col = "Cluster" if "Cluster" in cols else "None"
    
    f_geo = st.selectbox("Circle", ["All"] + sorted(raw_df[geo_col].unique())) if geo_col != "None" else "All"
    
    # Filter chaining for dynamic dropdowns
    temp_df = raw_df if f_geo == "All" else raw_df[raw_df[geo_col] == f_geo]
    
    f_macro = st.selectbox("Macro/ULS", ["All"] + sorted(temp_df[macro_col].unique())) if macro_col != "None" else "All"
    if f_macro != "All": temp_df = temp_df[temp_df[macro_col] == f_macro]
    
    f_dist = st.selectbox("District", ["All"] + sorted(temp_df[dist_col].unique())) if dist_col != "None" else "All"
    if f_dist != "All": temp_df = temp_df[temp_df[dist_col] == f_dist]
    
    f_town = st.selectbox("Town", ["All"] + sorted(temp_df[town_col].unique())) if town_col != "None" else "All"
    if f_town != "All": temp_df = temp_df[temp_df[town_col] == f_town]
    
    f_cluster = st.selectbox("Cluster", ["All"] + sorted(temp_df[cluster_col].unique())) if cluster_col != "None" else "All"

# Process Rules on FULL data, then apply global filters for speed
processed_df, fails, crits = apply_rules(raw_df, st.session_state.dynamic_rules)

# Apply Filters
final_df = processed_df.copy()
if f_geo != "All": final_df = final_df[final_df[geo_col] == f_geo]
if f_macro != "All": final_df = final_df[final_df[macro_col] == f_macro]
if f_dist != "All": final_df = final_df[final_df[dist_col] == f_dist]
if f_town != "All": final_df = final_df[final_df[town_col] == f_town]
if f_cluster != "All": final_df = final_df[final_df[cluster_col] == f_cluster]

total_sites = len(final_df)

# ==========================================================
# ROUTING & NAVIGATION
# ==========================================================
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🧭 Navigation")
    
    # Dynamic Pages
    pages = ["🏠 Home Summary", "⚙️ Logic Setup Studio"]
    
    # Add a page for every KPI marked as "Critical Dashboard"
    critical_dashboards = [r['name'] for r in st.session_state.dynamic_rules if r.get('make_dash', False)]
    for d in critical_dashboards:
        pages.append(f"📊 {d} Deep Dive")
        
    selection = st.radio("Go to:", pages)

# ==========================================================
# PAGE 1: LOGIC SETUP STUDIO (The Engine Room)
# ==========================================================
if selection == "⚙️ Logic Setup Studio":
    st.title("⚙️ Logic Setup Studio")
    st.markdown("Define exactly how KPIs are calculated, apply nested rules, and generate dedicated deep-dive dashboards.")
    
    with st.expander("➕ Create New KPI Rule", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            kpi_name = st.text_input("KPI Name (e.g., DG Automation)")
            use_pre = st.checkbox("1. Requires Pre-condition? (e.g., Only DG sites)")
            p_col = st.selectbox("Pre-Condition Column", cols) if use_pre else None
            p_op = st.selectbox("Operator", ["==", "!=", "Contains"]) if use_pre else None
            p_val = st.text_input("Value") if use_pre else None
            
            st.markdown("---")
            st.markdown("**2. Primary Failure Condition**")
            f_col = st.selectbox("Failure Column", cols)
            f_op = st.selectbox("Fail Operator", ["==", "!=", "<", ">", "<=", ">=", "Contains"])
            f_val = st.text_input("Fail Value")

        with col2:
            use_nest = st.checkbox("3. Add Nested Condition? (AND logic)")
            n_col = st.selectbox("Nested Column", cols) if use_nest else None
            n_op = st.selectbox("Nested Op", ["==", "!=", "<", ">", "<=", ">="]) if use_nest else None
            n_val = st.text_input("Nested Value") if use_nest else None
            
            st.markdown("---")
            use_sev = st.checkbox("4. Define 'Critical' Severity Level?")
            st.caption("Identify highly degraded sites within this failure.")
            s_col = st.selectbox("Severity Column", cols) if use_sev else None
            s_op = st.selectbox("Severity Op", ["<", ">", "==", "<=", ">="]) if use_sev else None
            s_val = st.text_input("Severity Threshold (e.g., Backup < 2)") if use_sev else None
            
            st.markdown("---")
            make_dash = st.checkbox("🔥 Create Dedicated Dashboard for this KPI?", value=True)

        if st.button("Save KPI Logic", type="primary"):
            st.session_state.dynamic_rules.append({
                "name": kpi_name, "use_pre": use_pre, "pre_col": p_col, "pre_op": p_op, "pre_val": p_val,
                "fail_col": f_col, "fail_op": f_op, "fail_val": f_val,
                "use_nested": use_nest, "nest_col": n_col, "nest_op": n_op, "nest_val": n_val,
                "use_severe": use_sev, "sev_col": s_col, "sev_op": s_op, "sev_val": s_val,
                "make_dash": make_dash
            })
            st.rerun()

    if st.session_state.dynamic_rules:
        st.subheader("Active KPI Intelligence")
        for i, rule in enumerate(st.session_state.dynamic_rules):
            with st.container():
                st.markdown(f"**{rule['name']}** {'(Has Dedicated Dash)' if rule['make_dash'] else ''}")
                st.caption(f"FAIL IF: `{rule['fail_col']} {rule['fail_op']} {rule['fail_val']}`")
                if st.button(f"Delete {rule['name']}", key=f"del_{i}"):
                    st.session_state.dynamic_rules.pop(i)
                    st.rerun()
                st.markdown("---")

# ==========================================================
# PAGE 2: HOME SUMMARY
# ==========================================================
elif selection == "🏠 Home Summary":
    st.title("Global Network Summary")
    
    ok_count = final_df["_IS_OK"].sum() if total_sites > 0 else 0
    fail_count = total_sites - ok_count
    
    # 3D Metric Cards
    st.markdown(f"""
    <div style="display:flex; gap: 20px;">
        <div class="card-3d" style="flex:1;">
            <div class="card-title">Total Filtered Sites</div>
            <div class="card-value">{total_sites:,}</div>
        </div>
        <div class="card-3d" style="flex:1;">
            <div class="card-title">Sites 100% OK</div>
            <div class="card-value val-success">{ok_count:,}</div>
        </div>
        <div class="card-3d" style="flex:1;">
            <div class="card-title">Deficient Sites</div>
            <div class="card-value val-alert">{fail_count:,}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if total_sites > 0 and fails:
        col1, col2 = st.columns([6, 4])
        
        with col1:
            st.subheader("Matrix View")
            # Build matrix like Excel
            h_cols = [c for c in ["Macro/ULS", "DG/ Non-DG", "Site- Principal Owner"] if c in final_df.columns]
            if not h_cols: h_cols = [final_df.columns[0]]
            
            matrix = final_df.groupby(h_cols).agg(Total=('_IS_OK', 'count'), OK=('_IS_OK', 'sum'))
            matrix['Deficient'] = matrix['Total'] - matrix['OK']
            for f in fails: matrix[f.replace("FAIL_", "")] = final_df.groupby(h_cols)[f].sum()
            st.dataframe(matrix, use_container_width=True, height=400)
            
        with col2:
            st.subheader("Deficiency Breakdown")
            fail_sums = final_df[fails].sum().reset_index()
            fail_sums.columns = ["Type", "Count"]
            fail_sums["Type"] = fail_sums["Type"].str.replace("FAIL_", "")
            
            # 3D-styled Altair Chart
            chart = alt.Chart(fail_sums).mark_bar(cornerRadiusEnd=4, color=alt.Gradient(
                gradient='linear', stops=[alt.GradientStop(color='#ff4b4b', offset=0), alt.GradientStop(color='#8b0000', offset=1)]
            )).encode(
                x=alt.X('Count:Q', title=""),
                y=alt.Y('Type:N', sort='-x', title=""),
                tooltip=['Type', 'Count']
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Head to the Logic Setup Studio to define KPIs.")

# ==========================================================
# PAGE 3: DYNAMIC KPI DEEP DIVES
# ==========================================================
else:
    kpi_name = selection.replace("📊 ", "").replace(" Deep Dive", "")
    st.title(f"🔍 {kpi_name} Analysis")
    
    fail_col = f"FAIL_{kpi_name}"
    crit_col = f"CRIT_{kpi_name}"
    
    kpi_df = final_df[final_df[fail_col] == True]
    total_kpi_fails = len(kpi_df)
    critical_fails = kpi_df[crit_col].sum() if crit_col in kpi_df.columns else 0
    normal_fails = total_kpi_fails - critical_fails
    
    st.markdown(f"""
    <div style="display:flex; gap: 20px;">
        <div class="card-3d" style="flex:1;"><div class="card-title">Total Failed Sites</div><div class="card-value">{total_kpi_fails:,}</div></div>
        <div class="card-3d" style="flex:1;"><div class="card-title">Critical Severity</div><div class="card-value val-alert">{critical_fails:,}</div></div>
        <div class="card-3d" style="flex:1;"><div class="card-title">Normal Severity</div><div class="card-value">{normal_fails:,}</div></div>
    </div>
    """, unsafe_allow_html=True)
    
    if total_kpi_fails > 0:
        c1, c2 = st.columns(2)
        
        # Breakdown by District
        if dist_col != "None":
            dist_df = kpi_df.groupby(dist_col).size().reset_index(name='Count').sort_values('Count', ascending=False).head(15)
            ch1 = alt.Chart(dist_df).mark_bar(color='#219ebc', cornerRadiusTop=4).encode(
                x=alt.X(f'{dist_col}:N', sort='-y', title="District"),
                y=alt.Y('Count:Q'), tooltip=[dist_col, 'Count']
            ).properties(title="Top 15 Districts (Fail Count)", height=350)
            c1.altair_chart(ch1, use_container_width=True)
            
        # Breakdown by Cluster
        if cluster_col != "None":
            clus_df = kpi_df.groupby(cluster_col).size().reset_index(name='Count').sort_values('Count', ascending=False).head(15)
            ch2 = alt.Chart(clus_df).mark_bar(color='#fb8500', cornerRadiusTop=4).encode(
                x=alt.X(f'{cluster_col}:N', sort='-y', title="Cluster"),
                y=alt.Y('Count:Q'), tooltip=[cluster_col, 'Count']
            ).properties(title="Top 15 Clusters (Fail Count)", height=350)
            c2.altair_chart(ch2, use_container_width=True)

        st.subheader(f"Actionable Data: {kpi_name}")
        
        # Let user download only the failed sites for THIS specific KPI
        clean_cols = [c for c in kpi_df.columns if not c.startswith("FAIL_") and not c.startswith("CRIT_") and not c.startswith("_")]
        
        col_btn, _ = st.columns([2, 8])
        csv_export = kpi_df[clean_cols].to_csv(index=False).encode('utf-8')
        col_btn.download_button(f"📥 Download {kpi_name} Actions", data=csv_export, file_name=f"{kpi_name}_actionable.csv")
        
        st.dataframe(kpi_df[clean_cols].head(1000), use_container_width=True)
    else:
        st.success(f"No {kpi_name} failures detected in the current filter scope!")
