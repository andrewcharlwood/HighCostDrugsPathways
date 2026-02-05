"""
Design tokens and style helpers for HCD Analysis v2.1 (SaaS Redesign).

All visual styling should use these tokens for consistency.
Import: from pathways_app.styles import Colors, Spacing, Typography, etc.

Updated to match DESIGN_SYSTEM.md v2.1 with:
- Tighter spacing (25% reduction)
- Smaller typography (reduced headline sizes)
- Compact component variants for filters/KPIs
- Full-width chart support
"""


class Colors:
    """Color palette from DESIGN_SYSTEM.md"""

    # Primary Blues (NHS-inspired, used sparingly)
    HERITAGE_BLUE = "#003087"  # Top bar background, strong accents
    PRIMARY = "#0066CC"        # Interactive elements, links, focus states
    VIBRANT = "#1E88E5"        # Hover states, active elements
    SKY = "#4FC3F7"            # Subtle accents, progress indicators
    PALE = "#E3F2FD"           # Selected states, subtle backgrounds

    # Neutrals (refined for modern feel)
    SLATE_900 = "#0F172A"      # Primary text (slightly darker)
    SLATE_700 = "#334155"      # Secondary text
    SLATE_500 = "#64748B"      # Muted text, placeholders
    SLATE_300 = "#CBD5E1"      # Borders, dividers
    SLATE_100 = "#F8FAFC"      # Backgrounds (slightly lighter)
    WHITE = "#FFFFFF"          # Card/modal backgrounds

    # Semantic Colors (modernized)
    SUCCESS = "#10B981"        # Positive (modern green)
    WARNING = "#F59E0B"        # Caution
    ERROR = "#EF4444"          # Errors
    INFO = "#3B82F6"           # Informational

    # Chart Palette
    CHART_SERIES = ["#003087", "#0066CC", "#1E88E5", "#4FC3F7", "#90CAF9"]
    CHART_CATEGORICAL = ["#0066CC", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899"]


class Typography:
    """Typography tokens from DESIGN_SYSTEM.md v2.1 - REDUCED sizes"""

    # Font families
    FONT_FAMILY = "Inter, system-ui, -apple-system, sans-serif"
    FONT_MONO = "JetBrains Mono, monospace"

    # Display: Page titles (REDUCED from 32px)
    DISPLAY_SIZE = "28px"
    DISPLAY_WEIGHT = "600"
    DISPLAY_TRACKING = "-0.02em"
    DISPLAY_LINE_HEIGHT = "1.2"

    # Heading 1: Section headers (REDUCED from 24px)
    H1_SIZE = "18px"
    H1_WEIGHT = "600"
    H1_TRACKING = "-0.01em"
    H1_LINE_HEIGHT = "1.3"

    # Heading 2: Card titles (REDUCED from 20px)
    H2_SIZE = "16px"
    H2_WEIGHT = "600"
    H2_TRACKING = "normal"
    H2_LINE_HEIGHT = "1.4"

    # Heading 3: Subsections
    H3_SIZE = "14px"
    H3_WEIGHT = "600"
    H3_TRACKING = "normal"
    H3_LINE_HEIGHT = "1.4"

    # Body: Default text
    BODY_SIZE = "14px"
    BODY_WEIGHT = "400"
    BODY_LINE_HEIGHT = "1.5"

    # Body Small: Secondary info
    BODY_SMALL_SIZE = "13px"
    BODY_SMALL_WEIGHT = "400"
    BODY_SMALL_LINE_HEIGHT = "1.5"

    # Caption: Labels, metadata (REDUCED from 12px)
    CAPTION_SIZE = "11px"
    CAPTION_WEIGHT = "500"
    CAPTION_LINE_HEIGHT = "1.4"

    # Mono: Data values, codes
    MONO_SIZE = "13px"
    MONO_WEIGHT = "500"
    MONO_LINE_HEIGHT = "1.5"


class Spacing:
    """Spacing scale from DESIGN_SYSTEM.md v2.1 - TIGHTER values (~25% reduction)"""

    XS = "4px"    # Tight gaps
    SM = "6px"    # Between related elements (was 8px)
    MD = "8px"    # Standard gaps (was 12px)
    LG = "12px"   # Section padding (was 16px)
    XL = "16px"   # Card padding (was 24px)
    XXL = "24px"  # Major gaps (was 32px)
    XXXL = "32px" # Page margins (was 48px)


class Radii:
    """Border radius values from DESIGN_SYSTEM.md"""

    SM = "4px"      # Small elements
    MD = "6px"      # Inputs, buttons
    LG = "8px"      # Cards
    XL = "16px"     # Large containers
    FULL = "9999px" # Pills, badges


class Shadows:
    """Shadow values from DESIGN_SYSTEM.md v2.1 - LIGHTER values"""

    SM = "0 1px 2px rgba(0,0,0,0.04)"    # Subtle (lighter)
    MD = "0 1px 3px rgba(0,0,0,0.06)"    # Cards at rest
    LG = "0 4px 8px rgba(0,0,0,0.08)"    # Dropdowns, hover
    XL = "0 10px 15px rgba(0,0,0,0.1)"   # Modals, popovers


class Transitions:
    """Transition values from DESIGN_SYSTEM.md v2.1 - FASTER (150ms)"""

    DEFAULT = "150ms ease-out"
    COLOR = "150ms ease-out"
    TRANSFORM = "150ms ease-out"
    SHADOW = "150ms ease-out"
    OPACITY = "150ms ease-in-out"


# ==============================================================================
# Layout constants - UPDATED for SaaS redesign
# ==============================================================================

TOP_BAR_HEIGHT = "48px"      # Reduced from 64px
FILTER_STRIP_HEIGHT = "48px" # Single row filter strip
PAGE_MAX_WIDTH = "1600px"    # Keep for content areas (not chart)
PAGE_PADDING = Spacing.XXXL  # 32px


# ==============================================================================
# Helper functions for common style patterns
# ==============================================================================

def card_style(hoverable: bool = False) -> dict:
    """
    Card styling following DESIGN_SYSTEM.md specifications.

    - Background: White
    - Border: 1px Slate 300
    - Border radius: lg (8px)
    - Padding: xl (16px - reduced)
    - Shadow: md at rest, lg on hover
    """
    base_style = {
        "background_color": Colors.WHITE,
        "border": f"1px solid {Colors.SLATE_300}",
        "border_radius": Radii.LG,
        "padding": Spacing.XL,
        "box_shadow": Shadows.MD,
    }

    if hoverable:
        base_style.update({
            "transition": f"box-shadow {Transitions.SHADOW}, transform {Transitions.TRANSFORM}",
            "_hover": {
                "box_shadow": Shadows.LG,
                "transform": "translateY(-2px)",
            }
        })

    return base_style


def button_primary_style() -> dict:
    """
    Primary button styling following DESIGN_SYSTEM.md specifications.
    Includes accessible focus ring.
    """
    return {
        "background_color": Colors.PRIMARY,
        "color": Colors.WHITE,
        "border_radius": Radii.MD,
        "padding": "8px 16px",
        "font_weight": "500",
        "font_size": Typography.BODY_SIZE,
        "cursor": "pointer",
        "border": "none",
        "transition": f"background-color {Transitions.COLOR}, transform {Transitions.TRANSFORM}, box-shadow {Transitions.SHADOW}",
        "_hover": {
            "background_color": Colors.VIBRANT,
            "transform": "scale(1.02)",
        },
        "_focus": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px {Colors.WHITE}, 0 0 0 4px {Colors.PRIMARY}",
        },
        "_focus_visible": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px {Colors.WHITE}, 0 0 0 4px {Colors.PRIMARY}",
        },
        "_active": {
            "transform": "scale(0.98)",
        },
    }


