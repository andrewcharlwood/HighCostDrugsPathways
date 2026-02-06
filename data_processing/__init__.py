"""
Data processing module for NHS High-Cost Drug Patient Pathway Analysis Tool.

Contains SQLite database management, data loaders, and Snowflake integration.
Handles the migration from CSV-based storage to SQLite for improved performance.

Submodules:
    database: SQLite connection management and schema definitions
    loader: Data loading abstractions (CSV, SQLite, Snowflake)
    snowflake_connector: Snowflake integration with SSO authentication
"""

from data_processing.database import (
    DatabaseConfig,
    DatabaseManager,
    default_db_config,
    default_db_manager,
)
from data_processing.schema import (
    # Reference table schemas
    REF_DRUG_NAMES_SCHEMA,
    REF_ORGANIZATIONS_SCHEMA,
    REF_DIRECTORIES_SCHEMA,
    REF_DRUG_DIRECTORY_MAP_SCHEMA,
    REF_DRUG_INDICATION_CLUSTERS_SCHEMA,
    REFERENCE_TABLES_SCHEMA,
    # Combined schema
    ALL_TABLES_SCHEMA,
    # Reference table functions
    create_reference_tables,
    drop_reference_tables,
    get_reference_table_counts,
    verify_reference_tables_exist,
    # Combined functions
    create_all_tables,
    drop_all_tables,
    get_all_table_counts,
    verify_all_tables_exist,
)

# Reference data migration functions
from data_processing.reference_data import (
    MigrationResult,
    migrate_drug_names,
    get_drug_name_counts,
    verify_drug_names_migration,
    migrate_organizations,
    get_organization_counts,
    verify_organizations_migration,
    migrate_directories,
    get_directory_counts,
    verify_directories_migration,
    migrate_drug_directory_map,
    get_drug_directory_map_counts,
    verify_drug_directory_map_migration,
    migrate_drug_indication_clusters,
    get_drug_indication_cluster_counts,
    verify_drug_indication_clusters_migration,
)

# Data loader abstractions
from data_processing.loader import (
    DataLoader,
    FileDataLoader,
    LoadResult,
    get_loader,
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
)

# Snowflake connector
from data_processing.snowflake_connector import (
    SnowflakeConnector,
    SnowflakeConnectionError,
    SnowflakeNotConfiguredError,
    SnowflakeNotAvailableError,
    ConnectionInfo,
    get_connector,
    reset_connector,
    is_snowflake_available,
    is_snowflake_configured,
    SNOWFLAKE_AVAILABLE,
)

# Query result caching
from data_processing.cache import (
    QueryCache,
    CacheEntry,
    CacheStats,
    get_cache,
    reset_cache,
    is_cache_enabled,
)

# Data source management with fallback chain
from data_processing.data_source import (
    DataSourceType,
    DataSourceResult,
    SourceStatus,
    DataSourceManager,
    get_data_source_manager,
    get_data,
    reset_data_source_manager,
)

# Diagnosis lookup (GP diagnosis validation)
from data_processing.diagnosis_lookup import (
    ClusterSnomedCodes,
    IndicationValidationResult,
    DrugIndicationMatchRate,
    get_drug_clusters,
    get_drug_cluster_ids,
    get_cluster_snomed_codes,
    patient_has_indication,
    validate_indication,
    get_indication_match_rate,
    batch_validate_indications,
    get_available_clusters,
)

__all__ = [
    # Database management
    "DatabaseConfig",
    "DatabaseManager",
    "default_db_config",
    "default_db_manager",
    # Reference table schemas
    "REF_DRUG_NAMES_SCHEMA",
    "REF_ORGANIZATIONS_SCHEMA",
    "REF_DIRECTORIES_SCHEMA",
    "REF_DRUG_DIRECTORY_MAP_SCHEMA",
    "REF_DRUG_INDICATION_CLUSTERS_SCHEMA",
    "REFERENCE_TABLES_SCHEMA",
    # Combined schema
    "ALL_TABLES_SCHEMA",
    # Reference table functions
    "create_reference_tables",
    "drop_reference_tables",
    "get_reference_table_counts",
    "verify_reference_tables_exist",
    # Combined functions
    "create_all_tables",
    "drop_all_tables",
    "get_all_table_counts",
    "verify_all_tables_exist",
    # Reference data migration
    "MigrationResult",
    "migrate_drug_names",
    "get_drug_name_counts",
    "verify_drug_names_migration",
    "migrate_organizations",
    "get_organization_counts",
    "verify_organizations_migration",
    "migrate_directories",
    "get_directory_counts",
    "verify_directories_migration",
    "migrate_drug_directory_map",
    "get_drug_directory_map_counts",
    "verify_drug_directory_map_migration",
    "migrate_drug_indication_clusters",
    "get_drug_indication_cluster_counts",
    "verify_drug_indication_clusters_migration",
    # Data loader abstractions
    "DataLoader",
    "FileDataLoader",
    "LoadResult",
    "get_loader",
    "REQUIRED_COLUMNS",
    "OPTIONAL_COLUMNS",
    # Snowflake connector
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
    # Query result caching
    "QueryCache",
    "CacheEntry",
    "CacheStats",
    "get_cache",
    "reset_cache",
    "is_cache_enabled",
    # Data source management with fallback chain
    "DataSourceType",
    "DataSourceResult",
    "SourceStatus",
    "DataSourceManager",
    "get_data_source_manager",
    "get_data",
    "reset_data_source_manager",
    # Diagnosis lookup
    "ClusterSnomedCodes",
    "IndicationValidationResult",
    "DrugIndicationMatchRate",
    "get_drug_clusters",
    "get_drug_cluster_ids",
    "get_cluster_snomed_codes",
    "patient_has_indication",
    "validate_indication",
    "get_indication_match_rate",
    "batch_validate_indications",
    "get_available_clusters",
]
