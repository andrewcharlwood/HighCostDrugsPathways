"""Left sidebar navigation component matching 01_nhs_classic.html design."""
from urllib.parse import quote as url_quote

from dash import html


def _svg_icon(svg_body):
    """Wrap an SVG body string into an html.Img using a data URI."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="2">{svg_body}</svg>'
    )
    return html.Img(
        src=f"data:image/svg+xml,{url_quote(svg)}",
        className="sidebar__icon",
    )


# SVG icon bodies (Feather-style)
_ICONS = {
    "pathway": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    "icicle": '<rect x="3" y="3" width="18" height="4" rx="1"/><rect x="3" y="10" width="10" height="4" rx="1"/><rect x="3" y="17" width="6" height="4" rx="1"/>',
    "sankey": '<path d="M6 3v18"/><path d="M18 3v18"/><path d="M6 8c6 0 6 5 12 5"/><path d="M6 16c4 0 4-3 12-3"/>',
    "timeline": '<line x1="3" y1="12" x2="21" y2="12"/><circle cx="6" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="18" cy="12" r="2"/>',
}


def make_sidebar():
    """Return the fixed left sidebar navigation."""
    return html.Nav(
        className="sidebar",
        **{"aria-label": "Main navigation"},
        children=[
            # Overview section
            html.Div(
                className="sidebar__section",
                children=[
                    html.Div("Overview", className="sidebar__label"),
                    _sidebar_item("Pathway Overview", "pathway", active=True),
                ],
            ),
            # Chart views section
            html.Div(
                className="sidebar__section",
                children=[
                    html.Div("Chart Views", className="sidebar__label"),
                    _sidebar_item("Icicle Chart", "icicle", active=True),
                    _sidebar_item("Sankey Diagram", "sankey", disabled=True),
                    _sidebar_item("Timeline", "timeline", disabled=True),
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


def _sidebar_item(label, icon_key, active=False, disabled=False, item_id=None):
    """Create a single sidebar navigation item."""
    class_name = "sidebar__item"
    if active:
        class_name += " sidebar__item--active"
    if disabled:
        class_name += " sidebar__item--disabled"

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
