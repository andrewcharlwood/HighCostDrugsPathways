"""Top header bar component matching 01_nhs_classic.html design."""
from dash import html


def make_header():
    """Return the fixed top header with NHS branding and data freshness indicators."""
    return html.Header(
        className="top-header",
        children=[
            # Brand area (NHS logo + title) with angled clip-path
            html.Div(
                className="top-header__brand",
                children=[
                    html.Div("NHS", className="top-header__logo"),
                    html.Div(
                        html.Div("HCD Analysis", className="top-header__title"),
                    ),
                ],
            ),
            # Breadcrumb
            html.Div(
                className="top-header__breadcrumb",
                children=[
                    "Dashboard \u203A ",
                    html.Strong("Pathway Analysis"),
                ],
            ),
            # Right side: status dot + record count + last updated
            html.Div(
                className="top-header__right",
                children=[
                    html.Span(
                        children=[
                            html.Span(className="status-dot"),
                            html.Span("...", id="header-record-count"),
                        ],
                    ),
                    html.Span(
                        children=[
                            "Last updated: ",
                            html.Span("...", id="header-last-updated"),
                        ],
                    ),
                ],
            ),
        ],
    )
