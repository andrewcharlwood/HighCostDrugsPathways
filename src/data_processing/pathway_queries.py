"""
Shared query functions for pathway node data.

These functions extract the data loading logic from the Reflex AppState
into standalone functions that accept db_path as a parameter and return
plain JSON-serializable dicts/lists. Both Reflex and Dash can call these.

All queries are read-only SELECTs against pathways.db.
"""

import sqlite3
from pathlib import Path
from typing import Optional


def load_initial_data(db_path: Path) -> dict:
    """
    Load reference data from SQLite on app initialization.

    Extracted from AppState.load_data() (pathways_app.py lines 407-488).

    Returns dict with keys:
        available_drugs: sorted list of unique drug labels (level 3 nodes)
        available_directorates: sorted list of unique directorate labels (level 2, directory charts)
        available_indications: sorted list of unique indications from ref_drug_indication_clusters
        total_records: source row count from latest completed refresh
        total_patients: patient count from default root node
        total_cost: total cost from default root node
        last_updated: ISO timestamp of latest completed refresh
    """
    if not db_path.exists():
        return {
            "available_drugs": [],
            "available_directorates": [],
            "available_indications": [],
            "available_trusts": [],
            "total_records": 0,
            "last_updated": "",
            "error": "Database not found",
        }

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        # Latest completed refresh metadata
        cursor.execute("""
            SELECT source_row_count, completed_at
            FROM pathway_refresh_log
            WHERE status = 'completed'
            ORDER BY started_at DESC
            LIMIT 1
        """)
        refresh_row = cursor.fetchone()
        total_records = (refresh_row[0] or 0) if refresh_row else 0
        last_updated = (refresh_row[1] or "") if refresh_row else ""

        # Unique drugs from pathway_nodes level 3
        cursor.execute("""
            SELECT DISTINCT labels
            FROM pathway_nodes
            WHERE level = 3 AND labels IS NOT NULL AND labels != ''
            ORDER BY labels
        """)
        available_drugs = [row[0] for row in cursor.fetchall()]

        # Unique directorates from directory chart pathway_nodes level 2
        cursor.execute("""
            SELECT DISTINCT labels
            FROM pathway_nodes
            WHERE level = 2 AND chart_type = 'directory'
                AND labels IS NOT NULL AND labels != ''
            ORDER BY labels
        """)
        available_directorates = [row[0] for row in cursor.fetchall()]

        # Unique indications from ref_drug_indication_clusters
        cursor.execute("""
            SELECT DISTINCT indication
            FROM ref_drug_indication_clusters
            WHERE indication IS NOT NULL AND indication != ''
            ORDER BY indication
        """)
        available_indications = [row[0] for row in cursor.fetchall()]
        if not available_indications:
            available_indications = ["(No indications available)"]

        # Unique trusts from pathway_nodes level 1
        cursor.execute("""
            SELECT DISTINCT trust_name
            FROM pathway_nodes
            WHERE level = 1 AND trust_name IS NOT NULL AND trust_name != ''
            ORDER BY trust_name
        """)
        available_trusts = [row[0] for row in cursor.fetchall()]

        # Total patients and cost from default root node
        total_patients = 0
        total_cost = 0.0
        cursor.execute("""
            SELECT value, cost FROM pathway_nodes
            WHERE level = 0 AND date_filter_id = 'all_6mo' AND chart_type = 'directory'
            LIMIT 1
        """)
        root_row = cursor.fetchone()
        if root_row:
            total_patients = root_row[0] or 0
            total_cost = root_row[1] or 0.0

        return {
            "available_drugs": available_drugs,
            "available_directorates": available_directorates,
            "available_indications": available_indications,
            "available_trusts": available_trusts,
            "total_records": total_records,
            "total_patients": total_patients,
            "total_cost": total_cost,
            "last_updated": last_updated,
        }
    except sqlite3.Error as e:
        return {
            "available_drugs": [],
            "available_directorates": [],
            "available_indications": [],
            "available_trusts": [],
            "total_records": 0,
            "last_updated": "",
            "error": f"Database error: {e}",
        }
    finally:
        conn.close()


