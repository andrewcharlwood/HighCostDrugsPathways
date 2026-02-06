# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NHS High-Cost Drug Patient Pathway Analysis Tool - a web-based application that analyzes secondary care patient treatment pathways. It processes clinical activity data to visualize hierarchical treatment patterns as interactive Plotly icicle charts.

**Key Features:**
- **Dual chart types**: Directory-based (Trust → Directory → Drug → Pathway) and Indication-based (Trust → GP Diagnosis → Drug → Pathway) views with toggle
- **Pre-computed pathway architecture**: Treatment pathways pre-processed and stored in SQLite for instant filtering
- **GP diagnosis matching**: Patient indications matched from GP records using SNOMED cluster codes queried directly from Snowflake (~93% match rate)
- Data pipeline: Snowflake → pre-computed SQLite pathway nodes (CSV/Parquet file loading retained for legacy compatibility)
- Interactive browser-based UI using Dash (Plotly) + Dash Mantine Components
- 6 pre-defined date filter combinations × 2 chart types = 12 pre-computed datasets with sub-50ms response times

## Running the Application

```bash
# Install dependencies
uv sync

# One-time dev setup: adds src/ to Python path via .pth file
uv run python setup_dev.py

# Initialize/migrate the database (creates pathway tables)
python -m data_processing.migrate

# Refresh pathway data from Snowflake (requires SSO auth)
python -m cli.refresh_pathways

# Run the Dash web application
python run_dash.py
```

The application requires Python 3.10+ and runs on http://localhost:8050 by default.

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
5. Inserts pathway nodes to SQLite for fast Dash filtering

## Architecture

### Package Structure

```
.
├── src/                         # All application library code
│   ├── core/                    # Foundation: paths, models, logging
│   │   ├── config.py           # PathConfig dataclass for file paths
│   │   ├── models.py           # AnalysisFilters dataclass
│   │   └── logging_config.py   # Structured logging setup
│   │
│   ├── config/                  # Service configuration
│   │   ├── __init__.py         # SnowflakeConfig + loader
│   │   └── snowflake.toml      # Connection settings (co-located with loader)
│   │
│   ├── data_processing/         # Data layer
│   │   ├── database.py         # SQLite connection management
│   │   ├── schema.py           # Database schema (reference + pathway tables)
│   │   ├── pathway_pipeline.py # Pipeline: Snowflake → SQLite
│   │   ├── transforms.py       # Data transformations (UPID, drug names, directory)
│   │   ├── loader.py           # FileDataLoader for CSV/Parquet files
│   │   ├── reference_data.py   # Reference data migration
│   │   ├── snowflake_connector.py  # Snowflake integration
│   │   ├── cache.py            # Query result caching
│   │   ├── data_source.py      # Data source fallback chain
│   │   ├── diagnosis_lookup.py # GP diagnosis lookup (SNOMED clusters)
│   │   └── parsing.py          # Parse average_spacing HTML, pathway drugs, retention rates
│   │
│   ├── analysis/                # Analysis pipeline
│   │   ├── pathway_analyzer.py # prepare_data, calculate_statistics, build_hierarchy
│   │   └── statistics.py       # Statistical calculation functions
│   │
│   ├── visualization/           # Chart generation
│   │   └── plotly_generator.py # Icicle, market share, cost effectiveness, waterfall, Sankey, dosing, heatmap, duration figures
│   │
│   └── cli/                     # CLI tools
│       └── refresh_pathways.py # Data refresh command
│
├── dash_app/                    # Dash web application
│   ├── app.py                  # Dash app, layout root, dcc.Store, register_callbacks
│   ├── assets/
│   │   └── nhs.css             # NHS design system CSS
│   ├── data/
│   │   ├── queries.py          # Thin wrapper calling src/data_processing/pathway_queries.py
│   │   └── card_browser.py     # DimSearchTerm.csv → directorate tree for modals
│   ├── components/
│   │   ├── header.py           # Top header bar with fraction KPIs + data freshness
│   │   ├── sidebar.py          # Left nav: Patient Pathways + Trust Comparison
│   │   ├── sub_header.py       # Global filter bar (date dropdowns + chart type toggle)
│   │   ├── filter_bar.py       # Patient Pathways filter buttons (drugs, trusts, directorates)
│   │   ├── chart_card.py       # Chart area with Icicle/Sankey tabs + dcc.Graph
│   │   ├── modals.py           # dmc.Modal dialogs for drug/trust/directorate selection
│   │   ├── trust_comparison.py # Trust Comparison landing page + 6-chart dashboard
│   │   └── footer.py           # Page footer
│   ├── callbacks/
│   │   ├── __init__.py         # register_callbacks(app)
│   │   ├── filters.py          # Reference data loading + filter state management
│   │   ├── chart.py            # Tab switching, pathway data loading, chart dispatch
│   │   ├── modals.py           # Modal open/close + drug/trust/directorate selection
│   │   ├── navigation.py       # Sidebar view switching + Trust Comparison navigation
│   │   ├── trust_comparison.py # 6 Trust Comparison chart callbacks
│   │   └── kpi.py              # Header fraction KPI updates
│   └── utils/
│       └── __init__.py
│
├── run_dash.py                  # Entry point: python run_dash.py
├── tests/                       # Test suite (113 tests)
├── data/                        # Reference data + SQLite DB
├── docs/                        # Documentation
├── assets/                      # Static assets (logo, favicon)
├── archive/                     # Historical/deprecated (includes old Reflex app)
└── logs/                        # Runtime logs
```

