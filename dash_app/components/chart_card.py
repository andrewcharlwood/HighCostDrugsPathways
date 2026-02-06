"""Chart card component — tab bar, header, and dcc.Graph for charts."""
from dash import html, dcc


TAB_DEFINITIONS = [
    ("icicle", "Icicle"),
    ("market-share", "Market Share"),
    ("cost-effectiveness", "Cost Effectiveness"),
    ("cost-waterfall", "Cost Waterfall"),
    ("sankey", "Sankey"),
    ("dosing", "Dosing"),
    ("heatmap", "Heatmap"),
    ("duration", "Duration"),
]


def make_chart_card():
    """Return a chart card with tab bar and dcc.Graph.

    Contains:
    - Tab bar with 8 chart tabs (Icicle active by default)
    - Header with title and dynamic subtitle
    - dcc.Loading wrapper around dcc.Graph for loading spinner
    """
    tab_buttons = []
    for tab_id, label in TAB_DEFINITIONS:
        is_active = tab_id == "icicle"
        class_name = "chart-tab chart-tab--active" if is_active else "chart-tab"
        tab_buttons.append(
            html.Button(
                label,
                id=f"tab-{tab_id}",
                className=class_name,
                n_clicks=0,
            )
        )

    return html.Section(
        className="chart-card",
        **{"aria-label": "Patient pathway chart"},
        children=[
            # Tab bar
            html.Div(
                className="chart-card__tabs",
                role="tablist",
                children=tab_buttons,
            ),
            # Card header
            html.Div(
                className="chart-card__header",
                children=[
                    html.Div(
                        children=[
                            html.Div(
                                "Patient Pathway Visualization",
                                className="chart-card__title",
                            ),
                            html.Div(
                                "Trust \u2192 Directorate \u2192 Drug \u2192 Patient Pathway",
                                className="chart-card__subtitle",
                                id="chart-subtitle",
                            ),
                        ]
                    ),
                ],
            ),
            # Chart area with loading spinner
            dcc.Loading(
                type="circle",
                color="#005EB8",
                children=[
                    html.Div(
                        id="chart-container",
                        children=[
                            dcc.Graph(
                                id="pathway-chart",
                                style={"minHeight": "500px", "flex": "1"},
                                config={
                                    "displayModeBar": True,
                                    "displaylogo": False,
                                    "modeBarButtonsToRemove": [
                                        "lasso2d",
                                        "select2d",
                                    ],
                                },
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
