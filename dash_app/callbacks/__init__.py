"""Callback registration — imports all callback modules and wires them to the app."""


def register_callbacks(app):
    """Register all Dash callbacks with the app instance."""
    from dash_app.callbacks.filters import register_filter_callbacks

    register_filter_callbacks(app)
