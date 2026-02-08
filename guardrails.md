# Guardrails

Known failure patterns. Read EVERY iteration. Follow ALL of these rules.
If you discover a new failure pattern during your work, add it to this file.

---

## Backend Isolation

### Do NOT modify pipeline/analysis logic in src/
- **When**: Improving charts or adding analytics
- **Rule**: Do NOT change the logic in these files — they are the data pipeline and must stay as-is:
  - `data_processing/pathway_pipeline.py`, `transforms.py`, `diagnosis_lookup.py` (matching/query logic)
  - `analysis/pathway_analyzer.py`, `statistics.py`
  - `cli/refresh_pathways.py`
  - `data_processing/schema.py`, `reference_data.py`, `cache.py`, `data_source.py`
- **Why**: The pipeline is complete and tested. Changing it risks breaking the data refresh workflow.

### DO use shared utilities in src/ rather than duplicating
- **When**: Adding chart functions or query functions
- **Rule**: Chart figure functions go in `src/visualization/plotly_generator.py`. Query functions go in `src/data_processing/pathway_queries.py`. Dash callbacks should CALL INTO `src/`, not duplicate the code.
- **Why**: Duplicating SQL queries and figure logic creates copies that drift apart.

### Do NOT modify pathways.db schema or data from Dash callbacks
- **When**: Querying the database from Dash callbacks
- **Rule**: Read-only access from Dash. Use `sqlite3.connect(db_path)` with SELECT queries only. Never INSERT, UPDATE, DELETE, or ALTER from the Dash app.
- **Exception**: The standalone `cli/compute_trends.py` script may CREATE and INSERT into the `pathway_trends` table. This is a separate CLI command, not part of the Dash app or the main refresh pipeline.
- **Why**: pathways.db is populated by CLI commands. The Dash app is a read-only consumer.

### Trend computation uses existing pipeline functions as-is
- **When**: Building `cli/compute_trends.py`
- **Rule**: Import and call `fetch_and_transform_data()` and `process_pathway_for_date_filter()` from `pathway_pipeline.py`. Do NOT modify these functions. Do NOT modify `schema.py`, `reference_data.py`, or `refresh_pathways.py`. The new script creates its own table via `CREATE TABLE IF NOT EXISTS`.
- **Why**: The historical snapshot approach works by calling existing functions with different `max_date` values. No pipeline changes needed.

---

## Chart Generation (plotly_generator.py)

### Use _base_layout() for all chart functions
- **When**: Modifying or creating any chart function after Task A.1
- **Rule**: Call `_base_layout(title)` to get shared layout properties, then update with chart-specific overrides. Do NOT hardcode font family, title font size, bgcolor, hoverlabel, or autosize in individual functions.
- **Why**: DRY principle. Inconsistent styling was a bug category (Tier 2 fix).

### Use module-level palette constants
- **When**: Assigning colors to traces in any chart function
- **Rule**: Use `TRUST_PALETTE` (7 colors) for trust-comparison charts where bars/traces represent trusts. Use `DRUG_PALETTE` (15 colors) for charts where bars/traces represent drugs. Do NOT define local `nhs_colours` lists.
- **Why**: Local blue-heavy palettes made trusts indistinguishable (a reported bug).

### Heatmaps must have cell text annotations
- **When**: Modifying `create_heatmap_figure()` or `create_trust_heatmap_figure()`
- **Rule**: Always include `text=text_values, texttemplate="%{text}"` on the heatmap trace. Format text per metric: patients → `"N"`, cost → `"£Nk"`, cost_pp_pa → `"£N"`.
- **Why**: Without cell text, users must hover every cell to read values — a reported usability bug.

### Heatmaps must use linear colorscale
- **When**: Setting colorscale on heatmap traces
- **Rule**: Use linear 5-stop colorscale: `[0.0 #E3F2FD, 0.25 #90CAF9, 0.5 #42A5F5, 0.75 #1E88E5, 1.0 #003087]`. Always set `zmin=0`. Do NOT use non-linear stops like `[0.01, 0.1, 0.3, ...]`.
- **Why**: Non-linear stops compressed 99% of the value range into identical blues.

### Charts must use autosize, not fixed width
- **When**: Setting chart dimensions
- **Rule**: Use `autosize=True` instead of explicit `width=...`. Dynamic height is fine (calculated from data). Use `yaxis automargin=True` instead of fixed left margins.
- **Why**: Fixed widths overflow their containers on different screen sizes.

### Legends must adapt to item count
- **When**: Setting legend layout on charts with variable trace counts
- **Rule**: Use `_smart_legend(n_items)` helper (once created in Task A.3). >15 items = vertical right legend. ≤15 items = horizontal with dynamic bottom margin.
- **Why**: Horizontal legends with 42 drugs wrap 5+ rows and overlap chart content.

