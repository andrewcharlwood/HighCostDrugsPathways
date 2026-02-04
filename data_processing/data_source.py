"""
Unified data access layer with fallback chain for NHS Patient Pathway Analysis.

Provides a high-level interface that automatically selects the best available data source:
1. Cache - Returns cached results if valid and not expired
2. Snowflake - Queries Snowflake warehouse if configured and connected
3. Local - Falls back to SQLite database or CSV/Parquet files

The fallback chain handles connection errors, missing configurations, and
unavailable services gracefully, always attempting to provide data from
some source.

Usage:
    from data_processing.data_source import DataSourceManager, get_data

    # Simple usage with automatic source selection
    result = get_data(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        trusts=["TRUST A", "TRUST B"],
    )

    # Or with explicit source preference
    manager = DataSourceManager()
    result = manager.get_data(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        preferred_source="snowflake",
    )
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

import pandas as pd

from core.logging_config import get_logger

logger = get_logger(__name__)


class DataSourceType(Enum):
    """Enumeration of available data sources."""
    CACHE = "cache"
    SNOWFLAKE = "snowflake"
    SQLITE = "sqlite"
    FILE = "file"


@dataclass
class DataSourceResult:
    """Result from data source query.

    Attributes:
        df: The loaded DataFrame with patient intervention data
        source_type: Which data source was used
        source_detail: Additional details about the source (e.g., file path, query hash)
        row_count: Number of rows returned
        cached: Whether the result came from cache
        from_fallback: Whether a fallback source was used
        load_time_seconds: Time taken to load data
        warnings: Any warnings generated during loading
    """
    df: pd.DataFrame
    source_type: DataSourceType
    source_detail: str = ""
    row_count: int = 0
    cached: bool = False
    from_fallback: bool = False
    load_time_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.row_count == 0 and self.df is not None:
            self.row_count = len(self.df)


@dataclass
class SourceStatus:
    """Status of a data source.

    Attributes:
        source_type: The type of data source
        available: Whether the source is available
        configured: Whether the source is properly configured
        message: Status message explaining the state
        last_checked: When the status was last checked
    """
    source_type: DataSourceType
    available: bool = False
    configured: bool = False
    message: str = ""
    last_checked: Optional[datetime] = None


class DataSourceManager:
    """
    Manages data access with automatic fallback between sources.

    The manager attempts to retrieve data from sources in order of preference:
    1. Cache (if enabled and has valid cached data)
    2. Snowflake (if configured and connected)
    3. SQLite (if database exists with data)
    4. Local files (CSV/Parquet)

    Attributes:
        cache_enabled: Whether to use caching
        local_file_path: Path to local CSV/Parquet file (optional fallback)
        sqlite_db_path: Path to SQLite database (optional)

    Example:
        manager = DataSourceManager()

        # Check what sources are available
        status = manager.check_all_sources()
        for s in status:
            print(f"{s.source_type.value}: {s.message}")

        # Get data with automatic fallback
        result = manager.get_data(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
        )
        print(f"Got {result.row_count} rows from {result.source_type.value}")
    """

    def __init__(
        self,
        cache_enabled: bool = True,
        local_file_path: Optional[Path | str] = None,
        sqlite_db_path: Optional[Path | str] = None,
    ):
        """
        Initialize the data source manager.

        Args:
            cache_enabled: Whether to check cache before querying (default True)
            local_file_path: Path to local CSV/Parquet file for file fallback
            sqlite_db_path: Path to SQLite database (uses default if None)
        """
        self._cache_enabled = cache_enabled
        self._local_file_path = Path(local_file_path) if local_file_path else None
        self._sqlite_db_path = Path(sqlite_db_path) if sqlite_db_path else None
        self._source_status: dict[DataSourceType, SourceStatus] = {}

    @property
    def cache_enabled(self) -> bool:
        """Return whether caching is enabled."""
        return self._cache_enabled

    @cache_enabled.setter
    def cache_enabled(self, value: bool):
        """Set whether caching is enabled."""
        self._cache_enabled = value

    def _check_cache_status(self) -> SourceStatus:
        """Check if cache is available."""
        try:
            from data_processing.cache import is_cache_enabled, get_cache

            if not is_cache_enabled():
                return SourceStatus(
                    source_type=DataSourceType.CACHE,
                    available=False,
                    configured=False,
                    message="Cache disabled in configuration",
                    last_checked=datetime.now(),
                )

            cache = get_cache()
            stats = cache.get_stats()

            return SourceStatus(
                source_type=DataSourceType.CACHE,
                available=True,
                configured=True,
                message=f"Cache enabled ({stats.total_entries} entries, {stats.total_size_mb:.1f}MB)",
                last_checked=datetime.now(),
            )
        except Exception as e:
            return SourceStatus(
                source_type=DataSourceType.CACHE,
                available=False,
                configured=False,
                message=f"Cache error: {e}",
                last_checked=datetime.now(),
            )

    def _check_snowflake_status(self) -> SourceStatus:
        """Check if Snowflake is available and configured."""
        try:
            from data_processing.snowflake_connector import (
                is_snowflake_available,
                is_snowflake_configured,
            )

            if not is_snowflake_available():
                return SourceStatus(
                    source_type=DataSourceType.SNOWFLAKE,
                    available=False,
                    configured=False,
                    message="snowflake-connector-python not installed",
                    last_checked=datetime.now(),
                )

            if not is_snowflake_configured():
                return SourceStatus(
                    source_type=DataSourceType.SNOWFLAKE,
                    available=True,
                    configured=False,
                    message="Snowflake account not configured in config/snowflake.toml",
                    last_checked=datetime.now(),
                )

            return SourceStatus(
                source_type=DataSourceType.SNOWFLAKE,
                available=True,
                configured=True,
                message="Snowflake configured and ready",
                last_checked=datetime.now(),
            )
        except Exception as e:
            return SourceStatus(
                source_type=DataSourceType.SNOWFLAKE,
                available=False,
                configured=False,
                message=f"Snowflake error: {e}",
                last_checked=datetime.now(),
            )

    def _check_sqlite_status(self) -> SourceStatus:
        """Check if SQLite database is available with data."""
        try:
            from data_processing.database import default_db_manager, default_db_config

            db_path = self._sqlite_db_path or Path(default_db_config.db_path)

            if not db_path.exists():
                return SourceStatus(
                    source_type=DataSourceType.SQLITE,
                    available=False,
                    configured=True,
                    message=f"Database not found: {db_path}",
                    last_checked=datetime.now(),
                )

            from data_processing.database import DatabaseManager, DatabaseConfig

            config = DatabaseConfig(db_path=db_path)
            manager = DatabaseManager(config)

            if not manager.table_exists("fact_interventions"):
                return SourceStatus(
                    source_type=DataSourceType.SQLITE,
                    available=False,
                    configured=True,
                    message="fact_interventions table not found",
                    last_checked=datetime.now(),
                )

            count = manager.get_table_count("fact_interventions")
            if count == 0:
                return SourceStatus(
                    source_type=DataSourceType.SQLITE,
                    available=False,
                    configured=True,
                    message="fact_interventions table is empty",
                    last_checked=datetime.now(),
                )

            return SourceStatus(
                source_type=DataSourceType.SQLITE,
                available=True,
                configured=True,
                message=f"SQLite database ready ({count:,} rows)",
                last_checked=datetime.now(),
            )
        except Exception as e:
            return SourceStatus(
                source_type=DataSourceType.SQLITE,
                available=False,
                configured=False,
                message=f"SQLite error: {e}",
                last_checked=datetime.now(),
            )

    def _check_file_status(self) -> SourceStatus:
        """Check if local file is available."""
        if self._local_file_path is None:
            return SourceStatus(
                source_type=DataSourceType.FILE,
                available=False,
                configured=False,
                message="No local file path configured",
                last_checked=datetime.now(),
            )

        if not self._local_file_path.exists():
            return SourceStatus(
                source_type=DataSourceType.FILE,
                available=False,
                configured=True,
                message=f"File not found: {self._local_file_path}",
                last_checked=datetime.now(),
            )

        size_mb = self._local_file_path.stat().st_size / (1024 * 1024)
        return SourceStatus(
            source_type=DataSourceType.FILE,
            available=True,
            configured=True,
            message=f"Local file ready: {self._local_file_path.name} ({size_mb:.1f}MB)",
            last_checked=datetime.now(),
        )

    def check_source_status(self, source_type: DataSourceType) -> SourceStatus:
        """
        Check the status of a specific data source.

        Args:
            source_type: The type of source to check

        Returns:
            SourceStatus with current availability information
        """
        if source_type == DataSourceType.CACHE:
            return self._check_cache_status()
        elif source_type == DataSourceType.SNOWFLAKE:
            return self._check_snowflake_status()
        elif source_type == DataSourceType.SQLITE:
            return self._check_sqlite_status()
        elif source_type == DataSourceType.FILE:
            return self._check_file_status()
        else:
            return SourceStatus(
                source_type=source_type,
                available=False,
                configured=False,
                message=f"Unknown source type: {source_type}",
                last_checked=datetime.now(),
            )

    def check_all_sources(self) -> list[SourceStatus]:
        """
        Check the status of all data sources.

        Returns:
            List of SourceStatus for each source type
        """
        statuses = []
        for source_type in DataSourceType:
            status = self.check_source_status(source_type)
            self._source_status[source_type] = status
            statuses.append(status)
        return statuses

    def _build_cache_key_params(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
        trusts: Optional[list[str]],
        drugs: Optional[list[str]],
        directories: Optional[list[str]],
    ) -> tuple[str, tuple]:
        """Build a cache-compatible query string and params for the filter criteria."""
        # Create a canonical representation for caching
        query_parts = ["SELECT * FROM activity_data"]
        params = []

        conditions = []
        if start_date:
            conditions.append("start_date >= ?")
            params.append(str(start_date))
        if end_date:
            conditions.append("end_date <= ?")
            params.append(str(end_date))
        if trusts:
            placeholders = ",".join(["?"] * len(trusts))
            conditions.append(f"trust IN ({placeholders})")
            params.extend(sorted(trusts))
        if drugs:
            placeholders = ",".join(["?"] * len(drugs))
            conditions.append(f"drug IN ({placeholders})")
            params.extend(sorted(drugs))
        if directories:
            placeholders = ",".join(["?"] * len(directories))
            conditions.append(f"directory IN ({placeholders})")
            params.extend(sorted(directories))

        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))

        query = " ".join(query_parts)
        return query, tuple(params)

    def _try_cache(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
        trusts: Optional[list[str]],
        drugs: Optional[list[str]],
        directories: Optional[list[str]],
    ) -> Optional[DataSourceResult]:
        """Try to get data from cache."""
        if not self._cache_enabled:
            return None

        try:
            from data_processing.cache import get_cache

            cache = get_cache()
            if not cache.is_enabled:
                return None

            query, params = self._build_cache_key_params(
                start_date, end_date, trusts, drugs, directories
            )

            cached_data = cache.get(query, params)
            if cached_data is None:
                logger.debug("Cache miss")
                return None

            # Convert cached data back to DataFrame
            df = pd.DataFrame(cached_data)

            # Convert date columns
            if 'Intervention Date' in df.columns:
                df['Intervention Date'] = pd.to_datetime(df['Intervention Date'])

            logger.info(f"Cache hit: {len(df)} rows")

            return DataSourceResult(
                df=df,
                source_type=DataSourceType.CACHE,
                source_detail=f"cache_key={query[:50]}...",
                row_count=len(df),
                cached=True,
                from_fallback=False,
            )
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            return None

    def _try_snowflake(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
        trusts: Optional[list[str]],
        drugs: Optional[list[str]],
        directories: Optional[list[str]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[DataSourceResult]:
        """Try to get data from Snowflake."""
        import time

        try:
            from data_processing.snowflake_connector import (
                is_snowflake_available,
                is_snowflake_configured,
                get_connector,
                SnowflakeConnectionError,
            )

            if not is_snowflake_available():
                logger.debug("Snowflake connector not installed")
                return None

            if not is_snowflake_configured():
                logger.debug("Snowflake not configured")
                return None

            # Get connector and fetch data
            connector = get_connector()
            logger.info("Fetching data from Snowflake...")
            start_time = time.time()

            # Fetch activity data from Snowflake
            # Note: provider_codes filter not directly supported yet - would need trust name to code mapping
            rows = connector.fetch_activity_data(
                start_date=start_date,
                end_date=end_date,
                provider_codes=None,  # TODO: map trust names to provider codes if needed
            )

            if not rows:
                logger.warning("Snowflake returned no data")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(rows)
            load_time = time.time() - start_time

            logger.info(f"Snowflake loaded {len(df)} rows in {load_time:.2f}s")

            # Apply local transformations to match expected format
            # (patient_id, drug_names, department_identification)
            from tools.data import patient_id, drug_names, department_identification
            from core import default_paths

            df = patient_id(df)
            df = drug_names(df, paths=default_paths)
            df = department_identification(df, paths=default_paths)

            # Apply additional filters if provided
            if trusts and 'OrganisationName' in df.columns:
                df = df[df['OrganisationName'].isin(trusts)]
            if drugs and 'Drug Name' in df.columns:
                df = df[df['Drug Name'].isin(drugs)]
            if directories and 'Directory' in df.columns:
                df = df[df['Directory'].isin(directories)]

            return DataSourceResult(
                df=df,
                source_type=DataSourceType.SNOWFLAKE,
                source_detail="DATA_HUB.CDM.Acute__Conmon__PatientLevelDrugs",
                row_count=len(df),
                cached=False,
                from_fallback=False,
                load_time_seconds=load_time,
            )

        except Exception as e:
            logger.warning(f"Snowflake query failed: {e}")
            return None

    def _try_sqlite(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
        trusts: Optional[list[str]],
        drugs: Optional[list[str]],
        directories: Optional[list[str]],
    ) -> Optional[DataSourceResult]:
        """Try to get data from SQLite."""
        import time

        try:
            from data_processing.loader import SQLiteDataLoader

            # Determine database path
            db_path = self._sqlite_db_path
            if db_path is None:
                from data_processing.database import default_db_config
                db_path = Path(default_db_config.db_path)

            loader = SQLiteDataLoader(
                db_path=db_path,
                date_range=(start_date, end_date) if start_date and end_date else None,
                trusts=trusts,
                drugs=drugs,
                directories=directories,
            )

            # Check if source is valid
            is_valid, msg = loader.validate_source()
            if not is_valid:
                logger.debug(f"SQLite not available: {msg}")
                return None

            start_time = time.time()
            result = loader.load()
            load_time = time.time() - start_time

            logger.info(f"SQLite loaded {result.row_count} rows in {load_time:.2f}s")

            return DataSourceResult(
                df=result.df,
                source_type=DataSourceType.SQLITE,
                source_detail=str(db_path),
                row_count=result.row_count,
                cached=False,
                from_fallback=False,
                load_time_seconds=load_time,
            )
        except Exception as e:
            logger.warning(f"SQLite query failed: {e}")
            return None

    def _try_file(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
        trusts: Optional[list[str]],
        drugs: Optional[list[str]],
        directories: Optional[list[str]],
    ) -> Optional[DataSourceResult]:
        """Try to get data from local file."""
        import time

        if self._local_file_path is None:
            logger.debug("No local file configured")
            return None

        try:
            from data_processing.loader import FileDataLoader

            loader = FileDataLoader(file_path=self._local_file_path)

            is_valid, msg = loader.validate_source()
            if not is_valid:
                logger.debug(f"Local file not available: {msg}")
                return None

            start_time = time.time()
            result = loader.load()
            df = result.df

            # Apply filters (file loader loads all data, then we filter)
            if start_date and 'Intervention Date' in df.columns:
                df = df[df['Intervention Date'] >= pd.Timestamp(start_date)]
            if end_date and 'Intervention Date' in df.columns:
                df = df[df['Intervention Date'] < pd.Timestamp(end_date)]
            if trusts and 'OrganisationName' in df.columns:
                df = df[df['OrganisationName'].isin(trusts)]
            if drugs and 'Drug Name' in df.columns:
                df = df[df['Drug Name'].isin(drugs)]
            if directories and 'Directory' in df.columns:
                df = df[df['Directory'].isin(directories)]

            load_time = time.time() - start_time

            logger.info(f"File loaded and filtered: {len(df)} rows in {load_time:.2f}s")

            return DataSourceResult(
                df=df,
                source_type=DataSourceType.FILE,
                source_detail=str(self._local_file_path),
                row_count=len(df),
                cached=False,
                from_fallback=True,
                load_time_seconds=load_time,
            )
        except Exception as e:
            logger.warning(f"File load failed: {e}")
            return None

    def get_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        trusts: Optional[list[str]] = None,
        drugs: Optional[list[str]] = None,
        directories: Optional[list[str]] = None,
        preferred_source: Optional[str] = None,
        skip_cache: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DataSourceResult:
        """
        Get patient intervention data from the best available source.

        The fallback chain is: Cache → Snowflake → SQLite → File

        Args:
            start_date: Optional start date for filtering (inclusive)
            end_date: Optional end date for filtering (exclusive)
            trusts: Optional list of trust names to filter
            drugs: Optional list of drug names to filter
            directories: Optional list of directories to filter
            preferred_source: Optional preferred source ("snowflake", "sqlite", "file")
            skip_cache: If True, bypass cache and query source directly
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            DataSourceResult with the loaded data and metadata

        Raises:
            ValueError: If no data source is available or all sources fail
        """
        import time
        start_time = time.time()
        warnings = []

        # If preferred source specified, try that first
        if preferred_source:
            preferred = preferred_source.lower()
            if preferred == "snowflake":
                result = self._try_snowflake(
                    start_date, end_date, trusts, drugs, directories, progress_callback
                )
                if result:
                    result.load_time_seconds = time.time() - start_time
                    return result
                warnings.append("Preferred source 'snowflake' unavailable")

            elif preferred == "sqlite":
                result = self._try_sqlite(
                    start_date, end_date, trusts, drugs, directories
                )
                if result:
                    result.load_time_seconds = time.time() - start_time
                    return result
                warnings.append("Preferred source 'sqlite' unavailable")

            elif preferred == "file":
                result = self._try_file(
                    start_date, end_date, trusts, drugs, directories
                )
                if result:
                    result.load_time_seconds = time.time() - start_time
                    return result
                warnings.append("Preferred source 'file' unavailable")

        # Standard fallback chain: cache → snowflake → sqlite → file

        # 1. Try cache first (unless skipped)
        if not skip_cache:
            result = self._try_cache(
                start_date, end_date, trusts, drugs, directories
            )
            if result:
                result.load_time_seconds = time.time() - start_time
                return result

        # 2. Try Snowflake
        result = self._try_snowflake(
            start_date, end_date, trusts, drugs, directories, progress_callback
        )
        if result:
            # Cache the result for future queries
            if self._cache_enabled:
                self._cache_result(
                    result.df,
                    start_date, end_date, trusts, drugs, directories,
                    includes_current_data=end_date is None or end_date >= date.today()
                )
            result.load_time_seconds = time.time() - start_time
            return result

        # 3. Try SQLite
        result = self._try_sqlite(
            start_date, end_date, trusts, drugs, directories
        )
        if result:
            result.from_fallback = True  # Mark as fallback since Snowflake wasn't used
            result.load_time_seconds = time.time() - start_time
            if warnings:
                result.warnings.extend(warnings)
            return result

        # 4. Try local file
        result = self._try_file(
            start_date, end_date, trusts, drugs, directories
        )
        if result:
            result.from_fallback = True
            result.load_time_seconds = time.time() - start_time
            if warnings:
                result.warnings.extend(warnings)
            return result

        # All sources failed
        source_status = self.check_all_sources()
        status_msg = "; ".join(
            f"{s.source_type.value}: {s.message}" for s in source_status
        )
        raise ValueError(f"No data source available. Status: {status_msg}")

    def _cache_result(
        self,
        df: pd.DataFrame,
        start_date: Optional[date],
        end_date: Optional[date],
        trusts: Optional[list[str]],
        drugs: Optional[list[str]],
        directories: Optional[list[str]],
        includes_current_data: bool = False,
    ) -> bool:
        """Cache a query result for future use."""
        try:
            from data_processing.cache import get_cache

            cache = get_cache()
            if not cache.is_enabled:
                return False

            query, params = self._build_cache_key_params(
                start_date, end_date, trusts, drugs, directories
            )

            # Convert DataFrame to list of dicts for caching
            # Convert datetime columns to strings for JSON serialization
            df_copy = df.copy()
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].astype(str)

            data = df_copy.to_dict(orient='records')

            entry = cache.set(
                query, params, data,
                includes_current_data=includes_current_data
            )

            if entry:
                logger.info(f"Cached {len(data)} rows (key={entry.cache_key[:16]}...)")
                return True
            return False

        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
            return False

    def clear_cache(self) -> int:
        """
        Clear all cached data.

        Returns:
            Number of cache entries cleared
        """
        try:
            from data_processing.cache import get_cache
            cache = get_cache()
            return cache.clear()
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")
            return 0

    def refresh_from_snowflake(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        trusts: Optional[list[str]] = None,
        drugs: Optional[list[str]] = None,
        directories: Optional[list[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DataSourceResult:
        """
        Force a refresh from Snowflake, bypassing cache and other sources.

        This method specifically queries Snowflake and will fail if Snowflake
        is not available or not configured.

        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            trusts: Optional list of trust names
            drugs: Optional list of drug names
            directories: Optional list of directories
            progress_callback: Optional progress callback

        Returns:
            DataSourceResult from Snowflake

        Raises:
            ValueError: If Snowflake is not available or query fails
        """
        from data_processing.snowflake_connector import (
            is_snowflake_available,
            is_snowflake_configured,
        )

        if not is_snowflake_available():
            raise ValueError("Snowflake connector not installed")

        if not is_snowflake_configured():
            raise ValueError("Snowflake not configured - edit config/snowflake.toml")

        result = self._try_snowflake(
            start_date, end_date, trusts, drugs, directories, progress_callback
        )

        if result is None:
            raise ValueError("Snowflake query failed - check logs for details")

        # Cache the fresh result
        if self._cache_enabled:
            self._cache_result(
                result.df,
                start_date, end_date, trusts, drugs, directories,
                includes_current_data=end_date is None or end_date >= date.today()
            )

        return result


# Module-level singleton and convenience functions
_default_manager: Optional[DataSourceManager] = None


def get_data_source_manager(
    cache_enabled: bool = True,
    local_file_path: Optional[Path | str] = None,
    sqlite_db_path: Optional[Path | str] = None,
) -> DataSourceManager:
    """
    Get a DataSourceManager instance.

    Args:
        cache_enabled: Whether to enable caching
        local_file_path: Optional path to local CSV/Parquet file
        sqlite_db_path: Optional path to SQLite database

    Returns:
        DataSourceManager instance
    """
    global _default_manager

    # If custom paths provided, create a new manager
    if local_file_path or sqlite_db_path:
        return DataSourceManager(
            cache_enabled=cache_enabled,
            local_file_path=local_file_path,
            sqlite_db_path=sqlite_db_path,
        )

    # Otherwise use/create singleton
    if _default_manager is None:
        _default_manager = DataSourceManager(cache_enabled=cache_enabled)

    return _default_manager


def get_data(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    trusts: Optional[list[str]] = None,
    drugs: Optional[list[str]] = None,
    directories: Optional[list[str]] = None,
    preferred_source: Optional[str] = None,
    skip_cache: bool = False,
) -> DataSourceResult:
    """
    Convenience function to get data using the default manager.

    Args:
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        trusts: Optional list of trust names
        drugs: Optional list of drug names
        directories: Optional list of directories
        preferred_source: Optional preferred source
        skip_cache: If True, bypass cache

    Returns:
        DataSourceResult with loaded data
    """
    manager = get_data_source_manager()
    return manager.get_data(
        start_date=start_date,
        end_date=end_date,
        trusts=trusts,
        drugs=drugs,
        directories=directories,
        preferred_source=preferred_source,
        skip_cache=skip_cache,
    )


def reset_data_source_manager() -> None:
    """Reset the default data source manager singleton."""
    global _default_manager
    _default_manager = None


# Export public API
__all__ = [
    "DataSourceType",
    "DataSourceResult",
    "SourceStatus",
    "DataSourceManager",
    "get_data_source_manager",
    "get_data",
    "reset_data_source_manager",
]
