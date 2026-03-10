
# AIR – Airtel Infra‑Health Report  
## Project Design Brief & Development Prompt

### Background

This project was developed on a **corporate‑managed laptop** with the following
constraints:

- No admin rights
- No ability to install Python packages
- No system‑level configuration changes
- Limited control over Python environment
- Must run using plain `python app.py`

Despite these limitations, the requirement was to build a **robust, scalable,
and professional analytics dashboard** for telecom infrastructure health
monitoring.

---

## Design Philosophy

1. **Environment‑first engineering**
   - Tool must adapt to constraints, not the other way around
2. **Business‑correct logic**
   - KPI definitions must match actual field interpretation
3. **Extendable architecture**
   - Easy to add new KPIs, scoring models, and exports
4. **Manager‑ready output**
   - Clear summaries + drill‑down capability

---

## Key Technical Decisions

### ✅ Streamlit Auto‑Launcher
Instead of relying on `streamlit run`, the app auto‑launches itself using:

```python
python -m streamlit run app.py
````

This allows execution from restricted terminals.

***

### ✅ No Plotting Libraries

*   `matplotlib`, `plotly`, etc. are not available
*   All visualizations use **Streamlit native charts**
*   Bar charts are used where pie charts would normally be preferred

***

### ✅ Column Normalization & Deduplication

Excel files often contain:

*   Multi‑line headers
*   Duplicate column names (e.g., "Sl No.")
*   Inconsistent spacing

A preprocessing step:

*   Cleans headers
*   Enforces uniqueness
*   Prevents PyArrow / Streamlit crashes

***

### ✅ Smart Column Mapping

Regex‑based auto detection is used to:

*   Reduce manual mapping effort
*   Improve robustness across report formats

Manual override is still available for safety.

***

### ✅ KPI Classification Strategy

#### Core KPIs (used for 100% OK check)

*   Battery Backup
*   DG Automation
*   SNMP Communication
*   RM Count (N+1)

#### KPI Interpretation

*   Yes → OK
*   No → FAIL

Fail Score = number of failed KPIs per site

This allows:

*   Severity ranking
*   Worst‑site identification
*   Priority‑based action planning

***

## Intended Usage Flow

1.  Upload Infra KPI Excel / CSV
2.  Confirm column mapping (optional)
3.  Select KPIs that define “100% OK”
4.  Select cluster (or All)
5.  Review:
    *   Overall health
    *   Worst sites
    *   KPI‑specific failures

***

## Extension Guidelines (Future Work)

When extending this project:

*   Keep dependencies minimal
*   Maintain separation between:
    *   KPI logic
    *   Visualization
    *   Data preprocessing
*   Add new KPIs using:
    *   Boolean fail flags
    *   Inclusion toggles in sidebar
*   Preserve backward compatibility with existing reports

***

## Final Note

AIR is not just a dashboard —
it is a **constraint‑driven engineering solution** designed to work where most
“ideal” tools cannot.

The project demonstrates:

*   Practical problem solving
*   Adaptability
*   Real‑world telecom analytics thinking


---


