"""Callbacks for tab switching, pathway data loading, and chart rendering."""
import logging

from dash import Input, Output, State, ctx, no_update
import plotly.graph_objects as go

from dash_app.components.chart_card import TAB_DEFINITIONS

log = logging.getLogger(__name__)

# Tab IDs for callback inputs
_TAB_IDS = [f"tab-{tab_id}" for tab_id, _ in TAB_DEFINITIONS]


def _empty_figure(message):
    """Return a blank Plotly figure with a centered message annotation."""
    fig = go.Figure()
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"t": 0, "l": 0, "r": 0, "b": 0},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {
                    "size": 16,
                    "color": "#768692",
                    "family": "Source Sans 3, Arial, sans-serif",
                },
                "xanchor": "center",
                "yanchor": "middle",
            }
        ],
    )
    return fig


def _generate_chart_title(app_state):
    """Generate chart title from current filter state."""
    parts = []

    chart_type = app_state.get("chart_type", "directory")
    parts.append("By Indication" if chart_type == "indication" else "By Directory")

    initiated = app_state.get("initiated", "all")
    initiated_labels = {"all": "All years", "1yr": "Last 1 year", "2yr": "Last 2 years"}
    last_seen = app_state.get("last_seen", "6mo")
    last_seen_labels = {"6mo": "Last 6 months", "12mo": "Last 12 months"}
    parts.append(
        f"{initiated_labels.get(initiated, 'All years')} / "
        f"{last_seen_labels.get(last_seen, 'Last 6 months')}"
    )

    selected_drugs = app_state.get("selected_drugs") or []
    if selected_drugs:
        if len(selected_drugs) <= 3:
            parts.append(", ".join(selected_drugs))
        else:
            parts.append(f"{len(selected_drugs)} drugs selected")

    selected_directorates = app_state.get("selected_directorates") or []
    if selected_directorates:
        if len(selected_directorates) <= 2:
            parts.append(", ".join(selected_directorates))
        else:
            parts.append(f"{len(selected_directorates)} directorates")

    selected_trusts = app_state.get("selected_trusts") or []
    if selected_trusts:
        if len(selected_trusts) <= 2:
            parts.append(", ".join(selected_trusts))
        else:
            parts.append(f"{len(selected_trusts)} trusts")

    return " | ".join(parts) if parts else "All Patients"


def register_chart_callbacks(app):
    """Register tab switching, pathway data loading, and chart rendering callbacks."""

    # --- Tab switching callback ---
    tab_inputs = [Input(tid, "n_clicks") for tid in _TAB_IDS]
    tab_outputs = [Output(tid, "className") for tid in _TAB_IDS]

    @app.callback(
        Output("active-tab", "data"),
        *tab_outputs,
        *tab_inputs,
        State("active-tab", "data"),
        prevent_initial_call=True,
    )
    def switch_tab(*args):
        """Handle tab button clicks — update active-tab store and CSS classes."""
        n_tabs = len(_TAB_IDS)
        # args layout: n_clicks_0..n_clicks_N-1, current_active_tab
        current_tab = args[-1] or "icicle"

        triggered_id = ctx.triggered_id
        if not triggered_id:
            return (no_update,) * (1 + n_tabs)

        # Determine new active tab from triggered button ID
        new_tab = current_tab
        for tab_id, (short_id, _) in zip(_TAB_IDS, TAB_DEFINITIONS):
            if triggered_id == tab_id:
                new_tab = short_id
                break

        # Build CSS class outputs
        base = "chart-tab"
        active = f"{base} chart-tab--active"
        classes = [active if short_id == new_tab else base for short_id, _ in TAB_DEFINITIONS]

        return (new_tab, *classes)

    # --- Pathway data loading callback ---
    @app.callback(
        Output("chart-data", "data"),
        Input("app-state", "data"),
    )
    def load_pathway_data(app_state):
        """Load pathway nodes when app-state changes (filter or chart type)."""
        if not app_state:
            return no_update

        from dash_app.data.queries import load_pathway_data as query_pathway_data

        filter_id = app_state.get("date_filter_id", "all_6mo")
        chart_type = app_state.get("chart_type", "directory")
        selected_drugs = app_state.get("selected_drugs") or None
        selected_directorates = app_state.get("selected_directorates") or None
        selected_trusts = app_state.get("selected_trusts") or None

        try:
            return query_pathway_data(
                filter_id=filter_id,
                chart_type=chart_type,
                selected_drugs=selected_drugs,
                selected_directorates=selected_directorates,
                selected_trusts=selected_trusts,
            )
        except Exception:
            log.exception("Failed to load pathway data")
            return {
                "nodes": [],
                "unique_patients": 0,
                "total_drugs": 0,
                "total_cost": 0.0,
                "error": "Database query failed. Check logs for details.",
            }

    # --- Chart rendering callback ---
    @app.callback(
        Output("pathway-chart", "figure"),
        Output("chart-subtitle", "children"),
        Input("chart-data", "data"),
        Input("active-tab", "data"),
        Input("app-state", "data"),
    )
    def update_chart(chart_data, active_tab, app_state):
        """Render the active tab's chart from chart-data nodes."""
        active_tab = active_tab or "icicle"
        chart_type = (app_state or {}).get("chart_type", "directory")

        if chart_type == "indication":
            subtitle = "Trust \u2192 Indication \u2192 Drug \u2192 Patient Pathway"
        else:
            subtitle = "Trust \u2192 Directorate \u2192 Drug \u2192 Patient Pathway"

        if not chart_data:
            return no_update, no_update

        error_msg = chart_data.get("error")
        if error_msg:
            return _empty_figure(error_msg), subtitle

        if not chart_data.get("nodes"):
            return _empty_figure(
                "No matching pathways found.\n"
                "Try adjusting your filters."
            ), subtitle

        # Lazy rendering — only compute the active tab's chart
        if active_tab == "icicle":
            from visualization.plotly_generator import create_icicle_from_nodes

            title = _generate_chart_title(app_state) if app_state else ""
            fig = create_icicle_from_nodes(chart_data["nodes"], title)
        else:
            # Placeholder for charts not yet implemented
            tab_label = dict(TAB_DEFINITIONS).get(active_tab, active_tab)
            fig = _empty_figure(f"{tab_label} chart — coming soon")

        return fig, subtitle
