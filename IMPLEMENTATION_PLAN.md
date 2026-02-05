# Implementation Plan - Direct SNOMED Indication Mapping

## Project Overview

Extend the pathway analysis application to use direct SNOMED code matching from GP records to:
1. **Improve directorate assignment** - Use diagnosis-based directorate as primary method
2. **Add indication-based icicle chart** - New chart type showing Trust → Search_Term → Drug → Pathway

### Data Source
`data/drug_snomed_mapping_enriched.csv` - 163K rows mapping:
- Drug → Indication → TA_ID → Search_Term → SNOMEDCode → PrimaryDirectorate

### Key Design Decisions
| Aspect | Decision |
|--------|----------|
| Primary directorate method | Diagnosis-based (SNOMED match → PrimaryDirectorate) |
| Fallback | department_identification() chain |
| Grouping level | `Search_Term` column (187 unique values) |
| Chart types | Two: "By Directory" and "By Indication" (user toggle) |
| No-match display | Show assigned directorate in indication chart (mixed labels) |
| Multiple matches | Use most recent SNOMED code by GP record date |
| Data storage | SQLite table `ref_drug_snomed_mapping`, accessed at ingestion |

## Quality Checks

Run after each task:

```bash
# Syntax check
python -m py_compile <modified_file.py>

# Import verification
python -c "from data_processing.diagnosis_lookup import *"
python -c "from data_processing.pathway_pipeline import *"

# For Reflex changes
python -m reflex compile
```

---

## Phase 1: Data Infrastructure

### 1.1 Create SQLite Table for SNOMED Mapping
- [x] Add `REF_DRUG_SNOMED_MAPPING_SCHEMA` to `data_processing/schema.py`:
  - Columns: drug_name, indication, ta_id, search_term, snomed_code, snomed_description, cleaned_drug_name, primary_directorate, all_directorates
  - Index on: cleaned_drug_name, snomed_code, search_term
- [x] Add `create_drug_snomed_mapping_table()` helper function
- [x] Add to `ALL_TABLES_SCHEMA` and migration
- [x] Verify: `python -m data_processing.migrate` creates table

### 1.2 Load Enriched Mapping Data
- [x] Create `data_processing/load_snomed_mapping.py` script:
  - Read `data/drug_snomed_mapping_enriched.csv`
  - Insert into `ref_drug_snomed_mapping` table
  - Log: row count, unique drugs, unique search terms
- [x] Add CLI entry point: `python -m data_processing.load_snomed_mapping`
- [x] Verify: Query confirms 163K+ rows, 187 search terms

### 1.3 Extend Diagnosis Lookup Module
- [x] Add `get_drug_snomed_codes(drug_name)` to `diagnosis_lookup.py`:
  - Query `ref_drug_snomed_mapping` for all SNOMED codes for a drug
  - Return list of DrugSnomedMapping(snomed_code, snomed_description, search_term, primary_directorate, indication, ta_id)
- [x] Add `patient_has_indication_direct(patient_pseudonym, snomed_codes, connector)`:
  - Query `PrimaryCareClinicalCoding` directly for exact SNOMED code matches
  - Return most recent match by EventDateTime
  - Return: DirectSnomedMatchResult(matched_code, search_term, primary_directorate, event_date) or unmatched
- [x] Verify: Tested with ADALIMUMAB (1320 mappings, 10 Search_Terms), RANIBIZUMAB (104 mappings), case-insensitivity

---

## Phase 2: Pathway Processing Updates

### 2.1 Update Directorate Assignment Logic
- [x] Modify `tools/data.py` `department_identification()` or create wrapper:
  - Add `get_directorate_from_diagnosis(upid, drug_name, connector)` function
  - Logic: Try diagnosis-based first → fallback to department_identification()
  - Return: (directorate, source) where source is "DIAGNOSIS" or "FALLBACK"
- [x] Track assignment source for metrics (how many diagnosis-based vs fallback)
- [x] Verify: Test with sample patient data

### 2.2 Add Chart Type Support to Schema
- [x] Add `chart_type` column to `pathway_nodes` table:
  - Values: "directory" (existing), "indication" (new)
  - Update schema in `data_processing/schema.py`
- [x] Update UNIQUE constraint to include chart_type: `UNIQUE(date_filter_id, chart_type, ids)`
- [x] Add `idx_pathway_nodes_chart_type` index for filtering by chart type
- [x] Add `migrate_pathway_nodes_chart_type()` function for existing databases
- [x] Update `initialize_database()` to run migration automatically
- [x] Verify: Migration adds column, existing data defaults to "directory"

### 2.3 Create Indication Pathway Processing
- [ ] Add `process_indication_pathways()` to `pathway_pipeline.py`:
  - Group by: Trust → Search_Term → Drug → Pathway
  - For unmatched patients: use directorate name as Search_Term fallback
  - Output: Same structure as directory pathways but with indication grouping
- [ ] Add `extract_indication_fields()` for denormalized columns:
  - Extract: trust_name, search_term (or fallback_directorate), drug_sequence
- [ ] Verify: Process sample data, check hierarchy structure

---

## Phase 3: CLI & Data Refresh Updates

### 3.1 Update Refresh Command for Dual Chart Types
- [ ] Modify `cli/refresh_pathways.py`:
  - Process both "directory" and "indication" chart types
  - For each of 6 date filters: generate 2 chart datasets
  - Total: 12 pathway datasets (6 dates × 2 chart types)
