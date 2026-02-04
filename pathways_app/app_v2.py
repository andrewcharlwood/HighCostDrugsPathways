"""
HCD Analysis v2 - Redesigned Reflex Application.

Single-page dashboard with reactive filtering and real-time chart updates.
Design reference: DESIGN_SYSTEM.md
"""

import reflex as rx

from pathways_app.styles import (
    Colors,
    Typography,
    Spacing,
    Radii,
    Shadows,
    Transitions,
    TOP_BAR_HEIGHT,
    PAGE_MAX_WIDTH,
    PAGE_PADDING,
    card_style,
    text_h1,
)


# =============================================================================
# State
# =============================================================================

class AppState(rx.State):
    """
    Application state for HCD Analysis v2.

    This is a minimal placeholder state for the app skeleton.
    Will be expanded in Phase 3 with full filter state and data management.
    """

    # Placeholder state variables (expanded in Phase 3)
    data_loaded: bool = False
    total_records: int = 0
    chart_loading: bool = False
    error_message: str = ""

    # Placeholder for current chart type (for top bar tabs)
    current_chart: str = "icicle"


# =============================================================================
# Layout Components
# =============================================================================

def chart_tab(label: str, chart_type: str, is_active: bool = False) -> rx.Component:
    """
    Individual chart type tab/pill for top bar navigation.

    Active state: White background with Heritage Blue text
    Inactive state: Transparent with white text, hover shows Vibrant Blue background
    """
    return rx.box(
        rx.text(
            label,
            font_size=Typography.BODY_SMALL_SIZE,
            font_weight="500",
            color=Colors.HERITAGE_BLUE if is_active else Colors.WHITE,
            font_family=Typography.FONT_FAMILY,
        ),
        background_color=Colors.WHITE if is_active else "transparent",
        padding_x=Spacing.LG,
        padding_y=Spacing.SM,
        border_radius=Radii.FULL,
        cursor="pointer",
        transition=f"background-color {Transitions.COLOR}",
        _hover={
            "background_color": Colors.WHITE if is_active else "rgba(255,255,255,0.15)",
        },
        # Future: on_click handler to switch chart type
    )


def top_bar() -> rx.Component:
    """
    Top navigation bar component.

    Contains: Logo + App Name | Chart Type Tabs | Data Freshness Indicator
    Fixed height: 64px (from design system)
    Heritage Blue background with white text.
    """
    return rx.box(
        rx.hstack(
            # Left: Logo and App Title
            rx.hstack(
                rx.image(
                    src="/logo.png",
                    height="36px",
                    alt="NHS Logo",
                ),
                rx.text(
                    "HCD Analysis",
                    font_size=Typography.H2_SIZE,
                    font_weight=Typography.H2_WEIGHT,
                    color=Colors.WHITE,
                    font_family=Typography.FONT_FAMILY,
                    letter_spacing="-0.01em",
                ),
                align="center",
                spacing="3",
            ),
            # Center: Chart Type Tabs
            rx.hstack(
                chart_tab("Icicle", "icicle", is_active=True),
                chart_tab("Sankey", "sankey", is_active=False),
                chart_tab("Timeline", "timeline", is_active=False),
                spacing="2",
                align="center",
                background_color="rgba(255,255,255,0.1)",
                padding=Spacing.XS,
                border_radius=Radii.FULL,
            ),
            # Right: Data Freshness Indicator
            rx.hstack(
                rx.icon(
                    "database",
                    size=16,
                    color=Colors.SKY,
                ),
                rx.vstack(
                    rx.text(
                        rx.cond(
                            AppState.data_loaded,
                            AppState.total_records.to_string() + " records",
                            "Loading data...",
                        ),
                        font_size=Typography.CAPTION_SIZE,
                        font_weight="500",
                        color=Colors.WHITE,
                        font_family=Typography.FONT_FAMILY,
                    ),
                    rx.text(
                        rx.cond(
                            AppState.data_loaded,
                            "Last refreshed: recently",
                            "Connecting...",
                        ),
                        font_size="11px",
                        color=Colors.WHITE,
                        opacity="0.7",
                        font_family=Typography.FONT_FAMILY,
                    ),
                    spacing="0",
                    align="end",
                ),
                spacing="2",
                align="center",
            ),
            justify="between",
            align="center",
            width="100%",
            max_width=PAGE_MAX_WIDTH,
            margin_x="auto",
            padding_x=Spacing.XL,
        ),
        background_color=Colors.HERITAGE_BLUE,
        height=TOP_BAR_HEIGHT,
        width="100%",
        display="flex",
        align_items="center",
        position="sticky",
        top="0",
        z_index="100",
        box_shadow=Shadows.MD,
    )


