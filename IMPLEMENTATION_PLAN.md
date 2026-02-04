# Implementation Plan - HCD Analysis UI Redesign

## Project Overview

Complete frontend redesign of the Patient Pathway Analysis tool. Replace the current multi-page sidebar layout with a modern, single-page dashboard featuring:
- Instant reactive filtering with debounce
- Interactive Plotly icicle chart that updates in real-time
- NHS-inspired but bold, modern visual design
- KPI metrics that respond to filter changes

**Design Reference:** See `DESIGN_SYSTEM.md` for color palette, typography, spacing, and component specs.

**Source Code:** The existing `pathways_app/pathways_app.py` contains the current implementation. Create a new `pathways_app/app_v2.py` for the redesign, leaving the original intact until verification.

## Quality Checks

Run after each task:

```bash
# Syntax check
python -m py_compile pathways_app/app_v2.py

# Import verification
python -c "from pathways_app.app_v2 import app"

# Reflex compilation test
cd pathways_app && timeout 60 python -m reflex run 2>&1 | head -30

# If compilation shows errors, fix before marking task complete
```

## Phase 1: Foundation

### 1.1 Design Tokens Module
- [ ] Create `pathways_app/styles.py` with design token classes:
  - `Colors` class with all palette colors as constants
  - `Typography` class with font sizes, weights
  - `Spacing` class with spacing scale
  - `Shadows` class with shadow values
  - `Radii` class with border radius values
- [ ] Create helper functions for common style patterns (e.g., `card_style()`, `button_primary_style()`)
- [ ] Verify imports work: `from pathways_app.styles import Colors, Spacing`

### 1.2 App Skeleton
- [ ] Create `pathways_app/app_v2.py` with basic Reflex app structure
- [ ] Define new `AppState` class with minimal state (placeholder for now)
- [ ] Create single-page layout structure matching DESIGN_SYSTEM.md
- [ ] Verify `reflex run` compiles and shows blank page with correct structure
- [ ] Configure Reflex theme with design system colors

## Phase 2: Layout Components

### 2.1 Top Navigation Bar
- [ ] Create `top_bar()` component:
  - Logo (use existing NHS person logo from assets)
  - App title "HCD Analysis"
  - Chart type tabs/pills (Icicle active, placeholders for future charts)
  - Data freshness indicator (right side): "12,450 records (2d ago)"
- [ ] Style with Heritage Blue accents, clean typography
- [ ] Fixed height: 64px
- [ ] Verify renders correctly

### 2.2 Filter Section
- [ ] Create `filter_section()` component with card styling
- [ ] Add date range pickers:
  - "Initiated" range with enable/disable checkbox (default: disabled)
  - "Last Seen" range with enable/disable checkbox (default: enabled, last 6 months)
  - "To" date defaults to latest date in dataset
- [ ] Add searchable multi-select dropdowns:
  - Drugs dropdown with search, select all, count display
  - Indications dropdown with search, select all, count display
  - Directorates dropdown with search, select all, count display
- [ ] Implement debounced filter change handlers (300ms)
- [ ] Style according to design system

### 2.3 KPI Row
- [ ] Create `kpi_card()` component:
  - Large mono number (32-48px)
  - Label below (caption style)
  - Subtle background tint
- [ ] Create `kpi_row()` component with responsive grid
- [ ] Initially show: Unique Patients count
- [ ] Leave space for future metrics (Drugs count, Total cost, Match rate)
- [ ] KPIs should be reactive to filter state

### 2.4 Chart Container
- [ ] Create `chart_section()` component
- [ ] Full-width card with appropriate padding
- [ ] Placeholder for Plotly chart (integrate in Phase 3)
- [ ] Loading state with skeleton/spinner
- [ ] Error state with friendly message

## Phase 3: State Management

