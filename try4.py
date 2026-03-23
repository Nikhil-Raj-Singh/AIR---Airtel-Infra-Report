import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import subprocess

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Network Diagnostic Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- 2. DATA INGESTION & UPLOAD ---
with st.sidebar:
    st.header("📂 Data Input")
    uploaded_file = st.file_uploader("Upload Site Data (CSV/Excel)", type=["csv", "xlsx"])
    
    # Fallback to generate sample data if no file is uploaded yet
    if uploaded_file is None:
        st.warning("Please upload a file, or click below to test with sample data.")
        if st.button("Load Sample Data"):
            np.random.seed(42)
            n_sites = 500
            df = pd.DataFrame({
                "SITE ID": [f"S_{i:05d}" for i in range(1, n_sites + 1)],
                "Cluster": np.random.choice(["Alpha", "Beta", "Gamma", "Delta"], n_sites),
                "Town": np.random.choice(["Town A", "Town B", "Town C", "Town D"], n_sites),
                "DG/Non-DG ULS": np.random.choice(["DG", "Non-DG"], n_sites, p=[0.7, 0.3]),
                "DG Automation (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.8, 0.2]),
                "DG Automation Status (SNMP)": np.random.choice(["OK", "Failed", "Not Reachable", "Timeout"], n_sites, p=[0.7, 0.15, 0.1, 0.05]),
                "Automation OK (Session Percentage)": np.random.uniform(40.0, 100.0, n_sites),
                "Battery Backup (Hrs)": np.random.uniform(0.5, 12.0, n_sites),
                "BB Low (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.2, 0.8]),
                "BB Replacement (Yes/No)": np.random.choice(["Yes", "No"], n_sites, p=[0.1, 0.9]),
                "RM Count (N+1)": np.random.choice(["OK", "Failed", "Degraded"], n_sites, p=[0.85, 0.1, 0.05])
            })
            st.session_state['dummy_data'] = df
        
        if 'dummy_data' in st.session_state:
            df = st.session_state['dummy_data']
            st.success("Sample Data Loaded!")
        else:
            st.stop() # Stops the rest of the app from running until data is present
    else:
        # Load the actual uploaded file
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Error loading file: {e}")
            st.stop()

# --- 3. SIDEBAR: ENGINE ROOM & KPI CONFIGURATION ---
with st.sidebar:
    st.markdown("---")
    st.header("⚙️ KPI Engine Room")
    
    st.subheader("✅ Standard Critical KPIs")
    check_battery = st.checkbox("Battery Check", value=True)
    check_dg = st.checkbox("DG Automation Check", value=True)
    check_rm = st.checkbox("RM (N+1) Check", value=True)
    
    if check_dg:
        with st.expander("🛠️ DG Logic", expanded=False):
            # Check if column exists before trying to use it to prevent KeyError
            if "DG Automation Status (SNMP)" in df.columns:
                dg_opts = df["DG Automation Status (SNMP)"].dropna().unique().tolist()
                default_dg = [x for x in ["Failed", "Not Reachable"] if x in dg_opts]
                dg_fail_states = st.multiselect("SNMP Failure Statuses:", options=dg_opts, default=default_dg)
            else:
                dg_fail_states = []
                st.warning("Column 'DG Automation Status (SNMP)' missing.")
            session_threshold = st.slider("Min Session %", 0.0, 100.0, 80.0, step=5.0)

    if check_battery:
        with st.expander("🔋 Battery Logic", expanded=False):
            battery_min_hrs = st.number_input("Min Backup (Hrs)", value=3.0, step=0.5)
            check_bb_low_flag = st.checkbox("Fail on 'BB Low' = Yes", value=True)

    if check_rm:
        with st.expander("📡 RM Logic", expanded=False):
            if "RM Count (N+1)" in df.columns:
                rm_opts = df["RM Count (N+1)"].dropna().unique().tolist()
                default_rm = [x for x in ["Failed", "Degraded"] if x in rm_opts]
                rm_fail_states = st.multiselect("RM Failure Statuses:", options=rm_opts, default=default_rm)
            else:
                rm_fail_states = []
                st.warning("Column 'RM Count (N+1)' missing.")

    st.markdown("---")
    st.subheader("🏗️ Custom Rule Builder")
    use_custom_rule = st.checkbox("Enable Custom Rule", value=False)
    
    if use_custom_rule:
        custom_col = st.selectbox("Select Column", df.columns)
        custom_op = st.selectbox("Condition (Fails if)", ["Equals", "Not Equals", "Contains", "Greater Than", "Less Than"])
        custom_val = st.text_input("Value to check")


# --- 4. VECTORIZED KPI EVALUATION ---
df['Is_100_OK'] = True
df['Failure_Reasons'] = ""

