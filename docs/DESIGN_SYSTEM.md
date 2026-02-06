# Design System - HCD Analysis v2.1 (SaaS Redesign)

This document defines the visual design language for the UI redesign. The goal is a **modern SaaS aesthetic** - think Stripe, Linear, Vercel - while staying thematically aligned with the blue color palette.

**Design Philosophy**:
- The chart is the hero; everything else supports it
- Minimal chrome, maximum data visibility
- Clean, confident, spacious - not clinical or governmental
- Every pixel of vertical space matters

## Color Palette

### Primary Blues (kept from original, used sparingly)
| Name | Hex | Usage |
|------|-----|-------|
| Heritage Blue | `#003087` | Top bar background, strong accents |
| Primary Blue | `#0066CC` | Interactive elements, links, focus |
| Vibrant Blue | `#1E88E5` | Hover states, active elements |
| Sky Blue | `#4FC3F7` | Subtle accents, progress indicators |
| Pale Blue | `#E3F2FD` | Selected states, subtle backgrounds |

### Neutrals (refined for modern feel)
| Name | Hex | Usage |
|------|-----|-------|
| Slate 900 | `#0F172A` | Primary text (slightly darker) |
| Slate 700 | `#334155` | Secondary text |
| Slate 500 | `#64748B` | Muted text, placeholders |
| Slate 300 | `#CBD5E1` | Borders, dividers |
| Slate 100 | `#F8FAFC` | Backgrounds (slightly lighter) |
| White | `#FFFFFF` | Card/modal backgrounds |

### Semantic Colors
| Name | Hex | Usage |
|------|-----|-------|
| Success | `#10B981` | Positive (modern green) |
| Warning | `#F59E0B` | Caution |
| Error | `#EF4444` | Errors |
| Info | `#3B82F6` | Informational |

## Typography

**Font Family:** Inter (primary), system-ui (fallback)

| Style | Size | Weight | Usage |
|-------|------|--------|-------|
| Display | 28px | 600 | Page titles (reduced from 32px) |
| Heading 1 | 18px | 600 | Section headers (reduced from 24px) |
| Heading 2 | 16px | 600 | Card titles (reduced from 20px) |
| Heading 3 | 14px | 600 | Subsections |
| Body | 14px | 400 | Default text |
| Body Small | 13px | 400 | Secondary info |
| Caption | 11px | 500 | Labels, metadata (reduced from 12px) |
| Mono | 13px | 500 | Data values (JetBrains Mono) |

## Spacing Scale (Tighter)

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight gaps |
| sm | 6px | Between related elements (was 8px) |
| md | 8px | Standard gaps (was 12px) |
| lg | 12px | Section padding (was 16px) |
| xl | 16px | Card padding (was 24px) |
| 2xl | 24px | Major gaps (was 32px) |
| 3xl | 32px | Page margins (was 48px) |

## Layout Specifications

### Page Structure (Target)
```
┌─────────────────────────────────────────────────────────────────┐
│ Logo │ Tabs                                     │ Freshness    │ 48px
├─────────────────────────────────────────────────────────────────┤
│ [Initiated▾] [LastSeen▾] │ [Drugs▾] [Ind▾] [Dir▾] │ KPI badges │ 48px
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        I C I C L E  C H A R T                   │ flex
│                         (full viewport width)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Top Bar
- **Height**: 48px (reduced from 64px)
- **Background**: Heritage Blue
- **Logo**: 28px height (reduced from 36px)
- **Tabs**: Small pills, 28px height

### Filter Strip
- **Height**: 48px (single row)
- **Layout**: Horizontal flex, all filters inline
- **Dropdown triggers**: 32px height, 8px padding
- **No section header** - labels are in dropdown triggers
- **Background**: Slate 100 or transparent

### KPI Section (Options)

**Option A: Inline badges** (preferred - zero extra height)
```
Filters row: [Initiated▾] [LastSeen▾] | [Drugs▾] ... | 12,345 patients • £45.2M • 89 drugs
```

**Option B: Compact strip** (48px max)
```
┌─────┬─────┬─────┬─────┐
│12.3K│£45M │ 89  │  7  │  28px value
│pts  │cost │drugs│trust│  14px label
└─────┴─────┴─────┴─────┘
```

### Chart Container
- **Width**: Full viewport minus 32px (16px padding each side)
- **Height**: Fill remaining space (min 500px)
- **No max-width constraint**
- **Margins**: Minimal (t:40, l:8, r:8, b:24)

## Component Specifications

### Compact Dropdown Trigger
- Height: 32px
- Padding: 8px 12px
- Border: 1px Slate 300
- Border radius: 6px
- Font: 13px
- Chevron: 14px icon

### Compact KPI Badge
- Padding: 4px 12px
- Border radius: 16px (pill)
- Background: Slate 100
- Value: 14px mono, weight 600
- Label: 11px, Slate 500

### Searchable Dropdown Panel
- Max height: 200px (items area)
- Item padding: 6px 8px
- Search input height: 28px
- Width: 240px min

## Shadows

| Token | Value | Usage |
|-------|-------|-------|
| sm | `0 1px 2px rgba(0,0,0,0.04)` | Subtle (lighter) |
| md | `0 1px 3px rgba(0,0,0,0.06)` | Cards at rest |
| lg | `0 4px 8px rgba(0,0,0,0.08)` | Dropdowns, hover |

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| sm | 4px | Small elements |
| md | 6px | Inputs, buttons |
| lg | 8px | Cards |
| full | 9999px | Pills, badges |

## Transitions

All transitions: 150ms ease-out (faster than before)

## Implementation Notes

### Key Changes from v2.0
1. **Vertical space reduction**: ~210px saved (364px → ~156px overhead)
2. **Full-width chart**: Remove PAGE_MAX_WIDTH for chart
3. **Inline KPIs**: Either badges in filter row or minimal strip
4. **Smaller fonts**: Headlines and captions reduced
5. **Tighter spacing**: All spacing tokens reduced by ~25%

### CSS Patterns
```css
/* Full-height chart container */
.chart-container {
  height: calc(100vh - 96px);  /* viewport minus top bar + filter strip */
  min-height: 500px;
  width: calc(100vw - 32px);
  margin: 0 16px;
}

/* Filter strip */
.filter-strip {
  display: flex;
  align-items: center;
  height: 48px;
  gap: 12px;
  padding: 0 16px;
}
```

### Dash Implementation
- Chart container uses `dcc.Loading` wrapper around `dcc.Graph`
- Full-width layout via CSS class `.chart-card` in `dash_app/assets/nhs.css`
- Minimum height set via CSS: `min-height: 500px`
- Margins controlled in `create_icicle_from_nodes()`: `t:40, l:8, r:8, b:24`
