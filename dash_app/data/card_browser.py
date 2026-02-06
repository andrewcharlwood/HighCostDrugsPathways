"""
Directorate card tree builder for the drug browser drawer.

Loads DimSearchTerm.csv and builds a nested structure:
    {PrimaryDirectorate: {Search_Term: [drug_fragment, ...]}}

Also provides get_all_drugs() for the flat "All Drugs" card.
"""

import csv
from collections import defaultdict
from pathlib import Path

from data_processing.diagnosis_lookup import SEARCH_TERM_MERGE_MAP

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DIM_SEARCH_TERM_PATH = DATA_DIR / "DimSearchTerm.csv"


def build_directorate_tree() -> dict[str, dict[str, list[str]]]:
    """
    Build a nested dict from DimSearchTerm.csv grouped by directorate.

    Returns:
        {
            "CARDIOLOGY": {
                "acute coronary syndrome": ["ABCIXIMAB", "CLOPIDOGREL", ...],
                "atrial fibrillation": ["APIXABAN", "DABIGATRAN", ...],
                ...
            },
            "CLINICAL HAEMATOLOGY": { ... },
            ...
        }

    Search_Term values are normalized via SEARCH_TERM_MERGE_MAP
    (e.g. "allergic asthma" → "asthma"). Drug fragments within
    merged terms are combined and deduplicated.
    """
    # directorate → search_term → set of drug fragments
    tree: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    with open(DIM_SEARCH_TERM_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            search_term = (row.get("Search_Term") or "").strip().lower()
            drug_names_raw = row.get("CleanedDrugName") or ""
            directorate = (row.get("PrimaryDirectorate") or "").strip().upper()

            if not search_term or not directorate:
                continue

            # Apply merge map (e.g. "allergic asthma" → "asthma")
            search_term = SEARCH_TERM_MERGE_MAP.get(search_term, search_term)

            fragments = [
                frag.strip().upper()
                for frag in drug_names_raw.split("|")
                if frag.strip()
            ]

            tree[directorate][search_term].update(fragments)

    # Convert sets → sorted lists and sort at every level
    result: dict[str, dict[str, list[str]]] = {}
    for directorate in sorted(tree):
        result[directorate] = {
            term: sorted(tree[directorate][term])
            for term in sorted(tree[directorate])
        }

    return result


def get_all_drugs() -> list[str]:
    """
    Return a sorted flat list of all unique drug labels from pathway_nodes level 3.

    Delegates to load_initial_data() which already queries the database.
    """
    from dash_app.data.queries import load_initial_data

    data = load_initial_data()
    return data.get("available_drugs", [])


def get_all_trusts() -> list[str]:
    """
    Return a sorted flat list of all unique trust names from pathway_nodes level 1.

    Delegates to load_initial_data() which already queries the database.
    """
    from dash_app.data.queries import load_initial_data

    data = load_initial_data()
    return data.get("available_trusts", [])
