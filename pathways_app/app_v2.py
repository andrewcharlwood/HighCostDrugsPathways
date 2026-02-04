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
    input_style,
    text_h1,
    text_h3,
    text_caption,
    button_ghost_style,
    kpi_card_style,
    kpi_value_style,
    kpi_label_style,
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

    # Filter toggle state
    initiated_filter_enabled: bool = False
    last_seen_filter_enabled: bool = True

    # Date filter values (ISO format strings for simplicity)
    initiated_from_date: str = ""
    initiated_to_date: str = ""
    last_seen_from_date: str = ""
    last_seen_to_date: str = ""

    # Available options for dropdowns (populated from data in Phase 3)
    available_drugs: list[str] = ["Drug A", "Drug B", "Drug C", "Drug D", "Drug E"]
    available_indications: list[str] = ["Indication 1", "Indication 2", "Indication 3"]
    available_directorates: list[str] = ["Medical", "Surgical", "Oncology", "Rheumatology"]

    # Selected items (empty = all)
    selected_drugs: list[str] = []
    selected_indications: list[str] = []
    selected_directorates: list[str] = []

    # Search text for dropdowns
    drug_search: str = ""
    indication_search: str = ""
    directorate_search: str = ""

    # Dropdown visibility state
    drug_dropdown_open: bool = False
    indication_dropdown_open: bool = False
    directorate_dropdown_open: bool = False

    # Event handlers for filter toggles
    def toggle_initiated_filter(self):
        """Toggle initiated date filter on/off."""
        self.initiated_filter_enabled = not self.initiated_filter_enabled

    def toggle_last_seen_filter(self):
        """Toggle last seen date filter on/off."""
        self.last_seen_filter_enabled = not self.last_seen_filter_enabled

    # Event handlers for date changes
    def set_initiated_from(self, value: str):
        """Set initiated from date."""
        self.initiated_from_date = value

    def set_initiated_to(self, value: str):
        """Set initiated to date."""
        self.initiated_to_date = value

    def set_last_seen_from(self, value: str):
        """Set last seen from date."""
        self.last_seen_from_date = value

    def set_last_seen_to(self, value: str):
        """Set last seen to date."""
        self.last_seen_to_date = value

    # Event handlers for search
    def set_drug_search(self, value: str):
        """Update drug search text."""
        self.drug_search = value

    def set_indication_search(self, value: str):
        """Update indication search text."""
        self.indication_search = value

    def set_directorate_search(self, value: str):
        """Update directorate search text."""
        self.directorate_search = value

    # Event handlers for dropdown visibility
    def toggle_drug_dropdown(self):
        """Toggle drug dropdown visibility."""
        self.drug_dropdown_open = not self.drug_dropdown_open
        # Close other dropdowns
        self.indication_dropdown_open = False
        self.directorate_dropdown_open = False

    def toggle_indication_dropdown(self):
        """Toggle indication dropdown visibility."""
        self.indication_dropdown_open = not self.indication_dropdown_open
        # Close other dropdowns
        self.drug_dropdown_open = False
        self.directorate_dropdown_open = False

    def toggle_directorate_dropdown(self):
        """Toggle directorate dropdown visibility."""
        self.directorate_dropdown_open = not self.directorate_dropdown_open
        # Close other dropdowns
        self.drug_dropdown_open = False
        self.indication_dropdown_open = False

    def close_all_dropdowns(self):
        """Close all dropdowns."""
        self.drug_dropdown_open = False
        self.indication_dropdown_open = False
        self.directorate_dropdown_open = False

    # Event handlers for item selection
    def toggle_drug(self, drug: str):
        """Toggle a drug selection."""
        if drug in self.selected_drugs:
            self.selected_drugs = [d for d in self.selected_drugs if d != drug]
        else:
            self.selected_drugs = self.selected_drugs + [drug]

    def toggle_indication(self, indication: str):
        """Toggle an indication selection."""
        if indication in self.selected_indications:
            self.selected_indications = [i for i in self.selected_indications if i != indication]
        else:
            self.selected_indications = self.selected_indications + [indication]

    def toggle_directorate(self, directorate: str):
        """Toggle a directorate selection."""
        if directorate in self.selected_directorates:
            self.selected_directorates = [d for d in self.selected_directorates if d != directorate]
        else:
            self.selected_directorates = self.selected_directorates + [directorate]

    # Select/clear all handlers
    def select_all_drugs(self):
        """Select all available drugs."""
        self.selected_drugs = self.available_drugs.copy()

    def clear_all_drugs(self):
        """Clear all drug selections."""
        self.selected_drugs = []

    def select_all_indications(self):
        """Select all available indications."""
        self.selected_indications = self.available_indications.copy()

    def clear_all_indications(self):
        """Clear all indication selections."""
        self.selected_indications = []

    def select_all_directorates(self):
        """Select all available directorates."""
        self.selected_directorates = self.available_directorates.copy()

    def clear_all_directorates(self):
        """Clear all directorate selections."""
        self.selected_directorates = []

    # Computed vars for filtered options based on search
    @rx.var
    def filtered_drugs(self) -> list[str]:
        """Return drugs filtered by search text."""
        if not self.drug_search:
            return self.available_drugs
        search_lower = self.drug_search.lower()
        return [d for d in self.available_drugs if search_lower in d.lower()]

    @rx.var
    def filtered_indications(self) -> list[str]:
        """Return indications filtered by search text."""
        if not self.indication_search:
            return self.available_indications
        search_lower = self.indication_search.lower()
        return [i for i in self.available_indications if search_lower in i.lower()]

    @rx.var
    def filtered_directorates(self) -> list[str]:
        """Return directorates filtered by search text."""
        if not self.directorate_search:
            return self.available_directorates
        search_lower = self.directorate_search.lower()
        return [d for d in self.available_directorates if search_lower in d.lower()]

    # Computed vars for selection counts
    @rx.var
    def drug_selection_text(self) -> str:
        """Display text for drug selection count."""
        count = len(self.selected_drugs)
        total = len(self.available_drugs)
        if count == 0:
            return f"All {total} drugs"
        return f"{count} of {total} selected"

    @rx.var
    def indication_selection_text(self) -> str:
        """Display text for indication selection count."""
        count = len(self.selected_indications)
        total = len(self.available_indications)
        if count == 0:
            return f"All {total} indications"
        return f"{count} of {total} selected"

    @rx.var
    def directorate_selection_text(self) -> str:
        """Display text for directorate selection count."""
        count = len(self.selected_directorates)
        total = len(self.available_directorates)
        if count == 0:
            return f"All {total} directorates"
        return f"{count} of {total} selected"

    # =========================================================================
    # KPI State Variables
    # =========================================================================

    # Placeholder KPI values (will be computed from filtered data in Phase 3)
    # For now, these are static placeholders that demonstrate reactivity
    unique_patients: int = 0
    total_drugs: int = 0
    total_cost: float = 0.0
    indication_match_rate: float = 0.0

    # Computed KPI display values
    @rx.var
    def unique_patients_display(self) -> str:
        """Format unique patients count for display."""
        if self.unique_patients == 0:
            return "—"
        return f"{self.unique_patients:,}"

    @rx.var
    def total_drugs_display(self) -> str:
        """Format total drugs count for display."""
        if self.total_drugs == 0:
            return "—"
        return f"{self.total_drugs:,}"

    @rx.var
    def total_cost_display(self) -> str:
        """Format total cost for display."""
        if self.total_cost == 0.0:
            return "—"
        # Format as £X.XM or £X.XK depending on magnitude
        if self.total_cost >= 1_000_000:
            return f"£{self.total_cost / 1_000_000:.1f}M"
        if self.total_cost >= 1_000:
            return f"£{self.total_cost / 1_000:.1f}K"
        return f"£{self.total_cost:,.0f}"

    @rx.var
    def match_rate_display(self) -> str:
        """Format indication match rate for display."""
        if self.indication_match_rate == 0.0:
            return "—"
        return f"{self.indication_match_rate:.0f}%"


