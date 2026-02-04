"""
Patient data migration functions for NHS High-Cost Drug Patient Pathway Analysis Tool.

Provides functions to load patient intervention data from CSV/Parquet files
into the SQLite fact_interventions table. Supports:
- Batch processing for large files
- File hash tracking for incremental updates
- Progress reporting during loading
"""

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from core import PathConfig, default_paths
from core.logging_config import get_logger
from data_processing.database import DatabaseManager

logger = get_logger(__name__)


@dataclass
class PatientDataLoadResult:
    """Results from a patient data load operation."""
    file_path: str
    file_hash: str
    rows_read: int
    rows_inserted: int
    rows_skipped: int
    success: bool
    error_message: Optional[str] = None
    load_time_seconds: float = 0.0
    was_already_processed: bool = False

    def __str__(self) -> str:
        if self.was_already_processed:
            return f"{self.file_path}: Already processed (same hash)"
        elif self.success:
            return (
                f"{self.file_path}: Loaded {self.rows_inserted:,} rows "
                f"in {self.load_time_seconds:.1f}s"
            )
        else:
            return f"{self.file_path}: FAILED - {self.error_message}"


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of a file.

    Uses chunked reading to handle large files efficiently.

    Args:
        file_path: Path to the file.

    Returns:
        Hex string of SHA256 hash.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def check_file_processed(
    conn: sqlite3.Connection,
    file_path: str,
    file_hash: str
) -> tuple[bool, Optional[str]]:
    """
    Check if a file has already been processed with the same hash.

    Args:
        conn: Database connection.
        file_path: Full path to the file.
        file_hash: SHA256 hash of the file.

    Returns:
        Tuple of (is_processed, old_hash).
        - If is_processed is True and old_hash == file_hash, file is unchanged.
        - If is_processed is True and old_hash != file_hash, file has changed.
        - If is_processed is False, file is new.
    """
    cursor = conn.execute(
        "SELECT file_hash, status FROM processed_files WHERE file_path = ?",
        (file_path,)
    )
    result = cursor.fetchone()

    if result is None:
        return False, None

    old_hash = result["file_hash"]
    status = result["status"]

    # Only consider it processed if status is success and hash matches
    if status == "success" and old_hash == file_hash:
        return True, old_hash

    return False, old_hash


