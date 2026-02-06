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
