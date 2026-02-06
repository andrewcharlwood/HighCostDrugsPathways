"""Entry point for the Dash application."""
from dash_app.app import app

if __name__ == "__main__":
    app.run(debug=True, port=8050)
