"""Resolve file paths for both development and PyInstaller frozen modes."""

import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """Return absolute path to a bundled resource.

    In frozen mode (PyInstaller), resolves from sys._MEIPASS.
    In dev mode, resolves from the project root (2 parents up from this file:
    core/resource_path.py → core → project root).
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[1]
    return base / relative_path
