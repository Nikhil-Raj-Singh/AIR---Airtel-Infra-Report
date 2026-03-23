import streamlit as st
import pandas as pd
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Network Diagnostic Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- 2. DATA LOADING (Hardcoded to your exact screenshot columns) ---
@st.cache_data
def load_data():
    np.random.seed(42)
    n_sites = 500
    data = {
        "SITE ID": [f"S_{i:05d}" for i in range(1, n_sites + 1)],
        "Cluster": np.random.choice(["Alpha", "Beta", "Gamma", "Delta"], n_sites),
        "Town": np.random.choice(["Town A", "Town B", "Town C", "Town D"], n_sites),
        "Macro/ULS": np.random.choice(["Macro", "ULS"], n_sites),
        "Toco ID": [f"T_{i:04d}" for i in range(1, n_sites + 1)],
        "DG/Non-DG ULS": np.random.choice(["DG", "Non-DG"], n_sites, p=[0.7, 0.3]),
        "DG KVA": np.random.choice([10, 15, 20, 25], n_sites),
        "DG Automation (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.8, 0.2]),
        "DG Automation Status (SNMP)": np.random.choice(["OK", "Failed", "Not Reachable", "Timeout"], n_sites, p=[0.7, 0.15, 0.1, 0.05]),
        "Automation OK (Session Percentage)": np.random.uniform(40.0, 100.0, n_sites),
        "Battery Backup (Hrs)": np.random.uniform(0.5, 12.0, n_sites),
        "Battery Backup As per ALARM (Hrs)": np.random.uniform(0.5, 12.0, n_sites),
        "Battery Backup Bucket": np.random.choice(["<2 Hrs", "2-4 Hrs", ">4 Hrs"], n_sites),
        "BB Low (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.2, 0.8]),
        "BB Replacement (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.1, 0.9]),
        "BB Enhancement (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.15, 0.85]),
        "RM Count (N+1)": np.random.choice(["OK", "Failed", "Degraded"], n_sites, p=[0.85, 0.1, 0.05])
    }
    return pd.DataFrame(data)

df = load_data()

# --- 3. SIDEBAR: ENGINE ROOM & NESTED LOGIC ---
with st.sidebar:
    st.header("⚙️ KPI Engine Room")
    st.markdown("Configure nested logic for 100% OK calculation.")
    
    # Main KPI Toggles (As seen in your first screenshot)
    st.subheader("✅ KPIs for 100% OK")
    check_battery = st.checkbox("Battery", value=True)
    check_dg = st.checkbox("DG Automation", value=True)
    check_rm = st.checkbox("RM (N+1)", value=True)
    
    st.markdown("---")
    
    # Nested Configuration Expanders
    if check_dg:
        with st.expander("🛠️ DG Logic Configuration", expanded=True):
            st.caption("Site must be 'DG' AND 'Automation=Yes' to be evaluated.")
            dg_fail_states = st.multiselect(
                "SNMP Failure Statuses:", 
                options=df["DG Automation Status (SNMP)"].unique(),
                default=["Failed", "Not Reachable", "Timeout"]
            )
            session_threshold = st.slider("Min Automation Session %", 0.0, 100.0, 80.0, step=5.0)

    if check_battery:
        with st.expander("🔋 Battery Logic Configuration", expanded=True):
            battery_min_hrs = st.number_input("Min Battery Backup (Hrs)", value=3.0, step=0.5)
            check_bb_low_flag = st.checkbox("Also fail if 'BB Low' = Yes", value=True)
            check_bb_replace_flag = st.checkbox("Also fail if 'BB Replacement' = Yes", value=False)

    if check_rm:
        with st.expander("📡 RM Logic Configuration", expanded=True):
            rm_fail_states = st.multiselect(
                "RM Failure Statuses:",
                options=df["RM Count (N+1)"].unique(),
                default=["Failed", "Degraded"]
            )

# --- 4. VECTORIZED KPI EVALUATION ---
df['Is_100_OK'] = True
df['Failure_Reasons'] = ""