def record_file_processing_start(
    conn: sqlite3.Connection,
    file_path: str,
    file_hash: str,
    file_size: int,
    file_modified: datetime
) -> None:
    """
    Record that we're starting to process a file.

    Args:
        conn: Database connection.
        file_path: Full path to the file.
        file_hash: SHA256 hash of the file.
        file_size: File size in bytes.
        file_modified: File modification timestamp.
    """
    file_name = Path(file_path).name
    now = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO processed_files (
            file_path, file_name, file_hash, file_size_bytes,
            file_modified_at, status, first_processed_at, last_processed_at
        ) VALUES (?, ?, ?, ?, ?, 'processing', ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            file_hash = excluded.file_hash,
            file_size_bytes = excluded.file_size_bytes,
            file_modified_at = excluded.file_modified_at,
            status = 'processing',
            last_processed_at = excluded.last_processed_at,
            error_message = NULL
    """, (file_path, file_name, file_hash, file_size, file_modified.isoformat(), now, now))


def record_file_processing_complete(
    conn: sqlite3.Connection,
    file_path: str,
    row_count: int,
    duration_seconds: float,
    success: bool,
    error_message: Optional[str] = None
) -> None:
    """
    Record that file processing has completed.

    Args:
        conn: Database connection.
        file_path: Full path to the file.
        row_count: Number of rows processed.
        duration_seconds: Time taken to process.
        success: Whether processing was successful.
        error_message: Error message if failed.
    """
    status = "success" if success else "error"

    conn.execute("""
        UPDATE processed_files
        SET status = ?,
            row_count = ?,
            processing_duration_seconds = ?,
            error_message = ?,
            last_processed_at = ?
        WHERE file_path = ?
    """, (status, row_count, duration_seconds, error_message, datetime.now().isoformat(), file_path))


def load_dataframe_to_sqlite(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    source_file: str,
    batch_size: int = 5000,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> int:
    """
    Load a processed DataFrame into fact_interventions table.

    Args:
        df: Processed DataFrame with required columns (from FileDataLoader).
        conn: Database connection.
        source_file: Source file path for tracking.
        batch_size: Number of rows to insert per batch.
        progress_callback: Optional callback(rows_inserted, total_rows) for progress updates.

    Returns:
        Number of rows inserted.
    """
    # Store the original drug names before processing (for rows where mapping doesn't exist)
    # The drug_names() transformation sets Drug Name to NULL when no mapping exists.
    # We need to preserve the original for those cases.

    # Insert SQL columns - always include drug_name_raw
    insert_columns = [
        "upid", "provider_code", "person_key",
        "drug_name_raw", "drug_name_std",
        "intervention_date", "price_actual",
        "org_name", "directory",
        "treatment_function_code",
        "additional_detail_1", "additional_detail_2", "additional_detail_3",
        "additional_detail_4", "additional_detail_5",
        "source_file"
    ]
    placeholders = ",".join(["?"] * len(insert_columns))
    insert_sql = f"""
        INSERT INTO fact_interventions ({",".join(insert_columns)})
        VALUES ({placeholders})
    """

    rows_inserted = 0
    rows_skipped = 0
    total_rows = len(df)

    # Process in batches
    for batch_start in range(0, total_rows, batch_size):
        batch_end = min(batch_start + batch_size, total_rows)
        batch_df = df.iloc[batch_start:batch_end]

        # Prepare batch data
        batch_data = []
        for _, row in batch_df.iterrows():
            # Skip rows missing required fields
            if pd.isna(row.get("UPID")) or pd.isna(row.get("Intervention Date")):
                rows_skipped += 1
                continue
            # Get drug names - raw and standardized
            drug_name_raw = row.get("Drug Name Raw") if "Drug Name Raw" in df.columns else None
            drug_name_std = row.get("Drug Name")

            # If drug_name_std is NULL, use the raw drug name (uppercase)
            # This handles cases where the drug isn't in the drugnames.csv mapping
            if pd.isna(drug_name_std):
                if drug_name_raw is not None and not pd.isna(drug_name_raw):
                    drug_name_std = str(drug_name_raw).upper().strip()
                else:
                    drug_name_std = "UNKNOWN"

            # Also clean up raw drug name for storage
            if drug_name_raw is not None and not pd.isna(drug_name_raw):
                drug_name_raw = str(drug_name_raw).strip()

            # Get other values with null handling
            def get_value(col_name):
                if col_name not in df.columns:
                    return None
                val = row[col_name]
                if pd.isna(val):
                    return None
                elif hasattr(val, "strftime"):
                    return val.strftime("%Y-%m-%d")
                return val

            row_data = (
                get_value("UPID"),
                get_value("Provider Code"),
                get_value("PersonKey"),
                drug_name_raw,
                drug_name_std,
                get_value("Intervention Date"),
                get_value("Price Actual") or 0,
                get_value("OrganisationName"),
                get_value("Directory"),
                get_value("Treatment Function Code"),
                get_value("Additional Detail 1"),
                get_value("Additional Detail 2"),
                get_value("Additional Detail 3"),
                get_value("Additional Detail 4"),
                get_value("Additional Detail 5"),
                source_file
            )
            batch_data.append(row_data)

        # Execute batch insert
        conn.executemany(insert_sql, batch_data)
        rows_inserted += len(batch_data)

        # Report progress
        if progress_callback:
            progress_callback(rows_inserted, total_rows)

    if rows_skipped > 0:
        logger.info(f"Skipped {rows_skipped:,} rows with missing UPID or Intervention Date")

    return rows_inserted


def delete_file_data(conn: sqlite3.Connection, source_file: str) -> int:
    """
    Delete all data from a specific source file.

    Used when re-processing a changed file.

    Args:
        conn: Database connection.
        source_file: Source file path.

    Returns:
        Number of rows deleted.
    """
    cursor = conn.execute(
        "DELETE FROM fact_interventions WHERE source_file = ?",
        (source_file,)
    )
    return cursor.rowcount


def load_patient_data(
    file_path: Path | str,
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None,
    batch_size: int = 5000,
    force: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> PatientDataLoadResult:
    """
    Load patient data from CSV/Parquet file into fact_interventions table.

    This is the main entry point for loading patient data. It:
    1. Calculates file hash to detect changes
    2. Checks if file was already processed (skip if unchanged)
    3. Loads and transforms data using FileDataLoader
    4. Inserts data into SQLite in batches
    5. Records processing status in processed_files table

    Args:
        file_path: Path to CSV or Parquet file.
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig for reference data. Uses default if not provided.
        batch_size: Number of rows to insert per batch (default: 5000).
        force: If True, re-process even if file hash matches.
        progress_callback: Optional callback(rows_inserted, total_rows) for progress.

    Returns:
        PatientDataLoadResult with loading statistics.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    file_path = Path(file_path)
    file_path_str = str(file_path.absolute())

    logger.info(f"Starting patient data load from {file_path}")
    start_time = time.time()

    # Check file exists
    if not file_path.exists():
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return PatientDataLoadResult(
            file_path=file_path_str,
            file_hash="",
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )

    # Calculate file hash
    logger.info("Calculating file hash...")
    file_hash = calculate_file_hash(file_path)
    file_size = file_path.stat().st_size
    file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)

    logger.info(f"File hash: {file_hash[:16]}... Size: {file_size:,} bytes")

    # Check if already processed
    if not force:
        with db_manager.get_connection() as conn:
            is_processed, old_hash = check_file_processed(conn, file_path_str, file_hash)
            if is_processed:
                logger.info(f"File already processed with same hash, skipping")
                return PatientDataLoadResult(
                    file_path=file_path_str,
                    file_hash=file_hash,
                    rows_read=0,
                    rows_inserted=0,
                    rows_skipped=0,
                    success=True,
                    was_already_processed=True
                )
            elif old_hash is not None:
                logger.info(f"File hash changed, will re-process (old: {old_hash[:16]}...)")

    try:
        # Use FileDataLoader to load and transform data
        from data_processing.loader import FileDataLoader

        loader = FileDataLoader(file_path, paths)
        logger.info("Loading and transforming data...")
        result = loader.load()
        df = result.df
        rows_read = result.row_count

        logger.info(f"Loaded {rows_read:,} rows, starting SQLite insert...")

        # Load into SQLite
        with db_manager.get_transaction() as conn:
            # Record that we're starting
            record_file_processing_start(conn, file_path_str, file_hash, file_size, file_modified)

            # Delete any existing data from this file (for re-processing)
            deleted = delete_file_data(conn, file_path_str)
            if deleted > 0:
                logger.info(f"Deleted {deleted:,} existing rows from previous load")

            # Insert new data
            rows_inserted = load_dataframe_to_sqlite(
                df, conn, file_path_str, batch_size, progress_callback
            )

            # Record success
            load_time = time.time() - start_time
            record_file_processing_complete(
                conn, file_path_str, rows_inserted, load_time, True
            )

        logger.info(f"Successfully loaded {rows_inserted:,} rows in {load_time:.1f}s")

        return PatientDataLoadResult(
            file_path=file_path_str,
            file_hash=file_hash,
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_skipped=rows_read - rows_inserted,
            success=True,
            load_time_seconds=load_time
        )

    except Exception as e:
        load_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Failed to load patient data: {error_msg}")

        # Record failure
        try:
            with db_manager.get_connection() as conn:
                record_file_processing_complete(
                    conn, file_path_str, 0, load_time, False, error_msg
                )
        except Exception:
            pass  # Don't fail on failure to record failure

        return PatientDataLoadResult(
            file_path=file_path_str,
            file_hash=file_hash if 'file_hash' in dir() else "",
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg,
            load_time_seconds=load_time
        )


