# Implementation Plan — Reflex → Dash Migration

## Project Overview

Migrate the Reflex web application to Dash (Plotly) + Dash Mantine Components. The backend (`src/`) is untouched — only the frontend changes.

### What Changes
- `pathways_app/` (Reflex) → `dash_app/` (Dash + DMC)
- `run_dash.py` entry point replaces `reflex run`
- CSS extracted from `01_nhs_classic.html` → `dash_app/assets/nhs.css`
- Drug/Directory/Indication filters consolidated into a right-side `dmc.Drawer`

### What Stays (DO NOT MODIFY pipeline/analysis logic)
- `data_processing/pathway_pipeline.py`, `transforms.py`, `diagnosis_lookup.py` (matching logic)
- `analysis/pathway_analyzer.py`, `statistics.py`
- `cli/refresh_pathways.py`
- `data_processing/schema.py`, `reference_data.py`, `cache.py`, `data_source.py`
- SQLite schema and `pathway_nodes` table
- `data/` reference files (CSVs, pathways.db)

### What CAN be edited in `src/` (shared utilities)
- `visualization/plotly_generator.py` — add/refactor a function to accept list-of-dicts (what Dash produces) instead of only DataFrames
- `data_processing/database.py` — add shared query functions for pathway node loading so both Reflex and Dash use the same queries
- `core/config.py` — if path resolution needs adjusting

### Dash App Structure
```
dash_app/
├── __init__.py
├── app.py                    # Entry point, layout root, dcc.Store components
├── assets/
│   └── nhs.css               # Extracted from 01_nhs_classic.html
├── data/
│   ├── queries.py             # SQLite queries (extracted from Reflex AppState)
│   └── card_browser.py        # DimSearchTerm.csv → directorate tree
├── components/
│   ├── header.py              # Top header bar
│   ├── sidebar.py             # Left navigation
│   ├── kpi_row.py             # 4 KPI cards
│   ├── filter_bar.py          # Chart type toggle + date dropdowns
│   ├── chart_card.py          # Chart area with tabs + dcc.Graph
│   ├── drawer.py              # dmc.Drawer with card browser
│   └── footer.py              # Page footer
├── callbacks/
│   ├── __init__.py            # register_callbacks(app)
│   ├── filters.py             # Date/chart-type → app-state store
│   ├── chart.py               # chart-data → go.Icicle figure
│   ├── drawer.py              # Drawer open/close + drug selection
│   └── kpi.py                 # chart-data → KPI card values
└── utils/
    └── formatting.py          # Cost/patient display formatters
```

### State Management (3 dcc.Store components)
- **app-state** (session): `chart_type`, `initiated`, `last_seen`, `selected_drugs`, `selected_directorates`, `date_filter_id`
- **chart-data** (memory): `nodes[]`, `unique_patients`, `total_drugs`, `total_cost`
- **reference-data** (session): `available_drugs`, `directorate_tree` (loaded once)

### Callback Chain
```
Page Load → load_reference_data → reference-data store
         → load_pathway_data → chart-data store
                              ├→ update_kpis → KPI cards
                              └→ update_chart → dcc.Graph

Filter change → update_app_state → app-state store → load_pathway_data → (chain above)

Drawer selection → update_drug_selection → app-state store → load_pathway_data → (chain above)
```

### Directorate Card Browser (dmc.Drawer)
- Position: right, ~480px wide
- **Top card**: "All Drugs" — flat list from `pathway_nodes` level 3. Pick one drug → see it across all directorates/indications.
- **Below**: Cards per PrimaryDirectorate (from DimSearchTerm.csv). Each has `dmc.Accordion` with indication items → drug chips inside.
- **Clear Filters** button resets all selections.
- Data model: `DimSearchTerm.csv` grouped by PrimaryDirectorate → Search_Term → CleanedDrugName

---

## Phase 0: Project Scaffolding

### 0.1 Create dash_app/ skeleton + update pyproject.toml
- [x] Create `dash_app/` directory with `__init__.py`, `app.py`, subdirectories (`assets/`, `data/`, `components/`, `callbacks/`, `utils/`)
- [x] Create `run_dash.py` at project root (simple `from dash_app.app import app; app.run(debug=True, port=8050)`)
- [x] Update `pyproject.toml`: add `dash>=2.14.0`, `dash-mantine-components>=0.14.0` to dependencies (keep `reflex` temporarily)
- [x] Create minimal `app.py` with `dash.Dash(__name__)`, DMC provider wrapper, and "Hello Dash" placeholder layout
- **Checkpoint**: `python run_dash.py` starts, shows "Hello Dash" at localhost:8050 ✓

### 0.2 Extract CSS from 01_nhs_classic.html into dash_app/assets/nhs.css
- [x] Copy the `<style>` block from `01_nhs_classic.html` (lines 8-314) into `dash_app/assets/nhs.css`
- [x] Add Google Fonts `@import` for Source Sans 3 at top of CSS file
- [x] Remove the mock icicle chart CSS (`.icicle`, `.icicle__row`, `.icicle__cell`, `.lvl-*` classes) — Plotly handles the real chart
- [x] Verify CSS loads by checking browser dev tools when app starts
- **Checkpoint**: `python run_dash.py` loads CSS (check font renders as Source Sans 3) ✓

---

## Phase 1: Data Access Layer

### 1.1 Create shared data access functions
- [x] Add query functions to `src/data_processing/pathway_queries.py`:
  - `load_initial_data(db_path) -> dict` — extracted from `AppState.load_data()` (pathways_app.py lines 407-488): returns `{"available_drugs": [...], "available_directorates": [...], "available_indications": [...], "total_records": int, "last_updated": str}`
  - `load_pathway_nodes(db_path, filter_id, chart_type, selected_drugs=None, selected_directorates=None) -> dict` — extracted from `AppState.load_pathway_data()` (lines 490-642): returns `{"nodes": [...], "unique_patients": int, "total_drugs": int, "total_cost": float, "last_updated": str}`
  - These are plain Python functions that accept `db_path` as a parameter (no Reflex state objects)
