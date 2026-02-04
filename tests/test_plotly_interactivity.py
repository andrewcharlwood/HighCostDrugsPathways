"""
Test Plotly interactivity features in the visualization module.

Verifies that Plotly charts have the expected interactive capabilities:
1. Hover templates are properly configured
2. Icicle chart settings allow click-to-drill-down navigation
3. Layout settings support proper display of interactive features

Phase 4.7.2: Verify Plotly interactivity (zoom, pan, hover)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import plotly.graph_objects as go

# Import the visualization module
try:
    from visualization.plotly_generator import create_icicle_figure, save_figure_html
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False


@pytest.fixture
def sample_chart_data():
    """
    Create sample chart data (ice_df) for testing visualization.

    This mimics the output of prepare_chart_data() from analysis/pathway_analyzer.py
    """
    # Sample hierarchy data: Root -> Trust -> Directory -> Drug
    data = {
        'parents': [
            '',           # Root (N&WICS)
            'N&WICS',     # Trust 1
            'N&WICS',     # Trust 2
            'Trust1',     # Directory in Trust1
            'Trust1',     # Another Directory
            'Trust2',     # Directory in Trust2
            'Trust1/Rheum', # Drug
            'Trust1/Derm',  # Drug
            'Trust2/Rheum', # Drug
        ],
        'ids': [
            'N&WICS',
            'Trust1',
            'Trust2',
            'Trust1/Rheum',
            'Trust1/Derm',
            'Trust2/Rheum',
            'Trust1/Rheum/Adalimumab',
            'Trust1/Derm/Adalimumab',
            'Trust2/Rheum/Etanercept',
        ],
        'labels': [
            'Norfolk & Waveney ICS',
            'Manchester University Trust',
            'Barts Health Trust',
            'Rheumatology',
            'Dermatology',
            'Rheumatology',
            'Adalimumab',
            'Adalimumab',
            'Etanercept',
        ],
        'value': [50, 30, 20, 20, 10, 20, 20, 10, 20],
        'colour': [1.0, 0.6, 0.4, 0.4, 0.2, 0.4, 0.4, 0.2, 0.4],
        'cost': [50000, 30000, 20000, 20000, 10000, 20000, 20000, 10000, 20000],
        'costpp': [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
        'cost_pp_pa': [2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000],
        'First seen': [
            pd.Timestamp('2023-01-01')] * 9,
        'Last seen': [
            pd.Timestamp('2023-12-31')] * 9,
        'First seen (Parent)': [
            pd.Timestamp('2023-01-01')] * 9,
        'Last seen (Parent)': [
            pd.Timestamp('2023-12-31')] * 9,
        'average_spacing': ['14 days'] * 9,
        'avg_days': [pd.Timedelta('180 days')] * 9,
    }
    return pd.DataFrame(data)


@pytest.mark.skipif(not HAS_VISUALIZATION, reason="Visualization module not available")
class TestPlotlyFigureConfiguration:
    """Test that Plotly figures have correct interactive configuration."""

    def test_figure_has_hovertemplate(self, sample_chart_data):
        """Verify the icicle chart has a hover template configured."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        # Get the icicle trace
        assert len(fig.data) > 0, "Figure should have at least one trace"

        icicle_trace = fig.data[0]
        assert icicle_trace.type == 'icicle', "First trace should be an icicle chart"

        # Verify hovertemplate is set and contains expected placeholders
        assert icicle_trace.hovertemplate is not None, "Hover template should be configured"
        assert '%{label}' in icicle_trace.hovertemplate, "Hover should include label"
        assert '%{customdata' in icicle_trace.hovertemplate, "Hover should include custom data"

    def test_figure_has_texttemplate(self, sample_chart_data):
        """Verify the icicle chart has a text template for in-chart text."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # Verify texttemplate is set
        assert icicle_trace.texttemplate is not None, "Text template should be configured"
        assert '%{label}' in icicle_trace.texttemplate, "Text should include label"

    def test_figure_has_correct_branchvalues(self, sample_chart_data):
        """Verify branchvalues is set to 'total' for proper hierarchy summing."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # branchvalues should be 'total' for proper hierarchy display
        assert icicle_trace.branchvalues == 'total', \
            "branchvalues should be 'total' for hierarchy summation"

    def test_figure_has_maxdepth_for_drilldown(self, sample_chart_data):
        """Verify maxdepth is set to allow drill-down navigation."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # maxdepth should be set to limit initial view depth
        # Users can then click to drill into deeper levels
        assert icicle_trace.maxdepth is not None, "maxdepth should be configured for drill-down"
        assert icicle_trace.maxdepth >= 2, "maxdepth should be at least 2 to show hierarchy"

    def test_figure_layout_has_hoverlabel(self, sample_chart_data):
        """Verify layout has hoverlabel configuration for readable tooltips."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        # Check hoverlabel configuration
        assert 'hoverlabel' in fig.layout, "Layout should have hoverlabel configuration"
        # Plotly uses 'font' as a dict with 'size' attribute
        assert fig.layout.hoverlabel.font is not None, "Hover label font should be configured"
        assert fig.layout.hoverlabel.font.size is not None, "Hover label font size should be set"
        assert fig.layout.hoverlabel.font.size >= 12, "Hover label should be readable (>=12px)"

    def test_figure_has_proper_margins(self, sample_chart_data):
        """Verify layout has margins configured for proper display."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        # Check margin configuration
        assert fig.layout.margin is not None, "Margins should be configured"
        assert fig.layout.margin.t >= 50, "Top margin should have room for title"

    def test_figure_has_title(self, sample_chart_data):
        """Verify the figure has a title configured."""
        fig = create_icicle_figure(sample_chart_data, "Test Analysis")

        assert fig.layout.title is not None, "Figure should have a title"
        assert "Test Analysis" in fig.layout.title.text, "Title should include custom text"

    def test_figure_has_colorscale(self, sample_chart_data):
        """Verify the icicle chart has a colorscale for visual differentiation."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # Check marker has colorscale
        assert icicle_trace.marker is not None, "Marker should be configured"
        assert icicle_trace.marker.colorscale is not None, "Colorscale should be set"