def get_patient_data_stats(db_manager: Optional[DatabaseManager] = None) -> dict:
    """
    Get statistics about patient data in fact_interventions.

    Returns:
        Dictionary with statistics about the loaded data.
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    stats = {}

    with db_manager.get_connection() as conn:
        # Total rows
        cursor = conn.execute("SELECT COUNT(*) FROM fact_interventions")
        stats["total_rows"] = cursor.fetchone()[0]

        # Unique patients
        cursor = conn.execute("SELECT COUNT(DISTINCT upid) FROM fact_interventions")
        stats["unique_patients"] = cursor.fetchone()[0]

        # Unique drugs
        cursor = conn.execute("SELECT COUNT(DISTINCT drug_name_std) FROM fact_interventions")
        stats["unique_drugs"] = cursor.fetchone()[0]

        # Unique organizations
        cursor = conn.execute("SELECT COUNT(DISTINCT org_name) FROM fact_interventions")
        stats["unique_organizations"] = cursor.fetchone()[0]

        # Date range
        cursor = conn.execute("""
            SELECT MIN(intervention_date), MAX(intervention_date)
            FROM fact_interventions
        """)
        result = cursor.fetchone()
        stats["date_range"] = (result[0], result[1]) if result else (None, None)

        # Processed files
        cursor = conn.execute("""
            SELECT COUNT(*), SUM(row_count)
            FROM processed_files WHERE status = 'success'
        """)
        result = cursor.fetchone()
        stats["processed_files"] = result[0] if result else 0
        stats["processed_rows"] = result[1] if result and result[1] else 0

    return stats


def list_processed_files(db_manager: Optional[DatabaseManager] = None) -> list[dict]:
    """
    List all processed files and their status.

    Returns:
        List of dictionaries with file processing information.
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    files = []

    with db_manager.get_connection() as conn:
        cursor = conn.execute("""
            SELECT file_path, file_name, file_hash, file_size_bytes,
                   row_count, status, error_message,
                   first_processed_at, last_processed_at, processing_duration_seconds
            FROM processed_files
            ORDER BY last_processed_at DESC
        """)

        for row in cursor.fetchall():
            files.append({
                "file_path": row["file_path"],
                "file_name": row["file_name"],
                "file_hash": row["file_hash"],
                "file_size_bytes": row["file_size_bytes"],
                "row_count": row["row_count"],
                "status": row["status"],
                "error_message": row["error_message"],
                "first_processed_at": row["first_processed_at"],
                "last_processed_at": row["last_processed_at"],
                "processing_duration_seconds": row["processing_duration_seconds"],
            })

    return files


