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

# ---------------------------------------------------------------------------
# Shared styling constants
# ---------------------------------------------------------------------------

CHART_FONT_FAMILY = "Source Sans 3, system-ui, sans-serif"
CHART_TITLE_SIZE = 18
CHART_TITLE_COLOR = "#1E293B"
GRID_COLOR = "#E2E8F0"
ANNOTATION_COLOR = "#768692"

# 7 maximally-distinct colours for trust-comparison charts
TRUST_PALETTE = [
    "#005EB8",  # NHS Blue
    "#DA291C",  # Red
    "#009639",  # Green
    "#ED8B00",  # Orange
    "#7C2855",  # Plum
    "#00A499",  # Teal
    "#330072",  # Purple
]

# 15 distinct colours for drug-level charts
DRUG_PALETTE = [
    "#005EB8", "#DA291C", "#009639", "#ED8B00", "#7C2855",
    "#00A499", "#330072", "#E06666", "#6FA8DC", "#93C47D",
    "#F6B26B", "#8E7CC3", "#C27BA0", "#76A5AF", "#FFD966",
]


def _smart_legend(n_items: int, legend_title: str = "") -> dict:
    """Return a legend dict that adapts to the number of items.

    - >15 items: vertical legend to the right of the chart
    - ≤15 items: horizontal legend below the chart with dynamic bottom margin

    Returns a dict suitable for ``legend=...`` inside ``fig.update_layout()``.
    The caller should also set bottom margin accordingly — use
    ``_smart_legend_margin_b(n_items)`` for that.
    """
    base = dict(
        font=dict(family=CHART_FONT_FAMILY, size=11),
    )
    if legend_title:
        base["title"] = legend_title

    if n_items > 15:
        base.update(
            orientation="v",
            x=1.02,
            y=1,
            xanchor="left",
            yanchor="top",
        )
    else:
        base.update(
            orientation="h",
            yanchor="top",
            y=-0.12,
            xanchor="center",
            x=0.5,
        )
    return base


def _smart_legend_margin(n_items: int) -> dict:
    """Return margin dict with bottom margin adapted to legend size.

    - >15 items: vertical right legend needs extra right margin (r=140)
      but minimal bottom margin (b=40).
    - ≤15 items: horizontal legend needs bottom margin scaled to
      estimated row count (~6 items per row at font size 11).
    """
    if n_items > 15:
        return dict(r=140, b=40)
    else:
        rows = max(1, (n_items + 5) // 6)  # ~6 items per row
        return dict(b=max(60, rows * 28 + 30), r=24)


def _base_layout(title: str, **overrides) -> dict:
    """Return a dict of shared Plotly layout properties.

    All chart functions should call this to get consistent styling, then
    update the result with chart-specific overrides.

    Args:
        title: Display title for the chart.
        **overrides: Any key accepted by ``fig.update_layout()``; these are
            merged on top of the base dict so callers can override margins,
            height, etc.

    Returns:
        Dict ready to be unpacked into ``fig.update_layout(**layout)``.
    """
    layout = dict(
        title=dict(
            text=title,
            font=dict(
                family=CHART_FONT_FAMILY,
                size=CHART_TITLE_SIZE,
                color=CHART_TITLE_COLOR,
            ),
            x=0.5,
            xanchor="center",
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(
                family=CHART_FONT_FAMILY,
                size=13,
                color=CHART_TITLE_COLOR,
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        font=dict(family=CHART_FONT_FAMILY),
    )
    layout.update(overrides)
    return layout


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
                family=CHART_FONT_FAMILY,
                size=12,
            ),
        )
    )

    display_title = f"Patient Pathways \u2014 {title}" if title else "Patient Pathways"

    layout = _base_layout(
        display_title,
        margin=dict(t=40, l=8, r=8, b=24),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            bordercolor="#CBD5E1",
            font=dict(
                family=CHART_FONT_FAMILY,
                size=14,
                color=CHART_TITLE_COLOR,
            ),
        ),
        clickmode="event+select",
    )
    fig.update_layout(**layout)

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
    drug_colour_map = {drug: DRUG_PALETTE[i % len(DRUG_PALETTE)] for i, drug in enumerate(seen_drugs)}

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

    n_drugs = len(seen_drugs)
    legend_margins = _smart_legend_margin(n_drugs)

    fig = go.Figure(data=traces)
    layout = _base_layout(display_title)
    layout.update(
        barmode="stack",
        xaxis=dict(
            title="% of patients",
            ticksuffix="%",
            range=[0, 105],
            gridcolor=GRID_COLOR,
            zeroline=False,
        ),
        yaxis=dict(title="", automargin=True),
        legend=_smart_legend(n_drugs, legend_title="Drug"),
        margin=dict(t=50, l=8, **legend_margins),
        height=max(400, len(seen_dirs) * 60 + 200),
    )
    fig.update_layout(**layout)

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

    def _lerp_color(ratio: float) -> str:
        """Smooth green→amber→red gradient via linear RGB interpolation."""
        green = (0x00, 0x96, 0x39)
        amber = (0xED, 0x8B, 0x00)
        red = (0xDA, 0x29, 0x1C)
        ratio = max(0.0, min(1.0, ratio))
        if ratio <= 0.5:
            t = ratio / 0.5
            c1, c2 = green, amber
        else:
            t = (ratio - 0.5) / 0.5
            c1, c2 = amber, red
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        return f"rgb({r},{g},{b})"

    colours = [_lerp_color((c - min_cost) / cost_range) for c in costs]

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
                font=dict(size=10, color=ANNOTATION_COLOR, family=CHART_FONT_FAMILY),
            )
            annotation_count += 1

    layout = _base_layout(display_title)
    layout.update(
        xaxis=dict(
            title="£ per patient per annum",
            tickprefix="£",
            tickformat=",",
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor="#CBD5E1",
        ),
        yaxis=dict(
            title="",
            automargin=True,
            tickfont=dict(size=11),
        ),
        margin=dict(t=50, l=8, r=24, b=40),
        height=max(450, len(filtered) * 28 + 150),
    )
    fig.update_layout(**layout)

    return fig


def create_cost_waterfall_figure(
    data: list[dict],
    title: str = "",
    is_trust_comparison: bool = False,
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

    palette = TRUST_PALETTE if is_trust_comparison else DRUG_PALETTE
    bar_colours = [palette[i % len(palette)] for i in range(len(data))]

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
            font=dict(size=10, color=ANNOTATION_COLOR, family=CHART_FONT_FAMILY),
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
                size=11, color="#DA291C", family=CHART_FONT_FAMILY
            ),
        )

    display_title = (
        f"Cost per Patient by Directorate — {title}" if title
        else "Cost per Patient by Directorate"
    )

    layout = _base_layout(display_title)
    layout.update(
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
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor="#CBD5E1",
        ),
        margin=dict(t=60, l=8, r=24, b=40),
        showlegend=False,
        bargap=0.25,
    )
    fig.update_layout(**layout)

    return fig


