
# AIR – Airtel Infra‑Health Report

AIR (Airtel Infra‑Health Report) is an internal analytics dashboard designed to
analyze and monitor telecom infrastructure site health using KPI data extracted
from Excel / CSV reports.

The tool is built specifically to work in **corporate‑restricted environments**
(where package installation and system access are limited), while still
providing meaningful, scalable, and actionable insights for network and infra
operations teams.

---

## 🎯 Objective

- Identify **100% OK sites** based on selected core KPIs
- Identify **Not OK sites** and rank them by severity
- Perform **cluster‑wise and KPI‑wise failure analysis**
- Highlight **worst affected sites** (Top‑N) for prioritization
- Provide a clean, interactive dashboard usable by engineers and managers

---

## 🧩 Key Features

### ✅ Corporate‑Safe Design
- Runs using `python app.py` (no `streamlit run` required)
- No dependency on restricted libraries (no matplotlib, plotly, seaborn, etc.)
- Uses only:
  - `streamlit`
  - `pandas`
  - Python standard libraries

### ✅ Smart Column Handling
- Automatically cleans multi‑line and duplicate Excel headers
- Enforces **unique column names** (prevents Streamlit / PyArrow crashes)
- Regex‑based **auto column detection**
- Manual override available via sidebar (collapsible)

### ✅ Flexible KPI Logic
- KPIs used for **100% OK classification** are configurable:
  - Battery Backup
  - DG Automation
  - SNMP Communication
  - RM Count (N+1)
- Additional KPIs can be analyzed without affecting the “100% OK” definition

### ✅ Correct Business Logic
- Battery Backup: **Yes / No**
  - Yes → OK
  - No → FAIL
- RM Count (N+1): **Yes / No**
  - Yes → OK
  - No → FAIL

### ✅ Actionable Analytics
- Fail score per site (number of failed KPIs)
- Top‑N worst sites (10 / 20 / 50)
- Cluster‑wise and KPI‑wise failure distribution
- Full row data visibility (no column hiding)

---

## 🖥 Dashboard Structure

### 🔹 Sidebar (Control Center)
- File upload (Excel / CSV)
- KPI configuration (checkbox‑based)
- Column mapping (auto‑detected + override)

### 🔹 Main Dashboard
- Cluster selector
- KPI summary cards:
  - ✅ 100% OK Sites
  - ❌ Not OK Sites
  - 📊 Total Sites

### 🔹 Tabs
1. **Overview**
   - Cluster‑wise or KPI‑wise failure distribution
2. **Not OK Analysis**
   - Worst affected sites (Top‑N)
3. **KPI Deep Dive**
   - Per‑KPI stats, charts, and full site list

---

## ▶️ How to Run

```bash
python app.py
```

The application auto‑launches Streamlit internally.

***

## 📁 Expected Input

*   Excel (`.xlsx`, `.xls`) or CSV (`.csv`)
*   Typical columns:
    *   Site ID
    *   Cluster
    *   Battery Backup (Yes/No)
    *   DG Automation Status
    *   SNMP Communicated
    *   RM Count (N+1)
*   Extra columns are supported and retained for analysis

***

## 🚀 Future Enhancements (Planned)

*   Excel export per tab
*   Weighted severity scoring
*   EB / Feeder KPI integration
*   Auto‑mapping without manual confirmation
*   Dark / Airtel‑themed UI
*   Historical comparison (daily / weekly)

***

## 👤 Author Notes

This project was intentionally designed under **restricted corporate laptop
constraints** to ensure maximum portability and real‑world usability inside
enterprise environments.

AIR serves as a foundation that can be extended into a full‑fledged Infra
Health & SLA monitoring platform.

***

---

