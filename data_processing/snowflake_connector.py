"""
Snowflake connector module for NHS Patient Pathway Analysis.

Provides connection handling with SSO browser authentication for NHS environments.
Uses the externalbrowser authenticator which opens a browser window for NHS identity
management authentication.

Usage:
    from data_processing.snowflake_connector import SnowflakeConnector, get_connector

    # Using context manager (recommended)
    with get_connector() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM table LIMIT 10")
        results = cursor.fetchall()

    # Manual connection management
    connector = SnowflakeConnector()
    try:
        conn = connector.connect()
        cursor = conn.cursor()
        # ... use cursor ...
    finally:
        connector.close()
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Generator, Optional, TYPE_CHECKING
import time

# Snowflake connector is an optional dependency
SNOWFLAKE_AVAILABLE = False
try:
    import snowflake.connector
    from snowflake.connector import SnowflakeConnection
    from snowflake.connector.cursor import SnowflakeCursor
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    snowflake = None  # type: ignore[assignment]

# Type hints for when snowflake is not available
if TYPE_CHECKING:
    from snowflake.connector import SnowflakeConnection
    from snowflake.connector.cursor import SnowflakeCursor

from config import get_snowflake_config, SnowflakeConfig
from core.logging_config import get_logger

logger = get_logger(__name__)


class SnowflakeConnectionError(Exception):
    """Raised when Snowflake connection fails."""
    pass


class SnowflakeNotConfiguredError(Exception):
    """Raised when Snowflake is not configured (no account)."""
    pass


class SnowflakeNotAvailableError(Exception):
    """Raised when snowflake-connector-python is not installed."""
    pass


@dataclass
class ConnectionInfo:
    """Information about the current connection state."""
    connected: bool = False
    account: str = ""
    warehouse: str = ""
    database: str = ""
    schema: str = ""
    user: str = ""
    role: str = ""
    connected_at: Optional[datetime] = None
    last_query_at: Optional[datetime] = None
    query_count: int = 0


class SnowflakeConnector:
    """
    Manages Snowflake connections with SSO browser authentication.

    This class provides connection management for NHS Snowflake access using
    the externalbrowser authenticator which triggers NHS SSO login via browser.

    Attributes:
        config: SnowflakeConfig with connection settings
        connection_info: ConnectionInfo tracking current state

    Example:
        connector = SnowflakeConnector()
        with connector.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_USER()")
            print(cursor.fetchone()[0])
    """

    def __init__(self, config: Optional[SnowflakeConfig] = None):
        """
        Initialize the connector with configuration.

        Args:
            config: Optional SnowflakeConfig. If not provided, loads from
                    config/snowflake.toml using get_snowflake_config().
        """
        self._config = config or get_snowflake_config()
        self._connection: Optional[SnowflakeConnection] = None
        self._connection_info = ConnectionInfo()

    @property
    def config(self) -> SnowflakeConfig:
        """Return the Snowflake configuration."""
        return self._config

    @property
    def connection_info(self) -> ConnectionInfo:
        """Return information about the current connection state."""
        return self._connection_info

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to Snowflake."""
        return self._connection is not None and not self._connection.is_closed()

    def _check_availability(self) -> None:
        """Check that snowflake-connector-python is installed."""
        if not SNOWFLAKE_AVAILABLE:
            raise SnowflakeNotAvailableError(
                "snowflake-connector-python is not installed. "
                "Install it with: pip install snowflake-connector-python"
            )

    def _check_configured(self) -> None:
        """Check that Snowflake is configured."""
        if not self._config.is_configured:
            raise SnowflakeNotConfiguredError(
                "Snowflake account is not configured. "
                "Edit config/snowflake.toml and set connection.account"
            )

    def connect(self) -> SnowflakeConnection:
        """
        Establish a connection to Snowflake.

        Uses the externalbrowser authenticator which opens a browser window
        for NHS SSO authentication. The browser popup is expected and normal.

        Returns:
            Active SnowflakeConnection

        Raises:
            SnowflakeNotAvailableError: If snowflake-connector-python not installed
            SnowflakeNotConfiguredError: If account is not configured
            SnowflakeConnectionError: If connection fails
        """
        self._check_availability()
        self._check_configured()

        # Close existing connection if any
        if self._connection is not None:
            self.close()

        conn_cfg = self._config.connection
        timeout_cfg = self._config.timeouts

        logger.info(f"Connecting to Snowflake account: {conn_cfg.account}")
        logger.info(f"Using warehouse: {conn_cfg.warehouse}, database: {conn_cfg.database}")
        logger.info(f"Authenticator: {conn_cfg.authenticator}")
        if conn_cfg.authenticator == "externalbrowser":
            logger.info("Browser window will open for NHS SSO authentication")

        start_time = time.time()

        try:
            # Build connection parameters
            connect_params = {
                "account": conn_cfg.account,
                "warehouse": conn_cfg.warehouse,
                "database": conn_cfg.database,
                "schema": conn_cfg.schema,
                "authenticator": conn_cfg.authenticator,
                "login_timeout": timeout_cfg.login_timeout,
                "network_timeout": timeout_cfg.connection_timeout,
            }

            # Optional parameters (only add if set)
            if conn_cfg.user:
                connect_params["user"] = conn_cfg.user
            if conn_cfg.role:
                connect_params["role"] = conn_cfg.role

            self._connection = snowflake.connector.connect(**connect_params)

            elapsed = time.time() - start_time
            logger.info(f"Connected to Snowflake successfully in {elapsed:.1f}s")

            # Update connection info
            self._connection_info = ConnectionInfo(
                connected=True,
                account=conn_cfg.account,
                warehouse=conn_cfg.warehouse,
                database=conn_cfg.database,
                schema=conn_cfg.schema,
                user=self._get_current_user(),
                role=self._get_current_role(),
                connected_at=datetime.now(),
                query_count=0,
            )

            return self._connection

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Failed to connect to Snowflake after {elapsed:.1f}s: {e}")
            self._connection_info = ConnectionInfo(connected=False)
            raise SnowflakeConnectionError(f"Failed to connect to Snowflake: {e}") from e

    def close(self) -> None:
        """Close the Snowflake connection if open."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Snowflake connection closed")
            except Exception as e:
                logger.warning(f"Error closing Snowflake connection: {e}")
            finally:
                self._connection = None
                self._connection_info = ConnectionInfo(connected=False)

    def _get_current_user(self) -> str:
        """Get the current authenticated user."""
        if self._connection is None:
            return ""
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT CURRENT_USER()")
            result = cursor.fetchone()
            return result[0] if result else ""
        except Exception:
            return ""

    def _get_current_role(self) -> str:
        """Get the current active role."""
        if self._connection is None:
            return ""
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT CURRENT_ROLE()")
            result = cursor.fetchone()
            return result[0] if result else ""
        except Exception:
            return ""

    @contextmanager
    def get_connection(self) -> Generator[SnowflakeConnection, None, None]:
        """
        Context manager for connection handling.

        Creates a new connection if not already connected, yields the connection,
        and ensures proper cleanup on exit.

        Yields:
            Active SnowflakeConnection

        Example:
            connector = SnowflakeConnector()
            with connector.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        """
        if not self.is_connected:
            self.connect()

        assert self._connection is not None, "Connection should be established"
        try:
            yield self._connection
        finally:
            # Keep connection open for reuse
            pass

    @contextmanager
    def get_cursor(
        self,
        dict_cursor: bool = False
    ) -> Generator[SnowflakeCursor, None, None]:
        """
        Context manager that provides a cursor.

        Args:
            dict_cursor: If True, returns cursor that yields dict-like rows

        Yields:
            SnowflakeCursor for executing queries

        Example:
            connector = SnowflakeConnector()
            with connector.get_cursor() as cursor:
                cursor.execute("SELECT * FROM table LIMIT 10")
                for row in cursor:
                    print(row)
        """
        if not self.is_connected:
            self.connect()

        assert self._connection is not None, "Connection should be established"
        cursor: Any = None
        try:
            if dict_cursor:
                cursor = self._connection.cursor(snowflake.connector.DictCursor)  # type: ignore[union-attr]
            else:
                cursor = self._connection.cursor()
            yield cursor  # type: ignore[misc]
            self._connection_info.last_query_at = datetime.now()
            self._connection_info.query_count += 1
        finally:
            if cursor is not None:
                cursor.close()

    def execute(
        self,
        query: str,
        params: Optional[tuple] = None,
        timeout: Optional[int] = None
    ) -> list[tuple]:
        """
        Execute a query and return all results.

        Args:
            query: SQL query to execute
            params: Optional query parameters for parameterized queries
            timeout: Optional query timeout in seconds (overrides config)

        Returns:
            List of result rows as tuples

        Raises:
            SnowflakeConnectionError: If not connected
            Various snowflake errors for query issues
        """
        if not self.is_connected:
            self.connect()

        effective_timeout = timeout or self._config.timeouts.query_timeout

        with self.get_cursor() as cursor:
            logger.info(f"Executing query (timeout={effective_timeout}s)")
            logger.debug(f"Query: {query[:200]}...")

            if effective_timeout > 0:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {effective_timeout}")

            start_time = time.time()
            cursor.execute(query, params)
            results = cursor.fetchall()
            elapsed = time.time() - start_time

            logger.info(f"Query returned {len(results)} rows in {elapsed:.2f}s")
            return results

    def execute_dict(
        self,
        query: str,
        params: Optional[tuple] = None,
        timeout: Optional[int] = None
    ) -> list[dict]:
        """
        Execute a query and return results as list of dictionaries.

        Args:
            query: SQL query to execute
            params: Optional query parameters
            timeout: Optional query timeout in seconds

        Returns:
            List of result rows as dictionaries
        """
        if not self.is_connected:
            self.connect()

        effective_timeout = timeout or self._config.timeouts.query_timeout

        with self.get_cursor(dict_cursor=True) as cursor:
            logger.info(f"Executing query (timeout={effective_timeout}s)")
            logger.debug(f"Query: {query[:200]}...")

            if effective_timeout > 0:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {effective_timeout}")

            start_time = time.time()
            cursor.execute(query, params)
            results = cursor.fetchall()
            elapsed = time.time() - start_time

            logger.info(f"Query returned {len(results)} rows in {elapsed:.2f}s")
            return results  # type: ignore[return-value]

    def execute_chunked(
        self,
        query: str,
        params: Optional[tuple] = None,
        chunk_size: Optional[int] = None,
        timeout: Optional[int] = None,
        max_rows: Optional[int] = None,
    ) -> Generator[list[tuple], None, None]:
        """
        Execute a query and yield results in chunks for memory efficiency.

        This method is useful for large result sets that would exceed memory
        if loaded all at once. Results are yielded as chunks of rows.

        Args:
            query: SQL query to execute
            params: Optional query parameters for parameterized queries
            chunk_size: Number of rows per chunk (default from config)
            timeout: Optional query timeout in seconds (overrides config)
            max_rows: Maximum total rows to return (default from config, 0 for no limit)

        Yields:
            List of result rows as tuples for each chunk

        Example:
            for chunk in connector.execute_chunked("SELECT * FROM large_table"):
                process_chunk(chunk)
        """
        if not self.is_connected:
            self.connect()

        effective_timeout = timeout or self._config.timeouts.query_timeout
        effective_chunk_size = chunk_size or self._config.query.chunk_size
        effective_max_rows = max_rows if max_rows is not None else self._config.query.max_rows

        with self.get_cursor() as cursor:
            logger.info(f"Executing chunked query (chunk_size={effective_chunk_size}, timeout={effective_timeout}s)")
            logger.debug(f"Query: {query[:200]}...")

            if effective_timeout > 0:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {effective_timeout}")

            start_time = time.time()
            cursor.execute(query, params)

            total_rows = 0
            chunk_num = 0

            while True:
                # Determine how many rows to fetch this chunk
                if effective_max_rows > 0:
                    remaining = effective_max_rows - total_rows
                    if remaining <= 0:
                        break
                    fetch_size = min(effective_chunk_size, remaining)
                else:
                    fetch_size = effective_chunk_size

                chunk = cursor.fetchmany(fetch_size)
                if not chunk:
                    break

                chunk_num += 1
                total_rows += len(chunk)
                logger.debug(f"Chunk {chunk_num}: {len(chunk)} rows (total: {total_rows})")
                yield chunk

            elapsed = time.time() - start_time
            logger.info(f"Chunked query returned {total_rows} rows in {chunk_num} chunks ({elapsed:.2f}s)")

    def execute_chunked_dict(
        self,
        query: str,
        params: Optional[tuple] = None,
        chunk_size: Optional[int] = None,
        timeout: Optional[int] = None,
        max_rows: Optional[int] = None,
    ) -> Generator[list[dict], None, None]:
        """
        Execute a query and yield dict results in chunks for memory efficiency.

        Same as execute_chunked but returns rows as dictionaries.

        Args:
            query: SQL query to execute
            params: Optional query parameters
            chunk_size: Number of rows per chunk (default from config)
            timeout: Optional query timeout in seconds
            max_rows: Maximum total rows to return (default from config, 0 for no limit)

        Yields:
            List of result rows as dictionaries for each chunk
        """
        if not self.is_connected:
            self.connect()

        effective_timeout = timeout or self._config.timeouts.query_timeout
        effective_chunk_size = chunk_size or self._config.query.chunk_size
        effective_max_rows = max_rows if max_rows is not None else self._config.query.max_rows

        with self.get_cursor(dict_cursor=True) as cursor:
            logger.info(f"Executing chunked dict query (chunk_size={effective_chunk_size}, timeout={effective_timeout}s)")
            logger.debug(f"Query: {query[:200]}...")

            if effective_timeout > 0:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {effective_timeout}")

            start_time = time.time()
            cursor.execute(query, params)

            total_rows = 0
            chunk_num = 0

            while True:
                # Determine how many rows to fetch this chunk
                if effective_max_rows > 0:
                    remaining = effective_max_rows - total_rows
                    if remaining <= 0:
                        break
                    fetch_size = min(effective_chunk_size, remaining)
                else:
                    fetch_size = effective_chunk_size

                chunk = cursor.fetchmany(fetch_size)
                if not chunk:
                    break

                chunk_num += 1
                total_rows += len(chunk)
                logger.debug(f"Chunk {chunk_num}: {len(chunk)} rows (total: {total_rows})")
                yield chunk  # type: ignore[misc]

            elapsed = time.time() - start_time
            logger.info(f"Chunked dict query returned {total_rows} rows in {chunk_num} chunks ({elapsed:.2f}s)")

    def execute_with_row_limit(
        self,
        query: str,
        params: Optional[tuple] = None,
        max_rows: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> tuple[list[dict], bool]:
        """
        Execute a query with a row limit and indicate if more rows were available.

        This is useful for pagination or previewing large result sets.

        Args:
            query: SQL query to execute
            params: Optional query parameters
            max_rows: Maximum rows to return (default from config)
            timeout: Optional query timeout in seconds

        Returns:
            Tuple of (results list, has_more bool)
            - results: List of result rows as dictionaries (up to max_rows)
            - has_more: True if there were more rows than max_rows
        """
        if not self.is_connected:
            self.connect()

        effective_timeout = timeout or self._config.timeouts.query_timeout
        effective_max_rows = max_rows if max_rows is not None else self._config.query.max_rows

        with self.get_cursor(dict_cursor=True) as cursor:
            logger.info(f"Executing query with limit (max_rows={effective_max_rows}, timeout={effective_timeout}s)")
            logger.debug(f"Query: {query[:200]}...")

            if effective_timeout > 0:
                cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {effective_timeout}")

            start_time = time.time()
            cursor.execute(query, params)

            # Fetch one more than max to detect if there are more rows
            results = cursor.fetchmany(effective_max_rows + 1)
            elapsed = time.time() - start_time

            has_more = len(results) > effective_max_rows
            if has_more:
                results = results[:effective_max_rows]

            logger.info(f"Query returned {len(results)} rows (has_more={has_more}) in {elapsed:.2f}s")
            return results, has_more  # type: ignore[return-value]

    def fetch_activity_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        provider_codes: Optional[list[str]] = None,
        max_rows: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> list[dict]:
        """
        Fetch high-cost drug activity data from Snowflake.

        Queries the CDM.Acute__Conmon__PatientLevelDrugs table and returns
        data in a format compatible with the existing analysis pipeline.

        Args:
            start_date: Optional start date for filtering (inclusive)
            end_date: Optional end date for filtering (inclusive)
            provider_codes: Optional list of provider codes to filter by
            max_rows: Maximum rows to return (default from config)
            timeout: Query timeout in seconds (default from config)

        Returns:
            List of dictionaries with keys matching expected DataFrame columns:
            - PseudoNHSNoLinked: Pseudonymised NHS number (for UPID creation)
            - Provider Code: NHS provider code
            - PersonKey: Local patient identifier
            - Drug Name: Raw drug name
            - Intervention Date: Date of intervention
            - Price Actual: Cost of intervention
            - OrganisationName: Provider organisation name
            - Treatment Function Code: NHS treatment function code
            - Additional Detail 1-5: Additional details for directory identification

        Raises:
            SnowflakeConnectionError: If not connected or query fails
        """
        if not self.is_connected:
            self.connect()

        # Build the query
        table_name = 'DATA_HUB.CDM."Acute__Conmon__PatientLevelDrugs"'

        query = f'''
            SELECT
                "PseudoNHSNoLinked",
                "ProviderCode" AS "Provider Code",
                "LocalPatientID" AS "PersonKey",
                "DrugName" AS "Drug Name",
                "InterventionDate" AS "Intervention Date",
                "PriceActual" AS "Price Actual",
                "ProviderName" AS "OrganisationName",
                "TreatmentFunctionCode" AS "Treatment Function Code",
                "TreatmentFunctionDesc" AS "Treatment Function Desc",
                "AdditionalDetail1" AS "Additional Detail 1",
                "AdditionalDescription1" AS "Additional Description 1",
                "AdditionalDetail2" AS "Additional Detail 2",
                "AdditionalDescription2" AS "Additional Description 2",
                "AdditionalDetail3" AS "Additional Detail 3",
                "AdditionalDescription3" AS "Additional Description 3",
                "AdditionalDetail4" AS "Additional Detail 4",
                "AdditionalDescription4" AS "Additional Description 4",
                "AdditionalDetail5" AS "Additional Detail 5",
                "AdditionalDescription5" AS "Additional Description 5"
            FROM {table_name}
            WHERE 1=1
        '''

        params = []

        # Add date filters
        if start_date:
            query += ' AND "InterventionDate" >= %s'
            params.append(start_date.isoformat())
        if end_date:
            query += ' AND "InterventionDate" <= %s'
            params.append(end_date.isoformat())

        # Add provider filter
        if provider_codes:
            placeholders = ", ".join(["%s"] * len(provider_codes))
            query += f' AND "ProviderCode" IN ({placeholders})'
            params.extend(provider_codes)

        # Add ordering for consistent results
        query += ' ORDER BY "InterventionDate", "ProviderCode", "PseudoNHSNoLinked"'

        logger.info(f"Fetching activity data from Snowflake")
        if start_date:
            logger.info(f"  Date range: {start_date} to {end_date or 'now'}")
        if provider_codes:
            logger.info(f"  Providers: {provider_codes}")

        effective_max_rows = max_rows if max_rows is not None else self._config.query.max_rows
        effective_timeout = timeout or self._config.timeouts.query_timeout

        # Execute with chunked results for large datasets
        all_results = []
        total_rows = 0

        for chunk in self.execute_chunked_dict(
            query,
            params=tuple(params) if params else None,
            timeout=effective_timeout,
            max_rows=effective_max_rows,
        ):
            all_results.extend(chunk)
            total_rows += len(chunk)
            logger.debug(f"Fetched {total_rows} rows so far...")

        logger.info(f"Fetched {len(all_results)} activity records from Snowflake")
        return all_results

    def test_connection(self) -> tuple[bool, str]:
        """
        Test the Snowflake connection.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            self._check_availability()
        except SnowflakeNotAvailableError as e:
            return False, str(e)

        try:
            self._check_configured()
        except SnowflakeNotConfiguredError as e:
            return False, str(e)

        try:
            self.connect()
            user = self._get_current_user()
            role = self._get_current_role()
            return True, f"Connected as {user} with role {role}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def __enter__(self) -> "SnowflakeConnector":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# Module-level singleton for convenience
