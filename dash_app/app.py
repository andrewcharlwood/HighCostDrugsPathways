"""Dash application entry point with layout root and state stores."""
from dash import Dash, html, dcc
import dash_mantine_components as dmc

from dash_app.components.header import make_header
from dash_app.components.sidebar import make_sidebar
from dash_app.components.kpi_row import make_kpi_row
from dash_app.components.filter_bar import make_filter_bar
from dash_app.components.chart_card import make_chart_card
from dash_app.components.footer import make_footer

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

        # Page structure
        make_header(),
        make_sidebar(),
        html.Main(
            className="main",
            children=[
                make_kpi_row(),
                make_filter_bar(),
                make_chart_card(),
                make_footer(),
            ],
        ),
    ],
)

server = app.server
