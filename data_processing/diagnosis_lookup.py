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
from typing import Optional, Callable, Any, cast
import csv

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
]