def create_sankey_figure(
    data: dict,
    title: str = "",
) -> go.Figure:
    """Create Sankey diagram showing drug switching flows between treatment lines.

    Args:
        data: Dict from get_drug_transitions() with keys:
              nodes: [{name}] — drug names with ordinal suffixes (e.g., "ADALIMUMAB (1st)")
              links: [{source_idx, target_idx, patients}] — transitions between drugs
        title: Chart title suffix (filter description).

    Returns:
        Plotly Figure with Sankey diagram.
    """
    import re

    nodes = data.get("nodes", [])
    links = data.get("links", [])

    if not nodes or not links:
        return go.Figure()

    # Extract base drug name (strip ordinal suffix) for colour consistency
    def base_drug(name: str) -> str:
        return re.sub(r"\s*\(\d+(?:st|nd|rd|th)\)\s*$", "", name)

    unique_bases = []
    for n in nodes:
        b = base_drug(n["name"])
        if b not in unique_bases:
            unique_bases.append(b)
    base_colour_map = {b: DRUG_PALETTE[i % len(DRUG_PALETTE)] for i, b in enumerate(unique_bases)}

    # Node colours — same drug gets same colour regardless of treatment line
    node_colours = [base_colour_map[base_drug(n["name"])] for n in nodes]

    # Node labels — format nicely
    node_labels = [n["name"] for n in nodes]

    # Link colours — use source node colour at 40% opacity for visual clarity
    def hex_to_rgba(hex_colour: str, alpha: float) -> str:
        h = hex_colour.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    link_colours = [
        hex_to_rgba(node_colours[link["source_idx"]], 0.35)
        for link in links
    ]

    # Build hover text for links
    link_hovers = [
        f"{node_labels[link['source_idx']]} → {node_labels[link['target_idx']]}"
        f"<br>Patients: {link['patients']:,}"
        for link in links
    ]

    # Compute total patients per node for node hover
    node_patients = [0] * len(nodes)
    for link in links:
        node_patients[link["source_idx"]] += link["patients"]
    # For terminal nodes (no outgoing), use incoming total
    node_incoming = [0] * len(nodes)
    for link in links:
        node_incoming[link["target_idx"]] += link["patients"]
    node_hover = []
    for i, n in enumerate(nodes):
        out_p = node_patients[i]
        in_p = node_incoming[i]
        total = max(out_p, in_p)
        node_hover.append(f"<b>{n['name']}</b><br>Patients: {total:,}")

    fig = go.Figure(
        go.Sankey(
            arrangement="freeform",
            node=dict(
                pad=25,
                thickness=25,
                line=dict(color="#FFFFFF", width=1),
                label=node_labels,
                color=node_colours,
                customdata=node_hover,
                hovertemplate="%{customdata}<extra></extra>",
            ),
            link=dict(
                source=[link["source_idx"] for link in links],
                target=[link["target_idx"] for link in links],
                value=[link["patients"] for link in links],
                color=link_colours,
                customdata=link_hovers,
                hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )

    chart_title = "Drug Switching Flows"
    if title:
        chart_title = f"{chart_title} — {title}"

    layout = _base_layout(chart_title)
    layout.update(
        font=dict(family=CHART_FONT_FAMILY, size=12),
        margin=dict(t=60, l=30, r=30, b=30),
        height=max(500, len(unique_bases) * 35 + 200),
    )
    fig.update_layout(**layout)

    return fig


def create_dosing_figure(
    data: list[dict],
    title: str = "",
    group_by: str = "drug",
) -> go.Figure:
    """Create dosing interval comparison chart.

    Shows weekly dosing intervals as horizontal bars, grouped either by drug
    (overview mode) or by trust (single-drug comparison mode).

    Args:
        data: List of dicts from get_dosing_intervals() with keys:
              drug, trust_name, directory, weekly_interval, dose_count,
              total_weeks, patients.
        title: Chart title suffix (filter description).
        group_by: "drug" for drug-level overview (default),
                  "trust" for per-trust comparison of a single drug.

    Returns:
        Plotly Figure with horizontal grouped bar chart.
    """
    if not data:
        return go.Figure()

    if group_by == "trust":
        fig = _dosing_by_trust(data, DRUG_PALETTE)
        chart_title = "Dosing Intervals by Trust"
    else:
        fig = _dosing_by_drug(data, DRUG_PALETTE)
        chart_title = "Dosing Interval Overview"

    if title:
        chart_title = f"{chart_title} — {title}"

    n_rows = len(fig.data[0].y) if fig.data else 10
    n_legend = sum(1 for t in fig.data if t.showlegend is not False)
    legend_margins = _smart_legend_margin(n_legend)

    layout = _base_layout(chart_title)
    layout.update(
        xaxis=dict(
            title="Weekly Interval (weeks between doses)",
            titlefont=dict(size=13, color="#425563"),
            gridcolor="rgba(66,85,99,0.1)",
            zeroline=True,
            zerolinecolor="rgba(66,85,99,0.2)",
        ),
        yaxis=dict(automargin=True, tickfont=dict(size=11)),
        margin=dict(t=60, l=20, **legend_margins),
        height=max(450, n_rows * 40 + 150),
        bargap=0.15,
        bargroupgap=0.05,
        showlegend=True,
        legend=_smart_legend(n_legend),
    )
    fig.update_layout(**layout)

    return fig


def _dosing_by_drug(data: list[dict], colours: list[str]) -> go.Figure:
    """Build dosing overview: one row per drug, bars per trust, showing weekly_interval."""
    # Aggregate: weighted average interval per drug, summing patients
    drug_agg = {}
    for d in data:
        drug = d["drug"]
        pts = d["patients"] or 0
        if drug not in drug_agg:
            drug_agg[drug] = {"weighted_sum": 0.0, "total_patients": 0,
                              "dose_count_ws": 0.0, "total_weeks_ws": 0.0}
        drug_agg[drug]["weighted_sum"] += d["weekly_interval"] * pts
        drug_agg[drug]["total_patients"] += pts
        drug_agg[drug]["dose_count_ws"] += d["dose_count"] * pts
        drug_agg[drug]["total_weeks_ws"] += d["total_weeks"] * pts

    # Build sorted list (by total patients desc)
    drugs_sorted = sorted(
        drug_agg.items(),
        key=lambda x: x[1]["total_patients"],
    )

    drug_names = [d[0] for d in drugs_sorted]
    intervals = []
    patients_list = []
    hover_texts = []

    for drug, agg in drugs_sorted:
        tp = agg["total_patients"]
        avg_interval = agg["weighted_sum"] / tp if tp > 0 else 0
        avg_doses = agg["dose_count_ws"] / tp if tp > 0 else 0
        avg_weeks = agg["total_weeks_ws"] / tp if tp > 0 else 0
        intervals.append(round(avg_interval, 1))
        patients_list.append(tp)
        hover_texts.append(
            f"<b>{drug}</b><br>"
            f"Avg interval: {avg_interval:.1f} weeks<br>"
            f"Avg doses: {avg_doses:.1f}<br>"
            f"Avg treatment: {avg_weeks:.0f} weeks<br>"
            f"Patients: {tp:,}"
        )

    # Colour bars by interval: lower = more frequent dosing, higher = less frequent
    # Use Viridis colorscale for meaningful gradient (replaces blue→blue interpolation)
    import plotly.colors as pc
    max_interval = max(intervals) if intervals else 1
    ratios = [iv / max_interval if max_interval > 0 else 0 for iv in intervals]
    bar_colours = pc.sample_colorscale("Viridis", ratios)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=drug_names,
        x=intervals,
        orientation="h",
        marker=dict(color=bar_colours, line=dict(color="#FFFFFF", width=0.5)),
        text=[f"{iv}w" for iv in intervals],
        textposition="outside",
        textfont=dict(size=10, color="#425563"),
        customdata=list(zip(hover_texts, patients_list)),
        hovertemplate="%{customdata[0]}<extra></extra>",
        name="Weighted Avg Interval",
        showlegend=False,
    ))

    # Add patient count annotations on the right
    for i, (drug, pts) in enumerate(zip(drug_names, patients_list)):
        fig.add_annotation(
            x=max(intervals) * 1.15 if intervals else 10,
            y=drug,
            text=f"n={pts:,}",
            showarrow=False,
            font=dict(size=9, color="#768692"),
            xanchor="left",
        )

    return fig


