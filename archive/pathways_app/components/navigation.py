"""
Navigation components for the Patient Pathway Analysis tool.

Provides sidebar navigation items with icons, matching the CustomTkinter design.
Includes accessibility features: ARIA labels, keyboard navigation, focus indicators.
"""

import reflex as rx
from typing import Callable


def nav_item(
    text: str,
    href: str,
    icon: str,
    is_active: bool = False,
) -> rx.Component:
    """
    Create a navigation item with icon.

    Args:
        text: The display text for the nav item
        href: The route to navigate to
        icon: The Lucide icon name (e.g., "home", "pill", "building", "folder")
        is_active: Whether this item is currently active

    Returns:
        A styled navigation button component with accessibility support
    """
    # NHS colors - use blue for active state
    active_bg = "rgb(0, 94, 184)"  # NHS Blue
    hover_bg = "rgb(0, 48, 135)"   # NHS Dark Blue

    return rx.link(
        rx.hstack(
            rx.icon(icon, size=20, aria_hidden="true"),  # Hide decorative icon from screen readers
            rx.text(text, size="3", weight="medium"),
            width="100%",
            padding="12px 16px",
            spacing="3",
            align="center",
            border_radius="8px",
            bg=rx.cond(is_active, active_bg, "transparent"),
            color=rx.cond(is_active, "white", "inherit"),
            _hover={
                "background": rx.cond(is_active, active_bg, "rgba(0, 94, 184, 0.1)"),
            },
            _focus_visible={
                "outline": "2px solid rgb(0, 94, 184)",
                "outline_offset": "2px",
            },
            transition="background 0.2s ease",
        ),
        href=href,
        text_decoration="none",
        width="100%",
        aria_current=rx.cond(is_active, "page", ""),
    )


def nav_section(title: str, children: list[rx.Component]) -> rx.Component:
    """
    Create a labeled section of navigation items.

    Args:
        title: Section header text
        children: List of nav_item components

    Returns:
        A styled section with header and items
    """
    return rx.vstack(
        rx.text(
            title,
            size="1",
            weight="bold",
            color="gray",
            padding_x="16px",
            padding_top="16px",
            padding_bottom="8px",
        ),
        *children,
        width="100%",
        spacing="1",
        align="start",
    )
