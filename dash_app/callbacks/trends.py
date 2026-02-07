"""Callbacks for Trends view — directorate overview + drug drill-down."""
from dash import Input, Output, State, no_update
import plotly.graph_objects as go


def register_trends_callbacks(app):
    """Register Trends view callbacks."""

    def _trends_empty(message):
        """Return a blank figure with a centered message."""
        fig = go.Figure()
        fig.update_layout(
            xaxis={"visible": False}, yaxis={"visible": False},
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin={"t": 0, "l": 0, "r": 0, "b": 0}, height=400,
            annotations=[{
                "text": message, "xref": "paper", "yref": "paper",
                "x": 0.5, "y": 0.5, "showarrow": False,
                "font": {"size": 14, "color": "#768692",
                         "family": "Source Sans 3, system-ui, sans-serif"},
                "xanchor": "center", "yanchor": "middle",
            }],
        )
        return fig

    # --- Landing / Detail toggle ---
    @app.callback(
        Output("trends-landing", "style"),
        Output("trends-detail", "style"),
        Output("trends-detail-title", "children"),
        Input("app-state", "data"),
    )
    def toggle_trends_subviews(app_state):
        """Toggle between landing page and drug detail view."""
        if not app_state:
            return {}, {"display": "none"}, ""

        selected = app_state.get("selected_trends_directorate")
        show = {}
        hide = {"display": "none"}

        if selected:
            title = f"{selected} \u2014 Drug Trends"
            return hide, show, title
        else:
            return show, hide, ""

    # --- Directorate overview chart (landing page) ---
    @app.callback(
        Output("trends-overview-chart", "figure"),
        Input("app-state", "data"),
        Input("trends-view-metric-toggle", "value"),
        prevent_initial_call=True,
    )
    def render_trends_overview(app_state, metric):
        """Render directorate-level trends line chart on the landing page."""
        if not app_state:
            return no_update

        active_view = app_state.get("active_view", "")
        if active_view != "trends":
            return no_update

        selected = app_state.get("selected_trends_directorate")
        if selected:
            return no_update

        metric = metric or "patients"

        from dash_app.data.queries import get_trend_data
        from visualization.plotly_generator import create_trend_figure

        try:
            data = get_trend_data(
                metric=metric,
                group_by="directory",
            )
        except Exception:
            return _trends_empty("Failed to load trend data.")

        if not data:
            return _trends_empty(
                "No trend data available.<br>"
                "Run <b>python -m cli.compute_trends</b> to generate."
            )

        metric_labels = {
            "patients": "Patients",
            "total_cost": "Cost per Patient",
            "cost_pp_pa": "Cost per Patient p.a.",
        }
        title = f"Directorate Trends \u2014 {metric_labels.get(metric, 'Patients')}"

        return create_trend_figure(data, title, metric)

    # --- Drug detail chart (drill-down) ---
    @app.callback(
        Output("trends-detail-chart", "figure"),
        Input("app-state", "data"),
        Input("trends-detail-metric-toggle", "value"),
        prevent_initial_call=True,
    )
    def render_trends_detail(app_state, metric):
        """Render drug-level trends for the selected directorate."""
        if not app_state:
            return no_update

        active_view = app_state.get("active_view", "")
        if active_view != "trends":
            return no_update

        selected = app_state.get("selected_trends_directorate")
        if not selected:
            return no_update

        metric = metric or "patients"

        from dash_app.data.queries import get_trend_data
        from visualization.plotly_generator import create_trend_figure

        try:
            data = get_trend_data(
                metric=metric,
                directory=selected,
                group_by="drug",
            )
        except Exception:
            return _trends_empty("Failed to load trend data.")

        if not data:
            return _trends_empty("No trend data for this directorate.")

        metric_labels = {
            "patients": "Patients",
            "total_cost": "Cost per Patient",
            "cost_pp_pa": "Cost per Patient p.a.",
        }
        title = f"{selected} \u2014 {metric_labels.get(metric, 'Patients')}"

        return create_trend_figure(data, title, metric)
