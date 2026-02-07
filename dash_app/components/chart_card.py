"""Chart card component — tab bar, header, and dcc.Graph for charts."""
from dash import html, dcc
import dash_mantine_components as dmc


# Patient Pathways view: Icicle, Sankey, Heatmap
TAB_DEFINITIONS = [
    ("icicle", "Icicle"),
    ("sankey", "Sankey"),
    ("heatmap", "Heatmap"),
    ("funnel", "Funnel"),
    ("depth", "Depth"),
    ("scatter", "Scatter"),
    ("network", "Network"),
    ("timeline", "Timeline"),
    ("doses", "Doses"),
]

# Full set retained for Trust Comparison dashboard (Phase 10.8)
ALL_TAB_DEFINITIONS = [
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
    - Tab bar with 2 chart tabs (Icicle active by default, Sankey)
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
                    # Heatmap metric toggle — visible only when heatmap tab active
                    html.Div(
                        id="heatmap-metric-wrapper",
                        style={"display": "none"},
                        children=[
                            dmc.SegmentedControl(
                                id="heatmap-metric-toggle",
                                data=[
                                    {"value": "patients", "label": "Patients"},
                                    {"value": "cost", "label": "Cost"},
                                    {"value": "cost_pp_pa", "label": "Cost p.a."},
                                ],
                                value="patients",
                                size="xs",
                            ),
                        ],
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
                                style={"flex": "1", "minHeight": "0"},
                                responsive=True,
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
