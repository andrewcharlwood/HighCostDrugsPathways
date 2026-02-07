# Implementation Plan — Dashboard Visualization Improvements

## Project Overview

Comprehensive review and improvement of all Plotly charts in the Dash dashboard. Four tiers: bug fixes, visual polish, new analytics from existing data, and new analytics requiring backend work.

**Primary file**: `src/visualization/plotly_generator.py`
**Palette policy**: Broader than NHS brand (maximally-distinct colors for trust comparisons)
**Constraint**: `python run_dash.py` must work after every task

### What Changes
- `src/visualization/plotly_generator.py` — shared styling constants, bug fixes, new chart functions
- `src/data_processing/pathway_queries.py` — new/modified query functions
- `dash_app/data/queries.py` — thin wrappers for new queries
- `dash_app/callbacks/chart.py` — remove Trends tab, fix chart height
- `dash_app/callbacks/trust_comparison.py` — trust color palette, heatmap metric toggle
- `dash_app/callbacks/trends.py` — NEW: Trends view callbacks (directorate overview + drug drill-down)
- `dash_app/callbacks/__init__.py` — register new trends callbacks
- `dash_app/components/chart_card.py` — remove Trends tab, metric toggle cleanup
- `dash_app/components/trust_comparison.py` — metric toggle component
- `dash_app/components/trends.py` — NEW: Trends landing + detail components
- `dash_app/components/sidebar.py` — add Trends nav item
- `dash_app/callbacks/navigation.py` — 3-way view switching
- `dash_app/callbacks/filters.py` — add nav-trends input
- `dash_app/app.py` — add trends-view to layout, add selected_trends_directorate to app-state
- `dash_app/assets/nhs.css` — chart height CSS for responsive sizing

### What Stays (DO NOT MODIFY)
- Pipeline/analysis logic: `pathway_pipeline.py`, `transforms.py`, `diagnosis_lookup.py`, `pathway_analyzer.py`
- Database schema and `pathway_nodes` table
- CLI refresh command and `cli/compute_trends.py`
- Existing callback chain architecture (app-state → chart-data → UI)
- Trust Comparison view (unchanged)

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

### D.1 Temporal trend analysis (historical snapshots approach)
- [x] **D.1a — Create `cli/compute_trends.py` CLI script**:
  - Creates `pathway_trends` table via `CREATE TABLE IF NOT EXISTS` (no schema.py changes):
    ```
    pathway_trends(period_end TEXT, drug TEXT, directory TEXT, patients INTEGER,
                   total_cost REAL, cost_pp_pa REAL, PRIMARY KEY(period_end, drug, directory))
    ```
  - Imports existing `fetch_and_transform_data()` and `process_pathway_for_date_filter()` from `pathway_pipeline.py` — does NOT modify them
  - Fetches all activity data once from Snowflake
  - Loops over 6-month historical endpoints (2021-06-30 through 2025-12-31, ~10 periods)
  - For each endpoint: calls `process_pathway_for_date_filter()` with `max_date=endpoint` using `all_6mo` config
  - Extracts level 3 summary stats (drug, directory, patients, cost, cost_pp_pa) from resulting DataFrame
  - Inserts aggregated rows into `pathway_trends` table
  - Run separately: `python -m cli.compute_trends` (not part of main refresh)
- [x] **D.1b — Add Trends tab to Dash** (standard 6-step pattern):
  1. Create `get_trend_data(db_path, metric, directory, drug)` in `pathway_queries.py` — query `pathway_trends` table, return time-series data
  2. Add thin wrapper in `dash_app/data/queries.py`
  3. Create `create_trend_figure(data, title, metric)` in `plotly_generator.py` — line chart: x=period_end, y=metric, one line per drug (or per directory). Uses `_base_layout()` + `_smart_legend()`. Add `dmc.SegmentedControl` for metric toggle (patients / cost / cost_pp_pa)
  4. Add "Trends" tab to `TAB_DEFINITIONS` in `chart_card.py`
  5. Add `_render_trends()` helper + dispatch case in `chart.py`
  6. Handle empty state: if `pathway_trends` table doesn't exist or is empty, show "Run `python -m cli.compute_trends` to generate trend data" message
- **Checkpoint**: Trends tab shows drug/directory trends over 10 historical periods, responds to filters. Empty state handled gracefully if trends not yet computed.

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