def _dosing_by_trust(data: list[dict], colours: list[str]) -> go.Figure:
    """Build per-trust comparison: one row per trust, bars per directory, showing weekly_interval."""
    from collections import defaultdict

    # Group by trust × directory
    trust_dir = defaultdict(list)
    for d in data:
        trust_dir[(d["trust_name"], d["directory"])].append(d)

    # Get unique trusts and directories
    trusts = sorted(set(d["trust_name"] for d in data))
    directories = sorted(set(d["directory"] for d in data))

    fig = go.Figure()

    for i, directory in enumerate(directories):
        y_labels = []
        x_vals = []
        hover_list = []

        for trust in trusts:
            entries = trust_dir.get((trust, directory))
            if not entries:
                continue
            # Average if multiple entries per trust+directory (shouldn't happen at level 3)
            avg_iv = sum(e["weekly_interval"] * (e["patients"] or 0) for e in entries)
            total_pts = sum(e["patients"] or 0 for e in entries)
            if total_pts == 0:
                continue
            avg_iv /= total_pts
            avg_doses = sum(e["dose_count"] * (e["patients"] or 0) for e in entries) / total_pts
            avg_weeks = sum(e["total_weeks"] * (e["patients"] or 0) for e in entries) / total_pts

            # Shorten trust name for readability
            short_trust = trust.replace(" NHS FOUNDATION TRUST", "").replace(" HOSPITALS", "")
            y_labels.append(short_trust)
            x_vals.append(round(avg_iv, 1))
            hover_list.append(
                f"<b>{short_trust}</b><br>"
                f"Directorate: {directory}<br>"
                f"Interval: {avg_iv:.1f} weeks<br>"
                f"Avg doses: {avg_doses:.1f}<br>"
                f"Treatment: {avg_weeks:.0f} weeks<br>"
                f"Patients: {total_pts:,}"
            )

        if y_labels:
            fig.add_trace(go.Bar(
                y=y_labels,
                x=x_vals,
                orientation="h",
                name=directory,
                marker=dict(color=colours[i % len(colours)]),
                customdata=hover_list,
                hovertemplate="%{customdata}<extra></extra>",
            ))

    fig.update_layout(barmode="group")
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


def create_heatmap_figure(
    data: dict,
    title: str = "",
    metric: str = "patients",
) -> go.Figure:
    """Create a directorate × drug heatmap chart.

    Args:
        data: Dict from get_drug_directory_matrix() with keys:
              directories (list), drugs (list),
              matrix ({dir: {drug: {patients, cost, cost_pp_pa}}}).
        title: Chart title suffix (filter description).
        metric: Colour metric — "patients", "cost", or "cost_pp_pa".

    Returns:
        Plotly Figure with annotated heatmap.
    """
    directories = data.get("directories", [])
    drugs = data.get("drugs", [])
    matrix = data.get("matrix", {})

    if not directories or not drugs:
        return go.Figure()

    # Cap columns to top 25 drugs for readability
    max_drugs = 25
    total_drug_count = len(drugs)
    drugs = drugs[:max_drugs]
    capped = total_drug_count > max_drugs

    metric_labels = {
        "patients": "Patients",
        "cost": "Total Cost (£)",
        "cost_pp_pa": "Cost per Patient p.a. (£)",
    }
    metric_label = metric_labels.get(metric, "Patients")

    # Build 2D arrays for z-values, hover text, and cell annotations
    z_values = []
    hover_texts = []
    text_values = []

    for d in directories:
        row_z = []
        row_hover = []
        row_text = []
        dir_data = matrix.get(d, {})
        for drug in drugs:
            cell = dir_data.get(drug)
            if cell:
                val = cell.get(metric, cell.get("patients", 0))
                patients = cell.get("patients", 0)
                cost = cell.get("cost", 0)
                cpp = cell.get("cost_pp_pa", 0)
                row_z.append(val if val else 0)
                row_hover.append(
                    f"<b>{drug}</b><br>"
                    f"{d}<br>"
                    f"Patients: {patients:,}<br>"
                    f"Total cost: £{cost:,.0f}<br>"
                    f"Cost p.a.: £{cpp:,.0f}"
                )
                # Cell annotation text, formatted per metric
                if metric == "cost":
                    row_text.append(f"£{cost / 1000:.0f}k" if cost >= 1000 else f"£{cost:.0f}")
                elif metric == "cost_pp_pa":
                    row_text.append(f"£{cpp:,.0f}")
                else:
                    row_text.append(f"{patients:,}")
            else:
                row_z.append(0)
                row_hover.append(
                    f"<b>{drug}</b><br>{d}<br>No patients"
                )
                row_text.append("")
        z_values.append(row_z)
        hover_texts.append(row_hover)
        text_values.append(row_text)

    # Linear 5-stop NHS blue colorscale
    colorscale = [
        [0.0, "#E3F2FD"],
        [0.25, "#90CAF9"],
        [0.5, "#42A5F5"],
        [0.75, "#1E88E5"],
        [1.0, "#003087"],
    ]

    n_drugs = len(drugs)
    gap = 1 if n_drugs > 15 else 2

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=drugs,
            y=directories,
            colorscale=colorscale,
            zmin=0,
            text=text_values,
            texttemplate="%{text}",
            textfont=dict(size=10),
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            colorbar=dict(
                title=dict(
                    text=metric_label,
                    font=dict(size=12, color="#425563"),
                ),
                thickness=15,
                len=0.8,
            ),
            xgap=gap,
            ygap=gap,
        )
    )

    chart_title = f"Directorate × Drug — {metric_label}"
    if title:
        chart_title = f"{chart_title} — {title}"

    n_dirs = len(directories)
    fig_height = max(400, 80 + n_dirs * 40)

    layout = _base_layout(chart_title)
    layout.update(
        xaxis=dict(
            title="",
            tickfont=dict(size=11, color="#425563"),
            tickangle=-45,
            side="bottom",
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=12, color="#425563"),
            autorange="reversed",
            automargin=True,
        ),
        margin=dict(t=60, l=8, r=80, b=120),
        height=fig_height,
    )
    fig.update_layout(**layout)

    # Add subtitle when drug cap is reached
    if capped:
        fig.add_annotation(
            text=f"Showing top {max_drugs} of {total_drug_count} drugs",
            xref="paper", yref="paper",
            x=0.5, y=1.02,
            showarrow=False,
            font=dict(size=12, color=ANNOTATION_COLOR),
        )

    return fig


