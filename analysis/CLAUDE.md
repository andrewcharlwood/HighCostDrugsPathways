# Analysis Package

Four-step pathway analysis pipeline refactored from original 267-line `generate_graph()` function.

## Module: pathway_analyzer.py

**Main entry points:**
- `generate_icicle_chart(df, filters)` — Directory charts (Trust → Directory → Drug → Pathway)
- `generate_icicle_chart_indication(df, indication_df, filters)` — Indication charts using Search_Term hierarchy

**Pipeline steps:**
1. `prepare_data()` — Filter by date/trusts/drugs/directories. **MUST use `df.copy()`** to prevent mutation.
2. `calculate_statistics()` — Compute frequency, cost, duration stats
3. `build_hierarchy()` — Create Trust → Directory/Indication → Drug → Pathway structure
4. `prepare_chart_data()` — Format data for Plotly icicle chart

**Note on modified UPIDs:**
For drug-aware indication matching, UPIDs are formatted as `{original}|{search_term}`. The hierarchy-building functions treat UPID as opaque — pipe delimiters work transparently without code changes.

## Module: statistics.py

Statistical calculation helper functions (frequency, cost, duration, per-patient metrics).

Called by `calculate_statistics()` during pipeline execution.