---

## Phase E: Trends View Redesign + Chart Height

### E.1 Remove Trends tab from Patient Pathways
- [x] Remove `("trends", "Trends")` from `TAB_DEFINITIONS` in `dash_app/components/chart_card.py`
- [x] Remove `trends-metric-wrapper` div and `trends-metric-toggle` SegmentedControl from `chart_card.py`
- [x] Remove `_render_trends()` helper from `dash_app/callbacks/chart.py`
- [x] Remove `elif active_tab == "trends"` dispatch case from `update_chart()`
- [x] Remove `Output("trends-metric-wrapper", "style")` and `Input("trends-metric-toggle", "value")` from `update_chart()` callback signature — updated ALL 4 return paths to return 3 values instead of 4
- [x] Remove thin wrapper `get_trend_data()` from `dash_app/data/queries.py` (will be re-imported by the new Trends view callbacks)
- [x] Keep `get_trend_data()` in `pathway_queries.py` — it's still used by the new Trends view
- [x] Keep `create_trend_figure()` in `plotly_generator.py` — it's still used by the new Trends view
- **Checkpoint**: Patient Pathways has 9 tabs (Icicle through Doses, no Trends). `python run_dash.py` starts cleanly. PASSED.

### E.2 Add Trends sidebar nav item + view container
- [ ] Add `"trends"` icon SVG to `_ICONS` dict in `dash_app/components/sidebar.py` — use a line chart icon: `<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>`
- [ ] Add `_sidebar_item("Trends", "trends", active=False, item_id="nav-trends")` to sidebar children
- [ ] Add `html.Div(id="trends-view", style={"display": "none"}, children=[...])` to `app.py` layout inside `view-container`, after `trust-comparison-view`
- [ ] Update `switch_view()` in `dash_app/callbacks/navigation.py`:
  - Add `Output("trends-view", "style")` and `Output("nav-trends", "className")` — now 3 views, 3 nav items (6 outputs total)
  - Handle 3-way switching: `"patient-pathways"`, `"trust-comparison"`, `"trends"`
- [ ] Update `update_app_state()` in `dash_app/callbacks/filters.py`:
  - Add `Input("nav-trends", "n_clicks")`
  - Add `elif triggered_id == "nav-trends": active_view = "trends"` case
- **Checkpoint**: 3 sidebar items visible. Clicking "Trends" switches to empty trends view. `python run_dash.py` starts cleanly.

### E.3 Create Trends landing page — directorate-level trends
- [ ] Create `dash_app/components/trends.py`:
  - `make_trends_landing()` — container with title, description, metric toggle (`dmc.SegmentedControl` id: `trends-view-metric-toggle`, options: Patients / Cost per Patient / Cost per Patient p.a.), and `dcc.Graph(id="trends-overview-chart")` wrapped in `dcc.Loading`
  - `make_trends_detail()` — hidden container with back button (id: `trends-back-btn`), title (id: `trends-detail-title`), same metric toggle, and `dcc.Graph(id="trends-detail-chart")` wrapped in `dcc.Loading`
- [ ] Update `get_trend_data()` in `pathway_queries.py` to support `group_by` parameter:
  - `group_by="drug"` (default, existing behavior): one line per drug
  - `group_by="directory"`: one line per directory (aggregate drugs within each directory)
  - When `group_by="directory"`: `SELECT period_end, directory AS name, SUM(...) ... GROUP BY period_end, directory`
- [ ] Update thin wrapper in `dash_app/data/queries.py` to pass `group_by` param
- [ ] Create `dash_app/callbacks/trends.py` with `register_trends_callbacks(app)`:
  - Callback to render directorate-level chart: Input `app-state` + `trends-view-metric-toggle` → Output `trends-overview-chart` figure. Calls `get_trend_data(group_by="directory", metric=...)` → `create_trend_figure(data, title, metric)`.
  - Only fires when `active_view == "trends"` and `selected_trends_directorate` is None.
- [ ] Register in `dash_app/callbacks/__init__.py`
- [ ] Rename "Cost" label to "Cost per Patient" in the metric toggle options (value stays `total_cost`)
- [ ] Wire `trends-view` div in `app.py` to contain `make_trends_landing()` + `make_trends_detail()`
- **Checkpoint**: Trends view shows directorate-level line chart. Metric toggle switches y-axis. Lines show one per directorate.

