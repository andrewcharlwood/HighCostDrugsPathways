"""Callbacks for the drug browser drawer: open/close, drug selection, fragment matching, clear."""
from dash import Input, Output, State, ctx, no_update, ALL


def register_drawer_callbacks(app):
    """Register drawer-related callbacks."""

    @app.callback(
        Output("drug-drawer", "opened"),
        Input("sidebar-drug-selection", "n_clicks"),
        Input("sidebar-indications", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_drawer(_drug_clicks, _indication_clicks):
        """Open the drawer when sidebar Drug Selection or Indications is clicked."""
        return True

    @app.callback(
        Output("all-drugs-chips", "value"),
        Input({"type": "drug-fragment", "index": ALL}, "n_clicks"),
        Input("clear-drug-filters", "n_clicks"),
        State("all-drugs-chips", "value"),
        State("reference-data", "data"),
        prevent_initial_call=True,
    )
    def handle_fragment_or_clear(fragment_clicks, _clear_clicks, current_chips, ref_data):
        """Handle drug fragment badge click (substring match) or clear all filters.

        Fragment click: find all full drug names containing the fragment substring,
        toggle them in the chip selection.
        Clear click: reset chip selection to empty.
        """
        triggered = ctx.triggered_id

        # Clear button
        if triggered == "clear-drug-filters":
            return []

        # Fragment badge click — triggered_id is a dict like {"type": "drug-fragment", "index": "DIR|FRAG"}
        if isinstance(triggered, dict) and triggered.get("type") == "drug-fragment":
            # Check if any fragment was actually clicked (not just initial render)
            if not any(n for n in (fragment_clicks or []) if n):
                return no_update

            fragment_key = triggered["index"]  # e.g. "CARDIOLOGY|ABCIXIMAB"
            fragment = fragment_key.split("|", 1)[-1] if "|" in fragment_key else fragment_key

            # Get all available drugs from reference data
            all_drugs = (ref_data or {}).get("available_drugs", [])

            # Find drugs whose names contain this fragment (case-insensitive substring)
            matching_drugs = [
                drug for drug in all_drugs
                if fragment.upper() in drug.upper()
            ]

            if not matching_drugs:
                return no_update

            # Toggle: if all matching drugs are already selected, deselect them;
            # otherwise, add them to selection
            current = set(current_chips or [])
            all_selected = all(d in current for d in matching_drugs)

            if all_selected:
                updated = current - set(matching_drugs)
            else:
                updated = current | set(matching_drugs)

            return sorted(updated)

        return no_update