# =============================================================================
# Layout Components
# =============================================================================

def date_range_picker(
    label: str,
    enabled: rx.Var[bool],
    toggle_handler,
    from_value: rx.Var[str],
    to_value: rx.Var[str],
    on_from_change,
    on_to_change,
) -> rx.Component:
    """
    Date range picker with enable/disable checkbox.

    Args:
        label: Label for the date range (e.g., "Initiated", "Last Seen")
        enabled: Whether the filter is active
        toggle_handler: Event handler to toggle enabled state
        from_value: Current "from" date value
        to_value: Current "to" date value
        on_from_change: Handler for from date change
        on_to_change: Handler for to date change
    """
    return rx.vstack(
        # Header with checkbox
        rx.hstack(
            rx.checkbox(
                checked=enabled,
                on_change=toggle_handler,
                size="2",
            ),
            rx.text(
                label,
                font_size=Typography.H3_SIZE,
                font_weight=Typography.H3_WEIGHT,
                color=Colors.SLATE_900,
                font_family=Typography.FONT_FAMILY,
            ),
            align="center",
            spacing="2",
        ),
        # Date inputs
        rx.hstack(
            rx.vstack(
                rx.text(
                    "From",
                    **text_caption(),
                ),
                rx.input(
                    type="date",
                    value=from_value,
                    on_change=on_from_change,
                    disabled=~enabled,
                    **input_style(),
                    width="140px",
                    opacity=rx.cond(enabled, "1", "0.5"),
                ),
                spacing="1",
                align="start",
            ),
            rx.vstack(
                rx.text(
                    "To",
                    **text_caption(),
                ),
                rx.input(
                    type="date",
                    value=to_value,
                    on_change=on_to_change,
                    disabled=~enabled,
                    **input_style(),
                    width="140px",
                    opacity=rx.cond(enabled, "1", "0.5"),
                ),
                spacing="1",
                align="start",
            ),
            spacing="3",
            align="end",
        ),
        spacing="2",
        align="start",
    )