- [ ] Add `--chart-type` argument: "all" (default), "directory", "indication"
- [ ] Update progress logging to show both chart types
- [ ] Verify: Dry run shows both chart types being processed

### 3.2 Integrate Diagnosis-Based Directorate in Pipeline
- [ ] Update `fetch_and_transform_data()` to include diagnosis lookup:
  - After UPID creation, batch lookup SNOMED matches for all patients
  - Store: matched_search_term, matched_directorate, match_source
- [ ] Handle Snowflake connection for GP record queries (batched for performance)
- [ ] Log coverage: X% diagnosis-matched, Y% fallback
- [ ] Verify: Test refresh with --dry-run, check coverage stats

### 3.3 Test Full Refresh Pipeline
- [ ] Run `python -m cli.refresh_pathways` with real data
- [ ] Verify pathway_nodes table has both chart_type values
- [ ] Verify indication chart has expected hierarchy (Trust → SearchTerm → Drug)
- [ ] Verify unmatched patients appear with directorate fallback label
- [ ] Document: Processing time, record counts, coverage percentages

---

## Phase 4: Reflex UI Updates

### 4.1 Add Chart Type State
- [ ] Add state variables to `AppState`:
  - `selected_chart_type: str = "directory"` (options: "directory", "indication")
  - `chart_type_options: list[dict]` for dropdown
- [ ] Add `set_chart_type()` event handler
- [ ] Update `load_pathway_data()` to filter by chart_type
- [ ] Verify: State changes correctly, data queries include chart_type filter

### 4.2 Add Chart Type Toggle UI
- [ ] Create `chart_type_toggle()` component:
  - Radio buttons or segmented control: "By Directory" | "By Indication"
  - Place in filter strip or chart header area
- [ ] Wire to `set_chart_type()` handler
- [ ] Verify: Toggle switches chart data, UI updates reactively

### 4.3 Update Chart Display for Indication Labels
- [ ] Ensure icicle chart handles mixed labels:
  - Search_Term labels (e.g., "rheumatoid arthritis") for matched patients
  - Directorate labels (e.g., "RHEUMATOLOGY (no GP dx)") for unmatched
- [ ] Update hover templates if needed for indication context
- [ ] Verify: Chart renders correctly with both label types

---

## Phase 5: Validation & Documentation

### 5.1 Measure Coverage Improvement
- [ ] Compare match rates: cluster-only vs cluster+direct SNOMED
- [ ] Generate report: % of patients with diagnosis-based directorate
- [ ] Identify drugs with best/worst coverage improvement
- [ ] Document results in progress.txt

### 5.2 End-to-End Validation
- [ ] Run full app with both chart types
- [ ] Verify chart toggle works correctly
- [ ] Verify filter interactions (drugs, directorates) work for both types
- [ ] Verify KPIs update correctly for both chart types
- [ ] Test at multiple viewport sizes

### 5.3 Update Documentation
- [ ] Update CLAUDE.md with new architecture
- [ ] Document new CLI arguments
- [ ] Document chart_type toggle behavior
- [ ] Update data flow diagrams

---

## Completion Criteria

All tasks marked `[x]` AND:
- [ ] App compiles without errors (`reflex compile` succeeds)
- [ ] Both chart types generate pathway data (12 total: 6 dates × 2 types)
- [ ] Chart type toggle switches between Directory and Indication views
- [ ] Diagnosis-based directorate is primary method with fallback working
- [ ] Unmatched patients show in indication chart with directorate fallback label
- [ ] Coverage metrics logged (% diagnosis-matched vs fallback)
- [ ] All filters work correctly for both chart types
- [ ] Performance acceptable (< 10 min full refresh, < 500ms filter change)

---

## Reference

### Current Pathway Hierarchy (Directory-based)
```
Root (N&W ICS)
└── Trust (NNUH, QEH, JPH, etc.)
    └── Directory (RHEUMATOLOGY, OPHTHALMOLOGY, etc.)
        └── Drug (ADALIMUMAB, RANIBIZUMAB, etc.)
            └── Pathway (drug sequences)
```

### New Pathway Hierarchy (Indication-based)
```
Root (N&W ICS)
└── Trust (NNUH, QEH, JPH, etc.)
    └── Search_Term (rheumatoid arthritis, macular degeneration, etc.)
        │   OR Directorate (RHEUMATOLOGY - for unmatched patients)
        └── Drug (ADALIMUMAB, RANIBIZUMAB, etc.)
            └── Pathway (drug sequences)
```

### Key Files

| File | Purpose |
|------|---------|
| `data_processing/schema.py` | SQLite schema for ref_drug_snomed_mapping |
| `data_processing/diagnosis_lookup.py` | Direct SNOMED lookup functions |
| `data_processing/pathway_pipeline.py` | Indication pathway processing |
| `cli/refresh_pathways.py` | CLI for dual chart type refresh |
| `pathways_app/pathways_app.py` | Reflex UI with chart type toggle |
| `data/drug_snomed_mapping_enriched.csv` | Source mapping data |

### Expected Data Volumes

| Metric | Expected |
|--------|----------|
| SNOMED mapping rows | ~163K |
| Unique Search_Terms | 187 |
| Unique drugs | ~364 |
| Pathway nodes (directory, per date filter) | ~300 |
| Pathway nodes (indication, per date filter) | ~400-600 (more granular) |
| Total pathway nodes (6 dates × 2 types) | ~4,000-5,000 |
