"""
Pathway data processing pipeline.

This module provides functions to:
1. Fetch and transform raw intervention data from Snowflake
2. Process data for each of the 6 date filter combinations
3. Extract denormalized fields from hierarchical path strings
4. Convert processed data to records for SQLite storage

The pipeline integrates with:
- analysis/pathway_analyzer.py: generate_icicle_chart() for pathway processing
- data_processing/snowflake_connector.py: fetch_activity_data() for data retrieval
- tools/data.py: patient_id(), drug_names(), department_identification()
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Literal
import json

import numpy as np
import pandas as pd

from core import PathConfig, default_paths
from core.logging_config import get_logger
from analysis.pathway_analyzer import generate_icicle_chart, generate_icicle_chart_indication
from tools.data import patient_id, drug_names, department_identification

logger = get_logger(__name__)

# Type alias for chart types
ChartType = Literal["directory", "indication"]


@dataclass
class DateFilterConfig:
    """Configuration for a date filter combination."""

    id: str                    # e.g., 'all_6mo', '1yr_12mo'
    initiated_years: Optional[int]  # None for 'All', 1, or 2
    last_seen_months: int      # 6 or 12


# Pre-defined date filter configurations matching pathway_date_filters table
DATE_FILTER_CONFIGS = [
    DateFilterConfig(id="all_6mo", initiated_years=None, last_seen_months=6),
    DateFilterConfig(id="all_12mo", initiated_years=None, last_seen_months=12),
    DateFilterConfig(id="1yr_6mo", initiated_years=1, last_seen_months=6),
    DateFilterConfig(id="1yr_12mo", initiated_years=1, last_seen_months=12),
    DateFilterConfig(id="2yr_6mo", initiated_years=2, last_seen_months=6),
    DateFilterConfig(id="2yr_12mo", initiated_years=2, last_seen_months=12),
]


def compute_date_ranges(
    config: DateFilterConfig,
    max_date: Optional[date] = None,
) -> tuple[str, str, str]:
    """
    Compute actual date strings from a date filter configuration.

    Args:
        config: DateFilterConfig with initiated_years and last_seen_months
        max_date: Reference date (defaults to today)

    Returns:
        Tuple of (start_date, end_date, last_seen_date) as ISO format strings
        - start_date: Start of initiated filter period
        - end_date: End of initiated filter period (usually max_date)
        - last_seen_date: Date threshold for last_seen filter
    """
    if max_date is None:
        max_date = date.today()

    # Calculate end_date (always max_date)
    end_date = max_date

    # Calculate start_date based on initiated_years
    if config.initiated_years is None:
        # "All years" - use a very old date
        start_date = date(2000, 1, 1)
    else:
        # Last N years from max_date
        start_date = max_date.replace(year=max_date.year - config.initiated_years)

    # Calculate last_seen_date based on last_seen_months
    # Patients must have been seen within the last N months
    last_seen_date = max_date - timedelta(days=config.last_seen_months * 30)

    return (
        start_date.isoformat(),
        end_date.isoformat(),
        last_seen_date.isoformat(),
    )


def fetch_and_transform_data(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    provider_codes: Optional[list[str]] = None,
    paths: Optional[PathConfig] = None,
) -> pd.DataFrame:
    """
    Fetch data from Snowflake and apply standard transformations.

    This function:
    1. Fetches raw intervention data from Snowflake
    2. Applies UPID generation (Provider Code[:3] + PersonKey)
    3. Standardizes drug names via drugnames.csv mapping
    4. Assigns directories using the 5-level fallback logic

    Args:
        start_date: Optional start date filter for Snowflake query
        end_date: Optional end date filter for Snowflake query
        provider_codes: Optional list of provider codes to filter
        paths: PathConfig for file paths (uses default if None)

    Returns:
        DataFrame with columns: UPID, Drug Name, Directory, Intervention Date,
        Price Actual, Provider Code, PersonKey, OrganisationName, etc.

    Raises:
        ImportError: If snowflake-connector-python is not installed
        SnowflakeConnectionError: If connection fails
    """
    if paths is None:
        paths = default_paths

    # Import here to avoid circular imports and handle optional dependency
    from data_processing.snowflake_connector import get_connector, is_snowflake_available

    if not is_snowflake_available():
        raise ImportError(
            "snowflake-connector-python is not installed. "
            "Install it with: pip install snowflake-connector-python"
        )

    logger.info("Fetching activity data from Snowflake...")

    connector = get_connector()
    raw_data = connector.fetch_activity_data(
        start_date=start_date,
        end_date=end_date,
        provider_codes=provider_codes,
        max_rows=0,  # No limit
    )

    if not raw_data:
        logger.warning("No data returned from Snowflake")
        return pd.DataFrame()

    logger.info(f"Fetched {len(raw_data)} records from Snowflake")

    # Convert to DataFrame
    df = pd.DataFrame(raw_data)

    # Apply transformations in the standard order
    logger.info("Applying data transformations...")

    # 1. Generate UPID
    df = patient_id(df)
    logger.info(f"Generated UPID for {df['UPID'].nunique()} unique patients")

    # 2. Standardize drug names
    df = drug_names(df, paths)
    # Remove rows where drug name mapping failed (NaN)
    before_count = len(df)
    df = df.dropna(subset=['Drug Name'])
    after_count = len(df)
    if before_count != after_count:
        logger.info(f"Removed {before_count - after_count} rows with unmapped drug names")

    # 3. Assign directories
    df = department_identification(df, paths)
    logger.info(f"Assigned directories to {len(df)} records")

    # Ensure Intervention Date is datetime
    df['Intervention Date'] = pd.to_datetime(df['Intervention Date'])

    logger.info(f"Data transformation complete. Final record count: {len(df)}")
    return df


def process_pathway_for_date_filter(
    df: pd.DataFrame,
    config: DateFilterConfig,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    minimum_patients: int = 5,
    max_date: Optional[date] = None,
    paths: Optional[PathConfig] = None,
) -> Optional[pd.DataFrame]:
    """
    Process pathway data for a single date filter configuration.

    Uses the existing generate_icicle_chart() function from pathway_analyzer.py
    to build the pathway hierarchy with treatment statistics.

    Args:
        df: Transformed DataFrame from fetch_and_transform_data()
        config: DateFilterConfig specifying the date filter combination
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        minimum_patients: Minimum patients to include a pathway
        max_date: Reference date for computing date ranges
        paths: PathConfig for file paths

    Returns:
        DataFrame with pathway hierarchy (ice_df) or None if no data
    """
    if paths is None:
        paths = default_paths

    # Compute actual date ranges for this filter config
    start_date, end_date, last_seen_date = compute_date_ranges(config, max_date)

    logger.info(f"Processing pathway for {config.id}")
    logger.info(f"  Date range: {start_date} to {end_date}")
    logger.info(f"  Last seen after: {last_seen_date}")

    # Use the existing pathway analyzer
    ice_df, title = generate_icicle_chart(
        df=df,
        start_date=start_date,
        end_date=end_date,
        last_seen_date=last_seen_date,
        trust_filter=trust_filter,
        drug_filter=drug_filter,
        directory_filter=directory_filter,
        minimum_num_patients=minimum_patients,
        title="",
        paths=paths,
    )

    if ice_df is None or len(ice_df) == 0:
        logger.warning(f"No pathway data for filter {config.id}")
        return None

    logger.info(f"Generated {len(ice_df)} pathway nodes for {config.id}")
    return ice_df


def process_indication_pathway_for_date_filter(
    df: pd.DataFrame,
    indication_df: pd.DataFrame,
    config: DateFilterConfig,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    minimum_patients: int = 5,
    max_date: Optional[date] = None,
    paths: Optional[PathConfig] = None,
) -> Optional[pd.DataFrame]:
    """
    Process indication-based pathway data for a single date filter configuration.

    This is similar to process_pathway_for_date_filter() but uses indication-based
    grouping (Search_Term from GP diagnosis) instead of directory grouping.

    Hierarchy: Trust → Indication_Group → Drug → Pathway

    Args:
        df: Transformed DataFrame from fetch_and_transform_data()
        indication_df: DataFrame with UPID → Indication_Group mapping
                      Must have columns: UPID, Indication_Group
                      Indication_Group is either Search_Term or "Directory (no GP dx)"
        config: DateFilterConfig specifying the date filter combination
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        minimum_patients: Minimum patients to include a pathway
        max_date: Reference date for computing date ranges
        paths: PathConfig for file paths

    Returns:
        DataFrame with pathway hierarchy (ice_df) or None if no data
    """
    if paths is None:
        paths = default_paths

    # Compute actual date ranges for this filter config
    start_date, end_date, last_seen_date = compute_date_ranges(config, max_date)

    logger.info(f"Processing indication pathway for {config.id}")
    logger.info(f"  Date range: {start_date} to {end_date}")
    logger.info(f"  Last seen after: {last_seen_date}")

    # Use the indication-aware pathway analyzer
    ice_df, title = generate_icicle_chart_indication(
        df=df,
        indication_df=indication_df,
        start_date=start_date,
        end_date=end_date,
        last_seen_date=last_seen_date,
        trust_filter=trust_filter,
        drug_filter=drug_filter,
        directory_filter=directory_filter,
        minimum_num_patients=minimum_patients,
        title="",
        paths=paths,
    )

    if ice_df is None or len(ice_df) == 0:
        logger.warning(f"No indication pathway data for filter {config.id}")
        return None

    logger.info(f"Generated {len(ice_df)} indication pathway nodes for {config.id}")
    return ice_df


def extract_denormalized_fields(ice_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract denormalized filter columns from the ids column.

    The ids column contains hierarchical paths like:
    - "N&WICS" (root)
    - "N&WICS - NNUH" (trust level)
    - "N&WICS - NNUH - OPHTHALMOLOGY" (directory level)
    - "N&WICS - NNUH - OPHTHALMOLOGY - RANIBIZUMAB" (first drug)
    - "N&WICS - NNUH - OPHTHALMOLOGY - RANIBIZUMAB - AFLIBERCEPT" (pathway)

    This function extracts:
    - trust_name: The trust component (level 1)
    - directory: The directory component (level 2)
    - drug_sequence: Pipe-separated drugs (level 3+)

    Args:
        ice_df: DataFrame from generate_icicle_chart()

    Returns:
        DataFrame with added columns: trust_name, directory, drug_sequence
    """
    df = ice_df.copy()

    # Split ids by " - " delimiter
    def extract_components(ids_str: str) -> tuple[str, str, str]:
        """Extract trust, directory, and drug sequence from ids string."""
        if not ids_str or pd.isna(ids_str):
            return ("", "", "")

        parts = ids_str.split(" - ")

        # Level 0: Root (e.g., "N&WICS")
        if len(parts) <= 1:
            return ("", "", "")

        # Level 1+: Trust is always parts[1]
        trust_name = parts[1] if len(parts) > 1 else ""

        # Level 2+: Directory is parts[2]
        directory = parts[2] if len(parts) > 2 else ""

        # Level 3+: Drugs are parts[3:]
        drugs = parts[3:] if len(parts) > 3 else []
        drug_sequence = "|".join(drugs) if drugs else ""

        return (trust_name, directory, drug_sequence)

    # Apply extraction to all rows
    extracted = df['ids'].apply(extract_components)
    df['trust_name'] = extracted.apply(lambda x: x[0])
    df['directory'] = extracted.apply(lambda x: x[1])
    df['drug_sequence'] = extracted.apply(lambda x: x[2])

    logger.info(f"Extracted denormalized fields for {len(df)} nodes")
    logger.info(f"  Unique trusts: {df['trust_name'].nunique()}")
    logger.info(f"  Unique directories: {df['directory'].nunique()}")

    return df


