"""
Reference data migration functions for NHS High-Cost Drug Patient Pathway Analysis Tool.

Provides functions to migrate reference data from CSV files to SQLite tables:
- drugnames.csv → ref_drug_names
- org_codes.csv → ref_organizations
- directory_list.csv → ref_directories
- drug_directory_list.csv → ref_drug_directory_map

Each migration function:
- Reads source CSV file
- Validates data format
- Inserts into SQLite table (INSERT OR IGNORE for duplicates)
- Returns statistics about the migration
"""

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core import PathConfig, default_paths
from core.logging_config import get_logger
from data_processing.database import DatabaseManager

logger = get_logger(__name__)


def _read_csv_with_fallback_encoding(filepath: Path) -> list[list[str]]:
    """
    Read a CSV file with encoding fallback.

    Tries UTF-8 first, falls back to latin-1 for Windows files with special characters.

    Args:
        filepath: Path to the CSV file.

    Returns:
        List of rows (each row is a list of strings).
    """
    encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']

    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                return list(reader)
        except UnicodeDecodeError:
            continue

    # If all encodings fail, try latin-1 with errors='replace'
    with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
        reader = csv.reader(f)
        return list(reader)


@dataclass
class MigrationResult:
    """Results from a reference data migration."""
    table_name: str
    source_file: str
    rows_read: int
    rows_inserted: int
    rows_skipped: int
    success: bool
    error_message: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return (
                f"{self.table_name}: Read {self.rows_read} rows from {self.source_file}, "
                f"inserted {self.rows_inserted}, skipped {self.rows_skipped} duplicates"
            )
        else:
            return f"{self.table_name}: FAILED - {self.error_message}"


def migrate_drug_names(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> MigrationResult:
    """
    Migrate drug names from CSV to SQLite ref_drug_names table.

    Source file format (no header):
        raw_name,standard_name

    Example rows:
        ABATACEPT,ABATACEPT
        ABATACEPT  250MG POWDER FOR...,ABATACEPT

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        MigrationResult with statistics about the migration.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.drugnames_csv
    table_name = "ref_drug_names"

    logger.info(f"Migrating drug names from {source_file} to {table_name}")

    # Validate source file exists
    if not source_file.exists():
        error_msg = f"Source file not found: {source_file}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    try:
        with db_manager.get_transaction() as conn:
            # Read CSV (no header) with encoding fallback
            rows = _read_csv_with_fallback_encoding(source_file)

            for row in rows:
                    rows_read += 1

                    # Validate row format
                    if len(row) < 2:
                        logger.warning(f"Skipping malformed row {rows_read}: {row}")
                        rows_skipped += 1
                        continue

                    raw_name = row[0].strip()
                    standard_name = row[1].strip()

                    # Skip empty rows
                    if not raw_name or not standard_name:
                        logger.warning(f"Skipping row {rows_read} with empty values: {row}")
                        rows_skipped += 1
                        continue

                    # Insert with conflict handling (IGNORE duplicates)
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO ref_drug_names (raw_name, standard_name)
                        VALUES (?, ?)
                        """,
                        (raw_name, standard_name)
                    )

                    if cursor.rowcount > 0:
                        rows_inserted += 1
                    else:
                        rows_skipped += 1

        logger.info(
            f"Drug names migration complete: {rows_read} read, "
            f"{rows_inserted} inserted, {rows_skipped} skipped"
        )

        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_skipped=rows_skipped,
            success=True
        )

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )


def get_drug_name_counts(conn: sqlite3.Connection) -> dict:
    """
    Get statistics about the ref_drug_names table.

    Returns:
        Dictionary with:
        - total_mappings: Total rows in table
        - unique_standard_names: Count of distinct standard names
    """
    cursor = conn.execute("SELECT COUNT(*) FROM ref_drug_names")
    total = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT standard_name) FROM ref_drug_names")
    unique_standard = cursor.fetchone()[0]

    return {
        "total_mappings": total,
        "unique_standard_names": unique_standard
    }