def create_duration_figure(
    data: list[dict],
    title: str = "",
    show_directory: bool = False,
) -> go.Figure:
    """Create horizontal bar chart showing average treatment duration by drug.

    Args:
        data: List of dicts from get_treatment_durations() with keys:
              drug, directory, avg_days, patients.
              Sorted by avg_days desc.
        title: Chart title suffix (filter description).
        show_directory: If True, include directory in label (for overview mode).

    Returns:
        Plotly Figure with horizontal bars coloured by patient count.
    """
    if not data:
        return go.Figure()

    # When not showing directory breakdown, aggregate same drug across directorates
    if not show_directory:
        agg = {}
        for d in data:
            drug = d["drug"]
            pts = d["patients"]
            days = d["avg_days"]
            if drug not in agg:
                agg[drug] = {"drug": drug, "total_weighted": 0.0, "total_pts": 0}
            agg[drug]["total_weighted"] += days * pts
            agg[drug]["total_pts"] += pts
        data = []
        for v in agg.values():
            if v["total_pts"] > 0:
                data.append({
                    "drug": v["drug"],
                    "avg_days": round(v["total_weighted"] / v["total_pts"], 1),
                    "patients": v["total_pts"],
                })
        data.sort(key=lambda x: -x["avg_days"])

    # Cap at 40 entries for readability (keep top by patient count, then re-sort by days)
    if len(data) > 40:
        data.sort(key=lambda x: -x["patients"])
        data = data[:40]
        data.sort(key=lambda x: -x["avg_days"])

    # Build labels
    if show_directory:
        labels = [f"{d['drug']} ({d['directory']})" for d in data]
    else:
        labels = [d["drug"] for d in data]

    days_values = [d["avg_days"] for d in data]
    patients_list = [d["patients"] for d in data]

    # Colour gradient by patient count: light for few → dark NHS blue for many
    max_pts = max(patients_list) if patients_list else 1
    min_pts = min(patients_list) if patients_list else 0
    pt_range = max_pts - min_pts if max_pts > min_pts else 1

    bar_colours = []
    for pts in patients_list:
        t = (pts - min_pts) / pt_range
        r = int(0x41 + (0x00 - 0x41) * t)
        g = int(0xB6 + (0x30 - 0xB6) * t)
        b = int(0xE6 + (0x87 - 0xE6) * t)
        bar_colours.append(f"rgb({r},{g},{b})")

    hover_texts = []
    for d in data:
        years = d["avg_days"] / 365.25
        hover_texts.append(
            f"<b>{d['drug']}</b><br>"
            f"Avg duration: {d['avg_days']:,.0f} days ({years:.1f} years)<br>"
            f"Patients: {d['patients']:,}"
        )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=labels,
            x=days_values,
            orientation="h",
            marker=dict(
                color=bar_colours,
                line=dict(color="#FFFFFF", width=1),
            ),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            text=[f"{v:,.0f}d" for v in days_values],
            textposition="outside",
            textfont=dict(size=10, color="#425563"),
        )
    )

    for i, pts in enumerate(patients_list):
        fig.add_annotation(
            x=days_values[i],
            y=labels[i],
            text=f"n={pts:,}",
            showarrow=False,
            xshift=45,
            font=dict(size=9, color=ANNOTATION_COLOR, family=CHART_FONT_FAMILY),
        )

    chart_title = "Treatment Duration by Drug"
    if title:
        chart_title += f"<br><span style='font-size:13px;color:{ANNOTATION_COLOR}'>{title}</span>"

    n_bars = len(data)
    fig_height = max(400, 40 + n_bars * 28)

    layout = _base_layout(chart_title)
    layout.update(
        xaxis=dict(
            title="Average Duration (days)",
            titlefont=dict(size=13, color="#425563"),
            tickfont=dict(size=11, color="#425563"),
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=True,
            zerolinecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=11, color="#425563"),
            automargin=True,
            autorange="reversed",
        ),
        margin=dict(t=60, l=8, r=80, b=50),
        height=fig_height,
        showlegend=False,
    )
    fig.update_layout(**layout)

    return fig


# --- Trust Comparison chart functions ---


