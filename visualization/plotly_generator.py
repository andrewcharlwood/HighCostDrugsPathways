"""
Plotly chart generation for patient pathway analysis.

This module contains functions for creating interactive icicle charts
that visualize patient treatment pathways. The charts display hierarchical
data: Trust → Directory → Drug → Pathway.
"""

import webbrowser
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core.logging_config import get_logger

logger = get_logger(__name__)


def create_icicle_figure(ice_df: pd.DataFrame, title: str) -> go.Figure:
    """
    Create Plotly icicle figure from prepared DataFrame.

    This function generates an interactive icicle chart showing patient pathway
    hierarchies with custom data including costs, dates, and treatment durations.

    Args:
        ice_df: DataFrame with columns:
            - parents: Parent node in hierarchy
            - ids: Unique identifier for each node
            - labels: Display label for each node
            - value: Number of patients
            - colour: Color value for visualization
            - cost: Total cost
            - costpp: Cost per patient
            - cost_pp_pa: Cost per patient per annum
            - First seen: First intervention date
            - Last seen: Last intervention date
            - First seen (Parent): Earliest date in parent group
            - Last seen (Parent): Latest date in parent group
            - average_spacing: Formatted string with dosing information
            - avg_days: Average treatment duration
        title: Chart title

    Returns:
        Plotly Figure object ready for display or export
    """
    ice_df = ice_df.copy()
    ice_df.sort_values(by=["labels"], ascending=True, inplace=True, ignore_index=True)

    first_seen = ice_df["First seen"].astype(str).replace("NaT", "N/A").to_list()
    last_seen = ice_df["Last seen"].astype(str).replace("NaT", "N/A").to_list()
    first_seen_parent = ice_df["First seen (Parent)"].astype(str).to_list()
    last_seen_parent = ice_df["Last seen (Parent)"].astype(str).to_list()
    average_spacing = ice_df.average_spacing.astype(str).to_list()

    fig = go.Figure(
        go.Icicle(
            labels=ice_df.labels,
            ids=ice_df.ids,
            parents=ice_df.parents,
            customdata=np.stack(
                (
                    ice_df.value,
                    ice_df.colour,
                    ice_df.cost,
                    ice_df.costpp,
                    first_seen,
                    last_seen,
                    first_seen_parent,
                    last_seen_parent,
                    average_spacing,
                    ice_df.cost_pp_pa,
                ),
                axis=1,
            ),
            values=ice_df.value,
            branchvalues="total",
            marker=dict(colors=ice_df.colour, colorscale="Viridis"),
            maxdepth=3,
            texttemplate="<b>%{label}</b> "
            "<br><b>Total patients:</b> %{customdata[0]} (including children/further treatments)"
            "<br><b>First seen:</b> %{customdata[4]}"
            "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
            "<br><b>Average treatment duration:</b> %{customdata[8]}"
            "<br><b>Total cost:</b> £%{customdata[2]:.3~s}"
            "<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}"
            "<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}",
            hovertemplate="<b>%{label}</b>"
            "<br><b>Total patients:</b> %{customdata[0]} - %{customdata[1]:.3p} of patients in level"
            "<br><b>Total cost:</b> £%{customdata[2]:.3~s}"
            "<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}"
            "<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}"
            "<br><b>First seen:</b> %{customdata[4]}"
            "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
            "<br><b>Average treatment duration:</b>"
            "%{customdata[8]}"
            "<extra></extra>",
        )
    )
    fig.update_traces(sort=False)
    fig.update_layout(
        margin=dict(t=60, l=1, r=1, b=60),
        title=f"Norfolk & Waveney ICS high-cost drug patient pathways - {title}",
        title_x=0.5,
        hoverlabel=dict(font_size=16),
    )

    return fig