def migrate_organizations(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> MigrationResult:
    """
    Migrate organization codes from CSV to SQLite ref_organizations table.

    Source file format (with header):
        Name,Code

    Example rows:
        MANCHESTER UNIVERSITY NHS FOUNDATION TRUST,R0A
        BARTS HEALTH NHS TRUST,R1H

    Note: The CSV has Name first, then Code. We store as org_code (unique), org_name.

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        MigrationResult with statistics about the migration.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.org_codes_csv
    table_name = "ref_organizations"

    logger.info(f"Migrating organizations from {source_file} to {table_name}")

    # Validate source file exists
    if not source_file.exists():
        error_msg = f"Source file not found: {source_file}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    try:
        with db_manager.get_transaction() as conn:
            # Read CSV with encoding fallback
            rows = _read_csv_with_fallback_encoding(source_file)

            for i, row in enumerate(rows):
                # Skip header row
                if i == 0 and len(row) >= 2 and row[0].strip().lower() == 'name':
                    logger.debug("Skipping header row")
                    continue

                rows_read += 1

                # Validate row format
                if len(row) < 2:
                    logger.warning(f"Skipping malformed row {rows_read}: {row}")
                    rows_skipped += 1
                    continue

                org_name = row[0].strip()
                org_code = row[1].strip()

                # Skip empty rows
                if not org_name or not org_code:
                    logger.warning(f"Skipping row {rows_read} with empty values: {row}")
                    rows_skipped += 1
                    continue

                # Insert with conflict handling (IGNORE duplicates on org_code)
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO ref_organizations (org_code, org_name)
                    VALUES (?, ?)
                    """,
                    (org_code, org_name)
                )

                if cursor.rowcount > 0:
                    rows_inserted += 1
                else:
                    rows_skipped += 1

        logger.info(
            f"Organizations migration complete: {rows_read} read, "
            f"{rows_inserted} inserted, {rows_skipped} skipped"
        )

        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_skipped=rows_skipped,
            success=True
        )

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )


def get_organization_counts(conn: sqlite3.Connection) -> dict:
    """
    Get statistics about the ref_organizations table.

    Returns:
        Dictionary with:
        - total_organizations: Total rows in table
    """
    cursor = conn.execute("SELECT COUNT(*) FROM ref_organizations")
    total = cursor.fetchone()[0]

    return {
        "total_organizations": total
    }


