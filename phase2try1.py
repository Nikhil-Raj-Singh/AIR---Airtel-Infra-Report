# ==========================================================
# app.py — AIR V12: Airtel Corporate Edition (Phase 2 Final)
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
# CONFIG & AIRTEL CORPORATE GLASSMORPHISM CSS
# ==========================================================
st.set_page_config(page_title="AIR Central BI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* Clean corporate light gray background */
    .stApp { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    @keyframes pulse-red {
        0% { opacity: 1; }
        50% { opacity: 0.7; text-shadow: 0 0 10px rgba(228,0,43,0.5); }
        100% { opacity: 1; }
    }
    
    /* Static Cards for Top Row Summaries */
    .card-static {
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(228,0,43,0.2);
        border-top: 5px solid #E4002B; /* Airtel Red */
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        margin-bottom: 15px;
        text-align: center;
        height: 100%;
    }
    
    .card-title { color: #555; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;}
    .card-value { font-size: 2.4rem; font-weight: 800; color: #2b2d42; margin-bottom: 5px;}
    .val-alert { color: #E4002B; animation: pulse-red 2.5s infinite; }
    .val-success { color: #00A300; }
    .val-pending { color: #FFB703; } /* Vibrant Yellow */
    
    .stDataFrame { border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    
    /* ---------------------------------------------------
       UNIFORM KPI BUTTONS (Glassy & 3D)
       --------------------------------------------------- */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(228,0,43,0.2);
        border-top: 5px solid #E4002B;
        border-radius: 12px;
        color: #E4002B;
        font-weight: 700;
        font-size: 1.1rem;
        padding: 20px 10px;
        box-shadow: 0 8px 25px 0 rgba(228,0,43,0.1);
        transition: all 0.2s ease-in-out;
        height: 100%;
        width: 100%;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background: #E4002B;
        color: #ffffff;
        border-color: #E4002B;
        transform: translateY(-4px);
        box-shadow: 0 12px 30px 0 rgba(228,0,43,0.3);
    }
    div[data-testid="stButton"] button[kind="secondary"] p {
        font-size: 1.25rem;
        margin: 0;
    }
    
    /* Primary buttons (Home, Download) */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #E4002B;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #cc0026;
    }
    
    /* Popover filter button styling */
    div[data-testid="stPopover"] button {
        background-color: #005A9C; /* Airtel Blue accent */
        color: white;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE & ROUTING ENGINE
# ==========================================================
if 'dynamic_rules' not in st.session_state:
    st.session_state.dynamic_rules = []

if 'nav_selection' not in st.session_state:
    st.session_state.nav_selection = "🏠 Home Summary"

def navigate_to(page_name):
    st.session_state.nav_selection = page_name

def stay_here():
    pass # Dummy function for non-dashboard buttons

def set_data_view(kpi_name, view_type):
    st.session_state[f'view_{kpi_name}'] = view_type

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
# LEFT SIDEBAR: NAVIGATION & SETUP
# ==========================================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Bharti_Airtel_Logo.svg/512px-Bharti_Airtel_Logo.svg.png", width=140)
    st.markdown("<br>", unsafe_allow_html=True)
    
    pages = ["🏠 Home Summary", "⚙️ Logic Setup Studio"]
    critical_dashboards = [r['name'] for r in st.session_state.dynamic_rules if r.get('make_dash', False)]
    for d in critical_dashboards:
        pages.append(f"📊 {d} Deep Dive")
        
    st.radio("Main Menu", pages, key="nav_selection", label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown("### 📂 Data & Config")
    uploaded_file = st.file_uploader("1. Upload Master Dataset", type=["xlsx", "xls", "csv"])

    if st.session_state.dynamic_rules:
        with st.expander("💾 Config Management", expanded=False):
            config_json = json.dumps(st.session_state.dynamic_rules)
            st.download_button("Export Config", data=config_json, file_name="air_config.json", mime="application/json", type="primary")
            
    uploaded_config = st.file_uploader("2. Import Config (Optional)", type=["json"])
    if uploaded_config is not None:
        st.session_state.dynamic_rules = json.load(uploaded_config)

if not uploaded_file:
    st.info("👈 Please upload your Site Data in the left sidebar to initialize the platform.")
    st.stop()

# ==========================================================
# MAIN PAGE: TOP HEADER & FLOATING FILTER
# ==========================================================
raw_df = load_data(uploaded_file)
cols = raw_df.columns.tolist()

geo_col = "Auto_Circle" if "Auto_Circle" in cols else "None"
macro_col = "Macro/ULS" if "Macro/ULS" in cols else "None"
dist_col = "District" if "District" in cols else "None"
town_col = "Town" if "Town" in cols else "None"
cluster_col = "Cluster" if "Cluster" in cols else "None"
toco_col = "Site- Principal Owner" if "Site- Principal Owner" in cols else "None"

# Top alignment for filters
col_empty, col_filter = st.columns([7, 3])
with col_filter:
    with st.popover("🔍 Global Drill-Down Filters", use_container_width=True):
        st.markdown("**Select parameters to filter the dashboard:**")
        f_geo = st.selectbox("Circle", ["All"] + sorted(raw_df[geo_col].unique())) if geo_col != "None" else "All"
        temp_df = raw_df if f_geo == "All" else raw_df[raw_df[geo_col] == f_geo]
        
        f_toco = st.selectbox("Toco", ["All"] + sorted(temp_df[toco_col].unique())) if toco_col != "None" else "All"
        if f_toco != "All": temp_df = temp_df[temp_df[toco_col] == f_toco]
        
        f_macro = st.selectbox("Macro/ULS", ["All"] + sorted(temp_df[macro_col].unique())) if macro_col != "None" else "All"
        if f_macro != "All": temp_df = temp_df[temp_df[macro_col] == f_macro]
        
        f_dist = st.selectbox("District", ["All"] + sorted(temp_df[dist_col].unique())) if dist_col != "None" else "All"
        if f_dist != "All": temp_df = temp_df[temp_df[dist_col] == f_dist]
        
        f_town = st.selectbox("Town", ["All"] + sorted(temp_df[town_col].unique())) if town_col != "None" else "All"
        if f_town != "All": temp_df = temp_df[temp_df[town_col] == f_town]
        
        f_cluster = st.selectbox("Cluster", ["All"] + sorted(temp_df[cluster_col].unique())) if cluster_col != "None" else "All"

# Apply Filters
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
# PAGE ROUTING
# ==========================================================
if st.session_state.nav_selection == "⚙️ Logic Setup Studio":
    st.title("⚙️ Logic Setup Studio")
    with st.container():
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
            use_sev = st.checkbox("4. Define KPI-Specific Critical Level (Feeders)?")
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

    if st.session_state.dynamic_rules:
        st.subheader("Active KPI Intelligence")
        for i, rule in enumerate(st.session_state.dynamic_rules):
            st.markdown(f"**{rule['name']}**")
            if st.button(f"Delete {rule['name']}", key=f"del_{i}", type="primary"):
                st.session_state.dynamic_rules.pop(i)
                st.rerun()
            st.markdown("---")

elif st.session_state.nav_selection == "🏠 Home Summary":
    ok_count = final_df["_IS_OK"].sum() if total_sites > 0 else 0
    fail_count = total_sites - ok_count
    health_pct = (ok_count / total_sites * 100) if total_sites > 0 else 0
    severe_count = len(final_df[final_df["_TOTAL_FAILS"] >= 3])
    
    # ROW 1: TOP TIER METRICS
    st.markdown(f"""
    <div style="display:flex; gap: 15px; margin-bottom: 15px;">
        <div class="card-static" style="flex:1;"><div class="card-title">Total Sites</div><div class="card-value">{total_sites:,}</div></div>
        <div class="card-static" style="flex:1;"><div class="card-title">Network Health</div><div class="card-value val-success">{health_pct:.1f}%</div></div>
        <div class="card-static" style="flex:1;"><div class="card-title">Sites 100% OK</div><div class="card-value val-success">{ok_count:,}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ROW 2: DEGRADED & FEEDERS
    st.markdown(f"""
    <div style="display:flex; gap: 15px; margin-bottom: 30px;">
        <div class="card-static" style="flex:1;"><div class="card-title">Deficient Sites</div><div class="card-value val-alert">{fail_count:,}</div></div>
        <div class="card-static" style="flex:1;"><div class="card-title">Severely Degraded (≥3 Fails)</div><div class="card-value val-alert">{severe_count:,}</div></div>
        <div class="card-static" style="flex:1;"><div class="card-title">Feeder Analysis</div><div class="card-value val-pending">Pending Module</div></div>
    </div>
    """, unsafe_allow_html=True)

    if total_sites > 0 and fails:
        st.markdown("<h3 style='color: #2b2d42; margin-bottom: 15px;'>Different Fail Types</h3>", unsafe_allow_html=True)
        kpi_cols = st.columns(4)
        for i, fail_col in enumerate(fails):
            rule_name = fail_col.replace("FAIL_", "")
            fail_cnt = final_df[fail_col].sum() if fail_col in final_df.columns else 0
            
            with kpi_cols[i % 4]:
                has_dash = any(r['name'] == rule_name and r.get('make_dash') for r in st.session_state.dynamic_rules)
                if has_dash:
                    # Navigate on click
                    st.button(f"{rule_name}\n\n🚨 {fail_cnt:,}", key=f"nav_{rule_name}", on_click=navigate_to, args=(f"📊 {rule_name} Deep Dive",), use_container_width=True, type="secondary")
                else:
                    # Uniform button, does nothing on click
                    st.button(f"{rule_name}\n\n🚨 {fail_cnt:,}", key=f"stat_{rule_name}", on_click=stay_here, use_container_width=True, type="secondary")
        
        # RESTORED HOME GRAPHS
        st.markdown("---")
        c1, c2 = st.columns([7, 3])
        with c1: st.subheader("Fail Distribution Overview")
        with c2: top_n_str = st.selectbox("Show Top:", ["5", "10", "15", "25", "All"], index=1, key="home_top")
        
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

            # Airtel Colors: Red, Yellow, Blue shades
            chart = alt.Chart(melted_df).mark_bar().encode(
                x=alt.X(f'{view_col}:N', title=view_col, sort=alt.EncodingSortField(field='count()', order='descending')),
                y=alt.Y('count():Q', title="Total Failures"),
                color=alt.Color('Failure Type:N', scale=alt.Scale(range=['#E4002B', '#FFB703', '#005A9C', '#FF5C5C', '#1E90FF'])),
                tooltip=[view_col, 'Failure Type', 'count()']
            ).properties(height=400).configure_view(strokeWidth=0)
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Head to the Logic Setup Studio to define KPIs.")

else:
    # ---------------------------------------------------------
    # DEDICATED KPI DEEP DIVE VIEW
    # ---------------------------------------------------------
    kpi_name = st.session_state.nav_selection.replace("📊 ", "").replace(" Deep Dive", "")
    
    col_title, col_back = st.columns([9, 1])
    with col_title: 
        st.markdown(f"<h1 style='color: #2b2d42;'>🔍 {kpi_name} Analysis</h1>", unsafe_allow_html=True)
    with col_back: 
        st.write("") 
        st.button("🏠 Home", on_click=navigate_to, args=("🏠 Home Summary",), type="primary", use_container_width=True)
    
    fail_col = f"FAIL_{kpi_name}"
    crit_col = f"CRIT_{kpi_name}"
    
    kpi_df = final_df[final_df[fail_col] == True]
    total_kpi_fails = len(kpi_df)
    kpi_severe_df = kpi_df[kpi_df["_TOTAL_FAILS"] >= 3]
    kpi_severe_count = len(kpi_severe_df)
    kpi_specific_crit = kpi_df[crit_col].sum() if crit_col in kpi_df.columns else 0
    
    if f'view_{kpi_name}' not in st.session_state:
        st.session_state[f'view_{kpi_name}'] = 'all'
    
    c1, c2, c3 = st.columns(3)
    with c1: 
        st.button(f"FAILED SITES\n\n🚨 {total_kpi_fails:,}", on_click=set_data_view, args=(kpi_name, 'all'), use_container_width=True, type="secondary")
    with c2: 
        st.markdown(f"<div class='card-static'><div class='card-title'>Feeders Impacted</div><div class='card-value val-alert'>{kpi_specific_crit:,}</div></div>", unsafe_allow_html=True)
    with c3: 
        st.button(f"SEVERELY DEGRADED\n\n🔥 {kpi_severe_count:,}", on_click=set_data_view, args=(kpi_name, 'severe'), use_container_width=True, type="secondary")
    
    if total_kpi_fails > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Determine if we should show charts (Hide if only 1 selection)
        show_town_chart = town_col != "None" and f_town == "All"
        show_cluster_chart = cluster_col != "None" and f_cluster == "All"
        
        if show_town_chart or show_cluster_chart:
            c1, c2 = st.columns(2)
            
            if show_town_chart:
                town_df = kpi_df.groupby(town_col).size().reset_index(name='Count').sort_values('Count', ascending=False).head(10)
                ch1 = alt.Chart(town_df).mark_bar(color='#E4002B').encode( # Airtel Red
                    x=alt.X(f'{town_col}:N', sort='-y', title="Town", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('Count:Q', title="Failures"), 
                    tooltip=[town_col, 'Count']
                ).properties(title="Top 10 Towns", height=320).configure_view(strokeWidth=0)
                c1.altair_chart(ch1, use_container_width=True)
            
            if show_cluster_chart:
                clus_df = kpi_df.groupby(cluster_col).size().reset_index(name='Count').sort_values('Count', ascending=False).head(10)
                ch2 = alt.Chart(clus_df).mark_bar(color='#FFB703').encode( # Vibrant Yellow
                    x=alt.X(f'{cluster_col}:N', sort='-y', title="Cluster", axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('Count:Q', title="Failures"), 
                    tooltip=[cluster_col, 'Count']
                ).properties(title="Top 10 Clusters", height=320).configure_view(strokeWidth=0)
                
                chart_col = c2 if show_town_chart else c1 
                chart_col.altair_chart(ch2, use_container_width=True)

        # Stateful Actionable Data Table
        current_view = st.session_state[f'view_{kpi_name}']
        display_df = kpi_df if current_view == 'all' else kpi_severe_df
        view_label = "All Failed Sites" if current_view == 'all' else "Severely Degraded Sites (≥3 Fails)"
        
        st.markdown("---")
        st.markdown(f"<h3 style='color: #2b2d42;'>Actionable Data: {view_label} ({len(display_df)})</h3>", unsafe_allow_html=True)
        
        clean_cols = [c for c in display_df.columns if not c.startswith("FAIL_") and not c.startswith("CRIT_") and not c.startswith("_")]
        
        if not display_df.empty:
            csv_export_all = display_df[clean_cols].to_csv(index=False).encode('utf-8')
            st.download_button(f"📥 Export Current View ({len(display_df)} rows)", data=csv_export_all, file_name=f"{kpi_name}_{current_view}.csv", type="primary")
            
            st.dataframe(display_df[clean_cols].head(1000), use_container_width=True)
        else:
            st.success(f"No records found for '{view_label}' in current filter scope.")