# =============================================================================
# Materialized View Refresh Functions
# =============================================================================

@dataclass
class MVRefreshResult:
    """Results from refreshing the patient treatment summary materialized view."""
    patients_processed: int
    rows_inserted: int
    refresh_time_seconds: float
    success: bool
    error_message: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return (
                f"Refreshed MV: {self.patients_processed:,} patients "
                f"in {self.refresh_time_seconds:.1f}s"
            )
        else:
            return f"MV refresh FAILED: {self.error_message}"


def refresh_patient_treatment_summary(
    db_manager: Optional[DatabaseManager] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> MVRefreshResult:
    """
    Refresh the mv_patient_treatment_summary materialized view.

    This computes per-patient aggregations from fact_interventions:
    - First/last seen dates
    - Total cost, average cost per intervention
    - Intervention count, unique drug count
    - Drug sequence (chronological, pipe-separated)
    - Drug counts, costs, and date ranges (as JSON)

    The MV is fully rebuilt (truncate and re-insert) for simplicity.
    This typically takes 30-60 seconds for ~35,000 patients.

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        progress_callback: Optional callback(patients_done, total_patients).

    Returns:
        MVRefreshResult with refresh statistics.
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    logger.info("Starting materialized view refresh...")
    start_time = time.time()

    try:
        with db_manager.get_transaction() as conn:
            # Step 1: Get total patient count for progress reporting
            cursor = conn.execute("SELECT COUNT(DISTINCT upid) FROM fact_interventions")
            total_patients = cursor.fetchone()[0]
            logger.info(f"Processing {total_patients:,} unique patients")

            if total_patients == 0:
                logger.warning("No patient data in fact_interventions, MV will be empty")
                return MVRefreshResult(
                    patients_processed=0,
                    rows_inserted=0,
                    refresh_time_seconds=time.time() - start_time,
                    success=True
                )

            # Step 2: Clear existing MV data
            conn.execute("DELETE FROM mv_patient_treatment_summary")
            logger.info("Cleared existing MV data")

            # Step 3: Compute aggregations using SQL CTEs
            # This is more efficient than processing row-by-row in Python
            refresh_sql = """
            WITH patient_aggs AS (
                -- Basic aggregations per patient
                SELECT
                    upid,
                    MIN(org_name) as org_name,
                    MIN(directory) as directory,
                    MIN(intervention_date) as first_seen_date,
                    MAX(intervention_date) as last_seen_date,
                    JULIANDAY(MAX(intervention_date)) - JULIANDAY(MIN(intervention_date)) as days_treated,
                    SUM(price_actual) as total_cost,
                    AVG(price_actual) as avg_cost_per_intervention,
                    COUNT(*) as intervention_count,
                    COUNT(DISTINCT drug_name_std) as unique_drug_count,
                    COUNT(*) as source_row_count
                FROM fact_interventions
                GROUP BY upid
            ),
            drug_sequences AS (
                -- Drug sequence per patient (chronological order, pipe-separated)
                SELECT
                    upid,
                    GROUP_CONCAT(drug_name_std, '|') as drug_sequence
                FROM (
                    SELECT DISTINCT
                        upid,
                        drug_name_std,
                        MIN(intervention_date) as first_date
                    FROM fact_interventions
                    GROUP BY upid, drug_name_std
                    ORDER BY upid, first_date
                )
                GROUP BY upid
            ),
            drug_counts AS (
                -- JSON object of drug counts per patient
                SELECT
                    upid,
                    '{' || GROUP_CONCAT('"' || drug_name_std || '": ' || cnt, ', ') || '}' as drug_counts_json
                FROM (
                    SELECT
                        upid,
                        drug_name_std,
                        COUNT(*) as cnt
                    FROM fact_interventions
                    GROUP BY upid, drug_name_std
                )
                GROUP BY upid
            ),
            drug_costs AS (
                -- JSON object of drug costs per patient
                SELECT
                    upid,
                    '{' || GROUP_CONCAT('"' || drug_name_std || '": ' || ROUND(total_cost, 2), ', ') || '}' as drug_costs_json
                FROM (
                    SELECT
                        upid,
                        drug_name_std,
                        SUM(price_actual) as total_cost
                    FROM fact_interventions
                    GROUP BY upid, drug_name_std
                )
                GROUP BY upid
            ),
            drug_dates AS (
                -- JSON object of drug date ranges per patient
                SELECT
                    upid,
                    '{' || GROUP_CONCAT('"' || drug_name_std || '": {"first": "' || first_date || '", "last": "' || last_date || '"}', ', ') || '}' as drug_date_ranges_json
                FROM (
                    SELECT
                        upid,
                        drug_name_std,
                        MIN(intervention_date) as first_date,
                        MAX(intervention_date) as last_date
                    FROM fact_interventions
                    GROUP BY upid, drug_name_std
                )
                GROUP BY upid
            )
            INSERT INTO mv_patient_treatment_summary (
                upid, org_name, directory,
                first_seen_date, last_seen_date, days_treated,
                total_cost, avg_cost_per_intervention,
                intervention_count, unique_drug_count,
                drug_sequence, drug_counts_json, drug_costs_json, drug_date_ranges_json,
                source_row_count, computed_at
            )
            SELECT
                pa.upid,
                pa.org_name,
                pa.directory,
                pa.first_seen_date,
                pa.last_seen_date,
                CAST(pa.days_treated AS INTEGER),
                pa.total_cost,
                pa.avg_cost_per_intervention,
                pa.intervention_count,
                pa.unique_drug_count,
                ds.drug_sequence,
                dc.drug_counts_json,
                dco.drug_costs_json,
                dd.drug_date_ranges_json,
                pa.source_row_count,
                CURRENT_TIMESTAMP
            FROM patient_aggs pa
            LEFT JOIN drug_sequences ds ON pa.upid = ds.upid
            LEFT JOIN drug_counts dc ON pa.upid = dc.upid
            LEFT JOIN drug_costs dco ON pa.upid = dco.upid
            LEFT JOIN drug_dates dd ON pa.upid = dd.upid
            """

            logger.info("Executing MV refresh query...")
            conn.execute(refresh_sql)

            # Get actual rows inserted
            cursor = conn.execute("SELECT COUNT(*) FROM mv_patient_treatment_summary")
            rows_inserted = cursor.fetchone()[0]

            refresh_time = time.time() - start_time
            logger.info(f"MV refresh complete: {rows_inserted:,} rows in {refresh_time:.1f}s")

            # Report progress if callback provided
            if progress_callback:
                progress_callback(rows_inserted, total_patients)

            return MVRefreshResult(
                patients_processed=total_patients,
                rows_inserted=rows_inserted,
                refresh_time_seconds=refresh_time,
                success=True
            )

    except Exception as e:
        refresh_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"MV refresh failed: {error_msg}")
        return MVRefreshResult(
            patients_processed=0,
            rows_inserted=0,
            refresh_time_seconds=refresh_time,
            success=False,
            error_message=error_msg
        )


def get_patient_summary_stats(db_manager: Optional[DatabaseManager] = None) -> dict:
    """
    Get statistics about the patient treatment summary MV.

    Returns:
        Dictionary with MV statistics.
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    stats = {}

    with db_manager.get_connection() as conn:
        # Total rows
        cursor = conn.execute("SELECT COUNT(*) FROM mv_patient_treatment_summary")
        stats["total_patients"] = cursor.fetchone()[0]

        if stats["total_patients"] == 0:
            return stats

        # Aggregated statistics
        cursor = conn.execute("""
            SELECT
                SUM(total_cost) as total_cost_all,
                AVG(total_cost) as avg_cost_per_patient,
                SUM(intervention_count) as total_interventions,
                AVG(intervention_count) as avg_interventions_per_patient,
                AVG(unique_drug_count) as avg_drugs_per_patient,
                AVG(days_treated) as avg_days_treated,
                MIN(first_seen_date) as earliest_date,
                MAX(last_seen_date) as latest_date,
                MAX(computed_at) as last_refresh
            FROM mv_patient_treatment_summary
        """)
        result = cursor.fetchone()

        stats["total_cost"] = result[0] if result[0] else 0
        stats["avg_cost_per_patient"] = result[1] if result[1] else 0
        stats["total_interventions"] = result[2] if result[2] else 0
        stats["avg_interventions_per_patient"] = result[3] if result[3] else 0
        stats["avg_drugs_per_patient"] = result[4] if result[4] else 0
        stats["avg_days_treated"] = result[5] if result[5] else 0
        stats["date_range"] = (result[6], result[7])
        stats["last_refresh"] = result[8]

        # Unique directories in MV
        cursor = conn.execute("SELECT COUNT(DISTINCT directory) FROM mv_patient_treatment_summary")
        stats["unique_directories"] = cursor.fetchone()[0]

        # Unique organizations in MV
        cursor = conn.execute("SELECT COUNT(DISTINCT org_name) FROM mv_patient_treatment_summary")
        stats["unique_organizations"] = cursor.fetchone()[0]

    return stats


def verify_mv_consistency(db_manager: Optional[DatabaseManager] = None) -> tuple[bool, str]:
    """
    Verify that the MV is consistent with fact_interventions.

    Checks that:
    - Patient counts match
    - Total cost sums match
    - Intervention counts match

    Returns:
        Tuple of (is_consistent, message).
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    with db_manager.get_connection() as conn:
        # Get fact table counts
        cursor = conn.execute("""
            SELECT
                COUNT(DISTINCT upid) as patients,
                SUM(price_actual) as total_cost,
                COUNT(*) as interventions
            FROM fact_interventions
        """)
        fact_row = cursor.fetchone()
        fact_patients = fact_row[0] or 0
        fact_cost = fact_row[1] or 0
        fact_interventions = fact_row[2] or 0

        # Get MV counts
        cursor = conn.execute("""
            SELECT
                COUNT(*) as patients,
                SUM(total_cost) as total_cost,
                SUM(intervention_count) as interventions
            FROM mv_patient_treatment_summary
        """)
        mv_row = cursor.fetchone()
        mv_patients = mv_row[0] or 0
        mv_cost = mv_row[1] or 0
        mv_interventions = mv_row[2] or 0

        # Compare
        issues = []

        if fact_patients != mv_patients:
            issues.append(f"Patient count mismatch: fact={fact_patients:,}, mv={mv_patients:,}")

        if mv_interventions != fact_interventions:
            issues.append(f"Intervention count mismatch: fact={fact_interventions:,}, mv={mv_interventions:,}")

        # Allow small floating point differences in cost
        cost_diff = abs(fact_cost - mv_cost)
        if cost_diff > 0.01:
            issues.append(f"Cost mismatch: fact={fact_cost:,.2f}, mv={mv_cost:,.2f}, diff={cost_diff:.2f}")

        if issues:
            return False, "; ".join(issues)

        return True, f"MV consistent: {mv_patients:,} patients, {mv_interventions:,} interventions, £{mv_cost:,.2f} total"
