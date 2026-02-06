"""Callbacks for drug selection: fragment matching and clear filters.

The open_drawer callback was removed in Task 7.3 (sidebar restructure) because
the sidebar no longer has filter trigger items. Task 7.4 will replace the drawer
with modals opened from the filter bar.
"""
from dash import Input, Output, State, ctx, no_update, ALL


def register_drawer_callbacks(app):
    """Register drug/trust selection callbacks (fragment matching + clear)."""

    @app.callback(
        Output("all-drugs-chips", "value"),
        Output("trust-chips", "value"),
        Input({"type": "drug-fragment", "index": ALL}, "n_clicks"),
        Input("clear-drug-filters", "n_clicks"),
        State("all-drugs-chips", "value"),
        State("reference-data", "data"),
        prevent_initial_call=True,
    )
    def handle_fragment_or_clear(fragment_clicks, _clear_clicks, current_chips, ref_data):
        """Handle drug fragment badge click (substring match) or clear all filters.

        Fragment click: find all full drug names containing the fragment substring,
        toggle them in the chip selection. Trust chips unchanged.
        Clear click: reset both drug and trust chip selections.
        """
        triggered = ctx.triggered_id

        # Clear button — reset both drug and trust chips
        if triggered == "clear-drug-filters":
            return [], []

        # Fragment badge click — triggered_id is a dict like {"type": "drug-fragment", "index": "DIR|FRAG"}
        if isinstance(triggered, dict) and triggered.get("type") == "drug-fragment":
            # Check if any fragment was actually clicked (not just initial render)
            if not any(n for n in (fragment_clicks or []) if n):
                return no_update, no_update

            fragment_key = triggered["index"]  # e.g. "CARDIOLOGY|acute coronary syndrome|RIVAROXABAN"
            fragment = fragment_key.rsplit("|", 1)[-1] if "|" in fragment_key else fragment_key

            # Get all available drugs from reference data
            all_drugs = (ref_data or {}).get("available_drugs", [])

            # Find drugs whose names contain this fragment (case-insensitive substring)
            matching_drugs = [
                drug for drug in all_drugs
                if fragment.upper() in drug.upper()
            ]

            if not matching_drugs:
                return no_update, no_update

            # Toggle: if all matching drugs are already selected, deselect them;
            # otherwise, add them to selection
            current = set(current_chips or [])
            all_selected = all(d in current for d in matching_drugs)

            if all_selected:
                updated = current - set(matching_drugs)
            else:
                updated = current | set(matching_drugs)

            return sorted(updated), no_update

        return no_update, no_update
