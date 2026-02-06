"""
Configuration module for Patient Pathway Analysis.

This module provides access to configuration settings loaded from TOML files.
Primary configuration file: config/snowflake.toml

Usage:
    from config import load_snowflake_config, SnowflakeConfig

    config = load_snowflake_config()
    print(config.connection.account)
    print(config.cache.ttl_seconds)
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


@dataclass
class ConnectionConfig:
    """Snowflake connection settings."""
    account: str = ""
    warehouse: str = "ANALYST_WH"
    database: str = "DATA_HUB"
    schema: str = "DWH"
    authenticator: str = "externalbrowser"
    user: str = ""
    role: str = ""


@dataclass
class TimeoutConfig:
    """Timeout settings for Snowflake operations."""
    connection_timeout: int = 30
    query_timeout: int = 300
    login_timeout: int = 120


@dataclass
class CacheConfig:
    """Cache settings for Snowflake query results."""
    enabled: bool = True
    directory: str = "data/cache"
    ttl_seconds: int = 86400  # 24 hours
    ttl_current_data_seconds: int = 3600  # 1 hour
    max_size_mb: int = 500


@dataclass
class TableReference:
    """Reference to a Snowflake table or view."""
    database: str = ""
    schema: str = ""
    view: str = ""
    table: str = ""
    key_columns: list = field(default_factory=list)

    @property
    def fully_qualified_name(self) -> str:
        """Return the fully qualified table/view name."""
        obj_name = self.table or self.view
        if not obj_name:
            return ""
        if self.database and self.schema:
            return f'"{self.database}"."{self.schema}"."{obj_name}"'
        elif self.schema:
            return f'"{self.schema}"."{obj_name}"'
        else:
            return f'"{obj_name}"'


@dataclass
class TablesConfig:
    """Configuration for commonly used tables."""
    activity: TableReference = field(default_factory=TableReference)
    patient: TableReference = field(default_factory=TableReference)
    medication: TableReference = field(default_factory=TableReference)
    organization: TableReference = field(default_factory=TableReference)


@dataclass
class QueryConfig:
    """Query execution settings."""
    quote_identifiers: bool = True
    test_limit: int = 20
    max_rows: int = 100000
    chunk_size: int = 10000


@dataclass
class SnowflakeConfig:
    """Complete Snowflake configuration."""
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    tables: TablesConfig = field(default_factory=TablesConfig)
    query: QueryConfig = field(default_factory=QueryConfig)

    def validate(self) -> list[str]:
        """
        Validate the configuration.

        Returns:
            List of error messages (empty if valid).
        """
        errors = []

        if not self.connection.account:
            errors.append("Snowflake account is not configured (connection.account)")

        if not self.connection.warehouse:
            errors.append("Snowflake warehouse is not configured (connection.warehouse)")

        if self.connection.authenticator not in ("externalbrowser", "snowflake", "oauth", "okta"):
            errors.append(f"Invalid authenticator: {self.connection.authenticator}")

        if self.cache.ttl_seconds < 0:
            errors.append("Cache TTL must be non-negative")

        if self.query.max_rows < 1:
            errors.append("max_rows must be at least 1")

        return errors

    @property
    def is_configured(self) -> bool:
        """Return True if minimum required settings are present."""
        return bool(self.connection.account)


def _parse_table_reference(data: dict) -> TableReference:
    """Parse a table reference from TOML data."""
    return TableReference(
        database=data.get("database", ""),
        schema=data.get("schema", ""),
        view=data.get("view", ""),
        table=data.get("table", ""),
        key_columns=data.get("key_columns", []),
    )


def load_snowflake_config(config_path: Optional[Path] = None) -> SnowflakeConfig:
    """
    Load Snowflake configuration from TOML file.

    Args:
        config_path: Path to the TOML config file. Defaults to config/snowflake.toml
                     relative to the project root.

    Returns:
        SnowflakeConfig dataclass with all settings.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        tomllib.TOMLDecodeError: If the TOML is invalid.
    """
    if config_path is None:
        # Default to config/snowflake.toml relative to this file's directory
        config_path = Path(__file__).parent / "snowflake.toml"

    if not config_path.exists():
        # Return default config if file doesn't exist
        return SnowflakeConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Parse connection settings
    conn_data = data.get("connection", {})
    connection = ConnectionConfig(
        account=conn_data.get("account", ""),
        warehouse=conn_data.get("warehouse", "ANALYST_WH"),
        database=conn_data.get("database", "DATA_HUB"),
        schema=conn_data.get("schema", "DWH"),
        authenticator=conn_data.get("authenticator", "externalbrowser"),
        user=conn_data.get("user", ""),
        role=conn_data.get("role", ""),
    )

    # Parse timeout settings
    timeout_data = data.get("timeouts", {})
    timeouts = TimeoutConfig(
        connection_timeout=timeout_data.get("connection_timeout", 600),
        query_timeout=timeout_data.get("query_timeout", 300),
        login_timeout=timeout_data.get("login_timeout", 120),
    )

    # Parse cache settings
    cache_data = data.get("cache", {})
    cache = CacheConfig(
        enabled=cache_data.get("enabled", True),
        directory=cache_data.get("directory", "data/cache"),
        ttl_seconds=cache_data.get("ttl_seconds", 86400),
        ttl_current_data_seconds=cache_data.get("ttl_current_data_seconds", 3600),
        max_size_mb=cache_data.get("max_size_mb", 500),
    )

    # Parse table references
    tables_data = data.get("tables", {})
    tables = TablesConfig(
        activity=_parse_table_reference(tables_data.get("activity", {})),
        patient=_parse_table_reference(tables_data.get("patient", {})),
        medication=_parse_table_reference(tables_data.get("medication", {})),
        organization=_parse_table_reference(tables_data.get("organization", {})),
    )

    # Parse query settings
    query_data = data.get("query", {})
    query = QueryConfig(
        quote_identifiers=query_data.get("quote_identifiers", True),
        test_limit=query_data.get("test_limit", 20),
        max_rows=query_data.get("max_rows", 100000),
        chunk_size=query_data.get("chunk_size", 10000),
    )

    return SnowflakeConfig(
        connection=connection,
        timeouts=timeouts,
        cache=cache,
        tables=tables,
        query=query,
    )


# Module-level cached config (loaded on first access)
_cached_config: Optional[SnowflakeConfig] = None


def get_snowflake_config() -> SnowflakeConfig:
    """
    Get the Snowflake configuration (cached after first load).

    Returns:
        SnowflakeConfig dataclass with all settings.
    """
    global _cached_config
    if _cached_config is None:
        _cached_config = load_snowflake_config()
    return _cached_config


def reload_snowflake_config() -> SnowflakeConfig:
    """
    Reload the Snowflake configuration from disk.

    Returns:
        SnowflakeConfig dataclass with all settings.
    """
    global _cached_config
    _cached_config = load_snowflake_config()
    return _cached_config


# Export public API
__all__ = [
    "SnowflakeConfig",
    "ConnectionConfig",
    "TimeoutConfig",
    "CacheConfig",
    "TableReference",
    "TablesConfig",
    "QueryConfig",
    "load_snowflake_config",
    "get_snowflake_config",
    "reload_snowflake_config",
]
