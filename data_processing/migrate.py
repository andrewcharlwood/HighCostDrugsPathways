"""
Database migration script for NHS High-Cost Drug Patient Pathway Analysis Tool.

Provides functions to initialize the SQLite database schema and CLI interface
for running migrations from the command line.

Usage:
    # Initialize database (creates all tables)
    python -m data_processing.migrate

    # Drop existing tables and reinitialize
    python -m data_processing.migrate --drop-existing

    # Show current database status
    python -m data_processing.migrate --status

    # Migrate all reference data from CSV files
    python -m data_processing.migrate --reference-data

    # Migrate reference data with verification
    python -m data_processing.migrate --reference-data --verify
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure src/ is on sys.path when run as `python -m data_processing.migrate`
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core.logging_config import setup_logging, get_logger
from data_processing.database import DatabaseManager, DatabaseConfig
from core import PathConfig, default_paths
from data_processing.schema import (
    create_all_tables,
    drop_all_tables,
    verify_all_tables_exist,
    get_all_table_counts,
    migrate_pathway_nodes_chart_type,
    migrate_refresh_log_source_row_count,
)
from data_processing.reference_data import (
    MigrationResult,
    migrate_drug_names,
    migrate_organizations,
    migrate_directories,
    migrate_drug_directory_map,
    migrate_drug_indication_clusters,
    verify_drug_names_migration,
    verify_organizations_migration,
    verify_directories_migration,
    verify_drug_directory_map_migration,
    verify_drug_indication_clusters_migration,
)

logger = get_logger(__name__)


def initialize_database(
    db_manager: Optional[DatabaseManager] = None,
    drop_existing: bool = False,
    confirm_drop: bool = True
) -> bool:
    """
    Initialize the database with all required tables.

    Creates all tables defined in the schema (reference tables and pathway
    tables). Uses IF NOT EXISTS so safe to run multiple times.

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        drop_existing: If True, drops all existing tables before creating.
        confirm_drop: If True and drop_existing=True, prompts for confirmation.
                      Set to False for non-interactive use.

    Returns:
        True if initialization succeeded, False otherwise.
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    logger.info(f"Initializing database at: {db_manager.db_path}")

    # Handle drop existing with confirmation
    if drop_existing:
        if confirm_drop:
            print(f"\nWARNING: This will delete ALL data from the database:")
            print(f"  {db_manager.db_path}\n")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() not in ("yes", "y"):
                print("Operation cancelled.")
                return False

        if db_manager.exists:
            logger.warning("Dropping existing tables...")
            with db_manager.get_connection() as conn:
                drop_all_tables(conn)
                conn.commit()
            logger.info("Existing tables dropped")
        else:
            logger.info("Database does not exist yet, nothing to drop")

    # Create all tables
    try:
        with db_manager.get_transaction() as conn:
            create_all_tables(conn)
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

    # Run migrations for schema changes
    try:
        with db_manager.get_connection() as conn:
            # Add chart_type column to pathway_nodes if it doesn't exist
            success, msg = migrate_pathway_nodes_chart_type(conn)
            if success:
                logger.info(f"pathway_nodes migration: {msg}")
            else:
                logger.error(f"pathway_nodes migration failed: {msg}")
                return False

            # Add source_row_count column to pathway_refresh_log if it doesn't exist
            success, msg = migrate_refresh_log_source_row_count(conn)
            if success:
                logger.info(f"pathway_refresh_log migration: {msg}")
            else:
                logger.error(f"pathway_refresh_log migration failed: {msg}")
                return False
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

    # Verify all tables were created
    with db_manager.get_connection() as conn:
        missing = verify_all_tables_exist(conn)

    if missing:
        logger.error(f"Table creation failed. Missing tables: {missing}")
        return False

    logger.info("All tables created successfully")
    return True


