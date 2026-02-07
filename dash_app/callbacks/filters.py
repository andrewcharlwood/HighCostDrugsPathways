"""Callbacks for reference data loading and filter state management."""
from datetime import datetime
from dash import Input, Output, State, callback, ctx, no_update, ALL


def _format_relative_time(iso_timestamp: str) -> str:
    """Format an ISO timestamp as relative time (e.g., '2h ago', 'yesterday')."""
    if not iso_timestamp:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        now = datetime.now()
        delta = now - dt
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days == 1:
            return "yesterday"
        if days < 7:
            return f"{days}d ago"
        if days < 30:
            weeks = days // 7
            return f"{weeks}w ago"
        return dt.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return iso_timestamp[:10] if len(iso_timestamp) >= 10 else "Unknown"


def register_filter_callbacks(app):
    """Register reference data loading and filter state callbacks."""

    @app.callback(
        Output("reference-data", "data"),
        Output("header-record-count", "children"),
        Output("header-last-updated", "children"),
        Input("url", "pathname"),  # fires once on page load
    )
    def load_reference_data(_pathname):
        """Load reference data once on page load."""
        from dash_app.data.queries import load_initial_data

        ref = load_initial_data()

        total = ref.get("total_records", 0)
        patients = ref.get("total_patients", 0)
        if total:
            record_text = f"{total:,} records"
        elif patients:
            record_text = f"{patients:,} patients"
        else:
            record_text = "Data loaded"

        last_updated = ref.get("last_updated", "")
        updated_text = _format_relative_time(last_updated)

        return ref, record_text, updated_text

    @app.callback(
        Output("app-state", "data"),
        Output("chart-type-directory", "className"),
        Output("chart-type-indication", "className"),
        Input("chart-type-directory", "n_clicks"),
        Input("chart-type-indication", "n_clicks"),
        Input("filter-initiated", "value"),
        Input("filter-last-seen", "value"),
        Input("all-drugs-chips", "value"),
        Input("trust-chips", "value"),
        Input("nav-patient-pathways", "n_clicks"),
        Input("nav-trust-comparison", "n_clicks"),
        Input("nav-trends", "n_clicks"),
        Input({"type": "tc-selector", "index": ALL}, "n_clicks"),
        Input("tc-back-btn", "n_clicks"),
        Input("trends-overview-chart", "clickData"),
        Input("trends-back-btn", "n_clicks"),
        State("app-state", "data"),
    )
    def update_app_state(
        _dir_clicks, _ind_clicks, initiated, last_seen, selected_drugs,
        selected_trusts, _nav_pp_clicks, _nav_tc_clicks, _nav_trends_clicks,
        _tc_selector_clicks, _tc_back_clicks, trends_click_data,
        _trends_back_clicks, current_state
    ):
        """Update app-state when any filter, nav, or TC selector changes."""
        if not current_state:
            current_state = {
                "chart_type": "directory",
                "initiated": "all",
                "last_seen": "6mo",
                "date_filter_id": "all_6mo",
                "selected_drugs": [],
                "selected_directorates": [],
                "selected_trusts": [],
                "active_view": "patient-pathways",
                "selected_comparison_directorate": None,
                "selected_trends_directorate": None,
            }

        triggered_id = ctx.triggered_id

        # Determine chart type from toggle pills
        chart_type = current_state.get("chart_type", "directory")
        prev_chart_type = chart_type
        if triggered_id == "chart-type-directory":
            chart_type = "directory"
        elif triggered_id == "chart-type-indication":
            chart_type = "indication"

        # Determine active view from sidebar nav
        active_view = current_state.get("active_view", "patient-pathways")
        if triggered_id == "nav-patient-pathways":
            active_view = "patient-pathways"
        elif triggered_id == "nav-trust-comparison":
            active_view = "trust-comparison"
        elif triggered_id == "nav-trends":
            active_view = "trends"

        # Trust Comparison directorate selection
        selected_comparison_directorate = current_state.get("selected_comparison_directorate")

        # Handle TC card click (pattern-matching ID)
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "tc-selector":
            selected_comparison_directorate = triggered_id["index"]

        # Handle TC back button
        if triggered_id == "tc-back-btn":
            selected_comparison_directorate = None

        # If chart type changed while a directorate is selected, return to landing
        if chart_type != prev_chart_type and selected_comparison_directorate is not None:
            selected_comparison_directorate = None

        # Trends directorate drill-down
        selected_trends_directorate = current_state.get("selected_trends_directorate")

        if triggered_id == "trends-overview-chart" and trends_click_data:
            points = trends_click_data.get("points", [])
            if points:
                selected_trends_directorate = points[0].get("customdata")

        if triggered_id == "trends-back-btn":
            selected_trends_directorate = None

        # If chart type changed while trends directorate is selected, return to landing
        if chart_type != prev_chart_type and selected_trends_directorate is not None:
            selected_trends_directorate = None

        # Compute date_filter_id from dropdown values
        date_filter_id = f"{initiated}_{last_seen}"

        # Build updated state
        updated_state = {
            **current_state,
            "chart_type": chart_type,
            "initiated": initiated,
            "last_seen": last_seen,
            "date_filter_id": date_filter_id,
            "selected_drugs": selected_drugs or [],
            "selected_trusts": selected_trusts or [],
            "active_view": active_view,
            "selected_comparison_directorate": selected_comparison_directorate,
            "selected_trends_directorate": selected_trends_directorate,
        }

        # Toggle pill CSS classes
        base = "toggle-pill"
        active_cls = f"{base} toggle-pill--active"
        dir_class = active_cls if chart_type == "directory" else base
        ind_class = active_cls if chart_type == "indication" else base

        return updated_state, dir_class, ind_class
