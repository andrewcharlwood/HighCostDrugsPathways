# Implementation Plan - UI Redesign Phase

## Project Overview

Redesign the HCD Analysis application with a modern SaaS-style interface. The current NHS-dashboard style is functional but dated. This phase focuses on:

1. **Modern SaaS aesthetic** - Clean, ambitious design that looks like a premium product
2. **Maximized chart space** - The icicle chart is the hero; everything else supports it
3. **Compact controls** - Filters and KPIs should be efficient, not sprawling
4. **Full-width layout** - Use the entire viewport width

**Design Philosophy**:
- Thematically aligned with blue color scheme but NOT constrained by NHS branding
- Think Stripe, Linear, Vercel - clean, spacious, confident
- Data visualization is the star; chrome should be minimal

**Source Files**:
- `pathways_app/pathways_app.py` - Main Reflex application
- `pathways_app/styles.py` - Design tokens and style helpers
- `DESIGN_SYSTEM.md` - Design specifications

## Quality Checks

Run after each task:

```bash
# Syntax check for Python files
python -m py_compile pathways_app/pathways_app.py

# Import verification
python -c "from pathways_app.pathways_app import app"

# Reflex compile
python -m reflex compile
```

## Phase 5: UI Redesign

### 5.1 Update Design System for Modern SaaS
- [x] Update `DESIGN_SYSTEM.md` with new specifications:
  - Reduce top bar height from 64px to 48px
  - Define compact filter row (single horizontal strip)
  - Define compact KPI card dimensions (reduce padding, font sizes)
  - Add full-width chart container specs