def migrate_all_reference_data(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None,
    verify: bool = False
) -> tuple[bool, list[MigrationResult]]:
    """
    Run all reference data migrations from CSV files to SQLite tables.

    Migrations are run in order:
    1. Drug names (drugnames.csv → ref_drug_names)
    2. Organizations (org_codes.csv → ref_organizations)
    3. Directories (directory_list.csv → ref_directories)
    4. Drug-directory mappings (drug_directory_list.csv → ref_drug_directory_map)

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV files. Uses default if not provided.
        verify: If True, runs verification after each migration.

    Returns:
        Tuple of (all_success: bool, results: list of MigrationResult)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    results: list[MigrationResult] = []
    all_success = True

    # Define migrations in order
    # Note: drug_indication_clusters uses a different signature (csv_path instead of paths)
    migrations = [
        ("Drug names", migrate_drug_names, verify_drug_names_migration if verify else None, True),
        ("Organizations", migrate_organizations, verify_organizations_migration if verify else None, True),
        ("Directories", migrate_directories, verify_directories_migration if verify else None, True),
        ("Drug-directory map", migrate_drug_directory_map, verify_drug_directory_map_migration if verify else None, True),
        ("Drug indication clusters", migrate_drug_indication_clusters, verify_drug_indication_clusters_migration if verify else None, False),
    ]

    logger.info(f"Starting reference data migrations ({len(migrations)} tables)")

    for name, migrate_fn, verify_fn, uses_paths in migrations:
        logger.info(f"Migrating: {name}...")

        # Run migration (some use paths parameter, some use csv_path)
        if uses_paths:
            result = migrate_fn(db_manager=db_manager, paths=paths)  # type: ignore[operator]
        else:
            # Drug indication clusters uses csv_path instead of paths
            result = migrate_fn(db_manager=db_manager)  # type: ignore[operator]
        results.append(result)

        if not result.success:
            logger.error(f"Migration failed: {name} - {result.error_message}")
            all_success = False
            continue

        logger.info(f"  {result}")

        # Run verification if requested
        if verify_fn is not None:
            logger.info(f"  Verifying {name}...")
            if uses_paths:
                verified, verify_msg = verify_fn(db_manager=db_manager, paths=paths)  # type: ignore[call-arg]
            else:
                verified, verify_msg = verify_fn(db_manager=db_manager)  # type: ignore[call-arg]
            if verified:
                logger.info(f"  OK: {verify_msg}")
            else:
                logger.error(f"  FAILED: Verification failed: {verify_msg}")
                all_success = False

    # Summary
    successful = sum(1 for r in results if r.success)
    logger.info(f"Reference data migrations complete: {successful}/{len(results)} succeeded")

    return all_success, results


def print_migration_summary(results: list[MigrationResult]) -> None:
    """Print a summary of migration results to stdout."""
    print("\n=== Reference Data Migration Summary ===\n")

    for result in results:
        status = "[OK]" if result.success else "[FAILED]"
        print(f"{status} {result.table_name}")
        if result.success:
            print(f"    Read: {result.rows_read}, Inserted: {result.rows_inserted}, Skipped: {result.rows_skipped}")
        else:
            print(f"    Error: {result.error_message}")

    successful = sum(1 for r in results if r.success)
    print(f"\nTotal: {successful}/{len(results)} migrations succeeded")
    print()


def create_progress_reporter(description: str = "Loading", width: int = 40):
    """
    Create a progress callback that prints a progress bar to stdout.

    Args:
        description: Label to show before the progress bar.
        width: Width of the progress bar in characters.

    Returns:
        Callback function(current, total) that prints progress.
    """
    last_percent = [-1]  # Use list to allow mutation in closure

    def report_progress(current: int, total: int) -> None:
        """Print a progress bar showing current/total progress."""
        if total == 0:
            percent = 100
        else:
            percent = int(100 * current / total)

        # Only update display when percentage changes (avoid excessive output)
        if percent == last_percent[0]:
            return
        last_percent[0] = percent

        filled = int(width * current / total) if total > 0 else width
        bar = "=" * filled + "-" * (width - filled)

        # Use carriage return to overwrite the line
        sys.stdout.write(f"\r{description}: [{bar}] {percent:3d}% ({current:,}/{total:,})")
        sys.stdout.flush()

        # Print newline when complete
        if current >= total:
            print()

    return report_progress


def get_database_status(db_manager: Optional[DatabaseManager] = None) -> dict:
    """
    Get the current status of the database.

    Returns:
        Dictionary with database status information:
        - exists: Whether the database file exists
        - path: Path to the database file
        - size_bytes: Size of database file (if exists)
        - tables: Dictionary of table names to row counts
        - missing_tables: List of expected tables that don't exist
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    status = {
        "exists": db_manager.exists,
        "path": str(db_manager.db_path),
        "size_bytes": None,
        "tables": {},
        "missing_tables": [],
    }

    if db_manager.exists:
        status["size_bytes"] = db_manager.db_path.stat().st_size

        with db_manager.get_connection() as conn:
            status["missing_tables"] = verify_all_tables_exist(conn)

            # Get counts for existing tables
            try:
                status["tables"] = get_all_table_counts(conn)
            except Exception as e:
                logger.warning(f"Could not get table counts: {e}")

    return status