**Path resolution**: `src/` is added to `sys.path` via a `.pth` file (created by `setup_dev.py`).
All imports use package names directly: `from core import ...`, `from data_processing import ...`, etc.

### Pathway Data Architecture

The application uses a pre-computed pathway architecture for performance:

**Architecture:** `Snowflake → Pathway Processing → SQLite (pre-computed) → Dash (filter & view)`

**Key Benefits:**
- **Performance**: Pathway calculation done once during data refresh, not on every filter change
- **Simplicity**: Dash callbacks filter pre-computed data with simple SQL WHERE clauses
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
- **Reference Tables**: `ref_drug_names`, `ref_organizations`, `ref_directories`, `ref_drug_directory_map`, `ref_drug_indication_clusters`
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
- `FileDataLoader` - Loads from CSV/Parquet files (used by legacy pipeline, not by Dash app)
- Factory function `get_loader()` creates a `FileDataLoader`

**Snowflake Integration:**
- SSO authentication via `externalbrowser` authenticator
- `fetch_activity_data(start_date, end_date, provider_codes)` method
- Query caching with TTL-based invalidation

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

- **create_icicle_figure(ice_df)** - Generate Plotly icicle chart from DataFrame (legacy/pipeline use)
- **create_icicle_from_nodes(nodes, title)** - Generate icicle chart from list-of-dicts (Dash use). Accepts JSON-serializable node dicts from `dcc.Store`. Uses NHS blue gradient colorscale, 10-field customdata, Source Sans 3 font.
- **create_market_share_figure(data, title)** - Horizontal stacked bar chart: drugs grouped by directorate/indication, bar length = % patients
- **create_cost_effectiveness_figure(data, retention, title)** - Lollipop chart: pathway cost_pp_pa with dot size = patient count, retention annotations
- **create_cost_waterfall_figure(data, title)** - Waterfall chart: directorate-level cost_pp_pa sorted highest to lowest
- **create_sankey_figure(data, title)** - Sankey diagram: drug switching flows across treatment lines (1st → 2nd → 3rd)
- **create_dosing_figure(data, title, group_by)** - Grouped horizontal bar chart: dosing intervals by drug or trust
- **create_heatmap_figure(data, title, metric)** - Matrix heatmap: directorate × drug with patient/cost/cost_pp_pa colouring
- **create_duration_figure(data, title, show_directory)** - Horizontal bar chart: average treatment duration in days per drug
- **create_trust_market_share_figure(data, title)** - Trust Comparison: horizontal stacked bars grouped by trust, drugs as segments
- **create_trust_heatmap_figure(data, title, metric)** - Trust Comparison: trust × drug matrix with NHS blue colorscale
- **create_trust_duration_figure(data, title)** - Trust Comparison: grouped horizontal bars with one trace per trust
- **save_figure_html()** - Save interactive HTML file
- **open_figure_in_browser()** - Open chart in default browser

### Parsing Utilities (`data_processing/parsing.py`)

- **parse_average_spacing(spacing_html)** - Extract drug_name, dose_count, weekly_interval, total_weeks from HTML string
- **parse_pathway_drugs(ids, level)** - Extract ordered drug list from ids column at level 4+
- **calculate_retention_rate(nodes)** - For each N-drug pathway, calculate % not escalating to N+1 drugs

### Shared Data Queries (`data_processing/pathway_queries.py`)

