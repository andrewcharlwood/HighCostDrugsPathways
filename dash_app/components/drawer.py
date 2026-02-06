"""
Filter drawer component using Dash Mantine Components.

Provides a right-side drawer with:
- "All Drugs" section: flat alphabetical list of all drugs from pathway_nodes
- "Trusts" section: all NHS trusts from pathway_nodes for trust filtering
- Directorate cards: grouped by PrimaryDirectorate from DimSearchTerm.csv,
  with Accordion items per Search_Term containing drug fragment chips
- "Clear Filters" button at the bottom
"""

from dash import html
import dash_mantine_components as dmc

from dash_app.data.card_browser import build_directorate_tree, get_all_drugs, get_all_trusts


def _make_drug_chips(drugs: list[str]) -> dmc.ChipGroup:
    """Create a ChipGroup with multiple selection for the 'All Drugs' section."""
    return dmc.ChipGroup(
        id="all-drugs-chips",
        multiple=True,
        value=[],
        children=[
            dmc.Chip(drug, value=drug, size="xs")
            for drug in drugs
        ],
    )


def _make_trust_chips(trusts: list[str]) -> dmc.ChipGroup:
    """Create a ChipGroup with multiple selection for the 'Trusts' section."""
    return dmc.ChipGroup(
        id="trust-chips",
        multiple=True,
        value=[],
        children=[
            dmc.Chip(trust, value=trust, size="xs")
            for trust in trusts
        ],
    )


def _make_directorate_card(directorate: str, indications: dict[str, list[str]]) -> dmc.AccordionItem:
    """
    Create an AccordionItem for a single directorate.

    Each indication becomes a panel with drug fragment badges inside.
    """
    panels = []
    for search_term, fragments in indications.items():
        panels.append(
            dmc.AccordionItem(
                value=f"{directorate}|{search_term}",
                children=[
                    dmc.AccordionControl(
                        search_term.title(),
                        className="drawer-indication",
                    ),
                    dmc.AccordionPanel(
                        dmc.Group(
                            gap="xs",
                            children=[
                                dmc.Badge(
                                    frag,
                                    id={"type": "drug-fragment", "index": f"{directorate}|{search_term}|{frag}"},
                                    variant="light",
                                    size="sm",
                                    className="drawer-drug-badge",
                                    style={"cursor": "pointer"},
                                )
                                for frag in fragments
                            ],
                        ),
                    ),
                ],
            )
        )

    return dmc.AccordionItem(
        value=directorate,
        children=[
            dmc.AccordionControl(
                dmc.Group(
                    gap="xs",
                    children=[
                        dmc.Text(directorate.title(), fw=600, size="sm"),
                        dmc.Badge(
                            str(len(indications)),
                            size="xs",
                            variant="light",
                            color="gray",
                        ),
                    ],
                ),
            ),
            dmc.AccordionPanel(
                dmc.Accordion(
                    variant="separated",
                    children=panels,
                ),
            ),
        ],
    )


def make_drawer():
    """
    Build the drug browser drawer component.

    Returns a dmc.Drawer that will be opened/closed via callbacks in Phase 4.2.
    """
    drugs = get_all_drugs()
    trusts = get_all_trusts()
    directorate_tree = build_directorate_tree()

    # All Drugs section
    all_drugs_section = html.Div(
        className="drawer-section",
        children=[
            dmc.Text("All Drugs", fw=700, size="sm", className="drawer-section-title"),
            dmc.Text(
                f"{len(drugs)} drugs from pathway data",
                size="xs",
                c="dimmed",
            ),
            html.Div(
                className="drawer-chips-wrap",
                children=_make_drug_chips(drugs),
            ),
        ],
    )

    # Trusts section
    trusts_section = html.Div(
        className="drawer-section",
        children=[
            dmc.Text("Trusts", fw=700, size="sm", className="drawer-section-title"),
            dmc.Text(
                f"{len(trusts)} NHS trusts",
                size="xs",
                c="dimmed",
            ),
            html.Div(
                className="drawer-chips-wrap",
                children=_make_trust_chips(trusts),
            ),
        ],
    )

    # Directorate cards section
    directorate_items = [
        _make_directorate_card(directorate, indications)
        for directorate, indications in directorate_tree.items()
    ]

    directorate_section = html.Div(
        className="drawer-section",
        children=[
            dmc.Text("By Directorate", fw=700, size="sm", className="drawer-section-title"),
            dmc.Text(
                f"{len(directorate_tree)} directorates \u00b7 {sum(len(v) for v in directorate_tree.values())} indications",
                size="xs",
                c="dimmed",
            ),
            dmc.Accordion(
                variant="separated",
                children=directorate_items,
                className="drawer-directorate-accordion",
            ),
        ],
    )

    # Clear filters button
    clear_button = dmc.Button(
        "Clear All Filters",
        id="clear-drug-filters",
        variant="outline",
        color="red",
        fullWidth=True,
        className="drawer-clear-btn",
    )

    return dmc.Drawer(
        id="drug-drawer",
        opened=False,
        position="right",
        size="480px",
        title=dmc.Text("Drug & Indication Browser", fw=700, size="lg"),
        children=[
            dmc.ScrollArea(
                h="calc(100vh - 140px)",
                children=dmc.Stack(
                    gap="md",
                    children=[
                        all_drugs_section,
                        dmc.Divider(),
                        trusts_section,
                        dmc.Divider(),
                        directorate_section,
                        clear_button,
                    ],
                ),
            ),
        ],
    )
