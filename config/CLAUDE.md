# Config Package

Snowflake configuration management with dataclass hierarchy and TOML loading.

## Modules

**__init__.py** - Configuration dataclass hierarchy:
- `ConnectionConfig`, `TimeoutConfig`, `CacheConfig`, `QueryConfig` — Settings containers
- `TableReference` — Snowflake object reference with `fully_qualified_name` property
- `TablesConfig` — Common table references (activity, patient, medication, organization)
- `SnowflakeConfig` — Root config aggregating all above + `validate()` and `is_configured` property
- `load_snowflake_config(path=None)` — Load from TOML, default `config/snowflake.toml`
- `get_snowflake_config()` — Cached singleton access
- `reload_snowflake_config()` — Force reload from disk

**snowflake.toml** — Snowflake connection settings (co-located with loader)

## Key Details

- Uses `tomllib` (Python 3.11+) with `tomli` fallback for 3.10
- Missing config file returns default SnowflakeConfig (no error)
- All dataclasses have sensible defaults (DATA_HUB.DWH, 24h cache TTL, etc.)
- Config is stateless but cached; call `reload_snowflake_config()` to refresh
