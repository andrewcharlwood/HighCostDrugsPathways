"""Trends view — directorate-level overview + drug-level drill-down."""
from dash import html, dcc
import dash_mantine_components as dmc


def make_trends_landing():
    """Trends landing page — directorate-level overview chart with metric toggle."""
    return html.Div(
        id="trends-landing",
        children=[
            html.Div(
                className="trends-landing__header",
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center",
                               "justifyContent": "space-between", "gap": "12px",
                               "flexWrap": "wrap"},
                        children=[
                            html.H2("Trends — Directorate Overview",
                                     className="trends-landing__title",
                                     style={"margin": "0", "color": "#1E293B",
                                            "fontSize": "18px",
                                            "fontFamily": "Source Sans 3, system-ui, sans-serif"}),
                            dmc.SegmentedControl(
                                id="trends-view-metric-toggle",
                                data=[
                                    {"value": "patients", "label": "Patients"},
                                    {"value": "total_cost", "label": "Cost per Patient"},
                                    {"value": "cost_pp_pa", "label": "Cost per Patient p.a."},
                                ],
                                value="patients",
                                size="xs",
                            ),
                        ],
                    ),
                    html.P(
                        "Click a directorate line to drill down into drug-level trends.",
                        className="trends-landing__desc",
                        style={"margin": "4px 0 0", "color": "#768692",
                               "fontSize": "14px"},
                    ),
                ],
                style={"padding": "20px 24px 8px"},
            ),
            dcc.Loading(type="circle", color="#005EB8", children=[
                dcc.Graph(
                    id="trends-overview-chart",
                    config={"displayModeBar": False, "displaylogo": False},
                    style={"height": "calc(100vh - 220px)", "minHeight": "400px"},
                    responsive=True,
                ),
            ]),
        ],
    )


def make_trends_detail():
    """Trends detail page — drug-level trends within a selected directorate."""
    return html.Div(
        id="trends-detail",
        style={"display": "none"},
        children=[
            html.Div(
                className="trends-detail__header",
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center",
                               "justifyContent": "space-between", "gap": "12px",
                               "flexWrap": "wrap"},
                        children=[
                            html.Div(
                                style={"display": "flex", "alignItems": "center",
                                       "gap": "12px"},
                                children=[
                                    html.Button(
                                        "\u2190 Back",
                                        id="trends-back-btn",
                                        className="tc-dashboard__back",
                                        n_clicks=0,
                                    ),
                                    html.H2(
                                        id="trends-detail-title",
                                        children="",
                                        style={"margin": "0", "color": "#1E293B",
                                               "fontSize": "18px",
                                               "fontFamily": "Source Sans 3, system-ui, sans-serif"},
                                    ),
                                ],
                            ),
                            dmc.SegmentedControl(
                                id="trends-detail-metric-toggle",
                                data=[
                                    {"value": "patients", "label": "Patients"},
                                    {"value": "total_cost", "label": "Cost per Patient"},
                                    {"value": "cost_pp_pa", "label": "Cost per Patient p.a."},
                                ],
                                value="patients",
                                size="xs",
                            ),
                        ],
                    ),
                ],
                style={"padding": "20px 24px 8px"},
            ),
            dcc.Loading(type="circle", color="#005EB8", children=[
                dcc.Graph(
                    id="trends-detail-chart",
                    config={"displayModeBar": False, "displaylogo": False},
                    style={"height": "calc(100vh - 220px)", "minHeight": "400px"},
                    responsive=True,
                ),
            ]),
        ],
    )
