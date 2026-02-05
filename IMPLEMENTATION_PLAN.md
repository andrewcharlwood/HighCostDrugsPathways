# Implementation Plan - Indication-Based Pathway Charts

## Project Overview

Extend the pathway analysis application to show indication-based icicle charts alongside directory-based charts. Patient diagnoses are matched from GP records using SNOMED cluster codes.

### Key Design Decisions
| Aspect | Decision |
|--------|----------|
| SNOMED source | Query `ClinicalCodingClusterSnomedCodes` clusters directly in Snowflake |
| Grouping level | `Search_Term` from cluster mapping (~148 conditions) |
| Chart types | Two: "By Directory" (existing) and "By Indication" (new toggle) |
| No-match display | Show assigned directorate in indication chart (mixed labels) |
| Multiple matches | Use most recent SNOMED code by GP record date |
| Data storage | No local SNOMED mapping — query Snowflake at refresh time |

### SNOMED Cluster Query
The `snomed_indication_mapping_query.sql` file contains the master query:
- Maps Search_Term → Cluster_ID for ~148 conditions
- Joins `ClinicalCodingClusterSnomedCodes` to get SNOMED codes per cluster
- Includes explicit manual mappings for conditions not in clusters
- Returns: Search_Term, SNOMEDCode, SNOMEDDescription

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

## Phase 1: Snowflake Integration

### 1.1 Create Indication Lookup Query
- [x] Add `get_patient_indication_groups()` function to `data_processing/diagnosis_lookup.py`:
  - Takes: list of patient pseudonyms (PseudoNHSNoLinked values)
  - Uses the cluster query from `snomed_indication_mapping_query.sql` as a CTE
  - Joins with `PrimaryCareClinicalCoding` to find patients with matching diagnoses
  - Returns: DataFrame with PatientPseudonym, Search_Term, EventDateTime
  - Uses most recent match per patient (ORDER BY EventDateTime DESC)
- [x] Handle edge cases: Snowflake unavailable, empty patient list
- [ ] Verify: Function returns expected Search_Terms for test patients

### 1.2 Update Data Pipeline to Include Indications
- [ ] Modify `cli/refresh_pathways.py` to call indication lookup during refresh:
  - After fetching HCD data, extract unique PseudoNHSNoLinked values
  - Call `get_patient_indication_groups()` with patient list
  - Create `indication_df` mapping UPID → Indication_Group
  - For patients with no GP match: Indication_Group = fallback directorate
- [ ] Log coverage: X% diagnosis-matched, Y% fallback
- [ ] Verify: indication_df has correct structure for pathway processing

---

## Phase 2: Schema & Processing Updates

### 2.1 Add Chart Type Support to Schema
- [x] Add `chart_type` column to `pathway_nodes` table (ALREADY DONE)
- [x] Update UNIQUE constraint to include chart_type (ALREADY DONE)
- [x] Add indexes for chart_type filtering (ALREADY DONE)
- [ ] Verify: Existing migration works correctly

### 2.2 Create Indication Pathway Processing
- [x] Add `generate_icicle_chart_indication()` to `pathway_analyzer.py` (ALREADY DONE)
- [x] Add `process_indication_pathway_for_date_filter()` to `pathway_pipeline.py` (ALREADY DONE)
- [x] Add `extract_indication_fields()` for denormalized columns (ALREADY DONE)
- [x] Update `convert_to_records()` with `chart_type` parameter (ALREADY DONE)
- [ ] Verify: Code compiles, imports work correctly

### 2.3 Update Refresh Command for Dual Charts
- [x] Add `--chart-type` argument: "all", "directory", "indication" (ALREADY DONE)
- [ ] Update indication processing to use new `get_patient_indication_groups()`:
  - Replace `batch_lookup_indication_groups()` with the new Snowflake-direct approach
  - Pass indication_df to `process_indication_pathway_for_date_filter()`
- [ ] Process all 6 date filters for both chart types
- [ ] Verify: Both chart types generate pathway data

---

## Phase 3: Test Full Pipeline

### 3.1 Test Refresh with Real Data
- [ ] Run `python -m cli.refresh_pathways --chart-type all` with Snowflake
- [ ] Verify pathway_nodes table has both chart_type values:
  - `SELECT chart_type, COUNT(*) FROM pathway_nodes GROUP BY chart_type`
- [ ] Verify indication hierarchy: Trust → Search_Term → Drug → Pathway
- [ ] Verify unmatched patients show with directorate fallback label
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

### 5.1 End-to-End Validation
- [ ] Run full app with both chart types
- [ ] Verify chart toggle works correctly
- [ ] Verify filter interactions (drugs, directorates) work for both types
- [ ] Verify KPIs update correctly for both chart types
- [ ] Test at multiple viewport sizes

### 5.2 Update Documentation
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
- [ ] GP diagnosis matching works via Snowflake cluster query
- [ ] Unmatched patients show in indication chart with directorate fallback label
- [ ] Coverage metrics logged (% diagnosis-matched vs fallback)
- [ ] All filters work correctly for both chart types
- [ ] Performance acceptable (< 10 min full refresh, < 500ms filter change)

---

## Reference

### SNOMED Cluster Query Structure
```sql
-- From snomed_indication_mapping_query.sql
WITH SearchTermClusters AS (
    SELECT Search_Term, Cluster_ID FROM (VALUES
        ('rheumatoid arthritis', 'eFI2_InflammatoryArthritis'),
        ('macular degeneration', 'CUST_ICB_VISUAL_IMPAIRMENT'),
        -- ... ~148 mappings
    ) AS t(Search_Term, Cluster_ID)
),
ClusterCodes AS (
    SELECT stc.Search_Term, c."SNOMEDCode", c."SNOMEDDescription"
    FROM SearchTermClusters stc
    JOIN DATA_HUB.PHM."ClinicalCodingClusterSnomedCodes" c
        ON stc.Cluster_ID = c."Cluster_ID"
    WHERE c."SNOMEDCode" IS NOT NULL
),
ExplicitCodes AS (
    -- Manual mappings for conditions not in clusters
    SELECT Search_Term, SNOMEDCode, SNOMEDDescription FROM (VALUES
        ('ankylosing spondylitis', '162930007', 'Manual mapping'),
        -- ...
    ) AS t(Search_Term, SNOMEDCode, SNOMEDDescription)
)
SELECT * FROM ClusterCodes
UNION ALL
SELECT * FROM ExplicitCodes
```

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
| `snomed_indication_mapping_query.sql` | Master SNOMED cluster query |
| `data_processing/diagnosis_lookup.py` | GP diagnosis lookup functions |
| `data_processing/pathway_pipeline.py` | Indication pathway processing |
| `cli/refresh_pathways.py` | CLI for dual chart type refresh |
| `pathways_app/pathways_app.py` | Reflex UI with chart type toggle |

### Expected Data Volumes

| Metric | Expected |
|--------|----------|
| Search_Term conditions | ~148 (from cluster mapping) |
| Pathway nodes (directory, per date filter) | ~300 |
| Pathway nodes (indication, per date filter) | ~400-600 (more granular) |
| Total pathway nodes (6 dates × 2 types) | ~4,000-5,000 |
