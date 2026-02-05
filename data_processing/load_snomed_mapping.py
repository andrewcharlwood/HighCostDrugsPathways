"""
Load enriched SNOMED mapping data into SQLite database.

This module loads the drug_snomed_mapping_enriched.csv file into the
ref_drug_snomed_mapping table for direct GP record matching.

Source file: data/drug_snomed_mapping_enriched.csv (163K rows)
Target table: ref_drug_snomed_mapping

Usage:
    python -m data_processing.load_snomed_mapping

Columns mapped:
    Drug -> drug_name
    Indication -> indication
    TA_ID -> ta_id
    Search_Term -> search_term
    SNOMEDCode -> snomed_code (cleaned: removes trailing .0)
    SNOMEDDescription -> snomed_description
    CleanedDrugName -> cleaned_drug_name
    PrimaryDirectorate -> primary_directorate
    AllDirectorates -> all_directorates
"""

from pathlib import Path
from typing import Optional

from core.logging_config import get_logger
from data_processing.database import DatabaseManager
from data_processing.reference_data import MigrationResult, _read_csv_with_fallback_encoding

logger = get_logger(__name__)

DEFAULT_CSV_PATH = Path("./data/drug_snomed_mapping_enriched.csv")


def clean_snomed_code(snomed_code: str) -> str:
    """
    Clean SNOMED code by removing trailing .0 suffix.

    The enriched CSV has SNOMED codes with decimal notation (e.g., "156370009.0")
    that need to be converted to clean integer strings.

    Args:
        snomed_code: Raw SNOMED code from CSV.

    Returns:
        Cleaned SNOMED code as string (e.g., "156370009").
    """
    if not snomed_code:
        return ""

    code = snomed_code.strip()

    # Remove trailing .0 if present
    if code.endswith(".0"):
        code = code[:-2]

    return code


