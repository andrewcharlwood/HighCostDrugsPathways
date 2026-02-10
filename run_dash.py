"""Entry point for the Dash application."""
import sys
from pathlib import Path

# Ensure project root is on sys.path so that core/, data_processing/, etc. are importable
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dash_app.app import app

if __name__ == "__main__":
    app.run(debug=True, port=8050)
