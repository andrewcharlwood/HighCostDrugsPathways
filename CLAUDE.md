# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NHS High-Cost Drug Patient Pathway Analysis Tool - a web-based application that analyzes secondary care patient treatment pathways. It processes clinical activity data to visualize hierarchical treatment patterns as interactive Plotly icicle charts.

**Key Features:**
- **Dual chart types**: Directory-based (Trust → Directory → Drug → Pathway) and Indication-based (Trust → GP Diagnosis → Drug → Pathway) views with toggle
- **Pre-computed pathway architecture**: Treatment pathways pre-processed and stored in SQLite for instant filtering
- **GP diagnosis matching**: Patient indications matched from GP records using SNOMED cluster codes queried directly from Snowflake (~93% match rate)
- Multi-source data loading: CSV/Parquet files, SQLite database, Snowflake data warehouse
- Interactive browser-based UI using Reflex framework
- 6 pre-defined date filter combinations × 2 chart types = 12 pre-computed datasets with sub-50ms response times

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt
# OR with uv
uv sync

# Initialize/migrate the database (creates pathway tables)
python -m data_processing.migrate

# Refresh pathway data from Snowflake (requires SSO auth)
python -m cli.refresh_pathways

# Run the Reflex web application
reflex run
```

The application requires Python 3.10+ and runs on http://localhost:3000 by default.

### CLI Commands

**Refresh Pathway Data:**
```bash
# Full refresh — both chart types (directory + indication), all date filters
python -m cli.refresh_pathways --chart-type all

# Directory charts only (faster, skips GP diagnosis lookup)
python -m cli.refresh_pathways --chart-type directory

# Indication charts only
python -m cli.refresh_pathways --chart-type indication

# Dry run (test without database changes)
python -m cli.refresh_pathways --chart-type all --dry-run -v

# Custom minimum patient threshold
python -m cli.refresh_pathways --minimum-patients 10

# Help
python -m cli.refresh_pathways --help
```

The `--chart-type` argument controls which pathway types are processed:
- `all` (default) — generates both directory and indication charts (~15 minutes)
- `directory` — directory-based charts only (~5 minutes)
- `indication` — indication-based charts only (~12 minutes, includes GP lookup)

The refresh command:
1. Fetches activity data from Snowflake (656K+ records, ~7 seconds)
2. Applies UPID, drug name, and directory transformations (~6 minutes)
3. For indication charts: queries GP records via SNOMED clusters (~9 minutes for 37K patients)
4. Processes 6 date filter combinations × selected chart types
5. Inserts pathway nodes to SQLite for fast Reflex filtering

## Architecture

### Package Structure

```
.
├── core/                    # Core configuration and models
│   ├── config.py           # PathConfig dataclass for file paths
│   ├── models.py           # AnalysisFilters dataclass
│   └── logging_config.py   # Structured logging setup
│
├── cli/                     # Command-line interface tools
│   ├── __init__.py
│   └── refresh_pathways.py # CLI to refresh pre-computed pathway data
│
├── data_processing/         # Data layer
│   ├── database.py         # SQLite connection management
│   ├── schema.py           # Database schema (including pathway tables)
│   ├── pathway_pipeline.py # Pathway processing pipeline (Snowflake → SQLite)
│   ├── loader.py           # DataLoader abstraction (CSV/SQLite)
│   ├── patient_data.py     # Patient data migration and loading
│   ├── reference_data.py   # Reference data migration
│   ├── snowflake_connector.py  # Snowflake integration
│   ├── cache.py            # Query result caching
│   ├── data_source.py      # Data source fallback chain
│   └── diagnosis_lookup.py # GP diagnosis validation
│
├── analysis/                # Analysis pipeline
│   ├── pathway_analyzer.py # prepare_data, calculate_statistics, build_hierarchy
│   └── statistics.py       # Statistical calculation functions
│
├── visualization/           # Chart generation
│   └── plotly_generator.py # create_icicle_figure, save_figure_html
│
├── pathways_app/           # Reflex web application
│   ├── pathways_app.py     # State class and page components
│   └── components/         # Layout and navigation components
│
├── tools/                   # Legacy modules
│   ├── dashboard_gui.py    # Original analysis engine (being refactored)
│   └── data.py             # Data transformations (UPID, drug names, directory)
│
├── config/                  # Configuration files
│   └── snowflake.toml      # Snowflake connection settings
│
├── data/                    # Reference data and database
│   ├── pathways.db         # SQLite database (includes pathway_nodes)
│   └── *.csv               # Reference data files
│
└── tests/                   # Test suite
    ├── conftest.py         # Pytest fixtures
    └── test_*.py           # Test modules
