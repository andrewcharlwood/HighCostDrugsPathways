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
