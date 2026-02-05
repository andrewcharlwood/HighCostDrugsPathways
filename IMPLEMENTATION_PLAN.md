# Implementation Plan - Drug-Aware Indication Matching

## Project Overview

Update the indication-based pathway charts so that patient indications are matched **per drug**, not just per patient. Currently, each patient gets ONE indication (most recent GP diagnosis match). This ignores which drugs the patient is actually taking.

### The Problem

A patient on ADALIMUMAB + OMALIZUMAB currently gets assigned a single indication (e.g., "rheumatoid arthritis" — the most recent GP match). But:
- ADALIMUMAB is used for rheumatoid arthritis, axial spondyloarthritis, crohn's disease, etc.
- OMALIZUMAB is used for asthma, allergic asthma, urticaria

These are different clinical pathways and should be treated as separate treatment journeys.

### The Solution

Match each drug to an indication by cross-referencing:
1. **GP diagnosis** — which Search_Terms the patient has matching SNOMED codes for
2. **Drug mapping** — which Search_Terms list each drug (from `DimSearchTerm.csv`)

Only assign a drug to an indication if BOTH conditions are met. If a patient's drugs map to different indications, they become separate pathways (via modified UPID).

### Key Design Decisions

| Aspect | Decision |
|--------|----------|
| Drug-indication source | `data/DimSearchTerm.csv` — Search_Term → CleanedDrugName mapping |
| UPID modification | `{original_UPID}\|{search_term}` for drugs with matched indication |
| GP diagnosis matching | Return ALL matches per patient (not just most recent) |
| Drug matching | Substring match: HCD drug name contains DimSearchTerm fragment |
| Multiple indication matches per drug | Use highest GP code frequency as tiebreaker (COUNT of matching SNOMED codes per Search_Term) |
| GP code time range | Only codes from MIN(Intervention Date) onwards — restricts to HCD data window |
| No indication match | Fallback to directory (same as current behavior) |
| Same patient, different indications | Separate pathways via different modified UPIDs |

### Examples

**Patient on ADALIMUMAB + GOLIMUMAB, GP dx: axial spondyloarthritis + asthma**
- axial spondyloarthritis drug list includes both ADALIMUMAB and GOLIMUMAB
- → Both drugs grouped under "axial spondyloarthritis", single pathway
- Modified UPID: `RMV12345|axial spondyloarthritis`

**Patient on ADALIMUMAB + OMALIZUMAB, GP dx: axial spondyloarthritis + asthma**
- axial spondyloarthritis lists ADALIMUMAB but not OMALIZUMAB
- asthma lists OMALIZUMAB but not ADALIMUMAB
- → Two separate pathways:
  - `RMV12345|axial spondyloarthritis` with ADALIMUMAB
  - `RMV12345|asthma` with OMALIZUMAB

**Patient on ADALIMUMAB, GP dx: rheumatoid arthritis (47 codes) + crohn's disease (2 codes)**
- Both Search_Terms list ADALIMUMAB AND patient has GP dx for both
- → Tiebreaker: highest code frequency — rheumatoid arthritis has 47 matching SNOMED codes vs 2 for crohn's
- → Single pathway under rheumatoid arthritis (more clinical activity = more likely the treatment indication)

---

## Phase 1: Update Snowflake Query & Drug Mapping

### 1.1 Update `get_patient_indication_groups()` to return ALL matches with frequency
- [ ] Modify the Snowflake query in `get_patient_indication_groups()` (diagnosis_lookup.py):
  - Remove `QUALIFY ROW_NUMBER() OVER (PARTITION BY ... ORDER BY EventDateTime DESC) = 1`
  - Return ALL matching Search_Terms per patient with code frequency:
    ```sql
    SELECT pc."PatientPseudonym" AS "PatientPseudonym",
           aic.Search_Term AS "Search_Term",
           COUNT(*) AS "code_frequency"
    FROM PrimaryCareClinicalCoding pc
    JOIN AllIndicationCodes aic ON pc."SNOMEDCode" = aic.SNOMEDCode
    WHERE pc."PatientPseudonym" IN (...)
      AND pc."EventDateTime" >= :earliest_hcd_date
    GROUP BY pc."PatientPseudonym", aic.Search_Term
    ```
  - `code_frequency` = number of matching SNOMED codes per Search_Term per patient
  - Higher frequency = more clinical activity = stronger signal for tiebreaker
  - `earliest_hcd_date` = `MIN(Intervention Date)` from the HCD DataFrame — restricts GP codes to the HCD data window, reducing noise from old/irrelevant diagnoses