```

### Pathway Data Architecture

The application uses a pre-computed pathway architecture for performance:

**Architecture:** `Snowflake → Pathway Processing → SQLite (pre-computed) → Reflex (filter & view)`

**Key Benefits:**
- **Performance**: Pathway calculation done once during data refresh, not on every filter change
- **Simplicity**: Reflex filters pre-computed data with simple SQL WHERE clauses
- **Full Pathways**: Sequential treatment pathways (drug_0 → drug_1 → drug_2...) with statistics

**Chart Types:**

| Type | Hierarchy | Level 2 Source |
|------|-----------|----------------|
| `directory` | Trust → Directory → Drug → Pathway | Assigned directorate (5-level fallback) |
| `indication` | Trust → GP Diagnosis → Drug → Pathway | SNOMED cluster Search_Term from GP records |

For indication charts, ~93% of patients are matched to a GP diagnosis (Search_Term). Unmatched patients use their directorate as a fallback label (e.g., "RHEUMATOLOGY (no GP dx)").

**Date Filter Combinations:**
| ID | Initiated | Last Seen | Default |
|----|-----------|-----------|---------|
| `all_6mo` | All years | Last 6 months | Yes |
| `all_12mo` | All years | Last 12 months | No |
| `1yr_6mo` | Last 1 year | Last 6 months | No |
| `1yr_12mo` | Last 1 year | Last 12 months | No |
| `2yr_6mo` | Last 2 years | Last 6 months | No |
| `2yr_12mo` | Last 2 years | Last 12 months | No |

Total pre-computed datasets: 6 date filters × 2 chart types = 12 datasets (~3,600 pathway nodes).

**Pathway Node Structure:**
Each node in `pathway_nodes` contains:
- Routing: `chart_type` ("directory" or "indication"), `date_filter_id`
- Hierarchy: `parents`, `ids`, `labels`, `level` (0=Root, 1=Trust, 2=Directory/Indication, 3=Drug, 4+=Pathway)
- Counts: `value` (patient count)
- Costs: `cost`, `costpp`, `cost_pp_pa` (per patient per annum)
- Dates: `first_seen`, `last_seen`, `first_seen_parent`, `last_seen_parent`
- Statistics: `average_spacing`, `average_administered`, `avg_days`
- Denormalized: `trust_name`, `directory`, `drug_sequence` (for efficient filtering)
- Unique constraint: `UNIQUE(date_filter_id, chart_type, ids)`

### Core Module (`core/`)

- **PathConfig** - Dataclass encapsulating all file paths, with `validate()` method
- **AnalysisFilters** - Dataclass for filter state (dates, drugs, trusts, directories)
- **logging_config** - Structured logging with file and console output

### CLI Module (`cli/`)

- **refresh_pathways.py** - Command-line tool to refresh pre-computed pathway data:
  - `refresh_pathways()` - Main function orchestrating the full pipeline
  - `insert_pathway_records()` - SQLite insertion with parameterized queries
  - `log_refresh_start/complete/failed()` - Refresh tracking in `pathway_refresh_log`
  - `get_default_filters()` - Load trusts/drugs/directories from CSV files

### Data Processing Module (`data_processing/`)

**Database Management:**
- `DatabaseManager` - SQLite connection pooling and transaction management
- Tables: `ref_drug_names`, `ref_organizations`, `ref_directories`, `ref_drug_directory_map`, `ref_drug_indication_clusters`, `fact_interventions`, `mv_patient_treatment_summary`, `processed_files`
- **Pathway Tables**: `pathway_date_filters`, `pathway_nodes`, `pathway_refresh_log`

**Pathway Pipeline (`pathway_pipeline.py`):**
- `DateFilterConfig` - Dataclass for date filter configuration
- `DATE_FILTER_CONFIGS` - All 6 pre-defined date combinations
- `compute_date_ranges(config, max_date)` - Computes actual ISO dates from config
- `fetch_and_transform_data()` - Snowflake fetch + UPID/drug/directory transformations
- Directory chart functions:
  - `process_pathway_for_date_filter()` - Processes single date filter using `generate_icicle_chart()`
  - `extract_denormalized_fields()` - Parses `ids` column to extract trust, directory, drug_sequence
- Indication chart functions:
  - `process_indication_pathway_for_date_filter()` - Processes single date filter using `generate_icicle_chart_indication()`
  - `extract_indication_fields()` - Parses `ids` for indication charts (trust, search_term, drug_sequence)
- Shared functions:
  - `convert_to_records(ice_df, chart_type)` - Converts ice_df to list of dicts with `chart_type` column
  - `process_all_date_filters()` - Convenience function to process all 6 filters

**Data Loaders:**
- `FileDataLoader` - Loads from CSV/Parquet files
- `SQLiteDataLoader` - Queries fact_interventions table
- Factory function `get_loader()` selects appropriate loader

**Snowflake Integration:**
- SSO authentication via `externalbrowser` authenticator
- `fetch_activity_data(start_date, end_date, provider_codes)` method
- Query caching with TTL-based invalidation
- Fallback chain: cache → Snowflake → local files

**GP Diagnosis Lookup (`diagnosis_lookup.py`):**
- `CLUSTER_MAPPING_SQL` - Embedded SQL constant with ~148 Search_Term → Cluster_ID mappings plus explicit SNOMED codes
- `get_patient_indication_groups(patient_pseudonyms)` - Batch queries Snowflake to match patients to GP diagnoses:
  - Embeds cluster mapping as CTE, joins with `PrimaryCareClinicalCoding`
  - Uses `PseudoNHSNoLinked` (not PersonKey) to match `PatientPseudonym` in GP records
  - Returns most recent match per patient via `QUALIFY ROW_NUMBER()`
  - Batches 500 patients per query, returns DataFrame with PatientPseudonym, Search_Term, EventDateTime
- `patient_has_indication(patient_pseudonym, cluster_ids)` - Single-patient GP record check (legacy)
- `validate_indication(patient_pseudonym, drug_name)` - Full validation result with source tracking (legacy)

### Analysis Module (`analysis/`)

Refactored from the original 267-line `generate_graph()` function:

- **prepare_data()** - Filter DataFrame by date range, trusts, drugs, directories (copies df to prevent mutation)
- **calculate_statistics()** - Compute frequency, cost, duration statistics
- **build_hierarchy()** - Create Trust → Directory → Drug → Pathway structure
- **prepare_chart_data()** - Format data for Plotly icicle chart
- **generate_icicle_chart_indication(df, indication_df, ...)** - Build indication-based hierarchy using Search_Term instead of Directory. Takes an `indication_df` (UPID → Search_Term mapping) alongside the main activity DataFrame.

### Visualization Module (`visualization/`)

- **create_icicle_figure()** - Generate Plotly icicle chart figure
- **save_figure_html()** - Save interactive HTML file
- **open_figure_in_browser()** - Open chart in default browser

### Reflex Application (`pathways_app/`)

The `AppState` class manages all application state:
- **Chart type**: `selected_chart_type` ("directory" or "indication"), toggled via `set_chart_type()`
- **Computed vars**: `chart_hierarchy_label` (dynamic "Trust → Directorate → ..." or "Trust → Indication → ..."), `chart_type_label`
- Filter variables: dates, drugs, trusts, directories
- Reference data: available options loaded from CSV/SQLite
- Analysis state: running flag, status messages, chart data
- Data source state: file path, source type, row counts

**Chart Type Toggle** (`chart_type_toggle()` component):
- Segmented control with "By Directory" and "By Indication" pill buttons
- Placed first in the filter strip before date filters
- Switching reloads pathway data from SQLite filtered by `chart_type`
- Note: Directory filter only applies to directory charts (indication charts store Search_Terms in the directory column)

### Legacy Modules (`tools/`)

Still used during transition:

- **tools/data.py** - Data transformation functions:
  - `patient_id()` - Creates UPID = Provider Code (first 3 chars) + PersonKey
  - `drug_names()` - Standardizes via drugnames.csv lookup
  - `department_identification()` - 5-level fallback chain for directory assignment

- **tools/dashboard_gui.py** - Original analysis engine (being replaced by `analysis/` module)

### Data Flow

**Pre-Computed Pathway Architecture (Current):**

```
[CLI: python -m cli.refresh_pathways --chart-type all]

    Snowflake Data Warehouse
           │
           ▼ (fetch_and_transform_data)
    ┌──────────────────────────────────────────┐
    │ Data Transformations (tools/data.py)     │
    │   → patient_id() creates UPID            │
    │   → drug_names() standardizes names      │
    │   → department_identification() → Dir    │
    └──────────────────────────────────────────┘
           │
           ├─── Directory Charts ──────────────────────────────────────┐
           │                                                           │
           │    ┌──────────────────────────────────────────┐           │
           │    │ For each of 6 date filter combos:        │           │
           │    │   → generate_icicle_chart()              │           │
           │    │   → extract_denormalized_fields()        │           │
           │    │   → convert_to_records("directory")      │           │
           │    └──────────────────────────────────────────┘           │
           │                                                           │
           ├─── Indication Charts ─────────────────────────────────────┤
           │                                                           │
           │    ┌──────────────────────────────────────────┐           │
           │    │ GP Diagnosis Lookup (diagnosis_lookup.py)│           │
           │    │   → Extract PseudoNHSNoLinked from HCD   │           │
           │    │   → get_patient_indication_groups()      │           │
           │    │     (SNOMED cluster CTE + GP records)    │           │
           │    │   → Build indication_df: UPID → Search   │           │
           │    │     Term (matched) or Directorate (no GP)│           │
           │    └──────────────────────────────────────────┘           │
           │                        │                                  │
           │                        ▼                                  │
           │    ┌──────────────────────────────────────────┐           │
           │    │ For each of 6 date filter combos:        │           │
           │    │   → generate_icicle_chart_indication()   │           │
           │    │   → extract_indication_fields()          │           │
           │    │   → convert_to_records("indication")     │           │
           │    └──────────────────────────────────────────┘           │
           │                                                           │
           └───────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼ (insert_pathway_records)
    ┌──────────────────────────────────────────┐
    │ SQLite: pathway_nodes table              │
    │   → ~3,600 nodes across 12 datasets      │
    │   → UNIQUE(date_filter_id, chart_type,   │
    │     ids) prevents cross-type overwrites  │
    │   → Indexed for fast filtering           │
    └──────────────────────────────────────────┘


