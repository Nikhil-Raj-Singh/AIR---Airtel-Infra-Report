# AIR – Airtel Infra‑Health Report
**Project Design Brief & Development Prompt**

## Background
This project is developed on a **corporate‑managed laptop** with strict constraints:
* No admin rights
* No system‑level configuration changes
* Limited control over Python environment (no heavy external installations)
* Must run using plain `python app.py`

Despite these limitations, this is a **robust, scalable, and professional Business Intelligence dashboard** for telecom infrastructure health monitoring.

## Design Philosophy & Technical Constraints
1. **Environment‑first engineering:** The tool adapts to constraints. The entire app MUST remain in a single `app.py` file.
2. **Streamlit Auto‑Launcher:** The script auto-launches via `subprocess.run([sys.executable, "-m", "streamlit", "run", ...])` to bypass restricted terminals.
3. **Restricted Libraries:** ONLY use `streamlit`, `pandas`, `numpy`, and `altair` (which is native to Streamlit). NO Plotly, NO external CSS frameworks.
4. **Corporate UI Theme (Airtel):** * Background: Clean light gray (`#f4f6f9`).
   * Primary Accent: Airtel Red (`#E4002B`), with Yellow (`#FFB703`) and Blue (`#005A9C`).
   * Styling: Glassmorphism, 3D animated floating cards, and custom Streamlit button CSS injected via `st.markdown`.
5. **Performance:** Heavy data processing must be wrapped in `@st.cache_data`. UI routing must use `st.session_state`.

## What We Have Achieved (Phase 1 & 2 Complete)
* **Dynamic Logic Setup Studio:** Users dynamically build multi-level KPI failure rules (Pre-conditions + Base Failures + Nested AND logic + Severity Thresholds) directly from the UI based on uploaded Excel/CSV column headers. Configs can be exported/imported as JSON.
* **App Routing Engine:** A custom multi-page feel inside a single file using `st.session_state.nav_selection`.
* **Global Drill-Downs:** A floating popover button on the main page allows universal filtering by Circle, Toco, Macro/ULS, District, Town, and Cluster.
* **Home Summary:** Displays overall network health, total sites, Severely Degraded sites (≥3 fails globally), and specific KPI breakdown blocks.
* **Interactive Deep Dives:** Clicking a KPI on the Home page routes to a dedicated Deep Dive page. It features conditional Altair charts (Top 10 District/Cluster), and stateful buttons to toggle the actionable data table between "All Failed Sites" and "Severely Degraded (KPI Severity Met)".

## Current Goal / Next Steps (Phase 3)
*Wait for my prompt below to tell you what to build next. Keep the above context in mind for all code generation. Acknowledge this prompt by saying "AIR Central BI Context Loaded. What are we building next?"*
