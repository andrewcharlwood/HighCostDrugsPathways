# Phase 10 Design Specification

## Aesthetic Direction

**Utilitarian clinical** — authoritative, data-dense, no decoration. Every element earns its screen real estate. The NHS brand palette is law. The hierarchy is:

1. Header (identity + live metrics)
2. Sub-header (global controls — always visible, always the same)
3. Sidebar (view switching)
4. Content (view-specific)

Vertical rhythm: header 56px → sub-header 44px → content starts at 100px from top.

---

## 1. Header Redesign

### Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [NHS] HCD Analysis  │  3,847 / 11,118    39 / 42    £48.2M / £130.6M  │  ● 11,118 patients  Updated 2h ago │
│        BRAND        │   patients           drugs        cost           │           FRESHNESS               │
└─────────────────────────────────────────────────────────────────────────┘
```

The header stays 56px tall. The breadcrumb is REMOVED (it was redundant — the sidebar shows where you are). The middle section becomes **3 inline fraction KPIs**. The right section stays as data freshness.

### HTML Structure (Dash)

```python
html.Header(className="top-header", children=[
    # Left: brand (unchanged)
    html.Div(className="top-header__brand", children=[
        html.Div("NHS", className="top-header__logo"),
        html.Div(html.Div("HCD Analysis", className="top-header__title")),
    ]),

    # Center: fraction KPIs
    html.Div(className="top-header__kpis", children=[
        html.Div(className="header-kpi", children=[
            html.Span("—", id="kpi-filtered-patients", className="header-kpi__num"),
            html.Span(" / ", className="header-kpi__sep"),
            html.Span("—", id="kpi-total-patients", className="header-kpi__den"),
            html.Span("patients", className="header-kpi__label"),
        ]),
        html.Div(className="header-kpi", children=[
            html.Span("—", id="kpi-filtered-drugs", className="header-kpi__num"),
            html.Span(" / ", className="header-kpi__sep"),
            html.Span("—", id="kpi-total-drugs", className="header-kpi__den"),
            html.Span("drugs", className="header-kpi__label"),
        ]),
        html.Div(className="header-kpi", children=[
            html.Span("—", id="kpi-filtered-cost", className="header-kpi__num"),
            html.Span(" / ", className="header-kpi__sep"),
            html.Span("—", id="kpi-total-cost", className="header-kpi__den"),
            html.Span("cost", className="header-kpi__label"),
        ]),
    ]),

    # Right: data freshness (unchanged structure, same IDs)
    html.Div(className="top-header__right", children=[
        html.Span(children=[
            html.Span(className="status-dot"),
            html.Span("...", id="header-record-count"),
        ]),
        html.Span(children=[
            "Updated: ",
            html.Span("...", id="header-last-updated"),
        ]),
    ]),
])
```

### CSS — New Classes

```css
/* ── Header KPIs ── */
.top-header__kpis {
    display: flex;
    align-items: center;
    gap: 24px;
}
.header-kpi {
    display: flex;
    align-items: baseline;
    gap: 3px;
    color: rgba(255, 255, 255, 0.6);
    font-size: 13px;
    font-weight: 400;
    white-space: nowrap;
}
.header-kpi__num {
    color: var(--nhs-white);
    font-size: 16px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.header-kpi__sep {
    color: rgba(255, 255, 255, 0.35);
    font-weight: 300;
    font-size: 14px;
    margin: 0 1px;
}
.header-kpi__den {
    color: rgba(255, 255, 255, 0.5);
    font-size: 13px;
    font-weight: 400;
    font-variant-numeric: tabular-nums;
}
.header-kpi__label {
    color: rgba(255, 255, 255, 0.4);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-left: 4px;
}
```

### CSS — Modified Classes

Remove `.top-header__breadcrumb` usage (delete from header.py, CSS can stay for backward compat or be removed).

### Callback IDs

- **Outputs (filtered values from chart-data)**: `kpi-filtered-patients`, `kpi-filtered-drugs`, `kpi-filtered-cost`
- **Outputs (total values from reference-data)**: `kpi-total-patients`, `kpi-total-drugs`, `kpi-total-cost`
- **Existing (unchanged)**: `header-record-count`, `header-last-updated`

---

## 2. Global Filter Sub-Header

### Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  VIEW  [By Directory] [By Indication]  │  INITIATED [All years ▾]  LAST SEEN [Last 6 months ▾]  │
└─────────────────────────────────────────────────────────────────────────┘
```

Sits directly below the header. Fixed position. Full width minus sidebar. Light blue-grey background (`#E8F0FE` — the same tint used for active sidebar items) with a subtle bottom border. Contains ONLY the chart type toggle and date filters — no drug/trust/directorate buttons.

### HTML Structure (Dash)

```python
html.Div(className="sub-header", children=[
    # Chart type toggle
    html.Div(className="sub-header__group", children=[
        html.Span("View", className="sub-header__label"),
        html.Div(className="toggle-pills", role="radiogroup",
                 **{"aria-label": "Chart view type"}, children=[
            html.Button("By Directory", id="chart-type-directory",
                       className="toggle-pill toggle-pill--active",
                       role="radio", n_clicks=0, **{"aria-checked": "true"}),
            html.Button("By Indication", id="chart-type-indication",
                       className="toggle-pill", role="radio",
                       n_clicks=0, **{"aria-checked": "false"}),
        ]),
    ]),
    # Divider
    html.Div(className="sub-header__divider"),
    # Date filters
    html.Div(className="sub-header__group", children=[
        html.Span("Initiated", className="sub-header__label"),
        dcc.Dropdown(id="filter-initiated", ...same options...,
                    className="filter-dropdown"),
    ]),
    html.Div(className="sub-header__group", children=[
        html.Span("Last seen", className="sub-header__label"),
        dcc.Dropdown(id="filter-last-seen", ...same options...,
                    className="filter-dropdown"),
    ]),
])
```

### CSS — New Classes

```css
/* ── Global Filter Sub-Header ── */
.sub-header {
    position: fixed;
    top: 56px;                      /* below main header */
    left: var(--sidebar-w);         /* right of sidebar */
    right: 0;
    z-index: 150;
    height: 44px;
    background: #E8F0FE;
    border-bottom: 1px solid #C5D4E8;
    display: flex;
    align-items: center;
    padding: 0 24px;
    gap: 16px;
}
.sub-header__group {
    display: flex;
    align-items: center;
    gap: 8px;
}
.sub-header__label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--nhs-dark-blue);
    white-space: nowrap;
    opacity: 0.6;
}
.sub-header__divider {
    width: 1px;
    height: 24px;
    background: rgba(0, 48, 135, 0.15);
}
```

### CSS — Modified Classes

`.main` top margin increases from 56px to 100px (56px header + 44px sub-header):

```css
.main {
    margin-left: var(--sidebar-w);
    margin-top: 100px;   /* was 56px */
    padding: 24px;
    min-height: calc(100vh - 100px);  /* was 56px */
    display: flex; flex-direction: column; gap: 20px;
}
```

`.sidebar` top position increases to 56px (stays below main header, sub-header floats over content area):

Actually, the sidebar should start below the header (56px), and the sub-header should start at the right of the sidebar. The sidebar extends from 56px to bottom. The sub-header is only in the content area.

```
┌──────────────────────────────────────────────────┐
│                    HEADER (56px)                  │
├────────┬─────────────────────────────────────────┤
│        │          SUB-HEADER (44px)              │
│ SIDE   ├─────────────────────────────────────────┤
│ BAR    │                                         │
│ (240)  │           CONTENT AREA                  │
│        │                                         │
└────────┴─────────────────────────────────────────┘
```

---

## 3. Trust Comparison Landing Page

### Layout

A clean selector grid. Each button is a card-like element showing the directorate/indication name. Arranged in a responsive grid — 3 columns for ~14 directorates, 4 columns for ~32 indications.

```
┌─────────────────────────────────────────────────────┐
│  Trust Comparison                                   │
│  Select a directorate to compare drug usage across  │
│  trusts.                                            │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │CARDIOLOGY│ │DERMATOL- │ │DIABETIC  │            │
│  │          │ │OGY       │ │MEDICINE  │            │
│  │  847 pts │ │  423 pts │ │  312 pts │            │
│  │  12 drugs│ │   8 drugs│ │   6 drugs│            │
│  └──────────┘ └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │GASTRO-   │ │CLINICAL  │ │MEDICAL   │            │
│  │ENTEROLOGY│ │HAEMATOL..│ │ONCOLOGY  │            │
│  │  298 pts │ │  567 pts │ │  234 pts │            │
│  │  11 drugs│ │  15 drugs│ │   9 drugs│            │
│  └──────────┘ └──────────┘ └──────────┘            │
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

Each card shows: directorate name (bold), patient count, drug count. Sorted by patient count descending. The blue left border on hover provides the NHS accent.

### HTML Structure (Dash)

```python
html.Div(className="tc-landing", id="trust-comparison-landing", children=[
    # Header
    html.Div(className="tc-landing__header", children=[
        html.H2("Trust Comparison", className="tc-landing__title"),
        html.P(
            "Select a directorate to compare drug usage across trusts.",
            className="tc-landing__desc",
            id="tc-landing-desc",
        ),
    ]),
    # Grid of directorate cards
    html.Div(className="tc-landing__grid", id="tc-landing-grid", children=[
        # Populated by callback — one per directorate/indication
        # Each card:
        html.Button(
            className="tc-card",
            id={"type": "tc-selector", "index": "CARDIOLOGY"},
            n_clicks=0,
            children=[
                html.Div("CARDIOLOGY", className="tc-card__name"),
                html.Div(className="tc-card__stats", children=[
                    html.Span("847 patients", className="tc-card__stat"),
                    html.Span("·", className="tc-card__dot"),
                    html.Span("12 drugs", className="tc-card__stat"),
                ]),
            ],
        ),
        # ... more cards
    ]),
])
```

### CSS — New Classes

```css
/* ── Trust Comparison Landing ── */
.tc-landing {
    display: flex;
    flex-direction: column;
    gap: 24px;
}
.tc-landing__header {
    padding: 0 0 8px;
}
.tc-landing__title {
    font-size: 22px;
    font-weight: 700;
    color: var(--nhs-dark-blue);
    margin-bottom: 4px;
}
.tc-landing__desc {
    font-size: 14px;
    color: var(--nhs-mid-grey);
    font-weight: 400;
}
.tc-landing__grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}

