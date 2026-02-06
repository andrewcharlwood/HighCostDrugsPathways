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