def print_database_status(db_manager: Optional[DatabaseManager] = None) -> None:
    """Print database status to stdout in a human-readable format."""
    status = get_database_status(db_manager)

    print("\n=== Database Status ===\n")
    print(f"Path: {status['path']}")
    print(f"Exists: {status['exists']}")

    if status["exists"]:
        size_kb = (status["size_bytes"] or 0) / 1024
        print(f"Size: {size_kb:.1f} KB")

        if status["missing_tables"]:
            print(f"\nMissing tables: {', '.join(status['missing_tables'])}")
        else:
            print("\nAll expected tables exist.")

        if status["tables"]:
            print("\nTable row counts:")
            for table, count in sorted(status["tables"].items()):
                print(f"  {table}: {count:,} rows")
    else:
        print("\nDatabase does not exist. Run migration to create it.")

    print()


def main():
    """CLI entry point for database migration."""
    parser = argparse.ArgumentParser(
        description="Initialize NHS Pathways Analysis SQLite database schema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m data_processing.migrate              # Initialize database
  python -m data_processing.migrate --status     # Show database status
  python -m data_processing.migrate --drop-existing  # Reset database
  python -m data_processing.migrate --reference-data  # Migrate reference data
  python -m data_processing.migrate --reference-data --verify  # With verification
  python -m data_processing.migrate --db-path ./data/test.db  # Custom path
        """
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current database status and exit"
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop all existing tables before creating (WARNING: deletes data)"
    )
    parser.add_argument(
        "--reference-data",
        action="store_true",
        help="Migrate all reference data from CSV files to SQLite tables"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migrated data matches CSV sources (use with --reference-data)"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to database file (default: ./data/pathways.db)"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts (for non-interactive use)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    args = parser.parse_args()

    # Set up logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level, simple_console=True)

    # Create database manager with optional custom path
    if args.db_path:
        config = DatabaseConfig(db_path=args.db_path)
        db_manager = DatabaseManager(config)
    else:
        db_manager = DatabaseManager()

    # Handle --status
    if args.status:
        print_database_status(db_manager)
        return 0

    # Validate configuration
    config_errors = db_manager.config.validate()
    if config_errors:
        for error in config_errors:
            logger.error(error)
        return 1

    # Handle --reference-data (migrate reference data from CSV to SQLite)
    if args.reference_data:
        # Ensure database exists with tables first
        if not db_manager.exists:
            print("Database does not exist. Initializing schema first...")
            success = initialize_database(db_manager=db_manager)
            if not success:
                print("\nDatabase initialization failed. Check logs for details.")
                return 1

        # Run reference data migrations
        success, results = migrate_all_reference_data(
            db_manager=db_manager,
            paths=default_paths,
            verify=args.verify
        )

        print_migration_summary(results)
        print_database_status(db_manager)

        if success:
            print("Reference data migration completed successfully.")
            return 0
        else:
            print("Reference data migration completed with errors. Check logs for details.")
            return 1

    # Run schema migration (default behavior)
    success = initialize_database(
        db_manager=db_manager,
        drop_existing=args.drop_existing,
        confirm_drop=not args.yes
    )

    if success:
        print("\nDatabase initialized successfully.")
        print_database_status(db_manager)
        return 0
    else:
        print("\nDatabase initialization failed. Check logs for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
