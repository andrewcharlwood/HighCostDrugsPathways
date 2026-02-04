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
# Pathway Data Architecture Schemas
# =============================================================================

PATHWAY_DATE_FILTERS_SCHEMA = """
-- Stores the 6 pre-computed date filter combinations
-- Each combination represents a different initiated/last_seen date range
-- Used to efficiently query pre-computed pathway data
CREATE TABLE IF NOT EXISTS pathway_date_filters (
    id TEXT PRIMARY KEY,                    -- e.g., 'all_6mo', '1yr_12mo'
    initiated_label TEXT NOT NULL,          -- e.g., 'All years', 'Last 1 year', 'Last 2 years'
    last_seen_label TEXT NOT NULL,          -- e.g., 'Last 6 months', 'Last 12 months'
    initiated_years INTEGER,                -- NULL for 'All', 1, or 2
    last_seen_months INTEGER NOT NULL,      -- 6 or 12
    is_default INTEGER DEFAULT 0,           -- 1 for 'all_6mo' (default selection)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pre-populate the 6 combinations
INSERT OR REPLACE INTO pathway_date_filters (id, initiated_label, last_seen_label, initiated_years, last_seen_months, is_default) VALUES
    ('all_6mo', 'All years', 'Last 6 months', NULL, 6, 1),
    ('all_12mo', 'All years', 'Last 12 months', NULL, 12, 0),
    ('1yr_6mo', 'Last 1 year', 'Last 6 months', 1, 6, 0),
    ('1yr_12mo', 'Last 1 year', 'Last 12 months', 1, 12, 0),
    ('2yr_6mo', 'Last 2 years', 'Last 6 months', 2, 6, 0),
    ('2yr_12mo', 'Last 2 years', 'Last 12 months', 2, 12, 0);
"""

PATHWAY_NODES_SCHEMA = """
-- Main pathway nodes table (one set per date filter combination)
-- Stores pre-computed pathway hierarchy with all visualization data
-- Designed for fast filtering by date_filter_id + trust/directory/drug
CREATE TABLE IF NOT EXISTS pathway_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Date filter combination this belongs to
    date_filter_id TEXT NOT NULL,

    -- Hierarchy structure (for icicle chart)
    parents TEXT NOT NULL,                  -- Parent node identifier
    ids TEXT NOT NULL,                      -- Unique node identifier (hierarchical path)
    labels TEXT NOT NULL,                   -- Display label
    level INTEGER NOT NULL,                 -- Hierarchy depth (0=root, 1=trust, 2=directory, 3+=drugs)

    -- Patient counts (accurate for this date filter combination)
    value INTEGER NOT NULL DEFAULT 0,       -- Patient count

    -- Cost metrics
    cost REAL NOT NULL DEFAULT 0.0,         -- Total cost
    costpp REAL,                            -- Cost per patient
    cost_pp_pa TEXT,                        -- Cost per patient per annum (formatted string)

    -- Visualization
    colour REAL NOT NULL DEFAULT 0.0,       -- Color value (proportion of parent)

    -- Date ranges (for this node)
    first_seen TEXT,                        -- First intervention date (ISO format)
    last_seen TEXT,                         -- Last intervention date (ISO format)
    first_seen_parent TEXT,                 -- Earliest date in parent group
    last_seen_parent TEXT,                  -- Latest date in parent group

    -- Treatment statistics
    average_spacing TEXT,                   -- Formatted treatment duration string
    average_administered TEXT,              -- JSON array of average doses per drug
    avg_days REAL,                          -- Average treatment duration in days

    -- Denormalized filter columns (for efficient WHERE clause filtering)
    trust_name TEXT,                        -- Extracted trust name from ids
    directory TEXT,                         -- Extracted directory from ids
    drug_sequence TEXT,                     -- Pipe-separated drug sequence from pathway

    -- Metadata
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    data_refresh_id TEXT,                   -- Links to pathway_refresh_log

    -- Unique per date filter + pathway
    UNIQUE(date_filter_id, ids),
    FOREIGN KEY (date_filter_id) REFERENCES pathway_date_filters(id)
);

-- Indexes for efficient filtering
-- Primary filter: select by date_filter_id
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_date_filter ON pathway_nodes(date_filter_id);

-- Level filter: often used with date_filter_id
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_level ON pathway_nodes(date_filter_id, level);

-- Trust filter: for Trust dropdown filtering
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_trust ON pathway_nodes(date_filter_id, trust_name);

-- Directory filter: for Directory dropdown filtering
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_directory ON pathway_nodes(date_filter_id, directory);

-- Drug sequence filter: for drug filtering (uses LIKE '%DRUG%')
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_drug_seq ON pathway_nodes(drug_sequence);

-- Parents filter: for finding children of a node
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_parents ON pathway_nodes(date_filter_id, parents);

-- Composite index for common filter combination
CREATE INDEX IF NOT EXISTS idx_pathway_nodes_filter_composite
    ON pathway_nodes(date_filter_id, trust_name, directory);
"""