def verify_organizations_migration(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> tuple[bool, str]:
    """
    Verify that organizations were migrated correctly by comparing CSV to SQLite.

    Checks:
    - Row count matches (accounting for header and duplicates)
    - Sample lookups return expected values

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.org_codes_csv

    # Count rows in CSV using fallback encoding
    csv_unique_codes: set[str] = set()
    sample_mappings: list[tuple[str, str]] = []

    rows = _read_csv_with_fallback_encoding(source_file)
    for i, row in enumerate(rows):
        # Skip header
        if i == 0 and len(row) >= 2 and row[0].strip().lower() == 'name':
            continue
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            org_name = row[0].strip()
            org_code = row[1].strip()
            csv_unique_codes.add(org_code)
            if len(sample_mappings) < 5:  # Sample first 5 for verification
                sample_mappings.append((org_code, org_name))

    # Count rows in SQLite
    with db_manager.get_connection() as conn:
        stats = get_organization_counts(conn)

        # Check row count (should match unique org codes)
        if stats["total_organizations"] != len(csv_unique_codes):
            return False, (
                f"Row count mismatch: CSV has {len(csv_unique_codes)} unique org codes, "
                f"SQLite has {stats['total_organizations']} rows"
            )

        # Verify sample lookups
        for org_code, expected_name in sample_mappings:
            cursor = conn.execute(
                "SELECT org_name FROM ref_organizations WHERE org_code = ?",
                (org_code,)
            )
            result = cursor.fetchone()
            if result is None:
                return False, f"Missing organization for code: {org_code}"
            if result[0] != expected_name:
                return False, f"Wrong name for {org_code}: expected '{expected_name}', got '{result[0]}'"

    return True, f"Verified {stats['total_organizations']} organizations"


def verify_drug_names_migration(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> tuple[bool, str]:
    """
    Verify that drug names were migrated correctly by comparing CSV to SQLite.

    Checks:
    - Row count matches (accounting for duplicates)
    - Sample lookups return expected values

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.drugnames_csv

    # Count rows in CSV using fallback encoding
    csv_rows = 0
    csv_unique_raw = set()
    sample_mappings = []

    rows = _read_csv_with_fallback_encoding(source_file)
    for i, row in enumerate(rows):
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            csv_rows += 1
            raw = row[0].strip()
            std = row[1].strip()
            csv_unique_raw.add(raw)
            if i < 5:  # Sample first 5 for verification
                sample_mappings.append((raw, std))

    # Count rows in SQLite
    with db_manager.get_connection() as conn:
        stats = get_drug_name_counts(conn)

        # Check row count (should match unique raw names, not total rows)
        if stats["total_mappings"] != len(csv_unique_raw):
            return False, (
                f"Row count mismatch: CSV has {len(csv_unique_raw)} unique raw names, "
                f"SQLite has {stats['total_mappings']} rows"
            )

        # Verify sample lookups
        for raw, expected_std in sample_mappings:
            cursor = conn.execute(
                "SELECT standard_name FROM ref_drug_names WHERE raw_name = ?",
                (raw,)
            )
            result = cursor.fetchone()
            if result is None:
                return False, f"Missing mapping for: {raw}"
            if result[0] != expected_std:
                return False, f"Wrong mapping for {raw}: expected '{expected_std}', got '{result[0]}'"

    return True, f"Verified {stats['total_mappings']} drug name mappings"


def migrate_directories(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> MigrationResult:
    """
    Migrate medical directories from CSV to SQLite ref_directories table.

    Source file format (with header):
        directory

    Example rows:
        ONCOLOGY
        RHEUMATOLOGY
        NEPHROLOGY

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        MigrationResult with statistics about the migration.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.directory_list_csv
    table_name = "ref_directories"

    logger.info(f"Migrating directories from {source_file} to {table_name}")

    # Validate source file exists
    if not source_file.exists():
        error_msg = f"Source file not found: {source_file}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    try:
        with db_manager.get_transaction() as conn:
            # Read CSV with encoding fallback
            rows = _read_csv_with_fallback_encoding(source_file)

            for i, row in enumerate(rows):
                # Skip header row (check for 'directory' keyword)
                if i == 0 and len(row) >= 1 and row[0].strip().lower() == 'directory':
                    logger.debug("Skipping header row")
                    continue

                rows_read += 1

                # Validate row format (single column)
                if len(row) < 1:
                    logger.warning(f"Skipping empty row {rows_read}")
                    rows_skipped += 1
                    continue

                directory_name = row[0].strip()

                # Skip empty values
                if not directory_name:
                    logger.warning(f"Skipping row {rows_read} with empty directory name")
                    rows_skipped += 1
                    continue

                # Insert with conflict handling (IGNORE duplicates on directory_name)
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO ref_directories (directory_name)
                    VALUES (?)
                    """,
                    (directory_name,)
                )

                if cursor.rowcount > 0:
                    rows_inserted += 1
                else:
                    rows_skipped += 1

        logger.info(
            f"Directories migration complete: {rows_read} read, "
            f"{rows_inserted} inserted, {rows_skipped} skipped"
        )

        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_skipped=rows_skipped,
            success=True
        )

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )


def get_directory_counts(conn: sqlite3.Connection) -> dict:
    """
    Get statistics about the ref_directories table.

    Returns:
        Dictionary with:
        - total_directories: Total rows in table
    """
    cursor = conn.execute("SELECT COUNT(*) FROM ref_directories")
    total = cursor.fetchone()[0]

    return {
        "total_directories": total
    }


