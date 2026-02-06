# NHS High-Cost Drug Patient Pathway Analysis Tool

A web-based application for analyzing secondary care patient treatment pathways. It processes clinical activity data to visualize hierarchical treatment patterns (Trust → Directory/Specialty → Drug → Patient pathway) as interactive Plotly icicle charts.

## Features

- **Interactive Visualization**: Plotly icicle charts showing patient treatment hierarchies with cost and frequency statistics
- **Dual Chart Types**: Directory-based (Trust → Directorate → Drug → Pathway) and Indication-based (Trust → GP Diagnosis → Drug → Pathway) views
- **Pre-computed Pathways**: Treatment pathways pre-processed and stored in SQLite for sub-50ms filter response times
- **GP Diagnosis Matching**: Patient indications matched from GP records using SNOMED cluster codes (~93% match rate)
- **Modern Web Interface**: Browser-based UI using Dash (Plotly) + Dash Mantine Components with NHS branding
- **Drug Browser**: Drawer-based card browser organized by clinical directorate for drug/indication selection
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

# One-time dev setup: adds src/ to Python path via .pth file
uv run python setup_dev.py
```

## Quick Start

### Run the Web Application

```bash
python run_dash.py
```

Open http://localhost:8050 in your browser.

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

## Usage

### Interface Overview

The application has a single-page layout with:

| Component | Purpose |
|-----------|---------|
| **Header** | NHS branding, data freshness indicator (patient count + relative time) |
| **Sidebar** | Navigation items with drawer triggers for Drug Selection, Trust Selection, Indications |
| **KPI Row** | 4 cards: Unique Patients, Drug Types, Total Cost, Indication Match Rate |
| **Filter Bar** | Chart type toggle (By Directory / By Indication) + date filter dropdowns |
| **Chart Card** | Interactive Plotly icicle chart with loading spinner |
| **Drawer** | Right-side panel with drug chips, trust chips, and directorate card browser |

### Filtering Data

1. **Chart Type**: Toggle between "By Directory" and "By Indication" views
2. **Date Filters**: Select treatment initiation period and last-seen window
3. **Drug Selection**: Open the drawer to select specific drugs via chips
4. **Trust Selection**: Open the drawer to filter by NHS trusts
5. **Directorate Browser**: Navigate directorates → indications → drug fragments in the drawer
6. **Clear Filters**: Reset all selections to show full dataset

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
├── src/                         # All application library code
│   ├── core/                    # Foundation: paths, models, logging
│   ├── config/                  # Snowflake connection settings
│   ├── data_processing/         # Data layer (SQLite, Snowflake, transforms)
│   ├── analysis/                # Analysis pipeline
│   ├── visualization/           # Plotly chart generation
│   └── cli/                     # CLI tools (refresh_pathways)
├── dash_app/                    # Dash web application
│   ├── app.py                   # App entry point, layout, stores
│   ├── assets/nhs.css           # NHS design system CSS
│   ├── data/                    # Query wrappers + card browser data
│   ├── components/              # UI components (header, sidebar, etc.)
│   └── callbacks/               # Dash callbacks (filters, chart, KPI, drawer)
├── run_dash.py                  # Entry point: python run_dash.py
├── data/                        # Reference data + SQLite DB (pathways.db)
├── tests/                       # Test suite (113 tests)
├── docs/                        # Documentation
└── archive/                     # Historical/deprecated code
```

See `CLAUDE.md` for detailed architecture documentation.

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=core --cov=data_processing --cov=analysis

# Run only fast tests
python -m pytest tests/ -v -m "not slow"
```

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

## Troubleshooting

### App won't start

```bash
# Ensure dependencies are installed
uv sync

# Ensure src/ is on Python path
uv run python setup_dev.py

# Try running with uv
uv run python run_dash.py
```

### Database not found

```bash
# Check data/pathways.db exists
python -m data_processing.migrate
```

### Snowflake connection issues

1. Ensure `src/config/snowflake.toml` has the correct account identifier
2. A browser window will open for SSO authentication
3. Verify your network allows Snowflake connections

## Documentation

- [CLAUDE.md](CLAUDE.md) — Technical architecture documentation
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — End-user guide
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Deployment guide

## License

Internal NHS use only. Not for distribution.

## Support

For questions or issues, contact the Medicines Intelligence team.
