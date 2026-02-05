"""
Diagnosis lookup module for NHS Patient Pathway Analysis.

Provides functions to validate patient indications by checking GP diagnosis records
against SNOMED cluster codes. Uses the drug-to-cluster mapping from
drug_indication_clusters.csv and queries Snowflake for SNOMED codes and GP records.

Key workflow:
1. Get drug's valid indication clusters from local mapping
2. Get all SNOMED codes for those clusters from Snowflake
3. Check if patient has any of those SNOMED codes in GP records
4. Report indication validation status

IMPORTANT: HCD activity data indication codes are UNRELIABLE. This module uses
GP/Primary Care data (PrimaryCareClinicalCoding) as the authoritative source.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Callable, Any, cast, TYPE_CHECKING
import csv

if TYPE_CHECKING:
    import pandas as pd

from core.logging_config import get_logger
from data_processing.database import DatabaseManager, default_db_manager
from data_processing.snowflake_connector import (
    SnowflakeConnector,
    get_connector,
    is_snowflake_available,
    is_snowflake_configured,
    SNOWFLAKE_AVAILABLE,
)
from data_processing.cache import get_cache, is_cache_enabled

logger = get_logger(__name__)


@dataclass
class ClusterSnomedCodes:
    """SNOMED codes for a clinical coding cluster."""
    cluster_id: str
    cluster_description: str
    snomed_codes: list[str] = field(default_factory=list)
    snomed_descriptions: dict[str, str] = field(default_factory=dict)

    @property
    def code_count(self) -> int:
        return len(self.snomed_codes)


@dataclass
class IndicationValidationResult:
    """Result of validating a patient's indication for a drug."""
    patient_pseudonym: str
    drug_name: str
    has_valid_indication: bool
    matched_cluster_id: Optional[str] = None
    matched_snomed_code: Optional[str] = None
    matched_snomed_description: Optional[str] = None
    checked_clusters: list[str] = field(default_factory=list)
    total_codes_checked: int = 0
    source: str = "GP_SNOMED"  # GP_SNOMED | NONE
    error_message: Optional[str] = None


@dataclass
class DrugIndicationMatchRate:
    """Match rate statistics for a drug's indication validation."""
    drug_name: str
    total_patients: int
    patients_with_indication: int
    patients_without_indication: int
    match_rate: float  # 0.0 to 1.0
    clusters_checked: list[str] = field(default_factory=list)
    sample_unmatched: list[str] = field(default_factory=list)  # Sample patient IDs


@dataclass
class DrugSnomedMapping:
    """SNOMED code mapping for a drug from ref_drug_snomed_mapping."""
    snomed_code: str
    snomed_description: str
    search_term: str
    primary_directorate: str
    indication: str = ""
    ta_id: str = ""


@dataclass
class DirectSnomedMatchResult:
    """Result of direct SNOMED code lookup in GP records."""
    patient_pseudonym: str
    matched: bool
    snomed_code: Optional[str] = None
    snomed_description: Optional[str] = None
    search_term: Optional[str] = None
    primary_directorate: Optional[str] = None
    event_date: Optional[datetime] = None
    source: str = "DIRECT_SNOMED"  # DIRECT_SNOMED | NONE


@dataclass
class DirectorateAssignment:
    """Result of directorate assignment for a patient-drug combination."""
    upid: str
    drug_name: str
    directorate: Optional[str]
    search_term: Optional[str] = None
    source: str = "FALLBACK"  # DIAGNOSIS | FALLBACK
    snomed_code: Optional[str] = None
    event_date: Optional[datetime] = None


