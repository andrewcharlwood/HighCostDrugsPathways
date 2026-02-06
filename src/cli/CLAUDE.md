# CLI Package

Command-line interface for pathway data refresh operations.

## refresh_pathways.py

Main CLI module for refreshing pre-computed pathway data from Snowflake to SQLite.

**Key Functions:**
- `refresh_pathways()` — Orchestrates full pipeline: fetch from Snowflake, transform via tools/data.py, generate pathway charts, insert to SQLite
- `insert_pathway_records()` — Bulk inserts using parameterized queries with `INSERT OR REPLACE` (handles overwrites via UNIQUE constraint)
- `log_refresh_start()`, `log_refresh_complete()`, `log_refresh_failed()` — Tracks refresh status in pathway_refresh_log table
- `get_default_filters()` — Loads available trusts, drugs, directories from CSV files

**CLI Arguments:**
- `--chart-type [all|directory|indication]` — Which pathway types to refresh (default: all)
- `--dry-run` — Test without database changes
- `--minimum-patients N` — Pathway nodes with <N patients filtered out (default: 5)
- `-v, --verbose` — Enable debug logging

**Usage:**
```bash
python -m cli.refresh_pathways --chart-type all
python -m cli.refresh_pathways --chart-type indication --dry-run -v
```

**Note:** Module uses sys.path bootstrap at top to enable `python -m cli.refresh_pathways` from project root.
