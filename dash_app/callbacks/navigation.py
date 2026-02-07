"""Callbacks for view switching between Patient Pathways, Trust Comparison, and Trends."""
from dash import Input, Output


def register_navigation_callbacks(app):
    """Register view switching callbacks."""

    @app.callback(
        Output("patient-pathways-view", "style"),
        Output("trust-comparison-view", "style"),
        Output("trends-view", "style"),
        Output("nav-patient-pathways", "className"),
        Output("nav-trust-comparison", "className"),
        Output("nav-trends", "className"),
        Input("app-state", "data"),
    )
    def switch_view(app_state):
        """Show/hide views and update sidebar active state based on active_view."""
        show = {}
        hide = {"display": "none"}
        active_cls = "sidebar__item sidebar__item--active"
        inactive_cls = "sidebar__item"

        if not app_state:
            return show, hide, hide, active_cls, inactive_cls, inactive_cls

        view = app_state.get("active_view", "patient-pathways")

        if view == "patient-pathways":
            return show, hide, hide, active_cls, inactive_cls, inactive_cls
        elif view == "trust-comparison":
            return hide, show, hide, inactive_cls, active_cls, inactive_cls
        else:  # trends
            return hide, hide, show, inactive_cls, inactive_cls, active_cls
