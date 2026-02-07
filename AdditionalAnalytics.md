# Additional Analytics Charts — Implementation Plan

## UI Approach: Tabbed Chart Area
Extend existing `chart_card.py` tab bar. Currently has Icicle (active), Sankey (disabled), Timeline (disabled). Replace/extend with new tabs.

## Charts to Build (Priority Order)

### Tab 1: Icicle (existing — no change)

### Tab 2: First-Line Market Share — Horizontal Bar Chart
**What**: % of patients starting on each first-line drug, grouped by directorate or indication
**Data source**: `pathway_nodes WHERE level = 3` (drug level). The `colour` column already holds proportion of parent. `value` = patient count.
**Query**: Filter by `chart_type`, `date_filter_id`, optionally `directory` or `trust_name`. Group by `directory`, then show drugs as bars.
**Viz**: Horizontal grouped bar chart. One cluster per directorate/indication (top N), bars within = drugs, length = % of patients. Sorted by total patients desc. NHS blue palette.
**Interaction**: Responds to all existing filters (date, chart type, trust, drug, directorate). Clicking a directorate cluster could filter the icicle.

### Tab 3: Pathway Cost Effectiveness — Lollipop/Dot Plot
**What**: Compare annualized cost per patient across complete treatment pathways within a directorate/indication. Highlights most vs least cost-effective pathways.
**Data source**: `pathway_nodes WHERE level >= 4` (pathway nodes). Fields: `cost_pp_pa` (annualized), `value` (patient count), `ids` (parse to get pathway sequence), `directory`.
**Calculation**: `cost_pp_pa` is already computed as `(total_cost / patients) * (365 / avg_days)` — this IS the "total cost over N years / N years" the user described.
**Query**: Filter to a specific directorate/indication, then show all pathway variants ranked by `cost_pp_pa`.
**Viz**: Horizontal lollipop chart (dot on stick). Y-axis = pathway label (e.g., "Adalimumab → Secukinumab → Rituximab"), X-axis = £ per patient per annum. Dot size = patient count. Colour gradient: green (cheap) → amber → red (expensive).
**Interaction**: Directorate/indication selector drives which pathways are shown. Could also compare across directorates at the drug level (level 3).

**Bonus metric — "Pathway Retention" (fewest switches)**:
- For each 2nd-line pathway (e.g., "Drug A → Drug B"), calculate what % of patients escalate to a 3rd line
- Derivation: `value("Drug A → Drug B") - SUM(value("Drug A → Drug B → *"))` = patients who stayed on 2nd line
- Show as a secondary annotation or companion chart: "Drug B retains 72% of patients (no 3rd-line switch needed)"
- This identifies the most effective 2nd-line choices

### Tab 4: Cost Waterfall — Waterfall Chart
**What**: Break down £ per patient per annum by directorate, showing relative cost contribution
**Data source**: `pathway_nodes WHERE level = 2` (directorate/indication level). Field: `cost_pp_pa`, `value`.
**Viz**: Plotly waterfall chart. Each bar = one directorate's average cost_pp_pa. Sorted highest to lowest. Running reference line optional. Use NHS colours.
**Note**: User specifically wants cost_pp_pa (annualized), not total cost.
**Interaction**: Responds to chart_type toggle, date filter, trust filter.

### Tab 5: Drug Switching Sankey — Sankey Diagram
**What**: Flow of patients from 1st-line → 2nd-line → 3rd-line drugs
**Data source**: `pathway_nodes WHERE level >= 3`. Parse `ids` to extract drug transition sequences.
**Parsing**: `ids` format at level 4+: `"TRUST - DIRECTORY - DRUG_A - DRUG_A|DRUG_B"`. Split by " - ", take segments from level 3 onwards, split by "|" to get ordered drug list.
**Viz**: Plotly Sankey. Left nodes = 1st-line drugs, middle = 2nd-line, right = 3rd-line. Link width = patient count. Colour by drug or by directorate.
**Interaction**: Filter by directorate/indication to see switching within a specialty. Filter by trust to compare switching patterns.

### Tab 6: Dosing Interval Comparison — Grouped Bar Chart
**What**: Compare average dosing frequency/weekly interval for a drug across trusts or directorates
**Data source**: Level 3+ nodes, `average_spacing` (HTML string), `average_administered` (JSON array)
**Parsing needed**:
  - `average_spacing`: regex to extract weekly interval number from `"given X times with Y weekly interval"`
  - `average_administered`: `json.loads()` to get dose counts