- [x] Create thin `dash_app/data/queries.py` that imports and calls the shared functions with the correct `db_path`
- [x] Return plain dicts/lists — JSON-serializable for dcc.Store
- **Checkpoint**: `python -c "from dash_app.data.queries import load_initial_data; print(load_initial_data())"` returns valid data

### 1.2 Build directorate card tree from DimSearchTerm.csv
- [x] Create `dash_app/data/card_browser.py` with:
  - `build_directorate_tree()` → dict structured as `{PrimaryDirectorate: {Search_Term: [drug_fragment, ...]}}`
  - Loads `data/DimSearchTerm.csv`, groups by PrimaryDirectorate → Search_Term → split CleanedDrugName by pipe
  - Applies SEARCH_TERM_MERGE_MAP from `data_processing.diagnosis_lookup` (merge asthma variants)
  - `get_all_drugs()` → sorted flat list of all unique drug labels from `pathway_nodes` level 3
- **Checkpoint**: `python -c "from dash_app.data.card_browser import build_directorate_tree; import json; print(json.dumps(build_directorate_tree(), indent=2))"` returns valid tree ✓

---

## Phase 2: Static Layout

### 2.1 Header + sidebar components
- [x] Create `dash_app/components/header.py` — `make_header()` function returning Dash HTML component
  - NHS logo, title "HCD Analysis", breadcrumb, data freshness indicator (status dot + record count + last updated)
  - Use CSS classes from `nhs.css`: `.top-header`, `.top-header__brand`, `.top-header__logo`, `.top-header__title`, etc.
  - Record count and last updated are `html.Span` with IDs for callback updates: `id="header-record-count"`, `id="header-last-updated"`