### 3.1 Core State Variables
- [ ] Define filter state variables in `AppState`:
  - `initiated_filter_enabled: bool = False`
  - `initiated_from: datetime`
  - `initiated_to: datetime`
  - `last_seen_filter_enabled: bool = True`
  - `last_seen_from: datetime` (default: 6 months ago)
  - `last_seen_to: datetime` (default: latest in dataset)
  - `selected_drugs: List[str]` (default: all)
  - `selected_indications: List[str]` (default: all)
  - `selected_directorates: List[str]` (default: all)
- [ ] Define data state variables:
  - `data_loaded: bool`
  - `total_records: int`
  - `last_updated: datetime`
  - `filtered_data: pd.DataFrame` (or computed)
- [ ] Define UI state variables:
  - `chart_loading: bool`
  - `error_message: str`

### 3.2 Data Loading
- [ ] Create `load_data()` method that reads from SQLite
- [ ] Populate available options for dropdowns (drugs, indications, directorates)
- [ ] Detect latest date in dataset for "to" date defaults
- [ ] Calculate total records and last updated timestamp
- [ ] Call on app initialization

### 3.3 Filter Logic
- [ ] Create `apply_filters()` computed method that filters the data based on current state
- [ ] Handle initiated date filter (when enabled)
- [ ] Handle last seen date filter (when enabled)
- [ ] Handle drug/indication/directorate multi-select filters
- [ ] Return filtered DataFrame

### 3.4 KPI Calculations
- [ ] Create computed properties for KPI values:
  - `unique_patients: int` — COUNT(DISTINCT patient_id) from filtered data
  - (Future: drug count, total cost, indication match rate)
- [ ] Ensure KPIs update reactively when filters change

## Phase 4: Interactive Chart

### 4.1 Chart Data Preparation
- [ ] Create `prepare_chart_data()` method that transforms filtered data for Plotly icicle
- [ ] Reuse/adapt logic from existing `pathway_analyzer.py`
- [ ] Return data structure compatible with `plotly.express.icicle()`

### 4.2 Reactive Plotly Integration
- [ ] Create `generate_icicle_chart()` computed property that returns Plotly figure
- [ ] Configure chart colors using design system palette
- [ ] Configure chart interactivity (zoom, pan, click, hover)
- [ ] Set responsive sizing

### 4.3 Chart Component
- [ ] Integrate `rx.plotly()` component in chart_section
- [ ] Pass reactive figure from state
- [ ] Handle loading states (show skeleton while computing)
- [ ] Handle empty data state (friendly message)
- [ ] Verify chart updates when filters change

## Phase 5: Polish & Verification

### 5.1 Visual Polish
- [ ] Review all components against DESIGN_SYSTEM.md
- [ ] Ensure consistent spacing throughout
- [ ] Ensure consistent typography throughout
- [ ] Add hover states and transitions to interactive elements
- [ ] Test responsive behavior (resize browser)

### 5.2 Performance Optimization
- [ ] Profile filter + chart update cycle
- [ ] Ensure debounce is working correctly (not triggering on every keystroke)
- [ ] Optimize any slow computed properties
- [ ] Verify smooth 60fps interactions

### 5.3 Error Handling
- [ ] Handle no data loaded state gracefully
- [ ] Handle filter resulting in zero records
- [ ] Handle any data loading errors
- [ ] User-friendly error messages

### 5.4 Final Verification
- [ ] Load real data from SQLite
- [ ] Test all filter combinations
- [ ] Verify KPIs update correctly
- [ ] Verify chart updates correctly
- [ ] Compare key metrics with original app to ensure correctness
- [ ] Test with large dataset for performance

### 5.5 Cleanup
- [ ] Remove or comment out old `pathways_app.py` code paths
- [ ] Update any imports/references to use new app
- [ ] Update README with new run instructions
- [ ] Document any breaking changes

## Completion Criteria

All tasks marked `[x]` AND:
- [ ] App compiles without errors (`reflex run` succeeds)
- [ ] All filters work with instant (debounced) updates
- [ ] KPIs display correct numbers matching filter state
- [ ] Icicle chart renders and updates reactively
- [ ] Visual design matches DESIGN_SYSTEM.md
- [ ] No console errors during normal operation
- [ ] Verified with real patient data from SQLite
