"""Callbacks for view switching between Patient Pathways and Trust Comparison."""
from dash import Input, Output


def register_navigation_callbacks(app):
    """Register view switching callbacks."""

    @app.callback(
        Output("patient-pathways-view", "style"),
        Output("trust-comparison-view", "style"),
        Output("nav-patient-pathways", "className"),
        Output("nav-trust-comparison", "className"),
        Input("app-state", "data"),
    )
    def switch_view(app_state):
        """Show/hide views and update sidebar active state based on active_view."""
        if not app_state:
            return {}, {"display": "none"}, "sidebar__item sidebar__item--active", "sidebar__item"

        view = app_state.get("active_view", "patient-pathways")
        show = {}
        hide = {"display": "none"}
        active_cls = "sidebar__item sidebar__item--active"
        inactive_cls = "sidebar__item"

        if view == "patient-pathways":
            return show, hide, active_cls, inactive_cls
        else:
            return hide, show, inactive_cls, active_cls
