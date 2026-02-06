"""Callback for updating fraction KPI values in the header bar."""
from dash import Input, Output, no_update


def _format_cost(cost):
    """Format cost as £X.XM or £X.XK."""
    if cost >= 1_000_000:
        return f"\u00a3{cost / 1_000_000:.1f}M"
    if cost >= 1_000:
        return f"\u00a3{cost / 1_000:.1f}K"
    return f"\u00a3{cost:.0f}"


def register_kpi_callbacks(app):
    """Register header KPI update callbacks."""

    @app.callback(
        # Filtered values (numerators)
        Output("kpi-filtered-patients", "children"),
        Output("kpi-filtered-drugs", "children"),
        Output("kpi-filtered-cost", "children"),
        # Total values (denominators)
        Output("kpi-total-patients", "children"),
        Output("kpi-total-drugs", "children"),
        Output("kpi-total-cost", "children"),
        Input("chart-data", "data"),
        Input("reference-data", "data"),
    )
    def update_header_kpis(chart_data, ref_data):
        """Update header fraction KPIs from chart-data (filtered) and reference-data (totals)."""
        # Filtered values from chart-data
        if chart_data:
            patients = chart_data.get("unique_patients", 0)
            drugs = chart_data.get("total_drugs", 0)
            cost = chart_data.get("total_cost", 0.0)
            filtered_patients = f"{patients:,}" if patients else "\u2014"
            filtered_drugs = str(drugs) if drugs else "\u2014"
            filtered_cost = _format_cost(cost) if cost else "\u2014"
        else:
            filtered_patients = "\u2014"
            filtered_drugs = "\u2014"
            filtered_cost = "\u2014"

        # Total values from reference-data
        if ref_data:
            total_patients_val = ref_data.get("total_patients", 0)
            total_drugs_val = len(ref_data.get("available_drugs", []))
            total_cost_val = ref_data.get("total_cost", 0.0)
            total_patients = f"{total_patients_val:,}" if total_patients_val else "\u2014"
            total_drugs = str(total_drugs_val) if total_drugs_val else "\u2014"
            total_cost = _format_cost(total_cost_val) if total_cost_val else "\u2014"
        else:
            total_patients = "\u2014"
            total_drugs = "\u2014"
            total_cost = "\u2014"

        return (
            filtered_patients, filtered_drugs, filtered_cost,
            total_patients, total_drugs, total_cost,
        )