Shared query functions used by the Dash app (via thin wrappers in `dash_app/data/queries.py`):
- **load_initial_data(db_path)** - Returns available drugs (42), directorates (14), indications (32), trusts (7), total_patients, last_updated
- **load_pathway_nodes(db_path, filter_id, chart_type, selected_drugs, selected_directorates, selected_trusts)** - Returns pathway nodes, unique_patients, total_drugs, total_cost, last_updated. Parameterized SQL with optional drug/directorate/trust filters.
- **get_drug_market_share(db_path, filter_id, chart_type, directory, trust)** - Level 3 nodes grouped by directory, returns drug, value, colour
- **get_pathway_costs(db_path, filter_id, chart_type, directory, trust)** - Level 4+ nodes with cost_pp_pa, pathway labels, patient counts
- **get_cost_waterfall(db_path, filter_id, chart_type, trust)** - Level 2 nodes with cost_pp_pa per directorate/indication
- **get_drug_transitions(db_path, filter_id, chart_type, directory, trust)** - Level 3+ nodes parsed into source→target drug transitions
- **get_dosing_intervals(db_path, filter_id, chart_type, drug, trust)** - Level 3 nodes with parsed average_spacing intervals
- **get_drug_directory_matrix(db_path, filter_id, chart_type, trust)** - Level 3 nodes pivoted as directory × drug matrix
- **get_treatment_durations(db_path, filter_id, chart_type, directory, trust)** - Level 3 nodes with avg_days by drug
- **get_trust_market_share(db_path, filter_id, chart_type, directory)** - Trust Comparison: drugs by trust within a single directorate
- **get_trust_cost_waterfall(db_path, filter_id, chart_type, directory)** - Trust Comparison: one bar per trust showing cost_pp within directorate
- **get_trust_dosing(db_path, filter_id, chart_type, directory)** - Trust Comparison: drug dosing intervals broken down by trust
- **get_trust_heatmap(db_path, filter_id, chart_type, directory)** - Trust Comparison: trust × drug matrix for one directorate
- **get_trust_durations(db_path, filter_id, chart_type, directory)** - Trust Comparison: drug durations by trust within directorate
- **get_directorate_summary(db_path, filter_id, chart_type, directory)** - Summary stats for a directorate (total patients, drugs, cost)

### Dash Application (`dash_app/`)

**Two-View Architecture:**
The application is split into two analytical perspectives, selectable via the sidebar:
- **Patient Pathways**: Pathway-focused analysis (Icicle + Sankey charts) with drug/trust/directorate filters
- **Trust Comparison**: Per-directorate analysis comparing drugs across trusts (6 charts for a selected directorate)

**State Management** via 4 `dcc.Store` components:
- **app-state** (session): `chart_type`, `initiated`, `last_seen`, `date_filter_id`, `selected_drugs`, `selected_directorates`, `selected_trusts`, `active_view` ("patient-pathways" | "trust-comparison"), `selected_comparison_directorate` (null | directorate name)
- **chart-data** (memory): `nodes[]`, `unique_patients`, `total_drugs`, `total_cost`, `last_updated`
- **reference-data** (session): `available_drugs`, `available_directorates`, `available_indications`, `available_trusts`, `total_patients`, `last_updated`
- **active-tab** (memory): Currently selected chart tab within Patient Pathways ("icicle" | "sankey")

**Callback Chain** (unidirectional):
```
Page Load → load_reference_data → reference-data store + header indicators
         → update_app_state → app-state store (default filters)
                             → load_pathway_data → chart-data store
                                                  ├→ update_kpis → header fraction KPIs
                                                  └→ update_chart → dcc.Graph (Icicle or Sankey)

Filter change → update_app_state → app-state → load_pathway_data → (chain above)
Modal selection → drug/trust chips → update_app_state → (chain above)
Tab click → switch_tab → active-tab store → update_chart → dcc.Graph (lazy rendering)

Sidebar click → switch_view → active_view in app-state → show/hide views
Trust Comparison:
  Landing page → directorate button click → selected_comparison_directorate → 6 chart callbacks
  Back button → clear selected_comparison_directorate → return to landing
```

