"""Callbacks for pathway data loading and icicle chart rendering."""
from dash import Input, Output, no_update


def _generate_chart_title(app_state):
    """Generate chart title from current filter state."""
    parts = []

    chart_type = app_state.get("chart_type", "directory")
    parts.append("By Indication" if chart_type == "indication" else "By Directory")

    initiated = app_state.get("initiated", "all")
    initiated_labels = {"all": "All years", "1yr": "Last 1 year", "2yr": "Last 2 years"}
    last_seen = app_state.get("last_seen", "6mo")
    last_seen_labels = {"6mo": "Last 6 months", "12mo": "Last 12 months"}
    parts.append(
        f"{initiated_labels.get(initiated, 'All years')} / "
        f"{last_seen_labels.get(last_seen, 'Last 6 months')}"
    )

    selected_drugs = app_state.get("selected_drugs") or []
    if selected_drugs:
        if len(selected_drugs) <= 3:
            parts.append(", ".join(selected_drugs))
        else:
            parts.append(f"{len(selected_drugs)} drugs selected")

    selected_directorates = app_state.get("selected_directorates") or []
    if selected_directorates:
        if len(selected_directorates) <= 2:
            parts.append(", ".join(selected_directorates))
        else:
            parts.append(f"{len(selected_directorates)} directorates")

    selected_trusts = app_state.get("selected_trusts") or []
    if selected_trusts:
        if len(selected_trusts) <= 2:
            parts.append(", ".join(selected_trusts))
        else:
            parts.append(f"{len(selected_trusts)} trusts")

    return " | ".join(parts) if parts else "All Patients"


def register_chart_callbacks(app):
    """Register pathway data loading and chart rendering callbacks."""

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
        selected_trusts = app_state.get("selected_trusts") or None

        return query_pathway_data(
            filter_id=filter_id,
            chart_type=chart_type,
            selected_drugs=selected_drugs,
            selected_directorates=selected_directorates,
            selected_trusts=selected_trusts,
        )

    @app.callback(
        Output("pathway-chart", "figure"),
        Output("chart-subtitle", "children"),
        Input("chart-data", "data"),
        Input("app-state", "data"),
    )
    def update_chart(chart_data, app_state):
        """Render icicle chart from chart-data nodes."""
        if not chart_data or not chart_data.get("nodes"):
            return no_update, no_update

        from visualization.plotly_generator import create_icicle_from_nodes

        title = _generate_chart_title(app_state) if app_state else ""
        fig = create_icicle_from_nodes(chart_data["nodes"], title)

        chart_type = (app_state or {}).get("chart_type", "directory")
        if chart_type == "indication":
            subtitle = "Trust \u2192 Indication \u2192 Drug \u2192 Patient Pathway"
        else:
            subtitle = "Trust \u2192 Directorate \u2192 Drug \u2192 Patient Pathway"

        return fig, subtitle
