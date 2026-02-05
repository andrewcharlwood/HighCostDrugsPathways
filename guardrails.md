# Guardrails

Known failure patterns. Read EVERY iteration. Follow ALL of these rules.
If you discover a new failure pattern during your work, add it to this file.

---

## Reflex Guardrails

### Use .to() methods for Var operations in rx.foreach
- **When**: Working with items inside `rx.foreach` render functions
- **Rule**: Use `item.to(int)` for numeric comparisons, `item.to_string()` for text operations
- **Why**: Items from rx.foreach are `ObjectItemOperation` Vars, not plain Python values. Using `>=` or f-strings directly causes TypeError.

**Bad:**
```python
def render_row(item):
    color = rx.cond(item["value"] >= 50, "green", "red")  # TypeError!
    return rx.text(f"{item['name']}: {item['value']}")    # Won't interpolate!
```

**Good:**
```python
def render_row(item):
    color = rx.cond(item["value"].to(int) >= 50, "green", "red")
    return rx.text(item["name"].to_string() + ": " + item["value"].to_string())
```

### Use rx.cond for conditional rendering, not Python if
- **When**: Conditionally showing/hiding components or changing styles based on state
- **Rule**: Use `rx.cond(condition, true_component, false_component)` — not Python `if`
- **Why**: Python `if` evaluates at definition time; `rx.cond` evaluates reactively at render time

### State variables must have default values
- **When**: Defining state variables in the State class
- **Rule**: Always provide a default: `my_var: str = ""` not just `my_var: str`
- **Why**: Reflex requires defaults for state initialization

### Computed vars use @rx.var decorator
- **When**: Creating derived/computed values from state
- **Rule**: Use `@rx.var` decorator, return a value, and include return type annotation
- **Why**: Without the decorator, the method won't be reactive

```python
@rx.var
def filtered_count(self) -> int:
    return len(self.filtered_data)
```

### Event handlers don't return values to components
- **When**: Creating methods that handle user interactions
- **Rule**: Event handlers modify state; they don't return values directly to UI
- **Why**: Use state variables and computed vars to communicate between handlers and UI

---

## Design System Guardrails

### Never hardcode colors
- **When**: Any styling that involves color
- **Rule**: Import from `pathways_app.styles` and use `Colors.PRIMARY`, `Colors.SLATE_700`, etc.
- **Why**: Hardcoded colors break consistency and make theming impossible

### Never hardcode spacing
- **When**: Any padding, margin, gap values
- **Rule**: Use `Spacing.SM`, `Spacing.LG`, etc. from the styles module
- **Why**: Consistent spacing is fundamental to visual cohesion

### Use design system typography
- **When**: Any text styling
- **Rule**: Use the typography classes/helpers from styles.py
- **Why**: Typography hierarchy creates visual structure

---

## Data Processing Guardrails

### Use existing pathway_analyzer functions
- **When**: Processing pathway data for the icicle chart
- **Rule**: Reuse functions from `analysis/pathway_analyzer.py` — don't reinvent
- **Why**: The existing code handles edge cases (empty groups, statistics calculation, color mapping)

### Extract denormalized fields from ids string
- **When**: Creating denormalized columns (trust_name, directory, drug_sequence)
- **Rule**: Parse the `ids` column which contains the full hierarchical path
- **Why**: The ids format is "Trust|Directory|Drug1|Drug2|..." — split on "|" to extract components

### Handle None/NULL values in pathway data
- **When**: Reading pathway_nodes from SQLite
- **Rule**: Always use `or ""` / `or 0` / `or "N/A"` when accessing optional columns
- **Why**: Many columns (costpp, average_spacing, etc.) can be NULL for certain hierarchy levels

### Use parameterized queries for SQLite
- **When**: Building WHERE clauses with user-selected filters
- **Rule**: Use `?` placeholders and pass params tuple — never string interpolation
- **Why**: Prevents SQL injection and handles special characters in drug/directory names

---

## Code Quality Guardrails

### Verify compilation before committing
- **When**: After ANY code changes
- **Rule**: Run `python -m py_compile <file>` AND `reflex run` (briefly) to check
- **Why**: Committing broken code wastes the next iteration fixing preventable errors

### One component per function
- **When**: Creating UI components
- **Rule**: Each logical component should be its own function returning `rx.Component`
- **Why**: Smaller functions are easier to debug and reuse

### Keep state minimal
- **When**: Designing state structure
- **Rule**: Only store what's necessary; derive everything else with computed vars
- **Why**: Duplicate state leads to sync bugs

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

### Check existing code for patterns
- **When**: Unsure how to implement something in Reflex or pathway processing
- **Rule**: Look at `pathways_app/pathways_app.py`, `analysis/pathway_analyzer.py`, `visualization/plotly_generator.py`
- **Why**: The existing codebase has solved many quirks already

---

## UI Redesign Guardrails