def create_trust_market_share_figure(
    data: list[dict],
    title: str = "",
) -> go.Figure:
    """Create horizontal stacked bar chart showing drug market share per trust.

    Unlike create_market_share_figure (which groups by directorate), this groups
    by trust within a single directorate — used by Trust Comparison dashboard.

    Args:
        data: List of dicts from get_trust_market_share() with keys:
              trust_name, drug, patients, proportion, cost, cost_pp_pa.
        title: Chart title suffix.
    """
    if not data:
        return go.Figure()

    seen_trusts = []
    for d in data:
        t = d["trust_name"]
        if t not in seen_trusts:
            seen_trusts.append(t)

    seen_drugs = []
    for d in data:
        if d["drug"] not in seen_drugs:
            seen_drugs.append(d["drug"])

    drug_colour_map = {drug: DRUG_PALETTE[i % len(DRUG_PALETTE)] for i, drug in enumerate(seen_drugs)}
    lookup = {(d["trust_name"], d["drug"]): d for d in data}

    def short_trust(name):
        return name.replace(" NHS FOUNDATION TRUST", "").replace(" HOSPITALS", "")

    display_trusts = list(reversed(seen_trusts))

    traces = []
    for drug in seen_drugs:
        y_vals = []
        x_vals = []
        hover_texts = []
        for trust in display_trusts:
            row = lookup.get((trust, drug))
            y_vals.append(short_trust(trust))
            if row:
                x_vals.append(row["proportion"] * 100)
                hover_texts.append(
                    f"<b>{drug}</b><br>"
                    f"{short_trust(trust)}<br>"
                    f"Patients: {row['patients']:,}<br>"
                    f"Share: {row['proportion']:.1%}<br>"
                    f"Cost: £{row['cost']:,.0f}<br>"
                    f"Cost p.p.p.a: £{row['cost_pp_pa']:,.0f}"
                )
            else:
                x_vals.append(0)
                hover_texts.append("")

        traces.append(go.Bar(
            name=drug, y=y_vals, x=x_vals, orientation="h",
            marker_color=drug_colour_map[drug],
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        ))

    display_title = f"Drug Market Share by Trust — {title}" if title else "Drug Market Share by Trust"
    n_drugs = len(seen_drugs)
    legend_margins = _smart_legend_margin(n_drugs)

    fig = go.Figure(data=traces)
    layout = _base_layout(display_title)
    layout.update(
        barmode="stack",
        xaxis=dict(title="% of patients", ticksuffix="%", range=[0, 105], gridcolor=GRID_COLOR, zeroline=False),
        yaxis=dict(title="", automargin=True),
        legend=_smart_legend(n_drugs, legend_title="Drug"),
        margin=dict(t=50, l=8, **legend_margins),
        height=max(300, len(seen_trusts) * 60 + 200),
    )
    fig.update_layout(**layout)

    return fig


def create_trust_heatmap_figure(
    data: dict,
    title: str = "",
    metric: str = "patients",
) -> go.Figure:
    """Create a trust x drug heatmap for a single directorate.

    Args:
        data: Dict from get_trust_heatmap() with keys:
              trusts (list), drugs (list),
              matrix ({trust_name: {drug: {patients, cost, cost_pp_pa}}}).
        title: Chart title suffix.
        metric: Colour metric — "patients", "cost", or "cost_pp_pa".
    """
    trusts = data.get("trusts", [])
    drugs = data.get("drugs", [])
    matrix = data.get("matrix", {})

    if not trusts or not drugs:
        return go.Figure()

    total_drug_count = len(drugs)
    drugs = drugs[:25]
    capped = total_drug_count > 25

    metric_labels = {
        "patients": "Patients",
        "cost": "Total Cost (£)",
        "cost_pp_pa": "Cost per Patient p.a. (£)",
    }
    metric_label = metric_labels.get(metric, "Patients")

    def short_trust(name):
        return name.replace(" NHS FOUNDATION TRUST", "").replace(" HOSPITALS", "")

    z_values = []
    hover_texts = []
    text_values = []

    for t in trusts:
        row_z = []
        row_hover = []
        row_text = []
        trust_data = matrix.get(t, {})
        for drug in drugs:
            cell = trust_data.get(drug)
            if cell:
                val = cell.get(metric, cell.get("patients", 0))
                patients = cell.get("patients", 0)
                cost = cell.get("cost", 0)
                cpp = cell.get("cost_pp_pa", 0)
                row_z.append(val if val else 0)
                row_hover.append(
                    f"<b>{drug}</b><br>"
                    f"{short_trust(t)}<br>"
                    f"Patients: {patients:,}<br>"
                    f"Total cost: £{cost:,.0f}<br>"
                    f"Cost p.a.: £{cpp:,.0f}"
                )
                if metric == "cost":
                    row_text.append(f"£{cost / 1000:.0f}k" if cost >= 1000 else f"£{cost:.0f}")
                elif metric == "cost_pp_pa":
                    row_text.append(f"£{cpp:,.0f}")
                else:
                    row_text.append(f"{patients:,}")
            else:
                row_z.append(0)
                row_hover.append(f"<b>{drug}</b><br>{short_trust(t)}<br>No patients")
                row_text.append("")
        z_values.append(row_z)
        hover_texts.append(row_hover)
        text_values.append(row_text)

    # Linear 5-stop NHS blue colorscale
    colorscale = [
        [0.0, "#E3F2FD"],
        [0.25, "#90CAF9"],
        [0.5, "#42A5F5"],
        [0.75, "#1E88E5"],
        [1.0, "#003087"],
    ]

    display_trusts = [short_trust(t) for t in trusts]
    n_drugs = len(drugs)
    gap = 1 if n_drugs > 15 else 2

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values, x=drugs, y=display_trusts,
            colorscale=colorscale,
            zmin=0,
            text=text_values,
            texttemplate="%{text}",
            textfont=dict(size=10),
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
            colorbar=dict(
                title=dict(text=metric_label, font=dict(size=12, color="#425563")),
                thickness=15, len=0.8,
            ),
            xgap=gap, ygap=gap,
        )
    )

    chart_title = f"Trust × Drug — {metric_label}"
    if title:
        chart_title = f"{chart_title} — {title}"

    n_trusts = len(trusts)

    layout = _base_layout(chart_title)
    layout.update(
        xaxis=dict(title="", tickfont=dict(size=11, color="#425563"), tickangle=-45, side="bottom"),
        yaxis=dict(title="", tickfont=dict(size=12, color="#425563"), autorange="reversed", automargin=True),
        margin=dict(t=60, l=8, r=80, b=120),
        height=max(300, 80 + n_trusts * 50),
    )
    fig.update_layout(**layout)

    if capped:
        fig.add_annotation(
            text=f"Showing top 25 of {total_drug_count} drugs",
            xref="paper", yref="paper",
            x=0.5, y=1.02,
            showarrow=False,
            font=dict(size=12, color=ANNOTATION_COLOR),
        )

    return fig


