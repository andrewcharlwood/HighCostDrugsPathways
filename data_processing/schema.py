"""
SQLite schema definitions for NHS High-Cost Drug Patient Pathway Analysis Tool.

Contains SQL strings for creating reference tables, fact tables, and indexes.
Schema design supports:
- Reference data from CSV files (drug names, organizations, directories)
- Drug-directory mappings with single-valid-directory flag
- Patient intervention facts with proper indexing
- Cached aggregations for performance
- File tracking for incremental updates
"""

from typing import Optional
import sqlite3

from core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Reference Table Schemas
# =============================================================================

REF_DRUG_NAMES_SCHEMA = """
-- Mapping from raw drug names (as they appear in source data) to standardized names
-- Source: data/drugnames.csv
CREATE TABLE IF NOT EXISTS ref_drug_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL UNIQUE,
    standard_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups during data transformation
CREATE INDEX IF NOT EXISTS idx_ref_drug_names_raw ON ref_drug_names(raw_name);
CREATE INDEX IF NOT EXISTS idx_ref_drug_names_standard ON ref_drug_names(standard_name);
"""

REF_ORGANIZATIONS_SCHEMA = """
-- NHS organization codes and names
-- Source: data/org_codes.csv
CREATE TABLE IF NOT EXISTS ref_organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_code TEXT NOT NULL UNIQUE,
    org_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by organization code
CREATE INDEX IF NOT EXISTS idx_ref_organizations_code ON ref_organizations(org_code);
"""

REF_DIRECTORIES_SCHEMA = """
-- Medical directories/specialties
-- Source: data/directory_list.csv
CREATE TABLE IF NOT EXISTS ref_directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    directory_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by directory name
CREATE INDEX IF NOT EXISTS idx_ref_directories_name ON ref_directories(directory_name);
"""

REF_DRUG_DIRECTORY_MAP_SCHEMA = """
-- Mapping from drug names to valid directories
-- Source: data/drug_directory_list.csv
-- A drug may map to multiple directories (one row per drug-directory pair)
-- The is_single_valid flag indicates drugs with exactly ONE valid directory,
-- which enables automatic directory assignment in department_identification()
CREATE TABLE IF NOT EXISTS ref_drug_directory_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL,
    directory_name TEXT NOT NULL,
    is_single_valid BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(drug_name, directory_name)
);

-- Index for looking up directories by drug name (most common access pattern)
CREATE INDEX IF NOT EXISTS idx_ref_drug_directory_map_drug ON ref_drug_directory_map(drug_name);

-- Index for reverse lookup (find drugs by directory)
CREATE INDEX IF NOT EXISTS idx_ref_drug_directory_map_directory ON ref_drug_directory_map(directory_name);

-- Index for quick filtering of single-valid drugs
CREATE INDEX IF NOT EXISTS idx_ref_drug_directory_map_single ON ref_drug_directory_map(is_single_valid);
"""

REF_DRUG_INDICATION_CLUSTERS_SCHEMA = """
-- Mapping from drugs to SNOMED clusters for indication validation
-- Source: data/drug_indication_clusters.csv
-- Used to validate that patients have appropriate GP diagnoses for their prescribed drugs
-- A drug may map to multiple clusters (one row per drug-indication-cluster combination)
CREATE TABLE IF NOT EXISTS ref_drug_indication_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL,
    indication TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    cluster_description TEXT,
    nice_ta_reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(drug_name, indication, cluster_id)
);

-- Index for looking up clusters by drug name (most common access pattern)
CREATE INDEX IF NOT EXISTS idx_ref_drug_indication_clusters_drug ON ref_drug_indication_clusters(drug_name);

-- Index for looking up drugs by cluster (for finding all drugs treating a condition)
CREATE INDEX IF NOT EXISTS idx_ref_drug_indication_clusters_cluster ON ref_drug_indication_clusters(cluster_id);

-- Index for looking up by indication text
CREATE INDEX IF NOT EXISTS idx_ref_drug_indication_clusters_indication ON ref_drug_indication_clusters(indication);
"""


