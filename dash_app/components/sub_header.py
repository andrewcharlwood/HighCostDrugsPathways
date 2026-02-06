"""Global filter sub-header — chart type toggle + date filter dropdowns.

Fixed bar below the main header, constant across both views.
"""
from dash import html, dcc


def make_sub_header():
    """Return the global filter sub-header bar."""
    return html.Div(
        className="sub-header",
        children=[
            # Chart type toggle
            html.Div(
                className="sub-header__group",
                children=[
                    html.Span("View", className="sub-header__label"),
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
            html.Div(className="sub-header__divider"),
            # Initiated filter
            html.Div(
                className="sub-header__group",
                children=[
                    html.Span("Initiated", className="sub-header__label"),
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
                className="sub-header__group",
                children=[
                    html.Span("Last seen", className="sub-header__label"),
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