PATHWAY_REFRESH_LOG_SCHEMA = """
-- Metadata table for tracking refresh status
-- Tracks when pathway data was last refreshed from Snowflake
CREATE TABLE IF NOT EXISTS pathway_refresh_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    refresh_id TEXT NOT NULL,               -- Unique identifier for this refresh run
    started_at TEXT NOT NULL,               -- ISO timestamp when refresh started
    completed_at TEXT,                      -- ISO timestamp when refresh completed (NULL if still running)
    status TEXT DEFAULT 'running',          -- 'running', 'completed', 'failed'
    record_count INTEGER,                   -- Total pathway_nodes records created
    date_filter_counts TEXT,                -- JSON: {"all_6mo": 1234, "all_12mo": 1567, ...}
    error_message TEXT,                     -- Error details if status='failed'
    snowflake_query_date_from TEXT,         -- Start date of Snowflake query
    snowflake_query_date_to TEXT,           -- End date of Snowflake query
    processing_duration_seconds REAL,       -- How long the refresh took
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Index for finding latest refresh
CREATE INDEX IF NOT EXISTS idx_pathway_refresh_log_started ON pathway_refresh_log(started_at DESC);

-- Index for finding by status
CREATE INDEX IF NOT EXISTS idx_pathway_refresh_log_status ON pathway_refresh_log(status);
"""

# Combined pathway schema
PATHWAY_TABLES_SCHEMA = f"""
-- Pathway Data Architecture Tables
-- Pre-computed pathway data for fast Reflex filtering

{PATHWAY_DATE_FILTERS_SCHEMA}

{PATHWAY_NODES_SCHEMA}

{PATHWAY_REFRESH_LOG_SCHEMA}
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
-- Reference tables + Fact tables + Materialized views + File tracking + Pathway tables

{REFERENCE_TABLES_SCHEMA}

{FACT_TABLES_SCHEMA}

{MATERIALIZED_VIEWS_SCHEMA}

{FILE_TRACKING_SCHEMA}

{PATHWAY_TABLES_SCHEMA}
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
# Pathway Table Helper Functions
# =============================================================================

def create_pathway_tables(conn: sqlite3.Connection) -> None:
    """
    Create pathway data architecture tables in the database.

    Creates:
    - pathway_date_filters: 6 pre-defined date filter combinations
    - pathway_nodes: Pre-computed pathway hierarchy data
    - pathway_refresh_log: Refresh tracking metadata

    Args:
        conn: SQLite database connection.
    """
    logger.info("Creating pathway tables...")
    conn.executescript(PATHWAY_TABLES_SCHEMA)
    logger.info("Pathway tables created successfully")


def drop_pathway_tables(conn: sqlite3.Connection) -> None:
    """
    Drop pathway data architecture tables from the database.

    Args:
        conn: SQLite database connection.

    Warning:
        This will delete all pre-computed pathway data.
    """
    logger.warning("Dropping pathway tables...")
    conn.executescript("""
        DROP TABLE IF EXISTS pathway_nodes;
        DROP TABLE IF EXISTS pathway_refresh_log;
        DROP TABLE IF EXISTS pathway_date_filters;
    """)
    logger.info("Pathway tables dropped")


def get_pathway_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Get row counts for pathway tables.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary mapping table name to row count.
    """
    tables = ["pathway_date_filters", "pathway_nodes", "pathway_refresh_log"]
    counts = {}

    for table in tables:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            result = cursor.fetchone()
            counts[table] = result[0] if result else 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            counts[table] = 0

    return counts


def verify_pathway_tables_exist(conn: sqlite3.Connection) -> list[str]:
    """
    Verify that pathway tables exist.

    Args:
        conn: SQLite database connection.

    Returns:
        List of missing table names. Empty list means all tables exist.
    """
    required_tables = ["pathway_date_filters", "pathway_nodes", "pathway_refresh_log"]
    missing = []

    for table in required_tables:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if cursor.fetchone() is None:
            missing.append(table)

    return missing


def clear_pathway_nodes(conn: sqlite3.Connection, date_filter_id: str | None = None) -> int:
    """
    Clear pathway nodes, optionally for a specific date filter.

    Args:
        conn: SQLite database connection.
        date_filter_id: If provided, only clear nodes for this date filter.
                        If None, clear all pathway nodes.

    Returns:
        Number of rows deleted.
    """
    if date_filter_id:
        cursor = conn.execute(
            "DELETE FROM pathway_nodes WHERE date_filter_id = ?",
            (date_filter_id,)
        )
    else:
        cursor = conn.execute("DELETE FROM pathway_nodes")

    deleted_count = cursor.rowcount
    conn.commit()
    logger.info(f"Cleared {deleted_count} pathway nodes")
    return deleted_count


def get_pathway_refresh_status(conn: sqlite3.Connection) -> dict | None:
    """
    Get the status of the most recent pathway refresh.

    Args:
        conn: SQLite database connection.

    Returns:
        Dictionary with refresh status, or None if no refresh has been done.
    """
    try:
        cursor = conn.execute("""
            SELECT refresh_id, started_at, completed_at, status, record_count,
                   date_filter_counts, error_message, processing_duration_seconds
            FROM pathway_refresh_log
            ORDER BY started_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return {
                "refresh_id": row[0],
                "started_at": row[1],
                "completed_at": row[2],
                "status": row[3],
                "record_count": row[4],
                "date_filter_counts": row[5],
                "error_message": row[6],
                "processing_duration_seconds": row[7],
            }
        return None
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return None


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
    drop_pathway_tables(conn)
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
    counts.update(get_pathway_table_counts(conn))
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
    missing.extend(verify_pathway_tables_exist(conn))
    return missing
