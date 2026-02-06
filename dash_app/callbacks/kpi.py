"""Callback for updating KPI card values from chart-data store."""
from dash import Input, Output, no_update


def _format_cost(cost):
    """Format cost as £X.XM or £X.XK."""
    if cost >= 1_000_000:
        return f"\u00a3{cost / 1_000_000:.1f}M"
    if cost >= 1_000:
        return f"\u00a3{cost / 1_000:.1f}K"
    return f"\u00a3{cost:.0f}"


def register_kpi_callbacks(app):
    """Register KPI update callback."""

    @app.callback(
        Output("kpi-patients", "children"),
        Output("kpi-drugs", "children"),
        Output("kpi-cost", "children"),
        Output("kpi-match", "children"),
        Input("chart-data", "data"),
        Input("app-state", "data"),
    )
    def update_kpis(chart_data, app_state):
        """Update KPI card values when chart-data changes."""
        if not chart_data:
            return no_update, no_update, no_update, no_update

        patients = chart_data.get("unique_patients", 0)
        drugs = chart_data.get("total_drugs", 0)
        cost = chart_data.get("total_cost", 0.0)

        patients_str = f"{patients:,}" if patients else "\u2014"
        drugs_str = str(drugs) if drugs else "\u2014"
        cost_str = _format_cost(cost) if cost else "\u2014"

        chart_type = (app_state or {}).get("chart_type", "directory")
        match_str = "~93%" if chart_type == "indication" else "\u2014"

        return patients_str, drugs_str, cost_str, match_str