def button_secondary_style() -> dict:
    """
    Secondary button styling following DESIGN_SYSTEM.md specifications.
    Includes accessible focus ring.
    """
    return {
        "background_color": Colors.WHITE,
        "color": Colors.PRIMARY,
        "border": f"1px solid {Colors.PRIMARY}",
        "border_radius": Radii.MD,
        "padding": "8px 16px",
        "font_weight": "500",
        "font_size": Typography.BODY_SIZE,
        "cursor": "pointer",
        "transition": f"background-color {Transitions.COLOR}, box-shadow {Transitions.SHADOW}",
        "_hover": {
            "background_color": Colors.PALE,
        },
        "_focus": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        },
        "_focus_visible": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        },
        "_active": {
            "background_color": Colors.SLATE_100,
        },
    }


def button_ghost_style() -> dict:
    """
    Ghost button styling following DESIGN_SYSTEM.md specifications.
    Includes accessible focus ring.
    """
    return {
        "background_color": "transparent",
        "color": Colors.PRIMARY,
        "border": "none",
        "border_radius": Radii.MD,
        "padding": "8px 16px",
        "font_weight": "500",
        "font_size": Typography.BODY_SIZE,
        "cursor": "pointer",
        "transition": f"background-color {Transitions.COLOR}, box-shadow {Transitions.SHADOW}",
        "_hover": {
            "background_color": Colors.PALE,
        },
        "_focus": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        },
        "_focus_visible": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        },
        "_active": {
            "background_color": Colors.SLATE_100,
        },
    }


