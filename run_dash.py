"""Entry point for the Dash application."""
import sys
from pathlib import Path

# Ensure src/ is on sys.path so that core/, data_processing/, etc. are importable
_src_dir = str(Path(__file__).resolve().parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from dash_app.app import app

if __name__ == "__main__":
    app.run(debug=True, port=8050)