# =============================================================================
# Fact Table Schemas
# =============================================================================

FACT_INTERVENTIONS_SCHEMA = """
-- Patient intervention records (fact table)
-- Source: HCD activity data (CSV/Parquet files or Snowflake)
-- This is the main fact table storing all patient intervention events
CREATE TABLE IF NOT EXISTS fact_interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Patient identification
    upid TEXT NOT NULL,                     -- Unique Patient ID (Provider Code[:3] + PersonKey)
    provider_code TEXT NOT NULL,            -- Original provider code (3-5 chars)
    person_key TEXT NOT NULL,               -- Patient key from source system

    -- Intervention details
    drug_name_raw TEXT,                     -- Original drug name from source
    drug_name_std TEXT NOT NULL,            -- Standardized drug name (via ref_drug_names)
    intervention_date DATE NOT NULL,        -- Date of intervention
    price_actual REAL NOT NULL DEFAULT 0,   -- Cost of intervention in GBP

    -- Organization and directory
    org_name TEXT,                          -- Organization name (cleaned, no commas)
    directory TEXT,                         -- Medical directory/specialty (may be "Undefined")

    -- Source tracking
    source_file TEXT,                       -- Original file this record came from
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Additional clinical fields (optional, used in directory fallback logic)
    treatment_function_code INTEGER,
    additional_detail_1 TEXT,
    additional_detail_2 TEXT,
    additional_detail_3 TEXT,
    additional_detail_4 TEXT,
    additional_detail_5 TEXT
);

-- Primary indexes for common filter patterns used in generate_graph()
-- UPID: Used for patient grouping, pathway analysis
CREATE INDEX IF NOT EXISTS idx_fact_interventions_upid ON fact_interventions(upid);

-- Drug name (standardized): Used for drug filtering
CREATE INDEX IF NOT EXISTS idx_fact_interventions_drug ON fact_interventions(drug_name_std);

-- Intervention date: Used for date range filtering (start_date, end_date, last_seen)
CREATE INDEX IF NOT EXISTS idx_fact_interventions_date ON fact_interventions(intervention_date);

-- Directory: Used for directory/specialty filtering
CREATE INDEX IF NOT EXISTS idx_fact_interventions_directory ON fact_interventions(directory);

-- Organization: Used for trust filtering (Provider Code maps to org_name)
CREATE INDEX IF NOT EXISTS idx_fact_interventions_org ON fact_interventions(org_name);

-- Composite index for common filter combination (trust + drug + directory)
CREATE INDEX IF NOT EXISTS idx_fact_interventions_composite
    ON fact_interventions(org_name, drug_name_std, directory);

-- Composite index for date-based patient analysis
CREATE INDEX IF NOT EXISTS idx_fact_interventions_upid_date
    ON fact_interventions(upid, intervention_date);
"""


# =============================================================================
# Materialized View Schemas (Cached Aggregations)
# =============================================================================