def extract_indication_fields(ice_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract denormalized filter columns from the ids column for indication charts.

    Similar to extract_denormalized_fields() but for indication-based charts where
    the level-2 grouping is Search_Term (or fallback directorate) instead of Directory.

    The ids column contains hierarchical paths like:
    - "N&WICS" (root)
    - "N&WICS - NNUH" (trust level)
    - "N&WICS - NNUH - rheumatoid arthritis" (search_term level - matched patient)
    - "N&WICS - NNUH - RHEUMATOLOGY (no GP dx)" (fallback level - unmatched patient)
    - "N&WICS - NNUH - rheumatoid arthritis - ADALIMUMAB" (first drug)
    - "N&WICS - NNUH - rheumatoid arthritis - ADALIMUMAB - ETANERCEPT" (pathway)

    This function extracts:
    - trust_name: The trust component (level 1)
    - search_term: The Search_Term or fallback directorate (level 2)
    - drug_sequence: Pipe-separated drugs (level 3+)

    Note: For indication charts, 'directory' column contains the search_term
    to maintain schema compatibility with the pathway_nodes table.

    Args:
        ice_df: DataFrame from generate_icicle_chart() with indication grouping

    Returns:
        DataFrame with added columns: trust_name, directory (=search_term), drug_sequence
    """
    df = ice_df.copy()

    def extract_components(ids_str: str) -> tuple[str, str, str]:
        """Extract trust, search_term, and drug sequence from ids string."""
        if not ids_str or pd.isna(ids_str):
            return ("", "", "")

        parts = ids_str.split(" - ")

        # Level 0: Root (e.g., "N&WICS")
        if len(parts) <= 1:
            return ("", "", "")

        # Level 1+: Trust is always parts[1]
        trust_name = parts[1] if len(parts) > 1 else ""

        # Level 2+: Search_term (or fallback) is parts[2]
        search_term = parts[2] if len(parts) > 2 else ""

        # Level 3+: Drugs are parts[3:]
        drugs = parts[3:] if len(parts) > 3 else []
        drug_sequence = "|".join(drugs) if drugs else ""

        return (trust_name, search_term, drug_sequence)

    # Apply extraction to all rows
    extracted = df['ids'].apply(extract_components)
    df['trust_name'] = extracted.apply(lambda x: x[0])
    # Use 'directory' column to store search_term for schema compatibility
    df['directory'] = extracted.apply(lambda x: x[1])
    df['drug_sequence'] = extracted.apply(lambda x: x[2])

    logger.info(f"Extracted indication fields for {len(df)} nodes")
    logger.info(f"  Unique trusts: {df['trust_name'].nunique()}")
    logger.info(f"  Unique search_terms: {df['directory'].nunique()}")

    return df


def convert_to_records(
    ice_df: pd.DataFrame,
    date_filter_id: str,
    refresh_id: Optional[str] = None,
    chart_type: ChartType = "directory",
) -> list[dict]:
    """
    Convert ice_df to a list of dictionaries for SQLite insertion.

    Maps ice_df columns to pathway_nodes table schema:
    - parents, ids, labels: Direct mapping
    - level: From ice_df['level']
    - value, cost, costpp, colour: Direct mapping
    - cost_pp_pa: From ice_df['cost_pp_pa']
    - first_seen, last_seen, first_seen_parent, last_seen_parent: Date columns
    - average_spacing: From ice_df['average_spacing']
    - average_administered: JSON serialization of list
    - avg_days: From ice_df['avg_days']
    - trust_name, directory, drug_sequence: Denormalized fields
    - date_filter_id: The filter combination ID
    - chart_type: "directory" or "indication"
    - data_refresh_id: Optional refresh tracking ID

    Args:
        ice_df: DataFrame from generate_icicle_chart() with denormalized fields
        date_filter_id: The date filter combination ID (e.g., 'all_6mo')
        refresh_id: Optional refresh tracking ID
        chart_type: Chart type - "directory" (default) or "indication"

    Returns:
        List of dictionaries ready for SQLite insertion
    """
    records = []

    for _, row in ice_df.iterrows():
        # Handle date formatting
        first_seen = None
        last_seen = None
        first_seen_parent = None
        last_seen_parent = None

        if pd.notna(row.get('First seen')):
            if hasattr(row['First seen'], 'isoformat'):
                first_seen = row['First seen'].isoformat()
            else:
                first_seen = str(row['First seen'])

        if pd.notna(row.get('Last seen')):
            if hasattr(row['Last seen'], 'isoformat'):
                last_seen = row['Last seen'].isoformat()
            else:
                last_seen = str(row['Last seen'])

        if pd.notna(row.get('First seen (Parent)')):
            first_seen_parent = str(row['First seen (Parent)'])

        if pd.notna(row.get('Last seen (Parent)')):
            last_seen_parent = str(row['Last seen (Parent)'])

        # Handle average_administered (could be list, ndarray, or None)
        average_administered = None
        val = row.get('average_administered')
        if val is not None:
            # Check for scalar None-like values
            try:
                if pd.isna(val):
                    average_administered = None
                elif isinstance(val, (list, np.ndarray)):
                    average_administered = json.dumps(list(val) if hasattr(val, 'tolist') else val)
                else:
                    average_administered = str(val)
            except (ValueError, TypeError):
                # pd.isna raises ValueError for arrays with >1 element
                # In that case, val is an array/list, so convert to JSON
                if hasattr(val, 'tolist'):
                    average_administered = json.dumps(val.tolist())
                elif isinstance(val, list):
                    average_administered = json.dumps(val)
                else:
                    average_administered = str(val)

        record = {
            'date_filter_id': date_filter_id,
            'chart_type': chart_type,
            'parents': str(row.get('parents', '')) if pd.notna(row.get('parents')) else '',
            'ids': str(row.get('ids', '')) if pd.notna(row.get('ids')) else '',
            'labels': str(row.get('labels', '')) if pd.notna(row.get('labels')) else '',
            'level': int(row.get('level', 0)) if pd.notna(row.get('level')) else 0,
            'value': int(row.get('value', 0)) if pd.notna(row.get('value')) else 0,
            'cost': float(row.get('cost', 0)) if pd.notna(row.get('cost')) else 0.0,
            'costpp': float(row.get('costpp')) if pd.notna(row.get('costpp')) else None,
            'cost_pp_pa': str(row.get('cost_pp_pa', '')) if pd.notna(row.get('cost_pp_pa')) else None,
            'colour': float(row.get('colour', 0)) if pd.notna(row.get('colour')) else 0.0,
            'first_seen': first_seen,
            'last_seen': last_seen,
            'first_seen_parent': first_seen_parent,
            'last_seen_parent': last_seen_parent,
            'average_spacing': str(row.get('average_spacing', '')) if pd.notna(row.get('average_spacing')) else None,
            'average_administered': average_administered,
            'avg_days': float(row['avg_days'].total_seconds() / 86400) if pd.notna(row.get('avg_days')) and hasattr(row.get('avg_days'), 'total_seconds') else (float(row.get('avg_days')) if pd.notna(row.get('avg_days')) else None),
            'trust_name': row.get('trust_name', '') if pd.notna(row.get('trust_name')) else None,
            'directory': row.get('directory', '') if pd.notna(row.get('directory')) else None,
            'drug_sequence': row.get('drug_sequence', '') if pd.notna(row.get('drug_sequence')) else None,
            'data_refresh_id': refresh_id,
        }
        records.append(record)

    logger.info(f"Converted {len(records)} pathway nodes to records for {date_filter_id} ({chart_type})")
    return records


def process_all_date_filters(
    df: pd.DataFrame,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    minimum_patients: int = 5,
    max_date: Optional[date] = None,
    refresh_id: Optional[str] = None,
    paths: Optional[PathConfig] = None,
) -> dict[str, list[dict]]:
    """
    Process pathway data for all 6 date filter combinations.

    This is a convenience function that processes all DATE_FILTER_CONFIGS
    and returns a dictionary of records ready for SQLite insertion.

    Args:
        df: Transformed DataFrame from fetch_and_transform_data()
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        minimum_patients: Minimum patients to include a pathway
        max_date: Reference date for computing date ranges
        refresh_id: Optional refresh tracking ID
        paths: PathConfig for file paths

    Returns:
        Dictionary mapping date_filter_id to list of record dicts
        e.g., {"all_6mo": [...], "all_12mo": [...], ...}
    """
    if paths is None:
        paths = default_paths

    results = {}

    for config in DATE_FILTER_CONFIGS:
        logger.info(f"Processing date filter: {config.id}")

        # Process pathway for this date filter
        ice_df = process_pathway_for_date_filter(
            df=df,
            config=config,
            trust_filter=trust_filter,
            drug_filter=drug_filter,
            directory_filter=directory_filter,
            minimum_patients=minimum_patients,
            max_date=max_date,
            paths=paths,
        )

        if ice_df is None:
            logger.warning(f"Skipping {config.id} - no data")
            results[config.id] = []
            continue

        # Extract denormalized fields
        ice_df = extract_denormalized_fields(ice_df)

        # Convert to records
        records = convert_to_records(ice_df, config.id, refresh_id)
        results[config.id] = records

        logger.info(f"Completed {config.id}: {len(records)} nodes")

    total_records = sum(len(r) for r in results.values())
    logger.info(f"Total pathway nodes across all filters: {total_records}")

    return results


# Export public API
__all__ = [
    # Types
    "ChartType",
    # Data classes
    "DateFilterConfig",
    "DATE_FILTER_CONFIGS",
    # Core functions
    "compute_date_ranges",
    "fetch_and_transform_data",
    # Directory chart processing
    "process_pathway_for_date_filter",
    "extract_denormalized_fields",
    # Indication chart processing
    "process_indication_pathway_for_date_filter",
    "extract_indication_fields",
    # Common utilities
    "convert_to_records",
    "process_all_date_filters",
]
