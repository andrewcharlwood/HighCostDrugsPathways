"""Chart card component — header, tabs, and dcc.Graph for icicle chart."""
from dash import html, dcc


def make_chart_card():
    """Return a chart card matching 01_nhs_classic.html structure.

    Contains:
    - Header with title and dynamic subtitle (hierarchy label)
    - Tab row (Icicle active, Sankey and Timeline as disabled placeholders)
    - dcc.Graph for the Plotly icicle figure
    """
    return html.Section(
        className="chart-card",
        **{"aria-label": "Patient pathway chart"},
        children=[
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
            # Tab row
            html.Div(
                className="chart-card__tabs",
                role="tablist",
                children=[
                    html.Button(
                        "Icicle",
                        className="chart-tab chart-tab--active",
                        role="tab",
                        **{"aria-selected": "true"},
                    ),
                    html.Button(
                        "Sankey",
                        className="chart-tab",
                        role="tab",
                        disabled=True,
                        **{"aria-selected": "false"},
                    ),
                    html.Button(
                        "Timeline",
                        className="chart-tab",
                        role="tab",
                        disabled=True,
                        **{"aria-selected": "false"},
                    ),
                ],
            ),
            # Chart area
            dcc.Graph(
                id="pathway-chart",
                style={"minHeight": "500px", "flex": "1"},
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
            ),
        ],
    )