### E.4 Add drug drill-down within Trends view
- [ ] Add `selected_trends_directorate` key (default `None`) to `app-state` initial data in `app.py`
- [ ] Add directorate selection callback in `dash_app/callbacks/trends.py`:
  - Clicking a line/trace on the overview chart sets `selected_trends_directorate` in app-state
  - Use `clickData` from `trends-overview-chart` as Input
  - Extract directorate name from the clicked trace's `name` attribute
  - Update `app-state` with `selected_trends_directorate`
- [ ] Add landing/detail toggle callback:
  - Input: `app-state` → show/hide `trends-landing` vs `trends-detail`
  - When `selected_trends_directorate` is set: hide landing, show detail with title "[Directorate] — Drug Trends"
- [ ] Add detail chart callback:
  - Input: `app-state` + `trends-view-metric-toggle` → Output `trends-detail-chart`
  - Calls `get_trend_data(directory=selected, metric=..., group_by="drug")` → `create_trend_figure()`
  - Only fires when `selected_trends_directorate` is not None
- [ ] Add back button callback:
  - Clicking `trends-back-btn` clears `selected_trends_directorate` in app-state → returns to landing
- **Checkpoint**: Click a directorate line → drill into drug-level trends. Back button returns to overview. `python run_dash.py` starts cleanly.

### E.5 Fix chart height to fill viewport
- [ ] In `create_trend_figure()` in `plotly_generator.py`: remove explicit `height=500`, let `autosize=True` (from `_base_layout()`) handle it
- [ ] For ALL Patient Pathways chart functions (icicle, sankey, heatmap, funnel, depth, scatter, network, timeline, doses): review and remove fixed `height=...` values where appropriate. Replace with responsive height:
  - For charts with dynamic height (e.g. `max(400, n_bars * 28 + 150)`): keep the dynamic calculation but ensure minimum is high enough to fill viewport
  - For charts with fixed `height=500`: remove it
- [ ] Add CSS rule to ensure `#pathway-chart .js-plotly-plot, #pathway-chart .plot-container` have `height: 100%` to propagate the flex container height to the Plotly div
- [ ] Verify the existing CSS flex chain propagates correctly: `.chart-card` → `.dash-loading-callback` → `#chart-container` → `#pathway-chart`
- [ ] Rename "Cost" to "Cost per Patient" in any remaining metric toggle labels (heatmap toggles in `chart_card.py` and `trust_comparison.py`)
- **Checkpoint**: Charts fill available viewport height in Patient Pathways. No fixed 500px cutoff. `python run_dash.py` starts cleanly.

---

## Completion Criteria

### Phase A
- [x] All charts use `_base_layout()` for consistent styling
- [x] Heatmaps have linear colorscale + cell annotations + autosize
- [x] Legends don't overflow at any drug/trust count
- [x] Trust Comparison charts use 7 maximally-distinct colors
- [x] `python run_dash.py` starts cleanly

### Phase B
- [x] All chart titles use `CHART_TITLE_SIZE` and `CHART_TITLE_COLOR`
- [x] Cost effectiveness uses smooth gradient
- [x] Sankey handles narrow viewports
- [x] Heatmap metric toggle works in both views
- [x] `python run_dash.py` starts cleanly

### Phase C
- [x] Retention funnel renders with real data
- [x] Pathway depth distribution renders with real data
- [x] Duration vs cost scatter renders with quadrant lines
- [x] Drug network graph renders as Sankey alternative
- [x] All new tabs respond to existing filters
- [x] `python run_dash.py` starts cleanly

### Phase D
- [x] Temporal trends computed via historical snapshots (CLI script + Dash tab)
- [x] Dose distribution shows average administered doses per drug
- [x] Drug timeline shows Gantt-style cohort activity
- [x] `python run_dash.py` starts cleanly

### Phase E
- [ ] Trends tab removed from Patient Pathways (9 tabs remain)
- [ ] 3rd sidebar item "Trends" visible and functional
- [ ] Trends landing page shows directorate-level line chart with metric toggle
- [ ] Clicking a directorate drills into drug-level trends
- [ ] Back button returns to directorate overview
- [ ] Charts fill available viewport height (no fixed 500px cutoff)
- [ ] "Cost" renamed to "Cost per Patient" in metric toggles
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
