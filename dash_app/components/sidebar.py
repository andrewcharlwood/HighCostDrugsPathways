"""Left sidebar navigation component matching 01_nhs_classic.html design."""
from urllib.parse import quote as url_quote

from dash import html


def _svg_icon(svg_body):
    """Wrap an SVG body string into an html.Img using a data URI.

    This avoids needing dash-svg or dangerouslySetInnerHTML.
    The SVG icons are copied from 01_nhs_classic.html.
    """
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="2">{svg_body}</svg>'
    )
    return html.Img(
        src=f"data:image/svg+xml,{url_quote(svg)}",
        className="sidebar__icon",
    )


# SVG icon bodies from 01_nhs_classic.html
_ICONS = {
    "pathway": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "drug": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>',
    "trust": '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    "directory": '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
    "indication": '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/>',
    "cost": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    "export": '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
}


def make_sidebar():
    """Return the fixed left sidebar navigation."""
    return html.Nav(
        className="sidebar",
        **{"aria-label": "Main navigation"},
        children=[
            # Analysis section
            html.Div(
                className="sidebar__section",
                children=[
                    html.Div("Analysis", className="sidebar__label"),
                    _sidebar_item("Pathway Overview", "pathway", active=True),
                    _sidebar_item(
                        "Drug Selection", "drug", item_id="sidebar-drug-selection"
                    ),
                    _sidebar_item("Trust Selection", "trust"),
                    _sidebar_item("Directory Selection", "directory"),
                    _sidebar_item(
                        "Indications", "indication", item_id="sidebar-indications"
                    ),
                ],
            ),
            # Reports section
            html.Div(
                className="sidebar__section",
                children=[
                    html.Div("Reports", className="sidebar__label"),
                    _sidebar_item("Cost Analysis", "cost"),
                    _sidebar_item("Export Data", "export"),
                ],
            ),
            # Footer
            html.Div(
                className="sidebar__footer",
                children=[
                    "NHS Norfolk & Waveney ICB",
                    html.Br(),
                    "High Cost Drugs Programme",
                ],
            ),
        ],
    )


def _sidebar_item(label, icon_key, active=False, item_id=None):
    """Create a single sidebar navigation item."""
    class_name = "sidebar__item"
    if active:
        class_name += " sidebar__item--active"

    props = {"className": class_name}
    if item_id:
        props["id"] = item_id
        props["n_clicks"] = 0

    return html.A(
        **props,
        children=[
            _svg_icon(_ICONS[icon_key]),
            label,
        ],
    )
