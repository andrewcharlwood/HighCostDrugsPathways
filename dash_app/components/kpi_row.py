"""KPI row component — 4 metric cards with callback-updatable values."""
from dash import html


def make_kpi_row():
    """Return a section with 4 KPI cards matching 01_nhs_classic.html structure."""
    return html.Section(
        className="kpi-row",
        **{"aria-label": "Key performance indicators"},
        children=[
            _kpi_card("Unique Patients", "kpi-patients", "—", "across all trusts"),
            _kpi_card("Drug Types", "kpi-drugs", "—", "high-cost drugs tracked"),
            _kpi_card("Total Cost", "kpi-cost", "—", "current period spend"),
            _kpi_card(
                "Indication Match",
                "kpi-match",
                "—",
                "GP diagnosis confirmed",
                modifier="kpi-card--green",
            ),
        ],
    )


def _kpi_card(label, value_id, default_value, sub_text, modifier=None):
    """Build a single KPI card.

    Args:
        label: uppercase label text
        value_id: HTML id for the value span (for callback Output)
        default_value: initial display value before callbacks fire
        sub_text: description below the value
        modifier: optional CSS modifier class (e.g. 'kpi-card--green')
    """
    card_class = "kpi-card"
    if modifier:
        card_class += f" {modifier}"

    return html.Div(
        className=card_class,
        children=[
            html.Div(label, className="kpi-card__label"),
            html.Div(default_value, className="kpi-card__value", id=value_id),
            html.Div(sub_text, className="kpi-card__sub"),
        ],
    )
