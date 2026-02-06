"""Dash application entry point with layout root and state stores."""
from dash import Dash, html, dcc
import dash_mantine_components as dmc

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
)

app.layout = dmc.MantineProvider(
    children=[
        # State stores
        dcc.Store(id="app-state", storage_type="session", data={
            "chart_type": "directory",
            "initiated": "all",
            "last_seen": "6mo",
            "date_filter_id": "all_6mo",
            "selected_drugs": [],
            "selected_directorates": [],
        }),
        dcc.Store(id="chart-data", storage_type="memory"),
        dcc.Store(id="reference-data", storage_type="session"),

        # Placeholder layout — will be replaced by assembled components
        html.Div(
            className="main",
            style={"marginLeft": "0", "marginTop": "0"},
            children=[
                html.H1("HCD Analysis", style={"color": "#003087"}),
                html.P("Dash application scaffolding complete. Components will be added in subsequent phases."),
            ],
        ),
    ],
)

server = app.server