def migrate_drug_snomed_mapping(
    db_manager: Optional[DatabaseManager] = None,
    csv_path: Optional[Path] = None
) -> MigrationResult:
    """
    Migrate drug SNOMED mappings from CSV to SQLite ref_drug_snomed_mapping table.

    Source file format (with header):
        Drug,Indication,TA_ID,Search_Term,SNOMEDCode,SNOMEDDescription,
        CleanedDrugName,PrimaryDirectorate,AllDirectorates

    Example rows:
        ABATACEPT,Psoriatic arthritis after DMARDs,TA568,psoriatic arthritis,
        156370009.0,Psoriatic arthritis,ABATACEPT,RHEUMATOLOGY,RHEUMATOLOGY|DERMATOLOGY

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        csv_path: Path to the CSV file. Defaults to data/drug_snomed_mapping_enriched.csv.

    Returns:
        MigrationResult with statistics about the migration.
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if csv_path is None:
        csv_path = DEFAULT_CSV_PATH

    table_name = "ref_drug_snomed_mapping"

    logger.info(f"Migrating drug SNOMED mappings from {csv_path} to {table_name}")

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
            rows = _read_csv_with_fallback_encoding(csv_path)

            for i, row in enumerate(rows):
                # Skip header row
                if i == 0 and len(row) >= 5 and row[0].strip().lower() == "drug":
                    logger.debug("Skipping header row")
                    continue

                rows_read += 1

                # Validate row format (need at least: Drug, Indication, TA_ID, Search_Term, SNOMEDCode)
                if len(row) < 5:
                    logger.warning(f"Skipping malformed row {rows_read}: {row}")
                    rows_skipped += 1
                    continue

                drug_name = row[0].strip()
                indication = row[1].strip()
                ta_id = row[2].strip() if len(row) > 2 else ""
                search_term = row[3].strip()
                snomed_code_raw = row[4].strip() if len(row) > 4 else ""
                snomed_description = row[5].strip() if len(row) > 5 else ""
                cleaned_drug_name = row[6].strip() if len(row) > 6 else drug_name.upper()
                primary_directorate = row[7].strip() if len(row) > 7 else ""
                all_directorates = row[8].strip() if len(row) > 8 else ""

                # Skip if required fields are empty
                if not drug_name or not indication or not search_term or not snomed_code_raw:
                    logger.warning(f"Skipping row {rows_read} with empty required fields")
                    rows_skipped += 1
                    continue

                # Clean SNOMED code (remove trailing .0)
                snomed_code = clean_snomed_code(snomed_code_raw)

                if not snomed_code:
                    logger.warning(f"Skipping row {rows_read} with invalid SNOMED code: {snomed_code_raw}")
                    rows_skipped += 1
                    continue

                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO ref_drug_snomed_mapping
                    (drug_name, indication, ta_id, search_term, snomed_code, snomed_description,
                     cleaned_drug_name, primary_directorate, all_directorates)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        drug_name,
                        indication,
                        ta_id,
                        search_term,
                        snomed_code,
                        snomed_description,
                        cleaned_drug_name,
                        primary_directorate,
                        all_directorates,
                    )
                )

                if cursor.rowcount > 0:
                    rows_inserted += 1
                else:
                    rows_skipped += 1

                # Log progress every 10000 rows
                if rows_read % 10000 == 0:
                    logger.info(f"Processed {rows_read} rows, inserted {rows_inserted}")

        logger.info(
            f"Drug SNOMED mapping migration complete: {rows_read} rows read, "
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


def get_drug_snomed_mapping_counts(db_manager: Optional[DatabaseManager] = None) -> dict:
    """
    Get statistics about the ref_drug_snomed_mapping table.

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.

    Returns:
        Dictionary with:
        - total_mappings: Total rows in table
        - unique_drugs: Count of distinct drug names
        - unique_search_terms: Count of distinct search terms
        - unique_snomed_codes: Count of distinct SNOMED codes
        - unique_indications: Count of distinct indications
    """
    if db_manager is None:
        db_manager = DatabaseManager()

    with db_manager.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM ref_drug_snomed_mapping")
        total = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(DISTINCT drug_name) FROM ref_drug_snomed_mapping")
        unique_drugs = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(DISTINCT search_term) FROM ref_drug_snomed_mapping")
        unique_search_terms = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(DISTINCT snomed_code) FROM ref_drug_snomed_mapping")
        unique_snomed_codes = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(DISTINCT indication) FROM ref_drug_snomed_mapping")
        unique_indications = cursor.fetchone()[0]

        return {
            "total_mappings": total,
            "unique_drugs": unique_drugs,
            "unique_search_terms": unique_search_terms,
            "unique_snomed_codes": unique_snomed_codes,
            "unique_indications": unique_indications,
        }


def verify_drug_snomed_mapping_migration(
    db_manager: Optional[DatabaseManager] = None,
    csv_path: Optional[Path] = None
) -> tuple[bool, str]:
    """
    Verify that drug SNOMED mappings were migrated correctly.

    Checks:
    - Row count is reasonable (163K+ expected)
    - Unique search terms is reasonable (187 expected)
    - Sample lookups return expected values

    Args:
        db_manager: DatabaseManager instance. Uses default if not provided.
        csv_path: Path to the CSV file. Defaults to data/drug_snomed_mapping_enriched.csv.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if db_manager is None:
        db_manager = DatabaseManager()
    if csv_path is None:
        csv_path = DEFAULT_CSV_PATH

    stats = get_drug_snomed_mapping_counts(db_manager)

    # Basic sanity checks
    if stats["total_mappings"] < 100000:
        return False, f"Too few rows: expected 163K+, got {stats['total_mappings']}"

    if stats["unique_search_terms"] < 100:
        return False, f"Too few search terms: expected ~187, got {stats['unique_search_terms']}"

    # Sample lookup verification
    with db_manager.get_connection() as conn:
        # Check that ABATACEPT exists (from sample data)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM ref_drug_snomed_mapping WHERE drug_name = 'ABATACEPT'"
        )
        abatacept_count = cursor.fetchone()[0]
        if abatacept_count == 0:
            return False, "Sample drug ABATACEPT not found in table"

        # Check that SNOMED codes were cleaned (no .0 suffix)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM ref_drug_snomed_mapping WHERE snomed_code LIKE '%.0'"
        )
        dirty_codes = cursor.fetchone()[0]
        if dirty_codes > 0:
            return False, f"Found {dirty_codes} SNOMED codes with uncleaned .0 suffix"

    return True, (
        f"Verified {stats['total_mappings']:,} mappings: "
        f"{stats['unique_drugs']} drugs, "
        f"{stats['unique_search_terms']} search terms, "
        f"{stats['unique_snomed_codes']:,} SNOMED codes"
    )


def main():
    """CLI entry point for loading SNOMED mapping data."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Load drug SNOMED mapping data into SQLite database"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to CSV file (default: {DEFAULT_CSV_PATH})"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing data, don't migrate"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    import logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if args.verify_only:
        print("Verifying existing data...")
        success, message = verify_drug_snomed_mapping_migration(csv_path=args.csv)
        if success:
            print(f"[OK] Verification passed: {message}")
        else:
            print(f"[FAILED] Verification failed: {message}")
        return 0 if success else 1

    # Run migration
    print(f"Loading SNOMED mapping from {args.csv}...")
    result = migrate_drug_snomed_mapping(csv_path=args.csv)

    if result.success:
        print(f"[OK] {result}")

        # Show statistics
        stats = get_drug_snomed_mapping_counts()
        print(f"\nTable statistics:")
        print(f"  Total mappings: {stats['total_mappings']:,}")
        print(f"  Unique drugs: {stats['unique_drugs']}")
        print(f"  Unique search terms: {stats['unique_search_terms']}")
        print(f"  Unique SNOMED codes: {stats['unique_snomed_codes']:,}")
        print(f"  Unique indications: {stats['unique_indications']}")

        # Verify
        success, message = verify_drug_snomed_mapping_migration(csv_path=args.csv)
        if success:
            print(f"\n[OK] Verification: {message}")
        else:
            print(f"\n[WARNING] Verification: {message}")
            return 1
    else:
        print(f"[FAILED] {result}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
