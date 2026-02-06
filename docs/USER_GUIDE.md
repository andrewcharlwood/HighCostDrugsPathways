# User Guide - NHS Patient Pathway Analysis Tool

This guide explains how to use the NHS High-Cost Drug Patient Pathway Analysis Tool to analyze treatment pathways for secondary care patients.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Filtering Data](#filtering-data)
4. [Using the Drug Browser](#using-the-drug-browser)
5. [Understanding the Pathway Chart](#understanding-the-pathway-chart)
6. [GP Indication Matching](#gp-indication-matching)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing the Application

Start the application by running:

```bash
python run_dash.py
```

Then open your browser to **http://localhost:8050**

The application automatically loads pre-computed pathway data from SQLite on startup. No additional setup is needed to view existing data.

### Data Freshness

The header bar shows when data was last refreshed:
- **Patient count**: Total patients in the dataset (e.g., "11,118 patients")
- **Last updated**: Relative time since the last data refresh (e.g., "2h ago")

To refresh the data, run the CLI command (requires Snowflake access):

```bash
python -m cli.refresh_pathways --chart-type all
```

---

## Interface Overview

The application is a single-page layout with the following components:

### Header
- NHS branding and application title ("HCD Analysis")
- Green status dot with patient count and last-updated time

### Sidebar (Left)
Navigation items including:
- **Pathway Overview** — main view (always active)
- **Drug Selection** — opens the drug browser drawer
- **Trust Selection** — opens the drawer with trust chips
- **Indications** — opens the drawer with directorate browser

### KPI Row
Four summary cards that update dynamically:
- **Unique Patients** — number of distinct patients matching current filters
- **Drug Types** — number of distinct drugs in filtered data
- **Total Cost** — total cost of treatments in the filtered dataset
- **Indication Match** — GP diagnosis match rate (~93% for indication charts, shown as "—" for directory charts)

### Filter Bar
- **Chart type toggle**: "By Directory" / "By Indication" pills
- **Treatment Initiated**: All years, Last 2 years, or Last 1 year
- **Last Seen**: Last 6 months or Last 12 months

### Chart Card
- Dynamic subtitle showing the current hierarchy (e.g., "Trust → Directorate → Drug → Pathway")
- Interactive Plotly icicle chart
- Loading spinner during data fetch

---

## Filtering Data

### Chart Type

Toggle between two views using the pills in the filter bar:

| View | Hierarchy | Best For |
|------|-----------|----------|
| **By Directory** | Trust → Directorate → Drug → Pathway | Understanding treatment by medical specialty |
| **By Indication** | Trust → GP Diagnosis → Drug → Pathway | Understanding treatment by patient condition |

### Date Filters

Two dropdowns control the time window:

| Filter | Options | Effect |
|--------|---------|--------|
| **Treatment Initiated** | All years, Last 2 years, Last 1 year | When patients started treatment |
| **Last Seen** | Last 6 months, Last 12 months | Most recent activity window |

The default is "All years / Last 6 months" — showing all patients who have been active in the last 6 months.

### Drug and Trust Selection

Open the drawer (right panel) by clicking "Drug Selection" or "Trust Selection" in the sidebar:

- **Drug chips**: Click to select/deselect specific drugs. Selected drugs filter the chart.
- **Trust chips**: Click to select/deselect specific NHS trusts.
- **Clear All Filters**: Button at the bottom resets all drug and trust selections.

**No selections = show everything.** Leaving chips unselected is the same as selecting all.

---

## Using the Drug Browser

The drawer contains three sections:

### All Drugs
A flat list of all 42 available drugs as selectable chips. Click one or more to filter the chart to those drugs only.

### Trusts
A list of 7 NHS trusts as selectable chips. Click to filter by specific organizations.

### By Directorate
An accordion browser organized by clinical directorate:

1. Click a **directorate** (e.g., "CARDIOLOGY") to expand it
2. Inside, click an **indication** (e.g., "heart failure") to expand further
3. Each indication shows **drug fragment badges** (e.g., "SACUBITRIL", "IVABRADINE")
4. Clicking a drug fragment badge selects all full drug names that contain that fragment

For example, clicking the "ADALIMUMAB" badge would select "ADALIMUMAB" in the drug chips above.

### Fragment Matching

Drug fragments are substrings, not exact matches. The fragment "INHALED" would match drugs like "INHALED BECLOMETASONE" and "INHALED FLUTICASONE".

Clicking a fragment toggles its matching drugs:
- **First click**: Selects all matching drugs
- **Second click**: Deselects all matching drugs (if all were already selected)

---

## Understanding the Pathway Chart

### Hierarchy Structure

The icicle chart displays a hierarchical breakdown:

**Directory view:**
```
Root (Regional Total)
  └─ Trust (e.g., "Norfolk and Norwich University Hospitals")
      └─ Directorate (e.g., "RHEUMATOLOGY")
          └─ Drug (e.g., "ADALIMUMAB")
              └─ Pathway (e.g., "ADALIMUMAB → INFLIXIMAB")
```

**Indication view:**
```
Root (Regional Total)
  └─ Trust
      └─ GP Diagnosis (e.g., "rheumatoid arthritis")
          └─ Drug
              └─ Pathway
```

### Reading the Chart

- **Width** of each section indicates relative patient count
- **Color intensity** (NHS blue gradient) indicates proportion of parent group
- **Labels** show the name and patient count

### Interacting with the Chart

| Action | Effect |
|--------|--------|
| **Click** a section | Zoom in to show details for that branch |
| **Click** the parent/root | Zoom back out |
| **Hover** over a section | See tooltip with patient count, cost, dosing frequency, dates |

### Hover Tooltip Information

When hovering over a chart section, you'll see:
- Patient count and percentage of parent
- Total cost and cost per patient
- First and last seen dates
- Treatment dosing frequency (for drug nodes)
- Cost per patient per annum

---

## GP Indication Matching

When viewing "By Indication" charts, the application uses pre-computed GP diagnosis matches:

### How It Works

1. During data refresh, each patient's NHS pseudonym is queried against GP primary care records
2. SNOMED cluster codes map clinical conditions to drug indications
3. The most recent GP diagnosis match is used for each patient
4. ~93% of patients are matched to a GP diagnosis

### Unmatched Patients

Patients without a GP diagnosis match appear under their directorate with a "(no GP dx)" suffix (e.g., "RHEUMATOLOGY (no GP dx)").

Reasons for unmatched patients:
- GP is outside the data coverage area
- Diagnosis not yet recorded in GP system
- Condition managed only in secondary care
- Off-label prescribing

---

## Troubleshooting

### No data showing

1. Check the filter bar — are filters too restrictive?
2. Try clearing all drug/trust selections in the drawer
3. Widen the date range (e.g., "All years / Last 12 months")

### Chart shows "No matching pathways found"

The current filter combination matches zero patients. Adjust filters or click "Clear All Filters" in the drawer.

### App won't start

```bash
# Ensure dependencies are installed
uv sync

# Ensure src/ is on Python path
uv run python setup_dev.py

# Run with uv
uv run python run_dash.py
```

### Stale data

Data is as fresh as the last CLI refresh. Check the header's "Last updated" indicator. To refresh:

```bash
python -m cli.refresh_pathways --chart-type all
```

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [README](../README.md) for installation and setup
2. Review [DEPLOYMENT.md](./DEPLOYMENT.md) for server configuration
3. Consult [CLAUDE.md](../CLAUDE.md) for technical architecture details
4. Contact the Medicines Intelligence team for NHS-specific questions