/* Directorate selector cards */
.tc-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 16px 20px;
    background: var(--nhs-white);
    border: 1px solid var(--nhs-pale-grey);
    border-left: 4px solid transparent;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.tc-card:hover {
    border-left-color: var(--nhs-blue);
    background: #FAFCFF;
    box-shadow: 0 1px 4px rgba(0, 48, 135, 0.08);
}
.tc-card:focus-visible {
    box-shadow: 0 0 0 3px var(--nhs-yellow);
    z-index: 1;
}
.tc-card__name {
    font-size: 14px;
    font-weight: 700;
    color: var(--nhs-dark-blue);
    line-height: 1.3;
}
.tc-card__stats {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--nhs-mid-grey);
}
.tc-card__stat {
    font-weight: 400;
    font-variant-numeric: tabular-nums;
}
.tc-card__dot {
    color: var(--nhs-pale-grey);
}
```

For indication mode (~32 buttons), switch to 4 columns:

```css
/* Use this class when chart_type == "indication" */
.tc-landing__grid--wide {
    grid-template-columns: repeat(4, 1fr);
}
```

---

## 4. Trust Comparison 6-Chart Dashboard

### Layout

2-column × 3-row grid of chart cards. Each card has a small title and a `dcc.Graph`. A sticky top bar shows the selected directorate name + back button.

```
┌─────────────────────────────────────────────────────┐
│  ← Back    RHEUMATOLOGY — Trust Comparison          │
├────────────────────────┬────────────────────────────┤
│  Market Share          │  Cost Waterfall            │
│  ┌──────────────────┐  │  ┌──────────────────────┐  │
│  │   dcc.Graph      │  │  │   dcc.Graph          │  │
│  └──────────────────┘  │  └──────────────────────┘  │
├────────────────────────┼────────────────────────────┤
│  Dosing Intervals      │  Drug × Trust Heatmap      │
│  ┌──────────────────┐  │  ┌──────────────────────┐  │
│  │   dcc.Graph      │  │  │   dcc.Graph          │  │
│  └──────────────────┘  │  └──────────────────────┘  │
├────────────────────────┼────────────────────────────┤
│  Treatment Duration    │  Cost Effectiveness        │
│  ┌──────────────────┐  │  ┌──────────────────────┐  │
│  │   dcc.Graph      │  │  │   dcc.Graph          │  │
│  └──────────────────┘  │  └──────────────────────┘  │
└────────────────────────┴────────────────────────────┘
```

### HTML Structure (Dash)

```python
html.Div(className="tc-dashboard", id="trust-comparison-dashboard", children=[
    # Dashboard header with back button
    html.Div(className="tc-dashboard__header", children=[
        html.Button("← Back", id="tc-back-btn", className="tc-dashboard__back",
                    n_clicks=0),
        html.H2(id="tc-dashboard-title", className="tc-dashboard__title",
                children="RHEUMATOLOGY — Trust Comparison"),
    ]),
    # 6-chart grid
    html.Div(className="tc-dashboard__grid", children=[
        _tc_chart_cell("Market Share", "tc-chart-market-share"),
        _tc_chart_cell("Cost Waterfall", "tc-chart-cost-waterfall"),
        _tc_chart_cell("Dosing Intervals", "tc-chart-dosing"),
        _tc_chart_cell("Drug × Trust Heatmap", "tc-chart-heatmap"),
        _tc_chart_cell("Treatment Duration", "tc-chart-duration"),
        _tc_chart_cell("Cost Effectiveness", "tc-chart-cost-effectiveness"),
    ]),
])
```

Helper for each chart cell:
```python
def _tc_chart_cell(title, graph_id):
    return html.Div(className="tc-chart-cell", children=[
        html.Div(title, className="tc-chart-cell__title"),
        dcc.Loading(type="circle", color="#005EB8", children=[
            dcc.Graph(
                id=graph_id,
                config={"displayModeBar": False, "displaylogo": False},
                style={"height": "320px"},
            ),
        ]),
    ])