def create_trust_duration_figure(
    data: list[dict],
    title: str = "",
) -> go.Figure:
    """Create grouped horizontal bar chart showing drug durations by trust.

    Args:
        data: List of dicts from get_trust_durations() with keys:
              drug, trust_name, avg_days, patients.
        title: Chart title suffix.
    """
    if not data:
        return go.Figure()

    seen_drugs = []
    for d in data:
        if d["drug"] not in seen_drugs:
            seen_drugs.append(d["drug"])

    seen_trusts = []
    for d in data:
        t = d["trust_name"]
        if t not in seen_trusts:
            seen_trusts.append(t)

    def short_trust(name):
        return name.replace(" NHS FOUNDATION TRUST", "").replace(" HOSPITALS", "")

    trust_colour_map = {t: TRUST_PALETTE[i % len(TRUST_PALETTE)] for i, t in enumerate(seen_trusts)}
    lookup = {(d["drug"], d["trust_name"]): d for d in data}

    display_drugs = list(reversed(seen_drugs))

    traces = []
    for trust in seen_trusts:
        y_vals = []
        x_vals = []
        hover_texts = []
        for drug in display_drugs:
            row = lookup.get((drug, trust))
            y_vals.append(drug)
            if row:
                years = row["avg_days"] / 365.25
                x_vals.append(row["avg_days"])
                hover_texts.append(
                    f"<b>{drug}</b><br>"
                    f"{short_trust(trust)}<br>"
                    f"Avg duration: {row['avg_days']:,.0f} days ({years:.1f} yrs)<br>"
                    f"Patients: {row['patients']:,}"
                )
            else:
                x_vals.append(0)
                hover_texts.append("")

        traces.append(go.Bar(
            name=short_trust(trust), y=y_vals, x=x_vals, orientation="h",
            marker_color=trust_colour_map[trust],
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        ))

    display_title = f"Treatment Duration by Trust — {title}" if title else "Treatment Duration by Trust"
    n_trusts = len(seen_trusts)
    legend_margins = _smart_legend_margin(n_trusts)

    fig = go.Figure(data=traces)
    layout = _base_layout(display_title)
    layout.update(
        barmode="group",
        xaxis=dict(
            title="Average Duration (days)", titlefont=dict(size=13, color="#425563"),
            gridcolor="rgba(0,0,0,0.06)", zeroline=True, zerolinecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(title="", automargin=True, tickfont=dict(size=11, color="#425563")),
        legend=_smart_legend(n_trusts, legend_title="Trust"),
        margin=dict(t=60, l=8, **legend_margins),
        height=max(350, len(seen_drugs) * 35 + 200),
        bargap=0.15, bargroupgap=0.05,
    )
    fig.update_layout(**layout)

    return fig


def create_retention_funnel_figure(
    data: list[dict],
    title: str = "",
) -> go.Figure:
    """Create a retention funnel showing patient drop-off by treatment line depth.

    Args:
        data: List of dicts with keys: depth, label, patients, pct
        title: Chart title from filter state.

    Returns:
        Plotly Figure with go.Funnel trace.
    """
    if not data:
        return go.Figure()

    display_title = f"Treatment Retention — {title}" if title else "Treatment Retention"

    labels = [d["label"] for d in data]
    patients = [d["patients"] for d in data]
    pcts = [d["pct"] for d in data]

    # NHS blue gradient: darkest at top (most patients) → lightest at bottom
    funnel_colors = [
        "#003087",  # NHS Heritage Blue (1st drug)
        "#005EB8",  # NHS Blue
        "#1E88E5",  # Mid blue
        "#42A5F5",  # Light blue
        "#90CAF9",  # Pale blue
    ]
    colors = funnel_colors[: len(data)]
    if len(colors) < len(data):
        colors.extend(["#E3F2FD"] * (len(data) - len(colors)))

    text_values = [
        f"{p:,} patients ({pct}%)" for p, pct in zip(patients, pcts)
    ]

    fig = go.Figure(
        go.Funnel(
            y=labels,
            x=patients,
            text=text_values,
            textposition="inside",
            textfont=dict(family=CHART_FONT_FAMILY, size=14, color="white"),
            marker=dict(color=colors),
            connector=dict(line=dict(color=GRID_COLOR, width=1)),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Patients: %{x:,}<br>"
                "%{text}<extra></extra>"
            ),
        )
    )

    layout = _base_layout(display_title)
    layout.update(
        margin=dict(t=60, l=8, r=8, b=40),
        yaxis=dict(automargin=True),
        height=max(300, len(data) * 80 + 120),
    )
    fig.update_layout(**layout)

    return fig


def create_pathway_depth_figure(
    data: list[dict],
    title: str = "",
) -> go.Figure:
    """Create a horizontal bar chart showing patients who stopped at each treatment depth.

    Args:
        data: List of dicts with keys: depth, label, patients, pct
        title: Chart title from filter state.

    Returns:
        Plotly Figure with horizontal bar trace.
    """
    if not data:
        return go.Figure()

    display_title = f"Pathway Depth Distribution — {title}" if title else "Pathway Depth Distribution"

    labels = [d["label"] for d in data]
    patients = [d["patients"] for d in data]
    pcts = [d["pct"] for d in data]

    # NHS blue gradient: darkest for depth 1 (most patients) → lightest
    bar_colors = [
        "#003087",
        "#005EB8",
        "#1E88E5",
        "#42A5F5",
        "#90CAF9",
    ]
    colors = bar_colors[: len(data)]
    if len(colors) < len(data):
        colors.extend(["#E3F2FD"] * (len(data) - len(colors)))

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=patients,
            orientation="h",
            text=[f"{p:,} ({pct}%)" for p, pct in zip(patients, pcts)],
            textposition="auto",
            textfont=dict(family=CHART_FONT_FAMILY, size=13),
            marker=dict(color=colors),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Patients: %{x:,}<br>"
                "<extra></extra>"
            ),
        )
    )

    layout = _base_layout(display_title)
    layout.update(
        margin=dict(t=60, l=8, r=24, b=40),
        yaxis=dict(
            automargin=True,
            autorange="reversed",
            title="",
        ),
        xaxis=dict(
            title="Patients",
            gridcolor=GRID_COLOR,
        ),
        height=max(300, len(data) * 70 + 120),
        bargap=0.3,
    )
    fig.update_layout(**layout)

    return fig