**Key Components:**
- **Header** (`header.py`): NHS branding, fraction KPIs (X/X patients, X/X drugs, £X/£X cost), data freshness indicator
- **Sidebar** (`sidebar.py`): 2 navigation items — "Patient Pathways" (default), "Trust Comparison"
- **Sub-Header** (`sub_header.py`): Global filter bar — date dropdowns (Initiated, Last Seen) + chart type toggle pills (By Directory / By Indication). Constant across both views.
- **Filter Bar** (`filter_bar.py`): Patient Pathways-only filter buttons — Drugs (with count badge), Trusts (with count badge), Directorates (with count badge), Clear All. Only visible on Patient Pathways view.
- **Chart Card** (`chart_card.py`): 2-tab chart area (Icicle, Sankey) with `dcc.Loading` spinner, dynamic subtitle, and `dcc.Store(id="active-tab")`
- **Modals** (`modals.py`): 3 `dmc.Modal` dialogs for drug selection (ChipGroup), trust selection (ChipGroup), directorate browser (Accordion with indication sub-items and drug fragment badges)
- **Trust Comparison** (`trust_comparison.py`): Landing page (directorate/indication button grid) + 6-chart dashboard (Market Share, Cost Waterfall, Dosing, Heatmap, Duration, Cost Effectiveness)
- **Footer** (`footer.py`): NHS Norfolk and Waveney ICB branding

**Filter Modals:**
- Drug Modal: flat `dmc.ChipGroup` with 42 drugs from pathway_nodes level 3
- Trust Modal: `dmc.ChipGroup` with 7 trusts
- Directorate Modal: nested `dmc.Accordion` — 19 directorates → indications → drug fragment `dmc.Badge` items
- Clicking a drug fragment badge selects all full drug names containing that fragment (substring match)
- "Clear All Filters" button resets drug and trust selections

**Trust Comparison Dashboard (6 Charts):**
All scoped to a single selected directorate, comparing drugs across trusts:
1. **Market Share**: Drug breakdown per trust (stacked bars per trust)
2. **Cost Waterfall**: Per-trust cost within directorate
3. **Dosing**: Drug dosing intervals by trust
4. **Heatmap**: Trust × drug matrix
5. **Duration**: Drug durations by trust
6. **Cost Effectiveness**: Pathway costs within directorate (NOT split by trust)

### Data Transformations (`data_processing/transforms.py`)

Core data transformation functions used by the pipeline:
- `patient_id()` - Creates UPID = Provider Code (first 3 chars) + PersonKey
- `drug_names()` - Standardizes via drugnames.csv lookup
- `department_identification()` - 5-level fallback chain for directory assignment

### Data Flow

**Pre-Computed Pathway Architecture (Current):**

