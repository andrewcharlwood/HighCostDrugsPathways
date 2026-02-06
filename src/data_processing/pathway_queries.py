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

        # Total patients from default root node (fallback when source_row_count is empty)
        total_patients = 0
        if not total_records:
            cursor.execute("""
                SELECT value FROM pathway_nodes
                WHERE level = 0 AND date_filter_id = 'all_6mo' AND chart_type = 'directory'
                LIMIT 1
            """)
            root_row = cursor.fetchone()
            total_patients = (root_row[0] or 0) if root_row else 0

        return {
            "available_drugs": available_drugs,
            "available_directorates": available_directorates,
            "available_indications": available_indications,
            "available_trusts": available_trusts,
            "total_records": total_records,
            "total_patients": total_patients,
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

        nodes = []
        root_patients = 0
        root_cost = 0.0

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


def _empty_result(error: str = "") -> dict:
    return {
        "nodes": [],
        "unique_patients": 0,
        "total_drugs": 0,
        "total_cost": 0.0,
        "last_updated": "",
        "error": error,
    }
