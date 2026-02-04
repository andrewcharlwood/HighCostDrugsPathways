"""
Logging configuration for NHS High-Cost Drug Patient Pathway Analysis Tool.

Provides structured logging setup with console and optional file handlers.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Default log format: timestamp, level, module name, message
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Simplified format for console output (used when redirecting to GUI)
SIMPLE_FORMAT = "%(message)s"


def setup_logging(
    level: int = logging.INFO,
    log_dir: Optional[Path] = None,
    console: bool = True,
    file_logging: bool = False,
    simple_console: bool = False,
) -> logging.Logger:
    """
    Configure application-wide logging.

    Args:
        level: Logging level (default: INFO)
        log_dir: Directory for log files (default: ./logs/)
        console: Whether to log to console/stdout (default: True)
        file_logging: Whether to log to file (default: False)
        simple_console: Use simplified format for console (just message, no timestamp)

    Returns:
        Root logger configured for the application

    Usage:
        # Basic setup - console only
        logger = setup_logging()

        # With file logging
        logger = setup_logging(file_logging=True)

        # Debug mode
        logger = setup_logging(level=logging.DEBUG)

        # GUI mode - simple format for stdout capture
        logger = setup_logging(simple_console=True)
    """
    # Get root logger for the application
    root_logger = logging.getLogger("pathways")

    # Clear any existing handlers to avoid duplicates on re-initialization
    root_logger.handlers.clear()

    root_logger.setLevel(level)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        if simple_console:
            console_format = logging.Formatter(SIMPLE_FORMAT)
        else:
            console_format = logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)

        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)

    # File handler
    if file_logging:
        if log_dir is None:
            log_dir = Path("./logs")

        log_dir.mkdir(parents=True, exist_ok=True)

        log_filename = f"pathways_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_path = log_dir / log_filename

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance configured as child of root pathways logger

    Usage:
        from core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Processing started")
        logger.error("Something went wrong")
    """
    # Create child logger under the pathways namespace
    if name.startswith("pathways."):
        return logging.getLogger(name)
    return logging.getLogger(f"pathways.{name}")


# Module-level loggers for common components
data_logger = get_logger("data")
dashboard_logger = get_logger("dashboard")
gui_logger = get_logger("gui")
