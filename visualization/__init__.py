"""
Visualization package for patient pathway charts.

This package contains functions for generating interactive Plotly visualizations:
- plotly_generator: Create icicle charts for patient pathway analysis
"""

from visualization.plotly_generator import (
    create_icicle_figure,
    save_figure_html,
    open_figure_in_browser,
)

__all__ = [
    "create_icicle_figure",
    "save_figure_html",
    "open_figure_in_browser",
]
