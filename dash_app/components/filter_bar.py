"""Filter bar component — chart type toggle, date filters, and modal trigger buttons."""
from dash import html, dcc


def make_filter_bar():
    """Return a filter bar with chart type toggle, date dropdowns, and filter buttons.

    Filter buttons open modals for drug, trust, and directorate selection.
    Each button shows a selection count badge (updated via callbacks).
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
            # Divider before filter buttons
            html.Div(className="filter-bar__divider"),
            # Filter trigger buttons
            html.Div(
                className="filter-bar__group",
                children=[
                    html.Button(
                        children=[
                            "Drugs",
                            html.Span(id="drug-count-badge", className="filter-btn__badge filter-btn__badge--hidden"),
                        ],
                        id="open-drug-modal",
                        className="filter-btn",
                        n_clicks=0,
                    ),
                    html.Button(
                        children=[
                            "Trusts",
                            html.Span(id="trust-count-badge", className="filter-btn__badge filter-btn__badge--hidden"),
                        ],
                        id="open-trust-modal",
                        className="filter-btn",
                        n_clicks=0,
                    ),
                    html.Button(
                        children=[
                            "Directorates",
                            html.Span(id="directorate-count-badge", className="filter-btn__badge filter-btn__badge--hidden"),
                        ],
                        id="open-directorate-modal",
                        className="filter-btn",
                        n_clicks=0,
                    ),
                ],
            ),
            # Clear all filters
            html.Button(
                "Clear All",
                id="clear-all-filters",
                className="filter-btn filter-btn--clear",
                n_clicks=0,
            ),
        ],
    )
