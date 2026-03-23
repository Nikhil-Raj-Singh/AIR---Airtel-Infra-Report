# ==========================================================
# app.py — AIR V8: Enterprise Layout with Top-Bar Filters
# ==========================================================

import os, sys, subprocess
import re
import json
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
# CONFIG & 3D ANIMATED CSS
# ==========================================================
st.set_page_config(page_title="AIR Central BI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #e0e5ec; }
    
    /* 3D Floating Animation */
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-4px); }
        100% { transform: translateY(0px); }
    }
    
    /* Pulsating Alert Animation */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.65; }
        100% { opacity: 1; }
    }
    
    .card-3d {
        background: #e0e5ec;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 9px 9px 16px rgb(163,177,198,0.6), -9px -9px 16px rgba(255,255,255, 0.5);
        margin-bottom: 20px;
        text-align: center;
        transition: all 0.3s ease;
        animation: float 5s ease-in-out infinite;
    }
    
    .card-3d:hover { 
        transform: translateY(-8px) scale(1.02); 
        box-shadow: 15px 15px 25px rgb(163,177,198,0.7), -15px -15px 25px rgba(255,255,255, 0.6);
        animation: none;
    }
    
    .filter-bar {
        background: #e0e5ec;
        border-radius: 10px;
        padding: 15px 20px 5px 20px;
        box-shadow: inset 5px 5px 10px rgb(163,177,198,0.5), inset -5px -5px 10px rgba(255,255,255, 0.5);
        margin-bottom: 20px;
    }
    
    .card-title { color: #5c6b73; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;}
    .card-value { font-size: 2.2rem; font-weight: 800; color: #2b2d42; }
    .val-alert { color: #d90429; animation: pulse 2.5s infinite; }
    .val-success { color: #2a9d8f; }
    
    .stDataFrame { border-radius: 10px; box-shadow: 5px 5px 10px rgb(163,177,198,0.4); }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE
# ==========================================================
if 'dynamic_rules' not in st.session_state:
    st.session_state.dynamic_rules = []

# ==========================================================
# CORE DATA ENGINE (CACHED)
# ==========================================================
@st.cache_data(show_spinner="Ingesting Master Data...")
def load_data(file):
    df = pd.read_csv(file, engine="python") if file.name.endswith(".csv") else pd.read_excel(file)
    df.columns = [re.sub(r"\s+", " ", str(c).replace("\n", " ")).strip() for c in df.columns]
    
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str)
        
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
        
        if r['use_pre'] and r['pre_col'] in df.columns:
            pre_mask = evaluate_cond(df[r['pre_col']], r['pre_op'], r['pre_val'])
        else: pre_mask = pd.Series(True, index=df.index)
            
        fail_mask = evaluate_cond(df[r['fail_col']], r['fail_op'], r['fail_val'])
        
        if r['use_nested'] and r['nest_col'] in df.columns:
            nest_mask = evaluate_cond(df[r['nest_col']], r['nest_op'], r['nest_val'])
            fail_mask = fail_mask & nest_mask

        df[col_name] = pre_mask & fail_mask
        
        if r['use_severe'] and r['sev_col'] in df.columns:
            sev_mask = evaluate_cond(df[r['sev_col']], r['sev_op'], r['sev_val'])
            df[crit_col_name] = df[col_name] & sev_mask
            active_criticals.append(crit_col_name)
        else:
            df[crit_col_name] = False
            
    df["_TOTAL_FAILS"] = df[active_fails].sum(axis=1) if active_fails else 0
    df["_IS_OK"] = df["_TOTAL_FAILS"] == 0
    return df, active_fails, active_criticals

# ==========================================================
# LEFT SIDEBAR: NAVIGATION & SETUP (Moved to Top)
# ==========================================================
with st.sidebar:
    st.markdown("### 📡 Main Menu")
    
    # NAVIGATION AT THE VERY TOP
    pages = ["🏠 Home Summary", "⚙️ Logic Setup Studio"]
    critical_dashboards = [r['name'] for r in st.session_state.dynamic_rules if r.get('make_dash', False)]
    for d in critical_dashboards:
        pages.append(f"📊 {d} Deep Dive")
    selection = st.radio("Go to:", pages)
    
    st.markdown("---")
    st.markdown("### 📂 Data & Config")
    uploaded_file = st.file_uploader("1. Upload Master Dataset", type=["xlsx", "xls", "csv"])

    if st.session_state.dynamic_rules:
        with st.expander("💾 Config Management", expanded=False):
            config_json = json.dumps(st.session_state.dynamic_rules)
            st.download_button("Export Config", data=config_json, file_name="air_config.json", mime="application/json")
            
    uploaded_config = st.file_uploader("2. Import Config (Optional)", type=["json"])
    if uploaded_config is not None:
        st.session_state.dynamic_rules = json.load(uploaded_config)

if not uploaded_file:
    st.info("👈 Please upload your Site Data in the left sidebar to initialize the platform.")
    st.stop()

# ==========================================================
# MAIN PAGE: TOP-BAR GLOBAL FILTERS
# ==========================================================
raw_df = load_data(uploaded_file)
cols = raw_df.columns.tolist()

geo_col = "Auto_Circle" if "Auto_Circle" in cols else "None"
macro_col = "Macro/ULS" if "Macro/ULS" in cols else "None"
dist_col = "District" if "District" in cols else "None"
town_col = "Town" if "Town" in cols else "None"
cluster_col = "Cluster" if "Cluster" in cols else "None"
toco_col = "Site- Principal Owner" if "Site- Principal Owner" in cols else "None"

st.markdown("<div class='filter-bar'>", unsafe_allow_html=True)
st.markdown("**🌍 Global Drill-Downs**")
fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)

f_geo = fc1.selectbox("Circle", ["All"] + sorted(raw_df[geo_col].unique())) if geo_col != "None" else "All"
temp_df = raw_df if f_geo == "All" else raw_df[raw_df[geo_col] == f_geo]

f_toco = fc2.selectbox("Toco", ["All"] + sorted(temp_df[toco_col].unique())) if toco_col != "None" else "All"
if f_toco != "All": temp_df = temp_df[temp_df[toco_col] == f_toco]

f_macro = fc3.selectbox("Macro/ULS", ["All"] + sorted(temp_df[macro_col].unique())) if macro_col != "None" else "All"
if f_macro != "All": temp_df = temp_df[temp_df[macro_col] == f_macro]

f_dist = fc4.selectbox("District", ["All"] + sorted(temp_df[dist_col].unique())) if dist_col != "None" else "All"
if f_dist != "All": temp_df = temp_df[temp_df[dist_col] == f_dist]

f_town = fc5.selectbox("Town", ["All"] + sorted(temp_df[town_col].unique())) if town_col != "None" else "All"
if f_town != "All": temp_df = temp_df[temp_df[town_col] == f_town]

f_cluster = fc6.selectbox("Cluster", ["All"] + sorted(temp_df[cluster_col].unique())) if cluster_col != "None" else "All"
st.markdown("</div>", unsafe_allow_html=True)

# Process Data Post-Filtering
processed_df, fails, crits = apply_rules(raw_df, st.session_state.dynamic_rules)

final_df = processed_df.copy()
if f_geo != "All": final_df = final_df[final_df[geo_col] == f_geo]
if f_toco != "All": final_df = final_df[final_df[toco_col] == f_toco]
if f_macro != "All": final_df = final_df[final_df[macro_col] == f_macro]
if f_dist != "All": final_df = final_df[final_df[dist_col] == f_dist]
if f_town != "All": final_df = final_df[final_df[town_col] == f_town]
if f_cluster != "All": final_df = final_df[final_df[cluster_col] == f_cluster]

total_sites = len(final_df)

# ==========================================================
# PAGE ROUTING (Based on selection)
# ==========================================================
if selection == "⚙️ Logic Setup Studio":
    st.title("⚙️ Logic Setup Studio")
    
    with st.container():
        st.markdown("<div class='filter-bar'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            kpi_name = st.text_input("KPI Name (e.g., DG Automation)")
            use_pre = st.checkbox("1. Requires Pre-condition?")
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
            use_sev = st.checkbox("4. Define KPI-Specific Critical Level?")
            s_col = st.selectbox("Severity Column", cols) if use_sev else None
            s_op = st.selectbox("Severity Op", ["<", ">", "==", "<=", ">="]) if use_sev else None
            s_val = st.text_input("Severity Threshold") if use_sev else None
            
            st.markdown("---")
            make_dash = st.checkbox("🔥 Create Dedicated Dashboard?", value=True)

        if st.button("Save KPI Logic", type="primary"):
            st.session_state.dynamic_rules.append({
                "name": kpi_name, "use_pre": use_pre, "pre_col": p_col, "pre_op": p_op, "pre_val": p_val,
                "fail_col": f_col, "fail_op": f_op, "fail_val": f_val,
                "use_nested": use_nest, "nest_col": n_col, "nest_op": n_op, "nest_val": n_val,
                "use_severe": use_sev, "sev_col": s_col, "sev_op": s_op, "sev_val": s_val,
                "make_dash": make_dash
            })
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.dynamic_rules:
        st.subheader("Active KPI Intelligence")
        for i, rule in enumerate(st.session_state.dynamic_rules):
            st.markdown(f"**{rule['name']}**")
            if st.button(f"Delete {rule['name']}", key=f"del_{i}"):
                st.session_state.dynamic_rules.pop(i)
                st.rerun()
            st.markdown("---")

elif selection == "🏠 Home Summary":
    ok_count = final_df["_IS_OK"].sum() if total_sites > 0 else 0
    fail_count = total_sites - ok_count
    health_pct = (ok_count / total_sites * 100) if total_sites > 0 else 0
    severe_count = len(final_df[final_df["_TOTAL_FAILS"] >= 3])
    
    st.markdown(f"""
    <div style="display:flex; gap: 15px; flex-wrap: wrap;">
        <div class="card-3d" style="flex:1; min-width: 150px;"><div class="card-title">Total Sites</div><div class="card-value">{total_sites:,}</div></div>
        <div class="card-3d" style="flex:1; min-width: 150px;"><div class="card-title">Network Health</div><div class="card-value val-success">{health_pct:.1f}%</div></div>
        <div class="card-3d" style="flex:1; min-width: 150px;"><div class="card-title">Sites 100% OK</div><div class="card-value val-success">{ok_count:,}</div></div>
        <div class="card-3d" style="flex:1; min-width: 150px;"><div class="card-title">Deficient Sites</div><div class="card-value val-alert">{fail_count:,}</div></div>
        <div class="card-3d" style="flex:1; min-width: 150px;"><div class="card-title">Severely Degraded (≥3 Fails)</div><div class="card-value val-alert">{severe_count:,}</div></div>
    </div>
    """, unsafe_allow_html=True)

    if total_sites > 0 and fails:
        st.markdown("### Specific KPI Breakdowns")
        kpi_cols = st.columns(4)
        for i, fail_col in enumerate(fails):
            rule_name = fail_col.replace("FAIL_", "")
            fail_cnt = final_df[fail_col].sum() if fail_col in final_df.columns else 0
            kpi_cols[i % 4].markdown(f"<div class='card-3d'><div class='card-title'>{rule_name}</div><div class='card-value val-alert' style='font-size: 1.8rem;'>{fail_cnt:,}</div></div>", unsafe_allow_html=True)
            
        st.markdown("---")
        c1, c2 = st.columns([7, 3])
        with c1: st.subheader("Deep Visual Insights")
        with c2: top_n_str = st.selectbox("Show Top:", ["5", "10", "15", "25", "All"], index=2, key="home_top")
        
        view_toggle = st.radio("Select Analysis Dimension:", ["Cluster-wise Insights", "Toco-wise Insights"], horizontal=True)
        
        melted_df = final_df.melt(id_vars=[cluster_col, toco_col], value_vars=fails, var_name="Failure Type", value_name="Failed")
        melted_df = melted_df[melted_df["Failed"] == True]
        melted_df["Failure Type"] = melted_df["Failure Type"].str.replace("FAIL_", "")
        
        view_col = cluster_col if view_toggle == "Cluster-wise Insights" else toco_col
        
        if view_col != "None" and not melted_df.empty:
            grouped = melted_df.groupby(view_col).size().reset_index(name='Total_Errors')
            grouped = grouped.sort_values('Total_Errors', ascending=False)
            
            if top_n_str != "All":
                top_entities = grouped.head(int(top_n_str))[view_col]
                melted_df = melted_df[melted_df[view_col].isin(top_entities)]

            chart = alt.Chart(melted_df).mark_bar().encode(
                x=alt.X(f'{view_col}:N', title=view_col, sort=alt.EncodingSortField(field='count()', order='descending')),
                y=alt.Y('count():Q', title="Total Failures"),
                color=alt.Color('Failure Type:N', scale=alt.Scale(scheme='category20b')),
                tooltip=[view_col, 'Failure Type', 'count()']
            ).properties(height=450, title=f"Failure Distribution by {view_col} (Top {top_n_str})")
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Head to the Logic Setup Studio to define KPIs.")

else:
    kpi_name = selection.replace("📊 ", "").replace(" Deep Dive", "")
    st.title(f"🔍 {kpi_name} Analysis")
    
    fail_col = f"FAIL_{kpi_name}"
    crit_col = f"CRIT_{kpi_name}"
    
    kpi_df = final_df[final_df[fail_col] == True]
    total_kpi_fails = len(kpi_df)
    kpi_severe_count = len(kpi_df[kpi_df["_TOTAL_FAILS"] >= 3])
    kpi_specific_crit = kpi_df[crit_col].sum() if crit_col in kpi_df.columns else 0
    
    st.markdown(f"""
    <div style="display:flex; gap: 20px;">
        <div class="card-3d" style="flex:1;"><div class="card-title">Failed Sites</div><div class="card-value">{total_kpi_fails:,}</div></div>
        <div class="card-3d" style="flex:1;"><div class="card-title">KPI Critical Rules Met</div><div class="card-value val-alert">{kpi_specific_crit:,}</div></div>
        <div class="card-3d" style="flex:1;"><div class="card-title">Severely Degraded (≥3 Total Fails)</div><div class="card-value val-alert">{kpi_severe_count:,}</div></div>
    </div>
    """, unsafe_allow_html=True)
    
    if total_kpi_fails > 0:
        c1, c2, c3 = st.columns([4, 4, 2])
        with c3: top_x = st.selectbox("Show Top:", ["5", "10", "15", "25", "All"], index=1, key=f"top_{kpi_name}")
        limit = int(top_x) if top_x != "All" else None

        if dist_col != "None":
            dist_df = kpi_df.groupby(dist_col).size().reset_index(name='Count').sort_values('Count', ascending=False)
            if limit: dist_df = dist_df.head(limit)
            ch1 = alt.Chart(dist_df).mark_bar(color='#219ebc').encode(
                x=alt.X(f'{dist_col}:N', sort='-y', title="District"),
                y=alt.Y('Count:Q'), tooltip=[dist_col, 'Count']
            ).properties(title=f"Top {top_x} Districts", height=350)
            c1.altair_chart(ch1, use_container_width=True)
            
        if cluster_col != "None":
            clus_df = kpi_df.groupby(cluster_col).size().reset_index(name='Count').sort_values('Count', ascending=False)
            if limit: clus_df = clus_df.head(limit)
            ch2 = alt.Chart(clus_df).mark_bar(color='#fb8500').encode(
                x=alt.X(f'{cluster_col}:N', sort='-y', title="Cluster"),
                y=alt.Y('Count:Q'), tooltip=[cluster_col, 'Count']
            ).properties(title=f"Top {top_x} Clusters", height=350)
            c2.altair_chart(ch2, use_container_width=True)

        st.subheader(f"Actionable Data: {kpi_name}")
        clean_cols = [c for c in kpi_df.columns if not c.startswith("FAIL_") and not c.startswith("CRIT_") and not c.startswith("_")]
        
        col_btn, _ = st.columns([2, 8])
        csv_export = kpi_df[clean_cols].to_csv(index=False).encode('utf-8')
        col_btn.download_button(f"📥 Download Actions", data=csv_export, file_name=f"{kpi_name}_actionable.csv")
        
        st.dataframe(kpi_df[clean_cols].head(1000), use_container_width=True)
