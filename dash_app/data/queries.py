"""
Thin wrapper around shared pathway query functions.

Resolves the database path relative to this file's location and delegates
to the shared functions in src/data_processing/pathway_queries.py.
"""

from pathlib import Path
from typing import Optional

from data_processing.pathway_queries import (
    load_initial_data as _load_initial_data,
    load_pathway_nodes as _load_pathway_nodes,
    get_drug_market_share as _get_drug_market_share,
    get_pathway_costs as _get_pathway_costs,
    get_cost_waterfall as _get_cost_waterfall,
    get_drug_transitions as _get_drug_transitions,
    get_dosing_intervals as _get_dosing_intervals,
    get_drug_directory_matrix as _get_drug_directory_matrix,
    get_treatment_durations as _get_treatment_durations,
    get_trust_market_share as _get_trust_market_share,
    get_trust_cost_waterfall as _get_trust_cost_waterfall,
    get_trust_dosing as _get_trust_dosing,
    get_trust_heatmap as _get_trust_heatmap,
    get_trust_durations as _get_trust_durations,
    get_directorate_summary as _get_directorate_summary,
    get_retention_funnel as _get_retention_funnel,
    get_pathway_depth_distribution as _get_pathway_depth_distribution,
    get_duration_cost_scatter as _get_duration_cost_scatter,
)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "pathways.db"


def load_initial_data() -> dict:
    """Load reference data (drugs, directorates, indications, refresh info)."""
    return _load_initial_data(DB_PATH)


def load_pathway_data(
    filter_id: str = "all_6mo",
    chart_type: str = "directory",
    selected_drugs: Optional[list[str]] = None,
    selected_directorates: Optional[list[str]] = None,
    selected_trusts: Optional[list[str]] = None,
) -> dict:
    """Load pre-computed pathway nodes with optional filters."""
    return _load_pathway_nodes(
        DB_PATH,
        filter_id=filter_id,
        chart_type=chart_type,
        selected_drugs=selected_drugs,
        selected_directorates=selected_directorates,
        selected_trusts=selected_trusts,
    )


# --- Analytics chart query wrappers (Phase 9) ---


def get_drug_market_share(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 3 drug nodes grouped by directory with patient counts."""
    return _get_drug_market_share(DB_PATH, date_filter_id, chart_type, directory, trust)


def get_pathway_costs(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 4+ pathway nodes with annualized cost."""
    return _get_pathway_costs(DB_PATH, date_filter_id, chart_type, directory, trust)


def get_cost_waterfall(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 2 directorate nodes with cost per patient."""
    return _get_cost_waterfall(DB_PATH, date_filter_id, chart_type, trust)


def get_drug_transitions(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> dict:
    """Drug transition data for Sankey diagram."""
    return _get_drug_transitions(DB_PATH, date_filter_id, chart_type, directory, trust)


def get_dosing_intervals(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    drug: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Dosing interval data parsed from average_spacing."""
    return _get_dosing_intervals(DB_PATH, date_filter_id, chart_type, drug, trust)


def get_drug_directory_matrix(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    trust: Optional[str] = None,
) -> dict:
    """Directory × drug matrix with patient counts and costs."""
    return _get_drug_directory_matrix(DB_PATH, date_filter_id, chart_type, trust)


def get_treatment_durations(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Treatment duration data (avg_days) by drug."""
    return _get_treatment_durations(DB_PATH, date_filter_id, chart_type, directory, trust)


# --- Trust Comparison query wrappers (Phase 10) ---


def get_trust_market_share(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: str = "",
) -> list[dict]:
    """Drug market share by trust within a single directorate."""
    return _get_trust_market_share(DB_PATH, date_filter_id, chart_type, directory)


def get_trust_cost_waterfall(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: str = "",
) -> list[dict]:
    """Cost per patient by trust within a single directorate."""
    return _get_trust_cost_waterfall(DB_PATH, date_filter_id, chart_type, directory)


def get_trust_dosing(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: str = "",
) -> list[dict]:
    """Drug dosing intervals by trust within a single directorate."""
    return _get_trust_dosing(DB_PATH, date_filter_id, chart_type, directory)


def get_trust_heatmap(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: str = "",
) -> dict:
    """Trust x drug matrix for a single directorate."""
    return _get_trust_heatmap(DB_PATH, date_filter_id, chart_type, directory)


def get_trust_durations(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: str = "",
) -> list[dict]:
    """Drug durations by trust within a single directorate."""
    return _get_trust_durations(DB_PATH, date_filter_id, chart_type, directory)


# --- Directorate summary for Trust Comparison landing page ---


def get_directorate_summary(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
) -> list[dict]:
    """Per-directorate summary (name, patient count, drug count) for landing cards."""
    return _get_directorate_summary(DB_PATH, date_filter_id, chart_type)


# --- Retention funnel (Phase C) ---


def get_retention_funnel(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Patient retention by treatment line depth."""
    return _get_retention_funnel(DB_PATH, date_filter_id, chart_type, directory, trust)


def get_pathway_depth_distribution(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Patients who stopped at each treatment line depth (exclusive counts)."""
    return _get_pathway_depth_distribution(DB_PATH, date_filter_id, chart_type, directory, trust)


def get_duration_cost_scatter(
    date_filter_id: str = "all_6mo",
    chart_type: str = "directory",
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Drug-level avg_days and cost_pp_pa for scatter plot."""
    return _get_duration_cost_scatter(DB_PATH, date_filter_id, chart_type, directory, trust)