- [ ] Accept `earliest_hcd_date` parameter in `get_patient_indication_groups()` and pass to query
- [ ] Keep batch processing (500 patients per query)
- [ ] Update return type: DataFrame now has multiple rows per patient (PatientPseudonym, Search_Term, code_frequency)
- [ ] Verify: Query returns more rows than before (patients with multiple matching diagnoses)

### 1.2 Merge related asthma Search_Terms in CLUSTER_MAPPING_SQL
- [x] In `CLUSTER_MAPPING_SQL` (diagnosis_lookup.py), merge these 3 Search_Terms into one `"asthma"` entry:
  - `allergic asthma` (Cluster: OMALIZUMAB only)
  - `asthma` (Cluster: BENRALIZUMAB, DUPILUMAB, INHALED, MEPOLIZUMAB, OMALIZUMAB, RESLIZUMAB)
  - `severe persistent allergic asthma` (Cluster: OMALIZUMAB only)
- [x] Map all 3 Cluster_IDs to `Search_Term = 'asthma'` in the CTE VALUES
- [x] `urticaria` (OMALIZUMAB, DERMATOLOGY) stays SEPARATE — do NOT merge with asthma
- [x] Also update `load_drug_indication_mapping()` to apply the same merge when loading DimSearchTerm.csv:
  - Combine drug lists from all 3 entries under a single `"asthma"` key
  - Deduplicate drug fragments (OMALIZUMAB appears in all 3)
- [x] Verify: GP code lookup returns `"asthma"` (not `"allergic asthma"` or `"severe persistent allergic asthma"`)
- [x] Verify: Drug mapping for `"asthma"` includes full combined drug list: BENRALIZUMAB, DUPILUMAB, INHALED, MEPOLIZUMAB, OMALIZUMAB, RESLIZUMAB

### 1.3 Build drug-to-Search_Term lookup from DimSearchTerm.csv
- [x] Add function `load_drug_indication_mapping()` to `diagnosis_lookup.py`:
  - Loads `data/DimSearchTerm.csv`
  - Builds dict: `drug_fragment (uppercase) → list[Search_Term]`
  - Also builds reverse: `search_term → list[drug_fragments]`
  - CleanedDrugName is pipe-separated (e.g., "ADALIMUMAB|GOLIMUMAB|IXEKIZUMAB")
- [x] Add function `get_search_terms_for_drug(drug_name, search_term_to_fragments) -> list[str]`:
  - Returns all Search_Terms whose drug fragments are substrings of the drug name (case-insensitive)
  - More practical than per-term boolean check — returns all matches at once for Phase 2 use
- [x] Verify: ADALIMUMAB matches "axial spondyloarthritis", OMALIZUMAB matches "asthma"

---

## Phase 2: Drug-Aware Indication Matching Logic

### 2.1 Create `assign_drug_indications()` function
- [ ] Add to `diagnosis_lookup.py` or `pathway_pipeline.py`:
  ```
  def assign_drug_indications(
      df: pd.DataFrame,              # HCD data with UPID, Drug Name columns
      gp_matches_df: pd.DataFrame,   # PatientPseudonym → list of matched Search_Terms
      drug_mapping: dict,             # From load_drug_indication_mapping()
  ) -> tuple[pd.DataFrame, pd.DataFrame]:
      Returns: (modified_df, indication_df)
      - modified_df: HCD data with UPID replaced by {UPID}|{indication}
      - indication_df: mapping modified_UPID → Search_Term
  ```
- [ ] Logic per UPID + Drug Name pair:
  1. Get patient's GP-matched Search_Terms with code_frequency (from gp_matches_df via PseudoNHSNoLinked)
  2. Get which Search_Terms include this drug (from drug_mapping)
  3. Intersection = valid indications for this drug-patient pair
  4. If 1 match: use it
  5. If multiple matches: use highest code_frequency as tiebreaker (most GP coding activity = most likely treatment indication)
  6. If 0 matches: use fallback directory
- [ ] Modify UPID in df rows: `{original_UPID}|{matched_search_term}`
- [ ] Build indication_df: `{modified_UPID}` → `Search_Term` (or fallback label)
- [ ] Verify: Function compiles, handles edge cases (no GP match, no drug match)

### 2.2 Handle tiebreaker for multiple indication matches
- [ ] When a drug matches multiple Search_Terms AND patient has GP dx for multiple:
  - Use `code_frequency` from the GP query (COUNT of matching SNOMED codes per Search_Term)
  - Higher code_frequency = more clinical activity for that condition = more likely treatment indication
  - E.g., patient with 47 RA codes and 2 crohn's codes → ADALIMUMAB assigned to RA
  - code_frequency is already returned by the updated query in Task 1.1