_default_connector: Optional[SnowflakeConnector] = None


def get_connector(config: Optional[SnowflakeConfig] = None) -> SnowflakeConnector:
    """
    Get a Snowflake connector (creates singleton on first call).

    Args:
        config: Optional configuration. If provided, creates new connector
                with this config. If None, uses/creates default connector.

    Returns:
        SnowflakeConnector instance
    """
    global _default_connector

    if config is not None:
        # Custom config requested, create new connector
        return SnowflakeConnector(config)

    if _default_connector is None:
        _default_connector = SnowflakeConnector()

    return _default_connector


def reset_connector() -> None:
    """Reset the default connector (closes connection and clears singleton)."""
    global _default_connector

    if _default_connector is not None:
        _default_connector.close()
        _default_connector = None


def is_snowflake_available() -> bool:
    """Return True if snowflake-connector-python is installed."""
    return SNOWFLAKE_AVAILABLE


def is_snowflake_configured() -> bool:
    """Return True if Snowflake account is configured."""
    try:
        config = get_snowflake_config()
        return config.is_configured
    except Exception:
        return False


# Export public API
__all__ = [
    "SnowflakeConnector",
    "SnowflakeConnectionError",
    "SnowflakeNotConfiguredError",
    "SnowflakeNotAvailableError",
    "ConnectionInfo",
    "get_connector",
    "reset_connector",
    "is_snowflake_available",
    "is_snowflake_configured",
    "SNOWFLAKE_AVAILABLE",
]