def searchable_dropdown(
    label: str,
    selection_text: rx.Var[str],
    is_open: rx.Var[bool],
    toggle_handler,
    search_value: rx.Var[str],
    on_search_change,
    filtered_items: rx.Var[list[str]],
    selected_items: rx.Var[list[str]],
    toggle_item_handler,
    select_all_handler,
    clear_all_handler,
) -> rx.Component:
    """
    Searchable multi-select dropdown component.

    Args:
        label: Label for the dropdown
        selection_text: Text showing selection count
        is_open: Whether dropdown is expanded
        toggle_handler: Handler to toggle dropdown open/close
        search_value: Current search text
        on_search_change: Handler for search input change
        filtered_items: Items filtered by search
        selected_items: Currently selected items
        toggle_item_handler: Handler to toggle item selection
        select_all_handler: Handler to select all
        clear_all_handler: Handler to clear selection
    """
    return rx.box(
        rx.vstack(
            # Label
            rx.text(
                label,
                font_size=Typography.CAPTION_SIZE,
                font_weight=Typography.CAPTION_WEIGHT,
                color=Colors.SLATE_700,
                font_family=Typography.FONT_FAMILY,
            ),
            # Dropdown trigger button
            rx.box(
                rx.hstack(
                    rx.text(
                        selection_text,
                        font_size=Typography.BODY_SIZE,
                        color=Colors.SLATE_900,
                        font_family=Typography.FONT_FAMILY,
                        flex="1",
                    ),
                    rx.icon(
                        rx.cond(is_open, "chevron-up", "chevron-down"),
                        size=16,
                        color=Colors.SLATE_500,
                    ),
                    justify="between",
                    align="center",
                    width="100%",
                ),
                **input_style(),
                display="flex",
                align_items="center",
                cursor="pointer",
                on_click=toggle_handler,
                width="100%",
            ),
            # Dropdown panel
            rx.cond(
                is_open,
                rx.box(
                    rx.vstack(
                        # Search input
                        rx.hstack(
                            rx.icon("search", size=14, color=Colors.SLATE_500),
                            rx.input(
                                placeholder="Search...",
                                value=search_value,
                                on_change=on_search_change,
                                variant="soft",
                                size="2",
                                width="100%",
                            ),
                            spacing="2",
                            align="center",
                            width="100%",
                            padding=Spacing.SM,
                            background_color=Colors.SLATE_100,
                            border_radius=Radii.SM,
                        ),
                        # Action buttons
                        rx.hstack(
                            rx.button(
                                "Select All",
                                on_click=select_all_handler,
                                variant="ghost",
                                size="1",
                                color_scheme="blue",
                            ),
                            rx.button(
                                "Clear",
                                on_click=clear_all_handler,
                                variant="ghost",
                                size="1",
                                color_scheme="gray",
                            ),
                            spacing="2",
                        ),
                        # Items list
                        rx.box(
                            rx.foreach(
                                filtered_items,
                                lambda item: rx.box(
                                    rx.checkbox(
                                        item,
                                        checked=selected_items.contains(item),
                                        on_change=lambda: toggle_item_handler(item),
                                        size="2",
                                    ),
                                    padding_y=Spacing.XS,
                                    padding_x=Spacing.SM,
                                    border_radius=Radii.SM,
                                    background_color=rx.cond(
                                        selected_items.contains(item),
                                        Colors.PALE,
                                        "transparent",
                                    ),
                                    _hover={
                                        "background_color": Colors.SLATE_100,
                                    },
                                    width="100%",
                                ),
                            ),
                            max_height="200px",
                            overflow_y="auto",
                            width="100%",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                        padding=Spacing.SM,
                    ),
                    position="absolute",
                    top="100%",
                    left="0",
                    right="0",
                    background_color=Colors.WHITE,
                    border=f"1px solid {Colors.SLATE_300}",
                    border_radius=Radii.MD,
                    box_shadow=Shadows.LG,
                    z_index="50",
                    margin_top=Spacing.XS,
                ),
            ),
            spacing="1",
            align="start",
            width="100%",
        ),
        position="relative",
        width="100%",
    )


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

    Contains:
    - Two date range pickers: Initiated (default OFF), Last Seen (default ON)
    - Three searchable multi-select dropdowns: Drugs, Indications, Directorates

    Layout: Two rows
    - Row 1: Date pickers side by side
    - Row 2: Three dropdowns in a grid
    """
    return rx.box(
        rx.vstack(
            # Header
            rx.text(
                "Filters",
                **text_h1(),
            ),
            # Row 1: Date range pickers
            rx.hstack(
                date_range_picker(
                    label="Initiated",
                    enabled=AppState.initiated_filter_enabled,
                    toggle_handler=AppState.toggle_initiated_filter,
                    from_value=AppState.initiated_from_date,
                    to_value=AppState.initiated_to_date,
                    on_from_change=AppState.set_initiated_from,
                    on_to_change=AppState.set_initiated_to,
                ),
                rx.divider(orientation="vertical", size="3"),
                date_range_picker(
                    label="Last Seen",
                    enabled=AppState.last_seen_filter_enabled,
                    toggle_handler=AppState.toggle_last_seen_filter,
                    from_value=AppState.last_seen_from_date,
                    to_value=AppState.last_seen_to_date,
                    on_from_change=AppState.set_last_seen_from,
                    on_to_change=AppState.set_last_seen_to,
                ),
                spacing="5",
                align="start",
                flex_wrap="wrap",
            ),
            # Divider
            rx.divider(size="4"),
            # Row 2: Searchable dropdowns
            rx.hstack(
                rx.box(
                    searchable_dropdown(
                        label="Drugs",
                        selection_text=AppState.drug_selection_text,
                        is_open=AppState.drug_dropdown_open,
                        toggle_handler=AppState.toggle_drug_dropdown,
                        search_value=AppState.drug_search,
                        on_search_change=AppState.set_drug_search,
                        filtered_items=AppState.filtered_drugs,
                        selected_items=AppState.selected_drugs,
                        toggle_item_handler=AppState.toggle_drug,
                        select_all_handler=AppState.select_all_drugs,
                        clear_all_handler=AppState.clear_all_drugs,
                    ),
                    flex="1",
                    min_width="200px",
                ),
                rx.box(
                    searchable_dropdown(
                        label="Indications",
                        selection_text=AppState.indication_selection_text,
                        is_open=AppState.indication_dropdown_open,
                        toggle_handler=AppState.toggle_indication_dropdown,
                        search_value=AppState.indication_search,
                        on_search_change=AppState.set_indication_search,
                        filtered_items=AppState.filtered_indications,
                        selected_items=AppState.selected_indications,
                        toggle_item_handler=AppState.toggle_indication,
                        select_all_handler=AppState.select_all_indications,
                        clear_all_handler=AppState.clear_all_indications,
                    ),
                    flex="1",
                    min_width="200px",
                ),
                rx.box(
                    searchable_dropdown(
                        label="Directorates",
                        selection_text=AppState.directorate_selection_text,
                        is_open=AppState.directorate_dropdown_open,
                        toggle_handler=AppState.toggle_directorate_dropdown,
                        search_value=AppState.directorate_search,
                        on_search_change=AppState.set_directorate_search,
                        filtered_items=AppState.filtered_directorates,
                        selected_items=AppState.selected_directorates,
                        toggle_item_handler=AppState.toggle_directorate,
                        select_all_handler=AppState.select_all_directorates,
                        clear_all_handler=AppState.clear_all_directorates,
                    ),
                    flex="1",
                    min_width="200px",
                ),
                spacing="4",
                width="100%",
                flex_wrap="wrap",
            ),
            spacing="4",
            width="100%",
            align="start",
        ),
        **card_style(),
        width="100%",
    )


def kpi_card(
    value: rx.Var[str],
    label: str,
    icon_name: str = None,
    highlight: bool = False,
) -> rx.Component:
    """
    KPI card component displaying a metric value with label.

    Args:
        value: The display value (should be a formatted string from computed var)
        label: Label describing the metric
        icon_name: Optional Lucide icon name to display
        highlight: If True, uses Pale Blue background tint

    Design specs from DESIGN_SYSTEM.md:
    - Large mono number: 32-48px, Slate 900
    - Label: Caption size, Slate 500
    - Background: White or Pale Blue tint
    """
    # Build content - icon only if provided
    content_items = []
    if icon_name:
        content_items.append(
            rx.icon(
                icon_name,
                size=20,
                color=Colors.PRIMARY,
            )
        )

    return rx.box(
        rx.vstack(
            # Optional icon
            rx.icon(
                icon_name if icon_name else "activity",
                size=20,
                color=Colors.PRIMARY,
            ) if icon_name else rx.fragment(),
            # Value
            rx.text(
                value,
                **kpi_value_style(),
            ),
            # Label
            rx.text(
                label,
                **kpi_label_style(),
            ),
            spacing="1",
            align="center",
        ),
        # Apply card styling manually to allow background_color override
        background_color=Colors.PALE if highlight else Colors.WHITE,
        border=f"1px solid {Colors.SLATE_300}",
        border_radius=Radii.LG,
        padding=Spacing.XL,
        box_shadow=Shadows.SM,
        text_align="center",
        min_width="180px",
        flex="1",
        transition=f"box-shadow {Transitions.SHADOW}, transform {Transitions.TRANSFORM}",
        _hover={
            "box_shadow": Shadows.MD,
            "transform": "translateY(-2px)",
        },
    )


def kpi_row() -> rx.Component:
    """
    KPI metrics row component with responsive grid layout.

    Contains:
    - Unique Patients: COUNT(DISTINCT patient_id)
    - Total Drugs: Count of selected/filtered drugs
    - Total Cost: Sum of costs in filtered data
    - Match Rate: Indication match percentage

    Layout: Responsive flex row that wraps on smaller screens.
    KPIs update reactively when filters change (Phase 3).
    """
    return rx.hstack(
        # Unique Patients KPI - highlighted as primary metric
        kpi_card(
            value=AppState.unique_patients_display,
            label="Unique Patients",
            icon_name="users",
            highlight=True,
        ),
        # Total Drugs KPI
        kpi_card(
            value=AppState.total_drugs_display,
            label="Drug Types",
            icon_name="pill",
            highlight=False,
        ),
        # Total Cost KPI
        kpi_card(
            value=AppState.total_cost_display,
            label="Total Cost",
            icon_name="pound-sterling",
            highlight=False,
        ),
        # Indication Match Rate KPI
        kpi_card(
            value=AppState.match_rate_display,
            label="Indication Match",
            icon_name="circle-check",
            highlight=False,
        ),
        spacing="4",
        width="100%",
        flex_wrap="wrap",
        align="stretch",
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
