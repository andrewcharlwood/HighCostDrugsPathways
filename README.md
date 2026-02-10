# NHS High-Cost Drug Patient Pathway Analysis Tool

A web-based application for analyzing secondary care patient treatment pathways. It processes clinical activity data to visualize hierarchical treatment patterns (Trust → Directory/Specialty → Drug → Patient pathway) as interactive Plotly icicle charts.

## Features

- **Desktop App**: Native window experience via pywebview (no browser needed)
- **Interactive Visualization**: Plotly icicle charts showing patient treatment hierarchies with cost and frequency statistics
- **Dual Chart Types**: Directory-based (Trust → Directorate → Drug → Pathway) and Indication-based (Trust → GP Diagnosis → Drug → Pathway) views
- **Pre-computed Pathways**: Treatment pathways pre-processed and stored in SQLite for sub-50ms filter response times
- **GP Diagnosis Matching**: Patient indications matched from GP records using SNOMED cluster codes (~93% match rate)
- **Trend Analysis**: Historical trend views showing how drug usage and costs change over time
- **Modern Web Interface**: Dash (Plotly) + Dash Mantine Components with NHS branding
- **Flexible Filtering**: Filter by date range, NHS trusts, drugs, and medical directories

## Requirements

- Python 3.10 or higher
- uv package manager (recommended)

### Optional (for data refresh)
- Access to NHS Snowflake data warehouse with SSO authentication

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd patient-pathway-analysis

# Install dependencies
uv sync
```

## Quick Start

### Run the Application

```bash
# Run as desktop app (recommended)
python app_desktop.py

# Run in browser (development)
python run_dash.py
```

The desktop app opens automatically in a native window. For browser mode, open http://localhost:8050.

The application loads pre-computed pathway data from SQLite on startup. No additional configuration is needed for viewing existing data.

### Refresh Pathway Data (requires Snowflake)

```bash
# Initialize/migrate the database
python -m data_processing.migrate

# Full refresh — both chart types, all date filters
python -m cli.refresh_pathways --chart-type all

# Directory charts only (faster, ~5 minutes)
python -m cli.refresh_pathways --chart-type directory

# Indication charts only (~12 minutes, includes GP lookup)
python -m cli.refresh_pathways --chart-type indication

# Dry run (test without database changes)
python -m cli.refresh_pathways --chart-type all --dry-run -v
```

**Compute Trends (for Trends view):**

```bash
# Compute historical trend snapshots
python -m cli.compute_trends

# Custom date range
python -m cli.compute_trends --start 2022-01-01 --end 2025-06-30

# Help
python -m cli.compute_trends --help
```

## Usage

### Interface Overview

The application has a single-page layout with:

| Component | Purpose |
|-----------|---------|
| **Header** | NHS branding, fraction KPIs (patients, drugs, cost), data freshness indicator |
| **Sidebar** | Navigation: Patient Pathways, Trust Comparison, Trends |
| **Sub-Header** | Chart type toggle (By Directory / By Indication) + date filter dropdowns |
| **Filter Bar** | Patient Pathways drug/trust/directorate filter buttons with modals |
| **Chart Card** | 9-tab chart area (Icicle, Sankey, Heatmap, Funnel, Depth, Scatter, Network, Timeline, Doses) |
| **Trust Comparison** | Per-directorate 6-chart dashboard comparing drugs across trusts |
| **Trends** | Historical trend analysis with directorate overview + drug drill-down |

### Filtering Data

The application has three analytical views:

1. **Patient Pathways**: Icicle chart + 8 additional analytics tabs with drug/trust/directorate filtering
2. **Trust Comparison**: Per-directorate analysis comparing drugs across trusts
3. **Trends**: Historical trend analysis showing directorate and drug-level changes over time

Common controls across all views:

- **Chart Type**: Toggle between "By Directory" and "By Indication" views
- **Date Filters**: Select treatment initiation period and last-seen window
- **Drug/Trust/Directorate Selection**: Open modals to filter by specific drugs, trusts, or directorates (Patient Pathways)
- **Clear Filters**: Reset all selections to show full dataset

### Understanding the Pathway Chart

The icicle chart displays hierarchical treatment pathways:

```
Root (Regional Total)
  └─ Trust Name (e.g., "Norfolk and Norwich University Hospitals")
      └─ Directory/Indication (e.g., "Rheumatology" or "rheumatoid arthritis")
          └─ Drug Name (e.g., "ADALIMUMAB")
              └─ Treatment Pathway (e.g., "ADALIMUMAB → INFLIXIMAB")
```

- **Width**: Relative patient count
- **Color intensity**: Proportion of parent group
- **Hover**: Shows cost, dosing frequency, date range, and per-patient statistics
- **Click**: Zoom into a specific branch

### Date Filter Combinations

| Initiated | Last Seen | Description |
|-----------|-----------|-------------|
| All years | Last 6 months | Default — all patients active recently |
| All years | Last 12 months | Broader activity window |
| Last 1 year | Last 6 months | Recently initiated, active |
| Last 1 year | Last 12 months | Recently initiated, any activity |
| Last 2 years | Last 6 months | Medium history, active |
| Last 2 years | Last 12 months | Medium history, any activity |

## Project Structure

```
.
├── core/                        # Foundation: paths, models, logging
├── config/                      # Snowflake connection settings
├── data_processing/             # Data layer (SQLite, Snowflake, transforms)
├── analysis/                    # Analysis pipeline
├── visualization/               # Plotly chart generation
├── cli/                         # CLI tools (refresh_pathways, compute_trends)
├── dash_app/                    # Dash web application
│   ├── app.py                   # App entry point, layout, stores
│   ├── assets/nhs.css           # NHS design system CSS
│   ├── data/                    # Query wrappers + card browser data
│   ├── components/              # UI components (header, sidebar, chart_card, trends, etc.)
│   └── callbacks/               # Dash callbacks (filters, chart, KPI, trends, etc.)
├── app_desktop.py               # Desktop entry point (pywebview native window)
├── run_dash.py                  # Browser entry point
├── app.spec                     # PyInstaller packaging spec
├── data/                        # Reference data + SQLite DB (pathways.db)
├── tests/                       # Test suite (114 tests)
├── docs/                        # Documentation
└── archive/                     # Historical/deprecated code
```

See `CLAUDE.md` for detailed architecture documentation.

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage (114 tests)
python -m pytest tests/ -v --cov=core --cov=data_processing --cov=analysis

# Run only fast tests
python -m pytest tests/ -v -m "not slow"
```

## Configuration

### Desktop Packaging

```bash
# Build standalone executable (Windows)
pyinstaller app.spec

# Output: dist/NHS_Pathway_Analysis/NHS_Pathway_Analysis.exe
```

### Snowflake Connection (`config/snowflake.toml`)

```toml
[snowflake]
account = "your-account"
database = "DATA_HUB"
schema = "CDM"
warehouse = "your-warehouse"
authenticator = "externalbrowser"  # Required for NHS SSO
```

## Troubleshooting

### App won't start

```bash
# Ensure dependencies are installed
uv sync

# Try desktop mode
python app_desktop.py

# Or browser mode
python run_dash.py
```

### Database not found

```bash
# Check data/pathways.db exists
python -m data_processing.migrate
```

### Snowflake connection issues

1. Ensure `config/snowflake.toml` has the correct account identifier
2. A browser window will open for SSO authentication
3. Verify your network allows Snowflake connections

## License

Internal NHS use only. Not for distribution.

## Support

For questions or issues, contact the Medicines Intelligence team.
