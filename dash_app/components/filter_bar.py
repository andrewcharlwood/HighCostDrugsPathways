"""Patient Pathways filter strip — drug, trust, and directorate filter buttons.

View-specific controls for Patient Pathways only. Hidden when on Trust Comparison.
Global controls (chart type toggle, date filters) live in sub_header.py.
"""
from dash import html


def make_filter_bar():
    """Return a pathway filter strip with drug, trust, and directorate buttons."""
    return html.Div(
        className="pathway-filters",
        id="pathway-filters",
        children=[
            html.Div(
                className="pathway-filters__buttons",
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
                    html.Span(className="pathway-filters__separator"),
                    html.Button(
                        "Clear All",
                        id="clear-all-filters",
                        className="filter-btn filter-btn--clear",
                        n_clicks=0,
                    ),
                ],
            ),
        ],
    )
