"""
CLI command for refreshing pathway data from Snowflake.

This command fetches activity data from Snowflake, processes it through the
pathway pipeline for all 6 date filter combinations, and stores the results
in the SQLite pathway_nodes table. Supports two chart types:
- "directory": Trust → Directory → Drug → Pathway (default)
- "indication": Trust → Search_Term → Drug → Pathway (requires GP diagnosis lookup)

Usage:
    python -m cli.refresh_pathways
    python -m cli.refresh_pathways --minimum-patients 10
    python -m cli.refresh_pathways --provider-codes RGT,RM1
    python -m cli.refresh_pathways --chart-type all
    python -m cli.refresh_pathways --chart-type directory
    python -m cli.refresh_pathways --dry-run

Run `python -m cli.refresh_pathways --help` for full options.
"""

import argparse
import json
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure src/ is on sys.path when run as `python -m cli.refresh_pathways`
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core import PathConfig, default_paths
from core.logging_config import get_logger, setup_logging
from data_processing.database import DatabaseManager, DatabaseConfig
from data_processing.schema import (
    clear_pathway_nodes,
    get_pathway_table_counts,
    verify_pathway_tables_exist,
    create_pathway_tables,
)
from data_processing.pathway_pipeline import (
    ChartType,
    DATE_FILTER_CONFIGS,
    fetch_and_transform_data,
    process_all_date_filters,
    process_pathway_for_date_filter,
    process_indication_pathway_for_date_filter,
    extract_denormalized_fields,
    extract_indication_fields,
    convert_to_records,
)
from data_processing.diagnosis_lookup import (
    assign_drug_indications,
    get_patient_indication_groups,
    load_drug_indication_mapping,
)

logger = get_logger(__name__)


def get_default_filters(paths: PathConfig) -> tuple[list[str], list[str], list[str]]:
    """
    Load default filter values from reference files.

    Returns:
        Tuple of (trust_filter, drug_filter, directory_filter)
    """
    import pandas as pd

    # Load default trusts
    trust_filter = []
    if paths.default_trusts_csv.exists():
        try:
            trusts_df = pd.read_csv(paths.default_trusts_csv)
            # Use the "Name" column which contains trust names
            if 'Name' in trusts_df.columns:
                trust_filter = trusts_df['Name'].dropna().tolist()
            else:
                # Fallback to first column if no Name column
                trust_filter = trusts_df.iloc[:, 0].dropna().tolist()
            logger.info(f"Loaded {len(trust_filter)} default trusts")
        except Exception as e:
            logger.warning(f"Could not load default trusts: {e}")

    # Load default drugs (Include=1 in include.csv)
    drug_filter = []
    if paths.include_csv.exists():
        try:
            drugs_df = pd.read_csv(paths.include_csv)
            if 'Include' in drugs_df.columns:
                drug_filter = drugs_df[drugs_df['Include'] == 1].iloc[:, 0].dropna().tolist()
            else:
                # Assume first column contains drug names if no Include column
                drug_filter = drugs_df.iloc[:, 0].dropna().tolist()
            logger.info(f"Loaded {len(drug_filter)} default drugs")
        except Exception as e:
            logger.warning(f"Could not load default drugs: {e}")

    # Load default directories
    directory_filter = []
    if paths.directory_list_csv.exists():
        try:
            dirs_df = pd.read_csv(paths.directory_list_csv)
            # Assume first column contains directory names
            directory_filter = dirs_df.iloc[:, 0].dropna().tolist()
            logger.info(f"Loaded {len(directory_filter)} default directories")
        except Exception as e:
            logger.warning(f"Could not load default directories: {e}")

    return trust_filter, drug_filter, directory_filter


