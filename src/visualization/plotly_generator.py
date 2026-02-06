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


def create_market_share_figure(data: list[dict], title: str = "") -> go.Figure:
    """
    Create horizontal grouped bar chart showing first-line drug market share by directorate.

    Args:
        data: List of dicts from get_drug_market_share() with keys:
              directory, drug, patients, proportion, cost, cost_pp_pa
              Sorted by directory total patients desc, drugs desc within.
        title: Chart title suffix (filter description)

    Returns:
        Plotly Figure with horizontal bars grouped by directorate.
    """
    if not data:
        return go.Figure()

    # NHS blue palette for different drugs
    nhs_colours = [
        "#003087", "#005EB8", "#0072CE", "#1E88E5", "#41B6E6",
        "#4FC3F7", "#768692", "#AE2573", "#006747", "#ED8B00",
        "#8A1538", "#330072", "#009639", "#DA291C", "#00A499",
    ]

    # Collect unique directorates (in order — already sorted by total patients desc)
    seen_dirs = []
    for d in data:
        if d["directory"] not in seen_dirs:
            seen_dirs.append(d["directory"])

    # Collect unique drugs across all directorates (preserve first-encountered order)
    seen_drugs = []
    for d in data:
        if d["drug"] not in seen_drugs:
            seen_drugs.append(d["drug"])

    # Build one trace per drug
    drug_colour_map = {drug: nhs_colours[i % len(nhs_colours)] for i, drug in enumerate(seen_drugs)}

    # Build a lookup: (directory, drug) -> row
    lookup = {(d["directory"], d["drug"]): d for d in data}

    # Reverse directory order so highest total is at the top of horizontal chart
    display_dirs = list(reversed(seen_dirs))

    traces = []
    for drug in seen_drugs:
        y_vals = []
        x_vals = []
        hover_texts = []
        for directory in display_dirs:
            row = lookup.get((directory, drug))
            if row:
                y_vals.append(directory)
                x_vals.append(row["proportion"] * 100)
                hover_texts.append(
                    f"<b>{drug}</b><br>"
                    f"{directory}<br>"
                    f"Patients: {row['patients']:,}<br>"
                    f"Share: {row['proportion']:.1%}<br>"
                    f"Cost: £{row['cost']:,.0f}<br>"
                    f"Cost p.p.p.a: £{row['cost_pp_pa']:,.0f}"
                )
            else:
                y_vals.append(directory)
                x_vals.append(0)
                hover_texts.append("")

        traces.append(go.Bar(
            name=drug,
            y=y_vals,
            x=x_vals,
            orientation="h",
            marker_color=drug_colour_map[drug],
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        ))

    display_title = f"First-Line Drug Market Share — {title}" if title else "First-Line Drug Market Share"

    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="stack",
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
        xaxis=dict(
            title="% of patients",
            ticksuffix="%",
            range=[0, 105],
            gridcolor="#E2E8F0",
            zeroline=False,
        ),
        yaxis=dict(
            title="",
            automargin=True,
        ),
        legend=dict(
            title="Drug",
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=11,
            ),
        ),
        margin=dict(t=50, l=8, r=24, b=100),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=13,
                color="#1E293B",
            ),
        ),
        font=dict(
            family="Source Sans 3, system-ui, sans-serif",
        ),
        height=max(400, len(seen_dirs) * 60 + 200),
    )

    return fig


