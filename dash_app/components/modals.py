"""Filter selection modals using Dash Mantine Components.

Three separate modals replace the single drawer:
- Drug Selection modal: 42 drugs in a ChipGroup with search filter
- Trust Selection modal: 7 trusts in a ChipGroup
- Directorate Browser modal: nested accordion with indication sub-items and drug fragment badges

Component IDs are preserved from the drawer so existing callbacks work unchanged:
- all-drugs-chips, trust-chips, drug-fragment pattern, clear-drug-filters
"""

from dash import html
import dash_mantine_components as dmc

from dash_app.data.card_browser import build_directorate_tree, get_all_drugs, get_all_trusts


def _make_directorate_accordion_item(directorate: str, indications: dict[str, list[str]]) -> dmc.AccordionItem:
    """Create an AccordionItem for a single directorate with nested indication panels."""
    panels = []
    for search_term, fragments in indications.items():
        panels.append(
            dmc.AccordionItem(
                value=f"{directorate}|{search_term}",
                children=[
                    dmc.AccordionControl(
                        search_term.title(),
                        className="modal-indication",
                    ),
                    dmc.AccordionPanel(
                        dmc.Group(
                            gap="xs",
                            children=[
                                dmc.Badge(
                                    frag,
                                    id={"type": "drug-fragment", "index": f"{directorate}|{search_term}|{frag}"},
                                    variant="light",
                                    size="md",
                                    className="modal-drug-badge",
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
                        dmc.Text(directorate.title(), fw=600, size="md"),
                        dmc.Badge(
                            str(len(indications)),
                            size="sm",
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


def make_drug_modal():
    """Build the drug selection modal."""
    drugs = get_all_drugs()

    return dmc.Modal(
        id="drug-modal",
        opened=False,
        centered=True,
        size="70%",
        title=dmc.Group(
            justify="space-between",
            style={"width": "100%"},
            children=[
                dmc.Text("Select Drugs", fw=600, size="lg"),
                dmc.Badge(
                    id="drug-modal-count",
                    children=f"0 of {len(drugs)} selected",
                    variant="light",
                    color="blue",
                ),
            ],
        ),
        overlayProps={"backgroundOpacity": 0.55, "blur": 3},
        children=[
            html.Div(
                className="modal-chips-scroll",
                children=[
                    dmc.Text(
                        f"{len(drugs)} drugs from pathway data",
                        size="xs",
                        c="dimmed",
                        mb=8,
                    ),
                    dmc.ChipGroup(
                        id="all-drugs-chips",
                        multiple=True,
                        value=[],
                        children=[
                            dmc.SimpleGrid(
                                cols=4,
                                spacing="sm",
                                verticalSpacing="xs",
                                children=[
                                    dmc.Chip(drug, value=drug, size="sm")
                                    for drug in drugs
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            dmc.Space(h=12),
            dmc.Group(
                justify="flex-end",
                children=[
                    dmc.Button(
                        "Clear Selection",
                        id="clear-drug-selection",
                        variant="subtle",
                        color="gray",
                        size="sm",
                    ),
                ],
            ),
        ],
    )


def make_trust_modal():
    """Build the trust selection modal."""
    trusts = get_all_trusts()

    return dmc.Modal(
        id="trust-modal",
        opened=False,
        centered=True,
        size="lg",
        title=dmc.Group(
            justify="space-between",
            style={"width": "100%"},
            children=[
                dmc.Text("Select Trusts", fw=600, size="lg"),
                dmc.Badge(
                    id="trust-modal-count",
                    children=f"0 of {len(trusts)} selected",
                    variant="light",
                    color="blue",
                ),
            ],
        ),
        overlayProps={"backgroundOpacity": 0.55, "blur": 3},
        children=[
            dmc.ChipGroup(
                id="trust-chips",
                multiple=True,
                value=[],
                children=[
                    dmc.Stack(
                        gap="xs",
                        children=[
                            dmc.Chip(trust, value=trust, size="md")
                            for trust in trusts
                        ],
                    ),
                ],
            ),
            dmc.Space(h=12),
            dmc.Group(
                justify="flex-end",
                children=[
                    dmc.Button(
                        "Clear Selection",
                        id="clear-trust-selection",
                        variant="subtle",
                        color="gray",
                        size="sm",
                    ),
                ],
            ),
        ],
    )


def make_directorate_modal():
    """Build the directorate browser modal with nested accordion."""
    directorate_tree = build_directorate_tree()

    directorate_items = [
        _make_directorate_accordion_item(directorate, indications)
        for directorate, indications in directorate_tree.items()
    ]

    total_indications = sum(len(v) for v in directorate_tree.values())

    return dmc.Modal(
        id="directorate-modal",
        opened=False,
        centered=True,
        size="70%",
        title=dmc.Text("Browse by Directorate", fw=600, size="lg"),
        overlayProps={"backgroundOpacity": 0.55, "blur": 3},
        children=[
            html.Div(
                className="modal-chips-scroll",
                children=[
                    dmc.Text(
                        f"{len(directorate_tree)} directorates \u00b7 {total_indications} indications",
                        size="xs",
                        c="dimmed",
                        mb=8,
                    ),
                    dmc.Accordion(
                        variant="separated",
                        children=directorate_items,
                        className="modal-directorate-accordion",
                    ),
                ],
            ),
            dmc.Space(h=12),
            dmc.Group(
                justify="flex-end",
                children=[
                    dmc.Button(
                        "Clear All Filters",
                        id="clear-drug-filters",
                        variant="subtle",
                        color="red",
                        size="sm",
                    ),
                ],
            ),
        ],
    )


def make_modals():
    """Return all three filter modals as a list of components."""
    return html.Div(
        children=[
            make_drug_modal(),
            make_trust_modal(),
            make_directorate_modal(),
        ],
    )
