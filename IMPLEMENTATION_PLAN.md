# Implementation Plan — Dashboard Visualization Improvements

## Project Overview

Comprehensive review and improvement of all Plotly charts in the Dash dashboard. Four tiers: bug fixes, visual polish, new analytics from existing data, and new analytics requiring backend work.

**Primary file**: `src/visualization/plotly_generator.py`
**Palette policy**: Broader than NHS brand (maximally-distinct colors for trust comparisons)
**Constraint**: `python run_dash.py` must work after every task

### What Changes
- `src/visualization/plotly_generator.py` — shared styling constants, bug fixes, new chart functions
- `src/data_processing/pathway_queries.py` — new query functions for Tier 3 analytics
- `dash_app/data/queries.py` — thin wrappers for new queries
- `dash_app/callbacks/chart.py` — heatmap metric toggle, new tab support
- `dash_app/callbacks/trust_comparison.py` — trust color palette, heatmap metric toggle
- `dash_app/components/chart_card.py` — new tab definitions, metric toggle component
- `dash_app/components/trust_comparison.py` — metric toggle component

### What Stays (DO NOT MODIFY)
- Pipeline/analysis logic: `pathway_pipeline.py`, `transforms.py`, `diagnosis_lookup.py`, `pathway_analyzer.py`
- Database schema and `pathway_nodes` table
- CLI refresh command
- Existing callback chain architecture (app-state → chart-data → UI)
- Two-view architecture (Patient Pathways + Trust Comparison)

---

## Phase A: Core Fixes + Shared Constants

### A.1 Extract shared styling constants + `_base_layout()` helper
- [x] Add module-level constants to top of `src/visualization/plotly_generator.py`:
  ```python
  CHART_FONT_FAMILY = "Source Sans 3, system-ui, sans-serif"
  CHART_TITLE_SIZE = 18
  CHART_TITLE_COLOR = "#1E293B"
  GRID_COLOR = "#E2E8F0"
  ANNOTATION_COLOR = "#768692"

  TRUST_PALETTE = [
      "#005EB8", "#DA291C", "#009639", "#ED8B00",
      "#7C2855", "#00A499", "#330072",
  ]

  DRUG_PALETTE = [
      "#005EB8", "#DA291C", "#009639", "#ED8B00", "#7C2855",
      "#00A499", "#330072", "#E06666", "#6FA8DC", "#93C47D",
      "#F6B26B", "#8E7CC3", "#C27BA0", "#76A5AF", "#FFD966",
  ]
  ```
- [x] Create `_base_layout(title, **overrides)` helper returning a dict with shared layout properties (title font, hoverlabel, paper/plot bgcolor, autosize, font family)
- [x] Apply `_base_layout()` to `create_icicle_from_nodes()` as a proof-of-concept (keep all existing behavior, just DRY the layout dict)
- **Checkpoint**: `python run_dash.py` starts, icicle chart unchanged visually

### A.2 Fix heatmap colorscale + cell annotations (Patient Pathways)
- [x] In `create_heatmap_figure()` (~L1189):
  1. Replace non-linear colorscale with linear 5-stop: `[0.0 #E3F2FD, 0.25 #90CAF9, 0.5 #42A5F5, 0.75 #1E88E5, 1.0 #003087]`
  2. Add `text=text_values, texttemplate="%{text}"` with formatted values per metric (patients: `"N"`, cost: `"£Nk"`, cost_pp_pa: `"£N"`)
  3. Set `zmin=0` explicitly
  4. Remove explicit `width`, use `autosize=True`
  5. Replace `l=200` with `l=8` + `yaxis automargin=True`
  6. Add subtitle annotation when 25-drug cap is hit: `"Showing top 25 of N drugs"`
  7. Reduce `xgap/ygap` from 2→1 when >15 columns
- [x] Apply same fixes to `create_trust_heatmap_figure()` (~L1582)
- [x] Apply `_base_layout()` to both heatmap functions
- **Checkpoint**: Heatmaps show linear color gradient, cell text visible, no fixed width overflow