```

### CSS — New Classes

```css
/* ── Trust Comparison Dashboard ── */
.tc-dashboard {
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.tc-dashboard__header {
    display: flex;
    align-items: center;
    gap: 16px;
}
.tc-dashboard__back {
    padding: 6px 12px;
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    color: var(--nhs-blue);
    background: var(--nhs-white);
    border: 1px solid var(--nhs-pale-grey);
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
}
.tc-dashboard__back:hover {
    background: #E8F0FE;
}
.tc-dashboard__back:focus-visible {
    box-shadow: 0 0 0 3px var(--nhs-yellow);
}
.tc-dashboard__title {
    font-size: 20px;
    font-weight: 700;
    color: var(--nhs-dark-blue);
}

/* 2×3 chart grid */
.tc-dashboard__grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

/* Individual chart cell */
.tc-chart-cell {
    background: var(--nhs-white);
    border: 1px solid var(--nhs-pale-grey);
    display: flex;
    flex-direction: column;
}
.tc-chart-cell__title {
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 700;
    color: var(--nhs-dark-blue);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--nhs-pale-grey);
}
```

---

## 5. Patient Pathways Filter Placement

### Approach

The drug/trust/directorate filter buttons sit in a **secondary filter strip** directly below the global sub-header. This strip is ONLY rendered when `active_view == "patient-pathways"`. It's a slimmer, lighter bar that reads as "view-specific controls" vs the sub-header's "global controls."

```
┌──────────────────────────────────────────────────────┐  ← HEADER (always)
├────────────────────────────────────────────────────── │  ← SUB-HEADER (always)
├──────────────────────────────────────────────────────┤
│  Drugs (3)  Trusts (2)  Directorates  │  Clear All  │  ← PATHWAY FILTERS (Patient Pathways only)
├──────────────────────────────────────────────────────┤
│                                                      │
│  [chart card with tabs + graph]                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

