"""
Layout components for the Patient Pathway Analysis tool.

Provides the main application layout with sidebar navigation and content area.
Includes accessibility features: skip links, ARIA landmarks, keyboard navigation.
"""

import reflex as rx
from .navigation import nav_item


# NHS Color scheme
NHS_BLUE = "rgb(0, 94, 184)"
NHS_DARK_BLUE = "rgb(0, 48, 135)"
NHS_LIGHT_BLUE = "rgb(65, 182, 230)"
NHS_WHITE = "white"
NHS_GREY = "rgb(231, 231, 231)"


def skip_link() -> rx.Component:
    """
    Skip link for keyboard users to bypass navigation.

    Visually hidden until focused, allowing keyboard users to skip
    directly to main content.
    """
    return rx.link(
        "Skip to main content",
        href="#main-content",
        position="absolute",
        top="-40px",
        left="0",
        background=NHS_BLUE,
        color="white",
        padding="8px 16px",
        z_index="1000",
        text_decoration="none",
        font_weight="bold",
        _focus={
            "top": "0",
        },
    )


def logo_section() -> rx.Component:
    """NHS branding logo section at top of sidebar."""
    return rx.hstack(
        rx.image(
            src="/logo.png",
            height="32px",
            alt="NHS Norfolk and Waveney Logo",
        ),
        rx.text(
            "HCD Analysis",
            size="5",
            weight="bold",
            color=NHS_BLUE,
        ),
        padding="16px",
        spacing="3",
        align="center",
        width="100%",
        border_bottom=f"1px solid {NHS_GREY}",
    )


def sidebar(current_page: str = "home") -> rx.Component:
    """
    Create the sidebar navigation panel.

    Args:
        current_page: The current active page name for highlighting

    Returns:
        A sidebar component with navigation items and ARIA landmark
    """
    return rx.el.nav(
        rx.vstack(
            # Logo section
            logo_section(),
            # Navigation items
            rx.vstack(
                nav_item(
                    "Home",
                    "/",
                    "home",
                    is_active=(current_page == "home"),
                ),
                nav_item(
                    "Drug Selection",
                    "/drugs",
                    "pill",
                    is_active=(current_page == "drugs"),
                ),
                nav_item(
                    "Trust Selection",
                    "/trusts",
                    "building",
                    is_active=(current_page == "trusts"),
                ),
                nav_item(
                    "Directory Selection",
                    "/directories",
                    "folder",
                    is_active=(current_page == "directories"),
                ),
                padding="8px",
                spacing="1",
                width="100%",
                align="start",
            ),
            # Spacer to push theme toggle to bottom
            rx.spacer(),
            # Theme toggle at bottom
            rx.box(
                rx.hstack(
                    rx.el.label(
                        "Theme:",
                        html_for="theme-toggle",
                        font_size="14px",
                        color="gray",
                    ),
                    rx.color_mode.switch(id="theme-toggle"),
                    spacing="2",
                    align="center",
                ),
                padding="16px",
                border_top=f"1px solid {NHS_GREY}",
                width="100%",
            ),
            height="100vh",
            width="100%",
            spacing="0",
            align="start",
        ),
        aria_label="Main navigation",
        width="240px",
        min_width="240px",
        background="white",
        border_right=f"1px solid {NHS_GREY}",
        position="fixed",
        left="0",
        top="0",
        height="100vh",
        overflow_y="auto",
        z_index="100",
    )


def navbar() -> rx.Component:
    """
    Create a top navigation bar for mobile/smaller screens.

    Returns:
        A horizontal navbar component (collapsed sidebar for mobile) with ARIA support
    """
    return rx.el.header(
        rx.hstack(
            rx.image(src="/logo.png", height="28px", alt="NHS Norfolk and Waveney Logo"),
            rx.text("HCD Analysis", size="4", weight="bold"),
            rx.spacer(),
            rx.el.label(
                rx.color_mode.switch(id="theme-toggle-mobile"),
                html_for="theme-toggle-mobile",
                aria_label="Toggle dark mode",
            ),
            width="100%",
            padding="12px 16px",
            align="center",
            justify="between",
        ),
        background="white",
        border_bottom=f"1px solid {NHS_GREY}",
        display=["flex", "flex", "none"],  # Show on mobile, hide on desktop
        width="100%",
        position="fixed",
        top="0",
        left="0",
        z_index="100",
        role="banner",
    )


def content_area(*children, page_title: str = "") -> rx.Component:
    """
    Create the main content area.

    Args:
        *children: Child components to render in the content area
        page_title: Optional title to display at top of content

    Returns:
        A styled content area component with ARIA main landmark
    """
    content_children = list(children)

    if page_title:
        content_children.insert(
            0,
            rx.heading(
                page_title,
                size="6",
                weight="bold",
                color=NHS_DARK_BLUE,
                margin_bottom="16px",
            ),
        )

    return rx.el.main(
        rx.vstack(
            *content_children,
            width="100%",
            max_width="1200px",
            padding="24px",
            spacing="4",
            align="start",
        ),
        id="main-content",
        tabindex="-1",  # Allow focus for skip link
        # Offset for sidebar on desktop
        margin_left=["0", "0", "240px"],
        # Offset for navbar on mobile
        margin_top=["60px", "60px", "0"],
        min_height="100vh",
        background=rx.color_mode_cond(
            light="rgb(249, 250, 251)",  # Light gray background
            dark="rgb(17, 24, 39)",      # Dark background
        ),
        width="100%",
        _focus={
            "outline": "none",  # Hide focus ring on main (only accessible via skip link)
        },
    )


def main_layout(
    content: rx.Component,
    current_page: str = "home",
) -> rx.Component:
    """
    Create the complete page layout with sidebar and content.

    Args:
        content: The main content to display
        current_page: The current page name for navigation highlighting

    Returns:
        A complete page layout component with accessibility features
    """
    return rx.fragment(
        # Skip link for keyboard users
        skip_link(),
        # Sidebar (visible on desktop)
        rx.box(
            sidebar(current_page=current_page),
            display=["none", "none", "block"],  # Hide on mobile
        ),
        # Navbar (visible on mobile)
        navbar(),
        # Main content
        content,
    )