### A.3 Fix legend overflow in 4 charts
- [x] Create `_smart_legend(n_items)` helper that returns legend dict:
  - When >15 items: vertical legend on right (`orientation="v", x=1.02, y=1, xanchor="left"`) with dynamic right margin
  - When ≤15: horizontal legend with dynamic bottom margin based on estimated row count
- [x] Also created `_smart_legend_margin(n_items)` helper returning margin dict with dynamic b/r values
- [x] Apply to `create_market_share_figure()` — also replaced local nhs_colours with DRUG_PALETTE
- [x] Apply to `create_trust_market_share_figure()` — also replaced local nhs_colours with DRUG_PALETTE, fixed Unicode escapes to literal chars
- [x] Apply to `create_dosing_figure()` — replaced local nhs_colours with DRUG_PALETTE, legend adapts to trace count
- [x] Apply to `create_trust_duration_figure()` — replaced local nhs_colours with TRUST_PALETTE, fixed l=200→l=8+automargin
- [x] Apply `_base_layout()` to all 4 functions
- **Checkpoint**: Legends don't overlap chart content with 42 drugs or 7 trusts

### A.4 Fix trust comparison color differentiation
- [x] In `create_trust_duration_figure()`: replace `nhs_colours` list with `TRUST_PALETTE` (done in A.3)
- [x] Add `is_trust_comparison=False` param to `create_cost_waterfall_figure()` — use `TRUST_PALETTE` when True
- [x] Update `tc_cost_waterfall` callback in `dash_app/callbacks/trust_comparison.py` to pass `is_trust_comparison=True`
- [x] Fix `_dosing_by_drug()` blue→blue interpolation: replaced with `plotly.colors.sample_colorscale("Viridis", ...)` for meaningful gradient
- [x] Replace `nhs_colours` in `create_trust_market_share_figure()` with `DRUG_PALETTE` for drug traces (done in A.3)
- [x] Apply `_base_layout()` to all affected functions (done in A.3 for trust_market_share and trust_duration)
- **Checkpoint**: Trust Comparison charts have 7 visually distinct trust colors; dosing has meaningful gradient

---

## Phase B: Visual Polish

### B.1 Fix title inconsistencies across all charts
- [x] Sankey: replaced local nhs_colours with DRUG_PALETTE, title color `"#003087"` → `CHART_TITLE_COLOR` via `_base_layout()`
- [x] Dosing: already converted in A.3 — uses `_base_layout()` with CHART_TITLE_COLOR
- [x] Patient Pathways heatmap: already converted in A.2 — uses `_base_layout()` with CHART_TITLE_COLOR
- [x] Duration: title color `"#003087"` → `CHART_TITLE_COLOR`, fixed l=200→l=8+automargin, used constants for annotations
- [x] All Trust Comparison functions: already use `_base_layout()` (A.2-A.4), title size=18 via CHART_TITLE_SIZE
- [x] Applied `_base_layout()` to all remaining chart functions: Sankey, Cost Effectiveness, Duration
- [x] Cost Effectiveness: replaced 38-line manual layout with `_base_layout()`, hardcoded colors/fonts → constants
- **Checkpoint**: All chart titles use consistent font, size, and color

