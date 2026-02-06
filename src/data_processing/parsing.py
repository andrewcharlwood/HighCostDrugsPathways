"""Parsing utilities for pathway node data.

Shared functions for extracting structured data from pathway_nodes columns.
Used by analytics chart callbacks in dash_app/callbacks/.
"""
import re


def parse_average_spacing(spacing_html):
    """Extract dosing information from average_spacing HTML string.

    Args:
        spacing_html: HTML like '<br><b>DRUG</b><br>On average given 35.6 times
                      with a 9.0 weekly interval (320.0 weeks total treatment length)'
                      May contain multiple drug entries separated by <br><b>.

    Returns:
        List of dicts with keys: drug_name, dose_count, weekly_interval, total_weeks.
        Returns empty list for None/empty input or unparseable strings.
    """
    if not spacing_html:
        return []

    results = []
    pattern = (
        r"<b>([^<]+)</b><br>"
        r"On average given ([\d.]+) times "
        r"with a ([\d.]+) weekly interval "
        r"\(([\d.]+) weeks total treatment length\)"
    )

    for match in re.finditer(pattern, spacing_html):
        results.append({
            "drug_name": match.group(1).strip(),
            "dose_count": float(match.group(2)),
            "weekly_interval": float(match.group(3)),
            "total_weeks": float(match.group(4)),
        })

    return results


def parse_pathway_drugs(ids, level):
    """Extract ordered drug list from the ids column at level 4+.

    Args:
        ids: String like 'ROOT - TRUST - DIR - DRUG_A - DRUG_B - DRUG_C'.
             Segments are separated by ' - '. Drug names start at index 3
             (0=root, 1=trust, 2=directory, 3+=drugs).
        level: Node level. Only meaningful for level >= 3.

    Returns:
        List of drug names in treatment order. Empty list for level < 3
        or invalid input.
    """
    if not ids or level < 3:
        return []

    segments = ids.split(" - ")
    # Segments: [root, trust, directory, drug_0, drug_1, ...]
    if len(segments) <= 3:
        return []

    return segments[3:]


def _get_patients(node):
    """Get patient count from a node dict (supports both 'value' and 'patients' keys)."""
    return node.get("value") or node.get("patients") or 0


def calculate_retention_rate(nodes):
    """Calculate pathway retention rates from node data.

    For each N-drug pathway, calculate what % of patients do NOT escalate
    to an N+1 drug pathway. This identifies effective treatment sequences.

    Args:
        nodes: List of dicts with 'ids', 'level', and 'value' or 'patients' keys.
               Should contain level 4+ nodes (pathway level).

    Returns:
        Dict mapping pathway ids to retention info:
        {ids: {"retained_patients": int, "total_patients": int,
               "retention_rate": float, "drug_sequence": list}}
    """
    if not nodes:
        return {}

    # Index nodes by ids for parent lookup
    node_map = {n["ids"]: n for n in nodes if n.get("ids")}

    results = {}
    for node in nodes:
        level = node.get("level", 0)
        if level < 4:
            continue

        node_ids = node.get("ids", "")
        total_patients = _get_patients(node)
        if not total_patients:
            continue

        # Find child pathways (nodes whose ids start with this node's ids + " - ")
        child_prefix = node_ids + " - "
        child_patients = sum(
            _get_patients(n)
            for n in nodes
            if n.get("ids", "").startswith(child_prefix) and n.get("level", 0) == level + 1
        )

        retained = total_patients - child_patients
        retention_rate = (retained / total_patients * 100) if total_patients > 0 else 0.0

        results[node_ids] = {
            "retained_patients": retained,
            "total_patients": total_patients,
            "retention_rate": round(retention_rate, 1),
            "drug_sequence": parse_pathway_drugs(node_ids, level),
        }

    return results