def create_cost_effectiveness_figure(
    data: list[dict],
    retention: dict,
    title: str = "",
) -> go.Figure:
    """
    Create horizontal lollipop chart showing pathway cost per patient per annum.

    Args:
        data: List of dicts from get_pathway_costs() with keys:
              ids, pathway_label, cost_pp_pa, patients, cost, avg_days,
              directory, trust_name, drug_sequence, level.
              Sorted by cost_pp_pa desc.
        retention: Dict from calculate_retention_rate() mapping ids to retention
                   info: {retained_patients, total_patients, retention_rate, drug_sequence}.
        title: Chart title suffix (filter description).

    Returns:
        Plotly Figure with horizontal lollipop dots and retention annotations.
    """
    if not data:
        return go.Figure()

    # Filter to pathways with positive cost
    filtered = [d for d in data if d["cost_pp_pa"] > 0]
    if not filtered:
        return go.Figure()

    # Cap to top 40 pathways by cost to keep chart readable
    filtered = filtered[:40]

    # Reverse for horizontal chart (highest cost at top)
    filtered = list(reversed(filtered))

    pathway_labels = [d["pathway_label"] for d in filtered]
    costs = [d["cost_pp_pa"] for d in filtered]
    patients = [d["patients"] for d in filtered]

    # Colour gradient: green (cheap) → amber → red (expensive)
    max_cost = max(costs) if costs else 1
    min_cost = min(costs) if costs else 0
    cost_range = max_cost - min_cost if max_cost != min_cost else 1

    colours = []
    for c in costs:
        ratio = (c - min_cost) / cost_range
        if ratio < 0.33:
            colours.append("#009639")  # NHS green
        elif ratio < 0.66:
            colours.append("#ED8B00")  # NHS warm yellow
        else:
            colours.append("#DA291C")  # NHS red

    # Dot size scaled by patient count (min 8, max 30)
    max_pts = max(patients) if patients else 1
    min_pts = min(patients) if patients else 1
    pts_range = max_pts - min_pts if max_pts != min_pts else 1
    sizes = [8 + (p - min_pts) / pts_range * 22 for p in patients]

    # Build hover text with retention info
    hover_texts = []
    for d in filtered:
        retention_info = retention.get(d["ids"], {})
        retention_rate = retention_info.get("retention_rate")
        drugs_in_seq = len(d["drug_sequence"])

        hover = (
            f"<b>{d['pathway_label']}</b><br>"
            f"Cost p.p.p.a.: £{d['cost_pp_pa']:,.0f}<br>"
            f"Patients: {d['patients']:,}<br>"
            f"Total cost: £{d['cost']:,.0f}<br>"
            f"Avg duration: {d['avg_days']:,.0f} days<br>"
            f"Directorate: {d['directory']}<br>"
            f"Treatment lines: {drugs_in_seq}"
        )
        if retention_rate is not None:
            hover += f"<br>Retention: {retention_rate:.0f}% (no further switch)"
        hover_texts.append(hover)

    # Lollipop sticks (horizontal lines from 0 to cost)
    stick_traces = []
    for i, (label, cost) in enumerate(zip(pathway_labels, costs)):
        stick_traces.append(
            go.Scatter(
                x=[0, cost],
                y=[label, label],
                mode="lines",
                line=dict(color="#CBD5E1", width=1.5),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Lollipop dots
    dot_trace = go.Scatter(
        x=costs,
        y=pathway_labels,
        mode="markers",
        marker=dict(
            size=sizes,
            color=colours,
            line=dict(color="#FFFFFF", width=1),
        ),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        showlegend=False,
    )

    display_title = (
        f"Pathway Cost Effectiveness — {title}" if title
        else "Pathway Cost Effectiveness (£ per patient per annum)"
    )

    fig = go.Figure(data=stick_traces + [dot_trace])

    # Add retention annotations for pathways with notable retention
    annotation_count = 0
    for d in filtered:
        ret = retention.get(d["ids"], {})
        rate = ret.get("retention_rate")
        if rate is not None and rate < 90 and d["patients"] >= 10 and annotation_count < 8:
            fig.add_annotation(
                x=d["cost_pp_pa"],
                y=d["pathway_label"],
                text=f"{rate:.0f}% retain",
                showarrow=False,
                xanchor="left",
                xshift=10,
                font=dict(size=10, color="#768692", family="Source Sans 3"),
            )
            annotation_count += 1

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
        xaxis=dict(
            title="£ per patient per annum",
            tickprefix="£",
            tickformat=",",
            gridcolor="#E2E8F0",
            zeroline=True,
            zerolinecolor="#CBD5E1",
        ),
        yaxis=dict(
            title="",
            automargin=True,
            tickfont=dict(size=11),
        ),
        margin=dict(t=50, l=8, r=24, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=13,
                color="#1E293B",
            ),
        ),
        font=dict(
            family="Source Sans 3, system-ui, sans-serif",
        ),
        height=max(450, len(filtered) * 28 + 150),
    )

    return fig


