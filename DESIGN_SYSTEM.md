# Design System - HCD Analysis v2

This document defines the visual design language for the UI redesign. All components should reference these tokens for consistency.

## Color Palette

### Primary Blues (NHS-inspired, modernized)
| Name | Hex | Usage |
|------|-----|-------|
| Heritage Blue | `#003087` | Deep headers, authoritative accents |
| Primary Blue | `#0066CC` | Main actions, links, focus states |
| Vibrant Blue | `#1E88E5` | Highlights, hover states, chart primary |
| Sky Blue | `#4FC3F7` | Accents, progress bars, secondary elements |
| Pale Blue | `#E3F2FD` | Subtle backgrounds, card tints |

### Neutrals (warm-tinted for clinical warmth)
| Name | Hex | Usage |
|------|-----|-------|
| Slate 900 | `#1E293B` | Primary text |
| Slate 700 | `#334155` | Secondary text |
| Slate 500 | `#64748B` | Muted text, placeholders |
| Slate 300 | `#CBD5E1` | Borders, dividers |
| Slate 100 | `#F1F5F9` | Card backgrounds, hover states |
| White | `#FFFFFF` | Page background |

### Semantic Colors
| Name | Hex | Usage |
|------|-----|-------|
| Success | `#059669` | Positive states, confirmations |
| Warning | `#D97706` | Caution states, alerts |
| Error | `#DC2626` | Error states, destructive actions |
| Info | `#0284C7` | Informational (matches primary family) |

### Chart Palette
```
Primary series: #003087, #0066CC, #1E88E5, #4FC3F7, #90CAF9
Categorical: #0066CC, #059669, #D97706, #8B5CF6, #EC4899
```

## Typography

**Font Family:** Inter (primary), system-ui (fallback)

| Style | Size | Weight | Tracking | Line Height | Usage |
|-------|------|--------|----------|-------------|-------|
| Display | 32px | 700 | -0.02em | 1.2 | Page titles |
| Heading 1 | 24px | 600 | -0.01em | 1.3 | Section headers |
| Heading 2 | 20px | 600 | normal | 1.4 | Card titles |
| Heading 3 | 16px | 600 | normal | 1.4 | Subsections |
| Body | 14px | 400 | normal | 1.5 | Default text |
| Body Small | 13px | 400 | normal | 1.5 | Secondary info |
| Caption | 12px | 500 | normal | 1.4 | Labels, metadata |
| Mono | 13px | 400 | normal | 1.5 | Data values, codes (JetBrains Mono) |

## Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight internal padding |
| sm | 8px | Between related elements |
| md | 12px | Standard gaps |
| lg | 16px | Section padding |
| xl | 24px | Card padding |
| 2xl | 32px | Major section gaps |
| 3xl | 48px | Page margins |

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| sm | 4px | Small elements, inputs |
| md | 8px | Buttons, small cards |
| lg | 12px | Cards, modals |
| xl | 16px | Large containers |
| full | 9999px | Pills, avatars |

## Shadows

| Token | Value | Usage |
|-------|-------|-------|
| sm | `0 1px 2px rgba(0,0,0,0.05)` | Subtle elevation |
| md | `0 1px 3px rgba(0,0,0,0.08)` | Cards at rest |
| lg | `0 4px 6px rgba(0,0,0,0.1)` | Cards on hover, dropdowns |
| xl | `0 10px 15px rgba(0,0,0,0.1)` | Modals, popovers |

## Component Specifications

### Cards
- Background: White
- Border: 1px Slate 300 (optional, or use shadow only)
- Border radius: lg (12px)
- Padding: xl (24px)
- Shadow: md at rest, lg on hover
- Hover: translateY(-2px) transition

### Buttons
**Primary:**
- Background: Primary Blue
- Text: White
- Border radius: md (8px)
- Padding: 10px 20px
- Hover: Vibrant Blue background, slight scale (1.02)

**Secondary:**
- Background: White
- Border: 1px Primary Blue
- Text: Primary Blue
- Hover: Pale Blue background

**Ghost:**
- Background: transparent
- Text: Primary Blue
- Hover: Pale Blue background

### Form Controls
- Height: 40px (inputs, selects)
- Border: 1px Slate 300
- Border radius: md (8px)
- Focus: 2px Primary Blue ring
- Placeholder: Slate 500

### Data Cards (KPIs)
- Large mono number: 32-48px, Slate 900
- Label: Caption size, Slate 500
- Background: White or Pale Blue tint
- Optional trend indicator or sparkline

## Layout

### Page Structure
```
┌─────────────────────────────────────────────────────────────────┐
│  Logo + App Name          [Chart Tabs]       Data Freshness     │  ← Top Bar (64px height)
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ Filters ─────────────────────────────────────────────────┐ │  ← Filter Section
│  │  Date ranges, dropdowns, filter controls                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─ KPIs ────────────────────────────────────────────────────┐ │  ← KPI Row
│  │  [ Metric 1 ]  [ Metric 2 ]  [ Metric 3 ]  [ Metric 4 ]   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─ Chart ───────────────────────────────────────────────────┐ │  ← Main Chart (fills remaining)
│  │                                                           │ │
│  │              [ Interactive Visualization ]                │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Responsive Breakpoints
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

## Transitions

| Property | Duration | Easing |
|----------|----------|--------|
| Color, background | 150ms | ease-out |
| Transform | 200ms | ease-out |
| Shadow | 200ms | ease-out |
| Opacity | 200ms | ease-in-out |

## Reflex Implementation Notes

### Using Design Tokens
Create a `styles.py` module with these values as Python constants. Import throughout the app:

```python
# Example structure
class Colors:
    PRIMARY = "#0066CC"
    PRIMARY_DARK = "#003087"
    # etc.

class Spacing:
    XS = "4px"
    SM = "8px"
    # etc.
```

### rx.theme Configuration
Configure Reflex's theme provider with the color palette for consistent component styling.

### Custom CSS
For styles not achievable via Reflex props, use `rx.style` or a custom CSS file.
