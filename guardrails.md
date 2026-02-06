# Guardrails

Known failure patterns. Read EVERY iteration. Follow ALL of these rules.
If you discover a new failure pattern during your work, add it to this file.

---

## Backend Isolation

### Do NOT modify pipeline/analysis logic in src/
- **When**: Building Dash integration
- **Rule**: Do NOT change the logic in these files — they are the data pipeline and must stay as-is:
  - `data_processing/pathway_pipeline.py`, `transforms.py`, `diagnosis_lookup.py` (matching/query logic)
  - `analysis/pathway_analyzer.py`, `statistics.py`
  - `cli/refresh_pathways.py`
  - `data_processing/schema.py`, `reference_data.py`, `cache.py`, `data_source.py`
- **Why**: The pipeline is complete and tested. Changing it risks breaking the data refresh workflow.

### DO use shared utilities in src/ rather than duplicating
- **When**: The Dash app needs data loading or figure construction
- **Rule**: Dash callbacks should CALL INTO `src/`, not duplicate the code. Shared functions:
  - `data_processing/pathway_queries.py` — `load_initial_data()` and `load_pathway_nodes()` for all SQLite queries
  - `visualization/plotly_generator.py` — `create_icicle_from_nodes()` for icicle chart from list-of-dicts
  - `dash_app/data/queries.py` — thin wrapper that resolves DB path and delegates to shared functions
- **Why**: Duplicating SQL queries and figure logic creates copies that drift apart. Shared code in `src/` is the cleaner architecture.

### Do NOT modify pathways.db schema or data
- **When**: Querying the database from Dash callbacks
- **Rule**: Read-only access. Use `sqlite3.connect(db_path)` with SELECT queries only. Never INSERT, UPDATE, DELETE, or ALTER.
- **Why**: pathways.db is populated by `python -m cli.refresh_pathways`. The Dash app is a read-only consumer.

---

## CSS & Design Fidelity

### Use className matching 01_nhs_classic.html, not inline styles
- **When**: Building any Dash HTML component
- **Rule**: Use `className="css-class-name"` referencing classes from `dash_app/assets/nhs.css`. Do NOT use inline `style={}` dicts for layout/visual styling. Only use inline styles for truly dynamic values (e.g., `style={"flex": patient_count}` for proportional widths).
- **Why**: CSS fidelity to the HTML concept is a primary goal. Inline styles drift from the design and are harder to maintain.

### nhs.css is the single source of CSS truth
- **When**: Adding or modifying styles
- **Rule**: All styles go in `dash_app/assets/nhs.css`. If the concept HTML doesn't have a class for something, add it to nhs.css with the same naming convention (`.component__element--modifier`).
- **Why**: Dash auto-serves files from `assets/`. Keeping CSS in one file matches the design source (01_nhs_classic.html) and avoids style fragmentation.

### Read 01_nhs_classic.html when building UI components
- **When**: Creating any component in `dash_app/components/`
- **Rule**: Read `01_nhs_classic.html` first to see the exact HTML structure, CSS classes, and element hierarchy for that component. Match it as closely as possible.
- **Why**: The HTML concept IS the design spec. Deviating creates visual inconsistency.

---

## Callback Architecture

### No circular callback dependencies
- **When**: Writing Dash callbacks
- **Rule**: Callbacks must flow unidirectionally: filter inputs → `app-state` store → `chart-data` store → UI components. Never have a component that is both Input and Output in the same callback chain without an intermediate store.
- **Why**: Dash raises `DuplicateCallback` errors for circular dependencies, and they're extremely hard to debug.

### Use dcc.Store for all state, not server-side globals
- **When**: Managing application state (selected filters, chart data, reference data)
- **Rule**: ALL state lives in `dcc.Store` components. Never use module-level globals, class variables, or `flask.g` for state. The 3 stores are: `app-state` (session), `chart-data` (memory), `reference-data` (session).
- **Why**: Dash is stateless per request. Server-side state breaks with multiple users and causes subtle bugs during development.

### Use callback_context for multi-input callbacks
- **When**: A callback has multiple Inputs and needs to know which one triggered it
- **Rule**: Use `dash.callback_context.triggered` (or `ctx.triggered_id` in Dash 2.x) to determine the triggering input.
- **Why**: Without this, the callback runs for every input change and you can't distinguish which filter changed.

### Pattern-matching callbacks for dynamic drug chips
- **When**: Building the card browser drawer with clickable drug chips
- **Rule**: Use `{"type": "drug-chip", "index": drug_name}` pattern for chip IDs. Register callbacks with `Input({"type": "drug-chip", "index": ALL}, "n_clicks")`. Access triggered chip via `ctx.triggered_id["index"]`.
- **Why**: The number of drug chips is dynamic (changes per directorate/indication). Pattern-matching callbacks handle this without hardcoding IDs.

---

## Plotly Figure

### Preserve create_icicle_from_nodes() in src/visualization/plotly_generator.py
- **When**: Modifying the icicle chart
- **Rule**: `create_icicle_from_nodes(nodes, title)` in `src/visualization/plotly_generator.py` is the shared icicle chart function. It accepts list-of-dicts from dcc.Store. Key properties:
  - 10-field customdata structure (value, colour, cost, costpp, first_seen, last_seen, first_seen_parent, last_seen_parent, average_spacing, cost_pp_pa)
  - NHS colorscale: `[[0.0, "#003087"], [0.25, "#0066CC"], [0.5, "#1E88E5"], [0.75, "#4FC3F7"], [1.0, "#E3F2FD"]]`
  - `maxdepth=3`, `branchvalues="total"`, `sort=False`
  - Layout: transparent background, reduced margins, autosize