- [x] Create `dash_app/components/sidebar.py` — `make_sidebar()` function
  - Navigation items matching 01_nhs_classic.html sidebar (Pathway Overview active, Drug Selection, Trust Selection, Directory Selection, Indications, Cost Analysis, Export Data)
  - SVG icons via data URI img elements (Dash doesn't support inline SVGs natively)
  - "Drug Selection" (`id="sidebar-drug-selection"`) and "Indications" (`id="sidebar-indications"`) items have IDs for drawer callbacks (Phase 4)
  - Footer: "NHS Norfolk & Waveney ICB / High Cost Drugs Programme"
- **Checkpoint**: Components render in browser with correct NHS styling ✓

### 2.2 Main content area: KPI row + filter bar + chart card
- [x] Create `dash_app/components/kpi_row.py` — `make_kpi_row()` function
  - 4 KPI cards: Unique Patients, Drug Types, Total Cost, Indication Match Rate
  - Each card value has an ID for callback updates: `id="kpi-patients"`, `id="kpi-drugs"`, `id="kpi-cost"`, `id="kpi-match"`
  - CSS classes: `.kpi-row`, `.kpi-card`, `.kpi-card__label`, `.kpi-card__value`, `.kpi-card__sub`
- [x] Create `dash_app/components/filter_bar.py` — `make_filter_bar()` function
  - Chart type toggle pills ("By Directory" / "By Indication") — use `html.Button` with `.toggle-pill` CSS
  - Initiated dropdown: All years, Last 2 years, Last 1 year — use `dcc.Dropdown` or `html.Select` with `.filter-select`
  - Last seen dropdown: Last 6 months, Last 12 months
  - NO drug/directorate dropdowns here (those are in the drawer)
  - Component IDs: `id="chart-type-directory"`, `id="chart-type-indication"`, `id="filter-initiated"`, `id="filter-last-seen"`
- [x] Create `dash_app/components/chart_card.py` — `make_chart_card()` function
  - Card header with title + dynamic subtitle (hierarchy label: "Trust → Directorate → Drug → Pathway")
  - Tab row: Icicle (active), Sankey (disabled placeholder), Timeline (disabled placeholder)
  - `dcc.Graph(id="pathway-chart")` filling the card body
  - CSS classes: `.chart-card`, `.chart-card__header`, `.chart-card__tabs`, `.chart-tab`
- **Checkpoint**: All three components render with correct layout and styling

### 2.3 Footer + full page assembly
- [x] Create `dash_app/components/footer.py` — `make_footer()` function
  - CSS class `.page-footer`, same text as 01_nhs_classic.html
- [x] Update `dash_app/app.py` to assemble full page layout:
  - `dmc.MantineProvider(children=[header, sidebar, main_content])`
  - Main content: KPI row → filter bar → chart card → footer
  - Add 3 `dcc.Store` components: `id="app-state"`, `id="chart-data"`, `id="reference-data"`
  - Wrap main content in `html.Main(className="main")`
- **Checkpoint**: Full page renders at localhost:8050, layout matches 01_nhs_classic.html visually

---

## Phase 3: Core Callbacks

### 3.1 Reference data loading + filter state management
- [x] Create `dash_app/callbacks/filters.py`:
  - `load_reference_data` callback: fires on page load, calls `queries.load_initial_data()`, populates `reference-data` store + header indicators
  - `update_app_state` callback: fires when chart-type toggle or date dropdowns change, computes `date_filter_id` (e.g., `"all_6mo"`), updates `app-state` store
  - Chart type toggle: use `callback_context` to determine which button was clicked, set active class via `className`
- [x] Create `dash_app/callbacks/__init__.py` with `register_callbacks(app)` that imports and registers all callback modules
- [x] Wire `register_callbacks(app)` in `app.py`
- **Checkpoint**: Page loads reference data, filter dropdowns update app-state store (verify via browser dev tools → dcc.Store)

### 3.2 Pathway data loading callback
- [x] Create `dash_app/callbacks/chart.py` (or add to filters.py):
  - `load_pathway_data` callback: Input=`app-state` store, Output=`chart-data` store
  - Calls `queries.load_pathway_data(filter_id, chart_type, selected_drugs, selected_directorates)`
  - Runs on page load AND whenever `app-state` changes
- **Checkpoint**: Changing date filter updates chart-data store with new pathway nodes ✓

### 3.3 KPI update callback
- [x] Create `dash_app/callbacks/kpi.py`:
  - `update_kpis` callback: Input=`chart-data` store, Output=KPI card values (4 outputs)
  - Extracts `unique_patients`, `total_drugs`, `total_cost` from chart-data
  - Formats numbers: patients with commas, cost as "£XXX.XM", drugs as plain number
- **Checkpoint**: KPIs update when date filters change

### 3.4 Icicle chart rendering callback
- [x] Add a `create_icicle_from_nodes(nodes: list[dict], title: str) -> go.Figure` function to `src/visualization/plotly_generator.py`:
  - Accepts list-of-dicts (the format stored in `chart-data` dcc.Store / returned by `load_pathway_data`)
  - Same 10-field customdata, colorscale, texttemplate, hovertemplate as the existing Reflex `icicle_figure` (pathways_app.py lines 769-920)
  - The existing `create_icicle_figure(ice_df)` stays untouched — the new function is an additional entry point for dict-based data
  - Use the NHS blue gradient colorscale from the Reflex version: `[[0.0, "#003087"], [0.25, "#0066CC"], ...]`
- [x] Add to `dash_app/callbacks/chart.py`:
  - `update_chart` callback: Input=`chart-data` store, Output=`pathway-chart` figure
  - Calls `create_icicle_from_nodes(chart_data["nodes"], title)` from the shared visualization module
  - Dynamic title based on chart type and filters
- **Checkpoint**: Real icicle chart renders with SQLite data, filters change the chart, hover shows full statistics

---

## Phase 4: Directorate Card Browser

### 4.1 dmc.Drawer layout
- [x] Create `dash_app/components/drawer.py` — `make_drawer()` function:
  - `dmc.Drawer(id="drug-drawer", position="right", size="480px")`
  - **Top section**: "All Drugs" card — flat alphabetical list of all drug names from pathway_nodes level 3
    - Each drug as a `dmc.Chip` or clickable badge, ID pattern: `{"type": "drug-chip", "index": drug_name}`
  - **Below**: One `dmc.Card` per PrimaryDirectorate from DimSearchTerm.csv
    - Card title = PrimaryDirectorate name
    - Inside: `dmc.Accordion` with one item per Search_Term (indication)
    - Inside each accordion item: drug fragment chips
  - **Bottom**: `dmc.Button("Clear Filters", id="clear-drug-filters")` — full width
- **Checkpoint**: Drawer opens with correct layout, all directorates and drugs visible

### 4.2 Drawer callbacks
- [x] Create `dash_app/callbacks/drawer.py`:
  - Open/close drawer: sidebar "Drug Selection" or "Indications" click → open drawer
  - Drug selection: ChipGroup value change → app-state.selected_drugs via update_app_state
  - Drug fragment click: pattern-matching badge clicks → substring match → update chip selection
  - Clear filters: resets chip selection → app-state.selected_drugs empties
  - Fragment matching uses `drug.upper() in fragment.upper()` for substring match
  - Toggle behavior: clicking already-selected fragment deselects matching drugs
- **Checkpoint**: Select drug from drawer → chart filters to show that drug → clear resets

---

## Phase 5: Polish & Cleanup

### 5.1 Trust selection
- [x] Add trust selection either:
  - In the dmc.Drawer as a "Trusts" section (preferred — keeps all filters in one place), OR
  - As sidebar checkboxes
- [x] Wire trust selection to `selected_trusts` in `app-state` → pathway data reload
- **Checkpoint**: Selecting trusts filters the chart correctly

### 5.2 Loading/error/empty states + dynamic hierarchy label
- [x] Add `dcc.Loading` wrapper around chart area
- [x] Show "No data" message when chart-data is empty
- [x] Show error feedback when database query fails
- [x] Dynamic chart subtitle: "Trust → Directorate → Drug → Pathway" or "Trust → Indication → Drug → Pathway" based on chart type (done in Task 3.4)
- **Checkpoint**: Loading spinner appears during data fetch, empty state shows message

### 5.3 Data freshness indicator
- [x] Header shows: green dot + "{N} patients" + "Last updated: {relative_time}"
- [x] Pull from `pathway_refresh_log` via `queries.load_initial_data()` (uses total_patients from root node as fallback when source_row_count is 0)
- [x] Format as relative time (e.g., "2h ago", "yesterday")
- **Checkpoint**: Header shows correct data freshness

### 5.4 Remove Reflex + final validation
- [x] Remove `reflex` from `pyproject.toml` dependencies
- [x] Delete or archive `pathways_app/` directory (move to `archive/`)
- [x] Delete `pathways_app/styles.py` and any Reflex-specific files
- [x] Update project `CLAUDE.md` to document Dash app structure, new run command, callback architecture
- [x] Verify: `python run_dash.py` starts cleanly, full end-to-end workflow works
- [x] Verify: No Reflex imports anywhere in `dash_app/`
- **Checkpoint**: Full application works, no Reflex remnants, CLAUDE.md updated



## Phase 6: Update all documentation
- [x] Remove `reflex` references from all documentation
- [x] Verify: No Reflex mentions of reflex in any md files (archive/ excluded — historical)
- [x] Add documentation in readme re how to run dash app
- [x] Update all claude.md files (CLAUDE.md was updated in Task 5.4)
- **Checkpoint**: Full application works, no Reflex remnants, CLAUDE.md updated
---

---

## Phase 7: Bug Fixes & UI Restructure

### 7.1 Fix duplicate component ID error on first load
- [x] **Bug**: `DuplicateIdError` for `{"index":"CARDIOLOGY|RIVAROXABAN","type":"drug-fragment"}` on first page load (works on refresh)
- [x] **Root cause**: Same drug fragment (e.g. RIVAROXABAN) appears under multiple indications within the same directorate in DimSearchTerm.csv. The `{"type": "drug-fragment", "index": f"{directorate}|{frag}"}` ID in `drawer.py:66` is keyed by directorate+fragment, NOT directorate+indication+fragment. So if CARDIOLOGY has RIVAROXABAN under both "acute coronary syndrome" and "atrial fibrillation", two badges get the same ID.
- [x] **Fix**: Changed badge ID to include search_term: `f"{directorate}|{search_term}|{frag}"`. Updated callback to use `rsplit("|", 1)[-1]` to extract the fragment from the 3-part key.
- [x] **Also investigate**: First-load-only failure was because Dash validates layout IDs on initial render but `suppress_callback_exceptions=True` only suppresses callback-related ID checks, not layout duplication checks. After refresh, session store may short-circuit the check.
- **Checkpoint**: `python run_dash.py` starts, first page load has no DuplicateIdError, drawer still works.

### 7.2 Fix drug filter breaking the icicle chart ("multiple implied roots")
- [x] **Bug**: Selecting a drug from the All Drugs chip list makes the chart go blank. Console error: `WARN: Multiple implied roots, cannot build icicle hierarchy of trace 0. These roots include: N&WICS - NORFOLK AND NORWICH... - RHEUMATOLOGY, ...RHEUMATOLOGY - RITUXIMAB, ...RHEUMATOLOGY - ADALIMUMAB - RITUXIMAB`
- [x] **Root cause**: The drug filter in `pathway_queries.py:load_pathway_nodes()` uses `drug_sequence LIKE %DRUG%` which returns drug-level and pathway-level nodes, but drops ancestor nodes (root, trust, directory levels 0-2) that have `drug_sequence = ''` (empty string, not NULL). The `OR drug_sequence IS NULL` check doesn't match empty strings. Same bug existed for directorate filter (`directory = ''` at levels 0-1).
- [x] **Fix**: Restructured WHERE clauses to use level-based gating: drug filter now uses `(level < 3 OR drug_sequence LIKE ...)` so levels 0-2 are always included. Directorate filter now uses `(level < 2 OR directory IN (...) OR directory IS NULL OR directory = '')` so levels 0-1 are always included. Trust filter was already correct (had `OR trust_name = ''`).
- [x] **Note**: Trust filter was OK. Drug and directorate filters both had the bug. Both fixed.
- [x] Verify: select a single drug → chart renders correctly with trust→directory→drug→pathway hierarchy intact. Select multiple drugs → works. Clear → full chart returns.
- **Checkpoint**: Drug selection filters chart without "multiple implied roots" error.

### 7.3 Restructure sidebar: move chart views to sidebar, remove placeholder items
- [x] **Remove** from sidebar: "Cost Analysis" and "Export Data" items (no functionality behind them)
- [x] **Remove** from sidebar: "Drug Selection", "Trust Selection", "Directory Selection", "Indications" items (filters moving to top bar — see 7.5)
- [x] **Add** to sidebar: chart view buttons — "Icicle Chart" (active), "Sankey Diagram" (disabled), "Timeline" (disabled). These replace the tab row currently in chart_card.py.
- [x] **Keep**: "Pathway Overview" as the top active item
- [x] Update sidebar IDs and callback wiring. The chart type toggle pills (By Directory / By Indication) stay in the filter bar — they're data filters, not view selectors.
- [x] Remove the tab row from `chart_card.py` since chart view selection moves to sidebar
- **Checkpoint**: Sidebar shows chart view options, no placeholder items, app runs without errors.

### 7.4 Replace dmc.Drawer with dmc.Modal for filter selection
- [x] **Problem**: The single dmc.Drawer with drugs + trusts + directorates requires excessive scrolling and is confusing (multiple sidebar buttons all open the same drawer)
- [x] **Solution**: Replace `dmc.Drawer` with `dmc.Modal` dialogs. Create separate modals:
  - Drug Selection modal (contains the All Drugs ChipGroup)
  - Trust Selection modal (contains the Trust ChipGroup)
  - Directorate Browser modal (contains the nested directorate accordion with indication sub-items and drug fragment badges)
- [x] Each modal is opened by its corresponding button in the filter bar (see 7.5)
- [x] Modals should be appropriately sized (`size="lg"` or `size="xl"`) and use `dmc.Modal` with `centered=True`
- [x] Preserve all existing selection logic: ChipGroup values, fragment matching, clear button
- [x] Consider having a shared "Clear All Filters" mechanism accessible from each modal or from the filter bar
- [x] Delete `dash_app/components/drawer.py` after modals are working, or refactor it into a `modals.py`
- [x] **Use the frontend-developer agent** to determine optimal modal layout, sizing, and UX patterns. The agent should review the data shapes (42 drugs, 7 trusts, 19 directorates × 163 indications) and recommend the best modal organization.
- **Checkpoint**: Each filter has its own modal, selection works, no excessive scrolling, chart updates correctly.

### 7.5 Move filter triggers to the top filter bar
- [x] **Problem**: Filter buttons are in the sidebar, which should be for navigation/views, not filters. Filters should be in the persistent top filter bar.
- [x] **Add** to the filter bar (alongside existing chart-type toggle and date dropdowns):
  - "Drugs" button that opens the Drug Selection modal (show count badge when drugs are selected, e.g. "Drugs (3)")
  - "Trusts" button that opens the Trust Selection modal (show count badge)
  - "Directorates" button that opens the Directorate Browser modal (show count badge)
  - "Clear All" button to reset all filter selections
- [x] The filter bar should remain static across all chart views (icicle, sankey, timeline) — it's the global filter control
- [x] Update callback wiring: filter bar buttons → open corresponding modal; modal selections → app-state → chart-data → chart
- [x] Remove drawer-related sidebar callbacks (`open_drawer` in `dash_app/callbacks/drawer.py`)
- **Checkpoint**: Filter bar has drug/trust/directorate buttons with count badges, each opens correct modal, filter bar is visible across all views.


## 8 - Additional notes
-  [x] When filtering drugs, ensure that any 2nd levels (e.g., directorate) with no children is hidden. For example, if Immunoglobulin is filtered, then directorates with no pathways such ar ophthalmology are hidden.
- [x] ensure filters update the KPI cards at the top to reflect the icicle chart visible
---

## Phase 9: Additional Analytics Charts

### Design Approach
- Replace sidebar chart view selection with a **tab bar inside `chart_card.py`**
- Each tab renders its chart in the same `dcc.Graph` area
- Only the active tab's chart is computed (lazy rendering)
- Store `active_tab` in `app-state` (default: "icicle")
- All new charts respond to existing filters (date, chart type, trust, drug, directorate)
- New query functions go in `src/data_processing/pathway_queries.py` (shared, not in dash_app/)
- New parsing utilities go in `src/data_processing/pathway_queries.py` (or a new `parsing.py` if large)
- New figure-building functions go in `src/visualization/` (shared, callable from Dash callbacks)
- New callback files in `dash_app/callbacks/` — one per chart type

### 9.1 Parsing utilities + tab infrastructure
- [x] Create parsing utility functions (in new `src/data_processing/parsing.py`):
  - `parse_average_spacing(spacing_html: str) -> list[dict]` — extract drug_name, dose_count, weekly_interval, total_weeks from HTML string
  - `parse_pathway_drugs(ids: str, level: int) -> list[str]` — extract ordered drug list from ids column at level 4+
  - `calculate_retention_rate(nodes: list[dict]) -> dict` — for each N-drug pathway, calculate % not escalating to N+1 drugs
- [x] Update `dash_app/components/chart_card.py`:
  - Add tab bar with 8 tabs: Icicle, Market Share, Cost Effectiveness, Cost Waterfall, Sankey, Dosing, Heatmap, Duration
  - Plain HTML buttons with existing `.chart-tab` / `.chart-tab--active` CSS classes
  - Single `dcc.Graph` shared across all tabs (lazy rendering)
  - `active_tab` stored in separate `dcc.Store(id="active-tab")`
- [x] Update `dash_app/components/sidebar.py`:
  - Remove "Chart Views" section (Icicle/Sankey/Timeline items) — chart selection moves to tab bar
  - Keep "Overview" section with "Pathway Overview"
- [x] Update `dash_app/callbacks/chart.py`:
  - Tab switching callback: 8 tab button Inputs → `active-tab` store + CSS class Outputs
  - `update_chart` checks `active-tab` store and dispatches to correct figure builder
  - Icicle renders normally; other tabs show "coming soon" placeholder
- **Checkpoint**: App starts, tab bar renders with all 8 tabs, icicle tab still works, other tabs show placeholder "Coming soon" messages ✓

### 9.2 Query functions for all chart types
- [x] Add to `src/data_processing/pathway_queries.py`:
  - `get_drug_market_share(db_path, date_filter_id, chart_type, directory=None, trust=None)` — Level 3 nodes grouped by directory, returning drug, value, colour
  - `get_pathway_costs(db_path, date_filter_id, chart_type, directory=None)` — Level 4+ nodes with cost_pp_pa, parsed pathway labels, patient counts
  - `get_cost_waterfall(db_path, date_filter_id, chart_type, trust=None)` — Level 2 nodes with cost_pp_pa per directorate/indication
  - `get_drug_transitions(db_path, date_filter_id, chart_type, directory=None)` — Level 3+ nodes parsed into source→target drug transitions with patient counts
  - `get_dosing_intervals(db_path, date_filter_id, chart_type, drug=None)` — Level 3 nodes for a specific drug, parsed average_spacing by trust/directory
  - `get_drug_directory_matrix(db_path, date_filter_id, chart_type)` — Level 3 nodes pivoted as directory × drug with value/cost metrics
  - `get_treatment_durations(db_path, date_filter_id, chart_type, directory=None)` — Level 3 nodes with avg_days by drug within a directorate
- [x] Add thin wrappers in `dash_app/data/queries.py` for each new function (resolve DB_PATH and delegate)
- **Checkpoint**: All 7 query functions return correct data via manual Python tests (`python -c "..."`) ✓

### 9.3 First-Line Market Share chart (Tab 2)
- [x] Create market share chart rendering:
  - Build horizontal stacked bar chart from `get_drug_market_share()` data
  - One cluster per directorate/indication (sorted by total patients desc), bars = drugs, length = % of patients
  - NHS colour palette, stacked bars with hover showing patients, share, cost, cost_pp_pa
  - Responds to all existing filters (date, chart type, trust, directorate)
- [x] Create figure function in `src/visualization/plotly_generator.py` — `create_market_share_figure(data, title)`
- [x] Wire into tab switching in `update_chart` callback via `_render_market_share()` helper
- **Checkpoint**: Market Share tab renders real data, responds to filters, icicle still works

### 9.4 Pathway Cost Effectiveness chart (Tab 3)
- [x] Create `dash_app/callbacks/pathway_costs.py`:
  - Build horizontal lollipop chart from `get_pathway_costs()` data
  - Y-axis = pathway label (e.g., "Adalimumab → Secukinumab → Rituximab"), X-axis = £ per patient per annum
  - Dot size = patient count, colour gradient: green (cheap) → amber → red (expensive)
  - Uses `parse_pathway_drugs()` to extract pathway labels
- [x] Add retention rate annotations using `calculate_retention_rate()`
  - Show as secondary annotation: "Drug B retains 72% of patients"
- [x] Create figure function in `src/visualization/`
- [x] Wire into tab switching
- **Checkpoint**: Cost Effectiveness tab renders with lollipop dots and retention annotations ✓

### 9.5 Cost Waterfall chart (Tab 4)
- [x] Create `dash_app/callbacks/cost_waterfall.py`:
  - Build Plotly waterfall chart from `get_cost_waterfall()` data
  - Each bar = one directorate's average cost_pp_pa, sorted highest to lowest
  - NHS colours, responds to chart_type toggle, date filter, trust filter
- [x] Create figure function in `src/visualization/`
- [x] Wire into tab switching
- **Checkpoint**: Cost Waterfall tab renders real data, responds to filters ✓

### 9.6 Drug Switching Sankey chart (Tab 5)
- [x] Create `dash_app/callbacks/sankey.py`:
  - Build Plotly Sankey diagram from `get_drug_transitions()` data
  - Left nodes = 1st-line drugs, middle = 2nd-line, right = 3rd-line
  - Link width = patient count, colour by drug or directorate
  - Uses `parse_pathway_drugs()` to extract drug transitions from `ids` column
- [x] Create figure function in `src/visualization/`
- [x] Wire into tab switching
- **Checkpoint**: Sankey tab renders real drug transition flows ✓

### 9.7 Dosing Interval Comparison chart (Tab 6)
- [x] Create `dash_app/callbacks/dosing.py`:
  - Build horizontal grouped bar chart from `get_dosing_intervals()` data
  - Uses `parse_average_spacing()` to extract weekly interval numbers
  - Y-axis = trust or directorate, X-axis = weekly interval
- [x] Create figure function in `src/visualization/`
- [x] Wire into tab switching
- **Checkpoint**: Dosing tab renders real data with parsed interval numbers ✓

### 9.8 Directorate × Drug Heatmap chart (Tab 7)
- [x] Create `dash_app/callbacks/heatmap.py`:
  - Build Plotly heatmap from `get_drug_directory_matrix()` data
  - Rows = directorates (sorted by total patients), columns = drugs (sorted by frequency)
  - Cell colour = patient count or cost, hover shows details
  - Toggle between patient count / cost / cost_pp_pa colouring (additional control in tab)
- [x] Create figure function in `src/visualization/`
- [x] Wire into tab switching
- **Checkpoint**: Heatmap tab renders matrix with correct colour mapping ✓

### 9.9 Treatment Duration chart (Tab 8)
- [x] Create `dash_app/callbacks/duration.py`:
  - Build horizontal bar chart from `get_treatment_durations()` data
  - Y-axis = drug, X-axis = average days, colour intensity by patient count
  - Directorate filter drives which drugs are shown
- [x] Create figure function in `src/visualization/`
- [x] Wire into tab switching
- **Checkpoint**: Duration tab renders real data, responds to directorate filter

### 9.10 Final integration + polish
- [x] Verify all 8 tabs switch smoothly with no unnecessary recomputation
- [x] Verify each chart responds to filter changes (date, chart type, trust, directorate, drug)
- [x] Test with both "directory" and "indication" chart types
- [x] Verify icicle chart still works correctly (no regressions)
- [x] Update CLAUDE.md with new chart types, callback files, and query functions
- **Checkpoint**: All tabs work, all filters work, no regressions, documentation updated ✓

---

## Phase 10: Two-View Architecture + Header Redesign

### Context
Phase 9 delivered 8 chart tabs in a single view. User feedback: comparing drugs across directorates is "apples and oranges" — e.g., Remicade (ophthalmology) vs Adalimumab (multi-directorate) isn't useful. The new architecture splits charts into two views with distinct perspectives:
- **Patient Pathways**: Pathway-focused analysis (Icicle + Sankey) with drug/trust/directorate filters
- **Trust Comparison**: Per-directorate analysis comparing drugs across trusts (6 charts for a selected directorate)

Additionally: KPI row removed, fraction KPIs moved to header, global filter sub-header added.

### 10.1 Design consultation via frontend-design skill
- [x] Use the `/frontend-design` skill to design the following layouts:
  1. **Header redesign**: Fraction KPIs (X/X patients, X/X drugs, £X/£X cost) integrated into the header bar. Data freshness info stays right. Title stays left.
  2. **Global filter sub-header**: Date filter dropdowns (Initiated, Last Seen) + chart type toggle pills (By Directory / By Indication). Styled as a prominent, permanent fixture directly below the main blue header — visually distinct (semi-light blue or similar). Constant across both views.
  3. **Trust Comparison landing page**: ~14 directorate buttons (or ~32 indication buttons when "By Indication" active). Clickable cards/buttons that lead to the 6-chart dashboard for that directorate.
  4. **Trust Comparison 6-chart dashboard**: Market Share, Cost Waterfall, Dosing, Heatmap, Duration, Cost Effectiveness — all for one selected directorate, comparing drugs across trusts. Layout optimized for 6 charts on one screen.
  5. **Patient Pathways filter placement**: Drug/trust/directorate filter buttons (only visible on Patient Pathways, not Trust Comparison). Design appropriate placement — could be inline with content, or in a secondary bar.
- [x] Capture design decisions (component structure, CSS classes, layout approach) for subsequent tasks
- **Checkpoint**: Design mockups/specifications ready for all 5 areas above

### 10.2 State management + sidebar restructure
- [x] Add `active_view` to `app-state`: `"patient-pathways"` (default) or `"trust-comparison"`
- [x] Add `selected_comparison_directorate` to `app-state`: `null` (landing page) or directorate name
- [x] Update `dash_app/components/sidebar.py`:
  - Rename "Pathway Overview" → "Patient Pathways"
  - Add "Trust Comparison" nav item below it
  - Active state tracks `active_view`
- [x] Add callback: sidebar clicks → update `active_view` in app-state
- [x] Main content area switches between Patient Pathways view and Trust Comparison view based on `active_view`
- [x] Date filter + chart type toggle remain in global sub-header (visible in both views)
- **Checkpoint**: Sidebar switches between two views, active state highlights correctly, app starts without errors ✓

### 10.3 Header redesign — remove KPI row, add fraction KPIs
- [x] Remove `dash_app/components/kpi_row.py` (or gut it)
- [x] Remove KPI row from `app.py` layout
- [x] Update `dash_app/components/header.py`:
  - Add fraction KPI display: "X / X patients", "X / X drugs", "£X / £X cost"
  - Numerator = filtered values (from chart-data store), denominator = global totals (from reference-data store)
  - Position: right side of header, alongside existing data freshness indicator
  - Remove indication match rate KPI entirely
- [x] Update header callbacks to receive both filtered and total values
- [x] Update CSS in `dash_app/assets/nhs.css` for new header layout
- [x] Apply design from 10.1
- **Checkpoint**: Header shows fraction KPIs, KPI row is gone, header looks clean with design from 10.1 ✓

### 10.4 Global filter sub-header bar
- [x] Extract date filter dropdowns + chart type toggle from `filter_bar.py` into a new sub-header component (or restyle existing filter_bar)
- [x] Style as a prominent bar directly below the main header — visually distinct per design from 10.1
- [x] Remove drug/trust/directorate filter buttons from this bar (they move to Patient Pathways view only — see 10.7)
- [x] Ensure sub-header is constant across both views (Patient Pathways and Trust Comparison)
- [x] Date filter and chart type toggle changes update `app-state` globally (triggering updates in whichever view is active)
- [x] Update CSS per design from 10.1
- **Checkpoint**: Global sub-header renders below main header, date/chart-type controls work, visible in both views ✓

### 10.5 Patient Pathways view — reduce to Icicle + Sankey
- [x] Create a Patient Pathways view component (or update chart_card.py) with only 2 tabs: Icicle, Sankey
- [x] Remove Market Share, Cost Waterfall, Dosing, Heatmap, Duration, Cost Effectiveness from this view's tab bar
- [x] Existing filter → chart-data → chart callback pipeline stays for these 2 tabs
- [x] This view is shown when `active_view == "patient-pathways"`
- **Checkpoint**: Patient Pathways shows only Icicle + Sankey tabs, both still work with all existing filters

### 10.6 Trust Comparison query functions
- [ ] Add new/modified query functions to `src/data_processing/pathway_queries.py` for per-trust-within-directorate perspective:
  - `get_trust_market_share(db_path, filter_id, chart_type, directory)` — drugs by trust within a single directorate (stacked bars per trust instead of per directorate)
  - `get_trust_cost_waterfall(db_path, filter_id, chart_type, directory)` — one bar per trust showing cost_pp within that directorate
  - `get_trust_dosing(db_path, filter_id, chart_type, directory)` — drug dosing intervals broken down by trust within a directorate
  - `get_trust_heatmap(db_path, filter_id, chart_type, directory)` — trust × drug matrix for one directorate (rows=trusts, cols=drugs)
  - `get_trust_durations(db_path, filter_id, chart_type, directory)` — drug durations by trust within a directorate
  - `get_directorate_pathway_costs(db_path, filter_id, chart_type, directory)` — pathway costs filtered to one directorate (same as existing `get_pathway_costs` with directory param, but verify it works correctly)
- [ ] Add thin wrappers in `dash_app/data/queries.py`
- [ ] Verify all queries return correct data for both "directory" and "indication" chart types
- **Checkpoint**: All 6 query functions return correct per-trust data for sample directorates

### 10.7 Trust Comparison landing page + directorate selector
- [ ] Create Trust Comparison view component with two states:
  - **Landing**: Grid of directorate/indication buttons (source: reference-data store)
  - **Dashboard**: 6-chart layout for selected directorate (see 10.8)
- [ ] Directorate buttons: ~14 for "By Directory" mode, ~32 for "By Indication" mode (from chart type toggle)
- [ ] Clicking a button sets `selected_comparison_directorate` in app-state, switching to dashboard view
- [ ] Back button to return to landing page (clears `selected_comparison_directorate`)
- [ ] Apply layout design from 10.1
- [ ] This view is shown when `active_view == "trust-comparison"`
- **Checkpoint**: Landing page shows directorate buttons, clicking one transitions to dashboard state, back button works

### 10.8 Trust Comparison 6-chart dashboard
- [ ] Build 6-chart dashboard layout per design from 10.1
- [ ] All 6 charts scoped to the selected directorate:
  1. **Market Share**: Drug breakdown per trust (using `get_trust_market_share`)
  2. **Cost Waterfall**: Per-trust cost within directorate (using `get_trust_cost_waterfall`)
  3. **Dosing**: Drug dosing intervals by trust (using `get_trust_dosing`)
  4. **Heatmap**: Trust × drug matrix (using `get_trust_heatmap`)
  5. **Duration**: Drug durations by trust (using `get_trust_durations`)
  6. **Cost Effectiveness**: Pathway costs within directorate, NOT split by trust (using `get_directorate_pathway_costs`)
- [ ] Create new visualization functions in `src/visualization/plotly_generator.py` where existing ones don't fit the trust-comparison perspective (may need `create_trust_market_share_figure`, `create_trust_heatmap_figure`, etc., or parameterize existing functions)
- [ ] All 6 charts respond to date filter and chart type toggle (global filters)
- [ ] Dashboard title shows selected directorate name
- [ ] Use `dcc.Loading` wrappers for each chart
- **Checkpoint**: All 6 charts render for a selected directorate, comparing drugs across trusts. Charts update when date filter or chart type changes.

### 10.9 Patient Pathways filter relocation
- [ ] Drug/trust/directorate filter buttons (with count badges) only visible when on Patient Pathways view
- [ ] Hidden when on Trust Comparison view
- [ ] Placement per design from 10.1 (could be below the global sub-header, or inline with Patient Pathways content)
- [ ] Filter modals still work as before (drug modal, trust modal, directorate modal)
- [ ] "Clear All Filters" still works
- **Checkpoint**: Filters visible on Patient Pathways, hidden on Trust Comparison, all filter functionality preserved

### 10.10 CSS updates + polish
- [ ] Global filter sub-header styling per design from 10.1
- [ ] Trust Comparison landing page styling (directorate buttons grid)
- [ ] Trust Comparison dashboard grid styling (6-chart layout)
- [ ] Header fraction KPI styling
- [ ] Remove or repurpose `.kpi-row` / `.kpi-card` CSS
- [ ] Ensure responsive behavior
- [ ] Update `01_nhs_classic.html` if it serves as an ongoing design reference (or note that Phase 10 diverges)
- **Checkpoint**: All new components styled consistently with NHS design system

### 10.11 Final integration + documentation
- [ ] Verify all views work: Patient Pathways (Icicle + Sankey), Trust Comparison (landing + 6-chart dashboard)
- [ ] Verify global filters (date, chart type) affect both views
- [ ] Verify Patient Pathways filters (drug, trust, directorate) only affect Patient Pathways
- [ ] Verify Trust Comparison directorate selector works for all directorates and indications
- [ ] Verify no regressions in Icicle and Sankey charts
- [ ] Test with both "directory" and "indication" chart types
- [ ] Update CLAUDE.md with new architecture (two views, state management, callback chains)
- [ ] `python run_dash.py` starts cleanly
- **Checkpoint**: Full application works end-to-end, documentation updated ✓

---

## Completion Criteria

All tasks marked `[x]` AND:
- [x] `python run_dash.py` starts cleanly at localhost:8050
- [x] Layout matches 01_nhs_classic.html (header, sidebar, KPIs, filter bar, chart card, footer)
- [x] Icicle chart renders with real SQLite data (pathway_nodes)
- [x] Date filters + chart type toggle update chart correctly
- [x] Filter modals open correctly for drugs, trusts, and directorates
- [x] Selecting a drug filters the chart correctly (no "multiple implied roots" error)
- [x] "All Drugs" card allows selecting any drug across all contexts
- [x] "Clear Filters" resets all selections
- [x] KPIs update dynamically (patients, drugs, cost)
- [x] No Reflex imports in `dash_app/`
- [x] No duplicate component ID errors on first load
- [x] Sidebar shows chart views (icicle/sankey/timeline), not filter triggers
- [x] Filter bar has drug/trust/directorate trigger buttons with selection count badges

### Phase 9 Completion Criteria
- [x] 8 chart tabs render in the chart card (Icicle + 7 new)
- [x] Tab switching is smooth — only active tab's chart is computed
- [x] All 7 new charts render real data from SQLite
- [x] All charts respond to existing filters (date, chart type, trust, drug, directorate)
- [x] Market Share shows grouped bars by directorate with drug breakdown
- [x] Cost Effectiveness shows lollipop chart with retention annotations
- [x] Cost Waterfall shows directorate cost_pp_pa bars
- [x] Sankey shows drug switching flows across treatment lines
- [x] Dosing shows parsed interval comparisons
- [x] Heatmap shows directorate × drug matrix
- [x] Treatment Duration shows avg_days bars
- [x] Icicle chart has no regressions
- [x] `python run_dash.py` starts cleanly with all tabs

### Phase 10 Completion Criteria
- [ ] Sidebar has "Patient Pathways" + "Trust Comparison" navigation items
- [ ] Patient Pathways view shows Icicle + Sankey tabs only
- [ ] Trust Comparison landing page shows directorate/indication buttons
- [ ] Trust Comparison dashboard renders 6 charts for selected directorate (Market Share, Cost Waterfall, Dosing, Heatmap, Duration, Cost Effectiveness)
- [ ] All 6 Trust Comparison charts show per-trust breakdown within selected directorate (except Cost Effectiveness which is directorate-scoped, no trust split)
- [ ] KPI row removed — fraction KPIs (X/X patients, drugs, cost) in header
- [ ] Global filter sub-header (date + chart type) is prominent and constant across both views
- [ ] Drug/trust/directorate filters only visible on Patient Pathways
- [ ] Chart type toggle affects Trust Comparison (indication mode shows indication buttons)
- [ ] Date filter changes update both views
- [ ] Icicle + Sankey have no regressions
- [ ] `python run_dash.py` starts cleanly

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `01_nhs_classic.html` | Design reference — CSS classes, layout structure, visual targets |
| `pathways_app/pathways_app.py` | Source of truth for data loading logic (lines 407-642) and icicle chart (lines 769-920) |
| `data/pathways.db` | SQLite database with pre-computed pathway_nodes |
| `data/DimSearchTerm.csv` | Directorate → Search_Term → drug mapping for card browser |
| `src/data_processing/diagnosis_lookup.py` | SEARCH_TERM_MERGE_MAP constant for asthma normalization |

## Key Data Patterns

### Date Filter IDs
| ID | Initiated | Last Seen |
|----|-----------|-----------|
| `all_6mo` | All years | Last 6 months (DEFAULT) |
| `all_12mo` | All years | Last 12 months |
| `1yr_6mo` | Last 1 year | Last 6 months |
| `1yr_12mo` | Last 1 year | Last 12 months |
| `2yr_6mo` | Last 2 years | Last 6 months |
| `2yr_12mo` | Last 2 years | Last 12 months |

### Pathway Node Columns (from SQLite)
`parents, ids, labels, level, value, cost, costpp, cost_pp_pa, colour, first_seen, last_seen, first_seen_parent, last_seen_parent, average_spacing, average_administered, avg_days, trust_name, directory, drug_sequence, chart_type, date_filter_id`

### Icicle Chart Customdata (10 fields)
```
[0] value          — patient count
[1] colour         — proportion of parent
[2] cost           — total cost
[3] costpp         — cost per patient
[4] first_seen     — first intervention date
[5] last_seen      — last intervention date
[6] first_seen_parent  — earliest date in parent group
[7] last_seen_parent   — latest date in parent group
[8] average_spacing    — dosing information string
[9] cost_pp_pa         — cost per patient per annum
```