- [ ] Verify: Tiebreaker logic correctly picks highest-frequency diagnosis
- [ ] Verify: Tie on frequency (rare but possible) falls back to alphabetical Search_Term for determinism

---

## Phase 3: Pipeline Integration

### 3.1 Update `refresh_pathways.py` indication processing
- [ ] In the `elif current_chart_type == "indication":` block:
  1. Call `get_patient_indication_groups()` as before (but now returns ALL matches)
  2. Load drug mapping: `drug_mapping = load_drug_indication_mapping()`
  3. Call `assign_drug_indications(df, gp_matches_df, drug_mapping)`
  4. Use modified_df (with indication-aware UPIDs) for pathway processing
  5. Use indication_df for the indication mapping
- [ ] Pass modified_df (not original df) to `process_indication_pathway_for_date_filter()`
- [ ] Verify: Pipeline compiles, `python -m py_compile cli/refresh_pathways.py`

### 3.2 Test with dry run
- [ ] Run `python -m cli.refresh_pathways --chart-type indication --dry-run -v`
- [ ] Verify:
  - Modified UPIDs appear in pipeline log (e.g., `RMV12345|rheumatoid arthritis`)
  - Patient counts are reasonable (will be higher than before since same patient can appear under multiple indications)
  - Drug-indication matching is logged (match rate, fallback rate)
  - Pathway hierarchy shows drug-specific grouping under correct indications

---

## Phase 4: Full Refresh & Validation

### 4.1 Full refresh with both chart types
- [ ] Run `python -m cli.refresh_pathways --chart-type all`
- [ ] Verify:
  - Both chart types generate data
  - Directory charts unchanged (no modified UPIDs)
  - Indication charts reflect drug-aware matching

### 4.2 Validate indication chart correctness
- [ ] Check that drugs under an indication all appear in that Search_Term's drug list
- [ ] Verify that a patient on drugs for different indications creates separate pathway branches
- [ ] Verify that drugs sharing an indication are grouped in the same pathway
- [ ] Log: patient count comparison (old vs new approach)

### 4.3 Validate Reflex UI
- [ ] Run `python -m reflex compile` to verify app compiles
- [ ] Verify chart type toggle still works
- [ ] Verify indication chart shows correct hierarchy

---

## Completion Criteria

All tasks marked `[x]` AND:
- [ ] App compiles without errors (`reflex compile` succeeds)
- [ ] Both chart types generate pathway data
- [ ] Indication charts show drug-specific indication matching
- [ ] Drugs under the same indication for the same patient are in one pathway
- [ ] Drugs under different indications for the same patient create separate pathways
- [ ] Fallback works for drugs with no indication match
- [ ] Full refresh completes successfully
- [ ] Existing directory charts are unaffected

---

## Reference

### DimSearchTerm.csv Structure
```
Search_Term,CleanedDrugName,PrimaryDirectorate
rheumatoid arthritis,ABATACEPT|ADALIMUMAB|ANAKINRA|BARICITINIB|...,RHEUMATOLOGY
asthma,BENRALIZUMAB|DUPILUMAB|INHALED|MEPOLIZUMAB|OMALIZUMAB|RESLIZUMAB,THORACIC MEDICINE
```

### Modified UPID Format
```
Original:  RMV12345
Modified:  RMV12345|rheumatoid arthritis
Fallback:  RMV12345|RHEUMATOLOGY (no GP dx)
```

### Current vs New Indication Flow
```
CURRENT:
  Patient → GP dx (most recent) → single Search_Term → one pathway

NEW:
  Patient + Drug A → GP dx matching Drug A → Search_Term X
  Patient + Drug B → GP dx matching Drug B → Search_Term Y
  → If X == Y: one pathway under X
  → If X != Y: two pathways (modified UPIDs)
```

### Key Files

| File | Changes |
|------|---------|
| `data_processing/diagnosis_lookup.py` | Update query, add drug mapping functions |
| `data_processing/pathway_pipeline.py` | Possibly minor changes for modified UPIDs |
| `cli/refresh_pathways.py` | Integrate drug-aware matching into pipeline |
| `data/DimSearchTerm.csv` | Reference data (read-only) |
| `analysis/pathway_analyzer.py` | No changes expected (UPID changes are transparent) |
| `pathways_app/pathways_app.py` | No changes expected |