def save_figure_html(
    fig: go.Figure, save_dir: str, title: str, open_browser: bool = False
) -> str:
    """
    Save Plotly figure to HTML file.

    Args:
        fig: Plotly Figure object
        save_dir: Directory to save the HTML file
        title: Title used for filename
        open_browser: If True, open the file in the default browser

    Returns:
        Path to the saved HTML file
    """
    filepath = f"{save_dir}/{title}.html"
    fig.write_html(filepath)
    logger.info(f"Success! File saved to {filepath}")

    if open_browser:
        open_figure_in_browser(filepath)

    return filepath


def open_figure_in_browser(filepath: str) -> None:
    """
    Open an HTML file in the default browser.

    Args:
        filepath: Path to the HTML file
    """
    webbrowser.open_new_tab("file:///" + filepath)


def figure_legacy(ice_df: pd.DataFrame, dir_string: str, save_dir: str) -> None:
    """
    Create and display icicle figure (legacy interface).

    This function maintains backward compatibility with the original figure()
    function signature. It creates the figure, saves it to HTML, and opens
    it in the browser.

    Args:
        ice_df: DataFrame with chart data
        dir_string: Title string (used for filename and chart title)
        save_dir: Directory to save the HTML file

    Note:
        This function is provided for backward compatibility.
        New code should use create_icicle_figure() + save_figure_html() instead.
    """
    # Handle avg_days column for display
    ice_df = ice_df.copy()
    ice_df.sort_values(by=["labels"], ascending=True, inplace=True, ignore_index=True)

    first_seen = ice_df["First seen"].astype(str).replace("NaT", "N/A").to_list()
    last_seen = ice_df["Last seen"].astype(str).replace("NaT", "N/A").to_list()
    first_seen_parent = ice_df["First seen (Parent)"].astype(str).to_list()
    last_seen_parent = ice_df["Last seen (Parent)"].astype(str).to_list()
    average_spacing = ice_df.average_spacing.astype(str).to_list()
    avg_seen = ice_df["avg_days"].dt.round("D").astype(str).replace("0 days", "N/A").to_list()

    fig = go.Figure(
        go.Icicle(
            labels=ice_df.labels,
            ids=ice_df.ids,
            parents=ice_df.parents,
            customdata=np.stack(
                (
                    ice_df.value,
                    ice_df.colour,
                    ice_df.cost,
                    ice_df.costpp,
                    first_seen,
                    last_seen,
                    first_seen_parent,
                    last_seen_parent,
                    average_spacing,
                    ice_df.cost_pp_pa,
                ),
                axis=1,
            ),
            values=ice_df.value,
            branchvalues="total",
            marker=dict(colors=ice_df.colour, colorscale="Viridis"),
            maxdepth=3,
            texttemplate="<b>%{label}</b> "
            "<br><b>Total patients:</b> %{customdata[0]} (including children/further treatments)"
            "<br><b>First seen:</b> %{customdata[4]}"
            "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
            "<br><b>Average treatment duration:</b> %{customdata[8]}"
            "<br><b>Total cost:</b> £%{customdata[2]:.3~s}"
            "<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}"
            "<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}",
            hovertemplate="<b>%{label}</b>"
            "<br><b>Total patients:</b> %{customdata[0]} - %{customdata[1]:.3p} of patients in level"
            "<br><b>Total cost:</b> £%{customdata[2]:.3~s}"
            "<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}"
            "<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}"
            "<br><b>First seen:</b> %{customdata[4]}"
            "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
            "<br><b>Average treatment duration:</b>"
            "%{customdata[8]}"
            "<extra></extra>",
        )
    )
    fig.update_traces(sort=False)
    fig.update_layout(
        margin=dict(t=60, l=1, r=1, b=60),
        title=f"Norfolk & Waveney ICS high-cost drug patient pathways - {dir_string}",
        title_x=0.5,
        hoverlabel=dict(font_size=16),
    )

    filepath = f"{save_dir}/{dir_string}.html"
    fig.write_html(filepath)
    logger.info(f"Success! File saved to {filepath}")
    webbrowser.open_new_tab("file:///" + filepath)
