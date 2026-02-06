# data_processing Package

Data layer for NHS High-Cost Drug Patient Pathway Analysis Tool.

## Core Responsibilities

**Data Pipeline:** `Snowflake → Transforms → Pathway Generation → SQLite`

## Key Modules

**transforms.py** — Core data transformations (moved from tools/data.py):
- `patient_id()` — Creates UPID = Provider Code (first 3 chars) + PersonKey
- `drug_names()` — Standardizes drug names via drugnames.csv lookup
- `department_identification()` — 5-level fallback chain for directory assignment

**pathway_pipeline.py** — Pipeline orchestration:
- Processes 6 date filter combinations × 2 chart types (directory + indication)
- `fetch_and_transform_data()` — Snowflake fetch + UPID/drug/directory transforms
- `process_pathway_for_date_filter()` — Directory charts using `generate_icicle_chart()`
- `process_indication_pathway_for_date_filter()` — Indication charts using `generate_icicle_chart_indication()`
- `insert_pathway_records()` — SQLite insertion with parameterized queries

**diagnosis_lookup.py** — GP diagnosis matching:
- `get_patient_indication_groups()` — Batch queries Snowflake (500 patients at a time)
- Embeds ~148 Search_Term → Cluster_ID mappings as SQL CTE
- Returns most recent match per patient via `QUALIFY ROW_NUMBER()`

**database.py** — SQLite connection pooling and transaction management

**schema.py** — SQL schema definitions (reference tables + pathway_nodes)

**snowflake_connector.py** — Snowflake SSO integration via externalbrowser authenticator

**cache.py** — Query result caching with TTL-based invalidation

## Import Pattern

All imports use package names directly:
```python
from data_processing.transforms import patient_id, drug_names, department_identification
from data_processing.pathway_pipeline import process_all_date_filters
```