[Reflex App: reflex run]

    ┌──────────────────────────────────────────┐
    │ Chart Type Toggle (segmented control)    │
    │   → "By Directory" | "By Indication"     │
    │   → Triggers set_chart_type() handler    │
    └──────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ AppState.load_pathway_data()             │
    │   → Query pathway_nodes WHERE            │
    │     date_filter AND chart_type            │
    │   → Apply drug/directory filters         │
    │   → recalculate_parent_totals()          │
    └──────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ AppState.icicle_figure                   │
    │   → Plotly icicle chart                  │
    │   → 10-field customdata structure        │
    │   → Full hover/text templates            │
    └──────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ Reflex UI (rx.plotly component)          │
    │   → <50ms filter response time           │
    │   → Treatment statistics in tooltips     │
    │   → Dynamic hierarchy label updates      │
    └──────────────────────────────────────────┘
```

**Legacy Data Flow (Original):**

```
Data Sources:
    CSV/Parquet file upload
    OR SQLite database query
    OR Snowflake fetch (with caching)
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ Data Transformations (tools/data.py)     │
    │   → patient_id() creates UPID            │
    │   → drug_names() standardizes names      │
    │   → department_identification() → Dir    │
    └──────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ Analysis Pipeline (analysis/)            │
    │   → prepare_data() - filter by criteria  │
    │   → calculate_statistics()               │
    │   → build_hierarchy()                    │
    │   → prepare_chart_data()                 │
    └──────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────────┐
    │ Visualization (visualization/)           │
    │   → create_icicle_figure()               │
    │   → Display in rx.plotly() component     │
    └──────────────────────────────────────────┘
