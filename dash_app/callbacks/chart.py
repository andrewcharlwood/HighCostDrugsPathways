"""Callback for loading pathway data from SQLite into chart-data store."""
from dash import Input, Output, callback, no_update


def register_chart_callbacks(app):
    """Register pathway data loading callback."""

    @app.callback(
        Output("chart-data", "data"),
        Input("app-state", "data"),
    )
    def load_pathway_data(app_state):
        """Load pathway nodes when app-state changes (filter or chart type)."""
        if not app_state:
            return no_update

        from dash_app.data.queries import load_pathway_data as query_pathway_data

        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        selected_drugs = app_state.get("selected_drugs") or None
        selected_directorates = app_state.get("selected_directorates") or None

        return query_pathway_data(
            filter_id=filter_id,
            chart_type=chart_type,
            selected_drugs=selected_drugs,
            selected_directorates=selected_directorates,
        )
