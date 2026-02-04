"""
Design tokens and style helpers for HCD Analysis v2.

All visual styling should use these tokens for consistency.
Import: from pathways_app.styles import Colors, Spacing, Typography, etc.
"""


class Colors:
    """Color palette from DESIGN_SYSTEM.md"""

    # Primary Blues (NHS-inspired, modernized)
    HERITAGE_BLUE = "#003087"  # Deep headers, authoritative accents
    PRIMARY = "#0066CC"        # Main actions, links, focus states
    VIBRANT = "#1E88E5"        # Highlights, hover states, chart primary
    SKY = "#4FC3F7"            # Accents, progress bars, secondary elements
    PALE = "#E3F2FD"           # Subtle backgrounds, card tints

    # Neutrals (warm-tinted for clinical warmth)
    SLATE_900 = "#1E293B"      # Primary text
    SLATE_700 = "#334155"      # Secondary text
    SLATE_500 = "#64748B"      # Muted text, placeholders
    SLATE_300 = "#CBD5E1"      # Borders, dividers
    SLATE_100 = "#F1F5F9"      # Card backgrounds, hover states
    WHITE = "#FFFFFF"          # Page background

    # Semantic Colors
    SUCCESS = "#059669"        # Positive states, confirmations
    WARNING = "#D97706"        # Caution states, alerts
    ERROR = "#DC2626"          # Error states, destructive actions
    INFO = "#0284C7"           # Informational (matches primary family)

    # Chart Palette
    CHART_SERIES = ["#003087", "#0066CC", "#1E88E5", "#4FC3F7", "#90CAF9"]
    CHART_CATEGORICAL = ["#0066CC", "#059669", "#D97706", "#8B5CF6", "#EC4899"]


class Typography:
    """Typography tokens from DESIGN_SYSTEM.md"""

    # Font families
    FONT_FAMILY = "Inter, system-ui, -apple-system, sans-serif"
    FONT_MONO = "JetBrains Mono, monospace"

    # Display: Page titles
    DISPLAY_SIZE = "32px"
    DISPLAY_WEIGHT = "700"
    DISPLAY_TRACKING = "-0.02em"
    DISPLAY_LINE_HEIGHT = "1.2"

    # Heading 1: Section headers
    H1_SIZE = "24px"
    H1_WEIGHT = "600"
    H1_TRACKING = "-0.01em"
    H1_LINE_HEIGHT = "1.3"

    # Heading 2: Card titles
    H2_SIZE = "20px"
    H2_WEIGHT = "600"
    H2_TRACKING = "normal"
    H2_LINE_HEIGHT = "1.4"

    # Heading 3: Subsections
    H3_SIZE = "16px"
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

    # Caption: Labels, metadata
    CAPTION_SIZE = "12px"
    CAPTION_WEIGHT = "500"
    CAPTION_LINE_HEIGHT = "1.4"

    # Mono: Data values, codes
    MONO_SIZE = "13px"
    MONO_WEIGHT = "400"
    MONO_LINE_HEIGHT = "1.5"


class Spacing:
    """Spacing scale from DESIGN_SYSTEM.md"""

    XS = "4px"    # Tight internal padding
    SM = "8px"    # Between related elements
    MD = "12px"   # Standard gaps
    LG = "16px"   # Section padding
    XL = "24px"   # Card padding
    XXL = "32px"  # Major section gaps
    XXXL = "48px" # Page margins


class Radii:
    """Border radius values from DESIGN_SYSTEM.md"""

    SM = "4px"      # Small elements, inputs
    MD = "8px"      # Buttons, small cards
    LG = "12px"     # Cards, modals
    XL = "16px"     # Large containers
    FULL = "9999px" # Pills, avatars


class Shadows:
    """Shadow values from DESIGN_SYSTEM.md"""

    SM = "0 1px 2px rgba(0,0,0,0.05)"    # Subtle elevation
    MD = "0 1px 3px rgba(0,0,0,0.08)"    # Cards at rest
    LG = "0 4px 6px rgba(0,0,0,0.1)"     # Cards on hover, dropdowns
    XL = "0 10px 15px rgba(0,0,0,0.1)"   # Modals, popovers


