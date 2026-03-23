import streamlit as st
import pandas as pd
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Network Diagnostic Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- 2. DUMMY DATA GENERATOR (For demonstration) ---
@st.cache_data
def load_sample_data():
    np.random.seed(42)
    data = {
        "SITE_ID": [f"S_{i:04d}" for i in range(1, 101)],
        "Cluster_Name": np.random.choice(["North", "South", "East", "West"], 100),
        "DG/Non-DG ULS": np.random.choice(["DG", "Non-DG"], 100, p=[0.7, 0.3]),
        "DG_Auto_Status": np.random.choice(["OK", "Failed", "Not Reachable"], 100, p=[0.6, 0.3, 0.1]),
        "Battery_Backup_Hrs": np.random.uniform(0.5, 12.0, 100),
        "RM_Status": np.random.choice(["OK", "Failed"], 100, p=[0.9, 0.1])
    }
    return pd.DataFrame(data)

df = load_sample_data()

# --- 3. AUTO-DETECTION ENGINE (Native Python) ---
STANDARD_FIELDS = {
    "Site ID": ["site id", "site_id", "siteid"],
    "Cluster": ["cluster", "cluster_name", "zone"],
    "DG Type": ["dg/non-dg", "dg/non-dg uls", "site type"],
    "DG Automation": ["dg_auto_status", "dg automation status", "automation"],
    "Battery Backup": ["battery_backup_hrs", "battery backup (hrs)", "bb_hrs"],
    "RM Status": ["rm_status", "rm (n+1)"]
}

def auto_detect_columns(df_cols, standard_fields):
    mapped_cols = {}
    df_cols_lower = [c.lower() for c in df_cols]
    
    for standard, synonyms in standard_fields.items():
        match = df_cols[0] # Default to first column if no match found
        for syn in synonyms:
            if syn in df_cols_lower:
                idx = df_cols_lower.index(syn)
                match = df_cols[idx]
                break
        mapped_cols[standard] = match
    return mapped_cols

# --- 4. SIDEBAR: CONTROLS & MAPPING ---
with st.sidebar:
    st.header("⚙️ Dashboard Engine")
    
    st.markdown("### 1. Column Mapping")
    detected_mapping = auto_detect_columns(df.columns.tolist(), STANDARD_FIELDS)
    
    with st.expander("Review Mapped Columns", expanded=False):
        final_mapping = {}
        for field, detected in detected_mapping.items():
            final_mapping[field] = st.selectbox(f"{field}", df.columns, index=df.columns.get_loc(detected))
    
    st.markdown("### 2. Critical KPI Logic")
    with st.expander("Configure KPI Thresholds", expanded=True):
        st.write("**DG Logic:**")
        check_dg = st.checkbox("Include DG Automation Failure", value=True)
        dg_fail_state = st.selectbox("What counts as DG fail?", ["Failed", "Not Reachable"], index=0)
        
        st.write("**Battery Logic:**")
        check_battery = st.checkbox("Include Low Battery", value=True)
        battery_threshold = st.slider("Min Battery Backup (Hrs)", 0.0, 12.0, 4.0)

# --- 5. NESTED LOGIC EVALUATION ---
df['Is_100_OK'] = True
df['Failure_Reasons'] = ""

# Condition 1: DG Logic
if check_dg:
    is_dg_site = df[final_mapping["DG Type"]].str.contains("DG", na=False, case=False)
    has_auto_failed = df[final_mapping["DG Automation"]] == dg_fail_state
    
    dg_failure_mask = is_dg_site & has_auto_failed
    df.loc[dg_failure_mask, 'Is_100_OK'] = False
    df.loc[dg_failure_mask, 'Failure_Reasons'] += "DG Auto Failed; "

# Condition 2: Battery Logic
if check_battery:
    battery_failure_mask = df[final_mapping["Battery Backup"]] < battery_threshold
    df.loc[battery_failure_mask, 'Is_100_OK'] = False
    df.loc[battery_failure_mask, 'Failure_Reasons'] += f"Low Battery (<{battery_threshold}h); "

# Clean up text
df['Failure_Reasons'] = df['Failure_Reasons'].str.rstrip('; ')
df['Failure_Reasons'] = df['Failure_Reasons'].replace("", "None")


# --- 6. MAIN PAGE: DASHBOARD ---
st.title("📡 Network Health & Site Diagnostics")
st.markdown("---")

total_sites = len(df)
ok_sites = df['Is_100_OK'].sum()
failed_sites = total_sites - ok_sites

col1, col2, col3 = st.columns(3)
col1.metric("Total Sites Evaluated", total_sites)
col2.metric("✅ 100% OK Sites", ok_sites, f"{(ok_sites/total_sites)*100:.1f}%")
col3.metric("🚨 Sites Requiring Action", failed_sites, f"-{failed_sites}", delta_color="inverse")

st.markdown("<br>", unsafe_allow_html=True)

# Native Streamlit Visualizations
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("Distribution of Failures")
    if failed_sites > 0:
        # Explode failure reasons and count them
        reasons_df = df[df['Is_100_OK'] == False]['Failure_Reasons'].str.split('; ').explode().value_counts()
        st.bar_chart(reasons_df)
    else:
        st.success("No failures detected!")

with col_chart2:
    st.subheader("Failures by Cluster")
    if failed_sites > 0:
        cluster_fails = df[df['Is_100_OK'] == False][final_mapping["Cluster"]].value_counts()
        st.bar_chart(cluster_fails)
    else:
        st.info("All clusters are 100% OK.")

st.markdown("### 📋 Actionable Site List (Failed Only)")
failed_df = df[df['Is_100_OK'] == False][[final_mapping["Site ID"], final_mapping["Cluster"], final_mapping["DG Type"], final_mapping["Battery Backup"], 'Failure_Reasons']]

st.dataframe(
    failed_df.style.applymap(lambda x: 'background-color: #ffcccc', subset=['Failure_Reasons']),
    use_container_width=True,
    hide_index=True
)