### Clear Reflex cache before running
- **When**: Before running `reflex run` or `reflex compile`, especially after style/layout changes
- **Rule**: Delete `.states` and `.web` folders first: `Remove-Item -Recurse -Force .states, .web -ErrorAction SilentlyContinue`
- **Why**: Stale cache causes old styles/components to persist, making it appear changes didn't work

### Test visual changes with reflex run
- **When**: After any layout or styling changes
- **Rule**: Run `reflex run` and visually verify in browser. Screenshots are not enough.
- **Why**: CSS calculations and flex layouts often behave differently than expected

### Don't break existing functionality
- **When**: Refactoring layout components
- **Rule**: Ensure all filter handlers, KPI updates, and chart rendering still work after changes
- **Why**: It's easy to accidentally disconnect event handlers when restructuring components

### Use calc() for responsive heights
- **When**: Making elements fill remaining viewport space
- **Rule**: Use `height="calc(100vh - Xpx)"` where X is the sum of fixed-height elements above
- **Why**: Fixed heights don't adapt to content changes; calc() keeps things responsive

### Test at multiple viewport widths
- **When**: Making full-width changes
- **Rule**: Test at 1366px, 1920px, and 2560px widths minimum
- **Why**: Full-width layouts can break or look sparse at extreme sizes

### Keep filter dropdown z-index high
- **When**: Restructuring filter section
- **Rule**: Dropdown panels need `z_index="50"` or higher to appear above chart
- **Why**: Plotly charts have their own stacking context and can overlap dropdowns

---

## Snowflake Query Guardrails

### Use PseudoNHSNoLinked for GP record matching
- **When**: Querying GP records (PrimaryCareClinicalCoding) for patient diagnoses
- **Rule**: Use `PseudoNHSNoLinked` column from HCD data, NOT `PersonKey` (LocalPatientID)
- **Why**: PersonKey is provider-specific local ID. Only PseudoNHSNoLinked matches PatientPseudonym in GP records.

### Use Search_Term for grouping, not Indication
- **When**: Creating indication-based pathway hierarchy
- **Rule**: Group patients by `Search_Term` from the cluster query
- **Why**: Search_Term provides meaningful clinical groupings (~148 values)

### Handle unmatched patients in indication chart
- **When**: Patient has no GP diagnosis matching cluster SNOMED codes
- **Rule**: Use their assigned directorate (from fallback logic) as the grouping label, not "Unknown"
- **Why**: User wants mixed labels - Search_Terms for matched patients, directorate names for unmatched

### Use most recent SNOMED code for multiple matches
- **When**: Patient has GP records matching multiple SNOMED codes
- **Rule**: Use the match with the most recent `EventDateTime` from PrimaryCareClinicalCoding
- **Why**: Most recent diagnosis reflects current clinical state

### Embed cluster query as CTE in Snowflake
- **When**: Looking up patient indications during data refresh
- **Rule**: Use the `snomed_indication_mapping_query.sql` content as a WITH clause in the patient lookup query
- **Why**: This ensures we always use the complete cluster mapping and don't need local storage

### Chart type column in pathway_nodes
- **When**: Inserting pathway records to SQLite
- **Rule**: Include `chart_type` column with value "directory" or "indication"
- **Why**: Needed to filter pathways when user toggles chart type in UI

### Quote mixed-case column aliases in Snowflake SQL
- **When**: Writing SELECT queries that return results to Python code
- **Rule**: Use `AS "ColumnName"` (quoted) for any column alias you'll access by name in Python
- **Why**: Snowflake uppercases unquoted identifiers. `SELECT foo AS Search_Term` returns `SEARCH_TERM`, so `row.get('Search_Term')` returns None. Fix: `SELECT foo AS "Search_Term"`

### Build indication_df from all unique UPIDs, not PseudoNHSNoLinked
- **When**: Creating the indication mapping DataFrame for pathway processing
- **Rule**: Use `df.drop_duplicates(subset=['UPID'])` not `drop_duplicates(subset=['PseudoNHSNoLinked'])`
- **Why**: A patient visiting multiple providers has multiple UPIDs (UPID = ProviderCode[:3] + PersonKey). Using unique PseudoNHSNoLinked only maps one UPID per patient, leaving others as NaN and causing TypeError in build_hierarchy.

### Handle NaN in Directory when building fallback labels
- **When**: Creating fallback indication labels for patients without GP diagnosis match
- **Rule**: Check `pd.notna(directory)` before concatenating to string. Use `"UNKNOWN (no GP dx)"` for NaN cases.
- **Why**: `str(nan) + " (no GP dx)"` doesn't cause error, but `nan + " (no GP dx)"` causes TypeError. Always be explicit about NaN handling.

<!--
ADD NEW GUARDRAILS BELOW as failures are observed during the loop.

Format:
### [Short descriptive name]
- **When**: What situation triggers this guardrail?
- **Rule**: What must you do (or not do)?
- **Why**: What failure prompted adding this guardrail?
-->