---

## Callback Architecture

### No circular callback dependencies
- **When**: Writing Dash callbacks
- **Rule**: Callbacks must flow unidirectionally: filter inputs → `app-state` store → `chart-data` store → UI components. Never have a component that is both Input and Output in the same callback chain without an intermediate store.
- **Why**: Dash raises `DuplicateCallback` errors for circular dependencies.

### Use dcc.Store for all state, not server-side globals
- **When**: Managing application state
- **Rule**: ALL state lives in `dcc.Store` components. Never use module-level globals or class variables for state. The 4 stores: `app-state` (session), `chart-data` (memory), `reference-data` (session), `active-tab` (memory).
- **Why**: Dash is stateless per request. Server-side state breaks with multiple users.

### Only render the active tab's chart
- **When**: Building tab switching or chart rendering callbacks
- **Rule**: Check `active-tab` store and ONLY compute the figure for the active tab. Return `no_update` or placeholder for inactive tabs.
- **Why**: Computing all charts on every filter change would be extremely slow.

### Chart figure functions go in src/visualization/, not dash_app/
- **When**: Creating new chart figures
- **Rule**: Create figure builder functions in `src/visualization/plotly_generator.py`. Dash callbacks call these shared functions. Do NOT put Plotly figure construction logic directly in `dash_app/callbacks/`.
- **Why**: Shared figure functions can be tested independently and reused.

### New query functions use same pattern as existing ones
- **When**: Adding query functions to `src/data_processing/pathway_queries.py`
- **Rule**: Follow the same pattern as `load_pathway_nodes()`: accept `db_path` parameter, use `sqlite3.connect()` with `row_factory = sqlite3.Row`, parameterized queries, return JSON-serializable dicts/lists. Add thin wrappers in `dash_app/data/queries.py`.
- **Why**: Consistency with existing code. The thin wrapper pattern ensures DB path resolution is centralized.

---

## Data Patterns

### Use parameterized queries for all filters
- **When**: Building WHERE clauses with user-selected values
- **Rule**: Use `?` placeholders and pass params as a list. Never use f-strings or string interpolation for filter values.
- **Why**: Prevents SQL injection and handles special characters in drug/directory names (e.g., "CROHN'S DISEASE").

### Parsing utilities must handle missing/null data gracefully
- **When**: Parsing `average_spacing` HTML strings, `average_administered` JSON, or `ids` column values
- **Rule**: Always handle `None`, empty string `""`, and malformed data. Return sensible defaults rather than raising exceptions.
- **Why**: Not all nodes have statistics populated. Level 0-2 nodes have no drug-level statistics.

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

### Re-read plotly_generator.py before editing
- **When**: Starting any task that modifies chart functions
- **Rule**: Always re-read `src/visualization/plotly_generator.py` at the start of the iteration. Line numbers in IMPLEMENTATION_PLAN.md are approximate and shift as edits accumulate. Search for function names, not line numbers.
- **Why**: Previous iterations may have changed the file, shifting all line numbers.

### 3-view navigation pattern
- **When**: Modifying `switch_view()` in `navigation.py` or `update_app_state()` in `filters.py`
- **Rule**: There are 3 views: `patient-pathways`, `trust-comparison`, `trends`. The `switch_view()` callback has 6 Outputs (3 view styles + 3 nav classNames). The `update_app_state()` callback has 3 nav Inputs. When updating either callback, ensure ALL return paths handle all 3 views correctly. Every return statement must include values for all 6 outputs / handle all 3 active_view values.
- **Why**: Adding a 3rd view to a previously binary toggle is error-prone — missing a return path causes Dash callback errors.

### Trends view state in app-state
- **When**: Working on the Trends view (E.2–E.4)
- **Rule**: `selected_trends_directorate` must be initialized as `None` in the `app-state` dcc.Store initial data in `app.py`. The Trends view uses landing/detail toggle based on this value (same pattern as Trust Comparison's `selected_comparison_directorate`).
- **Why**: Missing initial state causes KeyError on first page load.

### Removing callback Outputs/Inputs requires updating ALL return paths
- **When**: Removing Outputs or Inputs from an existing callback (e.g., E.1 removing trends toggle from update_chart)
- **Rule**: When removing an Output from a callback, you MUST update EVERY `return` statement in that callback to match the new Output count. Count the number of return statements before editing and verify the same count after. The `update_chart()` callback currently has 4+ return paths.
- **Why**: Mismatched return tuple length causes `InvalidCallbackReturnValue` at runtime.
