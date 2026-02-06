"""Trust Comparison view — landing page (directorate selector) + 6-chart dashboard."""
from dash import html, dcc


def _tc_chart_cell(title, graph_id):
    """Helper to create a single chart cell in the 6-chart dashboard grid."""
    return html.Div(className="tc-chart-cell", children=[
        html.Div(title, className="tc-chart-cell__title"),
        dcc.Loading(type="circle", color="#005EB8", children=[
            dcc.Graph(
                id=graph_id,
                config={"displayModeBar": False, "displaylogo": False},
                style={"height": "320px"},
            ),
        ]),
    ])


def make_tc_landing():
    """Trust Comparison landing page — directorate/indication selector grid."""
    return html.Div(
        className="tc-landing",
        id="trust-comparison-landing",
        children=[
            html.Div(
                className="tc-landing__header",
                children=[
                    html.H2("Trust Comparison", className="tc-landing__title"),
                    html.P(
                        "Select a directorate to compare drug usage across trusts.",
                        className="tc-landing__desc",
                        id="tc-landing-desc",
                    ),
                ],
            ),
            html.Div(
                className="tc-landing__grid",
                id="tc-landing-grid",
                children=[],
            ),
        ],
    )


def make_tc_dashboard():
    """Trust Comparison 6-chart dashboard for a selected directorate."""
    return html.Div(
        className="tc-dashboard",
        id="trust-comparison-dashboard",
        style={"display": "none"},
        children=[
            html.Div(
                className="tc-dashboard__header",
                children=[
                    html.Button(
                        "\u2190 Back",
                        id="tc-back-btn",
                        className="tc-dashboard__back",
                        n_clicks=0,
                    ),
                    html.H2(
                        id="tc-dashboard-title",
                        className="tc-dashboard__title",
                        children="",
                    ),
                ],
            ),
            html.Div(
                className="tc-dashboard__grid",
                children=[
                    _tc_chart_cell("Market Share", "tc-chart-market-share"),
                    _tc_chart_cell("Cost Waterfall", "tc-chart-cost-waterfall"),
                    _tc_chart_cell("Dosing Intervals", "tc-chart-dosing"),
                    _tc_chart_cell("Drug \u00d7 Trust Heatmap", "tc-chart-heatmap"),
                    _tc_chart_cell("Treatment Duration", "tc-chart-duration"),
                    _tc_chart_cell("Cost Effectiveness", "tc-chart-cost-effectiveness"),
                ],
            ),
        ],
    )
