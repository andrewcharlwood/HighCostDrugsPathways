# Patient Pathway Analysis - Improvement Recommendations

This document outlines recommended improvements to modernize the Patient Pathway Analysis application, based on multi-domain expert analysis.

---

## Executive Summary

| Area | Current State | Recommended Change | Priority |
|------|--------------|-------------------|----------|
| **GUI Framework** | CustomTkinter | **Reflex** (browser-based, native Plotly) | High |
| **Data Storage** | CSV files (90MB+) | SQLite with caching | High |
| **Data Source** | Manual CSV export | Direct Snowflake connection | Medium |
| **Directory Assignment** | Multi-stage fallback | GP diagnosis codes as primary | Medium |
| **Code Quality** | Monolithic, no types | Modular, typed, tested | Low |

---

## 1. GUI Framework: Replace CustomTkinter with Reflex or Flet

### What
Replace the CustomTkinter-based GUI with a modern Python framework. Two strong options:
- **[Reflex](https://reflex.dev)** - React-based, runs in browser
- **[Flet](https://flet.dev)** - Flutter-based, native desktop or browser

### Why

Since Python is approved and standalone `.exe` distribution isn't required, **both frameworks are viable**.

| Criterion | CustomTkinter | Reflex | Flet |
|-----------|---------------|--------|------|
| UI paradigm | Native desktop | Browser (localhost) | Desktop or browser |
| Component richness | Limited | 60+ React components | Material Design |
| Styling | Manual/limited | Full CSS/Tailwind | Flutter theming |
| Plotly integration | External HTML | **Native embed** | WebView needed |
| State management | Manual | Automatic re-render | Manual updates |
| Learning curve | Low | Moderate (React-like) | Low-moderate |
| Community | Small | 22k+ GitHub stars | 12k+ GitHub stars |
| Maturity | Stable | Active (v0.6+) | Active (v0.80+) |

### Recommendation: **Reflex**

Given that:
1. Python is approved for users
2. Standalone `.exe` not required
3. **Interactive Plotly is required** (Reflex has native `rx.plotly()` component)

Reflex is now the better choice because:
- **Native Plotly support** - no need to open external browser windows
- **Modern React-based UI** - cleaner, more customizable
- **Simpler state management** - automatic re-rendering on state changes
- **Better for data apps** - designed for dashboards and data visualization

### How (Reflex)

**Basic app structure:**

```python
import reflex as rx

class State(rx.State):
    """Application state."""
    start_date: str = "2019-04-01"
    end_date: str = "2025-04-30"
    selected_drugs: list[str] = []
    selected_trusts: list[str] = []
    analysis_running: bool = False
    chart_data: dict = {}

    async def run_analysis(self):
        self.analysis_running = True
        yield  # Update UI

        # Run analysis (async)
        df = await self.load_and_process_data()
        self.chart_data = generate_plotly_figure(df)

        self.analysis_running = False

def index() -> rx.Component:
    return rx.box(
        rx.hstack(
            # Sidebar with filters
            rx.vstack(
                rx.date_picker(
                    value=State.start_date,
                    on_change=State.set_start_date,
                ),
                rx.checkbox_group(
                    items=drug_list,
                    value=State.selected_drugs,
                    on_change=State.set_selected_drugs,
                ),
                rx.button(
                    "Run Analysis",
                    on_click=State.run_analysis,
                    loading=State.analysis_running,
                ),
                width="300px",
            ),
            # Main content - interactive Plotly chart
            rx.plotly(data=State.chart_data, layout=chart_layout),
            width="100%",
        )
    )

app = rx.App()
app.add_page(index)
```

**Key components mapping:**

| Current Component | Reflex Equivalent |
|-------------------|-------------------|
| `CTkFrame` | `rx.box`, `rx.vstack`, `rx.hstack` |
| `CTkButton` | `rx.button` |
| `CTkCheckBox` | `rx.checkbox` |
| `CTkSlider` | `rx.slider` |
| `DateEntry` | `rx.date_picker` |
| `CTkScrollableFrame` | `rx.scroll_area` |
| `filedialog` | `rx.upload` |
| Plotly HTML file | **`rx.plotly()`** - native embed! |

**Running the app:**

```bash
# Install
pip install reflex

# Initialize (first time)
reflex init

# Run development server
reflex run
# Opens http://localhost:3000 in browser
```

**Background tasks with progress:**

```python
class State(rx.State):
    progress: int = 0
    status: str = ""

    async def run_analysis(self):
        self.status = "Loading data..."
        self.progress = 10
        yield

        df = load_data()
        self.status = "Processing..."
        self.progress = 50
        yield

        result = process_data(df)
        self.status = "Complete"
        self.progress = 100
        yield
```

### Alternative: Flet

If you prefer a more desktop-like feel, Flet remains a good option:

```python
import flet as ft

def main(page: ft.Page):
    page.title = "HCD Analysis"

    async def run_analysis(e):
        # Background task
        page.run_task(do_analysis)

    page.add(
        ft.Row([
            # Sidebar
            ft.Column([
                ft.DatePicker(),
                ft.ElevatedButton("Run", on_click=run_analysis),
            ]),
            # Chart area (opens in browser for interactivity)
            ft.ElevatedButton("View Chart", on_click=open_chart),
        ])
    )

ft.app(target=main)  # Desktop window
# OR
ft.app(target=main, view=ft.WEB_BROWSER)  # Browser
```

### Effort Estimate
- Learning Reflex basics: 2-3 days
- Rewriting GUI: 1-2 weeks
- Testing and polish: 3-5 days

---

## 2. Data Storage: SQLite Architecture

### What
Replace CSV-based data loading with a SQLite database that stores reference data in normalized tables and caches processed patient data.

### Why

| Aspect | Current (CSV) | SQLite |
|--------|---------------|--------|
| Startup time | 90MB+ file read + full processing | Load reference data once (< 1MB) |
| Memory usage | Entire dataset in memory | Incremental queries |
| Incremental updates | Full reprocess required | Only process new/changed records |
| Query performance | Pandas groupby/merge | Indexed SQL with CTEs |
| Data consistency | Multiple CSVs can drift | Single source of truth with FK constraints |
| Caching | None | Materialized views |

**Expected improvements:**
- 60-80% faster startup
- 50-70% memory reduction
- 90%+ time savings on incremental updates

### How

**Recommended schema (simplified):**

```sql
-- Reference tables
CREATE TABLE ref_drug_names (
    drug_name_raw TEXT PRIMARY KEY,
    drug_name_std TEXT NOT NULL
);

CREATE TABLE ref_organizations (
    org_code TEXT PRIMARY KEY,
    org_name TEXT NOT NULL
);

CREATE TABLE ref_directories (
    directory_id INTEGER PRIMARY KEY,
    directory_name TEXT UNIQUE NOT NULL
);

CREATE TABLE ref_drug_directory_map (
    drug_name_std TEXT,
    directory_id INTEGER,
    is_single_valid BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (drug_name_std, directory_id)
);

-- Patient data (fact table)
CREATE TABLE fact_interventions (
    intervention_id INTEGER PRIMARY KEY,
    upid TEXT NOT NULL,
    provider_code TEXT,
    drug_name_std TEXT NOT NULL,
    intervention_date DATE NOT NULL,
    price_actual REAL,
    directory_id INTEGER,
    directory_assignment_method TEXT,
    data_load_batch_id INTEGER
);

-- Critical indexes
CREATE INDEX idx_upid ON fact_interventions(upid);
CREATE INDEX idx_upid_drug ON fact_interventions(upid, drug_name_std);
CREATE INDEX idx_intervention_date ON fact_interventions(intervention_date);

-- Materialized view for patient summaries (cached aggregations)
CREATE TABLE mv_patient_treatment_summary (
    upid TEXT PRIMARY KEY,
    first_seen DATE,
    last_seen DATE,
    total_cost REAL,
    drug_count INTEGER,
    last_refresh TIMESTAMP
);

-- File tracking for incremental updates
CREATE TABLE processed_files (
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    last_processed TIMESTAMP
);
```

**Migration strategy:**

1. **Phase 1**: Create schema, load reference tables from existing CSVs
2. **Phase 2**: Develop incremental load scripts for patient data
3. **Phase 3**: Build materialized views for aggregations
4. **Phase 4**: Modify `dashboard_gui.py` to query SQLite instead of processing CSVs

**Key query replacing pandas aggregation:**

```sql
-- Replaces ~200 lines of pandas groupby/merge
WITH patient_drugs AS (
    SELECT
        upid,
        drug_name_std,
        MIN(intervention_date) as first_date,
        MAX(intervention_date) as last_date,
        COUNT(*) as intervention_count,
        SUM(price_actual) as drug_cost
    FROM fact_interventions
    WHERE intervention_date BETWEEN :start_date AND :end_date
        AND provider_code IN (:trust_filters)
    GROUP BY upid, drug_name_std
)
SELECT * FROM patient_drugs;
```

### Effort Estimate
- Schema design and setup: 2-3 days
- Migration scripts: 3-4 days
- Query optimization: 2-3 days
- Integration testing: 2-3 days

---

## 3. Snowflake Integration

### What
Enable direct download of HCD activity data from Snowflake servers, replacing manual CSV exports.

### Why
- Eliminates manual export step
- Enables date-range filtering at query level (faster)
- Automatic caching with TTL
- Graceful fallback to local files if Snowflake unavailable

### How

**Authentication: SSO Browser Login**

Using `externalbrowser` authenticator - opens system browser for SSO authentication:

```python
import snowflake.connector

conn = snowflake.connector.connect(
    account="your_account.region",
    user="your.email@nhs.net",
    authenticator="externalbrowser",
    warehouse="ANALYTICS_WH",
    database="data_hub",
    schema="dwh"
)
```

**Note**: User will see browser popup on first connection each session.

**Configuration (`config/snowflake.toml`):**

```toml
[snowflake]
account = "your_account.region"
warehouse = "ANALYTICS_WH"
database = "DataWarehouse"
schema = "dwh"

[query]
default_timeout = 300
chunk_size = 100000

[cache]
enabled = true
ttl_hours = 24
directory = "./data/cache"
```

**Core connector pattern:**

```python
from snowflake.connector import connect

class SnowflakeConnector:
    def fetch_activity_data(self, start_date, end_date, provider_codes=None):
        query = """
        SELECT
            "Provider Code",
            "PersonKey",
            "ProductDescription" as "Drug Name",
            "Intervention Date",
            "Price Actual",
            -- ... other columns
        FROM DataWarehouse.dwh.FactHighCostDrugs
        WHERE "Intervention Date" BETWEEN :start_date AND :end_date
        """

        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {'start_date': start_date, 'end_date': end_date})
            return cursor.fetch_pandas_all()
```

**Caching strategy:**

| Scenario | Action |
|----------|--------|
| Same date range within 24 hours | Use cache |
| Date range includes today | Query Snowflake (data may be updating) |
| User clicks "Refresh" | Query Snowflake |
| Snowflake unavailable | Fallback to local CSV/Parquet |

**Data loader with fallback:**

```python
class DataLoader:
    def load_data(self, start_date, end_date, force_refresh=False):
        # 1. Try cache
        if self.cache and not force_refresh:
            cached = self.cache.get(start_date, end_date)
            if cached is not None:
                return cached, "cache"

        # 2. Try Snowflake
        try:
            df = self.snowflake.fetch_activity_data(start_date, end_date)
            self.cache.set(df, start_date, end_date)
            return df, "snowflake"
        except SnowflakeConnectionError:
            pass

        # 3. Fallback to local files
        if self.fallback_file.exists():
            return pd.read_parquet(self.fallback_file), "local_file"

        raise RuntimeError("No data source available")
```

**Dependencies to add:**

```toml
dependencies = [
    "snowflake-connector-python[pandas]>=3.12.0",
    "cryptography>=42.0.0",
]
```

### Effort Estimate
- Snowflake connector setup: 2-3 days
- Caching layer: 1-2 days
- GUI integration (data source selector): 1-2 days
- Testing with real data: 2-3 days

---

## 4. GP Diagnosis Code Integration

### What
Use GP diagnosis codes as the **primary source** for directory/specialty assignment, with existing logic as fallback.

### Why
- More accurate: Diagnosis directly indicates specialty
- Reduces "Undefined" assignments
- Leverages existing NHS data linkage
- Maintains current logic as safety net

### How

**NHS diagnosis code landscape:**

| Code System | Usage | Notes |
|-------------|-------|-------|
| **SNOMED CT** | GP systems (mandatory since 2018) | Primary source |
| **ICD-10** | Secondary care | Maps FROM SNOMED CT |
| **Read Codes** | Legacy only | Historical records |

**New priority chain:**

```
1. Drug has single valid directory → use that (unchanged)
2. [NEW] GP diagnosis available → map SNOMED/ICD-10 to directory
3. Extract from clinical data fields (existing)
4. Most frequent for same patient/drug (existing)
5. UPID-based inference (existing)
6. Default to "Undefined" (existing)
```

**ICD-10 to Directory mapping (examples):**

```python
ICD10_TO_DIRECTORY = {
    # Neoplasms (Chapter II)
    "C": ["MEDICAL ONCOLOGY", "CLINICAL ONCOLOGY", "CLINICAL HAEMATOLOGY"],

    # Blood diseases (Chapter III)
    "D5": ["CLINICAL HAEMATOLOGY"],
    "D6": ["CLINICAL HAEMATOLOGY"],

    # Endocrine (Chapter IV)
    "E10": ["DIABETIC MEDICINE"],  # Type 1 diabetes
    "E11": ["DIABETIC MEDICINE"],  # Type 2 diabetes

    # Eye (Chapter VII)
    "H0": ["OPHTHALMOLOGY"],
    "H1": ["OPHTHALMOLOGY"],
    "H2": ["OPHTHALMOLOGY"],
    "H3": ["OPHTHALMOLOGY"],

    # Musculoskeletal (Chapter XIII)
    "M05": ["RHEUMATOLOGY"],  # Rheumatoid arthritis
    "M06": ["RHEUMATOLOGY"],
    "M32": ["RHEUMATOLOGY"],  # SLE

    # Genitourinary (Chapter XIV)
    "N0": ["NEPHROLOGY"],
    "N1": ["NEPHROLOGY"],
    "N18": ["NEPHROLOGY"],  # CKD
}
```

**Multi-diagnosis resolution:**

```python
def resolve_directory_from_diagnoses(diagnoses, drug_valid_dirs):
    """
    When patient has multiple diagnoses:
    1. Filter to diagnoses mapping to directories valid for this drug
    2. Oncology diagnoses take priority (ICD-10 chapter C)
    3. Use most recent active diagnosis
    4. Default to first alphabetically (deterministic)
    """
    valid_matches = []

    for dx in diagnoses:
        icd10_prefix = dx.icd10_code[:3]
        possible_dirs = ICD10_TO_DIRECTORY.get(icd10_prefix, [])
        matching = set(possible_dirs) & set(drug_valid_dirs)

        if matching:
            valid_matches.append({
                'directories': matching,
                'is_oncology': dx.icd10_code.startswith('C'),
                'date': dx.diagnosis_date
            })

    if not valid_matches:
        return None  # Fall back to existing logic

    # Oncology priority
    oncology = [m for m in valid_matches if m['is_oncology']]
    if oncology:
        return sorted(oncology[0]['directories'])[0]

    # Most recent
    valid_matches.sort(key=lambda x: x['date'], reverse=True)
    return sorted(valid_matches[0]['directories'])[0]
```

**Data source options:**

1. **Snowflake linked data** (recommended): Query `data_hub.dwh.DimClinicalCoding` joined via `PatientPseudo`
2. **Local CSV cache**: Pre-extracted GP diagnosis data for offline use
3. **Hybrid**: Cache with Snowflake refresh

**GP Diagnosis Query (confirm column names via Snowflake MCP):**

```sql
SELECT
    PatientPseudo,
    SNOMEDCode,           -- or similar
    ICD10Code,            -- may need mapping from SNOMED
    DiagnosisDate,
    DiagnosisStatus       -- Active/Resolved if available
FROM data_hub.dwh.DimClinicalCoding
WHERE PatientPseudo IN (:patient_pseudo_list)
ORDER BY DiagnosisDate DESC
```

**New reference file needed (`./data/diagnosis_directory_map.csv`):**

```csv
icd10_prefix,directory,priority,notes
C,MEDICAL ONCOLOGY,1,All malignancies
C81,CLINICAL HAEMATOLOGY,1,Hodgkin lymphoma
C90,CLINICAL HAEMATOLOGY,1,Multiple myeloma
E10,DIABETIC MEDICINE,1,Type 1 diabetes
E11,DIABETIC MEDICINE,1,Type 2 diabetes
G35,NEUROLOGY,1,Multiple sclerosis
H0,OPHTHALMOLOGY,1,Eye disorders
M05,RHEUMATOLOGY,1,Rheumatoid arthritis
N18,NEPHROLOGY,1,Chronic kidney disease
```

**Tracking assignment source (for audit):**

```python
df['Directory_Source'] = pd.NA  # New column

# After each assignment step:
df.loc[assigned_mask, 'Directory_Source'] = 'DRUG_SINGLE'      # Step 1
df.loc[assigned_mask, 'Directory_Source'] = 'GP_DIAGNOSIS'     # Step 2 (NEW)
df.loc[assigned_mask, 'Directory_Source'] = 'CLINICAL_EXTRACT' # Step 3
# ... etc
```

### Prerequisites
- Explore `data_hub.dwh.DimClinicalCoding` schema to confirm exact column names (use Snowflake MCP)
- Map `PatientPseudo` to your HCD data (may need to add PatientPseudo to your data extract)
- Obtain SNOMED CT to ICD-10 mapping table from NHS TRUD (if DimClinicalCoding only has SNOMED)

### Effort Estimate
- Mapping table creation: 2-3 days
- Snowflake GP query development: 2-3 days
- Integration with existing logic: 2-3 days
- Validation and testing: 3-5 days

---

## 5. Code Quality Improvements

### What
Modernize the codebase with better structure, type hints, error handling, and testing.

### Why
- `generate_graph()` is 267 lines with complexity >30
- Zero type hints across entire codebase
- Global variables create hidden state
- No automated tests
- Print statements instead of logging

### How

**Quick wins (implement first):**

1. **Replace global variables** with dataclass:
```python
@dataclass
class AnalysisFilters:
    start_date: date
    end_date: date
    last_seen: date
    minimum_patients: int
    selected_trusts: list[str]
    selected_drugs: list[str]
    selected_directories: list[str]
    custom_title: str = ""

    def validate(self) -> list[str]:
        errors = []
        if self.start_date >= self.end_date:
            errors.append("Start date must be before end date")
        return errors
```

2. **Externalize configuration:**
```python
@dataclass
class PathConfig:
    data_dir: Path = Path("./data")

    @property
    def drug_names_file(self) -> Path:
        return self.data_dir / "include.csv"

    @property
    def org_codes_file(self) -> Path:
        return self.data_dir / "org_codes.csv"

    # ... etc for all 7 reference files

    def validate(self) -> list[str]:
        """Check all required files exist at startup."""
        errors = []
        for file_path in [self.drug_names_file, self.org_codes_file, ...]:
            if not file_path.exists():
                errors.append(f"Required file not found: {file_path}")
        return errors
```

3. **Add logging:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("./logs/analysis.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PatientPathway")

# Replace all print() with:
logger.info("Starting analysis...")
logger.error(f"Failed to load file: {e}")
```

4. **Extract `generate_graph()` into smaller functions:**
```python
def generate_graph(df, filters: AnalysisFilters, config: PathConfig):
    df = prepare_data(df, filters)           # ~50 lines
    stats = calculate_statistics(df)          # ~80 lines
    hierarchy = build_hierarchy(df, stats)    # ~60 lines
    chart_data = prepare_chart_data(hierarchy) # ~40 lines
    return render_icicle_chart(chart_data, filters.custom_title)  # ~40 lines
```

**Recommended project structure:**

```
project/
├── gui.py                    # Entry point only
├── core/
│   ├── config.py            # PathConfig, AnalysisFilters
│   ├── models.py            # Data models
│   └── exceptions.py        # Custom exceptions
├── data_processing/
│   ├── loader.py            # File/Snowflake loading
│   ├── transformer.py       # Data transformations
│   └── validator.py         # Data validation
├── analysis/
│   ├── pathway_analyzer.py  # Patient pathway calculations
│   └── statistics.py        # Statistical calculations
├── visualization/
│   └── plotly_generator.py  # Graph generation
└── tests/
    ├── test_data_processing.py
    ├── test_analysis.py
    └── test_config.py
```

**Add development dependencies:**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.8.0",
    "black>=24.0.0",
    "ruff>=0.2.0",
]
```

**Priority tests to write:**

```python
# tests/test_data_processing.py
def test_drop_duplicate_treatments_ascending():
    """Verify first intervention kept when ascending=True."""
    # ...

def test_drop_duplicate_treatments_descending():
    """Verify last intervention kept when ascending=False."""
    # ...

# tests/test_config.py
def test_path_config_validates_missing_files():
    """Verify validation catches missing reference files."""
    # ...

def test_analysis_filters_validates_date_range():
    """Verify start date must be before end date."""
    # ...
```

### Effort Estimate
- Dataclasses and config: 1-2 days
- Logging setup: 0.5 days
- Extract `generate_graph()`: 2-3 days
- Add type hints (public API): 1-2 days
- Basic test coverage: 2-3 days

---

## Implementation Roadmap

### Phase 1: Foundation (2-3 weeks)
1. Create `PathConfig` and `AnalysisFilters` dataclasses
2. Set up logging infrastructure
3. Design and create SQLite schema
4. Migrate reference data CSVs to SQLite

### Phase 2: Data Layer (2-3 weeks)
1. Implement Snowflake connector with SSO browser auth
2. Build caching layer with TTL
3. Create data loader with fallback chain
4. Migrate `dashboard_gui.py` to use SQLite queries

### Phase 3: Diagnosis Integration (2-3 weeks)
1. Explore `data_hub.dwh.DimClinicalCoding` schema via Snowflake MCP
2. Create ICD-10 to directory mapping table
3. Implement GP diagnosis lookup using `PatientPseudo` linkage
4. Integrate into `department_identification()` as step 2
5. Add `Directory_Source` tracking column

### Phase 4: GUI Modernization (3-4 weeks)
1. Learn Reflex fundamentals
2. Recreate main window and navigation with `rx.vstack`/`rx.hstack`
3. Implement filter panels (date pickers, checkbox groups)
4. Integrate Plotly charts with native `rx.plotly()` component
5. Test with `reflex run`

### Phase 5: Quality & Polish (1-2 weeks)
1. Add type hints to public API
2. Write priority unit tests
3. Extract `generate_graph()` into smaller functions
4. Documentation and cleanup

---

## Configuration Decisions

Based on requirements, the following decisions have been made:

| Question | Decision |
|----------|----------|
| **Snowflake auth** | SSO browser login (`authenticator='externalbrowser'`) |
| **GP diagnosis data** | `data_hub.dwh.DimClinicalCoding` |
| **Patient linkage** | Use `PatientPseudo` (anonymized identifier) - NOT UPID |
| **Plotly interactivity** | Must be interactive - **Reflex has native `rx.plotly()` component** |
| **Distribution** | Python script (`reflex run`) - no .exe needed |

### Implications

**Snowflake SSO**: Connection code becomes:
```python
conn = snowflake.connector.connect(
    account="your_account.region",
    user=os.environ.get("SNOWFLAKE_USER"),
    authenticator="externalbrowser",  # Opens browser for SSO
    warehouse="ANALYTICS_WH",
    database="data_hub",
    schema="dwh"
)
```

**Patient Linkage**: The GP diagnosis query needs to join on `PatientPseudo`, not UPID:
```sql
SELECT
    cc.PatientPseudo,
    cc.SNOMEDCode,      -- Confirm actual column names
    cc.ICD10Code,
    cc.DiagnosisDate
FROM data_hub.dwh.DimClinicalCoding cc
WHERE cc.PatientPseudo IN (:patient_list)
```

**Note**: You'll need to confirm the exact column names in `DimClinicalCoding` - explore via Snowflake MCP or SQL client.

**Plotly Interactivity**: Reflex solves this elegantly with native embedding:
```python
# Interactive Plotly chart directly in the Reflex app
rx.plotly(data=State.chart_data, layout=chart_layout)
```
Full interactivity (zoom, pan, hover tooltips) works in the browser-based app - no external HTML files needed.

---

## References

- [Reflex Documentation](https://reflex.dev/docs/)
- [Reflex Plotly Component](https://reflex.dev/docs/library/graphing/plotly/)
- [Flet Documentation](https://flet.dev/docs/) (alternative)
- [Snowflake Python Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector)
- [NHS SNOMED CT](https://digital.nhs.uk/services/terminology-and-classifications/snomed-ct)
- [NHS ICD-10 Classifications](https://isd.digital.nhs.uk/trud/users/guest/filters/0/categories/28)