def verify_directories_migration(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> tuple[bool, str]:
    """
    Verify that directories were migrated correctly by comparing CSV to SQLite.

    Checks:
    - Row count matches (accounting for header and duplicates)
    - Sample lookups return expected values

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.directory_list_csv

    # Count unique directories in CSV using fallback encoding
    csv_unique_directories: set[str] = set()
    sample_directories: list[str] = []

    rows = _read_csv_with_fallback_encoding(source_file)
    for i, row in enumerate(rows):
        # Skip header
        if i == 0 and len(row) >= 1 and row[0].strip().lower() == 'directory':
            continue
        if len(row) >= 1 and row[0].strip():
            directory_name = row[0].strip()
            csv_unique_directories.add(directory_name)
            if len(sample_directories) < 5:  # Sample first 5 for verification
                sample_directories.append(directory_name)

    # Count rows in SQLite
    with db_manager.get_connection() as conn:
        stats = get_directory_counts(conn)

        # Check row count (should match unique directories)
        if stats["total_directories"] != len(csv_unique_directories):
            return False, (
                f"Row count mismatch: CSV has {len(csv_unique_directories)} unique directories, "
                f"SQLite has {stats['total_directories']} rows"
            )

        # Verify sample lookups
        for directory_name in sample_directories:
            cursor = conn.execute(
                "SELECT id FROM ref_directories WHERE directory_name = ?",
                (directory_name,)
            )
            result = cursor.fetchone()
            if result is None:
                return False, f"Missing directory: {directory_name}"

    return True, f"Verified {stats['total_directories']} directories"


def migrate_drug_directory_map(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> MigrationResult:
    """
    Migrate drug-to-directory mappings from CSV to SQLite ref_drug_directory_map table.

    Source file format (no header):
        DRUG_NAME,DIR1|DIR2|DIR3,

    The file has pipe-separated directories and often a trailing comma.
    Each drug-directory pair becomes a row. The is_single_valid flag is set to 1
    if the drug has exactly one valid directory (used for auto-assignment).

    Example input:
        ABATACEPT,RHEUMATOLOGY|PAEDIATRICS|CLINICAL IMMUNOLOGY,
        ROXADUSTAT,NEPHROLOGY

    Example output rows:
        ABATACEPT, RHEUMATOLOGY, is_single_valid=0
        ABATACEPT, PAEDIATRICS, is_single_valid=0
        ABATACEPT, CLINICAL IMMUNOLOGY, is_single_valid=0
        ROXADUSTAT, NEPHROLOGY, is_single_valid=1

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        MigrationResult with statistics about the migration.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.drug_directory_list_csv
    table_name = "ref_drug_directory_map"

    logger.info(f"Migrating drug-directory map from {source_file} to {table_name}")

    # Validate source file exists
    if not source_file.exists():
        error_msg = f"Source file not found: {source_file}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    try:
        # First pass: Parse CSV and build drug->directories mapping
        drug_directories: dict[str, list[str]] = {}

        csv_rows = _read_csv_with_fallback_encoding(source_file)

        for row in csv_rows:
            rows_read += 1

            # Validate row format (at least drug name and directories)
            if len(row) < 2:
                logger.warning(f"Skipping malformed row {rows_read}: {row}")
                rows_skipped += 1
                continue

            drug_name = row[0].strip().upper()  # Normalize to uppercase

            # Skip empty drug names
            if not drug_name:
                logger.warning(f"Skipping row {rows_read} with empty drug name")
                rows_skipped += 1
                continue

            # Get directories (pipe-separated)
            directories_raw = row[1].strip()

            # Skip "NOT A DRUG" entries
            if directories_raw.upper() == "NOT A DRUG":
                logger.debug(f"Skipping non-drug entry: {drug_name}")
                rows_skipped += 1
                continue

            # Skip empty directories
            if not directories_raw:
                logger.warning(f"Skipping row {rows_read} with empty directories: {drug_name}")
                rows_skipped += 1
                continue

            # Parse pipe-separated directories
            directories = [d.strip().upper() for d in directories_raw.split('|')]
            directories = [d for d in directories if d]  # Remove empty strings

            if not directories:
                logger.warning(f"Skipping row {rows_read} with no valid directories: {drug_name}")
                rows_skipped += 1
                continue

            # Store mapping (accumulate for same drug if it appears multiple times)
            if drug_name in drug_directories:
                # Merge directories, avoiding duplicates
                existing = set(drug_directories[drug_name])
                for d in directories:
                    if d not in existing:
                        drug_directories[drug_name].append(d)
            else:
                drug_directories[drug_name] = directories

        logger.info(f"Parsed {len(drug_directories)} unique drugs from CSV")

        # Second pass: Insert into database with is_single_valid flag
        with db_manager.get_transaction() as conn:
            for drug_name, directories in drug_directories.items():
                is_single_valid = 1 if len(directories) == 1 else 0

                for directory in directories:
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO ref_drug_directory_map
                        (drug_name, directory_name, is_single_valid)
                        VALUES (?, ?, ?)
                        """,
                        (drug_name, directory, is_single_valid)
                    )

                    if cursor.rowcount > 0:
                        rows_inserted += 1

        logger.info(
            f"Drug-directory map migration complete: {rows_read} CSV rows read, "
            f"{len(drug_directories)} unique drugs, {rows_inserted} mappings inserted, "
            f"{rows_skipped} rows skipped"
        )

        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_skipped=rows_skipped,
            success=True
        )

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(source_file),
            rows_read=rows_read,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )


def get_drug_directory_map_counts(conn: sqlite3.Connection) -> dict:
    """
    Get statistics about the ref_drug_directory_map table.

    Returns:
        Dictionary with:
        - total_mappings: Total rows in table
        - unique_drugs: Count of distinct drug names
        - unique_directories: Count of distinct directory names
        - single_valid_drugs: Count of drugs with is_single_valid=1
    """
    cursor = conn.execute("SELECT COUNT(*) FROM ref_drug_directory_map")
    total = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT drug_name) FROM ref_drug_directory_map")
    unique_drugs = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT directory_name) FROM ref_drug_directory_map")
    unique_directories = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT COUNT(DISTINCT drug_name) FROM ref_drug_directory_map WHERE is_single_valid = 1"
    )
    single_valid = cursor.fetchone()[0]

    return {
        "total_mappings": total,
        "unique_drugs": unique_drugs,
        "unique_directories": unique_directories,
        "single_valid_drugs": single_valid
    }


def verify_drug_directory_map_migration(
    db_manager: Optional[DatabaseManager] = None,
    paths: Optional[PathConfig] = None
) -> tuple[bool, str]:
    """
    Verify that drug-directory mappings were migrated correctly.

    Checks:
    - All drugs from CSV are present in SQLite
    - is_single_valid flag is set correctly for sample drugs
    - Directory counts per drug are correct

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        paths: PathConfig instance for locating CSV file. Uses default if not provided.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if paths is None:
        paths = default_paths

    source_file = paths.drug_directory_list_csv

    # Parse CSV to get expected data
    expected_drugs: dict[str, list[str]] = {}

    csv_rows = _read_csv_with_fallback_encoding(source_file)
    for row in csv_rows:
        if len(row) < 2:
            continue
        drug_name = row[0].strip().upper()
        directories_raw = row[1].strip()
        if not drug_name or not directories_raw or directories_raw.upper() == "NOT A DRUG":
            continue
        directories = [d.strip().upper() for d in directories_raw.split('|')]
        directories = [d for d in directories if d]
        if directories:
            if drug_name in expected_drugs:
                existing = set(expected_drugs[drug_name])
                for d in directories:
                    if d not in existing:
                        expected_drugs[drug_name].append(d)
            else:
                expected_drugs[drug_name] = directories

    # Verify against SQLite
    with db_manager.get_connection() as conn:
        stats = get_drug_directory_map_counts(conn)

        # Check drug count
        if stats["unique_drugs"] != len(expected_drugs):
            return False, (
                f"Drug count mismatch: CSV has {len(expected_drugs)} unique drugs, "
                f"SQLite has {stats['unique_drugs']}"
            )

        # Verify sample drugs
        sample_drugs = list(expected_drugs.keys())[:10]
        for drug_name in sample_drugs:
            expected_dirs = expected_drugs[drug_name]
            expected_single_valid = 1 if len(expected_dirs) == 1 else 0

            # Check directories
            cursor = conn.execute(
                "SELECT directory_name, is_single_valid FROM ref_drug_directory_map WHERE drug_name = ?",
                (drug_name,)
            )
            actual_rows = cursor.fetchall()

            if len(actual_rows) != len(expected_dirs):
                return False, (
                    f"Directory count mismatch for {drug_name}: "
                    f"expected {len(expected_dirs)}, got {len(actual_rows)}"
                )

            # Check is_single_valid flag
            for row in actual_rows:
                if row['is_single_valid'] != expected_single_valid:
                    return False, (
                        f"is_single_valid mismatch for {drug_name}: "
                        f"expected {expected_single_valid}, got {row['is_single_valid']}"
                    )

    return True, (
        f"Verified {stats['unique_drugs']} drugs with {stats['total_mappings']} mappings "
        f"({stats['single_valid_drugs']} single-valid)"
    )


def migrate_drug_indication_clusters(
    db_manager: Optional[DatabaseManager] = None,
    csv_path: Optional[Path] = None
) -> MigrationResult:
    """
    Migrate drug indication clusters from CSV to SQLite ref_drug_indication_clusters table.

    Source file format (with header):
        Drug,Indication,Cluster_ID,Cluster_Description,NICE_TA_Reference

    Example rows:
        ADALIMUMAB,Rheumatoid arthritis,RARTH_COD,Rheumatoid arthritis diagnosis codes,TA130/TA195/TA375
        ADALIMUMAB,Psoriasis,PSORIASIS_COD,Psoriasis codes,TA146/TA455

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        csv_path: Path to the CSV file. Defaults to data/drug_indication_clusters.csv.

    Returns:
        MigrationResult with statistics about the migration.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if csv_path is None:
        csv_path = Path("./data/drug_indication_clusters.csv")

    table_name = "ref_drug_indication_clusters"

    logger.info(f"Migrating drug indication clusters from {csv_path} to {table_name}")

    # Validate source file exists
    if not csv_path.exists():
        error_msg = f"Source file not found: {csv_path}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(csv_path),
            rows_read=0,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )

    rows_read = 0
    rows_inserted = 0
    rows_skipped = 0

    try:
        with db_manager.get_transaction() as conn:
            # Read CSV with encoding fallback
            rows = _read_csv_with_fallback_encoding(csv_path)

            for i, row in enumerate(rows):
                # Skip header row
                if i == 0 and len(row) >= 3 and row[0].strip().lower() == 'drug':
                    logger.debug("Skipping header row")
                    continue

                rows_read += 1

                # Validate row format (need at least drug, indication, cluster_id)
                if len(row) < 3:
                    logger.warning(f"Skipping malformed row {rows_read}: {row}")
                    rows_skipped += 1
                    continue

                drug_name = row[0].strip().upper()
                indication = row[1].strip()
                cluster_id = row[2].strip().upper()
                cluster_description = row[3].strip() if len(row) > 3 else ""
                nice_ta_reference = row[4].strip() if len(row) > 4 else ""

                # Skip empty required fields
                if not drug_name or not indication or not cluster_id:
                    logger.warning(f"Skipping row {rows_read} with empty required fields")
                    rows_skipped += 1
                    continue

                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO ref_drug_indication_clusters
                    (drug_name, indication, cluster_id, cluster_description, nice_ta_reference)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (drug_name, indication, cluster_id, cluster_description, nice_ta_reference)
                )

                if cursor.rowcount > 0:
                    rows_inserted += 1
                else:
                    rows_skipped += 1
                    logger.debug(f"Duplicate row skipped: {drug_name}, {indication}, {cluster_id}")

        logger.info(
            f"Drug indication clusters migration complete: {rows_read} rows read, "
            f"{rows_inserted} inserted, {rows_skipped} skipped"
        )

        return MigrationResult(
            table_name=table_name,
            source_file=str(csv_path),
            rows_read=rows_read,
            rows_inserted=rows_inserted,
            rows_skipped=rows_skipped,
            success=True
        )

    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg)
        return MigrationResult(
            table_name=table_name,
            source_file=str(csv_path),
            rows_read=rows_read,
            rows_inserted=0,
            rows_skipped=0,
            success=False,
            error_message=error_msg
        )


def get_drug_indication_cluster_counts(conn: sqlite3.Connection) -> dict:
    """
    Get statistics about the ref_drug_indication_clusters table.

    Returns:
        Dictionary with:
        - total_mappings: Total rows in table
        - unique_drugs: Count of distinct drug names
        - unique_indications: Count of distinct indications
        - unique_clusters: Count of distinct cluster IDs
    """
    cursor = conn.execute("SELECT COUNT(*) FROM ref_drug_indication_clusters")
    total = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT drug_name) FROM ref_drug_indication_clusters")
    unique_drugs = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT indication) FROM ref_drug_indication_clusters")
    unique_indications = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT cluster_id) FROM ref_drug_indication_clusters")
    unique_clusters = cursor.fetchone()[0]

    return {
        "total_mappings": total,
        "unique_drugs": unique_drugs,
        "unique_indications": unique_indications,
        "unique_clusters": unique_clusters
    }


def verify_drug_indication_clusters_migration(
    db_manager: Optional[DatabaseManager] = None,
    csv_path: Optional[Path] = None
) -> tuple[bool, str]:
    """
    Verify that drug indication clusters were migrated correctly.

    Checks:
    - Row count matches CSV (accounting for header and duplicates)
    - Sample lookups return expected values

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        csv_path: Path to the CSV file. Defaults to data/drug_indication_clusters.csv.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if csv_path is None:
        csv_path = Path("./data/drug_indication_clusters.csv")

    # Parse CSV to get expected data
    csv_rows = _read_csv_with_fallback_encoding(csv_path)
    expected_mappings: set[tuple[str, str, str]] = set()
    sample_rows: list[tuple[str, str, str]] = []

    for i, row in enumerate(csv_rows):
        # Skip header
        if i == 0 and len(row) >= 3 and row[0].strip().lower() == 'drug':
            continue
        if len(row) >= 3 and row[0].strip() and row[1].strip() and row[2].strip():
            drug = row[0].strip().upper()
            indication = row[1].strip()
            cluster = row[2].strip().upper()
            expected_mappings.add((drug, indication, cluster))
            if len(sample_rows) < 5:
                sample_rows.append((drug, indication, cluster))

    # Verify against SQLite
    with db_manager.get_connection() as conn:
        stats = get_drug_indication_cluster_counts(conn)

        # Check row count
        if stats["total_mappings"] != len(expected_mappings):
            return False, (
                f"Row count mismatch: CSV has {len(expected_mappings)} unique mappings, "
                f"SQLite has {stats['total_mappings']} rows"
            )

        # Verify sample lookups
        for drug, indication, cluster in sample_rows:
            cursor = conn.execute(
                """
                SELECT cluster_id FROM ref_drug_indication_clusters
                WHERE drug_name = ? AND indication = ? AND cluster_id = ?
                """,
                (drug, indication, cluster)
            )
            if cursor.fetchone() is None:
                return False, f"Missing mapping: {drug} / {indication} / {cluster}"

    return True, (
        f"Verified {stats['total_mappings']} mappings for {stats['unique_drugs']} drugs "
        f"across {stats['unique_clusters']} clusters"
    )
