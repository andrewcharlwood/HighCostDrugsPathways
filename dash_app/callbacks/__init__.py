"""Callback registration — imports all callback modules and wires them to the app."""


def register_callbacks(app):
    """Register all Dash callbacks with the app instance."""
    from dash_app.callbacks.filters import register_filter_callbacks
    from dash_app.callbacks.chart import register_chart_callbacks
    from dash_app.callbacks.kpi import register_kpi_callbacks
    from dash_app.callbacks.modals import register_modal_callbacks
    from dash_app.callbacks.navigation import register_navigation_callbacks
    from dash_app.callbacks.trust_comparison import register_trust_comparison_callbacks

    register_filter_callbacks(app)
    register_chart_callbacks(app)
    register_kpi_callbacks(app)
    register_modal_callbacks(app)
    register_navigation_callbacks(app)
    register_trust_comparison_callbacks(app)