def filter_section() -> rx.Component:
    """
    Filter section component.

    Contains: Date range pickers, searchable multi-select dropdowns.

    Will be fully implemented in Task 2.2.
    """
    return rx.box(
        rx.text(
            "Filters",
            **text_h1(),
            margin_bottom=Spacing.MD,
        ),
        rx.text(
            "Filter controls will be implemented in Phase 2.",
            font_size=Typography.BODY_SIZE,
            font_weight=Typography.BODY_WEIGHT,
            color=Colors.SLATE_500,
            font_family=Typography.FONT_FAMILY,
        ),
        **card_style(),
        width="100%",
    )


def kpi_row() -> rx.Component:
    """
    KPI metrics row component.

    Contains: Unique patients count, and space for additional metrics.

    Will be fully implemented in Task 2.3.
    """
    return rx.hstack(
        rx.box(
            rx.vstack(
                rx.text(
                    "—",
                    font_family=Typography.FONT_MONO,
                    font_size="32px",
                    font_weight="600",
                    color=Colors.SLATE_900,
                ),
                rx.text(
                    "Unique Patients",
                    font_size=Typography.CAPTION_SIZE,
                    font_weight=Typography.CAPTION_WEIGHT,
                    color=Colors.SLATE_500,
                ),
                spacing="1",
                align="center",
            ),
            **card_style(),
            min_width="200px",
            text_align="center",
        ),
        # Space for additional KPI cards
        spacing="4",
        width="100%",
    )


def chart_section() -> rx.Component:
    """
    Main chart section component.

    Contains: Plotly icicle chart with loading and error states.

    Will be fully implemented in Task 2.4 and Phase 4.
    """
    return rx.box(
        rx.vstack(
            rx.text(
                "Patient Pathway Chart",
                **text_h1(),
            ),
            rx.text(
                "Chart will be displayed here once data is loaded.",
                font_size=Typography.BODY_SIZE,
                font_weight=Typography.BODY_WEIGHT,
                color=Colors.SLATE_500,
                font_family=Typography.FONT_FAMILY,
            ),
            # Placeholder for chart area
            rx.box(
                rx.center(
                    rx.text(
                        "Chart Placeholder",
                        color=Colors.SLATE_500,
                        font_size=Typography.BODY_SIZE,
                    ),
                    width="100%",
                    height="400px",
                ),
                background_color=Colors.SLATE_100,
                border_radius=Radii.MD,
                width="100%",
            ),
            spacing="4",
            width="100%",
            align="start",
        ),
        **card_style(),
        width="100%",
    )


def main_content() -> rx.Component:
    """
    Main content area below the top bar.

    Layout: Filter Section → KPI Row → Chart Section
    Max width constrained to PAGE_MAX_WIDTH, centered.
    """
    return rx.box(
        rx.vstack(
            filter_section(),
            kpi_row(),
            chart_section(),
            spacing="5",
            width="100%",
            align="stretch",
        ),
        width="100%",
        max_width=PAGE_MAX_WIDTH,
        margin_x="auto",
        padding=PAGE_PADDING,
        padding_top=Spacing.XL,
    )


def page_layout() -> rx.Component:
    """
    Full page layout combining top bar and main content.

    Structure:
    - Sticky top bar (64px)
    - Scrollable main content area
    - White background
    """
    return rx.box(
        rx.vstack(
            top_bar(),
            main_content(),
            spacing="0",
            width="100%",
            min_height="100vh",
        ),
        background_color=Colors.WHITE,
        font_family=Typography.FONT_FAMILY,
        width="100%",
    )


# =============================================================================
# Page Definition
# =============================================================================

def index() -> rx.Component:
    """Main page for HCD Analysis v2."""
    return page_layout()


# =============================================================================
# App Configuration
# =============================================================================

app = rx.App(
    theme=rx.theme(
        accent_color="blue",
        gray_color="slate",
        radius="medium",
    ),
    stylesheets=[
        # Google Fonts - Inter (primary) and JetBrains Mono (monospace)
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
    ],
)

# Register page
app.add_page(index, route="/", title="HCD Analysis | Patient Pathways")
