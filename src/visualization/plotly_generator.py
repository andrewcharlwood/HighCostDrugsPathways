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


def create_icicle_from_nodes(nodes: list[dict], title: str = "") -> go.Figure:
    """
    Create Plotly icicle figure from a list of pathway node dicts.

    This is the dict-based entry point used by the Dash app. The nodes list
    comes directly from the chart-data dcc.Store (JSON-serialized dicts with
    underscore keys matching SQLite column names).

    Args:
        nodes: List of dicts with keys: parents, ids, labels, value, cost,
               costpp, cost_pp_pa, colour, first_seen, last_seen,
               first_seen_parent, last_seen_parent, average_spacing
        title: Chart title (e.g. "By Directory | All years / Last 6 months")

    Returns:
        Plotly Figure object ready for dcc.Graph
    """
    if not nodes:
        return go.Figure()

    parents = [d.get("parents", "") for d in nodes]
    ids = [d.get("ids", "") for d in nodes]
    labels = [d.get("labels", "") for d in nodes]
    values = [d.get("value", 0) for d in nodes]
    colours = [d.get("colour", 0.0) for d in nodes]

    costs = [d.get("cost", 0.0) for d in nodes]
    costpp = [d.get("costpp", 0.0) for d in nodes]
    first_seen = [d.get("first_seen", "N/A") or "N/A" for d in nodes]
    last_seen = [d.get("last_seen", "N/A") or "N/A" for d in nodes]
    first_seen_parent = [d.get("first_seen_parent", "N/A") or "N/A" for d in nodes]
    last_seen_parent = [d.get("last_seen_parent", "N/A") or "N/A" for d in nodes]
    average_spacing = [d.get("average_spacing", "") or "" for d in nodes]
    cost_pp_pa = [d.get("cost_pp_pa", 0.0) or 0.0 for d in nodes]

    customdata = list(zip(
        values,              # [0]
        colours,             # [1]
        costs,               # [2]
        costpp,              # [3]
        first_seen,          # [4]
        last_seen,           # [5]
        first_seen_parent,   # [6]
        last_seen_parent,    # [7]
        average_spacing,     # [8]
        cost_pp_pa,          # [9]
    ))

    # NHS blue gradient (Heritage Blue → Primary Blue → Vibrant Blue → Sky Blue → Pale Blue)
    colorscale = [
        [0.0, "#003087"],
        [0.25, "#0066CC"],
        [0.5, "#1E88E5"],
        [0.75, "#4FC3F7"],
        [1.0, "#E3F2FD"],
    ]

    fig = go.Figure(
        go.Icicle(
            labels=labels,
            ids=ids,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(
                colors=colours,
                colorscale=colorscale,
                line=dict(width=1, color="#FFFFFF"),
            ),
            maxdepth=3,
            customdata=customdata,
            texttemplate=(
                "<b>%{label}</b> "
                "<br><b>Total patients:</b> %{customdata[0]} (including children/further treatments)"
                "<br><b>First seen:</b> %{customdata[4]}"
                "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
                "<br><b>Average treatment duration:</b> %{customdata[8]}"
                "<br><b>Total cost:</b> \u00a3%{customdata[2]:.3~s}"
                "<br><b>Average cost per patient:</b> \u00a3%{customdata[3]:.3~s}"
                "<br><b>Average cost per patient per annum:</b> \u00a3%{customdata[9]:.3~s}"
            ),
            hovertemplate=(
                "<b>%{label}</b>"
                "<br><b>Total patients:</b> %{customdata[0]} - %{customdata[1]:.3p} of patients in level"
                "<br><b>Total cost:</b> \u00a3%{customdata[2]:.3~s}"
                "<br><b>Average cost per patient:</b> \u00a3%{customdata[3]:.3~s}"
                "<br><b>Average cost per patient per annum:</b> \u00a3%{customdata[9]:.3~s}"
                "<br><b>First seen:</b> %{customdata[4]}"
                "<br><b>Last seen (including further treatments):</b> %{customdata[7]}"
                "<br><b>Average treatment duration:</b>"
                "%{customdata[8]}"
                "<extra></extra>"
            ),
            textfont=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=12,
            ),
        )
    )

    display_title = f"Patient Pathways \u2014 {title}" if title else "Patient Pathways"

    fig.update_layout(
        title=dict(
            text=display_title,
            font=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=18,
                color="#1E293B",
            ),
            x=0.5,
            xanchor="center",
        ),
        margin=dict(t=40, l=8, r=8, b=24),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=14,
                color="#1E293B",
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        clickmode="event+select",
    )

    fig.update_traces(sort=False)

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
