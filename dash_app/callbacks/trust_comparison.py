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

    # Dashboard chart rendering will be added in Task 10.8.
    # For now, register empty figure placeholders for the 6 chart IDs
    # so the dcc.Graph components don't error on load.
    _tc_chart_ids = [
        "tc-chart-market-share",
        "tc-chart-cost-waterfall",
        "tc-chart-dosing",
        "tc-chart-heatmap",
        "tc-chart-duration",
        "tc-chart-cost-effectiveness",
    ]

    for chart_id in _tc_chart_ids:
        @app.callback(
            Output(chart_id, "figure"),
            Input("app-state", "data"),
            prevent_initial_call=True,
        )
        def _placeholder_chart(app_state, _cid=chart_id):
            """Placeholder — returns empty figure until Task 10.8 implements real charts."""
            selected = (app_state or {}).get("selected_comparison_directorate")
            if not selected:
                return no_update
            fig = go.Figure()
            fig.update_layout(
                template="plotly_white",
                margin=dict(l=20, r=20, t=30, b=20),
                height=300,
                annotations=[
                    dict(
                        text="Chart will be implemented in Task 10.8",
                        xref="paper", yref="paper",
                        x=0.5, y=0.5, showarrow=False,
                        font=dict(size=14, color="#999"),
                    )
                ],
            )
            return fig
