"""Filter bar component — chart type toggle + date filter dropdowns."""
from dash import html, dcc


def make_filter_bar():
    """Return a filter bar matching 01_nhs_classic.html structure.

    Contains:
    - Chart type toggle pills (By Directory / By Indication)
    - Initiated dropdown (All years, Last 2 years, Last 1 year)
    - Last seen dropdown (Last 6 months, Last 12 months)

    Drug/directorate filters are in the drawer (Phase 4), not here.
    """
    return html.Section(
        className="filter-bar",
        **{"aria-label": "Filters"},
        children=[
            # Chart type toggle
            html.Div(
                className="filter-bar__group",
                children=[
                    html.Span("View", className="filter-bar__label"),
                    html.Div(
                        className="toggle-pills",
                        role="radiogroup",
                        **{"aria-label": "Chart view type"},
                        children=[
                            html.Button(
                                "By Directory",
                                id="chart-type-directory",
                                className="toggle-pill toggle-pill--active",
                                role="radio",
                                n_clicks=0,
                                **{"aria-checked": "true"},
                            ),
                            html.Button(
                                "By Indication",
                                id="chart-type-indication",
                                className="toggle-pill",
                                role="radio",
                                n_clicks=0,
                                **{"aria-checked": "false"},
                            ),
                        ],
                    ),
                ],
            ),
            # Divider
            html.Div(className="filter-bar__divider"),
            # Initiated filter
            html.Div(
                className="filter-bar__group",
                children=[
                    html.Span("Initiated", className="filter-bar__label"),
                    dcc.Dropdown(
                        id="filter-initiated",
                        options=[
                            {"label": "All years", "value": "all"},
                            {"label": "Last 2 years", "value": "2yr"},
                            {"label": "Last 1 year", "value": "1yr"},
                        ],
                        value="all",
                        clearable=False,
                        searchable=False,
                        className="filter-dropdown",
                    ),
                ],
            ),
            # Last seen filter
            html.Div(
                className="filter-bar__group",
                children=[
                    html.Span("Last seen", className="filter-bar__label"),
                    dcc.Dropdown(
                        id="filter-last-seen",
                        options=[
                            {"label": "Last 6 months", "value": "6mo"},
                            {"label": "Last 12 months", "value": "12mo"},
                        ],
                        value="6mo",
                        clearable=False,
                        searchable=False,
                        className="filter-dropdown",
                    ),
                ],
            ),
        ],
    )
