"""
Pytest configuration and fixtures for the test suite.

This module provides shared fixtures used across multiple test modules.
"""

import tempfile
from datetime import date
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_data_dir(temp_dir: Path) -> Path:
    """
    Create a mock data directory with empty reference files.

    Creates the expected directory structure and empty placeholder files
    so that PathConfig.validate() can pass file existence checks.
    """
    data_dir = temp_dir / "data"
    data_dir.mkdir()

    # Create empty reference files
    reference_files = [
        "drugnames.csv",
        "directory_list.csv",
        "treatment_function_codes.csv",
        "drug_directory_list.csv",
        "org_codes.csv",
        "include.csv",
        "defaultTrusts.csv",
    ]

    for filename in reference_files:
        (data_dir / filename).touch()

    return data_dir


@pytest.fixture
def mock_images_dir(temp_dir: Path) -> Path:
    """
    Create a mock images directory with empty font files.

    Creates the expected directory structure and empty placeholder files
    so that PathConfig.validate_fonts() can pass file existence checks.
    """
    images_dir = temp_dir / "images"
    images_dir.mkdir()

    # Create empty font files
    font_files = [
        "AvenirLTStd-Medium.ttf",
        "AvenirLTStd-Roman.ttf",
        "logo.ico",
        "logo.png",
    ]

    for filename in font_files:
        (images_dir / filename).touch()

    return images_dir


@pytest.fixture
def mock_project_dir(temp_dir: Path, mock_data_dir: Path, mock_images_dir: Path) -> Path:
    """
    Create a complete mock project directory structure.

    Combines data and images directories for full PathConfig validation.
    """
    return temp_dir


@pytest.fixture
def sample_date_range() -> tuple[date, date, date]:
    """
    Return a sample valid date range for testing AnalysisFilters.

    Returns:
        Tuple of (start_date, end_date, last_seen_date)
    """
    return (
        date(2024, 1, 1),   # start_date
        date(2024, 12, 31), # end_date
        date(2024, 6, 1),   # last_seen_date
    )


@pytest.fixture
def sample_trusts() -> list[str]:
    """Return a sample list of NHS trust names for testing."""
    return [
        "MANCHESTER UNIVERSITY NHS FOUNDATION TRUST",
        "LEEDS TEACHING HOSPITALS NHS TRUST",
        "SHEFFIELD TEACHING HOSPITALS NHS FOUNDATION TRUST",
    ]


@pytest.fixture
def sample_drugs() -> list[str]:
    """Return a sample list of drug names for testing."""
    return [
        "ADALIMUMAB",
        "ETANERCEPT",
        "INFLIXIMAB",
        "RITUXIMAB",
    ]


@pytest.fixture
def sample_directories() -> list[str]:
    """Return a sample list of medical directories for testing."""
    return [
        "RHEUMATOLOGY",
        "DERMATOLOGY",
        "GASTROENTEROLOGY",
    ]