def insert_pathway_records(
    conn: sqlite3.Connection,
    records: list[dict],
) -> int:
    """
    Insert pathway records into pathway_nodes table.

    Uses INSERT OR REPLACE to handle updates to existing records.

    Args:
        conn: SQLite connection
        records: List of record dicts from convert_to_records()

    Returns:
        Number of records inserted
    """
    if not records:
        return 0

    # Column order matching pathway_nodes schema (includes chart_type)
    columns = [
        'date_filter_id', 'chart_type', 'parents', 'ids', 'labels', 'level',
        'value', 'cost', 'costpp', 'cost_pp_pa', 'colour',
        'first_seen', 'last_seen', 'first_seen_parent', 'last_seen_parent',
        'average_spacing', 'average_administered', 'avg_days',
        'trust_name', 'directory', 'drug_sequence', 'data_refresh_id'
    ]

    placeholders = ', '.join(['?' for _ in columns])
    column_names = ', '.join(columns)

    insert_sql = f"""
        INSERT OR REPLACE INTO pathway_nodes ({column_names})
        VALUES ({placeholders})
    """

    # Convert records to tuples in column order
    rows = []
    for record in records:
        row = tuple(record.get(col) for col in columns)
        rows.append(row)

    cursor = conn.executemany(insert_sql, rows)
    return cursor.rowcount


