"""Callbacks for reference data loading and filter state management."""
from dash import Input, Output, State, callback, ctx, no_update


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
        record_text = f"{total:,} records" if total else "Data loaded"
        last_updated = ref.get("last_updated", "")
        updated_text = last_updated[:10] if last_updated else "Unknown"

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
        State("app-state", "data"),
    )
    def update_app_state(
        _dir_clicks, _ind_clicks, initiated, last_seen, selected_drugs, current_state
    ):
        """Update app-state when chart type toggle, date filters, or drug chips change."""
        if not current_state:
            current_state = {
                "chart_type": "directory",
                "initiated": "all",
                "last_seen": "6mo",
                "date_filter_id": "all_6mo",
                "selected_drugs": [],
                "selected_directorates": [],
            }

        triggered_id = ctx.triggered_id

        # Determine chart type from toggle pills
        chart_type = current_state.get("chart_type", "directory")
        if triggered_id == "chart-type-directory":
            chart_type = "directory"
        elif triggered_id == "chart-type-indication":
            chart_type = "indication"

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
        }

        # Toggle pill CSS classes
        base = "toggle-pill"
        active = f"{base} toggle-pill--active"
        dir_class = active if chart_type == "directory" else base
        ind_class = active if chart_type == "indication" else base

        return updated_state, dir_class, ind_class