**Viz**: Horizontal grouped bars. Y-axis = trust or directorate, X-axis = weekly interval (or total administrations). One colour per drug if comparing multiple.
**Interaction**: Drug selector to pick which drug to compare. Group-by selector (trust vs directorate).

### Tab 7: Directorate × Drug Heatmap
**What**: Matrix showing which drugs are used in which directorates, cells coloured by patient count or cost_pp_pa
**Data source**: Level 3 nodes, pivot `directory` × drug (parsed from `labels` or `ids`)
**Viz**: Plotly heatmap. Rows = directorates (sorted by total patients), columns = drugs (sorted by frequency). Cell colour = patient count or cost. Hover shows details.
**Interaction**: Toggle between patient count / cost / cost_pp_pa colouring.

### Tab 8: Treatment Duration Bars
**What**: Compare average treatment durations across drugs within a directorate
**Data source**: Level 3 nodes, `avg_days` field
**Viz**: Horizontal bar chart. Y-axis = drug, X-axis = average days. Colour intensity by patient count.
**Interaction**: Directorate filter drives which drugs are shown.

---

## Data Layer Changes

### New query functions needed (in `src/data_processing/pathway_queries.py`):

```python
def get_drug_market_share(db_path, date_filter_id, chart_type, directory=None, trust=None):
    """Level 3 nodes grouped by directory, returning drug, value, colour."""

def get_pathway_costs(db_path, date_filter_id, chart_type, directory=None):
    """Level 4+ nodes with cost_pp_pa, parsed pathway labels, patient counts."""

def get_cost_waterfall(db_path, date_filter_id, chart_type, trust=None):
    """Level 2 nodes with cost_pp_pa per directorate/indication."""

def get_drug_transitions(db_path, date_filter_id, chart_type, directory=None):
    """Level 3+ nodes parsed into source→target drug transitions with patient counts."""

def get_dosing_intervals(db_path, date_filter_id, chart_type, drug=None):
    """Level 3 nodes for a specific drug, parsed average_spacing by trust/directory."""

def get_drug_directory_matrix(db_path, date_filter_id, chart_type):
    """Level 3 nodes pivoted as directory × drug with value/cost metrics."""

def get_treatment_durations(db_path, date_filter_id, chart_type, directory=None):
    """Level 3 nodes with avg_days by drug within a directorate."""
```

### Parsing utilities needed:

```python
def parse_average_spacing(spacing_html: str) -> dict:
    """Extract drug_name, dose_count, weekly_interval, total_weeks from HTML string."""

def parse_pathway_drugs(ids: str, level: int) -> list[str]:
    """Extract ordered drug list from ids column at level 4+."""

def calculate_retention_rate(nodes: list[dict]) -> dict:
    """For each N-drug pathway, calculate % not escalating to N+1 drugs."""
```

---

## Callback Architecture

Each tab gets its own callback triggered by `chart-data` store + `active-tab` state:

```
active-tab change → render selected chart
chart-data change → re-render active chart
```

Only the active tab's chart is computed (lazy rendering). Store the active tab in `app-state`.

New callback per chart type in `dash_app/callbacks/`:
- `market_share.py` — builds bar chart from level 3 data
- `pathway_costs.py` — builds lollipop + retention annotations
- `cost_waterfall.py` — builds waterfall from level 2 data
- `sankey.py` — builds Sankey from parsed transitions
- `dosing.py` — builds grouped bars from parsed spacing
- `heatmap.py` — builds heatmap from pivoted matrix
- `duration.py` — builds bar chart from avg_days

---

## Implementation Order

1. **Data parsing utilities** — shared parsing for spacing, pathway drugs, retention
2. **Query functions** — one per chart type in pathway_queries.py
3. **Tab infrastructure** — extend chart_card.py with all tab labels, lazy rendering
4. **Charts one at a time** (in priority order):
   - First-Line Market Share (simplest, validates the tab pattern)
   - Pathway Cost Effectiveness + Retention (user's key insight)
   - Cost Waterfall
   - Drug Switching Sankey
   - Dosing Interval
   - Heatmap
   - Treatment Duration

---

## Verification

- Run `python run_dash.py` after each chart addition
- Verify each chart responds to filter changes (date, chart type, trust, directorate, drug)
- Test with both "directory" and "indication" chart types
- Verify icicle chart still works correctly (no regressions)
- Check tab switching is smooth with no unnecessary recomputation