def input_style() -> dict:
    """
    Form input styling following DESIGN_SYSTEM.md specifications.
    """
    return {
        "height": "32px",
        "border": f"1px solid {Colors.SLATE_300}",
        "border_radius": Radii.MD,
        "padding": f"0 {Spacing.MD}",
        "font_size": Typography.BODY_SMALL_SIZE,
        "font_family": Typography.FONT_FAMILY,
        "color": Colors.SLATE_900,
        "background_color": Colors.WHITE,
        "transition": f"border-color {Transitions.COLOR}, box-shadow {Transitions.COLOR}",
        "_placeholder": {
            "color": Colors.SLATE_500,
        },
        "_focus": {
            "outline": "none",
            "border_color": Colors.PRIMARY,
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        }
    }


# ==============================================================================
# KPI Card styles - COMPACT variants for v2.1
# ==============================================================================

def kpi_card_style() -> dict:
    """
    Standard KPI card styling (legacy, larger).
    """
    return {
        "background_color": Colors.WHITE,
        "border": f"1px solid {Colors.SLATE_300}",
        "border_radius": Radii.LG,
        "padding": Spacing.XL,
        "box_shadow": Shadows.SM,
        "text_align": "center",
    }


def kpi_value_style() -> dict:
    """Style for the large number in a KPI card (legacy)."""
    return {
        "font_family": Typography.FONT_MONO,
        "font_size": "32px",
        "font_weight": "600",
        "color": Colors.SLATE_900,
        "line_height": "1.2",
    }


def kpi_label_style() -> dict:
    """Style for the label in a KPI card (legacy)."""
    return {
        "font_size": Typography.CAPTION_SIZE,
        "font_weight": Typography.CAPTION_WEIGHT,
        "color": Colors.SLATE_500,
        "margin_top": Spacing.SM,
    }


def kpi_badge_style() -> dict:
    """
    KPI as inline pill/badge (Option A from design system).
    Zero extra height - embeds in filter row.

    Example: "12,345 patients"
    Includes subtle hover state for interactivity feedback.
    """
    return {
        "display": "inline-flex",
        "align_items": "center",
        "gap": Spacing.XS,
        "padding": f"{Spacing.XS} {Spacing.LG}",  # 4px 12px
        "background_color": Colors.SLATE_100,
        "border_radius": Radii.FULL,  # Pill shape
        "transition": f"transform {Transitions.TRANSFORM}, box-shadow {Transitions.SHADOW}",
        "cursor": "default",
        "_hover": {
            "transform": "translateY(-1px)",
            "box_shadow": Shadows.SM,
        },
    }


def kpi_badge_value_style() -> dict:
    """Style for value text in KPI badge."""
    return {
        "font_family": Typography.FONT_MONO,
        "font_size": "14px",
        "font_weight": "600",
        "color": Colors.SLATE_900,
    }


def kpi_badge_label_style() -> dict:
    """Style for label text in KPI badge."""
    return {
        "font_size": Typography.CAPTION_SIZE,
        "font_weight": "400",
        "color": Colors.SLATE_500,
    }


# ==============================================================================
# Filter strip styles - NEW for v2.1 redesign
# ==============================================================================

def filter_strip_style() -> dict:
    """
    Horizontal single-row filter container style.

    - Height: 48px
    - All filters inline
    - Slate 100 background (or transparent)
    """
    return {
        "display": "flex",
        "align_items": "center",
        "height": FILTER_STRIP_HEIGHT,
        "gap": Spacing.LG,  # 12px between filter groups
        "padding": f"0 {Spacing.XL}",  # 16px horizontal padding
        "background_color": Colors.SLATE_100,
        "border_bottom": f"1px solid {Colors.SLATE_300}",
        "width": "100%",
    }