MV_PATIENT_TREATMENT_SUMMARY_SCHEMA = """
-- Materialized view of patient treatment summaries
-- Pre-computed aggregations per patient for faster pathway analysis
-- Refreshed when fact_interventions data changes
CREATE TABLE IF NOT EXISTS mv_patient_treatment_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Patient identification
    upid TEXT NOT NULL UNIQUE,              -- Unique Patient ID

    -- Organization and directory (for filtering)
    org_name TEXT,                          -- Organization name (first org seen)
    directory TEXT,                         -- Primary directory (first directory assigned)

    -- Date range
    first_seen_date DATE NOT NULL,          -- First intervention date
    last_seen_date DATE NOT NULL,           -- Last intervention date
    days_treated INTEGER NOT NULL DEFAULT 0, -- Duration: last_seen - first_seen

    -- Cost aggregations
    total_cost REAL NOT NULL DEFAULT 0,     -- Sum of all intervention costs
    avg_cost_per_intervention REAL,         -- Average cost per intervention

    -- Treatment summary
    intervention_count INTEGER NOT NULL DEFAULT 0,  -- Total number of interventions
    unique_drug_count INTEGER NOT NULL DEFAULT 0,   -- Number of distinct drugs

    -- Drug sequence (pipe-separated standardized drug names in chronological order)
    -- Example: "ADALIMUMAB|ETANERCEPT|INFLIXIMAB"
    drug_sequence TEXT,

    -- Drug frequency counts (JSON: {"ADALIMUMAB": 5, "ETANERCEPT": 3})
    -- Stores count of each drug for this patient
    drug_counts_json TEXT,

    -- Drug cost totals (JSON: {"ADALIMUMAB": 15000.00, "ETANERCEPT": 8000.00})
    -- Stores total cost per drug for this patient
    drug_costs_json TEXT,

    -- Per-drug date ranges (JSON: {"ADALIMUMAB": {"first": "2023-01-01", "last": "2023-06-15"}, ...})
    -- Stores first/last date for each drug
    drug_date_ranges_json TEXT,

    -- Metadata
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_row_count INTEGER               -- Number of fact_interventions rows used
);

-- Index for fast patient lookup
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_upid ON mv_patient_treatment_summary(upid);

-- Indexes for common filter patterns
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_org ON mv_patient_treatment_summary(org_name);
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_directory ON mv_patient_treatment_summary(directory);
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_first_seen ON mv_patient_treatment_summary(first_seen_date);
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_last_seen ON mv_patient_treatment_summary(last_seen_date);

-- Composite index for date range filtering (common in generate_graph)
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_date_range
    ON mv_patient_treatment_summary(first_seen_date, last_seen_date);

-- Composite index for org + directory + dates (full filter pattern)
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_filter_composite
    ON mv_patient_treatment_summary(org_name, directory, first_seen_date, last_seen_date);

-- Index for drug sequence pattern matching
CREATE INDEX IF NOT EXISTS idx_mv_patient_summary_drug_seq ON mv_patient_treatment_summary(drug_sequence);
"""

MATERIALIZED_VIEWS_SCHEMA = f"""
-- Materialized Views Schema
-- Pre-computed aggregations for performance

{MV_PATIENT_TREATMENT_SUMMARY_SCHEMA}
"""


# =============================================================================
# File Tracking Schemas (Incremental Updates)
# =============================================================================

PROCESSED_FILES_SCHEMA = """
-- Tracks processed data files for incremental updates
-- Enables detecting changed files by comparing hashes
-- Stores processing status and statistics
CREATE TABLE IF NOT EXISTS processed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- File identification
    file_path TEXT NOT NULL,                -- Full path to the file
    file_name TEXT NOT NULL,                -- Just the filename (for display)
    file_hash TEXT NOT NULL,                -- SHA256 hash of file contents

    -- File metadata
    file_size_bytes INTEGER,                -- Size of file in bytes
    file_modified_at TIMESTAMP,             -- File's last modification timestamp

    -- Processing results
    row_count INTEGER DEFAULT 0,            -- Number of rows processed from this file
    status TEXT NOT NULL DEFAULT 'pending', -- pending, processing, success, error
    error_message TEXT,                     -- Error details if status='error'

    -- Timestamps
    first_processed_at TIMESTAMP,           -- When first processed
    last_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_duration_seconds REAL,       -- How long processing took

    -- Uniqueness: only one record per file path
    -- Hash changes indicate file content changed (needs reprocessing)
    UNIQUE(file_path)
);

-- Index for fast lookup by file path
CREATE INDEX IF NOT EXISTS idx_processed_files_path ON processed_files(file_path);

-- Index for finding files by status (e.g., find all pending or errored files)
CREATE INDEX IF NOT EXISTS idx_processed_files_status ON processed_files(status);

-- Index for finding files by hash (detect if same file appears at different paths)
CREATE INDEX IF NOT EXISTS idx_processed_files_hash ON processed_files(file_hash);

-- Index for finding recently processed files
CREATE INDEX IF NOT EXISTS idx_processed_files_last_processed ON processed_files(last_processed_at);
"""

