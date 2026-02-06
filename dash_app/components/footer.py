"""Page footer component."""
from dash import html


def make_footer():
    """Build the page footer matching 01_nhs_classic.html."""
    return html.Footer(
        className="page-footer",
        children="NHS Norfolk and Waveney ICB \u2014 High Cost Drugs Analysis",
    )
