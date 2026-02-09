"""
SQLite database connection management for NHS High-Cost Drug Patient Pathway Analysis Tool.

Provides connection management, schema initialization, and common database operations.
Uses context manager pattern for safe resource handling.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator, Literal

from core.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseConfig:
    """
    Configuration for SQLite database location and connection parameters.

    Attributes:
        db_path: Path to the SQLite database file
        timeout: Connection timeout in seconds (default: 30)
        isolation_level: Transaction isolation level (default: None for autocommit)
    """

    DEFAULT_DB_NAME = "pathways.db"

    def __init__(
        self,
        db_path: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        timeout: float = 30.0,
        isolation_level: Optional[Literal['DEFERRED', 'EXCLUSIVE', 'IMMEDIATE']] = None
    ):
        """
        Initialize database configuration.

        Args:
            db_path: Full path to database file. If None, uses data_dir/DEFAULT_DB_NAME.
            data_dir: Directory to place database in. Defaults to ./data/
            timeout: Connection timeout in seconds.
            isolation_level: Transaction isolation level. None = autocommit.
        """
        if db_path is not None:
            self.db_path = Path(db_path)
        elif data_dir is not None:
            self.db_path = Path(data_dir) / self.DEFAULT_DB_NAME
        else:
            self.db_path = Path("./data") / self.DEFAULT_DB_NAME

        self.timeout = timeout
        self.isolation_level = isolation_level

    def validate(self) -> list[str]:
        """
        Validate database configuration.

        Returns:
            List of error messages. Empty list means configuration is valid.
        """
        errors = []

        # Check parent directory exists
        parent_dir = self.db_path.parent
        if not parent_dir.exists():
            errors.append(f"Database directory does not exist: {parent_dir}")

        return errors


class DatabaseManager:
    """
    Manages SQLite database connections and operations.

    Provides context manager for safe connection handling and methods
    for common database operations.

    Usage:
        db_manager = DatabaseManager()

        # Using context manager (recommended)
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM ref_drug_names")
            results = cursor.fetchall()

        # Or get a managed connection for longer operations
        conn = db_manager.connect()
        try:
            # ... do work ...
        finally:
            conn.close()
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize the database manager.

        Args:
            config: Database configuration. If None, uses default configuration.
        """
        self.config = config or DatabaseConfig()
        self._connection: Optional[sqlite3.Connection] = None

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file."""
        return self.config.db_path

    @property
    def exists(self) -> bool:
        """Check if the database file exists."""
        return self.db_path.exists()

    def connect(self) -> sqlite3.Connection:
        """
        Create a new database connection.

        Returns:
            sqlite3.Connection: New database connection.

        Note:
            The caller is responsible for closing the connection.
            Consider using get_connection() context manager instead.
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.config.timeout,
            isolation_level=self.config.isolation_level
        )
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON")
        # Return rows as sqlite3.Row for dict-like access
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database connections.

        Yields:
            sqlite3.Connection: Database connection.

        Example:
            with db_manager.get_connection() as conn:
                conn.execute("INSERT INTO table VALUES (?)", (value,))
                conn.commit()
        """
        conn = self.connect()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def get_transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for transactional operations.

        Automatically commits on success, rolls back on exception.

        Yields:
            sqlite3.Connection: Database connection in transaction mode.

        Example:
            with db_manager.get_transaction() as conn:
                conn.execute("INSERT INTO table VALUES (?)", (value1,))
                conn.execute("INSERT INTO other_table VALUES (?)", (value2,))
                # Auto-commits if no exception
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.config.timeout,
            isolation_level="DEFERRED"  # Explicit transaction mode
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_script(self, sql_script: str) -> None:
        """
        Execute a SQL script (multiple statements).

        Args:
            sql_script: SQL script containing one or more statements.
        """
        with self.get_connection() as conn:
            conn.executescript(sql_script)
            logger.info("Executed SQL script successfully")

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of the table to check.

        Returns:
            True if the table exists, False otherwise.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return cursor.fetchone() is not None

    def get_table_count(self, table_name: str) -> int:
        """
        Get the row count for a table.

        Args:
            table_name: Name of the table.

        Returns:
            Number of rows in the table.
        """
        with self.get_connection() as conn:
            # Use parameterized table name via string formatting (safe since we control table_name)
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            result = cursor.fetchone()
            return result[0] if result else 0


# Default instance for application-wide use
default_db_config = DatabaseConfig()
default_db_manager = DatabaseManager(default_db_config)
