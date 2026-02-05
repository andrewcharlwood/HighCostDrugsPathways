# Guardrails

Known failure patterns. Read EVERY iteration. Follow ALL of these rules.
If you discover a new failure pattern during your work, add it to this file.

---

## Drug-Indication Matching Guardrails

### Match drugs to indications, not just patients to indications
- **When**: Building the indication mapping for pathway charts
- **Rule**: Each drug must be validated against BOTH the patient's GP diagnoses AND the drug-to-indication mapping from DimSearchTerm.csv. A patient being diagnosed with rheumatoid arthritis does NOT mean all their drugs are for rheumatoid arthritis.
- **Why**: The previous approach assigned ONE indication per patient (most recent GP dx), ignoring which drugs actually treat which conditions. This produced misleading pathways.

### Use DimSearchTerm.csv for drug-to-Search_Term mapping
- **When**: Determining which Search_Term a drug belongs to
- **Rule**: Load `data/DimSearchTerm.csv`. The `CleanedDrugName` column has pipe-separated drug name fragments. Match HCD drug names against these fragments using substring matching (case-insensitive).
- **Why**: This CSV is the authoritative mapping of which drugs are used for which clinical indications.

### Use substring matching for drug fragments
- **When**: Matching HCD drug names against DimSearchTerm CleanedDrugName fragments
- **Rule**: Check if any fragment from DimSearchTerm is a SUBSTRING of the HCD drug name (case-insensitive). E.g., "PEGYLATED" should match "PEGYLATED LIPOSOMAL DOXORUBICIN".
- **Why**: DimSearchTerm contains both full drug names (ADALIMUMAB) and partial fragments (PEGYLATED, INHALED). Exact match would miss the partial ones.

### Modified UPID uses pipe delimiter
- **When**: Creating indication-aware UPIDs
- **Rule**: Format is `{original_UPID}|{search_term}`. Use pipe `|` as delimiter. Do NOT use ` - ` (hyphen with spaces) as that's used for pathway hierarchy levels in the `ids` column.
- **Why**: The `ids` column uses " - " to separate hierarchy levels (e.g., "N&WICS - NNUH - rheumatoid arthritis - ADALIMUMAB"). Using the same delimiter in UPIDs would break hierarchy parsing.

### Return ALL GP matches per patient, not just most recent
- **When**: Querying Snowflake for patient GP diagnoses
- **Rule**: Remove `QUALIFY ROW_NUMBER() OVER (PARTITION BY ... ORDER BY EventDateTime DESC) = 1`. Return ALL matching Search_Terms per patient with `GROUP BY + COUNT(*)` for code_frequency.
- **Why**: A patient may have GP diagnoses for both rheumatoid arthritis AND asthma. We need ALL matches to cross-reference with their drugs.

### Restrict GP code lookup to HCD data window
- **When**: Building the WHERE clause for the GP record query
- **Rule**: Add `AND pc."EventDateTime" >= :earliest_hcd_date` where `earliest_hcd_date` is `MIN(Intervention Date)` from the HCD DataFrame. Pass this as a parameter to `get_patient_indication_groups()`.
- **Why**: Old GP codes from years before treatment started add noise. A diagnosis coded 10 years ago may no longer be relevant. Restricting to the HCD window ensures code_frequency reflects recent clinical activity for the conditions being actively treated.

### Tiebreaker: highest GP code frequency when a drug matches multiple indications
- **When**: A single drug maps to multiple Search_Terms AND the patient has GP dx for multiple
- **Rule**: Use `code_frequency` (COUNT of matching SNOMED codes per Search_Term per patient) from the GP query. The Search_Term with the most matching codes in the patient's GP record wins. If tied, use alphabetical Search_Term for determinism.
- **Why**: E.g., ADALIMUMAB is listed under rheumatoid arthritis, crohn's disease, psoriatic arthritis, etc. A patient with 47 RA codes and 2 crohn's codes is almost certainly on ADALIMUMAB for RA. Frequency of GP coding is a much stronger signal of clinical intent than recency — a recent one-off asthma check doesn't mean ADALIMUMAB is for asthma.

### Same patient, different indications = separate modified UPIDs
- **When**: A patient's drugs map to different Search_Terms
- **Rule**: Create separate modified UPIDs for each indication. E.g., `RMV12345|rheumatoid arthritis` and `RMV12345|asthma`. These are treated as separate "patients" by the pathway analyzer.
- **Why**: This is the core design — drugs for different indications should create separate treatment pathways, even for the same physical patient.

### Fallback to directory for unmatched drugs
- **When**: A drug doesn't match any Search_Term OR the patient has no GP dx for any of the drug's Search_Terms
- **Rule**: Use fallback format: `{UPID}|{Directory} (no GP dx)`. The indication_df maps this to `"{Directory} (no GP dx)"`.
- **Why**: Maintains consistent behavior with the previous approach for patients/drugs without GP diagnosis matches.

### Merge asthma Search_Terms but keep urticaria separate
- **When**: Working with asthma-related Search_Terms from CLUSTER_MAPPING_SQL or DimSearchTerm.csv
- **Rule**: Merge "allergic asthma", "asthma", and "severe persistent allergic asthma" into a single "asthma" Search_Term. Keep "urticaria" as a separate Search_Term — do NOT merge it with asthma.
- **Why**: These are clinically the same condition at different severity levels. Splitting them fragments the data. Urticaria is a distinct dermatological condition that happens to share OMALIZUMAB.

### Don't modify directory chart processing
- **When**: Making changes to the indication matching logic
- **Rule**: Only modify the indication chart path (`elif current_chart_type == "indication":`). Directory charts use unmodified UPIDs and directory-based grouping.
- **Why**: Directory charts work correctly and should not be affected by indication matching changes.