```

### Reference Data Files (`data/`)

| File | Purpose |
|------|---------|
| `include.csv` | Drug filter list with default selections (Include=1) |
| `defaultTrusts.csv` | NHS Trust list for filter |
| `directory_list.csv` | Medical specialties/directories |
| `drugnames.csv` | Drug name standardization mapping |
| `org_codes.csv` | Provider code to organization name mapping |
| `drug_directory_list.csv` | Valid drug-to-directory mappings (pipe-separated) |
| `treatment_function_codes.csv` | NHS treatment function code mappings |
| `drug_indication_clusters.csv` | Drug to SNOMED cluster mappings |
| `ta-recommendations.xlsx` | NICE TA recommendations |
| `pathways.db` | SQLite database with all tables |

### Key Patterns

**Department Identification Fallback Chain:**
The `department_identification()` function has 5 levels of fallback:
1. **SINGLE_VALID_DIR** - Drug has only one valid directory
2. **EXTRACTED** - Extracted from Additional Detail/Description fields
3. **CALCULATED_MOST_FREQ** - Most frequent valid directory for UPID/Drug
4. **UPID_INFERENCE** - Inferred from other records with same UPID
5. **UNDEFINED** - No directory could be determined

**Indication Lookup Workflow (for indication charts):**
1. Extract unique `PseudoNHSNoLinked` values from HCD activity data
2. Query Snowflake in batches of 500 patients:
   - Embed `CLUSTER_MAPPING_SQL` (~148 Search_Term → Cluster_ID mappings) as CTE
   - Join `ClinicalCodingClusterSnomedCodes` to get SNOMED codes per cluster
   - Join `PrimaryCareClinicalCoding` on `PatientPseudonym` = `PseudoNHSNoLinked`
   - Use `QUALIFY ROW_NUMBER() OVER (PARTITION BY PatientPseudonym ORDER BY EventDateTime DESC) = 1` for most recent match
3. Build `indication_df` mapping UPID → Search_Term (matched) or Directorate + " (no GP dx)" (unmatched)
4. Pass to `generate_icicle_chart_indication()` for pathway hierarchy building

**Indication Validation Workflow (legacy, per-patient):**
1. Map drug → SNOMED cluster IDs (e.g., ADALIMUMAB → RARTH_COD, PSORIASIS_COD)
2. Get all SNOMED codes for those clusters
3. Check GP records (PrimaryCareClinicalCoding) for matching codes
4. Report match/no-match with source tracking

**Data Source Fallback Chain:**
1. Query cache for recent results
2. Attempt Snowflake connection
3. Fall back to SQLite database
4. Fall back to CSV/Parquet files

## Database Schema

### Reference Tables
- `ref_drug_names` - Drug name standardization
- `ref_organizations` - Provider code to name mapping
- `ref_directories` - Valid directory names
- `ref_drug_directory_map` - Valid drug-directory pairs
- `ref_drug_indication_clusters` - Drug to SNOMED cluster mapping

### Fact Tables
- `fact_interventions` - Patient intervention records (UPID, drug, date, cost, directory)

### Materialized Views
- `mv_patient_treatment_summary` - Pre-aggregated patient statistics

### File Tracking
- `processed_files` - Hash-based tracking for incremental loading

### Pathway Tables
- `pathway_date_filters` - 6 pre-defined date filter combinations
  - Columns: `id`, `initiated`, `last_seen`, `is_default`, `description`
  - Auto-populated via migration
- `pathway_nodes` - Pre-computed pathway hierarchy nodes (~3,600 rows for 12 datasets)
  - Routing: `chart_type` ("directory" or "indication"), `date_filter_id`
  - Hierarchy: `parents`, `ids`, `labels`, `level`
  - Metrics: `value`, `cost`, `costpp`, `cost_pp_pa`, `colour`
  - Dates: `first_seen`, `last_seen`, `first_seen_parent`, `last_seen_parent`
  - Statistics: `average_spacing`, `average_administered`, `avg_days`
  - Denormalized: `trust_name`, `directory`, `drug_sequence`
  - Foreign key: `date_filter_id` → `pathway_date_filters.id`
  - Unique constraint: `UNIQUE(date_filter_id, chart_type, ids)` — critical for INSERT OR REPLACE correctness
  - Indexed for: date_filter_id, chart_type, trust_name, directory, level
- `pathway_refresh_log` - Tracks data refresh status
  - Columns: `refresh_id`, `started_at`, `completed_at`, `status`, `records_processed`, `error_message`

## Input Data Requirements

The input data (CSV/Parquet) must contain columns including:
- `Provider Code`, `PersonKey` - Used to create UPID
- `PseudoNHSNoLinked` - NHS pseudonym for GP record matching (indication charts)
- `Drug Name`, `Intervention Date`, `Price Actual`
- `OrganisationName`
- Various `Additional Detail/Description` columns for directory extraction
- `Treatment Function Code`

## Output

Interactive Plotly icicle chart with toggleable views:
- **Directory view**: Trust → Directorate → Drug → Patient Pathway
- **Indication view**: Trust → GP Diagnosis (Search_Term) → Drug → Patient Pathway
- Patient counts and percentages at each hierarchy level
- Total and average costs
- Treatment duration and dosing frequency information
- Color gradient based on patient volume

## Testing

```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=core --cov=analysis

