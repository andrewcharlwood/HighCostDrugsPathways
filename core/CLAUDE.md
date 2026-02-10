# core/ — Foundation Layer

Configuration, state models, and logging setup.

## Modules

**config.py** — `PathConfig` dataclass encapsulating all file paths (data dir, images, CSVs, fonts).
- `validate()` method checks existence of required directories and files
- `default_paths` module instance resolves from `Path.cwd()` (not package location)
- Critical: CWD must be project root for relative paths to work

**models.py** — `AnalysisFilters` dataclass for UI filter state (dates, drugs, trusts, directories).

**logging_config.py** — Structured logging with file + console output.
- `setup_logging()` initializes handlers
- `get_logger(name)` returns configured logger

**__init__.py** — Re-exports `PathConfig`, `default_paths`, `AnalysisFilters` for easy importing.

## Usage

```python
from core import PathConfig, default_paths, AnalysisFilters
default_paths.validate()  # Verify config on startup
```