This strip uses the existing `.filter-btn` classes. It's rendered as part of the Patient Pathways view content (not fixed position) — it scrolls with the content.

### HTML Structure (Dash)

```python
# This goes inside the Patient Pathways view, at the top of its content area
html.Div(className="pathway-filters", id="pathway-filters", children=[
    html.Div(className="pathway-filters__buttons", children=[
        html.Button(children=[
            "Drugs",
            html.Span(id="drug-count-badge",
                      className="filter-btn__badge filter-btn__badge--hidden"),
        ], id="open-drug-modal", className="filter-btn", n_clicks=0),

        html.Button(children=[
            "Trusts",
            html.Span(id="trust-count-badge",
                      className="filter-btn__badge filter-btn__badge--hidden"),
        ], id="open-trust-modal", className="filter-btn", n_clicks=0),

        html.Button(children=[
            "Directorates",
            html.Span(id="directorate-count-badge",
                      className="filter-btn__badge filter-btn__badge--hidden"),
        ], id="open-directorate-modal", className="filter-btn", n_clicks=0),
    ]),
    html.Button("Clear All", id="clear-all-filters",
                className="filter-btn filter-btn--clear", n_clicks=0),
])
```

### CSS — New Classes

```css
/* ── Patient Pathways Filter Strip ── */
.pathway-filters {
    background: var(--nhs-white);
    border: 1px solid var(--nhs-pale-grey);
    border-bottom: 2px solid var(--nhs-blue);
    padding: 8px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.pathway-filters__buttons {
    display: flex;
    align-items: center;
    gap: 8px;
}
```

