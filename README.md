
# 📡 AIR Central BI (Airtel Infra‑Health Report)

AIR Central BI is an internal analytics dashboard designed to analyze and monitor telecom infrastructure site health using KPI data extracted from Excel / CSV reports. 

The tool is built specifically to work in **corporate‑restricted environments** (where package installation and system access are limited), while providing an enterprise-grade, glassmorphic UI with dynamic, user-defined logic.

## 🎯 Objective
* Identify **100% OK sites** based on dynamically selected core KPIs.
* Identify **Deficient sites** and rank them by severity.
* Flag **Severely Degraded sites** (≥3 total concurrent failures).
* Perform **cluster‑wise, toco-wise, and town-wise** failure analysis.
* Provide a clean, interactive, Airtel-branded dashboard usable by engineers and managers.

---

## 🔬 How Fault Analysis Works (The Logic Engine)
Instead of hardcoding what constitutes a "fault," AIR evaluates faults row-by-row using user-defined rules via the **Logic Setup Studio**. 

A fault analysis rule consists of 4 layers of evaluation:
1. **Pre-Condition (Scope Filter):** Ensures the fault is only checked for relevant sites. 
   * *Example:* Only check for "DG Automation" failures if the site is a DG site (`DG/Non-DG == DG`).
2. **Primary Failure Condition:** The main trigger for the fault.
   * *Example:* `DG Automation (Yes/No) == No`.
3. **Nested Condition (AND Logic):** An additional constraint that must *also* be true.
   * *Example:* Only flag if `RM Count (N+1) > 1`.
4. **Severity Level (Feeders Impacted):** Identifies highly critical sites *within* this specific fault category.
   * *Example:* A site has Low Battery, but it becomes "Critical" if `Battery Backup < 2 hours`.

### 🚨 Severity Tracking
The dashboard tracks two different types of "Severity" to prioritize fieldwork:
1. **Global Severely Degraded (Network-Wide):** A site is flagged as "Severely Degraded" on the Home page if it is concurrently failing **≥ 3 different KPI rules** across the entire network.
2. **Feeders Impacted (KPI Specific):** Inside a specific KPI dashboard, this counts how many sites failing *this specific KPI* also breached the custom Step 4 "Severity Level" defined in the Logic Studio.

---

## 🧩 Key Features

* **Corporate‑Safe Single-File Design:** Runs using `python app.py` (no `streamlit run` required). Uses only `streamlit`, `pandas`, `numpy`, and `altair`.
* **Logic Setup Studio:** A no-code rules engine to build custom fault analyses.
* **Config Management:** Export and Import your KPI logic configurations as JSON files so you never have to rebuild your rules.
* **Floating Global Drill-Downs:** A popover menu allows instant slicing of data by Circle, Principal Owner (Toco), Macro/ULS, District, Town, and Cluster.
* **Airtel Corporate Theme:** A highly polished, Red-dominant (`#E4002B`) glassmorphic UI with 3D animated Streamlit buttons.
* **Dynamic Routing:** Seamless navigation between the Global Home Summary and dedicated KPI Deep Dive dashboards.
* **Stateful Exporting:** One-click CSV downloads for actionable site lists inside deep dives, pre-filtered for "All Fails" or "Severely Degraded".
* **Smart Visuals:** Altair bar charts automatically hide themselves if filtered down to a single entity (e.g., hiding a Top 10 Town chart if only one Town is selected).

---

## 🖥 Dashboard Structure

**🔹 Sidebar (Control Center)**
* Main Navigation Menu (Home, Logic Setup, dynamically generated Deep Dives)
* File upload (Excel / CSV)
* Config Management (JSON Import/Export)

**🔹 Top Bar**
* Floating 🔍 Global Drill-Down Search Filters

**🔹 Home Summary**
* Top Tier Metrics: Total Sites, Network Health %, Sites 100% OK
* Secondary Metrics: Deficient Sites, Severely Degraded, Feeder Analysis
* Different Fail Types: Clickable 3D buttons for each defined KPI
* Fail Distribution Overview: Top N charts colored by failure type

**🔹 KPI Deep Dive**
* Stateful toggle buttons: FAILED SITES vs. SEVERELY DEGRADED
* Top 10 District & Top 10 Cluster charts
* Actionable Data Table with context-aware CSV exports

---

## ▶️ How to Run

```bash
python app.py
```
*The application auto‑launches Streamlit internally.*

## 📁 Expected Input
Excel (`.xlsx`, `.xls`) or CSV (`.csv`). The app handles dynamic columns based on your Logic Setup Studio configurations. Extra columns are supported and retained for export analysis.

## 🚀 Future Enhancements (Planned / Phase 3)
* Feeder Analysis module integration.
* Weighted severity scoring.
* Historical comparison (daily / weekly trends).
