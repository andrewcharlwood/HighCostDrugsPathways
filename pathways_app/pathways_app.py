"""
HCD Analysis v2 - Redesigned Reflex Application.

Single-page dashboard with reactive filtering and real-time chart updates.
Design reference: DESIGN_SYSTEM.md
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import reflex as rx

from pathways_app.styles import (
    Colors,
    Typography,
    Spacing,
    Radii,
    Shadows,
    Transitions,
    TOP_BAR_HEIGHT,
    FILTER_STRIP_HEIGHT,
    PAGE_MAX_WIDTH,
    PAGE_PADDING,
    card_style,
    input_style,
    text_h1,
    text_h3,
    text_caption,
    button_ghost_style,
    kpi_card_style,
    kpi_value_style,
    kpi_label_style,
    # v2.1 compact styles
    filter_strip_style,
    compact_dropdown_trigger_style,
    searchable_dropdown_panel_style,
    searchable_dropdown_item_style,
)


# =============================================================================
# State
# =============================================================================

class AppState(rx.State):
    """
    Application state for HCD Analysis v2.

    This is a minimal placeholder state for the app skeleton.
    Will be expanded in Phase 3 with full filter state and data management.
    """

    # =========================================================================
    # Data State Variables
    # =========================================================================

    # Data loading status
    data_loaded: bool = False
    total_records: int = 0
    chart_loading: bool = False
    error_message: str = ""

    # Data freshness tracking
    last_updated: str = ""  # ISO format timestamp of last data load

    # Raw data storage - list of dicts (Reflex-friendly)
    # Each dict represents a patient record with keys like:
    # UPID, Drug Name, Intervention Date, Price Actual, Directory, etc.
    raw_data: list[dict[str, Any]] = []

    # Latest date in dataset (detected on load, used for "to" date defaults)
    latest_date_in_data: str = ""

    # =========================================================================
    # UI State Variables
    # =========================================================================

    # Placeholder for current chart type (for top bar tabs)
    current_chart: str = "icicle"

    # =========================================================================
    # Filter State Variables
    # =========================================================================

    # Date filter dropdowns (replaces date pickers)
    # These map to pathway_date_filters table: all_6mo, all_12mo, 1yr_6mo, etc.
    selected_initiated: str = "all"  # "all", "1yr", "2yr"
    selected_last_seen: str = "6mo"  # "6mo", "12mo"

    # Available options for date filter dropdowns
    initiated_options: list[dict[str, str]] = [
        {"value": "all", "label": "All years"},
        {"value": "1yr", "label": "Last 1 year"},
        {"value": "2yr", "label": "Last 2 years"},
    ]
    last_seen_options: list[dict[str, str]] = [
        {"value": "6mo", "label": "Last 6 months"},
        {"value": "12mo", "label": "Last 12 months"},
    ]

    # Legacy date filter state (kept for backwards compatibility, will be removed)
    # Filter toggle state
    initiated_filter_enabled: bool = False
    last_seen_filter_enabled: bool = True

    # Date filter values (ISO format strings YYYY-MM-DD)
    # Initiated filter: Defaults empty (filter is OFF by default)
    initiated_from_date: str = ""
    initiated_to_date: str = ""

    # Last Seen filter: Defaults to last 6 months (filter is ON by default)
    # These will be updated on data load to use actual latest date
    last_seen_from_date: str = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    last_seen_to_date: str = datetime.now().strftime("%Y-%m-%d")

    # Available options for dropdowns (populated from data in Phase 3)
    available_drugs: list[str] = ["Drug A", "Drug B", "Drug C", "Drug D", "Drug E"]
    available_indications: list[str] = ["Indication 1", "Indication 2", "Indication 3"]
    available_directorates: list[str] = ["Medical", "Surgical", "Oncology", "Rheumatology"]

    # Selected items (empty = all)
    selected_drugs: list[str] = []
    selected_indications: list[str] = []
    selected_directorates: list[str] = []

    # Search text for dropdowns
    drug_search: str = ""
    indication_search: str = ""
    directorate_search: str = ""

    # Dropdown visibility state
    drug_dropdown_open: bool = False
    indication_dropdown_open: bool = False
    directorate_dropdown_open: bool = False

    # Event handlers for filter toggles
    def toggle_initiated_filter(self):
        """Toggle initiated date filter on/off."""
        self.initiated_filter_enabled = not self.initiated_filter_enabled
        if self.data_loaded:
            self.apply_filters()

    def toggle_last_seen_filter(self):
        """Toggle last seen date filter on/off."""
        self.last_seen_filter_enabled = not self.last_seen_filter_enabled
        if self.data_loaded:
            self.apply_filters()

    # Event handlers for date changes
    def set_initiated_from(self, value: str):
        """Set initiated from date."""
        self.initiated_from_date = value
        if self.data_loaded:
            self.apply_filters()

    def set_initiated_to(self, value: str):
        """Set initiated to date."""
        self.initiated_to_date = value
        if self.data_loaded:
            self.apply_filters()

    def set_last_seen_from(self, value: str):
        """Set last seen from date."""
        self.last_seen_from_date = value
        if self.data_loaded:
            self.apply_filters()

    def set_last_seen_to(self, value: str):
        """Set last seen to date."""
        self.last_seen_to_date = value
        if self.data_loaded:
            self.apply_filters()

    # Event handlers for date filter dropdowns (new pathway_nodes approach)
    def set_initiated_filter(self, value: str):
        """Set initiated filter dropdown value."""
        self.selected_initiated = value
        if self.data_loaded:
            self.load_pathway_data()

    def set_last_seen_filter(self, value: str):
        """Set last seen filter dropdown value."""
        self.selected_last_seen = value
        if self.data_loaded:
            self.load_pathway_data()

    # Computed property for date filter ID
    @rx.var
    def date_filter_id(self) -> str:
        """
        Compute the date_filter_id from selected_initiated and selected_last_seen.

        Returns IDs like: all_6mo, all_12mo, 1yr_6mo, 1yr_12mo, 2yr_6mo, 2yr_12mo
        These match the pathway_date_filters table.
        """
        return f"{self.selected_initiated}_{self.selected_last_seen}"

    # Event handlers for search
    def set_drug_search(self, value: str):
        """Update drug search text."""
        self.drug_search = value

    def set_indication_search(self, value: str):
        """Update indication search text."""
        self.indication_search = value

    def set_directorate_search(self, value: str):
        """Update directorate search text."""
        self.directorate_search = value

    # Event handlers for dropdown visibility
    def toggle_drug_dropdown(self):
        """Toggle drug dropdown visibility."""
        self.drug_dropdown_open = not self.drug_dropdown_open
        # Close other dropdowns
        self.indication_dropdown_open = False
        self.directorate_dropdown_open = False

    def toggle_indication_dropdown(self):
        """Toggle indication dropdown visibility."""
        self.indication_dropdown_open = not self.indication_dropdown_open
        # Close other dropdowns
        self.drug_dropdown_open = False
        self.directorate_dropdown_open = False

    def toggle_directorate_dropdown(self):
        """Toggle directorate dropdown visibility."""
        self.directorate_dropdown_open = not self.directorate_dropdown_open
        # Close other dropdowns
        self.drug_dropdown_open = False
        self.indication_dropdown_open = False

    def close_all_dropdowns(self):
        """Close all dropdowns."""
        self.drug_dropdown_open = False
        self.indication_dropdown_open = False
        self.directorate_dropdown_open = False

    # Event handlers for item selection
    def toggle_drug(self, drug: str):
        """Toggle a drug selection."""
        if drug in self.selected_drugs:
            self.selected_drugs = [d for d in self.selected_drugs if d != drug]
        else:
            self.selected_drugs = self.selected_drugs + [drug]
        if self.data_loaded:
            self.load_pathway_data()

    def toggle_indication(self, indication: str):
        """Toggle an indication selection."""
        if indication in self.selected_indications:
            self.selected_indications = [i for i in self.selected_indications if i != indication]
        else:
            self.selected_indications = self.selected_indications + [indication]
        # Note: Indication filter not yet implemented at database level
        # Will be added when indication-based filtering is required

    def toggle_directorate(self, directorate: str):
        """Toggle a directorate selection."""
        if directorate in self.selected_directorates:
            self.selected_directorates = [d for d in self.selected_directorates if d != directorate]
        else:
            self.selected_directorates = self.selected_directorates + [directorate]
        if self.data_loaded:
            self.load_pathway_data()

    # Select/clear all handlers
    def select_all_drugs(self):
        """Select all available drugs."""
        self.selected_drugs = self.available_drugs.copy()
        if self.data_loaded:
            self.load_pathway_data()

    def clear_all_drugs(self):
        """Clear all drug selections."""
        self.selected_drugs = []
        if self.data_loaded:
            self.load_pathway_data()

    def select_all_indications(self):
        """Select all available indications."""
        self.selected_indications = self.available_indications.copy()
        # Note: Indication filter not yet implemented at database level

    def clear_all_indications(self):
        """Clear all indication selections."""
        self.selected_indications = []
        # Note: Indication filter not yet implemented at database level

    def select_all_directorates(self):
        """Select all available directorates."""
        self.selected_directorates = self.available_directorates.copy()
        if self.data_loaded:
            self.load_pathway_data()

    def clear_all_directorates(self):
        """Clear all directorate selections."""
        self.selected_directorates = []
        if self.data_loaded:
            self.load_pathway_data()

    # Computed vars for filtered options based on search
    @rx.var
    def filtered_drugs(self) -> list[str]:
        """Return drugs filtered by search text."""
        if not self.drug_search:
            return self.available_drugs
        search_lower = self.drug_search.lower()
        return [d for d in self.available_drugs if search_lower in d.lower()]

    @rx.var
    def filtered_indications(self) -> list[str]:
        """Return indications filtered by search text."""
        if not self.indication_search:
            return self.available_indications
        search_lower = self.indication_search.lower()
        return [i for i in self.available_indications if search_lower in i.lower()]

    @rx.var
    def filtered_directorates(self) -> list[str]:
        """Return directorates filtered by search text."""
        if not self.directorate_search:
            return self.available_directorates
        search_lower = self.directorate_search.lower()
        return [d for d in self.available_directorates if search_lower in d.lower()]

    # Computed vars for selection counts
    @rx.var
    def drug_selection_text(self) -> str:
        """Display text for drug selection count."""
        count = len(self.selected_drugs)
        total = len(self.available_drugs)
        if count == 0:
            return f"All {total} drugs"
        return f"{count} of {total} selected"

    @rx.var
    def indication_selection_text(self) -> str:
        """Display text for indication selection count."""
        count = len(self.selected_indications)
        total = len(self.available_indications)
        if count == 0:
            return f"All {total} indications"
        return f"{count} of {total} selected"

    @rx.var
    def directorate_selection_text(self) -> str:
        """Display text for directorate selection count."""
        count = len(self.selected_directorates)
        total = len(self.available_directorates)
        if count == 0:
            return f"All {total} directorates"
        return f"{count} of {total} selected"

    # =========================================================================
    # KPI State Variables
    # =========================================================================

    # Placeholder KPI values (will be computed from filtered data in Phase 3)
    # For now, these are static placeholders that demonstrate reactivity
    unique_patients: int = 0
    total_drugs: int = 0
    total_cost: float = 0.0
    indication_match_rate: float = 0.0

    # Computed KPI display values
    @rx.var
    def unique_patients_display(self) -> str:
        """Format unique patients count for display."""
        if self.unique_patients == 0:
            return "—"
        return f"{self.unique_patients:,}"

    @rx.var
    def total_drugs_display(self) -> str:
        """Format total drugs count for display."""
        if self.total_drugs == 0:
            return "—"
        return f"{self.total_drugs:,}"

    @rx.var
    def total_cost_display(self) -> str:
        """Format total cost for display."""
        if self.total_cost == 0.0:
            return "—"
        # Format as £X.XM or £X.XK depending on magnitude
        if self.total_cost >= 1_000_000:
            return f"£{self.total_cost / 1_000_000:.1f}M"
        if self.total_cost >= 1_000:
            return f"£{self.total_cost / 1_000:.1f}K"
        return f"£{self.total_cost:,.0f}"

    @rx.var
    def match_rate_display(self) -> str:
        """Format indication match rate for display."""
        if self.indication_match_rate == 0.0:
            return "—"
        return f"{self.indication_match_rate:.0f}%"

    @rx.var
    def last_updated_display(self) -> str:
        """Format last updated timestamp for display in top bar."""
        if not self.last_updated:
            return "Never"
        try:
            # Parse ISO format timestamp
            dt = datetime.fromisoformat(self.last_updated)
            now = datetime.now()
            diff = now - dt

            if diff.days == 0:
                if diff.seconds < 60:
                    return "Just now"
                if diff.seconds < 3600:
                    mins = diff.seconds // 60
                    return f"{mins}m ago"
                hours = diff.seconds // 3600
                return f"{hours}h ago"
            if diff.days == 1:
                return "Yesterday"
            if diff.days < 7:
                return f"{diff.days}d ago"
            return dt.strftime("%d %b %Y")
        except (ValueError, TypeError):
            return "Unknown"

    # =========================================================================
    # Filter Logic Methods
    # =========================================================================

    def apply_filters(self):
        """
        Apply current filter state to data and update KPI values.

        This method queries the SQLite database with the current filter settings:
        - Initiated date filter: filters patients whose FIRST intervention date is within range
        - Last Seen date filter: filters patients whose LAST intervention date is within range
        - Drug filter: filters by selected drugs (empty = all)
        - Directorate filter: filters by selected directorates (empty = all)

        Note: Indication filter is not implemented at the database level since indications
        are derived from drug mappings, not stored directly in fact_interventions.

        Updates: unique_patients, total_drugs, total_cost, and filtered_record_count
        """
        import sqlite3

        db_path = Path("data/pathways.db")

        if not db_path.exists():
            self.error_message = "Unable to connect to database. Please ensure data has been loaded."
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Build the filter query dynamically
            # We use a CTE to compute first_seen and last_seen dates per patient,
            # then filter based on those dates if date filters are enabled

            where_clauses = []
            params = []

            # Drug filter (if any drugs selected)
            if self.selected_drugs:
                placeholders = ",".join("?" * len(self.selected_drugs))
                where_clauses.append(f"drug_name_std IN ({placeholders})")
                params.extend(self.selected_drugs)

            # Directorate filter (if any directorates selected)
            if self.selected_directorates:
                placeholders = ",".join("?" * len(self.selected_directorates))
                where_clauses.append(f"directory IN ({placeholders})")
                params.extend(self.selected_directorates)

            # Build WHERE clause for base data filtering
            base_where = ""
            if where_clauses:
                base_where = "WHERE " + " AND ".join(where_clauses)

            # Date filter logic:
            # - "Initiated" filters patients whose FIRST intervention is within the date range
            # - "Last Seen" filters patients whose LAST intervention is within the date range
            # We need to use a subquery to compute patient-level date ranges

            having_clauses = []
            having_params = []

            # Initiated filter (when enabled)
            if self.initiated_filter_enabled and self.initiated_from_date:
                having_clauses.append("first_seen_date >= ?")
                having_params.append(self.initiated_from_date)
            if self.initiated_filter_enabled and self.initiated_to_date:
                having_clauses.append("first_seen_date <= ?")
                having_params.append(self.initiated_to_date)

            # Last Seen filter (when enabled)
            if self.last_seen_filter_enabled and self.last_seen_from_date:
                having_clauses.append("last_seen_date >= ?")
                having_params.append(self.last_seen_from_date)
            if self.last_seen_filter_enabled and self.last_seen_to_date:
                having_clauses.append("last_seen_date <= ?")
                having_params.append(self.last_seen_to_date)

            having_clause = ""
            if having_clauses:
                having_clause = "HAVING " + " AND ".join(having_clauses)

            # Query to get filtered patient UPIDs
            # This computes per-patient first/last seen dates and filters accordingly
            patient_filter_query = f"""
                WITH patient_dates AS (
                    SELECT
                        upid,
                        MIN(intervention_date) as first_seen_date,
                        MAX(intervention_date) as last_seen_date
                    FROM fact_interventions
                    {base_where}
                    GROUP BY upid
                    {having_clause}
                )
                SELECT upid FROM patient_dates
            """

            # Now get KPI values for filtered patients
            kpi_query = f"""
                WITH filtered_patients AS (
                    {patient_filter_query}
                )
                SELECT
                    COUNT(DISTINCT f.upid) as unique_patients,
                    COUNT(DISTINCT f.drug_name_std) as unique_drugs,
                    COALESCE(SUM(f.price_actual), 0) as total_cost,
                    COUNT(*) as record_count
                FROM fact_interventions f
                INNER JOIN filtered_patients fp ON f.upid = fp.upid
                {base_where.replace('WHERE', 'AND') if base_where else ''}
            """

            # Combine all params: base params for CTE, having params, then base params again for final join
            all_params = params + having_params
            if where_clauses:
                all_params.extend(params)  # For the AND conditions in the final query

            cursor.execute(kpi_query, all_params)
            result = cursor.fetchone()

            if result:
                self.unique_patients = result[0] or 0
                self.total_drugs = result[1] or 0
                self.total_cost = float(result[2]) if result[2] else 0.0
                # Note: filtered_record_count could be stored if needed

            conn.close()
            self.error_message = ""

            # Update chart data with new filtered results
            self.prepare_chart_data()

        except sqlite3.Error as e:
            self.error_message = f"Unable to filter data. Database error: {str(e)}"
        except Exception as e:
            self.error_message = f"An unexpected error occurred while filtering. Details: {str(e)}"

    # =========================================================================
    # Data Loading Methods
    # =========================================================================

    def load_data(self):
        """
        Load data from SQLite database on app initialization.

        This method:
        1. Connects to the SQLite database (data/pathways.db)
        2. Loads available drugs, indications, directorates from actual data
        3. Detects the latest date in the dataset for "to" date defaults
        4. Updates total_records, last_updated, and data_loaded state
        """
        import sqlite3

        db_path = Path("data/pathways.db")

        if not db_path.exists():
            self.error_message = "Database not found. Please ensure the data has been loaded (data/pathways.db)."
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Get total records
            cursor.execute("SELECT COUNT(*) FROM fact_interventions")
            self.total_records = cursor.fetchone()[0]

            if self.total_records == 0:
                self.error_message = "The database is empty. No patient records found."
                conn.close()
                return

            # Get available drugs (distinct, sorted)
            cursor.execute("""
                SELECT DISTINCT drug_name_std
                FROM fact_interventions
                WHERE drug_name_std IS NOT NULL AND drug_name_std != ''
                ORDER BY drug_name_std
            """)
            self.available_drugs = [row[0] for row in cursor.fetchall()]

            # Get available directories (distinct, sorted)
            cursor.execute("""
                SELECT DISTINCT directory
                FROM fact_interventions
                WHERE directory IS NOT NULL AND directory != ''
                ORDER BY directory
            """)
            self.available_directorates = [row[0] for row in cursor.fetchall()]

            # Get available indications from ref_drug_indication_clusters
            cursor.execute("""
                SELECT DISTINCT indication
                FROM ref_drug_indication_clusters
                WHERE indication IS NOT NULL AND indication != ''
                ORDER BY indication
            """)
            self.available_indications = [row[0] for row in cursor.fetchall()]

            # If no indications in reference table, use placeholder
            if not self.available_indications:
                self.available_indications = ["(No indications available)"]

            # Get date range from data
            cursor.execute("""
                SELECT MIN(intervention_date), MAX(intervention_date)
                FROM fact_interventions
            """)
            date_range = cursor.fetchone()
            min_date, max_date = date_range

            # Update latest_date_in_data and set "to" date defaults
            if max_date:
                self.latest_date_in_data = max_date
                self.last_seen_to_date = max_date
                self.initiated_to_date = max_date

                # Set "from" date for last_seen filter (6 months before max_date)
                max_dt = datetime.strptime(max_date, "%Y-%m-%d")
                six_months_ago = max_dt - timedelta(days=180)
                self.last_seen_from_date = six_months_ago.strftime("%Y-%m-%d")

            # Get unique patient count for KPIs
            cursor.execute("SELECT COUNT(DISTINCT upid) FROM fact_interventions")
            self.unique_patients = cursor.fetchone()[0]

            # Get unique drug count
            self.total_drugs = len(self.available_drugs)

            # Get total cost
            cursor.execute("SELECT SUM(price_actual) FROM fact_interventions")
            total_cost_result = cursor.fetchone()[0]
            self.total_cost = float(total_cost_result) if total_cost_result else 0.0

            conn.close()

            # Set data_loaded and last_updated
            self.data_loaded = True
            self.last_updated = datetime.now().isoformat()
            self.error_message = ""

            # Load pre-computed pathway data for the default date filter
            # This replaces apply_filters() which used dynamic calculation
            self.load_pathway_data()

        except sqlite3.Error as e:
            self.error_message = f"Unable to load data. Database error: {str(e)}"
            self.data_loaded = False
        except Exception as e:
            self.error_message = f"Failed to load data. Please check the database file. Details: {str(e)}"
            self.data_loaded = False

    def load_pathway_data(self):
        """
        Load pre-computed pathway data from pathway_nodes table.

        This method queries the pathway_nodes table using the current date_filter_id
        and applies trust/directory/drug filters. It replaces the dynamic calculation
        approach with pre-computed data for faster performance.

        Filters:
        - date_filter_id: Computed from selected_initiated + selected_last_seen
        - trust filter: Uses denormalized trust_name column
        - directory filter: Uses denormalized directory column
        - drug filter: Uses drug_sequence column with LIKE patterns
        """
        import sqlite3

        db_path = Path("data/pathways.db")

        if not db_path.exists():
            self.error_message = "Database not found. Please ensure the data has been loaded (data/pathways.db)."
            return

        self.chart_loading = True

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()

            # Build the date filter ID
            filter_id = f"{self.selected_initiated}_{self.selected_last_seen}"

            # Build WHERE clause for filters
            where_clauses = ["date_filter_id = ?"]
            params = [filter_id]

            # Trust filter (if any directorates selected, they map to trust_name)
            # Note: In the schema, trust_name is extracted from the hierarchy
            # For now, we filter at the directory level since that's what users select

            # Directory filter (if any directorates selected)
            if self.selected_directorates:
                placeholders = ",".join("?" * len(self.selected_directorates))
                where_clauses.append(f"(directory IN ({placeholders}) OR directory IS NULL)")
                params.extend(self.selected_directorates)

            # Drug filter (if any drugs selected)
            # Drug names appear in the drug_sequence column, use LIKE for matching
            if self.selected_drugs:
                drug_conditions = []
                for drug in self.selected_drugs:
                    drug_conditions.append("drug_sequence LIKE ?")
                    params.append(f"%{drug}%")
                where_clauses.append(f"({' OR '.join(drug_conditions)} OR drug_sequence IS NULL)")

            where_clause = " AND ".join(where_clauses)

            # Query pathway nodes for the selected date filter
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
                # No data for this filter combination
                self.chart_data = []
                self.unique_patients = 0
                self.total_drugs = 0
                self.total_cost = 0.0
                self.chart_loading = False
                self.error_message = f"No pathway data found for filter: {filter_id}"
                conn.close()
                return

            # Convert rows to chart_data format
            chart_data = []
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
                    # Additional fields for hover template
                    "first_seen": row["first_seen"] or "",
                    "last_seen": row["last_seen"] or "",
                    "first_seen_parent": row["first_seen_parent"] or "",
                    "last_seen_parent": row["last_seen_parent"] or "",
                    "average_spacing": row["average_spacing"] or "",
                    "cost_pp_pa": row["cost_pp_pa"] or "",
                }
                chart_data.append(node)

                # Track root node for KPIs (level 0)
                if row["level"] == 0:
                    root_patients = row["value"] or 0
                    root_cost = float(row["cost"]) if row["cost"] else 0.0

            self.chart_data = chart_data

            # Update KPIs from root node
            self.unique_patients = root_patients
            self.total_cost = root_cost

            # Count unique drugs from level 3+ nodes
            drug_nodes = [r for r in rows if r["level"] >= 3]
            unique_drugs = set()
            for r in drug_nodes:
                if r["drug_sequence"]:
                    # drug_sequence is pipe-separated
                    for drug in r["drug_sequence"].split("|"):
                        if drug:
                            unique_drugs.add(drug)
            self.total_drugs = len(unique_drugs)

            # Get data freshness from pathway_refresh_log
            cursor.execute("""
                SELECT completed_at
                FROM pathway_refresh_log
                WHERE status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            """)
            refresh_row = cursor.fetchone()
            if refresh_row and refresh_row["completed_at"]:
                self.last_updated = refresh_row["completed_at"]

            # Update chart title
            self.chart_title = self._generate_pathway_chart_title()

            conn.close()
            self.chart_loading = False
            self.error_message = ""

        except sqlite3.Error as e:
            self.error_message = f"Unable to load pathway data. Database error: {str(e)}"
            self.chart_data = []
            self.chart_loading = False
        except Exception as e:
            self.error_message = f"Failed to load pathway data. Details: {str(e)}"
            self.chart_data = []
            self.chart_loading = False

    def _generate_pathway_chart_title(self) -> str:
        """Generate chart title based on current pathway filter state."""
        parts = []

        # Date filter info
        initiated_label = "All years"
        if self.selected_initiated == "1yr":
            initiated_label = "Last 1 year"
        elif self.selected_initiated == "2yr":
            initiated_label = "Last 2 years"

        last_seen_label = "Last 6 months" if self.selected_last_seen == "6mo" else "Last 12 months"
        parts.append(f"{initiated_label} / {last_seen_label}")

        # Drug selection info
        if self.selected_drugs:
            if len(self.selected_drugs) <= 3:
                parts.append(", ".join(self.selected_drugs))
            else:
                parts.append(f"{len(self.selected_drugs)} drugs selected")

        # Directorate selection info
        if self.selected_directorates:
            if len(self.selected_directorates) <= 2:
                parts.append(", ".join(self.selected_directorates))
            else:
                parts.append(f"{len(self.selected_directorates)} directorates")

        if parts:
            return " | ".join(parts)
        return "All Patients"

    def recalculate_parent_totals(self):
        """
        Recalculate parent node totals after filtering.

        When trust/directory/drug filters are applied, the parent nodes
        (root, trust, directory) need their totals recalculated to sum
        only the visible children.

        This method walks up the hierarchy and recalculates values.
        """
        if not self.chart_data:
            return

        # Build parent-child relationships
        children_by_parent = {}
        nodes_by_id = {}

        for node in self.chart_data:
            node_id = node["ids"]
            parent_id = node["parents"]
            nodes_by_id[node_id] = node

            if parent_id not in children_by_parent:
                children_by_parent[parent_id] = []
            children_by_parent[parent_id].append(node)

        # Recalculate from bottom up
        # Find all leaf nodes (nodes with no children)
        all_ids = set(nodes_by_id.keys())
        parent_ids = set(children_by_parent.keys())
        leaf_ids = all_ids - parent_ids

        # Walk up from leaves, recalculating parent totals
        processed = set()
        to_process = list(leaf_ids)

        while to_process:
            node_id = to_process.pop(0)
            if node_id in processed or node_id not in nodes_by_id:
                continue

            node = nodes_by_id[node_id]
            parent_id = node["parents"]

            if parent_id and parent_id in nodes_by_id:
                parent = nodes_by_id[parent_id]
                # Sum children's values
                children = children_by_parent.get(parent_id, [])
                parent["value"] = sum(c["value"] for c in children)
                parent["cost"] = sum(c["cost"] for c in children)

                # Recalculate colour (proportion of grandparent)
                grandparent_id = parent["parents"]
                if grandparent_id and grandparent_id in nodes_by_id:
                    grandparent_value = nodes_by_id[grandparent_id]["value"]
                    if grandparent_value > 0:
                        parent["colour"] = parent["value"] / grandparent_value

                # Queue parent for processing
                if parent_id not in processed:
                    to_process.append(parent_id)

            processed.add(node_id)

        # Update the chart_data list
        self.chart_data = list(nodes_by_id.values())

        # Update KPIs from root
        for node in self.chart_data:
            if node["parents"] == "":  # Root node
                self.unique_patients = node["value"]
                self.total_cost = node["cost"]
                break

    # =========================================================================
    # Chart Data Preparation Methods
    # =========================================================================

    # Chart data stored as list of dicts for Reflex serialization
    # Structure: [{"parents": str, "ids": str, "labels": str, "value": int, "cost": float, "colour": float}, ...]
    chart_data: list[dict[str, Any]] = []
    chart_title: str = ""

    def prepare_chart_data(self):
        """
        Prepare hierarchical data for Plotly icicle chart.

        This method queries the filtered patient data and transforms it into
        a hierarchical structure: Root → Trust → Directory → Drug

        The chart data is stored in self.chart_data as a list of dicts with:
        - parents: Parent node identifier
        - ids: Unique node identifier (hierarchical path)
        - labels: Display label
        - value: Patient count
        - cost: Total cost
        - colour: Color value (proportion of parent)

        Updates: chart_data, chart_title, chart_loading
        """
        import sqlite3

        db_path = Path("data/pathways.db")

        if not db_path.exists():
            self.error_message = "Unable to generate chart. Database not found."
            self.chart_data = []
            return

        self.chart_loading = True

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Build WHERE clause for filters
            where_clauses = []
            params = []

            # Drug filter (if any drugs selected)
            if self.selected_drugs:
                placeholders = ",".join("?" * len(self.selected_drugs))
                where_clauses.append(f"drug_name_std IN ({placeholders})")
                params.extend(self.selected_drugs)

            # Directorate filter (if any directorates selected)
            if self.selected_directorates:
                placeholders = ",".join("?" * len(self.selected_directorates))
                where_clauses.append(f"directory IN ({placeholders})")
                params.extend(self.selected_directorates)

            base_where = ""
            if where_clauses:
                base_where = "WHERE " + " AND ".join(where_clauses)

            # Build date filter HAVING clauses for patient-level filtering
            having_clauses = []
            having_params = []

            if self.initiated_filter_enabled and self.initiated_from_date:
                having_clauses.append("first_seen >= ?")
                having_params.append(self.initiated_from_date)
            if self.initiated_filter_enabled and self.initiated_to_date:
                having_clauses.append("first_seen <= ?")
                having_params.append(self.initiated_to_date)

            if self.last_seen_filter_enabled and self.last_seen_from_date:
                having_clauses.append("last_seen >= ?")
                having_params.append(self.last_seen_from_date)
            if self.last_seen_filter_enabled and self.last_seen_to_date:
                having_clauses.append("last_seen <= ?")
                having_params.append(self.last_seen_to_date)

            having_clause = ""
            if having_clauses:
                having_clause = "HAVING " + " AND ".join(having_clauses)

            # Query to get aggregated data by Trust -> Directory -> Drug
            # fact_interventions already has org_name, use it directly
            chart_query = f"""
                WITH filtered_patients AS (
                    SELECT upid
                    FROM (
                        SELECT
                            upid,
                            MIN(intervention_date) as first_seen,
                            MAX(intervention_date) as last_seen
                        FROM fact_interventions
                        {base_where}
                        GROUP BY upid
                        {having_clause}
                    )
                ),
                patient_records AS (
                    SELECT
                        f.upid,
                        COALESCE(f.org_name, f.provider_code) as trust_name,
                        f.directory,
                        f.drug_name_std,
                        f.price_actual
                    FROM fact_interventions f
                    INNER JOIN filtered_patients fp ON f.upid = fp.upid
                    {base_where.replace('WHERE', 'AND') if base_where else ''}
                )
                SELECT
                    trust_name,
                    directory,
                    drug_name_std,
                    COUNT(DISTINCT upid) as patient_count,
                    COALESCE(SUM(price_actual), 0) as total_cost
                FROM patient_records
                GROUP BY trust_name, directory, drug_name_std
                ORDER BY trust_name, directory, drug_name_std
            """

            all_params = params + having_params
            if where_clauses:
                all_params.extend(params)

            cursor.execute(chart_query, all_params)
            rows = cursor.fetchall()

            conn.close()

            # Build hierarchical chart data
            chart_data = []
            hierarchy_totals = {}  # Track totals for calculating color values

            # Root node
            root_id = "N&WICS"
            chart_data.append({
                "parents": "",
                "ids": root_id,
                "labels": "Norfolk & Waveney ICS",
                "value": 0,
                "cost": 0.0,
                "colour": 1.0,
            })

            # Process rows to build hierarchy
            trust_totals = {}
            directory_totals = {}
            drug_data = []

            for row in rows:
                trust_name, directory, drug_name, patient_count, cost = row

                if not trust_name or not directory or not drug_name:
                    continue

                # Trust level
                trust_id = f"{root_id} - {trust_name}"
                if trust_id not in trust_totals:
                    trust_totals[trust_id] = {"value": 0, "cost": 0.0, "label": trust_name}
                trust_totals[trust_id]["value"] += patient_count
                trust_totals[trust_id]["cost"] += cost

                # Directory level
                dir_id = f"{trust_id} - {directory}"
                if dir_id not in directory_totals:
                    directory_totals[dir_id] = {
                        "value": 0,
                        "cost": 0.0,
                        "label": directory,
                        "parent": trust_id,
                    }
                directory_totals[dir_id]["value"] += patient_count
                directory_totals[dir_id]["cost"] += cost

                # Drug level (leaf)
                drug_id = f"{dir_id} - {drug_name}"
                drug_data.append({
                    "ids": drug_id,
                    "labels": drug_name,
                    "parent": dir_id,
                    "value": patient_count,
                    "cost": float(cost),
                })

            # Calculate root total
            root_total = sum(t["value"] for t in trust_totals.values())
            root_cost = sum(t["cost"] for t in trust_totals.values())
            chart_data[0]["value"] = root_total
            chart_data[0]["cost"] = root_cost

            # Add trust nodes with color proportions
            for trust_id, data in trust_totals.items():
                colour = data["value"] / root_total if root_total > 0 else 0
                chart_data.append({
                    "parents": root_id,
                    "ids": trust_id,
                    "labels": data["label"],
                    "value": data["value"],
                    "cost": data["cost"],
                    "colour": colour,
                })

            # Add directory nodes with color proportions
            for dir_id, data in directory_totals.items():
                parent_total = trust_totals[data["parent"]]["value"]
                colour = data["value"] / parent_total if parent_total > 0 else 0
                chart_data.append({
                    "parents": data["parent"],
                    "ids": dir_id,
                    "labels": data["label"],
                    "value": data["value"],
                    "cost": data["cost"],
                    "colour": colour,
                })

            # Add drug nodes with color proportions
            for drug in drug_data:
                parent_dir = drug["parent"]
                parent_total = directory_totals[parent_dir]["value"]
                colour = drug["value"] / parent_total if parent_total > 0 else 0
                chart_data.append({
                    "parents": parent_dir,
                    "ids": drug["ids"],
                    "labels": drug["labels"],
                    "value": drug["value"],
                    "cost": drug["cost"],
                    "colour": colour,
                })

            self.chart_data = chart_data
            self.chart_title = self._generate_chart_title()
            self.chart_loading = False
            self.error_message = ""

        except sqlite3.Error as e:
            self.error_message = f"Unable to generate chart. Database error: {str(e)}"
            self.chart_data = []
            self.chart_loading = False
        except Exception as e:
            self.error_message = f"Unable to generate chart. Details: {str(e)}"
            self.chart_data = []
            self.chart_loading = False

    def _generate_chart_title(self) -> str:
        """Generate chart title based on current filter state."""
        parts = []

        # Date range info
        if self.last_seen_filter_enabled:
            parts.append(f"Last seen: {self.last_seen_from_date} to {self.last_seen_to_date}")
        elif self.initiated_filter_enabled:
            parts.append(f"Initiated: {self.initiated_from_date} to {self.initiated_to_date}")

        # Drug selection info
        if self.selected_drugs:
            if len(self.selected_drugs) <= 3:
                parts.append(", ".join(self.selected_drugs))
            else:
                parts.append(f"{len(self.selected_drugs)} drugs selected")

        # Directorate selection info
        if self.selected_directorates:
            if len(self.selected_directorates) <= 2:
                parts.append(", ".join(self.selected_directorates))
            else:
                parts.append(f"{len(self.selected_directorates)} directorates")

        if parts:
            return " | ".join(parts)
        return "All Patients"

    # =========================================================================
    # Plotly Chart Generation
    # =========================================================================

    @rx.var
    def icicle_figure(self) -> go.Figure:
        """
        Generate Plotly icicle chart from chart_data.

        This computed property creates a go.Figure with the hierarchical icicle chart
        using data from load_pathway_data(). The chart displays patient pathways:
        Root → Trust → Directory → Drug → Pathway

        Uses the full 10-field customdata structure matching the original
        visualization/plotly_generator.py:
        [0] value - patient count
        [1] colour - proportion of parent
        [2] cost - total cost
        [3] costpp - cost per patient
        [4] first_seen - first intervention date
        [5] last_seen - last intervention date
        [6] first_seen_parent - earliest date in parent group
        [7] last_seen_parent - latest date in parent group
        [8] average_spacing - dosing information string
        [9] cost_pp_pa - cost per patient per annum

        Returns:
            Plotly Figure object ready for rx.plotly() component
        """
        # Return empty figure if no data
        if not self.chart_data:
            return go.Figure()

        # Extract lists from chart_data
        parents = [d.get("parents", "") for d in self.chart_data]
        ids = [d.get("ids", "") for d in self.chart_data]
        labels = [d.get("labels", "") for d in self.chart_data]
        values = [d.get("value", 0) for d in self.chart_data]
        colours = [d.get("colour", 0.0) for d in self.chart_data]

        # Extract full 10-field customdata
        costs = [d.get("cost", 0.0) for d in self.chart_data]
        costpp = [d.get("costpp", 0.0) for d in self.chart_data]
        first_seen = [d.get("first_seen", "N/A") or "N/A" for d in self.chart_data]
        last_seen = [d.get("last_seen", "N/A") or "N/A" for d in self.chart_data]
        first_seen_parent = [d.get("first_seen_parent", "N/A") or "N/A" for d in self.chart_data]
        last_seen_parent = [d.get("last_seen_parent", "N/A") or "N/A" for d in self.chart_data]
        average_spacing = [d.get("average_spacing", "") or "" for d in self.chart_data]
        cost_pp_pa = [d.get("cost_pp_pa", 0.0) or 0.0 for d in self.chart_data]

        # Build customdata as list of tuples (10 fields)
        customdata = list(zip(
            values,              # [0]
            colours,             # [1]
            costs,               # [2]
            costpp,              # [3]
            first_seen,          # [4]
            last_seen,           # [5]
            first_seen_parent,   # [6]
            last_seen_parent,    # [7]
            average_spacing,     # [8]
            cost_pp_pa,          # [9]
        ))

        # NHS-inspired blue gradient colorscale (from design system)
        # Heritage Blue → Primary Blue → Vibrant Blue → Sky Blue → Pale Blue
        colorscale = [
            [0.0, "#003087"],   # Heritage Blue
            [0.25, "#0066CC"],  # Primary Blue
            [0.5, "#1E88E5"],   # Vibrant Blue
            [0.75, "#4FC3F7"],  # Sky Blue
            [1.0, "#E3F2FD"],   # Pale Blue
        ]

        # Create the icicle chart with full customdata structure
        fig = go.Figure(
            go.Icicle(
                labels=labels,
                ids=ids,
                parents=parents,
                values=values,
                branchvalues="total",
                marker=dict(
                    colors=colours,
                    colorscale=colorscale,
                    line=dict(width=1, color="#FFFFFF"),
                ),
                maxdepth=3,
                customdata=customdata,
                # Text shown on chart segments - includes treatment statistics
                texttemplate=(
                    "<b>%{label}</b> "
                    "<br><b>Total patients:</b> %{customdata[0]} (including children/further treatments)"
                    "<br><b>First seen:</b> %{customdata[4]}"
                    "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
                    "<br><b>Average treatment duration:</b> %{customdata[8]}"
                    "<br><b>Total cost:</b> £%{customdata[2]:.3~s}"
                    "<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}"
                    "<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}"
                ),
                # Hover text with full details matching original chart
                hovertemplate=(
                    "<b>%{label}</b>"
                    "<br><b>Total patients:</b> %{customdata[0]} - %{customdata[1]:.3p} of patients in level"
                    "<br><b>Total cost:</b> £%{customdata[2]:.3~s}"
                    "<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}"
                    "<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}"
                    "<br><b>First seen:</b> %{customdata[4]}"
                    "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
                    "<br><b>Average treatment duration:</b>"
                    "%{customdata[8]}"
                    "<extra></extra>"
                ),
                textfont=dict(
                    family="Inter, system-ui, sans-serif",
                    size=12,
                ),
            )
        )

        # Configure layout
        fig.update_layout(
            title=dict(
                text=f"Patient Pathways — {self.chart_title}",
                font=dict(
                    family="Inter, system-ui, sans-serif",
                    size=18,
                    color="#1E293B",  # Slate 900
                ),
                x=0.5,
                xanchor="center",
            ),
            margin=dict(t=60, l=10, r=10, b=30),
            hoverlabel=dict(
                bgcolor="#FFFFFF",
                bordercolor="#CBD5E1",  # Slate 300
                font=dict(
                    family="Inter, system-ui, sans-serif",
                    size=14,
                    color="#1E293B",  # Slate 900
                ),
            ),
            paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
            plot_bgcolor="rgba(0,0,0,0)",
            # Responsive sizing - height set but width auto
            height=600,
            # Enable interactivity
            clickmode="event+select",
        )

        # Disable sort to maintain hierarchy order
        fig.update_traces(sort=False)

        return fig


# =============================================================================
# Layout Components
# =============================================================================

def initiated_filter_dropdown() -> rx.Component:
    """
    Compact dropdown for selecting the treatment initiated time period.

    Redesigned for v2.1 filter strip - single row, no external label.
    Options: All years, Last 2 years, Last 1 year
    Values: "all", "2yr", "1yr"
    """
    return rx.select.root(
        rx.select.trigger(
            placeholder="Initiated...",
            **compact_dropdown_trigger_style(),
        ),
        rx.select.content(
            rx.select.group(
                rx.select.label("Treatment Initiated"),
                rx.select.item("All years", value="all"),
                rx.select.item("Last 2 years", value="2yr"),
                rx.select.item("Last 1 year", value="1yr"),
            ),
        ),
        value=AppState.selected_initiated,
        on_change=AppState.set_initiated_filter,
        size="1",
    )


def last_seen_filter_dropdown() -> rx.Component:
    """
    Compact dropdown for selecting the last seen time period.

    Redesigned for v2.1 filter strip - single row, no external label.
    Options: Last 6 months, Last 12 months
    Values: "6mo", "12mo"
    """
    return rx.select.root(
        rx.select.trigger(
            placeholder="Last seen...",
            **compact_dropdown_trigger_style(),
        ),
        rx.select.content(
            rx.select.group(
                rx.select.label("Last Seen"),
                rx.select.item("Last 6 months", value="6mo"),
                rx.select.item("Last 12 months", value="12mo"),
            ),
        ),
        value=AppState.selected_last_seen,
        on_change=AppState.set_last_seen_filter,
        size="1",
    )


def searchable_dropdown(
    label: str,
    selection_text: rx.Var[str],
    is_open: rx.Var[bool],
    toggle_handler,
    search_value: rx.Var[str],
    on_search_change,
    filtered_items: rx.Var[list[str]],
    selected_items: rx.Var[list[str]],
    toggle_item_handler,
    select_all_handler,
    clear_all_handler,
) -> rx.Component:
    """
    Compact searchable multi-select dropdown component.

    Redesigned for v2.1 filter strip - 32px trigger, no external label.
    Uses debounced search input (300ms) for smooth filtering.

    Args:
        label: Label shown inside dropdown panel header
        selection_text: Text showing selection count
        is_open: Whether dropdown is expanded
        toggle_handler: Handler to toggle dropdown open/close
        search_value: Current search text
        on_search_change: Handler for search input change
        filtered_items: Items filtered by search
        selected_items: Currently selected items
        toggle_item_handler: Handler to toggle item selection
        select_all_handler: Handler to select all
        clear_all_handler: Handler to clear selection
    """
    return rx.box(
        # Compact trigger button (no external label)
        rx.box(
            rx.hstack(
                rx.text(
                    selection_text,
                    font_size=Typography.BODY_SMALL_SIZE,
                    color=Colors.SLATE_900,
                    font_family=Typography.FONT_FAMILY,
                    flex="1",
                    white_space="nowrap",
                    overflow="hidden",
                    text_overflow="ellipsis",
                ),
                rx.icon(
                    rx.cond(is_open, "chevron-up", "chevron-down"),
                    size=14,
                    color=Colors.SLATE_500,
                ),
                justify="between",
                align="center",
                gap=Spacing.SM,
            ),
            **compact_dropdown_trigger_style(),
            on_click=toggle_handler,
            min_width="120px",
        ),
        # Dropdown panel
        rx.cond(
            is_open,
            rx.box(
                rx.vstack(
                    # Header with label
                    rx.text(
                        label,
                        font_size=Typography.CAPTION_SIZE,
                        font_weight=Typography.CAPTION_WEIGHT,
                        color=Colors.SLATE_500,
                        font_family=Typography.FONT_FAMILY,
                        padding_x=Spacing.MD,
                        padding_top=Spacing.SM,
                    ),
                    # Search input (debounced 300ms)
                    rx.hstack(
                        rx.icon("search", size=12, color=Colors.SLATE_500),
                        rx.debounce_input(
                            rx.input(
                                placeholder="Search...",
                                value=search_value,
                                on_change=on_search_change,
                                variant="soft",
                                size="1",
                                width="100%",
                            ),
                            debounce_timeout=300,
                        ),
                        spacing="1",
                        align="center",
                        width="100%",
                        padding_x=Spacing.SM,
                    ),
                    # Action buttons (more compact)
                    rx.hstack(
                        rx.button(
                            "All",
                            on_click=select_all_handler,
                            variant="ghost",
                            size="1",
                            color_scheme="blue",
                        ),
                        rx.button(
                            "None",
                            on_click=clear_all_handler,
                            variant="ghost",
                            size="1",
                            color_scheme="gray",
                        ),
                        spacing="1",
                        padding_x=Spacing.SM,
                    ),
                    # Items list (reduced height)
                    rx.box(
                        rx.foreach(
                            filtered_items,
                            lambda item: rx.box(
                                rx.checkbox(
                                    item,
                                    checked=selected_items.contains(item),
                                    on_change=lambda: toggle_item_handler(item),
                                    size="1",
                                ),
                                padding=f"{Spacing.SM} {Spacing.MD}",
                                font_size=Typography.BODY_SMALL_SIZE,
                                cursor="pointer",
                                background_color=rx.cond(
                                    selected_items.contains(item),
                                    Colors.PALE,
                                    "transparent",
                                ),
                                _hover={
                                    "background_color": Colors.SLATE_100,
                                },
                                width="100%",
                            ),
                        ),
                        max_height="150px",
                        overflow_y="auto",
                        width="100%",
                    ),
                    spacing="1",
                    align="start",
                    width="100%",
                    padding_bottom=Spacing.SM,
                ),
                **searchable_dropdown_panel_style(),
                position="absolute",
                top="100%",
                left="0",
                margin_top=Spacing.XS,
            ),
        ),
        position="relative",
    )


def chart_tab(label: str, chart_type: str, is_active: bool = False) -> rx.Component:
    """
    Individual chart type tab/pill for top bar navigation.

    Active state: White background with Heritage Blue text
    Inactive state: Transparent with white text, hover shows Vibrant Blue background
    """
    return rx.box(
        rx.text(
            label,
            font_size=Typography.BODY_SMALL_SIZE,
            font_weight="500",
            color=Colors.HERITAGE_BLUE if is_active else Colors.WHITE,
            font_family=Typography.FONT_FAMILY,
        ),
        background_color=Colors.WHITE if is_active else "transparent",
        padding_x=Spacing.LG,
        padding_y=Spacing.SM,
        border_radius=Radii.FULL,
        cursor="pointer",
        transition=f"background-color {Transitions.COLOR}",
        _hover={
            "background_color": Colors.WHITE if is_active else "rgba(255,255,255,0.15)",
        },
        # Future: on_click handler to switch chart type
    )


def top_bar() -> rx.Component:
    """
    Top navigation bar component.

    Contains: Logo + App Name | Chart Type Tabs | Data Freshness Indicator
    Fixed height: 64px (from design system)
    Heritage Blue background with white text.
    """
    return rx.box(
        rx.hstack(
            # Left: Logo and App Title
            rx.hstack(
                rx.image(
                    src="/logo.png",
                    height="36px",
                    alt="NHS Logo",
                ),
                rx.text(
                    "HCD Analysis",
                    font_size=Typography.H2_SIZE,
                    font_weight=Typography.H2_WEIGHT,
                    color=Colors.WHITE,
                    font_family=Typography.FONT_FAMILY,
                    letter_spacing="-0.01em",
                ),
                align="center",
                spacing="3",
            ),
            # Center: Chart Type Tabs
            rx.hstack(
                chart_tab("Icicle", "icicle", is_active=True),
                chart_tab("Sankey", "sankey", is_active=False),
                chart_tab("Timeline", "timeline", is_active=False),
                spacing="2",
                align="center",
                background_color="rgba(255,255,255,0.1)",
                padding=Spacing.XS,
                border_radius=Radii.FULL,
            ),
            # Right: Data Freshness Indicator
            rx.hstack(
                rx.icon(
                    "database",
                    size=16,
                    color=Colors.SKY,
                ),
                rx.vstack(
                    rx.text(
                        rx.cond(
                            AppState.data_loaded,
                            AppState.total_records.to_string() + " records",
                            "Loading data...",
                        ),
                        font_size=Typography.CAPTION_SIZE,
                        font_weight="500",
                        color=Colors.WHITE,
                        font_family=Typography.FONT_FAMILY,
                    ),
                    rx.text(
                        rx.cond(
                            AppState.data_loaded,
                            "Refreshed: " + AppState.last_updated_display,
                            "Connecting...",
                        ),
                        font_size="11px",
                        color=Colors.WHITE,
                        opacity="0.7",
                        font_family=Typography.FONT_FAMILY,
                    ),
                    spacing="0",
                    align="end",
                ),
                spacing="2",
                align="center",
            ),
            justify="between",
            align="center",
            width="100%",
            max_width=PAGE_MAX_WIDTH,
            margin_x="auto",
            padding_x=Spacing.XL,
        ),
        background_color=Colors.HERITAGE_BLUE,
        height=TOP_BAR_HEIGHT,
        width="100%",
        display="flex",
        align_items="center",
        position="sticky",
        top="0",
        z_index="100",
        box_shadow=Shadows.MD,
    )


def filter_section() -> rx.Component:
    """
    Compact filter strip component (v2.1 redesign).

    Single horizontal row containing ALL filters:
    - Date filters: Treatment Initiated, Last Seen
    - Multi-select filters: Drugs, Indications, Directorates

    Target height: 48px (single row)
    No "Filters" header - labels are in dropdown triggers/panels.
    """
    return rx.box(
        rx.hstack(
            # Date filters group
            rx.hstack(
                initiated_filter_dropdown(),
                last_seen_filter_dropdown(),
                spacing="2",
                align="center",
            ),
            # Separator
            rx.divider(
                orientation="vertical",
                size="2",
                color_scheme="gray",
            ),
            # Multi-select filters group
            rx.hstack(
                searchable_dropdown(
                    label="Drugs",
                    selection_text=AppState.drug_selection_text,
                    is_open=AppState.drug_dropdown_open,
                    toggle_handler=AppState.toggle_drug_dropdown,
                    search_value=AppState.drug_search,
                    on_search_change=AppState.set_drug_search,
                    filtered_items=AppState.filtered_drugs,
                    selected_items=AppState.selected_drugs,
                    toggle_item_handler=AppState.toggle_drug,
                    select_all_handler=AppState.select_all_drugs,
                    clear_all_handler=AppState.clear_all_drugs,
                ),
                searchable_dropdown(
                    label="Indications",
                    selection_text=AppState.indication_selection_text,
                    is_open=AppState.indication_dropdown_open,
                    toggle_handler=AppState.toggle_indication_dropdown,
                    search_value=AppState.indication_search,
                    on_search_change=AppState.set_indication_search,
                    filtered_items=AppState.filtered_indications,
                    selected_items=AppState.selected_indications,
                    toggle_item_handler=AppState.toggle_indication,
                    select_all_handler=AppState.select_all_indications,
                    clear_all_handler=AppState.clear_all_indications,
                ),
                searchable_dropdown(
                    label="Directorates",
                    selection_text=AppState.directorate_selection_text,
                    is_open=AppState.directorate_dropdown_open,
                    toggle_handler=AppState.toggle_directorate_dropdown,
                    search_value=AppState.directorate_search,
                    on_search_change=AppState.set_directorate_search,
                    filtered_items=AppState.filtered_directorates,
                    selected_items=AppState.selected_directorates,
                    toggle_item_handler=AppState.toggle_directorate,
                    select_all_handler=AppState.select_all_directorates,
                    clear_all_handler=AppState.clear_all_directorates,
                ),
                spacing="2",
                align="center",
            ),
            # Spacer to push content left
            rx.spacer(),
            justify="start",
            align="center",
            gap=Spacing.LG,
            width="100%",
        ),
        **filter_strip_style(),
    )


def kpi_card(
    value: rx.Var[str],
    label: str,
    icon_name: str = None,
    highlight: bool = False,
) -> rx.Component:
    """
    KPI card component displaying a metric value with label.

    Args:
        value: The display value (should be a formatted string from computed var)
        label: Label describing the metric
        icon_name: Optional Lucide icon name to display
        highlight: If True, uses Pale Blue background tint

    Design specs from DESIGN_SYSTEM.md:
    - Large mono number: 32-48px, Slate 900
    - Label: Caption size, Slate 500
    - Background: White or Pale Blue tint
    """
    # Build content - icon only if provided
    content_items = []
    if icon_name:
        content_items.append(
            rx.icon(
                icon_name,
                size=20,
                color=Colors.PRIMARY,
            )
        )

    return rx.box(
        rx.vstack(
            # Optional icon
            rx.icon(
                icon_name if icon_name else "activity",
                size=20,
                color=Colors.PRIMARY,
            ) if icon_name else rx.fragment(),
            # Value
            rx.text(
                value,
                **kpi_value_style(),
            ),
            # Label
            rx.text(
                label,
                **kpi_label_style(),
            ),
            spacing="1",
            align="center",
        ),
        # Apply card styling manually to allow background_color override
        background_color=Colors.PALE if highlight else Colors.WHITE,
        border=f"1px solid {Colors.SLATE_300}",
        border_radius=Radii.LG,
        padding=Spacing.XL,
        box_shadow=Shadows.SM,
        text_align="center",
        min_width="180px",
        flex="1",
        transition=f"box-shadow {Transitions.SHADOW}, transform {Transitions.TRANSFORM}",
        _hover={
            "box_shadow": Shadows.MD,
            "transform": "translateY(-2px)",
        },
    )


def kpi_row() -> rx.Component:
    """
    KPI metrics row component with responsive grid layout.

    Contains:
    - Unique Patients: COUNT(DISTINCT patient_id)
    - Total Drugs: Count of selected/filtered drugs
    - Total Cost: Sum of costs in filtered data
    - Match Rate: Indication match percentage

    Layout: Responsive flex row that wraps on smaller screens.
    KPIs update reactively when filters change (Phase 3).
    """
    return rx.hstack(
        # Unique Patients KPI - highlighted as primary metric
        kpi_card(
            value=AppState.unique_patients_display,
            label="Unique Patients",
            icon_name="users",
            highlight=True,
        ),
        # Total Drugs KPI
        kpi_card(
            value=AppState.total_drugs_display,
            label="Drug Types",
            icon_name="pill",
            highlight=False,
        ),
        # Total Cost KPI
        kpi_card(
            value=AppState.total_cost_display,
            label="Total Cost",
            icon_name="pound-sterling",
            highlight=False,
        ),
        # Indication Match Rate KPI
        kpi_card(
            value=AppState.match_rate_display,
            label="Indication Match",
            icon_name="circle-check",
            highlight=False,
        ),
        spacing="4",
        width="100%",
        flex_wrap="wrap",
        align="stretch",
    )


def chart_loading_skeleton() -> rx.Component:
    """
    Loading skeleton for the chart area.

    Displays animated pulsing bars to indicate loading state.
    Uses design system colors and spacing.
    """
    return rx.box(
        rx.vstack(
            # Simulated chart bars at different heights
            rx.hstack(
                rx.box(
                    background_color=Colors.SLATE_300,
                    width="12%",
                    height="60%",
                    border_radius=Radii.SM,
                    animation="pulse 1.5s ease-in-out infinite",
                ),
                rx.box(
                    background_color=Colors.SLATE_300,
                    width="12%",
                    height="80%",
                    border_radius=Radii.SM,
                    animation="pulse 1.5s ease-in-out infinite",
                    animation_delay="0.1s",
                ),
                rx.box(
                    background_color=Colors.SLATE_300,
                    width="12%",
                    height="45%",
                    border_radius=Radii.SM,
                    animation="pulse 1.5s ease-in-out infinite",
                    animation_delay="0.2s",
                ),
                rx.box(
                    background_color=Colors.SLATE_300,
                    width="12%",
                    height="70%",
                    border_radius=Radii.SM,
                    animation="pulse 1.5s ease-in-out infinite",
                    animation_delay="0.3s",
                ),
                rx.box(
                    background_color=Colors.SLATE_300,
                    width="12%",
                    height="55%",
                    border_radius=Radii.SM,
                    animation="pulse 1.5s ease-in-out infinite",
                    animation_delay="0.4s",
                ),
                rx.box(
                    background_color=Colors.SLATE_300,
                    width="12%",
                    height="90%",
                    border_radius=Radii.SM,
                    animation="pulse 1.5s ease-in-out infinite",
                    animation_delay="0.5s",
                ),
                spacing="3",
                align="end",
                justify="center",
                height="100%",
                width="100%",
            ),
            # Loading text
            rx.hstack(
                rx.spinner(size="2"),
                rx.text(
                    "Generating chart...",
                    font_size=Typography.BODY_SIZE,
                    font_weight=Typography.BODY_WEIGHT,
                    color=Colors.SLATE_500,
                    font_family=Typography.FONT_FAMILY,
                ),
                spacing="2",
                align="center",
            ),
            spacing="4",
            align="center",
            justify="center",
            height="100%",
            width="100%",
        ),
        background_color=Colors.SLATE_100,
        border_radius=Radii.MD,
        width="100%",
        height="500px",
        padding=Spacing.XL,
    )


def chart_error_state(error_message: rx.Var[str]) -> rx.Component:
    """
    Error state for the chart area.

    Displays a friendly error message with an icon and the error details.
    Provides guidance on how to resolve the issue.
    """
    return rx.box(
        rx.center(
            rx.vstack(
                rx.icon(
                    "triangle-alert",
                    size=48,
                    color=Colors.WARNING,
                ),
                rx.text(
                    "Unable to Generate Chart",
                    font_size=Typography.H2_SIZE,
                    font_weight=Typography.H2_WEIGHT,
                    color=Colors.SLATE_900,
                    font_family=Typography.FONT_FAMILY,
                ),
                rx.text(
                    error_message,
                    font_size=Typography.BODY_SIZE,
                    font_weight=Typography.BODY_WEIGHT,
                    color=Colors.SLATE_700,
                    font_family=Typography.FONT_FAMILY,
                    text_align="center",
                    max_width="400px",
                ),
                rx.text(
                    "Try adjusting the filters or check the data source.",
                    font_size=Typography.CAPTION_SIZE,
                    font_weight=Typography.CAPTION_WEIGHT,
                    color=Colors.SLATE_500,
                    font_family=Typography.FONT_FAMILY,
                ),
                spacing="3",
                align="center",
            ),
            width="100%",
            height="100%",
        ),
        background_color=Colors.SLATE_100,
        border_radius=Radii.MD,
        width="100%",
        height="500px",
        padding=Spacing.XL,
    )


def chart_empty_state() -> rx.Component:
    """
    Empty state for when no data matches the filters.

    Displays a friendly message encouraging filter adjustment.
    """
    return rx.box(
        rx.center(
            rx.vstack(
                rx.icon(
                    "search-x",
                    size=48,
                    color=Colors.SLATE_500,
                ),
                rx.text(
                    "No Data to Display",
                    font_size=Typography.H2_SIZE,
                    font_weight=Typography.H2_WEIGHT,
                    color=Colors.SLATE_900,
                    font_family=Typography.FONT_FAMILY,
                ),
                rx.text(
                    "No patient records match your current filter criteria.",
                    font_size=Typography.BODY_SIZE,
                    font_weight=Typography.BODY_WEIGHT,
                    color=Colors.SLATE_700,
                    font_family=Typography.FONT_FAMILY,
                    text_align="center",
                ),
                rx.text(
                    "Try widening your date range or selecting more drugs/indications.",
                    font_size=Typography.CAPTION_SIZE,
                    font_weight=Typography.CAPTION_WEIGHT,
                    color=Colors.SLATE_500,
                    font_family=Typography.FONT_FAMILY,
                ),
                spacing="3",
                align="center",
            ),
            width="100%",
            height="100%",
        ),
        background_color=Colors.SLATE_100,
        border_radius=Radii.MD,
        width="100%",
        height="500px",
        padding=Spacing.XL,
    )


def chart_display() -> rx.Component:
    """
    Plotly icicle chart display component.

    Renders the interactive icicle chart from AppState.icicle_figure.
    The figure is a computed property that updates reactively when
    chart_data changes (which happens when filters change).

    Uses rx.plotly() to render the Plotly figure object.
    """
    return rx.box(
        rx.plotly(
            data=AppState.icicle_figure,
            width="100%",
            height="600px",
        ),
        width="100%",
        min_height="600px",
    )


def chart_section() -> rx.Component:
    """
    Main chart section component.

    Contains: Plotly icicle chart with loading, error, empty, and ready states.

    State handling:
    - Loading: Shows skeleton animation when chart_loading is True
    - Error: Shows error message when error_message is not empty
    - Empty: Shows empty state when data_loaded but unique_patients is 0
    - Ready: Shows interactive Plotly icicle chart

    The chart updates reactively when filters change via the icicle_figure computed property.
    """
    return rx.box(
        rx.vstack(
            # Header row with title and chart type info
            rx.hstack(
                rx.text(
                    "Patient Pathway Visualization",
                    **text_h1(),
                ),
                rx.hstack(
                    rx.icon(
                        "info",
                        size=14,
                        color=Colors.SLATE_500,
                    ),
                    rx.text(
                        "Hierarchical view: Trust → Directorate → Drug → Patient Pathway",
                        font_size=Typography.CAPTION_SIZE,
                        font_weight=Typography.CAPTION_WEIGHT,
                        color=Colors.SLATE_500,
                        font_family=Typography.FONT_FAMILY,
                    ),
                    spacing="1",
                    align="center",
                ),
                justify="between",
                align="center",
                width="100%",
                flex_wrap="wrap",
            ),
            # Chart container with state-based rendering
            rx.cond(
                # Priority 1: Loading state
                AppState.chart_loading,
                chart_loading_skeleton(),
                # Not loading - check for error
                rx.cond(
                    # Priority 2: Error state
                    AppState.error_message != "",
                    chart_error_state(AppState.error_message),
                    # No error - check if data loaded
                    rx.cond(
                        # Priority 3: Data loaded but empty
                        AppState.data_loaded & (AppState.unique_patients == 0),
                        chart_empty_state(),
                        # Priority 4: Ready state - show interactive Plotly chart
                        chart_display(),
                    ),
                ),
            ),
            spacing="4",
            width="100%",
            align="start",
        ),
        **card_style(),
        width="100%",
    )


def main_content() -> rx.Component:
    """
    Main content area below the top bar.

    Layout: Filter Section → KPI Row → Chart Section
    Max width constrained to PAGE_MAX_WIDTH, centered.
    """
    return rx.box(
        rx.vstack(
            filter_section(),
            kpi_row(),
            chart_section(),
            spacing="5",
            width="100%",
            align="stretch",
        ),
        width="100%",
        max_width=PAGE_MAX_WIDTH,
        margin_x="auto",
        padding=PAGE_PADDING,
        padding_top=Spacing.XL,
    )


def page_layout() -> rx.Component:
    """
    Full page layout combining top bar and main content.

    Structure:
    - Sticky top bar (64px)
    - Scrollable main content area
    - White background
    """
    return rx.box(
        rx.vstack(
            top_bar(),
            main_content(),
            spacing="0",
            width="100%",
            min_height="100vh",
        ),
        background_color=Colors.WHITE,
        font_family=Typography.FONT_FAMILY,
        width="100%",
    )


# =============================================================================
# Page Definition
# =============================================================================

def index() -> rx.Component:
    """Main page for HCD Analysis v2."""
    return page_layout()


# =============================================================================
# App Configuration
# =============================================================================

app = rx.App(
    theme=rx.theme(
        accent_color="blue",
        gray_color="slate",
        radius="medium",
    ),
    stylesheets=[
        # Google Fonts - Inter (primary) and JetBrains Mono (monospace)
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
    ],
)

# Register page with on_load handler to load data on app initialization
app.add_page(index, route="/", title="HCD Analysis | Patient Pathways", on_load=AppState.load_data)