class Transitions:
    """Transition values from DESIGN_SYSTEM.md"""

    COLOR = "150ms ease-out"
    TRANSFORM = "200ms ease-out"
    SHADOW = "200ms ease-out"
    OPACITY = "200ms ease-in-out"


# ==============================================================================
# Helper functions for common style patterns
# ==============================================================================

def card_style(hoverable: bool = False) -> dict:
    """
    Card styling following DESIGN_SYSTEM.md specifications.

    - Background: White
    - Border: 1px Slate 300
    - Border radius: lg (12px)
    - Padding: xl (24px)
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

    - Background: Primary Blue
    - Text: White
    - Border radius: md (8px)
    - Padding: 10px 20px
    - Hover: Vibrant Blue background, slight scale (1.02)
    """
    return {
        "background_color": Colors.PRIMARY,
        "color": Colors.WHITE,
        "border_radius": Radii.MD,
        "padding": "10px 20px",
        "font_weight": "500",
        "font_size": Typography.BODY_SIZE,
        "cursor": "pointer",
        "border": "none",
        "transition": f"background-color {Transitions.COLOR}, transform {Transitions.TRANSFORM}",
        "_hover": {
            "background_color": Colors.VIBRANT,
            "transform": "scale(1.02)",
        }
    }


def button_secondary_style() -> dict:
    """
    Secondary button styling following DESIGN_SYSTEM.md specifications.

    - Background: White
    - Border: 1px Primary Blue
    - Text: Primary Blue
    - Hover: Pale Blue background
    """
    return {
        "background_color": Colors.WHITE,
        "color": Colors.PRIMARY,
        "border": f"1px solid {Colors.PRIMARY}",
        "border_radius": Radii.MD,
        "padding": "10px 20px",
        "font_weight": "500",
        "font_size": Typography.BODY_SIZE,
        "cursor": "pointer",
        "transition": f"background-color {Transitions.COLOR}",
        "_hover": {
            "background_color": Colors.PALE,
        }
    }


def button_ghost_style() -> dict:
    """
    Ghost button styling following DESIGN_SYSTEM.md specifications.

    - Background: transparent
    - Text: Primary Blue
    - Hover: Pale Blue background
    """
    return {
        "background_color": "transparent",
        "color": Colors.PRIMARY,
        "border": "none",
        "border_radius": Radii.MD,
        "padding": "10px 20px",
        "font_weight": "500",
        "font_size": Typography.BODY_SIZE,
        "cursor": "pointer",
        "transition": f"background-color {Transitions.COLOR}",
        "_hover": {
            "background_color": Colors.PALE,
        }
    }


def input_style() -> dict:
    """
    Form input styling following DESIGN_SYSTEM.md specifications.

    - Height: 40px
    - Border: 1px Slate 300
    - Border radius: md (8px)
    - Focus: 2px Primary Blue ring
    - Placeholder: Slate 500
    """
    return {
        "height": "40px",
        "border": f"1px solid {Colors.SLATE_300}",
        "border_radius": Radii.MD,
        "padding": f"0 {Spacing.MD}",
        "font_size": Typography.BODY_SIZE,
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


def kpi_card_style() -> dict:
    """
    KPI card styling following DESIGN_SYSTEM.md specifications.

    - Large mono number: 32-48px, Slate 900
    - Label: Caption size, Slate 500
    - Background: White or Pale Blue tint
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
    """Style for the large number in a KPI card."""
    return {
        "font_family": Typography.FONT_MONO,
        "font_size": "32px",
        "font_weight": "600",
        "color": Colors.SLATE_900,
        "line_height": "1.2",
    }


def kpi_label_style() -> dict:
    """Style for the label in a KPI card."""
    return {
        "font_size": Typography.CAPTION_SIZE,
        "font_weight": Typography.CAPTION_WEIGHT,
        "color": Colors.SLATE_500,
        "margin_top": Spacing.SM,
    }


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
# Layout constants
# ==============================================================================

TOP_BAR_HEIGHT = "64px"
PAGE_MAX_WIDTH = "1600px"
PAGE_PADDING = Spacing.XXXL
