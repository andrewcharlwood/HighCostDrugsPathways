"""Trust Comparison view — landing page (directorate selector) + 6-chart dashboard."""
from dash import html, dcc
import dash_mantine_components as dmc


def _tc_chart_cell(title, graph_id):
    """Helper to create a single chart cell in the 6-chart dashboard grid."""
    return html.Div(className="tc-chart-cell", children=[
        html.Div(title, className="tc-chart-cell__title"),
        dcc.Loading(type="circle", color="#005EB8", children=[
            dcc.Graph(
                id=graph_id,
                config={"displayModeBar": False, "displaylogo": False},
                style={"height": "500px"},
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
                    html.Div(className="tc-chart-cell", children=[
                        html.Div(
                            className="tc-chart-cell__title-row",
                            style={"display": "flex", "alignItems": "center",
                                   "justifyContent": "space-between", "gap": "8px"},
                            children=[
                                html.Div("Drug \u00d7 Trust Heatmap",
                                         className="tc-chart-cell__title"),
                                dmc.SegmentedControl(
                                    id="tc-heatmap-metric-toggle",
                                    data=[
                                        {"value": "patients", "label": "Patients"},
                                        {"value": "cost", "label": "Cost per Patient"},
                                        {"value": "cost_pp_pa", "label": "Cost per Patient p.a."},
                                    ],
                                    value="patients",
                                    size="xs",
                                ),
                            ],
                        ),
                        dcc.Loading(type="circle", color="#005EB8", children=[
                            dcc.Graph(
                                id="tc-chart-heatmap",
                                config={"displayModeBar": False, "displaylogo": False},
                                style={"height": "500px"},
                            ),
                        ]),
                    ]),
                    _tc_chart_cell("Treatment Duration", "tc-chart-duration"),
                    _tc_chart_cell("Cost Effectiveness", "tc-chart-cost-effectiveness"),
                ],
            ),
        ],
    )
