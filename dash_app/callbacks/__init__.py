"""Callback registration — imports all callback modules and wires them to the app."""


def register_callbacks(app):
    """Register all Dash callbacks with the app instance."""
    from dash_app.callbacks.filters import register_filter_callbacks
    from dash_app.callbacks.chart import register_chart_callbacks
    from dash_app.callbacks.kpi import register_kpi_callbacks
    from dash_app.callbacks.drawer import register_drawer_callbacks

    register_filter_callbacks(app)
    register_chart_callbacks(app)
    register_kpi_callbacks(app)
    register_drawer_callbacks(app)