- **Why**: The icicle chart is tested and correct. The Dash callback in `dash_app/callbacks/chart.py` calls this function.

### Chart data is a list of dicts
- **When**: Passing data between `chart-data` store and chart callback
- **Rule**: `chart-data` store holds `{"nodes": [...], "unique_patients": int, "total_drugs": int, "total_cost": float}`. Each node is a dict with keys matching the SQLite columns needed for the figure: `parents, ids, labels, value, cost, costpp, colour, first_seen, last_seen, first_seen_parent, last_seen_parent, average_spacing, cost_pp_pa`.
- **Why**: `dcc.Store` serializes to JSON. Keep the same dict structure that `pathways_app.py` uses for `chart_data` so the figure callback works identically.

---

## Data Extraction

### Keep data logic in shared src/ functions, not dash_app/ duplicates
- **When**: Adding or modifying data loading functions
- **Rule**: SQL queries and data logic live in `src/data_processing/pathway_queries.py`. The `dash_app/data/queries.py` is a thin wrapper that resolves the DB path and delegates. Do not duplicate queries in `dash_app/`.
- **Why**: Shared code in `src/` prevents query drift and keeps the single source of truth for data access.

### DimSearchTerm.csv fragments are substrings
- **When**: Building the card browser or matching drugs to indications
- **Rule**: `CleanedDrugName` values in DimSearchTerm.csv are drug name FRAGMENTS (e.g., "ADALIMUMAB", "PEGYLATED", "INHALED"). They're matched against full drug names using `drug_name.upper().contains(fragment)`. Don't assume exact match.
- **Why**: Some fragments are partial (INHALED matches "INHALED BECLOMETASONE", "INHALED FLUTICASONE", etc.).

### Apply SEARCH_TERM_MERGE_MAP when loading DimSearchTerm.csv
- **When**: Building the directorate tree in `card_browser.py`
- **Rule**: Import and apply `SEARCH_TERM_MERGE_MAP` from `data_processing.diagnosis_lookup` to normalize "allergic asthma" → "asthma" and "severe persistent allergic asthma" → "asthma". Keep "urticaria" separate.
- **Why**: The Snowflake query and pathway processing already use merged Search_Terms. The card browser must match.

---

## SQLite Queries

### Use parameterized queries for all filters
- **When**: Building WHERE clauses with user-selected values
- **Rule**: Use `?` placeholders and pass params as a list. Never use f-strings or string interpolation for filter values.
- **Why**: Prevents SQL injection and handles special characters in drug/directory names (e.g., "CROHN'S DISEASE").

### Database path resolution
- **When**: Connecting to pathways.db from dash_app/
- **Rule**: Use `Path(__file__).resolve().parents[2] / "data" / "pathways.db"` from files in `dash_app/data/`. This resolves from `dash_app/data/queries.py` → project root → `data/pathways.db`.
- **Why**: Relative paths break depending on the working directory. Absolute path resolution is reliable.

---

## Dash Framework

### Wrap layout in dmc.MantineProvider
- **When**: Setting up the app layout in `app.py`
- **Rule**: The outermost layout element must be `dmc.MantineProvider(children=[...])`. Without this, DMC components (Drawer, Accordion, Chip, etc.) won't render.
- **Why**: Dash Mantine Components requires the Provider context to function.

### dcc.Store storage_type matters
- **When**: Creating the 3 store components
- **Rule**:
  - `app-state`: `storage_type="session"` — persists across page refreshes within a tab
  - `chart-data`: `storage_type="memory"` — cleared on page refresh (reloaded from SQLite)
  - `reference-data`: `storage_type="session"` — loaded once, persists across refreshes
- **Why**: Wrong storage type causes stale data bugs (memory clears too often) or wasted queries (session persists when it shouldn't).

### Dash assets directory is auto-served
- **When**: Placing CSS, JS, or images
- **Rule**: Put static assets in `dash_app/assets/`. Dash serves them automatically. Reference CSS via `className`, not `<link>` tags.
- **Why**: Dash's asset pipeline handles caching and serving. Manual `<link>` tags are unnecessary and may not work.

---

## Process Guardrails

### One task per iteration
- **When**: Temptation to do additional tasks after completing the current one
- **Rule**: Complete ONE task, validate it, commit it, update progress, then stop
- **Why**: Multiple tasks increase error risk and make failures harder to diagnose

### Never mark complete without validation
- **When**: Task feels "done" but hasn't been tested
- **Rule**: All validation tiers must pass before marking `[x]`
- **Why**: "Feels done" is not "is done"

### Write explicit handoff notes
- **When**: Every iteration, before stopping
- **Rule**: The "Next iteration should" section must contain specific, actionable guidance
- **Why**: The next iteration has zero memory. If you don't write it down, it's lost.

### Validate with `python run_dash.py`
- **When**: After completing any task
- **Rule**: Run `python run_dash.py` (or `python -c "from dash_app.app import app"` for import checks). The app must start without errors after EVERY task.
- **Why**: Broken imports or circular dependencies compound across tasks. Catch them immediately.

<!--
ADD NEW GUARDRAILS BELOW as failures are observed during the loop.

Format:
### [Short descriptive name]
- **When**: What situation triggers this guardrail?
- **Rule**: What must you do (or not do)?
- **Why**: What failure prompted adding this guardrail?
-->