def log_refresh_start(
    conn: sqlite3.Connection,
    refresh_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> None:
    """Log the start of a refresh operation."""
    conn.execute("""
        INSERT INTO pathway_refresh_log
        (refresh_id, started_at, status, snowflake_query_date_from, snowflake_query_date_to)
        VALUES (?, ?, 'running', ?, ?)
    """, (refresh_id, datetime.now().isoformat(), date_from, date_to))
    conn.commit()


def log_refresh_complete(
    conn: sqlite3.Connection,
    refresh_id: str,
    record_count: int,
    date_filter_counts: dict[str, int],
    duration_seconds: float,
    source_row_count: Optional[int] = None,
) -> None:
    """Log the successful completion of a refresh operation."""
    conn.execute("""
        UPDATE pathway_refresh_log
        SET completed_at = ?,
            status = 'completed',
            record_count = ?,
            date_filter_counts = ?,
            processing_duration_seconds = ?,
            source_row_count = ?
        WHERE refresh_id = ?
    """, (
        datetime.now().isoformat(),
        record_count,
        json.dumps(date_filter_counts),
        duration_seconds,
        source_row_count,
        refresh_id,
    ))
    conn.commit()


def log_refresh_failed(
    conn: sqlite3.Connection,
    refresh_id: str,
    error_message: str,
    duration_seconds: float,
) -> None:
    """Log a failed refresh operation."""
    conn.execute("""
        UPDATE pathway_refresh_log
        SET completed_at = ?,
            status = 'failed',
            error_message = ?,
            processing_duration_seconds = ?
        WHERE refresh_id = ?
    """, (
        datetime.now().isoformat(),
        error_message,
        duration_seconds,
        refresh_id,
    ))
    conn.commit()


def refresh_pathways(
    minimum_patients: int = 5,
    provider_codes: Optional[list[str]] = None,
    trust_filter: Optional[list[str]] = None,
    drug_filter: Optional[list[str]] = None,
    directory_filter: Optional[list[str]] = None,
    db_path: Optional[Path] = None,
    paths: Optional[PathConfig] = None,
    dry_run: bool = False,
    chart_type: str = "directory",
) -> tuple[bool, str, dict]:
    """
    Main refresh function that orchestrates the full pipeline.

    Args:
        minimum_patients: Minimum patients to include a pathway
        provider_codes: List of provider codes to filter Snowflake query
        trust_filter: List of trust names to include in pathways
        drug_filter: List of drug names to include in pathways
        directory_filter: List of directories to include in pathways
        db_path: Path to SQLite database (uses default if None)
        paths: PathConfig for file paths
        dry_run: If True, don't actually insert records
        chart_type: Which chart type to process: "directory", "indication", or "all"

    Returns:
        Tuple of (success: bool, message: str, stats: dict)
    """
    if paths is None:
        paths = default_paths

    # Set up database connection
    if db_path:
        db_config = DatabaseConfig(db_path=db_path)
    else:
        db_config = DatabaseConfig(data_dir=paths.data_dir)

    db_manager = DatabaseManager(db_config)

    # Load default filters if not provided
    default_trusts, default_drugs, default_dirs = get_default_filters(paths)

    if trust_filter is None:
        trust_filter = default_trusts
    if drug_filter is None:
        drug_filter = default_drugs
    if directory_filter is None:
        directory_filter = default_dirs

    # Ensure we have some filters
    if not drug_filter:
        return False, "No drugs specified and could not load defaults", {}

    # Determine which chart types to process
    if chart_type == "all":
        chart_types_to_process: list[ChartType] = ["directory", "indication"]
    else:
        chart_types_to_process = [chart_type]  # type: ignore

    logger.info("=" * 60)
    logger.info("Pathway Data Refresh Starting")
    logger.info("=" * 60)
    logger.info(f"Minimum patients: {minimum_patients}")
    logger.info(f"Trust filter: {len(trust_filter)} trusts")
    logger.info(f"Drug filter: {len(drug_filter)} drugs")
    logger.info(f"Directory filter: {len(directory_filter)} directories")
    logger.info(f"Provider codes: {provider_codes or 'All'}")
    logger.info(f"Chart type(s): {', '.join(chart_types_to_process)}")
    logger.info(f"Database: {db_manager.db_path}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("=" * 60)

    start_time = time.time()
    refresh_id = str(uuid.uuid4())[:8]
    stats = {
        "refresh_id": refresh_id,
        "date_filter_counts": {},
        "total_records": 0,
        "snowflake_rows": 0,
    }

    try:
        # Verify database and tables
        with db_manager.get_connection() as conn:
            missing_tables = verify_pathway_tables_exist(conn)
            if missing_tables:
                logger.info(f"Creating missing tables: {missing_tables}")
                create_pathway_tables(conn)

            # Log refresh start
            if not dry_run:
                log_refresh_start(conn, refresh_id)

        # Step 1: Fetch data from Snowflake
        logger.info("")
        logger.info("Step 1/4: Fetching data from Snowflake...")
        df = fetch_and_transform_data(
            provider_codes=provider_codes,
            paths=paths,
        )

        if df.empty:
            msg = "No data returned from Snowflake"
            logger.error(msg)
            with db_manager.get_connection() as conn:
                log_refresh_failed(conn, refresh_id, msg, time.time() - start_time)
            return False, msg, stats

        stats["snowflake_rows"] = len(df)
        logger.info(f"Fetched {len(df)} records from Snowflake")

        # Step 2: Process all date filters for each chart type
        num_date_filters = len(DATE_FILTER_CONFIGS)
        num_chart_types = len(chart_types_to_process)
        total_datasets = num_date_filters * num_chart_types

        logger.info("")
        logger.info(f"Step 2/4: Processing pathway data for {total_datasets} datasets "
                   f"({num_date_filters} date filters x {num_chart_types} chart types)...")

        # Store results keyed by "date_filter_id:chart_type"
        results: dict[str, list[dict]] = {}

        for current_chart_type in chart_types_to_process:
            logger.info("")
            logger.info(f"Processing chart type: {current_chart_type}")

            if current_chart_type == "directory":
                # Use existing process_all_date_filters for directory charts
                dir_results = process_all_date_filters(
                    df=df,
                    trust_filter=trust_filter,
                    drug_filter=drug_filter,
                    directory_filter=directory_filter,
                    minimum_patients=minimum_patients,
                    refresh_id=refresh_id,
                    paths=paths,
                )
                # Add results with chart_type suffix
                for filter_id, records in dir_results.items():
                    # Records already have chart_type set by convert_to_records
                    results[f"{filter_id}:directory"] = records

            elif current_chart_type == "indication":
                # For indication charts, use drug-aware matching:
                # 1. Get ALL GP diagnosis matches per patient (with code_frequency)
                # 2. Cross-reference with drug-to-Search_Term mapping from DimSearchTerm.csv
                # 3. Assign each drug to its matched indication via modified UPIDs
                logger.info("Building drug-aware indication groups...")

                # Check Snowflake availability
                from data_processing.snowflake_connector import get_connector, is_snowflake_available

                if not is_snowflake_available():
                    logger.warning("Snowflake not available - cannot process indication charts")
                    for config in DATE_FILTER_CONFIGS:
                        results[f"{config.id}:indication"] = []
                    continue

                try:
                    import pandas as pd
                    connector = get_connector()

                    if 'PseudoNHSNoLinked' not in df.columns:
                        logger.error("DataFrame missing 'PseudoNHSNoLinked' column - cannot lookup GP records")
                        for config in DATE_FILTER_CONFIGS:
                            results[f"{config.id}:indication"] = []
                        continue

                    # Step 1: Load drug-to-Search_Term mapping from DimSearchTerm.csv
                    _, search_term_to_fragments = load_drug_indication_mapping()
                    logger.info(f"Loaded drug mapping: {len(search_term_to_fragments)} Search_Terms")

                    # Step 2: Get ALL GP diagnosis matches per patient (with code_frequency)
                    patient_pseudonyms = df['PseudoNHSNoLinked'].dropna().unique().tolist()
                    logger.info(f"Looking up GP diagnoses for {len(patient_pseudonyms)} unique patients...")

                    # Restrict GP codes to HCD data window (reduces noise from old diagnoses)
                    earliest_hcd_date = df['Intervention Date'].min()
                    if pd.notna(earliest_hcd_date):
                        earliest_hcd_date_str = pd.Timestamp(earliest_hcd_date).strftime('%Y-%m-%d')
                        logger.info(f"Restricting GP codes to HCD window: >= {earliest_hcd_date_str}")
                    else:
                        earliest_hcd_date_str = None

                    gp_matches_df = get_patient_indication_groups(
                        patient_pseudonyms=patient_pseudonyms,
                        connector=connector,
                        batch_size=5000,
                        earliest_hcd_date=earliest_hcd_date_str,
                    )

                    # Step 3: Assign drug-aware indications using cross-referencing
                    # This replaces the old per-patient approach with per-drug matching
                    modified_df, indication_df = assign_drug_indications(
                        df=df,
                        gp_matches_df=gp_matches_df,
                        search_term_to_fragments=search_term_to_fragments,
                    )

                    logger.info(f"Drug-aware indication matching complete. "
                               f"Modified UPIDs: {modified_df['UPID'].nunique()}, "
                               f"Indication groups: {len(indication_df)}")

                    if indication_df.empty:
                        logger.warning("Empty indication_df - skipping indication charts")
                        for config in DATE_FILTER_CONFIGS:
                            results[f"{config.id}:indication"] = []
                    else:
                        # Process each date filter with drug-aware indication grouping
                        # Use modified_df (with indication-aware UPIDs) instead of original df
                        for config in DATE_FILTER_CONFIGS:
                            logger.info(f"Processing indication pathway for {config.id}")

                            ice_df = process_indication_pathway_for_date_filter(
                                df=modified_df,
                                indication_df=indication_df,
                                config=config,
                                trust_filter=trust_filter,
                                drug_filter=drug_filter,
                                directory_filter=directory_filter,
                                minimum_patients=minimum_patients,
                                paths=paths,
                            )

                            if ice_df is None:
                                logger.warning(f"No indication pathway data for {config.id}")
                                results[f"{config.id}:indication"] = []
                                continue

                            # Extract denormalized fields (using indication variant)
                            ice_df = extract_indication_fields(ice_df)

                            # Convert to records with chart_type="indication"
                            records = convert_to_records(ice_df, config.id, refresh_id, chart_type="indication")
                            results[f"{config.id}:indication"] = records

                            logger.info(f"Completed {config.id}:indication: {len(records)} nodes")

                except Exception as e:
                    logger.error(f"Error processing indication charts: {e}")
                    logger.exception(e)
                    for config in DATE_FILTER_CONFIGS:
                        results[f"{config.id}:indication"] = []

        # Count records per filter and chart type
        stats["chart_type_counts"] = {}
        for key, records in results.items():
            stats["date_filter_counts"][key] = len(records)
            stats["total_records"] += len(records)
            # Also track by chart type
            _, ct = key.split(":")
            stats["chart_type_counts"][ct] = stats["chart_type_counts"].get(ct, 0) + len(records)

        logger.info("")
        logger.info(f"Processed {stats['total_records']} total pathway nodes")
        for chart_type_name, count in stats.get("chart_type_counts", {}).items():
            logger.info(f"  {chart_type_name}: {count} nodes total")
        for key, count in sorted(stats["date_filter_counts"].items()):
            if count > 0:
                logger.info(f"    {key}: {count} nodes")

        if dry_run:
            logger.info("")
            logger.info("DRY RUN - Skipping database insertion")
            elapsed = time.time() - start_time
            return True, f"Dry run complete: {stats['total_records']} records would be inserted", stats

        # Step 3: Clear existing data and insert new records
        logger.info("")
        logger.info("Step 3/4: Clearing existing pathway data and inserting new records...")

        with db_manager.get_transaction() as conn:
            # Clear all existing pathway nodes
            deleted = clear_pathway_nodes(conn)
            logger.info(f"Cleared {deleted} existing pathway nodes")

            # Insert new records for each date filter + chart type combination
            total_inserted = 0
            for key, records in results.items():
                if records:
                    inserted = insert_pathway_records(conn, records)
                    total_inserted += len(records)
                    logger.info(f"  Inserted {len(records)} records for {key}")

        # Step 4: Log completion
        logger.info("")
        logger.info("Step 4/4: Logging refresh completion...")

        elapsed = time.time() - start_time

        with db_manager.get_connection() as conn:
            log_refresh_complete(
                conn=conn,
                refresh_id=refresh_id,
                record_count=stats["total_records"],
                date_filter_counts=stats["date_filter_counts"],
                duration_seconds=elapsed,
                source_row_count=stats.get("snowflake_rows"),
            )

            # Verify final counts
            counts = get_pathway_table_counts(conn)
            logger.info(f"Final table counts: {counts}")

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"Refresh completed successfully in {elapsed:.1f} seconds")
        logger.info(f"Total records: {stats['total_records']}")
        logger.info(f"Refresh ID: {refresh_id}")
        logger.info("=" * 60)

        return True, f"Refresh complete: {stats['total_records']} records in {elapsed:.1f}s", stats

    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"Refresh failed: {e}"
        logger.error(error_msg, exc_info=True)

        try:
            with db_manager.get_connection() as conn:
                log_refresh_failed(conn, refresh_id, str(e), elapsed)
        except Exception:
            pass  # Don't fail the error handling

        return False, error_msg, stats


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Refresh pathway data from Snowflake",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic refresh with defaults (directory chart only)
    python -m cli.refresh_pathways

    # Refresh both chart types (directory and indication)
    python -m cli.refresh_pathways --chart-type all

    # Refresh only indication-based charts
    python -m cli.refresh_pathways --chart-type indication

    # Refresh with custom minimum patients
    python -m cli.refresh_pathways --minimum-patients 10

    # Refresh specific providers only
    python -m cli.refresh_pathways --provider-codes RGT,RM1

    # Dry run to see what would be processed
    python -m cli.refresh_pathways --dry-run

    # Verbose output
    python -m cli.refresh_pathways --verbose
        """
    )

    parser.add_argument(
        "--minimum-patients",
        type=int,
        default=5,
        help="Minimum patients to include a pathway (default: 5)"
    )

    parser.add_argument(
        "--provider-codes",
        type=str,
        default=None,
        help="Comma-separated list of provider codes to filter (default: all)"
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to SQLite database (default: data/pathways.db)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process data but don't insert into database"
    )

    parser.add_argument(
        "--chart-type",
        type=str,
        choices=["directory", "indication", "all"],
        default="directory",
        help="Chart type to process: 'directory' (default), 'indication', or 'all'"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    import logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)

    # Parse provider codes
    provider_codes = None
    if args.provider_codes:
        provider_codes = [code.strip() for code in args.provider_codes.split(",")]

    # Parse db path
    db_path = Path(args.db_path) if args.db_path else None

    # Run the refresh
    success, message, stats = refresh_pathways(
        minimum_patients=args.minimum_patients,
        provider_codes=provider_codes,
        db_path=db_path,
        dry_run=args.dry_run,
        chart_type=args.chart_type,
    )

    if success:
        print(f"\n[OK] {message}")
        return 0
    else:
        print(f"\n[FAILED] {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