# Condition 1: Nested DG Logic
if check_dg:
    # Layer 1: Is it applicable?
    is_dg = df["DG/Non-DG ULS"].str.upper() == "DG"
    has_automation = df["DG Automation (Yes/No)"].str.upper() == "YES"
    
    # Layer 2: Did it fail? (Fails if SNMP is bad OR Session % is too low)
    snmp_failed = df["DG Automation Status (SNMP)"].isin(dg_fail_states)
    session_failed = df["Automation OK (Session Percentage)"] < session_threshold
    
    dg_failure_mask = is_dg & has_automation & (snmp_failed | session_failed)
    
    df.loc[dg_failure_mask, 'Is_100_OK'] = False
    df.loc[dg_failure_mask, 'Failure_Reasons'] += "DG Auto Issue; "

# Condition 2: Nested Battery Logic
if check_battery:
    # Fails if Hours are low OR (if checked) the specific flags say "Yes"
    hrs_failed = df["Battery Backup (Hrs)"] < battery_min_hrs
    flag_low_failed = (df["BB Low (Yes/No)"].str.upper() == "YES") if check_bb_low_flag else False
    flag_replace_failed = (df["BB Replacement (Yes/No)"].str.upper() == "YES") if check_bb_replace_flag else False
    
    battery_failure_mask = hrs_failed | flag_low_failed | flag_replace_failed
    
    df.loc[battery_failure_mask, 'Is_100_OK'] = False
    df.loc[battery_failure_mask, 'Failure_Reasons'] += "Battery Issue; "

# Condition 3: RM Logic
if check_rm:
    rm_failure_mask = df["RM Count (N+1)"].isin(rm_fail_states)
    
    df.loc[rm_failure_mask, 'Is_100_OK'] = False
    df.loc[rm_failure_mask, 'Failure_Reasons'] += "RM (N+1) Failed; "

# Clean up trailing text
df['Failure_Reasons'] = df['Failure_Reasons'].str.rstrip('; ')
df['Failure_Reasons'] = df['Failure_Reasons'].replace("", "None")


# --- 5. MAIN PAGE: DASHBOARD UI ---
st.title("📡 Site Health & Failure Distribution")
st.markdown("---")

# Metrics
total_sites = len(df)
ok_sites = df['Is_100_OK'].sum()
failed_sites = total_sites - ok_sites

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Active Sites", f"{total_sites:,}")
col2.metric("✅ 100% OK Sites", f"{ok_sites:,}", f"{(ok_sites/total_sites)*100:.1f}%")
col3.metric("🚨 Failed Sites", f"{failed_sites:,}", f"-{failed_sites}", delta_color="inverse")
# Adding a specific metric for high priority interventions
critical_battery = df[df["Battery Backup (Hrs)"] < 1.0].shape[0]
col4.metric("⚠️ Critical Battery (< 1Hr)", f"{critical_battery:,}")

st.markdown("<br>", unsafe_allow_html=True)

# Visualizations Row 1
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Distribution of Failure Reasons")
    if failed_sites > 0:
        # Split string, explode, and count to accurately graph multiple failures per site
        reasons_counts = df[df['Is_100_OK'] == False]['Failure_Reasons'].str.split('; ').explode().value_counts()
        st.bar_chart(reasons_counts, color="#ff4b4b")
    else:
        st.success("No failures to display.")

with chart_col2:
    st.subheader("Failures by Cluster")
    if failed_sites > 0:
        cluster_fails = df[df['Is_100_OK'] == False]["Cluster"].value_counts()
        st.bar_chart(cluster_fails, color="#ff9f36")
    else:
        st.info("No cluster failures.")

# Actionable Table
st.markdown("### 📋 Actionable Site List (Filtered to Failures)")

# Create a clean view of just the failed sites with the most important columns
failed_df_view = df[df['Is_100_OK'] == False][
    ["SITE ID", "Cluster", "Town", "DG/Non-DG ULS", "DG Automation Status (SNMP)", 
     "Automation OK (Session Percentage)", "Battery Backup (Hrs)", "RM Count (N+1)", "Failure_Reasons"]
].copy()

# Round numbers for cleaner display
failed_df_view["Automation OK (Session Percentage)"] = failed_df_view["Automation OK (Session Percentage)"].round(1)
failed_df_view["Battery Backup (Hrs)"] = failed_df_view["Battery Backup (Hrs)"].round(2)

st.dataframe(
    failed_df_view.style.map(lambda x: 'background-color: rgba(255, 75, 75, 0.1)', subset=['Failure_Reasons']),
    use_container_width=True,
    hide_index=True
)
