"""
Tests for core/models.py - AnalysisFilters dataclass.

Tests cover:
- Basic instantiation
- validate() method for filter validation
- Property accessors (has_trust_filter, etc.)
- title property (custom vs auto-generated)
- summary() method
"""

from datetime import date
from pathlib import Path

import pytest

from core.models import AnalysisFilters


class TestAnalysisFiltersBasic:
    """Test basic AnalysisFilters instantiation and access."""

    def test_create_with_required_dates(self, sample_date_range):
        """Should be able to create AnalysisFilters with just dates."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.start_date == start
        assert filters.end_date == end
        assert filters.last_seen_date == last_seen

    def test_default_lists_are_empty(self, sample_date_range):
        """Default filter lists should be empty."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.trusts == []
        assert filters.drugs == []
        assert filters.directories == []

    def test_default_minimum_patients_is_zero(self, sample_date_range):
        """Default minimum_patients should be 0."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.minimum_patients == 0

    def test_default_custom_title_is_empty(self, sample_date_range):
        """Default custom_title should be empty string."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.custom_title == ""


class TestAnalysisFiltersValidate:
    """Test validate() method."""

    def test_validate_passes_valid_config(self, sample_date_range):
        """validate() should return empty list for valid configuration."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        errors = filters.validate()
        assert errors == []

    def test_validate_fails_when_end_before_start(self):
        """validate() should fail when end_date is before start_date."""
        filters = AnalysisFilters(
            start_date=date(2024, 12, 31),  # Later
            end_date=date(2024, 1, 1),       # Earlier
            last_seen_date=date(2024, 6, 1),
        )

        errors = filters.validate()

        assert len(errors) >= 1
        assert any("cannot be before start date" in e for e in errors)

    def test_validate_fails_when_last_seen_after_end(self):
        """validate() should fail when last_seen_date is after end_date."""
        filters = AnalysisFilters(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            last_seen_date=date(2024, 12, 31),  # After end_date
        )

        errors = filters.validate()

        assert len(errors) >= 1
        assert any("would exclude all patients" in e for e in errors)

    def test_validate_fails_when_minimum_patients_negative(self, sample_date_range):
        """validate() should fail when minimum_patients is negative."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            minimum_patients=-1,
        )

        errors = filters.validate()

        assert len(errors) >= 1
        assert any("cannot be negative" in e for e in errors)

    def test_validate_fails_when_output_dir_missing(self, sample_date_range, temp_dir: Path):
        """validate() should fail when output_dir doesn't exist."""
        start, end, last_seen = sample_date_range
        nonexistent_dir = temp_dir / "nonexistent"

        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            output_dir=nonexistent_dir,
        )

        errors = filters.validate()

        assert len(errors) >= 1
        assert any("does not exist" in e for e in errors)

    def test_validate_passes_when_output_dir_exists(self, sample_date_range, temp_dir: Path):
        """validate() should pass when output_dir exists."""
        start, end, last_seen = sample_date_range
        output_dir = temp_dir / "output"
        output_dir.mkdir()

        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            output_dir=output_dir,
        )

        errors = filters.validate()
        assert errors == []

    def test_validate_multiple_errors(self):
        """validate() should report all errors, not just the first."""
        filters = AnalysisFilters(
            start_date=date(2024, 12, 31),  # End before start
            end_date=date(2024, 1, 1),
            last_seen_date=date(2024, 6, 1),
            minimum_patients=-5,            # Negative
        )

        errors = filters.validate()

        assert len(errors) >= 2


class TestAnalysisFiltersHasFilters:
    """Test has_*_filter properties."""

    def test_has_trust_filter_false_when_empty(self, sample_date_range):
        """has_trust_filter should be False when trusts list is empty."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.has_trust_filter is False

    def test_has_trust_filter_true_when_populated(self, sample_date_range, sample_trusts):
        """has_trust_filter should be True when trusts list has items."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            trusts=sample_trusts,
        )

        assert filters.has_trust_filter is True

    def test_has_drug_filter_false_when_empty(self, sample_date_range):
        """has_drug_filter should be False when drugs list is empty."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.has_drug_filter is False

    def test_has_drug_filter_true_when_populated(self, sample_date_range, sample_drugs):
        """has_drug_filter should be True when drugs list has items."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            drugs=sample_drugs,
        )

        assert filters.has_drug_filter is True

    def test_has_directory_filter_false_when_empty(self, sample_date_range):
        """has_directory_filter should be False when directories list is empty."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert filters.has_directory_filter is False

    def test_has_directory_filter_true_when_populated(self, sample_date_range, sample_directories):
        """has_directory_filter should be True when directories list has items."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            directories=sample_directories,
        )

        assert filters.has_directory_filter is True


class TestAnalysisFiltersTitle:
    """Test title property."""

    def test_title_returns_custom_when_set(self, sample_date_range):
        """title should return custom_title when set."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            custom_title="My Custom Analysis",
        )

        assert filters.title == "My Custom Analysis"

    def test_title_auto_generates_when_not_set(self, sample_date_range):
        """title should auto-generate from dates when custom_title is empty."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        assert "2024-01-01" in filters.title
        assert "2024-12-31" in filters.title

    def test_title_auto_generated_includes_dates(self):
        """Auto-generated title should include start and end dates."""
        filters = AnalysisFilters(
            start_date=date(2023, 6, 15),
            end_date=date(2024, 3, 20),
            last_seen_date=date(2024, 1, 1),
        )

        assert "2023-06-15" in filters.title
        assert "2024-03-20" in filters.title


class TestAnalysisFiltersSummary:
    """Test summary() method."""

    def test_summary_returns_string(self, sample_date_range):
        """summary() should return a string."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        summary = filters.summary()
        assert isinstance(summary, str)

    def test_summary_includes_date_range(self, sample_date_range):
        """summary() should include date range information."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        summary = filters.summary()
        assert "Date range" in summary
        assert "2024-01-01" in summary or str(start) in summary

    def test_summary_includes_minimum_patients(self, sample_date_range):
        """summary() should include minimum patients value."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            minimum_patients=10,
        )

        summary = filters.summary()
        assert "Minimum patients" in summary
        assert "10" in summary

    def test_summary_shows_all_when_no_filters(self, sample_date_range):
        """summary() should show 'All' when filter lists are empty."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
        )

        summary = filters.summary()
        assert "Trusts: All" in summary
        assert "Drugs: All" in summary
        assert "Directories: All" in summary

    def test_summary_shows_count_when_filters_set(
        self, sample_date_range, sample_trusts, sample_drugs, sample_directories
    ):
        """summary() should show count when filter lists are populated."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            trusts=sample_trusts,
            drugs=sample_drugs,
            directories=sample_directories,
        )

        summary = filters.summary()
        assert "3 selected" in summary  # trusts count
        assert "4 selected" in summary  # drugs count

    def test_summary_includes_custom_title_when_set(self, sample_date_range):
        """summary() should include custom title when set."""
        start, end, last_seen = sample_date_range
        filters = AnalysisFilters(
            start_date=start,
            end_date=end,
            last_seen_date=last_seen,
            custom_title="Special Analysis",
        )

        summary = filters.summary()
        assert "Custom title" in summary
        assert "Special Analysis" in summary
