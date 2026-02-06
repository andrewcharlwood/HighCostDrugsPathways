"""Callbacks for filter selection modals: open/close, fragment matching, clear, count badges."""
from dash import Input, Output, State, ctx, no_update, ALL


def register_modal_callbacks(app):
    """Register all modal-related callbacks."""

    # ── Open modals from filter bar buttons ──

    @app.callback(
        Output("drug-modal", "opened"),
        Input("open-drug-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_drug_modal(_n):
        return True

    @app.callback(
        Output("trust-modal", "opened"),
        Input("open-trust-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_trust_modal(_n):
        return True

    @app.callback(
        Output("directorate-modal", "opened"),
        Input("open-directorate-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def open_directorate_modal(_n):
        return True

    # ── Fragment matching + clear ──

    @app.callback(
        Output("all-drugs-chips", "value"),
        Output("trust-chips", "value"),
        Input({"type": "drug-fragment", "index": ALL}, "n_clicks"),
        Input("clear-drug-filters", "n_clicks"),
        Input("clear-drug-selection", "n_clicks"),
        Input("clear-trust-selection", "n_clicks"),
        Input("clear-all-filters", "n_clicks"),
        State("all-drugs-chips", "value"),
        State("trust-chips", "value"),
        State("reference-data", "data"),
        prevent_initial_call=True,
    )
    def handle_selection_actions(
        fragment_clicks, _clear_all_clicks, _clear_drug_clicks,
        _clear_trust_clicks, _clear_global_clicks,
        current_drugs, current_trusts, ref_data
    ):
        """Handle fragment clicks, per-modal clears, and global clear."""
        triggered = ctx.triggered_id

        # Global clear (filter bar) or directorate modal clear
        if triggered in ("clear-drug-filters", "clear-all-filters"):
            return [], []

        # Drug modal clear
        if triggered == "clear-drug-selection":
            return [], no_update

        # Trust modal clear
        if triggered == "clear-trust-selection":
            return no_update, []

        # Fragment badge click
        if isinstance(triggered, dict) and triggered.get("type") == "drug-fragment":
            if not any(n for n in (fragment_clicks or []) if n):
                return no_update, no_update

            fragment_key = triggered["index"]
            fragment = fragment_key.rsplit("|", 1)[-1] if "|" in fragment_key else fragment_key

            all_drugs = (ref_data or {}).get("available_drugs", [])
            matching_drugs = [
                drug for drug in all_drugs
                if fragment.upper() in drug.upper()
            ]

            if not matching_drugs:
                return no_update, no_update

            current = set(current_drugs or [])
            all_selected = all(d in current for d in matching_drugs)

            if all_selected:
                updated = current - set(matching_drugs)
            else:
                updated = current | set(matching_drugs)

            return sorted(updated), no_update

        return no_update, no_update

    # ── Count badges in filter bar ──

    @app.callback(
        Output("drug-count-badge", "children"),
        Output("drug-count-badge", "className"),
        Output("trust-count-badge", "children"),
        Output("trust-count-badge", "className"),
        Output("drug-modal-count", "children"),
        Output("trust-modal-count", "children"),
        Input("all-drugs-chips", "value"),
        Input("trust-chips", "value"),
        State("reference-data", "data"),
    )
    def update_count_badges(selected_drugs, selected_trusts, ref_data):
        """Update selection count badges in filter bar and modal headers."""
        drug_count = len(selected_drugs or [])
        trust_count = len(selected_trusts or [])

        all_drugs = (ref_data or {}).get("available_drugs", [])
        all_trusts = (ref_data or {}).get("available_trusts", [])
        total_drugs = len(all_drugs) if all_drugs else 42
        total_trusts = len(all_trusts) if all_trusts else 7

        hidden = "filter-btn__badge filter-btn__badge--hidden"
        visible = "filter-btn__badge"

        drug_badge_text = str(drug_count) if drug_count else ""
        drug_badge_class = visible if drug_count else hidden
        trust_badge_text = str(trust_count) if trust_count else ""
        trust_badge_class = visible if trust_count else hidden

        drug_modal_text = f"{drug_count} of {total_drugs} selected"
        trust_modal_text = f"{trust_count} of {total_trusts} selected"

        return (
            drug_badge_text, drug_badge_class,
            trust_badge_text, trust_badge_class,
            drug_modal_text, trust_modal_text,
        )