The bottom border `2px solid nhs-blue` gives it a subtle "active" feel that connects it visually to the chart content below.

---

## Page Structure Summary

### app.py Layout Assembly (Phase 10)

```python
app.layout = dmc.MantineProvider(children=[
    # State stores
    dcc.Store(id="app-state", storage_type="session", data={
        "chart_type": "directory",
        "initiated": "all",
        "last_seen": "6mo",
        "date_filter_id": "all_6mo",
        "selected_drugs": [],
        "selected_directorates": [],
        "selected_trusts": [],
        "active_view": "patient-pathways",
        "selected_comparison_directorate": None,
    }),
    dcc.Store(id="chart-data", storage_type="memory"),
    dcc.Store(id="reference-data", storage_type="session"),
    dcc.Store(id="active-tab", storage_type="memory", data="icicle"),
    dcc.Location(id="url", refresh=False),

    # Page structure
    make_header(),         # Fixed, 56px, dark blue
    make_sidebar(),        # Fixed, 240px left, below header
    make_sub_header(),     # Fixed, 44px, light blue, right of sidebar
    make_modals(),         # Filter modals (drug, trust, directorate)

    html.Main(className="main", children=[
        # Content switched by active_view
        html.Div(id="view-container", children=[
            # Patient Pathways view
            html.Div(id="patient-pathways-view", children=[
                make_pathway_filters(),  # Drug/trust/directorate buttons
                make_chart_card(),       # Tab bar + chart (Icicle + Sankey only)
            ]),
            # Trust Comparison view
            html.Div(id="trust-comparison-view", style={"display": "none"}, children=[
                make_tc_landing(),       # Directorate selector grid
                make_tc_dashboard(),     # 6-chart dashboard (hidden initially)
            ]),
        ]),
        make_footer(),
    ]),
])
```

### Sidebar Changes

```python
def make_sidebar():
    return html.Nav(className="sidebar", **{"aria-label": "Main navigation"}, children=[
        html.Div(className="sidebar__section", children=[
            html.Div("Analysis", className="sidebar__label"),
            _sidebar_item("Patient Pathways", "pathway",
                         active=True, item_id="nav-patient-pathways"),
            _sidebar_item("Trust Comparison", "compare",
                         active=False, item_id="nav-trust-comparison"),
        ]),
        html.Div(className="sidebar__footer", children=[
            "NHS Norfolk & Waveney ICB",
            html.Br(),
            "High Cost Drugs Programme",
        ]),
    ])
```

New icon needed for "compare":
```python
_ICONS = {
    "pathway": '<rect x="3" y="3" width="7" height="7"/>...',  # existing
    "compare": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',  # bar chart icon
}
```

### View Switching Callback

```python
@app.callback(
    Output("patient-pathways-view", "style"),
    Output("trust-comparison-view", "style"),
    Output("nav-patient-pathways", "className"),
    Output("nav-trust-comparison", "className"),
    Input("app-state", "data"),
)
def switch_view(app_state):
    view = app_state.get("active_view", "patient-pathways")
    show = {}
    hide = {"display": "none"}
    active_cls = "sidebar__item sidebar__item--active"
    inactive_cls = "sidebar__item"

    if view == "patient-pathways":
        return show, hide, active_cls, inactive_cls
    else:
        return hide, show, inactive_cls, active_cls
```

---

## CSS Variable Additions

```css
:root {
    /* ... existing ... */
    --sub-header-h: 44px;
    --header-total-h: 100px;  /* 56px header + 44px sub-header */
}
```

Update `.main`:
```css
.main {
    margin-left: var(--sidebar-w);
    margin-top: var(--header-total-h);
    padding: 24px;
    min-height: calc(100vh - var(--header-total-h));
    display: flex; flex-direction: column; gap: 20px;
}
```

---

## Responsive Adjustments

```css
@media (max-width: 1200px) {
    .tc-landing__grid { grid-template-columns: repeat(2, 1fr); }
    .tc-landing__grid--wide { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
    .sidebar { display: none; }
    .main { margin-left: 0; }
    .sub-header { left: 0; }
    .tc-landing__grid { grid-template-columns: 1fr; }
    .tc-dashboard__grid { grid-template-columns: 1fr; }
}
```