FILE_TRACKING_SCHEMA = f"""
-- File Tracking Schema
-- Supports incremental data loading

{PROCESSED_FILES_SCHEMA}
"""


# =============================================================================
# Combined Schemas
# =============================================================================

REFERENCE_TABLES_SCHEMA = f"""
-- Reference Tables Schema
-- Contains lookup data migrated from CSV files

{REF_DRUG_NAMES_SCHEMA}

{REF_ORGANIZATIONS_SCHEMA}

{REF_DIRECTORIES_SCHEMA}

{REF_DRUG_DIRECTORY_MAP_SCHEMA}

{REF_DRUG_INDICATION_CLUSTERS_SCHEMA}
"""

FACT_TABLES_SCHEMA = f"""
-- Fact Tables Schema
-- Contains patient intervention data

{FACT_INTERVENTIONS_SCHEMA}
"""

ALL_TABLES_SCHEMA = f"""
-- Complete Database Schema
-- Reference tables + Fact tables + Materialized views + File tracking

{REFERENCE_TABLES_SCHEMA}

{FACT_TABLES_SCHEMA}

{MATERIALIZED_VIEWS_SCHEMA}

{FILE_TRACKING_SCHEMA}
"""


# =============================================================================
# Schema Helper Functions
# =============================================================================

def create_reference_tables(conn: sqlite3.Connection) -> None:
    """
    Create all reference tables in the database.

    Args:
        conn: SQLite database connection.
    """
    logger.info("Creating reference tables...")
    conn.executescript(REFERENCE_TABLES_SCHEMA)
    logger.info("Reference tables created successfully")


def drop_reference_tables(conn: sqlite3.Connection) -> None:
    """
    Drop all reference tables from the database.

    Args:
        conn: SQLite database connection.

    Warning:
        This will delete all reference data. Use with caution.
    """
    logger.warning("Dropping reference tables...")
    conn.executescript("""
        DROP TABLE IF EXISTS ref_drug_names;
        DROP TABLE IF EXISTS ref_organizations;
        DROP TABLE IF EXISTS ref_directories;
        DROP TABLE IF EXISTS ref_drug_directory_map;
        DROP TABLE IF EXISTS ref_drug_indication_clusters;
    """)
    logger.info("Reference tables dropped")


def get_reference_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Get row counts for all reference tables.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping table name to row count.
    """
    tables = ["ref_drug_names", "ref_organizations", "ref_directories", "ref_drug_directory_map", "ref_drug_indication_clusters"]
    counts = {}

    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        result = cursor.fetchone()
        counts[table] = result[0] if result else 0

    return counts


def verify_reference_tables_exist(conn: sqlite3.Connection) -> list[str]:
    """
    Verify that all reference tables exist.

    Args:
        conn: SQLite database connection.

    Returns:
        List of missing table names. Empty list means all tables exist.
    """
    required_tables = ["ref_drug_names", "ref_organizations", "ref_directories", "ref_drug_directory_map", "ref_drug_indication_clusters"]
    missing = []

    for table in required_tables:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if cursor.fetchone() is None:
            missing.append(table)

    return missing


# =============================================================================
# Fact Table Helper Functions
# =============================================================================

def create_fact_tables(conn: sqlite3.Connection) -> None:
    """
    Create all fact tables in the database (including materialized views).

    Args:
        conn: SQLite database connection.
    """
    logger.info("Creating fact tables...")
    conn.executescript(FACT_TABLES_SCHEMA)
    conn.executescript(MATERIALIZED_VIEWS_SCHEMA)
    logger.info("Fact tables created successfully")


def drop_fact_tables(conn: sqlite3.Connection) -> None:
    """
    Drop all fact tables from the database.

    Args:
        conn: SQLite database connection.

    Warning:
        This will delete all patient intervention data. Use with caution.
    """
    logger.warning("Dropping fact tables...")
    conn.executescript("""
        DROP TABLE IF EXISTS fact_interventions;
        DROP TABLE IF EXISTS mv_patient_treatment_summary;
    """)
    logger.info("Fact tables dropped")


def get_fact_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Get row counts for all fact tables (including materialized views).

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping table name to row count.
    """
    tables = ["fact_interventions", "mv_patient_treatment_summary"]
    counts = {}

    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        result = cursor.fetchone()
        counts[table] = result[0] if result else 0

    return counts


