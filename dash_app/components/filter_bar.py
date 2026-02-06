"""Filter bar component — drug, trust, and directorate filter buttons.

View-specific controls for Patient Pathways. Global controls (chart type
toggle, date filters) live in sub_header.py.
"""
from dash import html


def make_filter_bar():
    """Return a filter bar with drug, trust, and directorate filter buttons."""
    return html.Section(
        className="filter-bar",
        **{"aria-label": "Filters"},
        children=[
            # Filter trigger buttons
            html.Div(
                className="filter-bar__group",
                children=[
                    html.Button(
                        children=[
                            "Drugs",
                            html.Span(
                                id="drug-count-badge",
                                className="filter-btn__badge filter-btn__badge--hidden",
                            ),
                        ],
                        id="open-drug-modal",
                        className="filter-btn",
                        n_clicks=0,
                    ),
                    html.Button(
                        children=[
                            "Trusts",
                            html.Span(
                                id="trust-count-badge",
                                className="filter-btn__badge filter-btn__badge--hidden",
                            ),
                        ],
                        id="open-trust-modal",
                        className="filter-btn",
                        n_clicks=0,
                    ),
                    html.Button(
                        children=[
                            "Directorates",
                            html.Span(
                                id="directorate-count-badge",
                                className="filter-btn__badge filter-btn__badge--hidden",
                            ),
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