def create_duration_cost_scatter_figure(
    data: list[dict],
    title: str = "",
) -> go.Figure:
    """Create a Duration vs Cost scatter plot from drug-level data.

    Each point represents a drug (within a directory). x=avg treatment days,
    y=annualised cost per patient, size=patient count, color=directory.
    Quadrant lines at median values divide into 4 regions.
    """
    if not data:
        return go.Figure()

    import statistics

    display_title = f"Duration vs Cost — {title}" if title else "Duration vs Cost"

    # Assign colors by directory
    directories = sorted(set(d["directory"] for d in data))
    dir_colors = {
        d: DRUG_PALETTE[i % len(DRUG_PALETTE)]
        for i, d in enumerate(directories)
    }

    # Global max patients for consistent sizing across directories
    global_max_p = max((d["patients"] for d in data), default=1) or 1

    # Build one trace per directory for legend grouping
    fig = go.Figure()
    for directory in directories:
        subset = [d for d in data if d["directory"] == directory]
        patients = [d["patients"] for d in subset]

        # Scale marker size: min 8, max 40, relative to global max
        sizes = [max(8, min(40, 8 + 32 * (p / global_max_p))) for p in patients]

        fig.add_trace(go.Scatter(
            x=[d["avg_days"] for d in subset],
            y=[d["cost_pp_pa"] for d in subset],
            mode="markers",
            name=directory,
            marker=dict(
                size=sizes,
                color=dir_colors[directory],
                opacity=0.75,
                line=dict(width=1, color="white"),
            ),
            text=[d["drug"] for d in subset],
            customdata=[[d["patients"], d["directory"], d["avg_days"], d["cost_pp_pa"]] for d in subset],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Directory: %{customdata[1]}<br>"
                "Avg duration: %{customdata[2]} days<br>"
                "Cost p.a.: £%{customdata[3]:,.0f}<br>"
                "Patients: %{customdata[0]:,}<br>"
                "<extra></extra>"
            ),
        ))

    # Quadrant lines at median values
    all_days = [d["avg_days"] for d in data]
    all_costs = [d["cost_pp_pa"] for d in data]
    med_days = statistics.median(all_days)
    med_cost = statistics.median(all_costs)

    fig.add_hline(
        y=med_cost, line_dash="dash", line_color=ANNOTATION_COLOR,
        line_width=1,
        annotation_text=f"Median £{med_cost:,.0f}",
        annotation_position="top left",
        annotation_font=dict(size=10, color=ANNOTATION_COLOR, family=CHART_FONT_FAMILY),
    )
    fig.add_vline(
        x=med_days, line_dash="dash", line_color=ANNOTATION_COLOR,
        line_width=1,
        annotation_text=f"Median {med_days:.0f} days",
        annotation_position="top right",
        annotation_font=dict(size=10, color=ANNOTATION_COLOR, family=CHART_FONT_FAMILY),
    )

    n_dirs = len(directories)
    legend = _smart_legend(n_dirs, "Directory")
    legend_margins = _smart_legend_margin(n_dirs)

    layout = _base_layout(display_title)
    layout.update(
        margin=dict(t=60, l=8, **legend_margins),
        xaxis=dict(
            title="Average Treatment Duration (days)",
            gridcolor=GRID_COLOR,
            zeroline=False,
        ),
        yaxis=dict(
            title="Cost per Patient per Annum (£)",
            gridcolor=GRID_COLOR,
            automargin=True,
            zeroline=False,
        ),
        legend=legend,
    )
    fig.update_layout(**layout)

    return fig