---

## Snowflake Query Guardrails

### Use PseudoNHSNoLinked for GP record matching
- **When**: Querying GP records (PrimaryCareClinicalCoding) for patient diagnoses
- **Rule**: Use `PseudoNHSNoLinked` column from HCD data, NOT `PersonKey` (LocalPatientID)
- **Why**: PersonKey is provider-specific local ID. Only PseudoNHSNoLinked matches PatientPseudonym in GP records.

### Embed cluster query as CTE in Snowflake
- **When**: Looking up patient indications during data refresh
- **Rule**: Use the `CLUSTER_MAPPING_SQL` content as a WITH clause in the patient lookup query
- **Why**: This ensures we always use the complete cluster mapping and don't need local storage

### Quote mixed-case column aliases in Snowflake SQL
- **When**: Writing SELECT queries that return results to Python code
- **Rule**: Use `AS "ColumnName"` (quoted) for any column alias you'll access by name in Python
- **Why**: Snowflake uppercases unquoted identifiers. `SELECT foo AS Search_Term` returns `SEARCH_TERM`, so `row.get('Search_Term')` returns None. Fix: `SELECT foo AS "Search_Term"`

### Build indication_df from all unique UPIDs, not PseudoNHSNoLinked
- **When**: Creating the indication mapping DataFrame for pathway processing
- **Rule**: Use `df.drop_duplicates(subset=['UPID'])` not `drop_duplicates(subset=['PseudoNHSNoLinked'])`
- **Why**: A patient visiting multiple providers has multiple UPIDs. Using unique PseudoNHSNoLinked only maps one UPID per patient, leaving others as NaN.

---

## Data Processing Guardrails

### Copy DataFrames in functions that modify columns
- **When**: Writing functions like `prepare_data()` that modify DataFrame columns
- **Rule**: Always `df = df.copy()` at the start of any function that modifies column values on the input DataFrame
- **Why**: `prepare_data()` mapped Provider Code → Name in-place. When called multiple times on the same DataFrame, only the first call worked. The fix: `df.copy()` prevents destructive mutation.

### Include chart_type in UNIQUE constraints for pathway_nodes
- **When**: Creating or modifying the pathway_nodes table schema
- **Rule**: The UNIQUE constraint MUST include `chart_type`: `UNIQUE(date_filter_id, chart_type, ids)`
- **Why**: Without `chart_type`, `INSERT OR REPLACE` silently overwrites directory chart nodes when indication chart nodes are inserted.

### Handle NaN in Directory when building fallback labels
- **When**: Creating fallback indication labels for patients without GP diagnosis match
- **Rule**: Check `pd.notna(directory)` before concatenating to string. Use `"UNKNOWN (no GP dx)"` for NaN cases.
- **Why**: NaN handling prevents TypeError and ensures meaningful fallback labels.

### Use parameterized queries for SQLite
- **When**: Building WHERE clauses with user-selected filters
- **Rule**: Use `?` placeholders and pass params tuple — never string interpolation
- **Why**: Prevents SQL injection and handles special characters in drug/directory names

### Use existing pathway_analyzer functions
- **When**: Processing pathway data for the icicle chart
- **Rule**: Reuse functions from `analysis/pathway_analyzer.py` — don't reinvent
- **Why**: The existing code handles edge cases (empty groups, statistics calculation, color mapping)

---

## Reflex Guardrails

### Use .to() methods for Var operations in rx.foreach
- **When**: Working with items inside `rx.foreach` render functions
- **Rule**: Use `item.to(int)` for numeric comparisons, `item.to_string()` for text operations
- **Why**: Items from rx.foreach are Var objects, not plain Python values.

### Use rx.cond for conditional rendering, not Python if
- **When**: Conditionally showing/hiding components or changing styles based on state
- **Rule**: Use `rx.cond(condition, true_component, false_component)` — not Python `if`
- **Why**: Python `if` evaluates at definition time; `rx.cond` evaluates reactively at render time

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
- **When**: Unsure how to implement something
- **Rule**: Look at `pathways_app/pathways_app.py`, `analysis/pathway_analyzer.py`, `cli/refresh_pathways.py`
- **Why**: The existing codebase has solved many quirks already

### Snowflake connection_timeout must be high enough for GP lookup queries
- **When**: GP record queries against PrimaryCareClinicalCoding time out
- **Rule**: Ensure `connection_timeout` in config/snowflake.toml is at least 600 (currently set to 600). This controls the Python client's `network_timeout`, which is how long the client waits for ANY Snowflake response. Do NOT lower this value.
- **Why**: GP lookup queries take ~40s per batch due to CTE compilation overhead. With connection_timeout=30, every batch timed out silently (error 000604/57014).

### Use large batch sizes (5000+) for GP record lookups
- **When**: Calling `get_patient_indication_groups()` with patient batches
- **Rule**: Use batch_size=5000 or larger. The query time is ~40s regardless of batch size (5 patients ≈ 500 patients ≈ 5000 patients). Smaller batches just multiply the fixed overhead.
- **Why**: With batch_size=500, 36K patients needed 74 batches × 40s = ~50 min. With batch_size=5000, only 8 batches × 45s = ~6 min. The bottleneck is CTE compilation, not data volume.

<!--
ADD NEW GUARDRAILS BELOW as failures are observed during the loop.

Format:
### [Short descriptive name]
- **When**: What situation triggers this guardrail?
- **Rule**: What must you do (or not do)?
- **Why**: What failure prompted adding this guardrail?
-->