@pytest.mark.skipif(not HAS_VISUALIZATION, reason="Visualization module not available")
class TestPlotlyInteractiveFeatures:
    """Test that Plotly figures support expected interactive features."""

    def test_figure_is_interactive_type(self, sample_chart_data):
        """Verify the figure is a go.Figure which supports interactivity."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        assert isinstance(fig, go.Figure), "Should return a Plotly Figure object"

    def test_figure_can_be_converted_to_html(self, sample_chart_data, tmp_path):
        """Verify the figure can be saved as interactive HTML."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        # Save to temporary file
        html_path = save_figure_html(fig, str(tmp_path), "test_chart", open_browser=False)

        assert html_path.endswith('.html'), "Should save as HTML file"

        # Verify the HTML file exists and contains Plotly data
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        assert 'plotly' in html_content.lower(), "HTML should contain Plotly"
        # Interactive HTML should include the plotly.js library
        assert 'cdn.plot.ly' in html_content or 'plotly-' in html_content, \
            "HTML should include Plotly.js for interactivity"

    def test_figure_data_includes_ids_for_drilldown(self, sample_chart_data):
        """Verify figure data includes ids necessary for click-to-drill navigation."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # ids are required for proper drill-down behavior in icicle charts
        assert icicle_trace.ids is not None, "ids should be provided for drill-down"
        assert len(icicle_trace.ids) > 0, "ids should not be empty"

    def test_figure_data_includes_parents_for_hierarchy(self, sample_chart_data):
        """Verify figure data includes parents for hierarchy navigation."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # parents are required for hierarchy structure
        assert icicle_trace.parents is not None, "parents should be provided"
        assert len(icicle_trace.parents) > 0, "parents should not be empty"

    def test_figure_customdata_enables_rich_hover(self, sample_chart_data):
        """Verify customdata is provided for rich hover information."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        icicle_trace = fig.data[0]

        # customdata enables rich hover templates with additional info
        assert icicle_trace.customdata is not None, "customdata should be provided"

        # customdata should be a 2D array with multiple columns of data
        assert len(icicle_trace.customdata) > 0, "customdata should have rows"
        # Each row should have multiple data points for hover display
        if hasattr(icicle_trace.customdata[0], '__len__'):
            assert len(icicle_trace.customdata[0]) >= 5, \
                "customdata should have multiple columns for rich hover"


@pytest.mark.skipif(not HAS_VISUALIZATION, reason="Visualization module not available")
class TestReflexCompatibility:
    """Test that figures are compatible with Reflex's rx.plotly() component."""

    def test_figure_to_json_serializable(self, sample_chart_data):
        """Verify figure can be serialized to JSON (required for Reflex)."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        # Reflex needs to serialize the figure to JSON for the frontend
        try:
            json_data = fig.to_json()
            assert json_data is not None
            assert len(json_data) > 0
        except Exception as e:
            pytest.fail(f"Figure should be JSON serializable: {e}")

    def test_figure_to_dict(self, sample_chart_data):
        """Verify figure can be converted to dict (used by Reflex internally)."""
        fig = create_icicle_figure(sample_chart_data, "Test Title")

        # Reflex may use to_dict internally
        fig_dict = fig.to_dict()

        assert 'data' in fig_dict, "Figure dict should have data"
        assert 'layout' in fig_dict, "Figure dict should have layout"
        assert len(fig_dict['data']) > 0, "Data should not be empty"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
