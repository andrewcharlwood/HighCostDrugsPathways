# User Guide - NHS Patient Pathway Analysis Tool

This guide explains how to use the NHS High-Cost Drug Patient Pathway Analysis Tool to analyze treatment pathways for secondary care patients.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Selecting Your Data Source](#selecting-your-data-source)
4. [Configuring Analysis Filters](#configuring-analysis-filters)
5. [Selecting Drugs, Trusts, and Directories](#selecting-drugs-trusts-and-directories)
6. [Running the Analysis](#running-the-analysis)
7. [Understanding the Pathway Chart](#understanding-the-pathway-chart)
8. [Exporting Results](#exporting-results)
9. [GP Indication Validation](#gp-indication-validation)
10. [Keyboard Navigation and Accessibility](#keyboard-navigation-and-accessibility)
11. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing the Application

Start the application by running:

```bash
reflex run
```

Then open your browser to **http://localhost:3000**

The application will automatically load reference data (drugs, trusts, directories) when you first access it.

### First-Time Setup

1. Click **Load Reference Data** on the Home page to populate the filter options
2. Select your preferred data source (SQLite, File Upload, or Snowflake)
3. Configure your date range and other filters
4. Click **Run Analysis** to generate your first pathway chart

---

## Interface Overview

The application has four main pages, accessible from the sidebar navigation:

| Page | Purpose |
|------|---------|
| **Home** | Main analysis dashboard with data source selection, filters, and chart display |
| **Drug Selection** | Select which high-cost drugs to include in the analysis |
| **Trust Selection** | Filter by specific NHS trusts |
| **Directory Selection** | Filter by medical directories/specialties |

### Navigation

- **Desktop**: Use the sidebar on the left to switch between pages
- **Mobile**: Use the top navigation bar
- **Keyboard**: Press Tab to navigate, Enter to select

---

## Selecting Your Data Source

The application supports three data sources:

### 1. SQLite Database (Recommended)

Pre-loaded patient data stored locally for fast performance.

**Advantages:**
- Fastest analysis performance
- Works offline
- No authentication required

**To use:** Click "Use SQLite" in the Data Source section

### 2. File Upload

Upload CSV or Parquet files directly.

**Supported formats:**
- CSV files (.csv)
- Apache Parquet files (.parquet, .pq)

**To use:**
1. Drag and drop a file, or click the upload area
2. Wait for the file to process
3. Click "Use File" to select it as your data source

### 3. Snowflake

Query live data from the NHS data warehouse.

**Requirements:**
- Snowflake must be configured (see `config/snowflake.toml`)
- Browser-based NHS SSO authentication

**To use:** Click "Use Snowflake" - you'll be prompted to authenticate via your browser

---

## Configuring Analysis Filters

The Home page provides several filter options:

### Date Range

| Field | Description |
|-------|-------------|
| **Start Date** | Include patients initiated from this date onwards |
| **End Date** | Include patients initiated until this date |
| **Last Seen After** | Only include patients with activity after this date (excludes patients who haven't been seen recently) |

**Tip:** The default range is the last 12 months.

### Minimum Patients

Filter out pathways with fewer patients than the threshold you set.

- Use the slider for quick adjustment (0-100)
- Or type a specific number in the text field
- Set to 0 to show all pathways regardless of patient count

### Custom Title

Override the automatically generated chart title with your own text.

- Leave empty to use the default title: "Patients initiated [start date] to [end date]"
- Useful for specific reports or presentations

---

## Selecting Drugs, Trusts, and Directories

Each selection page works the same way:

### Navigation

1. Click "Drug Selection", "Trust Selection", or "Directory Selection" in the sidebar
2. The page shows all available options with checkboxes

### Search

Type in the search box to filter the list. The list updates as you type.

### Selection Actions

| Button | Action |
|--------|--------|
| **Select All** | Check all visible items |
| **Clear All** | Uncheck all items |
| **Select Defaults** | (Drugs only) Select pre-configured default drugs (Include=1 in include.csv) |

### Selection Behavior

- **No items selected** = Include ALL items in analysis
- **Some items selected** = Include ONLY the selected items

This means leaving a filter empty is equivalent to "select all".

---

## Running the Analysis

### Steps

1. Ensure your data source is selected and configured
2. Set your date range and other filters
3. Select desired drugs, trusts, and directories (or leave empty for all)
4. Click the green **Run Analysis** button

### During Analysis

- The button shows a spinner while analysis is running
- Status messages appear below the button
- The interface remains responsive - you can review settings

### After Analysis

- The pathway chart appears in the chart section
- Export buttons become available
- GP indication validation results appear (if Snowflake is connected)

---

## Understanding the Pathway Chart

The analysis generates an interactive **icicle chart** showing patient treatment pathways.

### Hierarchy Structure

The chart displays a hierarchical structure:

```
N&WICS (Regional Total)
  └─ Trust Name (e.g., "Norfolk and Norwich University Hospitals")
      └─ Directory (e.g., "Rheumatology", "Gastroenterology")
          └─ Drug Name (e.g., "ADALIMUMAB", "INFLIXIMAB")
```

### Reading the Chart

- **Width** of each section indicates relative patient count
- **Color intensity** indicates proportion of patients at that level
- **Labels** show the category name and patient count

### Interacting with the Chart

| Action | Effect |
|--------|--------|
| **Click** a section | Zoom in to show details for that branch |
| **Click** the root | Zoom out to show full hierarchy |
| **Hover** over a section | See tooltip with patient count |
| Use the **toolbar** | Reset, download image, pan, zoom |

### Plotly Toolbar

The chart includes a Plotly toolbar (top right) with:

- **Download as PNG** - Save static image
- **Zoom controls** - Zoom in/out
- **Pan** - Click and drag to move
- **Reset** - Return to original view

---

## Exporting Results

Two export options are available after running an analysis:

### Export HTML

Creates an interactive HTML file that can be opened in any browser.

- **Output**: `data/exports/pathway_chart_[timestamp].html`
- **Use case**: Sharing interactive charts via email or file share
- **Features**: Full interactivity, no software required to view

### Export CSV

Exports the underlying data as a spreadsheet.

- **Output**: `data/exports/pathway_data_[timestamp].csv`
- **Use case**: Further analysis in Excel, importing to other tools
- **Includes**: Patient IDs, drugs, dates, costs, directories, indication validation status

### Export Location

All exports are saved to the `data/exports/` directory with timestamped filenames to prevent overwriting.

---

## GP Indication Validation

When connected to Snowflake, the application validates whether patients have appropriate GP diagnoses for their prescribed drugs.

### What It Does

1. Looks up the drug's licensed indications (e.g., ADALIMUMAB for rheumatoid arthritis)
2. Finds corresponding SNOMED codes for those indications
3. Checks each patient's GP records for matching diagnoses
4. Reports the match rate per drug

### Understanding Results

After analysis, a table shows:

| Column | Meaning |
|--------|---------|
| **Drug Name** | The high-cost drug |
| **Total Patients** | Number of patients prescribed this drug |
| **With GP Indication** | Patients with matching GP diagnosis |
| **Match Rate** | Percentage with valid indication |

### Match Rate Interpretation

| Rate | Meaning | Color |
|------|---------|-------|
| **80%+** | Good coverage - most patients have GP diagnoses | Green |
| **50-79%** | Moderate coverage - investigate missing cases | Orange |
| **<50%** | Low coverage - may indicate data quality issues or off-label use | Red |

### Why Rates May Be Low

Low match rates don't necessarily indicate problems:

- **Cross-provider treatment**: Patient's GP is outside the data coverage
- **Recent diagnoses**: Diagnosis not yet recorded in GP system
- **Specialist-only conditions**: Some conditions are only managed in secondary care
- **Off-label prescribing**: Legitimate use for indications not in the mapping

### Enabling/Disabling

Indication validation is enabled by default when Snowflake is connected. It requires:
- Active Snowflake connection
- Drug-to-cluster mappings in the database

---

## Keyboard Navigation and Accessibility

The application is designed to be accessible:

### Skip Link

Press **Tab** when the page loads to reveal a "Skip to main content" link that bypasses navigation.

### Keyboard Navigation

| Key | Action |
|-----|--------|
| **Tab** | Move to next interactive element |
| **Shift+Tab** | Move to previous element |
| **Enter** | Activate buttons, links, checkboxes |
| **Space** | Toggle checkboxes |
| **Arrow keys** | Adjust sliders |

### Screen Reader Support

- All buttons and inputs have descriptive labels
- Status messages announce via ARIA live regions
- Charts include figure descriptions

### Theme Toggle

A dark/light mode toggle is available at the bottom of the sidebar for visual preference.

---

## Troubleshooting

### "No data available" Error

**Cause**: No data matches your current filter settings

**Solutions:**
1. Check your date range - is it too narrow?
2. Verify your data source has data loaded
3. Check if selected trusts/drugs have any matching records
4. Try clearing all selections (to include everything)

### Chart Not Displaying

**Cause**: Analysis completed but no data met the minimum patients threshold

**Solutions:**
1. Lower the minimum patients threshold
2. Expand your date range
3. Select more drugs or trusts

### Snowflake Connection Failed

**Cause**: Unable to connect to Snowflake

**Solutions:**
1. Check that `config/snowflake.toml` exists and is configured
2. Complete browser authentication when prompted
3. Verify your network allows Snowflake connections
4. Try using SQLite as an alternative data source

### File Upload Failed

**Cause**: File format or content issue

**Solutions:**
1. Ensure file is CSV or Parquet format
2. Check file isn't corrupted or empty
3. Verify file contains required columns
4. Try a smaller file to test

### Slow Performance

**Cause**: Large data volume or complex filtering

**Solutions:**
1. Use SQLite instead of file upload for large datasets
2. Narrow your date range
3. Select fewer drugs/trusts to analyze
4. Increase minimum patients threshold to reduce chart complexity

### Reference Data Not Loading

**Cause**: Missing or corrupted reference files

**Solutions:**
1. Click "Load Reference Data" to retry
2. Check that `data/` directory contains required CSV files:
   - `include.csv`
   - `defaultTrusts.csv`
   - `directory_list.csv`
3. Verify files aren't empty or malformed

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [README](../README.md) for installation and setup information
2. Review [DEPLOYMENT.md](./DEPLOYMENT.md) for server configuration
3. Consult [CLAUDE.md](../CLAUDE.md) for technical architecture details
4. Contact your local support team for NHS-specific questions
