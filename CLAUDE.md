# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NHS High-Cost Drug Patient Pathway Analysis Tool - a web-based application that analyzes secondary care patient treatment pathways. It processes clinical activity data to visualize hierarchical treatment patterns (Trust → Directory/Specialty → Drug → Patient pathway) as interactive Plotly icicle charts.

**Key Features:**
- Multi-source data loading: CSV/Parquet files, SQLite database, Snowflake data warehouse
- GP diagnosis integration for indication validation via SNOMED clusters
- Interactive browser-based UI using Reflex framework
- Real-time analysis with progress feedback

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt
# OR with uv
uv sync

# Run the Reflex web application
reflex run
```

The application requires Python 3.10+ and runs on http://localhost:3000 by default.

## Architecture

### Package Structure

```
.
├── core/                    # Core configuration and models
│   ├── config.py           # PathConfig dataclass for file paths
│   ├── models.py           # AnalysisFilters dataclass
│   └── logging_config.py   # Structured logging setup
│
├── data_processing/         # Data layer
│   ├── database.py         # SQLite connection management
│   ├── schema.py           # Database schema definitions
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
│   ├── pathways.db         # SQLite database
│   └── *.csv               # Reference data files
│
└── tests/                   # Test suite
    ├── conftest.py         # Pytest fixtures
    └── test_*.py           # Test modules
```

### Core Module (`core/`)

- **PathConfig** - Dataclass encapsulating all file paths, with `validate()` method
- **AnalysisFilters** - Dataclass for filter state (dates, drugs, trusts, directories)
- **logging_config** - Structured logging with file and console output

### Data Processing Module (`data_processing/`)

**Database Management:**
- `DatabaseManager` - SQLite connection pooling and transaction management
- Tables: `ref_drug_names`, `ref_organizations`, `ref_directories`, `ref_drug_directory_map`, `ref_drug_indication_clusters`, `fact_interventions`, `mv_patient_treatment_summary`, `processed_files`

**Data Loaders:**
- `FileDataLoader` - Loads from CSV/Parquet files
- `SQLiteDataLoader` - Queries fact_interventions table
- Factory function `get_loader()` selects appropriate loader

**Snowflake Integration:**
- SSO authentication via `externalbrowser` authenticator
- `fetch_activity_data(start_date, end_date, provider_codes)` method
- Query caching with TTL-based invalidation
- Fallback chain: cache → Snowflake → local files

**GP Diagnosis Validation:**
- Uses pre-built SNOMED clusters from `ClinicalCodingClusterSnomedCodes`
- `patient_has_indication(patient_pseudonym, cluster_ids)` checks GP records
- `validate_indication(patient_pseudonym, drug_name)` returns full validation result
- Adds `Indication_Source` column: "GP_SNOMED" | "HCD_SNOMED" | "NONE"

### Analysis Module (`analysis/`)

Refactored from the original 267-line `generate_graph()` function:

- **prepare_data()** - Filter DataFrame by date range, trusts, drugs, directories
- **calculate_statistics()** - Compute frequency, cost, duration statistics
- **build_hierarchy()** - Create Trust → Directory → Drug → Pathway structure
- **prepare_chart_data()** - Format data for Plotly icicle chart

### Visualization Module (`visualization/`)

- **create_icicle_figure()** - Generate Plotly icicle chart figure
- **save_figure_html()** - Save interactive HTML file
- **open_figure_in_browser()** - Open chart in default browser

### Reflex Application (`pathways_app/`)

The `State` class manages all application state:
- Filter variables: dates, drugs, trusts, directories
- Reference data: available options loaded from CSV/SQLite
- Analysis state: running flag, status messages, chart data
- Data source state: file path, source type, row counts

### Legacy Modules (`tools/`)

Still used during transition:

- **tools/data.py** - Data transformation functions:
  - `patient_id()` - Creates UPID = Provider Code (first 3 chars) + PersonKey
  - `drug_names()` - Standardizes via drugnames.csv lookup
  - `department_identification()` - 5-level fallback chain for directory assignment

- **tools/dashboard_gui.py** - Original analysis engine (being replaced by `analysis/` module)

### Data Flow

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

**Indication Validation Workflow:**
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

## Input Data Requirements

The input data (CSV/Parquet) must contain columns including:
- `Provider Code`, `PersonKey` - Used to create UPID
- `Drug Name`, `Intervention Date`, `Price Actual`
- `OrganisationName`
- Various `Additional Detail/Description` columns for directory extraction
- `Treatment Function Code`

## Output

Interactive Plotly icicle chart showing:
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