def compact_dropdown_trigger_style() -> dict:
    """
    Compact dropdown trigger for filter strip.

    - Height: 32px
    - Padding: 8px 12px
    - Smaller font: 13px
    - Accessible focus ring
    """
    return {
        "height": "32px",
        "padding": f"{Spacing.MD} {Spacing.LG}",  # 8px 12px
        "border": f"1px solid {Colors.SLATE_300}",
        "border_radius": Radii.MD,
        "font_size": Typography.BODY_SMALL_SIZE,  # 13px
        "font_family": Typography.FONT_FAMILY,
        "color": Colors.SLATE_900,
        "background_color": Colors.WHITE,
        "cursor": "pointer",
        "display": "flex",
        "align_items": "center",
        "gap": Spacing.SM,
        "transition": f"border-color {Transitions.COLOR}, box-shadow {Transitions.SHADOW}",
        "_hover": {
            "border_color": Colors.PRIMARY,
            "background_color": Colors.SLATE_100,
        },
        "_focus": {
            "outline": "none",
            "border_color": Colors.PRIMARY,
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        },
        "_focus_visible": {
            "outline": "none",
            "border_color": Colors.PRIMARY,
            "box_shadow": f"0 0 0 2px {Colors.PALE}",
        },
    }


def searchable_dropdown_panel_style() -> dict:
    """
    Dropdown panel for searchable multi-select.

    - Max height: 200px for items
    - Compact item spacing
    """
    return {
        "background_color": Colors.WHITE,
        "border": f"1px solid {Colors.SLATE_300}",
        "border_radius": Radii.LG,
        "box_shadow": Shadows.LG,
        "min_width": "240px",
        "max_width": "320px",
        "z_index": "50",
        "overflow": "hidden",
    }


def searchable_dropdown_item_style(selected: bool = False) -> dict:
    """
    Individual item in searchable dropdown.

    - Tighter padding: 6px 8px
    - Visual selected state
    - Accessible focus state
    """
    base = {
        "padding": f"{Spacing.SM} {Spacing.MD}",  # 6px 8px
        "font_size": Typography.BODY_SMALL_SIZE,
        "cursor": "pointer",
        "display": "flex",
        "align_items": "center",
        "gap": Spacing.SM,
        "transition": f"background-color {Transitions.COLOR}",
        "border_radius": Radii.SM,  # Slight rounding for focus state
        "_focus": {
            "outline": "none",
            "background_color": Colors.SLATE_100,
            "box_shadow": f"inset 0 0 0 1px {Colors.PRIMARY}",
        },
    }

    if selected:
        base.update({
            "background_color": Colors.PALE,
            "color": Colors.PRIMARY,
            "_hover": {
                "background_color": Colors.PALE,
            },
        })
    else:
        base.update({
            "background_color": Colors.WHITE,
            "color": Colors.SLATE_900,
            "_hover": {
                "background_color": Colors.SLATE_100,
            },
        })

    return base


# ==============================================================================
# Chart container styles - NEW for v2.1 redesign
# ==============================================================================

def chart_container_style() -> dict:
    """
    Full-width, flex-grow chart wrapper.

    - Width: full viewport minus padding (16px each side)
    - Height: fills remaining space (min 500px)
    - No max-width constraint
    """
    return {
        "width": "100%",
        "padding": f"0 {Spacing.XL}",  # 16px horizontal padding
        "flex": "1",
        "min_height": "500px",
        "display": "flex",
        "flex_direction": "column",
    }


def chart_wrapper_style(overhead_height: str = "96px") -> dict:
    """
    Inner chart wrapper with calculated height.

    Args:
        overhead_height: Total height of fixed elements above chart
                        (top bar + filter strip = 48px + 48px = 96px default)
    """
    return {
        "width": "100%",
        "height": f"calc(100vh - {overhead_height})",
        "min_height": "500px",
    }


# ==============================================================================
# Typography helper functions
# ==============================================================================

def text_display() -> dict:
    """Display text style for page titles."""
    return {
        "font_size": Typography.DISPLAY_SIZE,
        "font_weight": Typography.DISPLAY_WEIGHT,
        "letter_spacing": Typography.DISPLAY_TRACKING,
        "line_height": Typography.DISPLAY_LINE_HEIGHT,
        "color": Colors.SLATE_900,
        "font_family": Typography.FONT_FAMILY,
    }


