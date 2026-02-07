"""Dash application entry point with layout root and state stores."""
from dash import Dash, html, dcc
import dash_mantine_components as dmc

from dash_app.components.header import make_header
from dash_app.components.sub_header import make_sub_header
from dash_app.components.sidebar import make_sidebar
from dash_app.components.filter_bar import make_filter_bar
from dash_app.components.chart_card import make_chart_card
from dash_app.components.footer import make_footer
from dash_app.components.modals import make_modals
from dash_app.components.trust_comparison import make_tc_landing, make_tc_dashboard

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
            "selected_trusts": [],
            "active_view": "patient-pathways",
            "selected_comparison_directorate": None,
            "selected_trends_directorate": None,
        }),
        dcc.Store(id="chart-data", storage_type="memory"),
        dcc.Store(id="reference-data", storage_type="session"),
        dcc.Store(id="active-tab", storage_type="memory", data="icicle"),
        dcc.Location(id="url", refresh=False),

        # Page structure
        make_header(),
        make_sub_header(),
        make_sidebar(),
        make_modals(),
        html.Main(
            className="main",
            children=[
                # View container — switched by active_view in app-state
                html.Div(
                    id="view-container",
                    children=[
                        # Patient Pathways view (default, visible)
                        html.Div(
                            id="patient-pathways-view",
                            children=[
                                make_filter_bar(),
                                make_chart_card(),
                            ],
                        ),
                        # Trust Comparison view (hidden initially)
                        html.Div(
                            id="trust-comparison-view",
                            style={"display": "none"},
                            children=[
                                make_tc_landing(),
                                make_tc_dashboard(),
                            ],
                        ),
                        # Trends view (hidden initially)
                        html.Div(
                            id="trends-view",
                            style={"display": "none"},
                            children=[
                                html.H3("Trends", style={"padding": "24px"}),
                            ],
                        ),
                    ],
                ),
                make_footer(),
            ],
        ),
    ],
)

from dash_app.callbacks import register_callbacks

register_callbacks(app)

server = app.server