def create_drug_network_figure(data: dict, title: str = "") -> go.Figure:
    """Create a drug co-occurrence network graph.

    Nodes are drugs arranged in a circle, edges show co-occurrence in pathways.
    Node size = total patients, edge width = switching flow between drugs.
    """
    import math

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not nodes:
        return go.Figure()

    display_title = f"Drug Network — {title}" if title else "Drug Network"

    # Circular layout
    n = len(nodes)
    node_names = [nd["name"] for nd in nodes]
    node_patients = [nd["total_patients"] for nd in nodes]
    name_to_idx = {nd["name"]: i for i, nd in enumerate(nodes)}

    angles = [2 * math.pi * i / n for i in range(n)]
    x_pos = [math.cos(a) for a in angles]
    y_pos = [math.sin(a) for a in angles]

    fig = go.Figure()

    # Draw edges as individual traces (each gets its own width)
    max_edge_patients = max((e["patients"] for e in edges), default=1) or 1
    for edge in edges:
        src_idx = name_to_idx.get(edge["source"])
        tgt_idx = name_to_idx.get(edge["target"])
        if src_idx is None or tgt_idx is None:
            continue

        # Scale width: min 0.5, max 6
        width = max(0.5, min(6, 0.5 + 5.5 * (edge["patients"] / max_edge_patients)))
        # Opacity scales with relative strength
        opacity = max(0.15, min(0.7, 0.15 + 0.55 * (edge["patients"] / max_edge_patients)))

        fig.add_trace(go.Scatter(
            x=[x_pos[src_idx], x_pos[tgt_idx]],
            y=[y_pos[src_idx], y_pos[tgt_idx]],
            mode="lines",
            line=dict(width=width, color=f"rgba(0,94,184,{opacity})"),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Draw nodes
    max_patients = max(node_patients, default=1) or 1
    sizes = [max(12, min(50, 12 + 38 * (p / max_patients))) for p in node_patients]
    colors = [DRUG_PALETTE[i % len(DRUG_PALETTE)] for i in range(n)]

    fig.add_trace(go.Scatter(
        x=x_pos,
        y=y_pos,
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=colors,
            line=dict(width=1.5, color="white"),
        ),
        text=node_names,
        textposition="top center",
        textfont=dict(size=9, family=CHART_FONT_FAMILY),
        customdata=[[p] for p in node_patients],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Patients: %{customdata[0]:,}<br>"
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    layout = _base_layout(display_title)
    layout.update(
        margin=dict(t=60, l=24, r=24, b=24),
        xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False),
    )
    fig.update_layout(**layout)

    return fig


def create_drug_timeline_figure(data: list[dict], title: str = "") -> go.Figure:
    """Create a Gantt-style timeline showing when each drug cohort was active.

    Each horizontal bar spans from first_seen to last_seen for a drug,
    grouped by directory, with color indicating directory and text showing
    patient count.

    Args:
        data: List of dicts with keys: drug, directory, first_seen, last_seen,
              patients, cost_pp_pa.
        title: Chart title.

    Returns:
        Plotly Figure with horizontal bars.
    """
    if not data:
        return go.Figure()

    from datetime import datetime

    display_title = title or "Drug Timeline"

    # Parse dates and sort by directory then first_seen
    for d in data:
        d["_fs"] = datetime.fromisoformat(d["first_seen"])
        d["_ls"] = datetime.fromisoformat(d["last_seen"])
        d["_duration_days"] = max(1, (d["_ls"] - d["_fs"]).days)

    # Sort: by directory alphabetically, then by first_seen ascending
    data.sort(key=lambda d: (d["directory"], d["_fs"]))

    # Assign colors by directory
    directories = list(dict.fromkeys(d["directory"] for d in data))
    dir_colors = {
        d: DRUG_PALETTE[i % len(DRUG_PALETTE)]
        for i, d in enumerate(directories)
    }

    # Build y-axis labels: "Drug (Directory)" for multi-directory views, just "Drug" for single
    single_directory = len(directories) == 1
    y_labels = []
    for d in data:
        if single_directory:
            y_labels.append(d["drug"])
        else:
            y_labels.append(f"{d['drug']} ({d['directory']})")

    # Build one trace per directory for legend grouping
    fig = go.Figure()
    dir_legend_shown = set()

    for i, d in enumerate(data):
        show_legend = d["directory"] not in dir_legend_shown
        dir_legend_shown.add(d["directory"])

        duration_ms = d["_duration_days"] * 86_400_000  # days → milliseconds
        patients = d["patients"]
        cost = d["cost_pp_pa"]

        fig.add_trace(
            go.Bar(
                y=[y_labels[i]],
                x=[duration_ms],
                base=[d["_fs"]],
                orientation="h",
                marker=dict(
                    color=dir_colors[d["directory"]],
                    line=dict(width=0),
                ),
                name=d["directory"],
                legendgroup=d["directory"],
                showlegend=show_legend,
                text=f"{patients:,}",
                textposition="inside",
                textfont=dict(color="white", size=10),
                hovertemplate=(
                    f"<b>{d['drug']}</b><br>"
                    f"Directory: {d['directory']}<br>"
                    f"First seen: {d['_fs'].strftime('%b %Y')}<br>"
                    f"Last seen: {d['_ls'].strftime('%b %Y')}<br>"
                    f"Duration: {d['_duration_days']:,} days<br>"
                    f"Patients: {patients:,}<br>"
                    f"Cost p.a.: £{cost:,.0f}"
                    "<extra></extra>"
                ),
            )
        )

    # Layout
    n_bars = len(data)
    bar_height = 28
    dynamic_height = max(400, n_bars * bar_height + 120)

    n_dirs = len(directories)
    legend_margins = _smart_legend_margin(n_dirs)
    legend = _smart_legend(n_dirs, legend_title="Directory")

    layout = _base_layout(display_title)
    layout.update(
        xaxis=dict(
            type="date",
            gridcolor=GRID_COLOR,
            dtick="M6",
            tickformat="%b\n%Y",
        ),
        yaxis=dict(
            automargin=True,
            autorange="reversed",
            tickfont=dict(size=11),
        ),
        barmode="overlay",
        height=dynamic_height,
        margin=dict(t=60, l=8, **legend_margins),
        legend=legend,
        bargap=0.3,
    )
    fig.update_layout(**layout)

    return fig


def create_dosing_distribution_figure(
    data: list[dict], title: str = ""
) -> go.Figure:
    """Create horizontal bar chart of average administered doses per drug.

    Args:
        data: list of dicts with keys: drug, directory, avg_doses, patients
        title: chart title suffix
    """
    if not data:
        return go.Figure()

    display_title = f"Average Administered Doses — {title}" if title else "Average Administered Doses"

    # Group by directory for coloring
    directories = sorted(set(d["directory"] for d in data))
    dir_colors = {
        d: DRUG_PALETTE[i % len(DRUG_PALETTE)]
        for i, d in enumerate(directories)
    }

    single_directory = len(directories) == 1

    # Sort by avg_doses descending
    sorted_data = sorted(data, key=lambda x: x["avg_doses"])

    # Build y-labels
    if single_directory:
        y_labels = [d["drug"] for d in sorted_data]
    else:
        y_labels = [f"{d['drug']} ({d['directory']})" for d in sorted_data]

    fig = go.Figure()

    # One trace per directory for legend grouping
    shown_dirs = set()
    for i, row in enumerate(sorted_data):
        d = row["directory"]
        show_legend = d not in shown_dirs
        shown_dirs.add(d)

        fig.add_trace(go.Bar(
            y=[y_labels[i]],
            x=[row["avg_doses"]],
            orientation="h",
            marker_color=dir_colors[d],
            name=d,
            showlegend=show_legend,
            legendgroup=d,
            text=[f"{row['avg_doses']:.0f}"],
            textposition="inside",
            textfont=dict(color="white", size=11),
            hovertemplate=(
                f"<b>{row['drug']}</b><br>"
                f"Directory: {d}<br>"
                f"Avg doses: {row['avg_doses']:.1f}<br>"
                f"Patients: {row['patients']:,}"
                "<extra></extra>"
            ),
        ))

    n_bars = len(sorted_data)
    bar_height = 24
    dynamic_height = max(400, n_bars * bar_height + 120)

    n_dirs = len(directories)
    legend_margins = _smart_legend_margin(n_dirs)
    legend = _smart_legend(n_dirs, legend_title="Directory")

    layout = _base_layout(display_title)
    layout.update(
        xaxis=dict(
            title="Average Doses Administered",
            gridcolor=GRID_COLOR,
            zeroline=False,
        ),
        yaxis=dict(
            automargin=True,
            tickfont=dict(size=11),
        ),
        barmode="overlay",
        height=dynamic_height,
        margin=dict(t=60, l=8, **legend_margins),
        legend=legend,
        bargap=0.3,
    )
    fig.update_layout(**layout)

    return fig


def create_trend_figure(
    data: list[dict],
    title: str = "",
    metric: str = "patients",
) -> go.Figure:
    """Create a line chart showing trends over time from pathway_trends data.

    Args:
        data: List of dicts with keys: period_end, name, value
        title: Chart title
        metric: "patients", "total_cost", or "cost_pp_pa" (for y-axis label)
    """
    if not data:
        fig = go.Figure()
        fig.add_annotation(
            text="No trend data available.<br>Run <b>python -m cli.compute_trends</b> to generate.",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color=ANNOTATION_COLOR, family=CHART_FONT_FAMILY),
        )
        layout = _base_layout(title or "Temporal Trends")
        fig.update_layout(**layout)
        return fig

    display_title = title or "Temporal Trends"

    # Group data by name (drug or directory)
    from collections import defaultdict
    series = defaultdict(lambda: {"periods": [], "values": []})
    for row in data:
        name = row.get("name", "")
        series[name]["periods"].append(row["period_end"])
        series[name]["values"].append(row.get("value", 0))

    n_series = len(series)
    fig = go.Figure()

    for i, (name, s) in enumerate(sorted(series.items())):
        colour = DRUG_PALETTE[i % len(DRUG_PALETTE)]
        fig.add_trace(go.Scatter(
            x=s["periods"],
            y=s["values"],
            mode="lines+markers",
            name=name,
            customdata=[name] * len(s["periods"]),
            line=dict(color=colour, width=2),
            marker=dict(color=colour, size=6),
            hovertemplate=(
                f"<b>{name}</b><br>"
                "Period: %{x}<br>"
                "Value: %{y:,.0f}<extra></extra>"
            ),
        ))

    metric_labels = {
        "patients": "Patients",
        "total_cost": "Total Cost (£)",
        "cost_pp_pa": "Cost per Patient p.a. (£)",
    }
    y_label = metric_labels.get(metric, "Value")

    legend = _smart_legend(n_series)
    legend_margins = _smart_legend_margin(n_series)

    layout = _base_layout(display_title)
    layout.update(
        xaxis=dict(
            title="Period",
            gridcolor=GRID_COLOR,
            type="category",
        ),
        yaxis=dict(
            title=y_label,
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor=GRID_COLOR,
        ),
        margin=dict(t=60, l=8, **legend_margins),
        legend=legend,
        hovermode="x unified",
    )
    fig.update_layout(**layout)

    return fig