def verify_fact_tables_exist(conn: sqlite3.Connection) -> list[str]:
    """
    Verify that all fact tables exist (including materialized views).

    Args:
        conn: SQLite database connection.

    Returns:
        List of missing table names. Empty list means all tables exist.
    """
    required_tables = ["fact_interventions", "mv_patient_treatment_summary"]
    missing = []

    for table in required_tables:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if cursor.fetchone() is None:
            missing.append(table)

    return missing


# =============================================================================
# File Tracking Helper Functions
# =============================================================================

def create_file_tracking_tables(conn: sqlite3.Connection) -> None:
    """
    Create file tracking tables in the database.

    Args:
        conn: SQLite database connection.
    """
    logger.info("Creating file tracking tables...")
    conn.executescript(FILE_TRACKING_SCHEMA)
    logger.info("File tracking tables created successfully")


def drop_file_tracking_tables(conn: sqlite3.Connection) -> None:
    """
    Drop file tracking tables from the database.

    Args:
        conn: SQLite database connection.

    Warning:
        This will delete all file tracking history.
    """
    logger.warning("Dropping file tracking tables...")
    conn.executescript("""
        DROP TABLE IF EXISTS processed_files;
    """)
    logger.info("File tracking tables dropped")


def get_file_tracking_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Get row counts for file tracking tables.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping table name to row count.
    """
    tables = ["processed_files"]
    counts = {}

    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        result = cursor.fetchone()
        counts[table] = result[0] if result else 0

    return counts


def verify_file_tracking_tables_exist(conn: sqlite3.Connection) -> list[str]:
    """
    Verify that file tracking tables exist.

    Args:
        conn: SQLite database connection.

    Returns:
        List of missing table names. Empty list means all tables exist.
    """
    required_tables = ["processed_files"]
    missing = []

    for table in required_tables:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if cursor.fetchone() is None:
            missing.append(table)

    return missing


# =============================================================================
# Combined Helper Functions
# =============================================================================

def create_all_tables(conn: sqlite3.Connection) -> None:
    """
    Create all tables (reference + fact) in the database.

    Args:
        conn: SQLite database connection.
    """
    logger.info("Creating all database tables...")
    conn.executescript(ALL_TABLES_SCHEMA)
    logger.info("All tables created successfully")


def drop_all_tables(conn: sqlite3.Connection) -> None:
    """
    Drop all tables from the database.

    Args:
        conn: SQLite database connection.

    Warning:
        This will delete all data. Use with extreme caution.
    """
    logger.warning("Dropping all tables...")
    drop_file_tracking_tables(conn)
    drop_fact_tables(conn)
    drop_reference_tables(conn)
    logger.info("All tables dropped")


def get_all_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Get row counts for all tables.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping table name to row count.
    """
    counts = {}
    counts.update(get_reference_table_counts(conn))
    counts.update(get_fact_table_counts(conn))
    counts.update(get_file_tracking_counts(conn))
    return counts


def verify_all_tables_exist(conn: sqlite3.Connection) -> list[str]:
    """
    Verify that all tables exist.

    Args:
        conn: SQLite database connection.

    Returns:
        List of missing table names. Empty list means all tables exist.
    """
    missing = []
    missing.extend(verify_reference_tables_exist(conn))
    missing.extend(verify_fact_tables_exist(conn))
    missing.extend(verify_file_tracking_tables_exist(conn))
    return missing
