"""Chart card component — header and dcc.Graph for icicle chart."""
from dash import html, dcc


def make_chart_card():
    """Return a chart card matching 01_nhs_classic.html structure.

    Contains:
    - Header with title and dynamic subtitle (hierarchy label)
    - dcc.Loading wrapper around dcc.Graph for loading spinner
    Chart view selection (icicle/sankey/timeline) is in the sidebar.
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