def create_cost_waterfall_figure(
    data: list[dict],
    title: str = "",
) -> go.Figure:
    """Create waterfall chart showing cost per patient by directorate/indication.

    Args:
        data: List of dicts from get_cost_waterfall() with keys:
              directory, patients, total_cost, cost_pp.
              Sorted by cost_pp desc.
        title: Chart title suffix (filter description).

    Returns:
        Plotly Figure with waterfall bars and total.
    """
    if not data:
        return go.Figure()

    labels = [d["directory"] for d in data]
    cost_pp_values = [d["cost_pp"] for d in data]
    patients_list = [d["patients"] for d in data]
    total_costs = [d["total_cost"] for d in data]

    # NHS colour palette for bars
    nhs_colours = [
        "#005EB8", "#003087", "#41B6E6", "#0066CC", "#1E88E5",
        "#4FC3F7", "#009639", "#ED8B00", "#768692", "#425563",
        "#DA291C", "#7C2855",
    ]

    # Assign colours cycling through palette
    bar_colours = [nhs_colours[i % len(nhs_colours)] for i in range(len(data))]

    hover_texts = []
    for d in data:
        hover_texts.append(
            f"<b>{d['directory']}</b><br>"
            f"Cost per patient: £{d['cost_pp']:,.0f}<br>"
            f"Patients: {d['patients']:,}<br>"
            f"Total cost: £{d['total_cost']:,.0f}"
        )

    # Use a standard bar chart (not go.Waterfall) for cleaner control
    # Each bar shows cost_pp for a directorate, sorted highest to lowest
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=labels,
            y=cost_pp_values,
            marker=dict(
                color=bar_colours,
                line=dict(color="#FFFFFF", width=1),
            ),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            text=[f"£{v:,.0f}" for v in cost_pp_values],
            textposition="outside",
            textfont=dict(size=11, color="#425563"),
        )
    )

    # Add patient count annotations below each bar
    for i, (label, pts) in enumerate(zip(labels, patients_list)):
        fig.add_annotation(
            x=label,
            y=0,
            text=f"n={pts:,}",
            showarrow=False,
            yshift=-18,
            font=dict(size=10, color="#768692", family="Source Sans 3"),
        )

    # Grand total line
    if cost_pp_values:
        total_patients = sum(patients_list)
        total_cost = sum(total_costs)
        weighted_avg = total_cost / total_patients if total_patients else 0
        fig.add_hline(
            y=weighted_avg,
            line_dash="dash",
            line_color="#DA291C",
            line_width=1.5,
            annotation_text=f"Weighted avg: £{weighted_avg:,.0f}",
            annotation_position="top right",
            annotation_font=dict(
                size=11, color="#DA291C", family="Source Sans 3"
            ),
        )

    display_title = (
        f"Cost per Patient by Directorate — {title}" if title
        else "Cost per Patient by Directorate"
    )

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
        xaxis=dict(
            title="",
            tickangle=-45 if len(data) > 6 else 0,
            tickfont=dict(size=11),
            automargin=True,
        ),
        yaxis=dict(
            title="£ per patient",
            tickprefix="£",
            tickformat=",",
            gridcolor="#E2E8F0",
            zeroline=True,
            zerolinecolor="#CBD5E1",
        ),
        margin=dict(t=60, l=8, r=24, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(
                family="Source Sans 3, system-ui, sans-serif",
                size=13,
                color="#1E293B",
            ),
        ),
        font=dict(
            family="Source Sans 3, system-ui, sans-serif",
        ),
        height=max(450, 500),
        bargap=0.25,
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