### B.2 Cost effectiveness smooth gradient
- [x] In `create_cost_effectiveness_figure()`:
  - Replaced 3-bin hard threshold with smooth `_lerp_color()` RGB interpolation
  - Green (#009639) → Amber (#ED8B00) for ratio 0–0.5
  - Amber (#ED8B00) → Red (#DA291C) for ratio 0.5–1.0
- [x] `_base_layout()` already applied in B.1
- **Checkpoint**: Lollipop dots show smooth green→amber→red gradient

### B.3 Sankey narrow-screen fix
- [x] In `create_sankey_figure()` (~L808):
  - Changed `arrangement="snap"` → `arrangement="freeform"`
  - Increased `pad` from 20 → 25
- **Checkpoint**: Sankey nodes don't overlap on narrow viewports

### B.4 Heatmap metric toggle (both views)
- [x] Add `dmc.SegmentedControl` component next to Patient Pathways heatmap:
  - Options: Patients, Cost, Cost p.a.
  - ID: `heatmap-metric-toggle`
  - Added to `dash_app/components/chart_card.py` in header, hidden by default, shown when heatmap tab active
  - Also added "heatmap" tab to TAB_DEFINITIONS (was only in ALL_TAB_DEFINITIONS before)
- [x] Add `dmc.SegmentedControl` next to Trust Comparison heatmap:
  - ID: `tc-heatmap-metric-toggle`
  - Added to `dash_app/components/trust_comparison.py` inline in heatmap chart cell header
- [x] Update `_render_heatmap()` in `dash_app/callbacks/chart.py` to accept metric param, `update_chart` passes toggle value + controls toggle visibility via `heatmap-metric-wrapper` style output
- [x] Update `tc_heatmap` callback in `dash_app/callbacks/trust_comparison.py` to read `tc-heatmap-metric-toggle` value and pass to `create_trust_heatmap_figure()`
- **Checkpoint**: Heatmap metric toggles work in both views, switching between patients/cost/cost_pp_pa

---

## Phase C: New Analytics (Existing Data)

### C.1 Retention funnel chart
- [x] Create `get_retention_funnel()` in `src/data_processing/pathway_queries.py`:
  - Query level 3+ nodes, aggregate patient counts by treatment line depth (level 3=1st drug, 4=2nd, 5=3rd)
  - Return: `[{depth: 1, label: "1st drug", patients: N, pct: 100.0}, ...]`
  - Supports directory/trust filters
- [x] Add thin wrapper in `dash_app/data/queries.py`
- [x] Create `create_retention_funnel_figure(data, title)` in `src/visualization/plotly_generator.py`:
  - Uses `go.Funnel` with NHS blue gradient (#003087 → #1E88E5)
  - Shows absolute patient count + percentage retained as text inside bars
  - Uses `_base_layout()` for consistent styling
- [x] Add "Funnel" tab to `TAB_DEFINITIONS` in `chart_card.py` (4 tabs: Icicle, Sankey, Heatmap, Funnel)
- [x] Add `_render_funnel()` helper and tab dispatch in `dash_app/callbacks/chart.py`
- **Checkpoint**: Funnel tab shows retention by treatment line depth, responds to filters

### C.2 Pathway depth distribution chart
- [x] Create `get_pathway_depth_distribution()` in `src/data_processing/pathway_queries.py`:
  - Aggregate patient counts at level 3 (1-drug), level 4 (2-drug), etc.
  - Subtract child counts to get patients who STOPPED at each depth
  - Return: `[{depth: 1, label: "1 drug only", patients: N, pct: 80.2}, ...]`
- [x] Add thin wrapper in `dash_app/data/queries.py`
- [x] Create `create_pathway_depth_figure(data, title)` in `src/visualization/plotly_generator.py`:
  - Horizontal bar chart with NHS blue gradient by depth
  - Text shows "N (pct%)" inside bars
  - Uses `_base_layout()` for consistent styling
- [x] Add "Depth" tab to `TAB_DEFINITIONS` in `chart_card.py` (5 tabs: Icicle, Sankey, Heatmap, Funnel, Depth)
- [x] Add `_render_depth()` helper and tab dispatch in `dash_app/callbacks/chart.py`
- **Checkpoint**: Depth tab shows patient distribution by treatment line count

### C.3 Duration vs Cost scatter plot
- [x] Create `get_duration_cost_scatter()` in `src/data_processing/pathway_queries.py`:
  - Query level 3 nodes for drug-level data with avg_days and cost_pp_pa
  - Aggregates across trusts using weighted averages
  - Return: `[{drug, directory, avg_days, cost_pp_pa, patients}, ...]`
- [x] Add thin wrapper in `dash_app/data/queries.py`
- [x] Create `create_duration_cost_scatter_figure(data, title)` in `src/visualization/plotly_generator.py`:
  - Scatter: x=avg_days, y=cost_pp_pa, size=patients (global max), color=directory
  - One trace per directory for legend grouping using DRUG_PALETTE
  - Quadrant lines at median values with annotations
  - Hover shows drug name, directory, all values
- [x] Add "Scatter" tab to `TAB_DEFINITIONS` in `chart_card.py` (6 tabs: Icicle, Sankey, Heatmap, Funnel, Depth, Scatter)
- [x] Add `_render_scatter()` helper and tab dispatch in `dash_app/callbacks/chart.py`
- **Checkpoint**: Scatter tab shows drugs by duration vs cost with directorate coloring

### C.4 Drug switching network graph
- [x] Create `get_drug_network()` in pathway_queries.py — undirected edges without ordinal suffixes, node patients from level 3, edge co-occurrence from level 4+
- [x] Add thin wrapper in `dash_app/data/queries.py`
- [x] Create `create_drug_network_figure(data, title)` in `src/visualization/plotly_generator.py`:
  - Circular layout using `go.Scatter` for nodes + individual edge traces as lines
  - Node size = total patients (12–50px), edge width = switching flow (0.5–6px), edge opacity scales with strength
  - `DRUG_PALETTE` for node colors, NHS Blue (`rgba(0,94,184,...)`) for edges
- [x] Added as separate "Network" tab (7th tab: Icicle, Sankey, Heatmap, Funnel, Depth, Scatter, Network)
- [x] Added `_render_network()` helper and dispatch case in `chart.py`
- **Checkpoint**: Network view shows drug switching as a graph alternative to Sankey

---

## Phase D: New Analytics (Backend Work)

### D.1 Temporal trend analysis
- [ ] Design `pathway_trends` table schema in `src/data_processing/schema.py`:
  - Columns: `snapshot_date, chart_type, directory, drug, patients, cost, cost_pp_pa`
  - Stores quarterly aggregates from each refresh
- [ ] Add migration for `pathway_trends` table in `data_processing/reference_data.py`
- [ ] Extend `cli/refresh_pathways.py` to compute and insert trend data after main refresh
- [ ] Create `get_trend_data()` query in `pathway_queries.py`
- [ ] Add thin wrapper in `dash_app/data/queries.py`
- [ ] Create `create_trend_figure(data, title, metric)` in plotly_generator.py:
  - Line chart: x=date, y=metric, one line per drug (or directory)
  - Metric selector: patients / cost / cost_pp_pa
- [ ] Add "Trends" tab to `TAB_DEFINITIONS` in `chart_card.py`
- [ ] Add callback wiring
- **Checkpoint**: Trends tab shows drug usage over time (requires at least 2 refresh cycles for meaningful data)

### D.2 Average administered doses analysis
- [x] Create `get_dosing_distribution()` query in `pathway_queries.py`:
  - Level 3 nodes with parsed `average_administered` JSON (position 0 = avg doses for drug)
  - Aggregates across trusts using weighted averages by patient count
  - Supports directory/trust filters. Returns `[{drug, directory, avg_doses, patients}]`
- [x] Add thin wrapper in `dash_app/data/queries.py`
- [x] Create `create_dosing_distribution_figure(data, title)` in plotly_generator.py:
  - Horizontal bar chart (avg doses per drug, one bar per drug x directory)
  - Colored by directory using DRUG_PALETTE, `_base_layout()` + `_smart_legend()`
  - Dynamic height, patient count in hover
- [x] Add "Doses" tab to TAB_DEFINITIONS (9th tab)
- [x] Add `_render_doses()` helper + dispatch in `chart.py`
- **Checkpoint**: Doses tab shows average administered doses per drug, responds to filters

### D.3 Drug timeline (Gantt chart)
- [x] Create `get_drug_timeline()` query in `pathway_queries.py`:
  - Level 3 nodes with `first_seen`, `last_seen`, `labels`, `value` per drug × directory
  - Aggregates across trusts: MIN(first_seen), MAX(last_seen), SUM(value), weighted avg cost_pp_pa
  - Supports directory/trust filters
- [x] Create `create_drug_timeline_figure(data, title)` in plotly_generator.py:
  - Gantt-style using `go.Bar` (horizontal bars from first_seen to last_seen)
  - One trace per bar, grouped by directory with legend grouping
  - Colored by directory using `DRUG_PALETTE`, patient count as bar text
  - Dynamic height (28px per bar), `_base_layout()` + `_smart_legend()`
- [x] Add "Timeline" tab to `TAB_DEFINITIONS` in `chart_card.py` (8th tab)
- [x] Add `_render_timeline()` helper + dispatch case in `chart.py`
- **Checkpoint**: Timeline tab shows when each drug cohort was active

### D.4 NICE TA compliance dashboard
- [ ] Parse `data/ta-recommendations.xlsx` into a reference table
- [ ] Create schema and migration for TA compliance reference data
- [ ] Create compliance scoring: cross-reference pathway data with TA recommendations
- [ ] Create `create_ta_compliance_figure(data, title)` — traffic-light matrix
- [ ] Add "Compliance" tab or separate Trust Comparison sub-view
- **Checkpoint**: Compliance matrix shows alignment with NICE guidance

---

## Completion Criteria

### Phase A
- [ ] All charts use `_base_layout()` for consistent styling
- [ ] Heatmaps have linear colorscale + cell annotations + autosize
- [ ] Legends don't overflow at any drug/trust count
- [ ] Trust Comparison charts use 7 maximally-distinct colors
- [ ] `python run_dash.py` starts cleanly

### Phase B
- [ ] All chart titles use `CHART_TITLE_SIZE` and `CHART_TITLE_COLOR`
- [ ] Cost effectiveness uses smooth gradient
- [ ] Sankey handles narrow viewports
- [ ] Heatmap metric toggle works in both views
- [ ] `python run_dash.py` starts cleanly

### Phase C
- [ ] Retention funnel renders with real data
- [ ] Pathway depth distribution renders with real data
- [ ] Duration vs cost scatter renders with quadrant lines
- [ ] Drug network graph renders as Sankey alternative
- [ ] All new tabs respond to existing filters
- [ ] `python run_dash.py` starts cleanly

### Phase D
- [ ] Temporal trends show data over time (if >1 refresh cycle)
- [ ] Dose distribution shows box/violin plots
- [ ] Drug timeline shows Gantt-style cohort activity
- [ ] NICE TA compliance matrix shows traffic-light scoring
- [ ] `python run_dash.py` starts cleanly

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `src/visualization/plotly_generator.py` | PRIMARY — all chart generation functions |
| `src/data_processing/pathway_queries.py` | All SQLite query functions |
| `src/data_processing/parsing.py` | HTML/JSON parsing utilities |
| `dash_app/callbacks/chart.py` | Patient Pathways tab dispatch + chart rendering |
| `dash_app/callbacks/trust_comparison.py` | Trust Comparison 6-chart callbacks |
| `dash_app/components/chart_card.py` | Tab definitions + chart card component |
| `dash_app/components/trust_comparison.py` | TC landing + dashboard layout |
| `dash_app/data/queries.py` | Thin wrappers around shared query functions |

## Key Patterns

### plotly_generator.py structure
- Module-level palettes: `TRUST_PALETTE` (7 colors), `DRUG_PALETTE` (15 colors)
- `_base_layout(title, **overrides)` helper for DRY layout dicts
- `_smart_legend(n_items)` helper for adaptive legend positioning
- Each `create_*_figure()` function accepts list-of-dicts, returns `go.Figure`

### Adding a new chart tab (Patient Pathways)
1. Add query function to `src/data_processing/pathway_queries.py`
2. Add thin wrapper to `dash_app/data/queries.py`
3. Add figure function to `src/visualization/plotly_generator.py`
4. Add tab to `TAB_DEFINITIONS` in `dash_app/components/chart_card.py`
5. Add `_render_*()` helper in `dash_app/callbacks/chart.py`
6. Add dispatch case in `update_chart()` callback

### Existing chart functions in plotly_generator.py
- `create_icicle_from_nodes(nodes, title)` — L113
- `create_market_share_figure(data, title)` — L247
- `create_cost_effectiveness_figure(data, retention, title)` — L384
- `create_cost_waterfall_figure(data, title)` — L562
- `create_sankey_figure(data, title)` — L706
- `create_dosing_figure(data, title, group_by)` — L837
- `_dosing_by_drug(data, colours)` — L926
- `_dosing_by_trust(data, colours)` — L1007
- `create_heatmap_figure(data, title, metric)` — L1189
- `create_duration_figure(data, title, show_directory)` — L1329
- `create_trust_market_share_figure(data, title)` — L1481
- `create_trust_heatmap_figure(data, title, metric)` — L1582
- `create_trust_duration_figure(data, title)` — L1689