def text_h1() -> dict:
    """Heading 1 style for section headers."""
    return {
        "font_size": Typography.H1_SIZE,
        "font_weight": Typography.H1_WEIGHT,
        "letter_spacing": Typography.H1_TRACKING,
        "line_height": Typography.H1_LINE_HEIGHT,
        "color": Colors.SLATE_900,
        "font_family": Typography.FONT_FAMILY,
    }


def text_h2() -> dict:
    """Heading 2 style for card titles."""
    return {
        "font_size": Typography.H2_SIZE,
        "font_weight": Typography.H2_WEIGHT,
        "letter_spacing": Typography.H2_TRACKING,
        "line_height": Typography.H2_LINE_HEIGHT,
        "color": Colors.SLATE_900,
        "font_family": Typography.FONT_FAMILY,
    }


def text_h3() -> dict:
    """Heading 3 style for subsections."""
    return {
        "font_size": Typography.H3_SIZE,
        "font_weight": Typography.H3_WEIGHT,
        "letter_spacing": Typography.H3_TRACKING,
        "line_height": Typography.H3_LINE_HEIGHT,
        "color": Colors.SLATE_900,
        "font_family": Typography.FONT_FAMILY,
    }


def text_body() -> dict:
    """Default body text style."""
    return {
        "font_size": Typography.BODY_SIZE,
        "font_weight": Typography.BODY_WEIGHT,
        "line_height": Typography.BODY_LINE_HEIGHT,
        "color": Colors.SLATE_900,
        "font_family": Typography.FONT_FAMILY,
    }


def text_body_small() -> dict:
    """Secondary/small body text style."""
    return {
        "font_size": Typography.BODY_SMALL_SIZE,
        "font_weight": Typography.BODY_SMALL_WEIGHT,
        "line_height": Typography.BODY_SMALL_LINE_HEIGHT,
        "color": Colors.SLATE_700,
        "font_family": Typography.FONT_FAMILY,
    }


def text_caption() -> dict:
    """Caption style for labels and metadata."""
    return {
        "font_size": Typography.CAPTION_SIZE,
        "font_weight": Typography.CAPTION_WEIGHT,
        "line_height": Typography.CAPTION_LINE_HEIGHT,
        "color": Colors.SLATE_500,
        "font_family": Typography.FONT_FAMILY,
    }


def text_mono() -> dict:
    """Monospace text style for data values and codes."""
    return {
        "font_size": Typography.MONO_SIZE,
        "font_weight": Typography.MONO_WEIGHT,
        "line_height": Typography.MONO_LINE_HEIGHT,
        "color": Colors.SLATE_900,
        "font_family": Typography.FONT_MONO,
    }


# ==============================================================================
# Top bar styles - NEW for v2.1 redesign
# ==============================================================================

def top_bar_style() -> dict:
    """
    Top bar container style.

    - Height: 48px (reduced from 64px)
    - Heritage Blue background
    """
    return {
        "height": TOP_BAR_HEIGHT,
        "background_color": Colors.HERITAGE_BLUE,
        "display": "flex",
        "align_items": "center",
        "justify_content": "space_between",
        "padding": f"0 {Spacing.XL}",
        "width": "100%",
    }


def top_bar_tab_style(active: bool = False) -> dict:
    """
    Tab/pill style for top bar navigation.

    - Height: 28px
    - Smaller pills
    - Accessible focus ring
    """
    base = {
        "height": "28px",
        "padding": f"{Spacing.XS} {Spacing.LG}",  # 4px 12px
        "border_radius": Radii.MD,
        "font_size": Typography.BODY_SMALL_SIZE,
        "font_weight": "500",
        "cursor": "pointer",
        "transition": f"background-color {Transitions.COLOR}, box-shadow {Transitions.SHADOW}",
        "_focus": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px rgba(255,255,255,0.4)",
        },
        "_focus_visible": {
            "outline": "none",
            "box_shadow": f"0 0 0 2px rgba(255,255,255,0.4)",
        },
    }

    if active:
        base.update({
            "background_color": Colors.WHITE,
            "color": Colors.HERITAGE_BLUE,
        })
    else:
        base.update({
            "background_color": "transparent",
            "color": Colors.WHITE,
            "_hover": {
                "background_color": "rgba(255,255,255,0.15)",
            }
        })

    return base


def logo_style() -> dict:
    """Logo style for top bar - 28px height (reduced from 36px)."""
    return {
        "height": "28px",
        "width": "auto",
    }
