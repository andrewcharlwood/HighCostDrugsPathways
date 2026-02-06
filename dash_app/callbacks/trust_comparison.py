"""Callbacks for Trust Comparison landing page and dashboard navigation."""
from dash import html, Input, Output, State, ctx, no_update
import plotly.graph_objects as go


def register_trust_comparison_callbacks(app):
    """Register Trust Comparison view callbacks."""

    @app.callback(
        Output("tc-landing-grid", "children"),
        Output("tc-landing-grid", "className"),
        Output("tc-landing-desc", "children"),
        Input("app-state", "data"),
    )
    def populate_landing_grid(app_state):
        """Populate the landing page grid with directorate/indication cards."""
        if not app_state:
            return [], "tc-landing__grid", "Select a directorate to compare drug usage across trusts."

        from dash_app.data.queries import get_directorate_summary

        chart_type = app_state.get("chart_type", "directory")
        date_filter_id = app_state.get("date_filter_id", "all_6mo")

        summaries = get_directorate_summary(date_filter_id, chart_type)

        # Build card buttons
        cards = []
        for item in summaries:
            name = item["name"]
            patients = item["patients"]
            drugs = item["drugs"]
            cards.append(
                html.Button(
                    className="tc-card",
                    id={"type": "tc-selector", "index": name},
                    n_clicks=0,
                    children=[
                        html.Div(name, className="tc-card__name"),
                        html.Div(
                            className="tc-card__stats",
                            children=[
                                html.Span(
                                    f"{patients:,} patients",
                                    className="tc-card__stat",
                                ),
                                html.Span("\u00b7", className="tc-card__dot"),
                                html.Span(
                                    f"{drugs} drugs",
                                    className="tc-card__stat",
                                ),
                            ],
                        ),
                    ],
                )
            )

        # Grid class: wider for indication mode (more items)
        grid_cls = "tc-landing__grid"
        if chart_type == "indication":
            grid_cls += " tc-landing__grid--wide"

        # Description text adapts to chart type
        if chart_type == "indication":
            desc = "Select an indication to compare drug usage across trusts."
        else:
            desc = "Select a directorate to compare drug usage across trusts."

        return cards, grid_cls, desc

    @app.callback(
        Output("trust-comparison-landing", "style"),
        Output("trust-comparison-dashboard", "style"),
        Output("tc-dashboard-title", "children"),
        Input("app-state", "data"),
    )
    def toggle_tc_subviews(app_state):
        """Toggle between landing page and 6-chart dashboard."""
        if not app_state:
            return {}, {"display": "none"}, ""

        selected = app_state.get("selected_comparison_directorate")
        show = {}
        hide = {"display": "none"}

        if selected:
            chart_type = app_state.get("chart_type", "directory")
            label = "Indication" if chart_type == "indication" else "Directorate"
            title = f"{selected} \u2014 Trust Comparison"
            return hide, show, title
        else:
            return show, hide, ""

    # --- Trust Comparison dashboard charts (6 charts) ---

    def _tc_empty(message):
        """Return a blank figure with a centered message for TC dashboard."""
        fig = go.Figure()
        fig.update_layout(
            xaxis={"visible": False}, yaxis={"visible": False},
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin={"t": 0, "l": 0, "r": 0, "b": 0}, height=300,
            annotations=[{
                "text": message, "xref": "paper", "yref": "paper",
                "x": 0.5, "y": 0.5, "showarrow": False,
                "font": {"size": 14, "color": "#768692", "family": "Source Sans 3"},
                "xanchor": "center", "yanchor": "middle",
            }],
        )
        return fig

    def _tc_title(app_state):
        """Generate a short title suffix from global filter state."""
        chart_type = (app_state or {}).get("chart_type", "directory")
        label = "By Indication" if chart_type == "indication" else "By Directory"
        initiated = (app_state or {}).get("initiated", "all")
        last_seen = (app_state or {}).get("last_seen", "6mo")
        i_labels = {"all": "All years", "1yr": "Last 1 yr", "2yr": "Last 2 yrs"}
        l_labels = {"6mo": "6 mo", "12mo": "12 mo"}
        return f"{label} | {i_labels.get(initiated, 'All')} / {l_labels.get(last_seen, '6 mo')}"

    # 1. Market Share — drug breakdown per trust
    @app.callback(
        Output("tc-chart-market-share", "figure"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def tc_market_share(app_state):
        selected = (app_state or {}).get("selected_comparison_directorate")
        if not selected:
            return no_update
        from dash_app.data.queries import get_trust_market_share
        from visualization.plotly_generator import create_trust_market_share_figure
        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        try:
            data = get_trust_market_share(filter_id, chart_type, selected)
        except Exception:
            return _tc_empty("Failed to load market share data.")
        if not data:
            return _tc_empty("No market share data for this selection.")
        return create_trust_market_share_figure(data, _tc_title(app_state))

    # 2. Cost Waterfall — cost per patient by trust
    @app.callback(
        Output("tc-chart-cost-waterfall", "figure"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def tc_cost_waterfall(app_state):
        selected = (app_state or {}).get("selected_comparison_directorate")
        if not selected:
            return no_update
        from dash_app.data.queries import get_trust_cost_waterfall
        from visualization.plotly_generator import create_cost_waterfall_figure
        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        try:
            data = get_trust_cost_waterfall(filter_id, chart_type, selected)
        except Exception:
            return _tc_empty("Failed to load cost data.")
        if not data:
            return _tc_empty("No cost data for this selection.")
        # Reuse existing waterfall figure — map trust_name to directory key
        mapped = [{"directory": d["trust_name"], "patients": d["patients"],
                    "total_cost": d["total_cost"], "cost_pp": d["cost_pp"]} for d in data]
        return create_cost_waterfall_figure(mapped, _tc_title(app_state))

    # 3. Dosing — drug dosing intervals by trust
    @app.callback(
        Output("tc-chart-dosing", "figure"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def tc_dosing(app_state):
        selected = (app_state or {}).get("selected_comparison_directorate")
        if not selected:
            return no_update
        from dash_app.data.queries import get_trust_dosing
        from visualization.plotly_generator import create_dosing_figure
        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        try:
            data = get_trust_dosing(filter_id, chart_type, selected)
        except Exception:
            return _tc_empty("Failed to load dosing data.")
        if not data:
            return _tc_empty("No dosing data for this selection.")
        # Add directory field expected by _dosing_by_trust helper
        for d in data:
            d["directory"] = selected
        return create_dosing_figure(data, _tc_title(app_state), group_by="trust")

    # 4. Heatmap — trust x drug matrix
    @app.callback(
        Output("tc-chart-heatmap", "figure"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def tc_heatmap(app_state):
        selected = (app_state or {}).get("selected_comparison_directorate")
        if not selected:
            return no_update
        from dash_app.data.queries import get_trust_heatmap
        from visualization.plotly_generator import create_trust_heatmap_figure
        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        try:
            data = get_trust_heatmap(filter_id, chart_type, selected)
        except Exception:
            return _tc_empty("Failed to load heatmap data.")
        if not data.get("trusts") or not data.get("drugs"):
            return _tc_empty("No heatmap data for this selection.")
        return create_trust_heatmap_figure(data, _tc_title(app_state))

    # 5. Duration — drug durations by trust
    @app.callback(
        Output("tc-chart-duration", "figure"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def tc_duration(app_state):
        selected = (app_state or {}).get("selected_comparison_directorate")
        if not selected:
            return no_update
        from dash_app.data.queries import get_trust_durations
        from visualization.plotly_generator import create_trust_duration_figure
        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        try:
            data = get_trust_durations(filter_id, chart_type, selected)
        except Exception:
            return _tc_empty("Failed to load duration data.")
        if not data:
            return _tc_empty("No duration data for this selection.")
        return create_trust_duration_figure(data, _tc_title(app_state))

    # 6. Cost Effectiveness — pathway costs within directorate (NOT split by trust)
    @app.callback(
        Output("tc-chart-cost-effectiveness", "figure"),
        Input("app-state", "data"),
        prevent_initial_call=True,
    )
    def tc_cost_effectiveness(app_state):
        selected = (app_state or {}).get("selected_comparison_directorate")
        if not selected:
            return no_update
        from dash_app.data.queries import get_pathway_costs
        from data_processing.parsing import calculate_retention_rate
        from visualization.plotly_generator import create_cost_effectiveness_figure
        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        try:
            data = get_pathway_costs(filter_id, chart_type, directory=selected)
        except Exception:
            return _tc_empty("Failed to load pathway cost data.")
        if not data:
            return _tc_empty("No pathway cost data for this selection.")
        retention = calculate_retention_rate(data)
        return create_cost_effectiveness_figure(data, retention, _tc_title(app_state))
