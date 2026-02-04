# NHS High-Cost Drug Patient Pathway Analysis Tool

A web-based application for analyzing secondary care patient treatment pathways. It processes clinical activity data to visualize hierarchical treatment patterns (Trust → Directory/Specialty → Drug → Patient pathway) as interactive Plotly icicle charts.

## Features

- **Interactive Visualization**: Plotly icicle charts showing patient treatment hierarchies with cost and frequency statistics
- **Multi-Source Data Loading**: CSV/Parquet files, SQLite database, or direct Snowflake integration
- **GP Diagnosis Validation**: Validate patient indications against GP SNOMED codes via NHS Snowflake
- **Modern Web Interface**: Browser-based UI using Reflex framework with NHS branding
- **Flexible Filtering**: Filter by date range, NHS trusts, drugs, and medical directories
- **Export Options**: Export charts as interactive HTML or data as CSV

## Requirements

- Python 3.10 or higher
- pip or uv package manager

### Optional (for Snowflake integration)
- `snowflake-connector-python` package
- Access to NHS Snowflake data warehouse with SSO authentication

## Installation

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd patient-pathway-analysis

# Install dependencies
pip install -r requirements.txt
```

### Using uv (recommended)

```bash
# Install uv if not already installed
pip install uv

# Sync dependencies
uv sync
```

### Install with test dependencies

```bash
pip install -e ".[test]"
```

## Quick Start

### 1. Run the Web Application (Recommended)

```bash
reflex run
```

Open http://localhost:3000 in your browser.

## Usage

### Web Interface (Reflex)

1. **Load Data**: On the home page, select your data source:
   - **SQLite Database**: Uses pre-loaded data from `data/pathways.db`
   - **File Upload**: Drag and drop a CSV or Parquet file
   - **Snowflake**: Fetch data directly from NHS Snowflake (requires configuration)

2. **Configure Filters**:
   - Set date range (Start Date, End Date, Last Seen After)
   - Navigate to Drug/Trust/Directory selection pages using the sidebar
   - Use search boxes to find and select items
   - Set minimum patient threshold to filter small groups

3. **Run Analysis**: Click "Run Analysis" to generate the icicle chart

4. **Export Results**:
   - **Export HTML**: Save the interactive chart as a standalone HTML file
   - **Export CSV**: Export the filtered data as a CSV file

### Data Migration

To populate the SQLite database from CSV files:

```bash
# Initialize database schema
python -m data_processing.migrate

# Load reference data from CSV files
python -m data_processing.migrate --reference-data --verify

# Load patient data from a CSV/Parquet file
python -m data_processing.migrate --load-patient-data path/to/data.csv
```

### Snowflake Configuration

To use Snowflake integration, edit `config/snowflake.toml`:

```toml
[connection]
account = "your-account-identifier"
warehouse = "your-warehouse"
database = "DATA_HUB"
schema = "CDM"
authenticator = "externalbrowser"  # NHS SSO authentication
```

## Project Structure

```
.
├── core/                    # Core configuration and models
├── data_processing/         # Data layer (SQLite, Snowflake, loaders)
├── analysis/                # Analysis pipeline (refactored from generate_graph)
├── visualization/           # Chart generation (Plotly)
├── pathways_app/            # Reflex web application
├── tools/                   # Legacy modules (original analysis engine)
├── config/                  # Configuration files
├── data/                    # Reference data and SQLite database
├── docs/                    # Additional documentation
└── tests/                   # Test suite
```

See `CLAUDE.md` for detailed architecture documentation.

## Documentation

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - End-user guide for using the web interface
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment guide (Docker, nginx, cloud)
- [CLAUDE.md](CLAUDE.md) - Technical architecture documentation for developers

## Deployment

Quick production start:

```bash
# Run in production mode
reflex run --env prod
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=core --cov=data_processing --cov=analysis

# Run only fast tests (exclude slow/integration)
python -m pytest tests/ -v -m "not slow"
```

## Reference Data Files

The `data/` directory contains essential reference files:

| File | Purpose |
|------|---------|
| `include.csv` | Drug filter list with default selections |
| `defaultTrusts.csv` | NHS Trust list for filtering |
| `directory_list.csv` | Medical specialties/directories |
| `drugnames.csv` | Drug name standardization mapping |
| `org_codes.csv` | Provider code to organization name mapping |
| `drug_directory_list.csv` | Valid drug-to-directory mappings |
| `drug_indication_clusters.csv` | Drug to SNOMED cluster mappings |
| `ta-recommendations.xlsx` | NICE TA recommendations |

## Troubleshooting

### Reflex compilation errors

If you encounter compilation errors when running `reflex run`:

```bash
# Clear the build cache and restart
rm -rf .web
reflex run
```

### Snowflake connection issues

1. Ensure `snowflake-connector-python` is installed:
   ```bash
   pip install snowflake-connector-python
   ```

2. Check that `config/snowflake.toml` has the correct account identifier

3. For SSO authentication, a browser window will open automatically

### SQLite database not found

If `data/pathways.db` doesn't exist, create it:

```bash
python -m data_processing.migrate
python -m data_processing.migrate --reference-data
```

## Development

### Code Quality

```bash
# Type checking
python -m mypy core/ data_processing/ analysis/ --ignore-missing-imports

# Run tests with coverage report
python -m pytest tests/ -v --cov=core --cov=data_processing --cov-report=html
```

### Adding New Reference Data

1. Add CSV file to `data/` directory
2. Define schema in `data_processing/schema.py`
3. Create migration function in `data_processing/reference_data.py`
4. Add path to `PathConfig` in `core/config.py`

## License

Internal NHS use only. Not for distribution.

## Support

For questions or issues, contact the Medicines Intelligence team.
