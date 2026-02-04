"""
Tests for core/config.py - PathConfig dataclass.

Tests cover:
- Default path construction
- Custom path configuration
- Path property access
- validate() method for file existence checks
- validate_fonts() method for font file checks
- as_legacy_paths() method for backwards compatibility
"""

from pathlib import Path

import pytest

from core.config import PathConfig


class TestPathConfigDefaults:
    """Test default behavior of PathConfig."""

    def test_default_base_dir_is_cwd(self):
        """Default base_dir should be current working directory."""
        config = PathConfig()
        assert config.base_dir == Path.cwd()

    def test_default_data_dir_is_under_base(self):
        """Default data_dir should be 'data' under base_dir."""
        config = PathConfig()
        assert config.data_dir == config.base_dir / "data"

    def test_default_images_dir_is_under_base(self):
        """Default images_dir should be 'images' under base_dir."""
        config = PathConfig()
        assert config.images_dir == config.base_dir / "images"


class TestPathConfigCustomPaths:
    """Test custom path configuration."""

    def test_custom_base_dir(self, temp_dir: Path):
        """PathConfig should accept custom base_dir."""
        config = PathConfig(base_dir=temp_dir)
        assert config.base_dir == temp_dir
        assert config.data_dir == temp_dir / "data"
        assert config.images_dir == temp_dir / "images"


class TestPathConfigProperties:
    """Test path property accessors."""

    def test_drugnames_csv_path(self):
        """drugnames_csv should point to correct file."""
        config = PathConfig()
        assert config.drugnames_csv == config.data_dir / "drugnames.csv"

    def test_directory_list_csv_path(self):
        """directory_list_csv should point to correct file."""
        config = PathConfig()
        assert config.directory_list_csv == config.data_dir / "directory_list.csv"

    def test_treatment_function_codes_csv_path(self):
        """treatment_function_codes_csv should point to correct file."""
        config = PathConfig()
        assert config.treatment_function_codes_csv == config.data_dir / "treatment_function_codes.csv"

    def test_drug_directory_list_csv_path(self):
        """drug_directory_list_csv should point to correct file."""
        config = PathConfig()
        assert config.drug_directory_list_csv == config.data_dir / "drug_directory_list.csv"

    def test_org_codes_csv_path(self):
        """org_codes_csv should point to correct file."""
        config = PathConfig()
        assert config.org_codes_csv == config.data_dir / "org_codes.csv"

    def test_include_csv_path(self):
        """include_csv should point to correct file."""
        config = PathConfig()
        assert config.include_csv == config.data_dir / "include.csv"

    def test_default_trusts_csv_path(self):
        """default_trusts_csv should point to correct file."""
        config = PathConfig()
        assert config.default_trusts_csv == config.data_dir / "defaultTrusts.csv"

    def test_font_medium_path(self):
        """font_medium should point to correct file."""
        config = PathConfig()
        assert config.font_medium == config.images_dir / "AvenirLTStd-Medium.ttf"

    def test_font_roman_path(self):
        """font_roman should point to correct file."""
        config = PathConfig()
        assert config.font_roman == config.images_dir / "AvenirLTStd-Roman.ttf"


class TestPathConfigValidate:
    """Test validate() method."""

    def test_validate_passes_when_all_files_exist(self, mock_project_dir: Path):
        """validate() should return empty list when all files exist."""
        config = PathConfig(base_dir=mock_project_dir)
        errors = config.validate()
        assert errors == []

    def test_validate_fails_when_data_dir_missing(self, temp_dir: Path):
        """validate() should report missing data directory."""
        # Create images dir but not data dir
        (temp_dir / "images").mkdir()
        config = PathConfig(base_dir=temp_dir)

        errors = config.validate()

        assert len(errors) >= 1
        assert any("Data directory not found" in e for e in errors)

    def test_validate_fails_when_images_dir_missing(self, temp_dir: Path):
        """validate() should report missing images directory."""
        # Create data dir but not images dir
        (temp_dir / "data").mkdir()
        config = PathConfig(base_dir=temp_dir)

        errors = config.validate()

        assert len(errors) >= 1
        assert any("Images directory not found" in e for e in errors)

    def test_validate_fails_when_required_file_missing(self, temp_dir: Path):
        """validate() should report missing required files."""
        # Create directories but only some files
        data_dir = temp_dir / "data"
        data_dir.mkdir()
        (temp_dir / "images").mkdir()

        # Create only one file
        (data_dir / "drugnames.csv").touch()

        config = PathConfig(base_dir=temp_dir)
        errors = config.validate()

        # Should report 6 missing files (7 total - 1 created)
        # Exclude directory-related messages (data/images directory checks)
        # but include files that have "directory" in the filename
        missing_file_errors = [
            e for e in errors
            if "not found" in e
            and "Data directory not found" not in e
            and "Images directory not found" not in e
        ]
        assert len(missing_file_errors) == 6


class TestPathConfigValidateFonts:
    """Test validate_fonts() method."""

    def test_validate_fonts_passes_when_fonts_exist(self, mock_project_dir: Path):
        """validate_fonts() should return empty list when fonts exist."""
        config = PathConfig(base_dir=mock_project_dir)
        errors = config.validate_fonts()
        assert errors == []

    def test_validate_fonts_fails_when_medium_font_missing(self, temp_dir: Path):
        """validate_fonts() should report missing medium font."""
        images_dir = temp_dir / "images"
        images_dir.mkdir()
        # Create only roman font
        (images_dir / "AvenirLTStd-Roman.ttf").touch()

        config = PathConfig(base_dir=temp_dir)
        errors = config.validate_fonts()

        assert len(errors) == 1
        assert "Medium font not found" in errors[0]

    def test_validate_fonts_fails_when_roman_font_missing(self, temp_dir: Path):
        """validate_fonts() should report missing roman font."""
        images_dir = temp_dir / "images"
        images_dir.mkdir()
        # Create only medium font
        (images_dir / "AvenirLTStd-Medium.ttf").touch()

        config = PathConfig(base_dir=temp_dir)
        errors = config.validate_fonts()

        assert len(errors) == 1
        assert "Roman font not found" in errors[0]


class TestPathConfigLegacyPaths:
    """Test as_legacy_paths() method for backwards compatibility."""

    def test_legacy_paths_returns_dict(self, temp_dir: Path):
        """as_legacy_paths() should return a dictionary."""
        config = PathConfig(base_dir=temp_dir)
        legacy = config.as_legacy_paths()
        assert isinstance(legacy, dict)

    def test_legacy_paths_contains_expected_keys(self, temp_dir: Path):
        """as_legacy_paths() should contain all expected keys."""
        config = PathConfig(base_dir=temp_dir)
        legacy = config.as_legacy_paths()

        expected_keys = [
            "drugnames_csv",
            "directory_list_csv",
            "treatment_function_codes_csv",
            "drug_directory_list_csv",
            "org_codes_csv",
            "include_csv",
            "default_trusts_csv",
            "na_directory_rows_csv",
            "ta_recommendations_xlsx",
        ]

        for key in expected_keys:
            assert key in legacy

    def test_legacy_paths_have_dot_slash_prefix(self, temp_dir: Path):
        """as_legacy_paths() values should start with './'."""
        config = PathConfig(base_dir=temp_dir)
        legacy = config.as_legacy_paths()

        for key, value in legacy.items():
            assert value.startswith("./"), f"{key} should start with ./ but got {value}"