```
[CLI: python -m cli.refresh_pathways --chart-type all]

    Snowflake Data Warehouse
           │
           ▼ (fetch_and_transform_data)
    ┌──────────────────────────────────────────┐
    │ Data Transformations (data_processing/transforms.py)     │
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


[Dash App: python run_dash.py]

    ┌──────────────────────────────────────────┐
    │ Global Sub-Header (date dropdowns,       │
    │   chart type toggle pills)               │
    │   → Triggers update_app_state callback   │
    └──────────────────────────────────────────┘
           │
           ├─── Patient Pathways View ─────────────────────────────┐
           │                                                        │
           │  ┌──────────────────────────────────────────┐          │
           │  │ Filter Bar (Drugs/Trusts/Directorates)   │          │
           │  │   → Modal selections → app-state         │          │
           │  └──────────────────────────────────────────┘          │
           │         │                                              │
           │         ▼                                              │
           │  ┌──────────────────────────────────────────┐          │
           │  │ load_pathway_data callback               │          │
           │  │   → chart-data store                     │          │
           │  └──────────────────────────────────────────┘          │
           │         │                                              │
           │         ├──────────────────────────────┐               │
           │         ▼                              ▼               │
           │  ┌────────────────────┐  ┌──────────────────────┐      │
           │  │ update_kpis        │  │ update_chart         │      │
           │  │   → header KPIs   │  │   → Icicle or Sankey │      │
           │  └────────────────────┘  └──────────────────────┘      │
           │                                                        │
           ├─── Trust Comparison View ─────────────────────────────┤
           │                                                        │
           │  ┌──────────────────────────────────────────┐          │
           │  │ Landing Page                             │          │
           │  │   → Directorate/Indication buttons       │          │
           │  │   → Click → selected_comparison_dir      │          │
           │  └──────────────────────────────────────────┘          │
           │         │                                              │
           │         ▼                                              │
           │  ┌──────────────────────────────────────────┐          │
           │  │ 6-Chart Dashboard                        │          │
           │  │   → Market Share, Cost Waterfall, Dosing │          │
           │  │   → Heatmap, Duration, Cost Effectiveness│          │
           │  │   → All per-trust within one directorate │          │
           │  └──────────────────────────────────────────┘          │
           │                                                        │
           └────────────────────────────────────────────────────────┘
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
| `pathways.db` | SQLite database (~3.5 MB: reference tables + pathway nodes) |

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

**Data Source Fallback Chain** (for raw data loading, not used by Dash app):
1. Query cache for recent results
2. Attempt Snowflake connection
3. Fall back to CSV/Parquet files

## Database Schema (~3.5 MB)

### Reference Tables
- `ref_drug_names` - Drug name standardization
- `ref_organizations` - Provider code to name mapping
- `ref_directories` - Valid directory names
- `ref_drug_directory_map` - Valid drug-directory pairs
- `ref_drug_indication_clusters` - Drug to SNOMED cluster mapping

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
  - Columns: `refresh_id`, `started_at`, `completed_at`, `status`, `records_processed`, `error_message`, `source_row_count`

## Input Data Requirements

The input data (CSV/Parquet) must contain columns including:
- `Provider Code`, `PersonKey` - Used to create UPID
- `PseudoNHSNoLinked` - NHS pseudonym for GP record matching (indication charts)
- `Drug Name`, `Intervention Date`, `Price Actual`
- `OrganisationName`
- Various `Additional Detail/Description` columns for directory extraction
- `Treatment Function Code`

## Output

Two-view Dash application with distinct analytical perspectives:

**Patient Pathways View** (2 tabs):
1. **Icicle** — Hierarchical pathway view (Directory: Trust → Directorate → Drug → Pathway; Indication: Trust → GP Diagnosis → Drug → Pathway)
2. **Sankey** — Drug switching flows across 1st → 2nd → 3rd treatment lines

Patient Pathways supports:
- Directory / Indication toggle
- Date filter combinations (6 options)
- Trust, drug, and directorate filters via modals
- Lazy rendering (only active tab computed)

**Trust Comparison View** (6 charts in dashboard):
Landing page with directorate/indication buttons → 6-chart dashboard for selected directorate:
1. **Market Share** — Drug breakdown per trust (stacked bars)
2. **Cost Waterfall** — Per-trust cost within directorate
3. **Dosing** — Drug dosing intervals by trust
4. **Heatmap** — Trust × drug matrix
5. **Duration** — Drug durations by trust
6. **Cost Effectiveness** — Pathway costs within directorate (not split by trust)

Trust Comparison supports:
- Directory / Indication toggle (changes landing page buttons)
- Date filter combinations (6 options)
- All 6 charts scoped to selected directorate

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

### Snowflake Connection (`src/config/snowflake.toml`)

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
Configure via `src/core/logging_config.py`.

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

### State Management (Dash)
- State lives in 4 `dcc.Store` components: `app-state`, `chart-data`, `reference-data`, `active-tab`
- Filter state: `chart_type`, `initiated`, `last_seen`, `date_filter_id`, `selected_drugs`, `selected_directorates`, `selected_trusts`
- View state: `active_view` ("patient-pathways" | "trust-comparison"), `selected_comparison_directorate` (null | directorate name)
- Chart type toggle: "By Directory" / "By Indication" pills in global sub-header
- Drug/trust/directorate selection via `dmc.Modal` dialogs (Patient Pathways only)
- Fraction KPIs in header (X/X patients, X/X drugs, £X/£X cost)

### Icicle Chart (Patient Pathways)
- Full 10-field customdata structure (value, colour, cost, costpp, first_seen, last_seen, first_seen_parent, last_seen_parent, average_spacing, cost_pp_pa)
- NHS blue gradient colorscale: Heritage Blue #003087 → Pale Blue #E3F2FD
- Treatment statistics (average_spacing, cost_pp_pa) in hover tooltips
- First/last seen dates for drug nodes
- `create_icicle_from_nodes()` in `src/visualization/plotly_generator.py` — shared function accepting list-of-dicts

## Development

### Adding New Analysis Features

1. Add statistical functions to `src/analysis/statistics.py`
2. Integrate into pipeline in `src/analysis/pathway_analyzer.py`
3. Update visualization in `src/visualization/plotly_generator.py`

### Adding New Reference Data

1. Add CSV file to `data/` directory
2. Define schema in `src/data_processing/schema.py`
3. Create migration function in `src/data_processing/reference_data.py`
4. Add path to `PathConfig` in `src/core/config.py`