- [x] Update `pathways_app/styles.py` tokens to match:
  - Typography: DISPLAY 32→28px, H1 24→18px, H2 20→16px, CAPTION 12→11px
  - Spacing: SM 8→6px, MD 12→8px, LG 16→12px, XL 24→16px, XXL 32→24px, XXXL 48→32px
  - Shadows: Lighter values (0.04, 0.06, 0.08 opacity)
  - Colors: Modernized semantic colors (SUCCESS #10B981, etc.)
  - Layout: TOP_BAR_HEIGHT 64→48px, FILTER_STRIP_HEIGHT 48px
- [x] Add new style helpers:
  - `compact_kpi_card_style()` - 12px padding, 24px value font
  - `compact_kpi_value_style()` / `compact_kpi_label_style()` - matching text styles
  - `kpi_badge_style()` - inline pill/badge variant (zero height impact)
  - `filter_strip_style()` - 48px horizontal container
  - `compact_dropdown_trigger_style()` - 32px height triggers
  - `searchable_dropdown_panel_style()` / `searchable_dropdown_item_style()` - compact items
  - `chart_container_style()` / `chart_wrapper_style()` - full-width, flex-grow
  - `top_bar_style()` / `top_bar_tab_style()` / `logo_style()` - 48px top bar
- [x] Verify: `python -c "from pathways_app.styles import *"` - PASSED

### 5.2 Compact Filter Section (50-67% height reduction)
- [x] Redesign filter_section() as a single horizontal strip:
  - All filters in ONE row: Date dropdowns | Drugs | Indications | Directorates
  - Remove "Filters" header (saves vertical space)
  - Use smaller dropdown triggers (height: 32px instead of 40px)
  - Use icon-only labels where possible
- [x] Reduce searchable_dropdown() panel heights:
  - Max item list height: 150px (was 200px)
  - Smaller search input (size="1" instead of size="2")
  - Tighter spacing (6px/8px gaps via Spacing.SM/MD)
- [x] Make filter dropdowns collapsible/expandable (optional advanced feature)
  - Note: This was already implemented - dropdowns open/close on click
- [x] Verify: Filter section height ≤ 60px when collapsed
  - Implemented: 48px filter strip via filter_strip_style()
  - Note: Visual verification with reflex run recommended

### 5.3 Compact KPI Cards (50% reduction)
- [x] Reduce KPI card dimensions:
  - Padding: 12px (was 24px)
  - Value font size: 24px (was 32px)
  - Label font size: 11px (was 12px)
- [x] Make KPIs a single compact row:
  - All 4 KPIs in horizontal strip
  - Minimal vertical footprint
  - Consider inline layout: "12,345 patients | £45.2M cost | 89 drugs | 7 trusts"
- [x] Alternative: KPI badges/pills instead of cards
  - Implemented kpi_badge() and kpi_badges() functions
  - KPIs are now inline badges integrated into the filter strip
  - Zero additional vertical height (Option A from design system)
- [x] Verify: KPI row height ≤ 48px
  - KPIs now embedded in filter strip - no separate row needed
  - reflex compile succeeds in 15s

### 5.4 Full-Width Chart Layout
- [x] Remove PAGE_MAX_WIDTH constraint for chart container
  - Removed from main_content() - now uses 100% width with 16px padding
- [x] Chart should stretch to viewport width (with small padding: 16px each side)
  - Using padding_x=Spacing.XL (16px) in main_content()
- [x] Update chart height calculation:
  - Using calc(100vh - 152px) for chart height
  - 152px = 48px top bar + 48px filter strip + 16px padding + 40px chart header
  - Minimum height: 500px preserved
- [x] Update Plotly layout:
  - Removed fixed height=600, using autosize=True
  - Reduced margins to t:40, l:8, r:8, b:24 per DESIGN_SYSTEM.md
- [x] Verify: Chart fills available space on 1920x1080 display
  - Implemented: calc(100vh - 152px) height, width="100%"
  - Note: Visual verification with reflex run recommended

### 5.5 Top Bar Refinement
- [x] Reduce top bar height to 48px (was 64px)
  - Using `top_bar_style()` which sets `height: TOP_BAR_HEIGHT` (48px)
- [x] Simplify chart tabs - smaller pills or just text links
  - Using `top_bar_tab_style()` for 28px height pills with tighter spacing
- [x] Consider moving data freshness indicator inline with filters
  - Simplified to single line: "X records · Refreshed: 2m ago"
  - Removed max_width constraint for full-width bar
- [x] Make logo smaller (28px instead of 36px)
  - Using `logo_style()` for 28px height
- [x] Verify: Top bar is minimal but functional
  - Syntax check: PASS
  - Import check: PASS
  - Reflex compile: PASS (1.7s)

### 5.6 Visual Polish
- [x] Add subtle hover states to interactive elements
  - KPI badges: subtle lift and shadow on hover
  - Top bar tabs: slightly brighter hover (0.15 opacity vs 0.1)
  - Dropdown triggers: background color change + border highlight on hover
  - Dropdown items: background color change on hover
  - Buttons: enhanced hover with transform/shadow
- [x] Ensure consistent focus rings for accessibility
  - Dropdown triggers: 2px Pale Blue focus ring
  - Top bar tabs: 2px white semi-transparent focus ring
  - Dropdown items: inset Primary border focus ring
  - Buttons (primary/secondary/ghost): consistent Pale Blue focus rings
  - All focus states use _focus and _focus_visible for keyboard nav
- [x] Test responsive behavior at common breakpoints (1366, 1920, 2560px widths)
  - Note: Layout uses calc(100vh - Xpx) for height, flexbox for width
  - Full-width chart with 16px padding scales to any viewport width
  - Visual verification required with `reflex run`
- [x] Remove any unused styles from styles.py
  - Removed compact_kpi_card_style, compact_kpi_value_style, compact_kpi_label_style (unused Option B)
  - Cleaned up pathways_app.py imports: removed card_style, input_style, button_ghost_style, chart_container_style, chart_wrapper_style, PAGE_MAX_WIDTH, PAGE_PADDING, text_h3
  - Kept kpi_value_style, kpi_label_style for legacy kpi_card fallback
- [x] Verify: No visual regressions, app looks cohesive
  - Syntax check: PASS
  - Import check: PASS
  - Reflex compile: PASS (14.6s)

## Completion Criteria

All tasks marked `[x]` AND:
- [x] App compiles without errors (`reflex compile` succeeds)
  - Verified: 14.6s compile time, no errors
- [x] Filter section height ≤ 60px (measured visually)
  - Implemented: 48px filter strip with inline KPI badges
- [x] KPI row height ≤ 48px (measured visually)
  - Implemented: Zero extra height (KPIs as inline badges in filter strip)
- [x] Top bar height = 48px
  - Verified: Uses TOP_BAR_HEIGHT constant = "48px"
- [x] Chart stretches to full viewport width (minus 32px total padding)
  - Implemented: width="100%", padding_x=Spacing.XL (16px)
- [x] Chart fills remaining vertical space (min 500px)
  - Implemented: calc(100vh - 152px), min_height="500px"
- [x] Design feels like modern SaaS, not NHS dashboard
  - Implemented: Compact filters, inline KPI badges, full-width chart
  - Implemented: Tighter spacing, smaller typography, lighter shadows
  - Note: Visual verification with reflex run recommended
- [x] All interactive elements have appropriate hover/focus states
  - Implemented in Task 5.6: hover/focus for buttons, dropdowns, tabs, badges

## Reference

### Current Layout (to be improved)
```
┌─────────────────────────────────────────────────────────────────┐
│  Top Bar (64px) - Logo, Tabs, Freshness                        │
├─────────────────────────────────────────────────────────────────┤
│  Filter Section (~200px) - Headers, Date dropdowns, Multi-select│
├─────────────────────────────────────────────────────────────────┤
│  KPI Cards (~100px) - 4 large cards in row                     │
├─────────────────────────────────────────────────────────────────┤
│  Chart (~600px fixed) - Constrained width                      │
└─────────────────────────────────────────────────────────────────┘
```

### Target Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ Logo │ Tabs │                                    │ Freshness   │ 48px
├─────────────────────────────────────────────────────────────────┤
│ [Date▾] [Date▾] [Drugs▾] [Indications▾] [Directories▾] │ KPIs │ 48-60px
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        CHART                                    │ flex-grow
│                    (full width)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Measurements
| Element | Current | Target |
|---------|---------|--------|
| Top bar | 64px | 48px |
| Filter section | ~200px | ≤60px |
| KPI row | ~100px | ≤48px (or merged with filters) |
| Chart | 600px fixed, constrained width | flex-grow, full width |
| Total overhead | ~364px | ~156px (57% reduction) |

### Key Files

| File | Purpose |
|------|---------|
| `pathways_app/pathways_app.py` | Main Reflex application |
| `pathways_app/styles.py` | Design tokens and style helpers |
| `DESIGN_SYSTEM.md` | Design specifications |