# Run specific test file
python -m pytest tests/test_config.py -v

# Run specific test class
python -m pytest tests/test_data_transformations.py::TestPatientId -v
```

Test coverage includes:
- PathConfig validation (23 tests)
- AnalysisFilters validation (26 tests)
- Data transformation functions (23 tests)
- Directory assignment logic (19 tests)

## Configuration

### Snowflake Connection (`config/snowflake.toml`)

```toml
[snowflake]
account = "your-account"
database = "DATA_HUB"
schema = "CDM"
warehouse = "your-warehouse"
authenticator = "externalbrowser"  # Required for NHS SSO
```

### Logging

Logs are written to `logs/` directory with structured format.
Configure via `core/logging_config.py`.

## Breaking Changes from Original App

The pre-computed pathway architecture introduces these changes:

### Date Filters
- **Old**: Date pickers for arbitrary `start_date` and `end_date`
- **New**: Two dropdowns:
  - "Treatment Initiated": All years, Last 2 years, Last 1 year
  - "Last Seen": Last 6 months, Last 12 months
- **Reason**: Pre-computed pathways require fixed date combinations for performance

### Data Refresh
- **Old**: Real-time pathway calculation on each filter change
- **New**: Pre-computed pathways stored in SQLite, refreshed via CLI command
- **Impact**: Data is as fresh as the last `python -m cli.refresh_pathways` run
- **Benefit**: Sub-50ms filter response time vs multi-minute calculations

### State Variables
- **Removed**: `start_date`, `end_date`, `set_start_date()`, `set_end_date()`
- **Added**: `selected_initiated`, `selected_last_seen`, `date_filter_id`
- **Added**: `selected_chart_type` ("directory" or "indication"), `chart_type_options`
- **Added**: `set_chart_type()` - switches chart type and reloads data
- **Added**: `chart_hierarchy_label`, `chart_type_label` - computed vars for dynamic UI text
- **Added**: `load_pathway_data()` - queries pre-computed `pathway_nodes` filtered by `date_filter_id` AND `chart_type`
- **Added**: `recalculate_parent_totals()` - adjusts hierarchy after filtering

### Chart Type Toggle
- **New**: Segmented control ("By Directory" | "By Indication") in filter strip
- **Added**: `selected_chart_type` state variable, `set_chart_type()` handler
- **Added**: Dynamic hierarchy label ("Trust → Directorate → ..." or "Trust → Indication → ...")
- **Note**: Directory filter only applies to directory charts; for indication charts the `directory` column stores Search_Terms

### Icicle Chart
- **Enhanced**: Now includes full 10-field customdata structure
- **Added**: Treatment statistics (average_spacing, cost_pp_pa) in hover tooltips
- **Added**: First/last seen dates for drug nodes
- **Added**: Indication chart uses `generate_icicle_chart_indication()` with Search_Term hierarchy

## Development

### Adding New Data Sources

1. Create loader class implementing `DataLoader` protocol in `data_processing/loader.py`
2. Add to factory function `get_loader()`
3. Update `DataSourceManager` fallback chain if needed

### Adding New Analysis Features

1. Add statistical functions to `analysis/statistics.py`
2. Integrate into pipeline in `analysis/pathway_analyzer.py`
3. Update visualization in `visualization/plotly_generator.py`

### Adding New Reference Data

1. Add CSV file to `data/` directory
2. Define schema in `data_processing/schema.py`
3. Create migration function in `data_processing/reference_data.py`
4. Add path to `PathConfig` in `core/config.py`