try:
    if check_dg and "DG/Non-DG ULS" in df.columns and "DG Automation (Yes/No)" in df.columns and "DG Automation Status (SNMP)" in df.columns and "Automation OK (Session Percentage)" in df.columns:
        is_dg = df["DG/Non-DG ULS"].astype(str).str.upper() == "DG"
        has_automation = df["DG Automation (Yes/No)"].astype(str).str.upper() == "YES"
        snmp_failed = df["DG Automation Status (SNMP)"].isin(dg_fail_states)
        session_failed = pd.to_numeric(df["Automation OK (Session Percentage)"], errors='coerce').fillna(100) < session_threshold
        
        dg_mask = is_dg & has_automation & (snmp_failed | session_failed)
        df.loc[dg_mask, 'Is_100_OK'] = False
        df.loc[dg_mask, 'Failure_Reasons'] += "DG Auto Issue; "

    if check_battery and "Battery Backup (Hrs)" in df.columns and "BB Low (Yes/No)" in df.columns:
        hrs_failed = pd.to_numeric(df["Battery Backup (Hrs)"], errors='coerce').fillna(99) < battery_min_hrs
        flag_low_failed = (df["BB Low (Yes/No)"].astype(str).str.upper() == "YES") if check_bb_low_flag else False
        
        batt_mask = hrs_failed | flag_low_failed
        df.loc[batt_mask, 'Is_100_OK'] = False
        df.loc[batt_mask, 'Failure_Reasons'] += "Battery Issue; "

    if check_rm and "RM Count (N+1)" in df.columns:
        rm_mask = df["RM Count (N+1)"].isin(rm_fail_states)
        df.loc[rm_mask, 'Is_100_OK'] = False
        df.loc[rm_mask, 'Failure_Reasons'] += "RM (N+1) Failed; "

    if use_custom_rule and custom_val:
        if custom_op == "Equals":
            custom_mask = df[custom_col].astype(str).str.strip().str.lower() == custom_val.strip().lower()
        elif custom_op == "Not Equals":
            custom_mask = df[custom_col].astype(str).str.strip().str.lower() != custom_val.strip().lower()
        elif custom_op == "Contains":
            custom_mask = df[custom_col].astype(str).str.contains(custom_val, case=False, na=False)
        elif custom_op == "Greater Than":
            custom_mask = pd.to_numeric(df[custom_col], errors='coerce') > float(custom_val)
        elif custom_op == "Less Than":
            custom_mask = pd.to_numeric(df[custom_col], errors='coerce') < float(custom_val)
        
        df.loc[custom_mask, 'Is_100_OK'] = False
        df.loc[custom_mask, 'Failure_Reasons'] += f"Custom Rule ({custom_col}); "

except Exception as e:
    st.error(f"Error applying logic: {e}")

# Clean up text
df['Failure_Reasons'] = df['Failure_Reasons'].str.rstrip('; ').replace("", "None")


# --- 5. MAIN PAGE: DASHBOARD UI ---
st.title("📡 Site Health & Failure Distribution")
st.markdown("---")

total_sites = len(df)
ok_sites = df['Is_100_OK'].sum()
failed_sites = total_sites - ok_sites

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Active Sites", f"{total_sites:,}")
col2.metric("✅ 100% OK Sites", f"{ok_sites:,}", f"{(ok_sites/total_sites)*100:.1f}%" if total_sites > 0 else "0%")
col3.metric("🚨 Failed Sites", f"{failed_sites:,}", f"-{failed_sites}", delta_color="inverse")

if "Battery Backup (Hrs)" in df.columns:
    critical_battery = df[pd.to_numeric(df["Battery Backup (Hrs)"], errors='coerce') < 1.0].shape[0]
    col4.metric("⚠️ Critical Battery (< 1Hr)", f"{critical_battery:,}")

st.markdown("<br>", unsafe_allow_html=True)

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Distribution of Failure Reasons")
    if failed_sites > 0:
        reasons_counts = df[df['Is_100_OK'] == False]['Failure_Reasons'].str.split('; ').explode().value_counts()
        st.bar_chart(reasons_counts, color="#ff4b4b")
    else:
        st.success("No failures to display.")

with chart_col2:
    st.subheader("Failures by Cluster")
    if failed_sites > 0 and "Cluster" in df.columns:
        cluster_fails = df[df['Is_100_OK'] == False]["Cluster"].value_counts()
        st.bar_chart(cluster_fails, color="#ff9f36")
    else:
        st.info("No cluster failures.")

st.markdown("### 📋 Actionable Site List (Filtered to Failures)")
failed_df_view = df[df['Is_100_OK'] == False].copy()

st.dataframe(
    failed_df_view.style.map(lambda x: 'background-color: rgba(255, 75, 75, 0.1)', subset=['Failure_Reasons']),
    use_container_width=True,
    hide_index=True
)

# --- 6. BULLETPROOF AUTO-RUN MAGIC ---
if __name__ == '__main__':
    # Prevent infinite loop if already running in Streamlit
    if "streamlit" not in sys.argv[0]:
        print("Initializing Dashboard Engine...")
        
        # Safely determine the script path, dodging VS Code Interactive environment errors
        try:
            if '__file__' in globals():
                script_path = os.path.abspath(__file__)
            else:
                script_path = os.path.abspath(sys.argv[0])
            
            # Use subprocess to safely handle spaces in Windows paths
            subprocess.run([sys.executable, "-m", "streamlit", "run", script_path])
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Auto-launch failed: {e}")
            print("\nPlease open your VS Code terminal and run this command manually:")
            print("streamlit run app.py")
            
        sys.exit()