def get_drug_clusters(
    drug_name: str,
    db_manager: Optional[DatabaseManager] = None
) -> list[dict]:
    """
    Get all SNOMED cluster mappings for a drug from local SQLite.

    Args:
        drug_name: Drug name to look up (case-insensitive)
        db_manager: Optional DatabaseManager (defaults to default_db_manager)

    Returns:
        List of dicts with keys: drug_name, indication, cluster_id,
        cluster_description, nice_ta_reference
    """
    if db_manager is None:
        db_manager = default_db_manager

    query = """
        SELECT drug_name, indication, cluster_id, cluster_description, nice_ta_reference
        FROM ref_drug_indication_clusters
        WHERE UPPER(drug_name) = UPPER(?)
        ORDER BY indication, cluster_id
    """

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.execute(query, (drug_name,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append({
                    "drug_name": row["drug_name"],
                    "indication": row["indication"],
                    "cluster_id": row["cluster_id"],
                    "cluster_description": row["cluster_description"],
                    "nice_ta_reference": row["nice_ta_reference"],
                })

            logger.debug(f"Found {len(results)} cluster mappings for drug '{drug_name}'")
            return results

    except Exception as e:
        logger.error(f"Error getting clusters for drug '{drug_name}': {e}")
        return []


def get_drug_cluster_ids(
    drug_name: str,
    db_manager: Optional[DatabaseManager] = None
) -> list[str]:
    """
    Get unique cluster IDs for a drug.

    Args:
        drug_name: Drug name to look up
        db_manager: Optional DatabaseManager

    Returns:
        List of unique cluster IDs
    """
    clusters = get_drug_clusters(drug_name, db_manager)
    return list(set(c["cluster_id"] for c in clusters))


def get_drug_snomed_codes(
    drug_name: str,
    db_manager: Optional[DatabaseManager] = None
) -> list[DrugSnomedMapping]:
    """
    Get all SNOMED codes for a drug from local ref_drug_snomed_mapping table.

    This uses the enriched mapping CSV data loaded into SQLite, which provides
    direct SNOMED-to-drug mappings with Search_Term and PrimaryDirectorate.

    Args:
        drug_name: Drug name to look up (case-insensitive, matches cleaned_drug_name)
        db_manager: Optional DatabaseManager (defaults to default_db_manager)

    Returns:
        List of DrugSnomedMapping with snomed_code, snomed_description,
        search_term, primary_directorate, indication, ta_id
    """
    if db_manager is None:
        db_manager = default_db_manager

    query = """
        SELECT DISTINCT
            snomed_code,
            snomed_description,
            search_term,
            primary_directorate,
            indication,
            ta_id
        FROM ref_drug_snomed_mapping
        WHERE UPPER(cleaned_drug_name) = UPPER(?)
           OR UPPER(drug_name) = UPPER(?)
        ORDER BY search_term, snomed_code
    """

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.execute(query, (drug_name, drug_name))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(DrugSnomedMapping(
                    snomed_code=row["snomed_code"],
                    snomed_description=row["snomed_description"] or "",
                    search_term=row["search_term"] or "",
                    primary_directorate=row["primary_directorate"] or "",
                    indication=row["indication"] or "",
                    ta_id=row["ta_id"] or "",
                ))

            logger.debug(f"Found {len(results)} SNOMED mappings for drug '{drug_name}'")
            return results

    except Exception as e:
        logger.error(f"Error getting SNOMED codes for drug '{drug_name}': {e}")
        return []


def patient_has_indication_direct(
    patient_pseudonym: str,
    drug_snomed_mappings: list[DrugSnomedMapping],
    connector: Optional[SnowflakeConnector] = None,
    before_date: Optional[date] = None,
) -> DirectSnomedMatchResult:
    """
    Check if patient has any of the SNOMED codes in their GP records.

    This is the direct SNOMED lookup - it queries PrimaryCareClinicalCoding
    for exact SNOMED code matches (not via cluster). Returns the most recent
    match by EventDateTime if multiple matches exist.

    Args:
        patient_pseudonym: Patient's pseudonymised NHS number
        drug_snomed_mappings: List of DrugSnomedMapping from get_drug_snomed_codes()
        connector: Optional SnowflakeConnector (defaults to singleton)
        before_date: Optional date - only check diagnoses before this date

    Returns:
        DirectSnomedMatchResult with match details (most recent by EventDateTime)
    """
    result = DirectSnomedMatchResult(
        patient_pseudonym=patient_pseudonym,
        matched=False,
        source="NONE",
    )

    if not drug_snomed_mappings:
        return result

    if not SNOWFLAKE_AVAILABLE:
        logger.warning("Snowflake connector not available")
        return result

    if not is_snowflake_configured():
        logger.warning("Snowflake not configured - cannot check GP records")
        return result

    if connector is None:
        connector = get_connector()

    # Build lookup dict for mapping snomed_code -> (search_term, primary_directorate, snomed_description)
    snomed_lookup = {
        m.snomed_code: (m.search_term, m.primary_directorate, m.snomed_description)
        for m in drug_snomed_mappings
    }

    # Get unique SNOMED codes
    snomed_codes = list(snomed_lookup.keys())

    # Build placeholders for SNOMED codes
    placeholders = ", ".join(["%s"] * len(snomed_codes))

    # Query to find most recent matching SNOMED code in GP records
    query = f'''
        SELECT
            "SNOMEDCode",
            "EventDateTime"
        FROM DATA_HUB.PHM."PrimaryCareClinicalCoding"
        WHERE "PatientPseudonym" = %s
            AND "SNOMEDCode" IN ({placeholders})
    '''

    params: list = [patient_pseudonym] + snomed_codes

    if before_date:
        query += ' AND "EventDateTime" < %s'
        params.append(before_date.isoformat())

    query += ' ORDER BY "EventDateTime" DESC LIMIT 1'

    try:
        results = connector.execute_dict(query, tuple(params))

        if results:
            row = results[0]
            matched_code = row.get("SNOMEDCode")
            event_dt = row.get("EventDateTime")

            if matched_code and matched_code in snomed_lookup:
                search_term, primary_dir, snomed_desc = snomed_lookup[matched_code]

                return DirectSnomedMatchResult(
                    patient_pseudonym=patient_pseudonym,
                    matched=True,
                    snomed_code=matched_code,
                    snomed_description=snomed_desc,
                    search_term=search_term,
                    primary_directorate=primary_dir,
                    event_date=event_dt,
                    source="DIRECT_SNOMED",
                )

        return result

    except Exception as e:
        logger.error(f"Error checking direct SNOMED for patient '{patient_pseudonym}': {e}")
        return result


def get_directorate_from_diagnosis(
    upid: str,
    drug_name: str,
    connector: Optional[SnowflakeConnector] = None,
    db_manager: Optional[DatabaseManager] = None,
    before_date: Optional[date] = None,
) -> DirectorateAssignment:
    """
    Get directorate assignment for a patient-drug combination using diagnosis-based lookup.

    This function attempts to assign a directorate based on the patient's GP records
    (direct SNOMED code matching). If no match is found, it returns a FALLBACK result
    indicating that the caller should use alternative assignment methods (e.g.,
    department_identification() from tools/data.py).

    Workflow:
    1. Get all SNOMED codes for the drug from ref_drug_snomed_mapping
    2. Query patient's GP records for matching SNOMED codes
    3. If match found → return diagnosis-based directorate and search_term
    4. If no match → return FALLBACK result (caller handles fallback logic)

    Args:
        upid: Patient's unique patient ID (Provider Code[:3] + PersonKey)
        drug_name: Drug name to look up
        connector: Optional SnowflakeConnector (defaults to singleton)
        db_manager: Optional DatabaseManager (defaults to default_db_manager)
        before_date: Optional date - only check diagnoses before this date

    Returns:
        DirectorateAssignment with directorate, search_term, and source
    """
    result = DirectorateAssignment(
        upid=upid,
        drug_name=drug_name,
        directorate=None,
        source="FALLBACK",
    )

    # Step 1: Get SNOMED codes for the drug
    drug_snomed_mappings = get_drug_snomed_codes(drug_name, db_manager)

    if not drug_snomed_mappings:
        logger.debug(f"No SNOMED mappings found for drug '{drug_name}' - using fallback")
        return result

    # Step 2: Check Snowflake availability
    if not SNOWFLAKE_AVAILABLE:
        logger.debug("Snowflake not available - using fallback")
        return result

    if not is_snowflake_configured():
        logger.debug("Snowflake not configured - using fallback")
        return result

    # Step 3: Get patient pseudonym from UPID
    # UPID format is Provider Code (3 chars) + PersonKey
    # We need to query Snowflake to get the PatientPseudonym for this PersonKey
    # However, patient_has_indication_direct expects PatientPseudonym, not UPID
    # For now, we'll use UPID as the identifier - the actual integration
    # will need to happen at the DataFrame level where we have PersonKey
    #
    # NOTE: This function will be called from the pipeline where we have
    # access to PatientPseudonym. The UPID is passed for logging/tracking.

    # Actually, looking at the pipeline, we need PatientPseudonym, not UPID.
    # The caller should pass the PatientPseudonym or we need to look it up.
    # For now, let's assume the caller will use this in a batch context
    # where they can map UPID -> PatientPseudonym.

    # Let me reconsider: the function signature takes UPID but we need
    # PatientPseudonym for Snowflake. In the pipeline context (fetch_and_transform_data),
    # we'll have the PersonKey column which IS the PatientPseudonym.
    # So UPID = ProviderCode[:3] + PersonKey, and PersonKey = PatientPseudonym.
    #
    # We can extract PatientPseudonym from UPID by removing the first 3 chars.
    patient_pseudonym = upid[3:] if len(upid) > 3 else upid

    # Step 4: Check patient's GP records for matching SNOMED codes
    match_result = patient_has_indication_direct(
        patient_pseudonym=patient_pseudonym,
        drug_snomed_mappings=drug_snomed_mappings,
        connector=connector,
        before_date=before_date,
    )

    if match_result.matched and match_result.primary_directorate:
        return DirectorateAssignment(
            upid=upid,
            drug_name=drug_name,
            directorate=match_result.primary_directorate,
            search_term=match_result.search_term,
            source="DIAGNOSIS",
            snomed_code=match_result.snomed_code,
            event_date=match_result.event_date,
        )

    # No match found - return fallback result
    return result


def get_cluster_snomed_codes(
    cluster_id: str,
    connector: Optional[SnowflakeConnector] = None,
    use_cache: bool = True,
) -> ClusterSnomedCodes:
    """
    Get all SNOMED codes for a cluster from Snowflake.

    Queries the ClinicalCodingClusterSnomedCodes table to get all SNOMED codes
    that belong to the specified cluster.

    Args:
        cluster_id: Cluster ID to look up (e.g., 'RARTH_COD', 'PSORIASIS_COD')
        connector: Optional SnowflakeConnector (defaults to singleton)
        use_cache: Whether to use cached results (default True)

    Returns:
        ClusterSnomedCodes with list of SNOMED codes and descriptions
    """
    if not SNOWFLAKE_AVAILABLE:
        logger.warning("Snowflake connector not available")
        return ClusterSnomedCodes(cluster_id=cluster_id, cluster_description="")

    if not is_snowflake_configured():
        logger.warning("Snowflake not configured - cannot get cluster codes")
        return ClusterSnomedCodes(cluster_id=cluster_id, cluster_description="")

    # Check cache first
    cache_key = f"cluster_snomed_{cluster_id}"
    if use_cache and is_cache_enabled():
        cache = get_cache()
        cached = cache.get(cache_key)
        if cached is not None and len(cached) > 0:
            logger.debug(f"Using cached SNOMED codes for cluster '{cluster_id}'")
            cached_dict = cached[0]  # First element is our data dict
            return ClusterSnomedCodes(
                cluster_id=cluster_id,
                cluster_description=str(cached_dict.get("description", "")),
                snomed_codes=list(cached_dict.get("codes", [])),
                snomed_descriptions=dict(cached_dict.get("descriptions", {})),
            )

    if connector is None:
        connector = get_connector()

    query = '''
        SELECT DISTINCT
            "Cluster_ID",
            "Cluster_Description",
            "SNOMEDCode",
            "SNOMEDDescription"
        FROM DATA_HUB.PHM."ClinicalCodingClusterSnomedCodes"
        WHERE "Cluster_ID" = %s
        ORDER BY "SNOMEDCode"
    '''

    try:
        results = connector.execute_dict(query, (cluster_id,))

        if not results:
            logger.warning(f"No SNOMED codes found for cluster '{cluster_id}'")
            return ClusterSnomedCodes(cluster_id=cluster_id, cluster_description="")

        codes = []
        descriptions = {}
        description = results[0].get("Cluster_Description", "") if results else ""

        for row in results:
            code = row.get("SNOMEDCode")
            if code:
                codes.append(code)
                descriptions[code] = row.get("SNOMEDDescription", "")

        logger.info(f"Found {len(codes)} SNOMED codes for cluster '{cluster_id}'")

        # Cache the results (using query-based cache with fake params)
        if use_cache and is_cache_enabled():
            cache = get_cache()
            cache_data = [{
                "description": description,
                "codes": codes,
                "descriptions": descriptions,
            }]
            cache.set(cache_key, None, cache_data)  # type: ignore[arg-type]

        return ClusterSnomedCodes(
            cluster_id=cluster_id,
            cluster_description=description,
            snomed_codes=codes,
            snomed_descriptions=descriptions,
        )

    except Exception as e:
        logger.error(f"Error getting SNOMED codes for cluster '{cluster_id}': {e}")
        return ClusterSnomedCodes(cluster_id=cluster_id, cluster_description="")


def patient_has_indication(
    patient_pseudonym: str,
    cluster_ids: list[str],
    connector: Optional[SnowflakeConnector] = None,
    before_date: Optional[date] = None,
) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Check if a patient has any SNOMED codes from the specified clusters in GP records.

    Args:
        patient_pseudonym: Patient's pseudonymised NHS number
        cluster_ids: List of cluster IDs to check against
        connector: Optional SnowflakeConnector
        before_date: Optional date - only check diagnoses before this date

    Returns:
        Tuple of (has_indication, matched_cluster_id, matched_snomed_code, matched_description)
    """
    if not SNOWFLAKE_AVAILABLE or not is_snowflake_configured():
        return False, None, None, None

    if not cluster_ids:
        return False, None, None, None

    if connector is None:
        connector = get_connector()

    # Build placeholders for cluster IDs
    placeholders = ", ".join(["%s"] * len(cluster_ids))

    # Query to check if patient has any matching SNOMED code
    query = f'''
        SELECT
            pc."SNOMEDCode",
            cc."Cluster_ID",
            cc."SNOMEDDescription"
        FROM DATA_HUB.PHM."PrimaryCareClinicalCoding" pc
        INNER JOIN DATA_HUB.PHM."ClinicalCodingClusterSnomedCodes" cc
            ON pc."SNOMEDCode" = cc."SNOMEDCode"
        WHERE pc."PatientPseudonym" = %s
            AND cc."Cluster_ID" IN ({placeholders})
    '''

    params = [patient_pseudonym] + cluster_ids

    if before_date:
        query += ' AND pc."EventDateTime" < %s'
        params.append(before_date.isoformat())

    query += ' LIMIT 1'

    try:
        results = connector.execute_dict(query, tuple(params))

        if results:
            row = results[0]
            return (
                True,
                row.get("Cluster_ID"),
                row.get("SNOMEDCode"),
                row.get("SNOMEDDescription"),
            )

        return False, None, None, None

    except Exception as e:
        logger.error(f"Error checking indication for patient '{patient_pseudonym}': {e}")
        return False, None, None, None


def validate_indication(
    patient_pseudonym: str,
    drug_name: str,
    connector: Optional[SnowflakeConnector] = None,
    db_manager: Optional[DatabaseManager] = None,
    before_date: Optional[date] = None,
) -> IndicationValidationResult:
    """
    Validate that a patient has an appropriate indication for a drug.

    Full validation workflow:
    1. Get drug's valid indication clusters from local mapping
    2. Check if patient has any matching SNOMED codes in GP records
    3. Return detailed validation result

    Args:
        patient_pseudonym: Patient's pseudonymised NHS number
        drug_name: Drug name to validate indication for
        connector: Optional SnowflakeConnector
        db_manager: Optional DatabaseManager
        before_date: Optional date - only check diagnoses before this date

    Returns:
        IndicationValidationResult with validation details
    """
    result = IndicationValidationResult(
        patient_pseudonym=patient_pseudonym,
        drug_name=drug_name,
        has_valid_indication=False,
    )

    # Step 1: Get drug's cluster mappings
    cluster_ids = get_drug_cluster_ids(drug_name, db_manager)

    if not cluster_ids:
        result.error_message = f"No cluster mappings found for drug '{drug_name}'"
        result.source = "NONE"
        return result

    result.checked_clusters = cluster_ids

    # Step 2: Check Snowflake availability
    if not SNOWFLAKE_AVAILABLE:
        result.error_message = "Snowflake connector not installed"
        result.source = "NONE"
        return result

    if not is_snowflake_configured():
        result.error_message = "Snowflake not configured"
        result.source = "NONE"
        return result

    # Step 3: Check patient GP records
    has_indication, matched_cluster, matched_code, matched_desc = patient_has_indication(
        patient_pseudonym=patient_pseudonym,
        cluster_ids=cluster_ids,
        connector=connector,
        before_date=before_date,
    )

    result.has_valid_indication = has_indication
    result.matched_cluster_id = matched_cluster
    result.matched_snomed_code = matched_code
    result.matched_snomed_description = matched_desc
    result.source = "GP_SNOMED" if has_indication else "NONE"

    return result


def get_indication_match_rate(
    drug_name: str,
    patient_pseudonyms: list[str],
    connector: Optional[SnowflakeConnector] = None,
    db_manager: Optional[DatabaseManager] = None,
    sample_unmatched_count: int = 10,
) -> DrugIndicationMatchRate:
    """
    Calculate indication match rate for a drug across a list of patients.

    Args:
        drug_name: Drug name to check
        patient_pseudonyms: List of patient pseudonymised NHS numbers
        connector: Optional SnowflakeConnector
        db_manager: Optional DatabaseManager
        sample_unmatched_count: Number of unmatched patient IDs to include in sample

    Returns:
        DrugIndicationMatchRate with match statistics
    """
    if connector is None and SNOWFLAKE_AVAILABLE and is_snowflake_configured():
        connector = get_connector()

    cluster_ids = get_drug_cluster_ids(drug_name, db_manager)

    total = len(patient_pseudonyms)
    matched = 0
    unmatched = 0
    sample_unmatched: list[str] = []

    if not cluster_ids:
        logger.warning(f"No cluster mappings for drug '{drug_name}' - all patients will be unmatched")
        return DrugIndicationMatchRate(
            drug_name=drug_name,
            total_patients=total,
            patients_with_indication=0,
            patients_without_indication=total,
            match_rate=0.0,
            clusters_checked=[],
            sample_unmatched=patient_pseudonyms[:sample_unmatched_count],
        )

    for i, pseudonym in enumerate(patient_pseudonyms):
        if i > 0 and i % 100 == 0:
            logger.info(f"Validating indications: {i}/{total} ({100*i/total:.1f}%)")

        has_indication, _, _, _ = patient_has_indication(
            patient_pseudonym=pseudonym,
            cluster_ids=cluster_ids,
            connector=connector,
        )

        if has_indication:
            matched += 1
        else:
            unmatched += 1
            if len(sample_unmatched) < sample_unmatched_count:
                sample_unmatched.append(pseudonym)

    match_rate = matched / total if total > 0 else 0.0

    logger.info(f"Indication match rate for '{drug_name}': {100*match_rate:.1f}% ({matched}/{total})")

    return DrugIndicationMatchRate(
        drug_name=drug_name,
        total_patients=total,
        patients_with_indication=matched,
        patients_without_indication=unmatched,
        match_rate=match_rate,
        clusters_checked=cluster_ids,
        sample_unmatched=sample_unmatched,
    )


def batch_validate_indications(
    patient_drug_pairs: list[tuple[str, str]],
    connector: Optional[SnowflakeConnector] = None,
    db_manager: Optional[DatabaseManager] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[IndicationValidationResult]:
    """
    Validate indications for multiple patient-drug pairs efficiently.

    Args:
        patient_drug_pairs: List of (patient_pseudonym, drug_name) tuples
        connector: Optional SnowflakeConnector
        db_manager: Optional DatabaseManager
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        List of IndicationValidationResult for each pair
    """
    results = []
    total = len(patient_drug_pairs)

    # Cache cluster lookups by drug
    drug_clusters_cache = {}

    for i, (pseudonym, drug_name) in enumerate(patient_drug_pairs):
        if progress_callback:
            progress_callback(i + 1, total)

        # Get clusters from cache or lookup
        drug_upper = drug_name.upper()
        if drug_upper not in drug_clusters_cache:
            drug_clusters_cache[drug_upper] = get_drug_cluster_ids(drug_name, db_manager)

        cluster_ids = drug_clusters_cache[drug_upper]

        if not cluster_ids:
            results.append(IndicationValidationResult(
                patient_pseudonym=pseudonym,
                drug_name=drug_name,
                has_valid_indication=False,
                source="NONE",
                error_message=f"No cluster mappings for drug '{drug_name}'",
            ))
            continue

        # Check patient indication
        has_indication, matched_cluster, matched_code, matched_desc = patient_has_indication(
            patient_pseudonym=pseudonym,
            cluster_ids=cluster_ids,
            connector=connector,
        )

        results.append(IndicationValidationResult(
            patient_pseudonym=pseudonym,
            drug_name=drug_name,
            has_valid_indication=has_indication,
            matched_cluster_id=matched_cluster,
            matched_snomed_code=matched_code,
            matched_snomed_description=matched_desc,
            checked_clusters=cluster_ids,
            source="GP_SNOMED" if has_indication else "NONE",
        ))

    matched_count = sum(1 for r in results if r.has_valid_indication)
    logger.info(f"Batch validation complete: {matched_count}/{total} ({100*matched_count/total:.1f}%) with valid indications")

    return results


def get_available_clusters(
    connector: Optional[SnowflakeConnector] = None,
) -> list[dict]:
    """
    Get list of all available SNOMED clusters from Snowflake.

    Returns:
        List of dicts with cluster_id, cluster_description, code_count
    """
    if not SNOWFLAKE_AVAILABLE or not is_snowflake_configured():
        logger.warning("Snowflake not available - cannot list clusters")
        return []

    if connector is None:
        connector = get_connector()

    query = '''
        SELECT
            "Cluster_ID",
            "Cluster_Description",
            COUNT(DISTINCT "SNOMEDCode") as code_count
        FROM DATA_HUB.PHM."ClinicalCodingClusterSnomedCodes"
        GROUP BY "Cluster_ID", "Cluster_Description"
        ORDER BY "Cluster_ID"
    '''

    try:
        results = connector.execute_dict(query)

        clusters = []
        for row in results:
            clusters.append({
                "cluster_id": row.get("Cluster_ID"),
                "cluster_description": row.get("Cluster_Description"),
                "code_count": row.get("code_count", 0),
            })

        logger.info(f"Found {len(clusters)} available SNOMED clusters")
        return clusters

    except Exception as e:
        logger.error(f"Error getting available clusters: {e}")
        return []


def batch_lookup_indication_groups(
    df: "pd.DataFrame",
    connector: Optional[SnowflakeConnector] = None,
    db_manager: Optional[DatabaseManager] = None,
    batch_size: int = 500,
) -> "pd.DataFrame":
    """
    Batch lookup GP diagnosis-based indication groups for a DataFrame of patients.

    This is the efficient batch version of get_directorate_from_diagnosis().
    Instead of querying Snowflake per patient, it batches the lookups for performance.

    Strategy:
    1. Get all unique (PersonKey, Drug Name) pairs from DataFrame
    2. For each unique drug, get all SNOMED codes from local SQLite
    3. Build batched Snowflake queries to check GP records
    4. Return indication_df mapping UPID → Indication_Group

    For unmatched patients, Indication_Group will be their Directory (with suffix).

    Args:
        df: DataFrame with columns: UPID, Drug Name, Directory, PersonKey
        connector: Optional SnowflakeConnector (defaults to singleton)
        db_manager: Optional DatabaseManager (defaults to default_db_manager)
        batch_size: Number of patients per Snowflake query batch

    Returns:
        DataFrame with columns: UPID, Indication_Group, Source
        - Indication_Group: Search_Term (if matched) or "Directory (no GP dx)" (if not)
        - Source: "DIAGNOSIS" or "FALLBACK"
    """
    import pandas as pd

    if db_manager is None:
        db_manager = default_db_manager

    logger.info(f"Starting batch indication lookup for {len(df)} records...")

    # Step 1: Get unique (UPID, Drug Name, PseudoNHSNoLinked, Directory) combinations
    # We need PseudoNHSNoLinked to query Snowflake - this matches PatientPseudonym in GP records
    # Note: PersonKey is LocalPatientID which is provider-specific and does NOT match GP records
    if 'PseudoNHSNoLinked' not in df.columns:
        logger.error("DataFrame missing 'PseudoNHSNoLinked' column - cannot lookup GP records")
        # Return fallback for all patients
        result_df = df[['UPID', 'Directory']].drop_duplicates().copy()
        result_df['Indication_Group'] = result_df['Directory'] + " (no GP dx)"
        result_df['Source'] = "FALLBACK"
        return result_df[['UPID', 'Indication_Group', 'Source']]

    # Get unique patient-drug combinations (we need one lookup per patient-drug pair)
    unique_pairs = df[['UPID', 'Drug Name', 'PseudoNHSNoLinked', 'Directory']].drop_duplicates()
    logger.info(f"Found {len(unique_pairs)} unique patient-drug combinations")

    # Step 2: Get all unique drugs and their SNOMED codes
    unique_drugs = unique_pairs['Drug Name'].unique()
    logger.info(f"Building SNOMED lookup for {len(unique_drugs)} unique drugs...")

    # Build drug -> list of DrugSnomedMapping dict
    drug_snomed_map: dict[str, list[DrugSnomedMapping]] = {}
    all_snomed_codes: set[str] = set()
    snomed_to_drug_searchterm: dict[str, list[tuple[str, str, str]]] = {}  # snomed -> [(drug, search_term, primary_dir), ...]

    for drug_name in unique_drugs:
        mappings = get_drug_snomed_codes(drug_name, db_manager)
        drug_snomed_map[drug_name] = mappings

        for m in mappings:
            all_snomed_codes.add(m.snomed_code)
            if m.snomed_code not in snomed_to_drug_searchterm:
                snomed_to_drug_searchterm[m.snomed_code] = []
            snomed_to_drug_searchterm[m.snomed_code].append(
                (drug_name, m.search_term, m.primary_directorate)
            )

    logger.info(f"Total SNOMED codes to check: {len(all_snomed_codes)}")

    # Step 3: Check Snowflake availability
    if not SNOWFLAKE_AVAILABLE or not is_snowflake_configured():
        logger.warning("Snowflake not available - returning fallback for all patients")
        result_df = unique_pairs[['UPID', 'Directory']].copy()
        result_df['Indication_Group'] = result_df['Directory'] + " (no GP dx)"
        result_df['Source'] = "FALLBACK"
        return result_df[['UPID', 'Indication_Group', 'Source']].drop_duplicates(subset=['UPID'])

    if connector is None:
        connector = get_connector()

    # Step 4: Query GP records for all patients in batches
    # The query finds the most recent matching SNOMED code for each patient

    # Get unique PseudoNHSNoLinked values (each = one patient in GP records)
    unique_patients = unique_pairs[['PseudoNHSNoLinked', 'UPID', 'Directory']].drop_duplicates(subset=['PseudoNHSNoLinked'])
    patient_pseudonyms = unique_patients['PseudoNHSNoLinked'].tolist()

    logger.info(f"Querying GP records for {len(patient_pseudonyms)} unique patients in batches of {batch_size}...")

    # Results dict: PersonKey -> (snomed_code, event_date)
    gp_matches: dict[str, tuple[str, Any]] = {}

    # Convert SNOMED codes to list for query
    snomed_list = list(all_snomed_codes)

    if not snomed_list:
        logger.warning("No SNOMED codes to check - returning fallback for all patients")
        result_df = unique_pairs[['UPID', 'Directory']].copy()
        result_df['Indication_Group'] = result_df['Directory'] + " (no GP dx)"
        result_df['Source'] = "FALLBACK"
        return result_df[['UPID', 'Indication_Group', 'Source']].drop_duplicates(subset=['UPID'])

    # Build SNOMED IN clause (reused across batches)
    snomed_placeholders = ", ".join(["%s"] * len(snomed_list))

    # Process patients in batches
    for batch_start in range(0, len(patient_pseudonyms), batch_size):
        batch_end = min(batch_start + batch_size, len(patient_pseudonyms))
        batch_pseudonyms = patient_pseudonyms[batch_start:batch_end]

        logger.info(f"Batch {batch_start//batch_size + 1}: patients {batch_start} to {batch_end}")

        # Build patient IN clause
        patient_placeholders = ", ".join(["%s"] * len(batch_pseudonyms))

        # Query to find all matching SNOMED codes for these patients
        # We'll get all matches and pick the most recent per patient in Python
        query = f'''
            SELECT
                "PatientPseudonym",
                "SNOMEDCode",
                "EventDateTime"
            FROM DATA_HUB.PHM."PrimaryCareClinicalCoding"
            WHERE "PatientPseudonym" IN ({patient_placeholders})
              AND "SNOMEDCode" IN ({snomed_placeholders})
            ORDER BY "PatientPseudonym", "EventDateTime" DESC
        '''

        params = tuple(batch_pseudonyms) + tuple(snomed_list)

        try:
            results = connector.execute_dict(query, params)

            # Process results - pick most recent per patient
            for row in results:
                person_key = row.get("PatientPseudonym")
                snomed_code = row.get("SNOMEDCode")
                event_date = row.get("EventDateTime")

                if person_key and snomed_code:
                    # Keep only if we haven't seen this patient yet (first = most recent due to ORDER BY)
                    if person_key not in gp_matches:
                        gp_matches[person_key] = (snomed_code, event_date)

        except Exception as e:
            logger.error(f"Error querying GP records for batch: {e}")
            # Continue with other batches

    logger.info(f"Found GP matches for {len(gp_matches)} patients")

    # Step 5: Build result DataFrame
    # For each unique_pair, determine Indication_Group based on match status
    results_list = []

    # We need to dedupe by UPID - a patient might be on multiple drugs
    # Strategy: For each UPID, use the most recent match (if any)
    upid_to_match: dict[str, tuple[str, str]] = {}  # UPID -> (Indication_Group, Source)

    for _, row in unique_pairs.iterrows():
        upid = row['UPID']
        drug_name = row['Drug Name']
        patient_pseudonym = row['PseudoNHSNoLinked']
        directory = row['Directory']

        # Check if patient has GP match (using PseudoNHSNoLinked which matches PatientPseudonym in GP)
        if patient_pseudonym in gp_matches:
            matched_snomed, event_date = gp_matches[patient_pseudonym]

            # Find the search_term for this SNOMED code and drug
            # (A SNOMED code might map to multiple drugs with different search_terms)
            if matched_snomed in snomed_to_drug_searchterm:
                # Look for match with current drug first
                search_term = None
                for drug, st, pd in snomed_to_drug_searchterm[matched_snomed]:
                    if drug.upper() == drug_name.upper():
                        search_term = st
                        break
                # If no drug-specific match, use any match
                if search_term is None:
                    search_term = snomed_to_drug_searchterm[matched_snomed][0][1]

                # Only update if we don't have a match for this UPID yet
                if upid not in upid_to_match:
                    upid_to_match[upid] = (search_term, "DIAGNOSIS")
            else:
                # Shouldn't happen but fallback just in case
                if upid not in upid_to_match:
                    upid_to_match[upid] = (directory + " (no GP dx)", "FALLBACK")
        else:
            # No GP match - use fallback
            if upid not in upid_to_match:
                upid_to_match[upid] = (directory + " (no GP dx)", "FALLBACK")

    # Build result DataFrame
    for upid, (indication_group, source) in upid_to_match.items():
        results_list.append({
            'UPID': upid,
            'Indication_Group': indication_group,
            'Source': source,
        })

    result_df = pd.DataFrame(results_list)

    # Log statistics
    diagnosis_count = len([s for s in result_df['Source'] if s == "DIAGNOSIS"])
    fallback_count = len([s for s in result_df['Source'] if s == "FALLBACK"])
    total = len(result_df)

    logger.info(f"Indication lookup complete:")
    logger.info(f"  Total unique patients: {total}")
    logger.info(f"  DIAGNOSIS matches: {diagnosis_count} ({100*diagnosis_count/total:.1f}%)")
    logger.info(f"  FALLBACK (no GP match): {fallback_count} ({100*fallback_count/total:.1f}%)")

    return result_df


# === Drug-to-indication mapping from DimSearchTerm.csv ===


def load_drug_indication_mapping(
    csv_path: Optional[str] = None,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Load the drug-to-Search_Term mapping from DimSearchTerm.csv.

    Builds two lookup dicts:
    - fragment_to_search_terms: drug fragment (UPPERCASE) -> list of Search_Terms containing it
    - search_term_to_fragments: search_term -> list of drug fragments (UPPERCASE)

    DimSearchTerm.csv has columns: Search_Term, CleanedDrugName, PrimaryDirectorate
    CleanedDrugName is pipe-separated (e.g., "ADALIMUMAB|GOLIMUMAB|IXEKIZUMAB").

    Note: A Search_Term can appear multiple times with different PrimaryDirectorates
    (e.g., "diabetes" appears under both DIABETIC MEDICINE and OPHTHALMOLOGY).
    Drug fragments from all rows for the same Search_Term are combined.

    Args:
        csv_path: Path to DimSearchTerm.csv. Defaults to data/DimSearchTerm.csv.

    Returns:
        Tuple of (fragment_to_search_terms, search_term_to_fragments)
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "data" / "DimSearchTerm.csv")

    fragment_to_search_terms: dict[str, list[str]] = {}
    search_term_to_fragments: dict[str, list[str]] = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                search_term = row.get("Search_Term", "").strip()
                drug_names_raw = row.get("CleanedDrugName", "").strip()

                if not search_term or not drug_names_raw:
                    continue

                fragments = [frag.strip().upper() for frag in drug_names_raw.split("|") if frag.strip()]

                # Build search_term -> fragments (accumulate for duplicate Search_Terms)
                if search_term not in search_term_to_fragments:
                    search_term_to_fragments[search_term] = []
                for frag in fragments:
                    if frag not in search_term_to_fragments[search_term]:
                        search_term_to_fragments[search_term].append(frag)

                # Build fragment -> search_terms
                for frag in fragments:
                    if frag not in fragment_to_search_terms:
                        fragment_to_search_terms[frag] = []
                    if search_term not in fragment_to_search_terms[frag]:
                        fragment_to_search_terms[frag].append(search_term)

        logger.info(
            f"Loaded drug-indication mapping: {len(search_term_to_fragments)} Search_Terms, "
            f"{len(fragment_to_search_terms)} drug fragments"
        )

    except FileNotFoundError:
        logger.error(f"DimSearchTerm.csv not found at {csv_path}")
    except Exception as e:
        logger.error(f"Error loading DimSearchTerm.csv: {e}")

    return fragment_to_search_terms, search_term_to_fragments


def get_search_terms_for_drug(
    drug_name: str,
    search_term_to_fragments: dict[str, list[str]],
) -> list[str]:
    """
    Get all Search_Terms that list a given drug using substring matching.

    Checks if any drug fragment from DimSearchTerm is a SUBSTRING of the given
    drug name (case-insensitive). This handles both exact matches (ADALIMUMAB)
    and partial fragments (PEGYLATED, INHALED).

    Args:
        drug_name: HCD drug name (e.g., "ADALIMUMAB 40MG", "PEGYLATED LIPOSOMAL DOXORUBICIN")
        search_term_to_fragments: Mapping of search_term -> list of drug fragments

    Returns:
        List of Search_Terms whose drug fragments match the drug name
    """
    drug_name_upper = drug_name.upper()
    matched_terms: list[str] = []

    for search_term, fragments in search_term_to_fragments.items():
        for frag in fragments:
            if frag in drug_name_upper:
                matched_terms.append(search_term)
                break  # One matching fragment is enough for this Search_Term

    return matched_terms


# === NEW APPROACH: Query Snowflake directly using cluster CTE ===

# The cluster query mapping (embedded from snomed_indication_mapping_query.sql)
# This maps Search_Term -> Cluster_ID for ~148 clinical conditions
CLUSTER_MAPPING_SQL = """
WITH SearchTermClusters AS (
    SELECT Search_Term, Cluster_ID FROM (VALUES
        ('acute lymphoblastic leukaemia', 'HAEMCANMORPH_COD'),
        ('acute myeloid leukaemia', 'C19HAEMCAN_COD'),
        ('acute promyelocytic leukaemia', 'HAEMCANMORPH_COD'),
        ('allergic asthma', 'AST_COD'),
        ('allergic rhinitis', 'MILDINTAST_COD'),
        ('alzheimer''s disease', 'DEMALZ_COD'),
        ('amyloidosis', 'AMYLOID_COD'),
        ('anaemia', 'eFI2_AnaemiaTimeSensitive'),
        ('anaplastic large cell lymphoma', 'C19HAEMCAN_COD'),
        ('apixaban', 'DOACCON_COD'),
        ('aplastic anaemia', 'eFI2_AnaemiaEver'),
        ('arthritis', 'eFI2_InflammatoryArthritis'),
        ('asthma', 'eFI2_Asthma'),
        ('atopic dermatitis', 'ATOPDERM_COD'),
        ('atrial fibrillation', 'eFI2_AtrialFibrillation'),
        ('attention deficit hyperactivity disorder', 'ADHD_COD'),
        ('bipolar disorder', 'MH_COD'),
        ('bladder', 'eFI2_UrinaryIncontinence'),
        ('breast cancer', 'BRCANSCR_COD'),
        ('cardiomyopathy', 'eFI2_HarmfulDrinking'),
        ('cardiovascular disease', 'CVDRISKASS_COD'),
        ('cervical cancer', 'CSDEC_COD'),
        ('cholangiocarcinoma', 'eFI2_Cancer'),
        ('chronic kidney disease', 'CKD_COD'),
        ('chronic liver disease', 'eFI2_LiverProblems'),
        ('chronic lymphocytic leukaemia', 'EPPHAEMCAN_COD'),
        ('chronic myeloid leukaemia', 'EPPHAEMCAN_COD'),
        ('chronic obstructive pulmonary disease', 'eFI2_COPD'),
        ('colon cancer', 'eFI2_Cancer'),
        ('colorectal cancer', 'GICANREF_COD'),
        ('constipation', 'CHRONCONSTIP_COD'),
        ('covid-19', 'POSSPOSTCOVID_COD'),
        ('crohn''s disease', 'eFI2_InflammatoryBowelDisease'),
        ('cutaneous t-cell lymphoma', 'C19HAEMCAN_COD'),
        ('cystic fibrosis', 'CUST_ICB_CYSTIC_FIBROSIS'),
        ('deep vein thrombosis', 'VTE_COD'),
        ('depression', 'eFI2_Depression'),
        ('diabetes', 'eFI2_DiabetesEver'),
        ('diabetic retinopathy', 'DRSELIGIBILITY_COD'),
        ('diffuse large b-cell lymphoma', 'C19HAEMCAN_COD'),
        ('dravet syndrome', 'EPIL_COD'),
        ('drug misuse', 'ILLSUBINT_COD'),
        ('dyspepsia', 'eFI2_AbdominalPain'),
        ('epilepsy', 'eFI2_Seizures'),
        ('fallopian tube', 'STERIL_COD'),
        ('follicular lymphoma', 'C19HAEMCAN_COD'),
        ('gastric cancer', 'eFI2_Cancer'),
        ('giant cell arteritis', 'GCA_COD'),
        ('glioma', 'NHAEMCANMORPH_COD'),
        ('gout', 'eFI2_InflammatoryArthritis'),
        ('graft versus host disease', 'GVHD_COD'),
        ('granulomatosis with polyangiitis', 'WEGENERVASC_COD'),
        ('growth hormone deficiency', 'HYPOPITUITARY_COD'),
        ('hand eczema', 'ECZEMA_COD'),
        ('heart failure', 'eFI2_HeartFailure'),
        ('hepatitis b', 'HEPBCVAC_COD'),
        ('hepatocellular carcinoma', 'eFI2_Cancer'),
        ('hiv', 'PREFLANG_COD'),
        ('hodgkin lymphoma', 'HAEMCANMORPH_COD'),
        ('hormone receptor', 'eFI2_ThyroidProblems'),
        ('hypercholesterolaemia', 'CLASSFH_COD'),
        ('immune thrombocytopenia', 'ITP_COD'),
        ('influenza', 'FLUINVITE_COD'),
        ('insomnia', 'eFI2_SleepProblems'),
        ('irritable bowel syndrome', 'IBS_COD'),
        ('ischaemic stroke', 'OSTR_COD'),
        ('juvenile idiopathic arthritis', 'RARTHAD_COD'),
        ('kidney transplant', 'RENALTRANSP_COD'),
        ('leukaemia', 'eFI2_Cancer'),
        ('lung cancer', 'FTCANREF_COD'),
        ('lymphoma', 'C19HAEMCAN_COD'),
        ('macular degeneration', 'CUST_ICB_VISUAL_IMPAIRMENT'),
        ('macular oedema', 'CUST_ICB_VISUAL_IMPAIRMENT'),
        ('major depressive episodes', 'eFI2_Depression'),
        ('malignant melanoma', 'eFI2_Cancer'),
        ('malignant pleural mesothelioma', 'LUNGCAN_COD'),
        ('manic episode', 'MH_COD'),
        ('mantle cell lymphoma', 'HAEMCANMORPH_COD'),
        ('melanoma', 'eFI2_Cancer'),
        ('merkel cell carcinoma', 'C19CAN_COD'),
        ('migraine', 'eFI2_Headache'),
        ('motor neurone disease', 'MND_COD'),
        ('multiple myeloma', 'C19HAEMCAN_COD'),
        ('multiple sclerosis', 'MS_COD'),
        ('myelodysplastic', 'eFI2_AnaemiaEver'),
        ('myelofibrosis', 'MDS_COD'),
        ('myocardial infarction', 'eFI2_IschaemicHeartDisease'),
        ('myotonia', 'CNDATRISK2_COD'),
        ('narcolepsy', 'LD_COD'),
        ('neuroendocrine tumour', 'LUNGCAN_COD'),
        ('non-small cell lung cancer', 'LUNGCAN_COD'),
        ('non-small-cell lung cancer', 'FTCANREF_COD'),
        ('obesity', 'BMI30_COD'),
        ('osteoarthritis', 'CUST_ICB_OSTEOARTHRITIS'),
        ('osteoporosis', 'eFI2_Osteoporosis'),
        ('osteosarcoma', 'NHAEMCANMORPH_COD'),
        ('ovarian cancer', 'C19CAN_COD'),
        ('peripheral arterial disease', 'PADEXC_COD'),
        ('plaque psoriasis', 'PSORIASIS_COD'),
        ('polycystic kidney disease', 'EPPCONGMALF_COD'),
        ('polycythaemia vera', 'C19HAEMCAN_COD'),
        ('pregnancy', 'C19PREG_COD'),
        ('primary biliary cholangitis', 'eFI2_LiverProblems'),
        ('primary hypercholesterolaemia', 'FNFHYP_COD'),
        ('prostate cancer', 'EPPSOLIDCAN_COD'),
        ('psoriasis', 'PSORIASIS_COD'),
        ('psoriatic arthritis', 'RARTHAD_COD'),
        ('pulmonary embolism', 'eFI2_RespiratoryDiseaseTimeSensitive'),
        ('pulmonary fibrosis', 'ILD_COD'),
        ('relapsing multiple sclerosis', 'MS_COD'),
        ('renal cell carcinoma', 'C19CAN_COD'),
        ('renal transplantation', 'RENALTRANSP_COD'),
        ('retinal vein occlusion', 'CUST_ICB_VISUAL_IMPAIRMENT'),
        ('rheumatoid arthritis', 'eFI2_InflammatoryArthritis'),
        ('rivaroxaban', 'DOACCON_COD'),
        ('schizophrenia', 'MH_COD'),
        ('seizures', 'LSZFREQ_COD'),
        ('sepsis', 'C19ACTIVITY_COD'),
        ('severe persistent allergic asthma', 'SEVAST_COD'),
        ('sickle cell disease', 'SICKLE_COD'),
        ('sleep apnoea', 'CUST_ICB_NON_SEVERE_LDA'),
        ('smoking cessation', 'SMOKINGINT_COD'),
        ('soft tissue sarcoma', 'NHAEMCANMORPH_COD'),
        ('spinal muscular atrophy', 'MND_COD'),
        ('squamous cell', 'C19CAN_COD'),
        ('squamous cell carcinoma', 'C19CAN_COD'),
        ('stem cell transplant', 'ALLOTRANSP_COD'),
        ('stroke', 'eFI2_Stroke'),
        ('systemic lupus erythematosus', 'SLUPUS_COD'),
        ('systemic mastocytosis', 'HAEMCANMORPH_COD'),
        ('thrombocytopenic purpura', 'TTP_COD'),
        ('thrombotic thrombocytopenic purpura', 'TTP_COD'),
        ('thyroid cancer', 'C19CAN_COD'),
        ('tophaceous gout', 'CUST_ICB_OSTEOARTHRITIS'),
        ('transitional cell carcinoma', 'C19CAN_COD'),
        ('type 1 diabetes', 'DMTYPE1_COD'),
        ('type 2 diabetes', 'DMTYPE2_COD'),
        ('ulcerative colitis', 'eFI2_InflammatoryBowelDisease'),
        ('urothelial carcinoma', 'NHAEMCANMORPH_COD'),
        ('urticaria', 'XSAL_COD'),
        ('uveitis', 'CUST_ICB_VISUAL_IMPAIRMENT'),
        ('vascular disease', 'CVDINVITE_COD'),
        ('vasculitis', 'CRYOGLOBVASC_COD')
    ) AS t(Search_Term, Cluster_ID)
),

ClusterCodes AS (
    SELECT
        stc.Search_Term,
        c."SNOMEDCode",
        c."SNOMEDDescription"
    FROM SearchTermClusters stc
    JOIN DATA_HUB.PHM."ClinicalCodingClusterSnomedCodes" c
        ON stc.Cluster_ID = c."Cluster_ID"
    WHERE c."SNOMEDCode" IS NOT NULL
),

ExplicitCodes AS (
    SELECT Search_Term, SNOMEDCode, SNOMEDDescription FROM (VALUES
        ('acute coronary syndrome', '837091000000100', 'Manual mapping'),
        ('ankylosing spondylitis', '162930007', 'Manual mapping'),
        ('ankylosing spondylitis', '239805001', 'Manual mapping'),
        ('ankylosing spondylitis', '239810002', 'Manual mapping'),
        ('ankylosing spondylitis', '239811003', 'Manual mapping'),
        ('ankylosing spondylitis', '394990003', 'Manual mapping'),
        ('ankylosing spondylitis', '429712009', 'Manual mapping'),
        ('ankylosing spondylitis', '441562009', 'Manual mapping'),
        ('ankylosing spondylitis', '441680005', 'Manual mapping'),
        ('ankylosing spondylitis', '441930001', 'Manual mapping'),
        ('axial spondyloarthritis', '723116002', 'Manual mapping'),
        ('choroidal neovascularisation', '380621000000102', 'Manual mapping'),
        ('choroidal neovascularisation', '733124000', 'Manual mapping')
    ) AS t(Search_Term, SNOMEDCode, SNOMEDDescription)
),

AllIndicationCodes AS (
    SELECT Search_Term, "SNOMEDCode" AS SNOMEDCode, "SNOMEDDescription" AS SNOMEDDescription
    FROM ClusterCodes
    UNION ALL
    SELECT Search_Term, SNOMEDCode, SNOMEDDescription
    FROM ExplicitCodes
)
"""


def get_patient_indication_groups(
    patient_pseudonyms: list[str],
    connector: Optional[SnowflakeConnector] = None,
    batch_size: int = 500,
) -> "pd.DataFrame":
    """
    Batch lookup GP diagnosis-based indication groups using Snowflake cluster query.

    This function queries Snowflake directly using the embedded cluster CTE
    (from snomed_indication_mapping_query.sql) to find patients with matching
    GP diagnoses. This is the NEW approach replacing the old SQLite-based lookup.

    The query:
    1. Uses the cluster mapping CTE to get all Search_Term -> SNOMED code mappings
    2. Joins with PrimaryCareClinicalCoding to find patients with matching codes
    3. Returns the most recent match per patient (by EventDateTime)

    Args:
        patient_pseudonyms: List of PseudoNHSNoLinked values (matches PatientPseudonym in GP records)
        connector: Optional SnowflakeConnector (defaults to singleton)
        batch_size: Number of patients per Snowflake query batch (default 500)

    Returns:
        DataFrame with columns:
        - PatientPseudonym: The patient identifier (PseudoNHSNoLinked value)
        - Search_Term: The matched indication (e.g., "rheumatoid arthritis")
        - EventDateTime: Date of the GP diagnosis record

        Patients not found in results have no matching GP diagnosis.
    """
    import pandas as pd

    logger.info(f"Starting Snowflake-direct indication lookup for {len(patient_pseudonyms)} patients...")

    # Handle edge case: empty patient list
    if not patient_pseudonyms:
        logger.warning("Empty patient list provided")
        return pd.DataFrame(columns=['PatientPseudonym', 'Search_Term', 'EventDateTime'])

    # Check Snowflake availability
    if not SNOWFLAKE_AVAILABLE:
        logger.error("Snowflake connector not available - cannot lookup GP records")
        return pd.DataFrame(columns=['PatientPseudonym', 'Search_Term', 'EventDateTime'])

    if not is_snowflake_configured():
        logger.error("Snowflake not configured - cannot lookup GP records")
        return pd.DataFrame(columns=['PatientPseudonym', 'Search_Term', 'EventDateTime'])

    if connector is None:
        connector = get_connector()

    # Results list to collect all matches
    all_results: list[dict] = []

    # Process patients in batches
    total_patients = len(patient_pseudonyms)
    for batch_start in range(0, total_patients, batch_size):
        batch_end = min(batch_start + batch_size, total_patients)
        batch_pseudonyms = patient_pseudonyms[batch_start:batch_end]
        batch_num = batch_start // batch_size + 1
        total_batches = (total_patients + batch_size - 1) // batch_size

        logger.info(f"Batch {batch_num}/{total_batches}: patients {batch_start + 1} to {batch_end}")

        # Build patient IN clause placeholders
        patient_placeholders = ", ".join(["%s"] * len(batch_pseudonyms))

        # Build the full query with cluster CTE
        # This finds the most recent matching diagnosis for each patient
        # Note: Column names must be aliased to ensure consistent casing in results
        query = f"""
{CLUSTER_MAPPING_SQL}
SELECT
    pc."PatientPseudonym" AS "PatientPseudonym",
    aic.Search_Term AS "Search_Term",
    pc."EventDateTime" AS "EventDateTime"
FROM DATA_HUB.PHM."PrimaryCareClinicalCoding" pc
INNER JOIN AllIndicationCodes aic
    ON pc."SNOMEDCode" = aic.SNOMEDCode
WHERE pc."PatientPseudonym" IN ({patient_placeholders})
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY pc."PatientPseudonym"
    ORDER BY pc."EventDateTime" DESC
) = 1
"""

        try:
            results = connector.execute_dict(query, tuple(batch_pseudonyms))

            for row in results:
                all_results.append({
                    'PatientPseudonym': row.get('PatientPseudonym'),
                    'Search_Term': row.get('Search_Term'),
                    'EventDateTime': row.get('EventDateTime'),
                })

            logger.debug(f"Batch {batch_num}: found {len(results)} matches")

        except Exception as e:
            logger.error(f"Error querying GP records for batch {batch_num}: {e}")
            # Continue with other batches - partial results are better than none

    # Build result DataFrame
    result_df = pd.DataFrame(all_results)

    # Log summary statistics
    if len(result_df) > 0:
        matched_count = len(result_df)
        match_rate = 100 * matched_count / total_patients
        unique_terms = result_df['Search_Term'].nunique()
        logger.info(f"Indication lookup complete:")
        logger.info(f"  Total patients queried: {total_patients}")
        logger.info(f"  Patients with GP match: {matched_count} ({match_rate:.1f}%)")
        logger.info(f"  Unique Search_Terms found: {unique_terms}")

        # Log top Search_Terms
        top_terms = result_df['Search_Term'].value_counts().head(5)
        logger.info(f"  Top 5 indications: {dict(top_terms)}")
    else:
        logger.info(f"Indication lookup complete: 0 matches from {total_patients} patients")

    return result_df


# Export public API
__all__ = [
    # Dataclasses
    "ClusterSnomedCodes",
    "IndicationValidationResult",
    "DrugIndicationMatchRate",
    "DrugSnomedMapping",
    "DirectSnomedMatchResult",
    "DirectorateAssignment",
    # Cluster-based lookup functions (existing)
    "get_drug_clusters",
    "get_drug_cluster_ids",
    "get_cluster_snomed_codes",
    "patient_has_indication",
    "validate_indication",
    "get_indication_match_rate",
    "batch_validate_indications",
    "get_available_clusters",
    # Direct SNOMED lookup functions (new)
    "get_drug_snomed_codes",
    "patient_has_indication_direct",
    # Diagnosis-based directorate assignment
    "get_directorate_from_diagnosis",
    # Batch lookup for indication groups
    "batch_lookup_indication_groups",
    # Drug-indication mapping from DimSearchTerm.csv
    "load_drug_indication_mapping",
    "get_search_terms_for_drug",
    # Snowflake-direct indication lookup (new approach)
    "get_patient_indication_groups",
    "CLUSTER_MAPPING_SQL",
]