def load_pathway_nodes(
    db_path: Path,
    filter_id: str,
    chart_type: str,
    selected_drugs: Optional[list[str]] = None,
    selected_directorates: Optional[list[str]] = None,
    selected_trusts: Optional[list[str]] = None,
) -> dict:
    """
    Load pre-computed pathway nodes from SQLite.

    Extracted from AppState.load_pathway_data() (pathways_app.py lines 490-642).

    Args:
        db_path: Path to pathways.db
        filter_id: e.g. "all_6mo", "2yr_12mo"
        chart_type: "directory" or "indication"
        selected_drugs: optional list of drug names to filter by
        selected_directorates: optional list of directorate names to filter by
        selected_trusts: optional list of trust names to filter by

    Returns dict with keys:
        nodes: list of dicts (JSON-serializable) with chart node data
        unique_patients: int (from root node)
        total_drugs: int (unique drugs across level 3+ nodes)
        total_cost: float (from root node)
        last_updated: ISO timestamp string
        error: optional error string
    """
    if not db_path.exists():
        return _empty_result("Database not found")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # Build WHERE clause with parameterized values
        where_clauses = ["date_filter_id = ?", "chart_type = ?"]
        params: list = [filter_id, chart_type]

        if selected_directorates:
            placeholders = ",".join("?" * len(selected_directorates))
            where_clauses.append(
                f"(level < 2 OR directory IN ({placeholders}) OR directory IS NULL OR directory = '')"
            )
            params.extend(selected_directorates)

        if selected_drugs:
            drug_conditions = []
            for drug in selected_drugs:
                drug_conditions.append("drug_sequence LIKE ?")
                params.append(f"%{drug}%")
            where_clauses.append(
                f"(level < 3 OR {' OR '.join(drug_conditions)})"
            )

        if selected_trusts:
            placeholders = ",".join("?" * len(selected_trusts))
            where_clauses.append(
                f"(trust_name IN ({placeholders}) OR trust_name IS NULL OR trust_name = '')"
            )
            params.extend(selected_trusts)

        where_clause = " AND ".join(where_clauses)

        query = f"""
            SELECT
                parents, ids, labels, level, value,
                cost, costpp, cost_pp_pa, colour,
                first_seen, last_seen, first_seen_parent, last_seen_parent,
                average_spacing, average_administered, avg_days,
                trust_name, directory, drug_sequence
            FROM pathway_nodes
            WHERE {where_clause}
            ORDER BY level, parents, ids
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            return _empty_result(f"No pathway data for filter: {filter_id}")

        # When drug or directorate filters are active, prune ancestor nodes
        # that have no matching descendants. Without this, the icicle chart
        # shows empty directorate/trust boxes with no children.
        if selected_drugs or selected_directorates:
            rows = _prune_empty_ancestors(rows)

        nodes = []
        root_patients = 0
        root_cost = 0.0
        has_entity_filter = bool(selected_drugs or selected_directorates or selected_trusts)

        for row in rows:
            node = {
                "parents": row["parents"] or "",
                "ids": row["ids"] or "",
                "labels": row["labels"] or "",
                "value": row["value"] or 0,
                "cost": float(row["cost"]) if row["cost"] else 0.0,
                "costpp": float(row["costpp"]) if row["costpp"] else 0.0,
                "colour": float(row["colour"]) if row["colour"] else 0.0,
                "first_seen": row["first_seen"] or "",
                "last_seen": row["last_seen"] or "",
                "first_seen_parent": row["first_seen_parent"] or "",
                "last_seen_parent": row["last_seen_parent"] or "",
                "average_spacing": row["average_spacing"] or "",
                "cost_pp_pa": row["cost_pp_pa"] or "",
            }
            nodes.append(node)

            if row["level"] == 0:
                root_patients = row["value"] or 0
                root_cost = float(row["cost"]) if row["cost"] else 0.0

        # Count unique drugs from level 3+ nodes
        unique_drugs = set()
        for row in rows:
            if row["level"] >= 3 and row["drug_sequence"]:
                for drug in row["drug_sequence"].split("|"):
                    if drug:
                        unique_drugs.add(drug)

        # When entity filters are active, sum level-3 drug nodes for KPIs
        # instead of using the root node's pre-computed (unfiltered) totals
        if has_entity_filter:
            filtered_patients = sum(
                row["value"] or 0 for row in rows if row["level"] == 3
            )
            filtered_cost = sum(
                float(row["cost"]) if row["cost"] else 0.0
                for row in rows if row["level"] == 3
            )
            root_patients = filtered_patients
            root_cost = filtered_cost

        # Data freshness
        cursor.execute("""
            SELECT completed_at
            FROM pathway_refresh_log
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        """)
        refresh_row = cursor.fetchone()
        last_updated = (
            refresh_row["completed_at"] if refresh_row and refresh_row["completed_at"] else ""
        )

        return {
            "nodes": nodes,
            "unique_patients": root_patients,
            "total_drugs": len(unique_drugs),
            "total_cost": root_cost,
            "last_updated": last_updated,
        }
    except sqlite3.Error as e:
        return _empty_result(f"Database error: {e}")
    finally:
        conn.close()


def _prune_empty_ancestors(rows):
    """Remove ancestor nodes that have no matching descendants.

    When drug/directorate filters are active, levels 0-2 are included
    unconditionally. This leaves directorate and trust nodes that have no
    children in the filtered result. Plotly's icicle chart shows these as
    empty boxes. Prune them by keeping only nodes whose ids appear as a
    parent of another kept node, or that are leaf nodes (level 3+), or
    are the root (level 0).
    """
    # Collect all parent references from the result set
    referenced_parents = {row["parents"] for row in rows if row["parents"]}
    # Keep: root (level 0), any node referenced as a parent, any leaf (level 3+)
    kept = [
        row for row in rows
        if row["level"] == 0
        or row["level"] >= 3
        or row["ids"] in referenced_parents
    ]
    # Second pass: a trust (level 1) may reference root but itself have no
    # kept level-2 children. Recheck that level-1 nodes are still parents
    # of something in the kept set.
    kept_parents = {row["parents"] for row in kept if row["parents"]}
    return [
        row for row in kept
        if row["level"] == 0
        or row["level"] >= 3
        or row["ids"] in kept_parents
    ]


def _empty_result(error: str = "") -> dict:
    return {
        "nodes": [],
        "unique_patients": 0,
        "total_drugs": 0,
        "total_cost": 0.0,
        "last_updated": "",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Analytics chart query functions (Phase 9)
# ---------------------------------------------------------------------------

def _safe_float(value, default=0.0):
    """Convert a value to float, returning default for None/N/A/empty."""
    if value is None or value == "" or value == "N/A":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_drug_market_share(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 3 drug nodes grouped by directory with patient counts and proportions.

    Returns list of dicts: [{directory, drug, patients, proportion, cost, cost_pp_pa}]
    Sorted by directory total patients desc, then drug patients desc within each.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level = 3"]
        params: list = [date_filter_id, chart_type]

        if directory:
            where.append("directory = ?")
            params.append(directory)
        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT labels AS drug, directory, value AS patients,
                   colour AS proportion, cost, cost_pp_pa, trust_name
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            ORDER BY directory, value DESC
        """
        rows = conn.execute(query, params).fetchall()

        # Aggregate across trusts: sum patients/cost per directory+drug
        agg = {}
        for r in rows:
            key = (r["directory"], r["drug"])
            if key not in agg:
                agg[key] = {"directory": r["directory"], "drug": r["drug"],
                            "patients": 0, "cost": 0.0}
            agg[key]["patients"] += r["patients"] or 0
            agg[key]["cost"] += float(r["cost"]) if r["cost"] else 0.0

        # Compute proportions within each directory
        dir_totals = {}
        for v in agg.values():
            dir_totals[v["directory"]] = dir_totals.get(v["directory"], 0) + v["patients"]

        result = []
        for v in agg.values():
            total = dir_totals.get(v["directory"], 1)
            result.append({
                "directory": v["directory"],
                "drug": v["drug"],
                "patients": v["patients"],
                "proportion": round(v["patients"] / total, 4) if total else 0,
                "cost": round(v["cost"], 2),
                "cost_pp_pa": round(v["cost"] / v["patients"], 2) if v["patients"] else 0,
            })

        # Sort: directory by total patients desc, drugs by patients desc within
        result.sort(key=lambda x: (-dir_totals.get(x["directory"], 0), -x["patients"]))
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_pathway_costs(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 4+ pathway nodes with annualized cost and pathway labels.

    Returns list of dicts: [{ids, pathway_label, cost_pp_pa, patients, directory, drug_sequence}]
    Sorted by cost_pp_pa desc.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level >= 4"]
        params: list = [date_filter_id, chart_type]

        if directory:
            where.append("directory = ?")
            params.append(directory)
        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT ids, labels, level, value AS patients, cost, costpp,
                   cost_pp_pa, avg_days, directory, drug_sequence, trust_name
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            ORDER BY value DESC
        """
        rows = conn.execute(query, params).fetchall()

        result = []
        for r in rows:
            cpp = _safe_float(r["cost_pp_pa"])
            drugs = (r["drug_sequence"] or "").split("|")
            pathway_label = " → ".join(d for d in drugs if d)
            result.append({
                "ids": r["ids"],
                "pathway_label": pathway_label,
                "cost_pp_pa": cpp,
                "patients": r["patients"] or 0,
                "cost": float(r["cost"]) if r["cost"] else 0.0,
                "avg_days": _safe_float(r["avg_days"]),
                "directory": r["directory"] or "",
                "trust_name": r["trust_name"] or "",
                "drug_sequence": drugs,
                "level": r["level"],
            })

        result.sort(key=lambda x: -x["cost_pp_pa"])
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_cost_waterfall(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 2 directorate/indication nodes with cost metrics.

    Since level 2 cost_pp_pa is 'N/A', we compute it from child (level 3) nodes:
    sum(cost) / sum(patients) for each directory.

    Returns list of dicts: [{directory, patients, total_cost, cost_pp}]
    Sorted by cost_pp desc.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level = 3"]
        params: list = [date_filter_id, chart_type]

        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT directory, SUM(value) AS patients, SUM(cost) AS total_cost
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            GROUP BY directory
            HAVING patients > 0
            ORDER BY total_cost DESC
        """
        rows = conn.execute(query, params).fetchall()

        result = []
        for r in rows:
            patients = r["patients"] or 0
            total_cost = float(r["total_cost"]) if r["total_cost"] else 0.0
            result.append({
                "directory": r["directory"] or "",
                "patients": patients,
                "total_cost": round(total_cost, 2),
                "cost_pp": round(total_cost / patients, 2) if patients else 0,
            })

        result.sort(key=lambda x: -x["cost_pp"])
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_drug_transitions(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> dict:
    """Parse level 3+ nodes into source→target drug transitions for Sankey.

    Returns dict with:
        nodes: [{name, total_patients}] — unique drug names
        links: [{source_idx, target_idx, patients}] — transitions between drugs
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level >= 4"]
        params: list = [date_filter_id, chart_type]

        if directory:
            where.append("directory = ?")
            params.append(directory)
        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT ids, level, value AS patients, drug_sequence, directory
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            ORDER BY level, ids
        """
        rows = conn.execute(query, params).fetchall()

        # Build node list and link aggregation
        # Each drug at each treatment line is a separate Sankey node
        # e.g., "ADALIMUMAB (1st)" and "ADALIMUMAB (2nd)" are different nodes
        drug_line_set = set()
        link_agg = {}

        for r in rows:
            drugs = [d for d in (r["drug_sequence"] or "").split("|") if d]
            patients = r["patients"] or 0
            if len(drugs) < 2 or patients == 0:
                continue

            # Only use adjacent transitions (drug[i] → drug[i+1])
            for i in range(len(drugs) - 1):
                src = f"{drugs[i]} ({_ordinal(i + 1)})"
                tgt = f"{drugs[i + 1]} ({_ordinal(i + 2)})"
                drug_line_set.add(src)
                drug_line_set.add(tgt)
                key = (src, tgt)
                link_agg[key] = link_agg.get(key, 0) + patients

        # Build indexed node list
        node_list = sorted(drug_line_set)
        node_idx = {name: i for i, name in enumerate(node_list)}

        nodes = [{"name": name} for name in node_list]
        links = [
            {"source_idx": node_idx[src], "target_idx": node_idx[tgt], "patients": pts}
            for (src, tgt), pts in sorted(link_agg.items(), key=lambda x: -x[1])
        ]

        return {"nodes": nodes, "links": links}
    except sqlite3.Error:
        return {"nodes": [], "links": []}
    finally:
        conn.close()


def _ordinal(n: int) -> str:
    """Return '1st', '2nd', '3rd', '4th', etc."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def get_dosing_intervals(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    drug: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 3 drug nodes with parsed dosing interval data.

    Returns list of dicts:
        [{drug, trust_name, directory, weekly_interval, dose_count, total_weeks, patients}]
    """
    from data_processing.parsing import parse_average_spacing

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level = 3",
                 "average_spacing IS NOT NULL", "average_spacing != ''"]
        params: list = [date_filter_id, chart_type]

        if drug:
            where.append("labels = ?")
            params.append(drug)
        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT labels AS drug, trust_name, directory, value AS patients,
                   average_spacing
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            ORDER BY labels, trust_name
        """
        rows = conn.execute(query, params).fetchall()

        result = []
        for r in rows:
            parsed = parse_average_spacing(r["average_spacing"])
            for entry in parsed:
                result.append({
                    "drug": entry["drug_name"],
                    "trust_name": r["trust_name"] or "",
                    "directory": r["directory"] or "",
                    "weekly_interval": entry["weekly_interval"],
                    "dose_count": entry["dose_count"],
                    "total_weeks": entry["total_weeks"],
                    "patients": r["patients"] or 0,
                })

        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_drug_directory_matrix(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    trust: Optional[str] = None,
) -> dict:
    """Level 3 nodes pivoted as directory × drug matrix.

    Returns dict with:
        directories: sorted list of directory names (rows)
        drugs: sorted list of drug names (columns)
        matrix: {directory: {drug: {patients, cost, cost_pp_pa}}}
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level = 3"]
        params: list = [date_filter_id, chart_type]

        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT labels AS drug, directory, value AS patients, cost, cost_pp_pa
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            ORDER BY directory, labels
        """
        rows = conn.execute(query, params).fetchall()

        # Aggregate across trusts
        matrix = {}
        dir_totals = {}
        drug_totals = {}

        for r in rows:
            d = r["directory"] or ""
            drug = r["drug"] or ""
            patients = r["patients"] or 0
            cost = float(r["cost"]) if r["cost"] else 0.0
            cpp = _safe_float(r["cost_pp_pa"])

            if d not in matrix:
                matrix[d] = {}
            if drug not in matrix[d]:
                matrix[d][drug] = {"patients": 0, "cost": 0.0}

            matrix[d][drug]["patients"] += patients
            matrix[d][drug]["cost"] += cost

            dir_totals[d] = dir_totals.get(d, 0) + patients
            drug_totals[drug] = drug_totals.get(drug, 0) + patients

        # Add cost_pp_pa to each cell
        for d in matrix:
            for drug in matrix[d]:
                cell = matrix[d][drug]
                cell["cost"] = round(cell["cost"], 2)
                cell["cost_pp_pa"] = (
                    round(cell["cost"] / cell["patients"], 2) if cell["patients"] else 0
                )

        # Sort directories by total patients desc, drugs by frequency desc
        directories = sorted(dir_totals, key=lambda x: -dir_totals[x])
        drugs = sorted(drug_totals, key=lambda x: -drug_totals[x])

        return {"directories": directories, "drugs": drugs, "matrix": matrix}
    except sqlite3.Error:
        return {"directories": [], "drugs": [], "matrix": {}}
    finally:
        conn.close()


def get_treatment_durations(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: Optional[str] = None,
    trust: Optional[str] = None,
) -> list[dict]:
    """Level 3 drug nodes with average treatment duration.

    Returns list of dicts: [{drug, avg_days, patients, directory}]
    Sorted by avg_days desc. Excludes nodes with no avg_days data.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where = ["date_filter_id = ?", "chart_type = ?", "level = 3",
                 "avg_days IS NOT NULL"]
        params: list = [date_filter_id, chart_type]

        if directory:
            where.append("directory = ?")
            params.append(directory)
        if trust:
            where.append("trust_name = ?")
            params.append(trust)

        query = f"""
            SELECT labels AS drug, directory, trust_name,
                   value AS patients, avg_days
            FROM pathway_nodes
            WHERE {' AND '.join(where)}
            ORDER BY avg_days DESC
        """
        rows = conn.execute(query, params).fetchall()

        # Aggregate across trusts: weighted average of avg_days by patients
        agg = {}
        for r in rows:
            key = (r["directory"] or "", r["drug"])
            patients = r["patients"] or 0
            days = _safe_float(r["avg_days"])
            if patients == 0 or days == 0:
                continue

            if key not in agg:
                agg[key] = {"drug": r["drug"], "directory": r["directory"] or "",
                            "total_weighted_days": 0.0, "total_patients": 0}
            agg[key]["total_weighted_days"] += days * patients
            agg[key]["total_patients"] += patients

        result = []
        for v in agg.values():
            if v["total_patients"] > 0:
                result.append({
                    "drug": v["drug"],
                    "directory": v["directory"],
                    "avg_days": round(v["total_weighted_days"] / v["total_patients"], 1),
                    "patients": v["total_patients"],
                })

        result.sort(key=lambda x: -x["avg_days"])
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Trust Comparison query functions (Phase 10)
#
# These functions provide per-trust breakdowns within a single directorate.
# Unlike Phase 9 functions which aggregate across trusts, these preserve
# per-trust detail for comparing drugs across trusts within a directorate.
# ---------------------------------------------------------------------------


def get_trust_market_share(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: str,
) -> list[dict]:
    """Drug market share broken down by trust within a single directorate.

    Returns list of dicts: [{trust_name, drug, patients, proportion, cost, cost_pp_pa}]
    Sorted by trust total patients desc, then drug patients desc within each trust.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT labels AS drug, trust_name, value AS patients, cost, cost_pp_pa
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 3
                AND directory = ?
            ORDER BY trust_name, value DESC
        """
        rows = conn.execute(query, (date_filter_id, chart_type, directory)).fetchall()

        # Compute proportions within each trust
        trust_totals = {}
        for r in rows:
            trust = r["trust_name"] or ""
            trust_totals[trust] = trust_totals.get(trust, 0) + (r["patients"] or 0)

        result = []
        for r in rows:
            trust = r["trust_name"] or ""
            patients = r["patients"] or 0
            cost = float(r["cost"]) if r["cost"] else 0.0
            total = trust_totals.get(trust, 1)
            result.append({
                "trust_name": trust,
                "drug": r["drug"],
                "patients": patients,
                "proportion": round(patients / total, 4) if total else 0,
                "cost": round(cost, 2),
                "cost_pp_pa": _safe_float(r["cost_pp_pa"]),
            })

        result.sort(key=lambda x: (-trust_totals.get(x["trust_name"], 0), -x["patients"]))
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_trust_cost_waterfall(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: str,
) -> list[dict]:
    """Cost per patient by trust within a single directorate.

    Returns list of dicts: [{trust_name, patients, total_cost, cost_pp}]
    Sorted by cost_pp desc.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT trust_name, SUM(value) AS patients, SUM(cost) AS total_cost
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 3
                AND directory = ?
            GROUP BY trust_name
            HAVING patients > 0
            ORDER BY total_cost DESC
        """
        rows = conn.execute(query, (date_filter_id, chart_type, directory)).fetchall()

        result = []
        for r in rows:
            patients = r["patients"] or 0
            total_cost = float(r["total_cost"]) if r["total_cost"] else 0.0
            result.append({
                "trust_name": r["trust_name"] or "",
                "patients": patients,
                "total_cost": round(total_cost, 2),
                "cost_pp": round(total_cost / patients, 2) if patients else 0,
            })

        result.sort(key=lambda x: -x["cost_pp"])
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_trust_dosing(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: str,
) -> list[dict]:
    """Drug dosing intervals by trust within a single directorate.

    Returns list of dicts:
        [{drug, trust_name, weekly_interval, dose_count, total_weeks, patients}]
    """
    from data_processing.parsing import parse_average_spacing

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT labels AS drug, trust_name, value AS patients, average_spacing
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 3
                AND directory = ?
                AND average_spacing IS NOT NULL AND average_spacing != ''
            ORDER BY labels, trust_name
        """
        rows = conn.execute(query, (date_filter_id, chart_type, directory)).fetchall()

        result = []
        for r in rows:
            parsed = parse_average_spacing(r["average_spacing"])
            for entry in parsed:
                result.append({
                    "drug": entry["drug_name"],
                    "trust_name": r["trust_name"] or "",
                    "weekly_interval": entry["weekly_interval"],
                    "dose_count": entry["dose_count"],
                    "total_weeks": entry["total_weeks"],
                    "patients": r["patients"] or 0,
                })

        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def get_trust_heatmap(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: str,
) -> dict:
    """Trust x drug matrix for a single directorate.

    Returns dict with:
        trusts: sorted list of trust names (rows)
        drugs: sorted list of drug names (columns)
        matrix: {trust_name: {drug: {patients, cost, cost_pp_pa}}}
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT labels AS drug, trust_name, value AS patients, cost, cost_pp_pa
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 3
                AND directory = ?
            ORDER BY trust_name, labels
        """
        rows = conn.execute(query, (date_filter_id, chart_type, directory)).fetchall()

        matrix = {}
        trust_totals = {}
        drug_totals = {}

        for r in rows:
            trust = r["trust_name"] or ""
            drug = r["drug"] or ""
            patients = r["patients"] or 0
            cost = float(r["cost"]) if r["cost"] else 0.0

            if trust not in matrix:
                matrix[trust] = {}
            matrix[trust][drug] = {
                "patients": patients,
                "cost": round(cost, 2),
                "cost_pp_pa": _safe_float(r["cost_pp_pa"]),
            }

            trust_totals[trust] = trust_totals.get(trust, 0) + patients
            drug_totals[drug] = drug_totals.get(drug, 0) + patients

        trusts = sorted(trust_totals, key=lambda x: -trust_totals[x])
        drugs = sorted(drug_totals, key=lambda x: -drug_totals[x])

        return {"trusts": trusts, "drugs": drugs, "matrix": matrix}
    except sqlite3.Error:
        return {"trusts": [], "drugs": [], "matrix": {}}
    finally:
        conn.close()


def get_trust_durations(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
    directory: str,
) -> list[dict]:
    """Drug treatment durations by trust within a single directorate.

    Returns list of dicts: [{drug, trust_name, avg_days, patients}]
    Sorted by drug name, then trust. No aggregation — each row is one
    trust+drug combination.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT labels AS drug, trust_name, value AS patients, avg_days
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 3
                AND directory = ?
                AND avg_days IS NOT NULL
            ORDER BY labels, trust_name
        """
        rows = conn.execute(query, (date_filter_id, chart_type, directory)).fetchall()

        result = []
        for r in rows:
            patients = r["patients"] or 0
            days = _safe_float(r["avg_days"])
            if patients == 0 or days == 0:
                continue
            result.append({
                "drug": r["drug"],
                "trust_name": r["trust_name"] or "",
                "avg_days": round(days, 1),
                "patients": patients,
            })

        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()


# --- Directorate/indication summary for Trust Comparison landing page ---


def get_directorate_summary(
    db_path: Path,
    date_filter_id: str,
    chart_type: str,
) -> list[dict]:
    """Get per-directorate (or per-indication) summary stats for landing page cards.

    Returns a list of dicts sorted by patient count descending:
        [{"name": "RHEUMATOLOGY", "patients": 847, "drugs": 12}, ...]

    Level 2 nodes provide patient counts; level 3 node count gives drug count.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Get patient counts from level 2 nodes
        level2_query = """
            SELECT labels AS name, SUM(value) AS patients
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 2
                AND labels IS NOT NULL AND labels != ''
            GROUP BY labels
        """
        level2_rows = conn.execute(level2_query, (date_filter_id, chart_type)).fetchall()

        # Get drug counts from level 3 nodes grouped by directory
        level3_query = """
            SELECT directory, COUNT(DISTINCT labels) AS drug_count
            FROM pathway_nodes
            WHERE date_filter_id = ? AND chart_type = ? AND level = 3
                AND directory IS NOT NULL AND directory != ''
            GROUP BY directory
        """
        level3_rows = conn.execute(level3_query, (date_filter_id, chart_type)).fetchall()
        drug_counts = {r["directory"]: r["drug_count"] for r in level3_rows}

        result = []
        for r in level2_rows:
            name = r["name"]
            patients = r["patients"] or 0
            if patients == 0:
                continue
            result.append({
                "name": name,
                "patients": patients,
                "drugs": drug_counts.get(name, 0),
            })

        result.sort(key=lambda x: x["patients"], reverse=True)
        return result
    except sqlite3.Error:
        return []
    finally:
        conn.close()
