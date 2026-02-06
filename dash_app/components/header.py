"""Top header bar component with NHS branding, fraction KPIs, and data freshness."""
from dash import html


def make_header():
    """Return the fixed top header with NHS branding, fraction KPIs, and freshness indicators."""
    return html.Header(
        className="top-header",
        children=[
            # Left: brand (NHS logo + title)
            html.Div(
                className="top-header__brand",
                children=[
                    html.Div("NHS", className="top-header__logo"),
                    html.Div(
                        html.Div("HCD Analysis", className="top-header__title"),
                    ),
                ],
            ),

            # Center: 3 fraction KPIs (filtered / total)
            html.Div(
                className="top-header__kpis",
                children=[
                    html.Div(className="header-kpi", children=[
                        html.Span("—", id="kpi-filtered-patients", className="header-kpi__num"),
                        html.Span(" / ", className="header-kpi__sep"),
                        html.Span("—", id="kpi-total-patients", className="header-kpi__den"),
                        html.Span("patients", className="header-kpi__label"),
                    ]),
                    html.Div(className="header-kpi", children=[
                        html.Span("—", id="kpi-filtered-drugs", className="header-kpi__num"),
                        html.Span(" / ", className="header-kpi__sep"),
                        html.Span("—", id="kpi-total-drugs", className="header-kpi__den"),
                        html.Span("drugs", className="header-kpi__label"),
                    ]),
                    html.Div(className="header-kpi", children=[
                        html.Span("—", id="kpi-filtered-cost", className="header-kpi__num"),
                        html.Span(" / ", className="header-kpi__sep"),
                        html.Span("—", id="kpi-total-cost", className="header-kpi__den"),
                        html.Span("cost", className="header-kpi__label"),
                    ]),
                ],
            ),

            # Right: data freshness (status dot + record count + last updated)
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
                            "Updated: ",
                            html.Span("...", id="header-last-updated"),
                        ],
                    ),
                ],
            ),
        ],
    )
