"""
Configuration module for NHS High-Cost Drug Patient Pathway Analysis Tool.

Contains PathConfig dataclass for centralizing all file path references.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PathConfig:
    """
    Centralizes all file paths used across the application.

    Provides a single source of truth for file locations, making it easier to:
    - Change the data directory location
    - Support different environments (development, production)
    - Validate that required files exist

    Attributes:
        base_dir: Root directory of the application (defaults to current working directory)
        data_dir: Directory containing reference data files
        images_dir: Directory containing UI assets and fonts
    """

    base_dir: Path = field(default_factory=Path.cwd)
    _data_dir: Optional[Path] = field(default=None, repr=False)
    _images_dir: Optional[Path] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Set default subdirectories relative to base_dir if not provided."""
        if self._data_dir is None:
            self._data_dir = self.base_dir / "data"
        if self._images_dir is None:
            self._images_dir = self.base_dir / "images"

    @property
    def data_dir(self) -> Path:
        """Directory containing reference data files."""
        # _data_dir is always set after __post_init__
        assert self._data_dir is not None
        return self._data_dir

    @property
    def images_dir(self) -> Path:
        """Directory containing UI assets and fonts."""
        # _images_dir is always set after __post_init__
        assert self._images_dir is not None
        return self._images_dir

    # Reference data files (read-only lookups)
    @property
    def drugnames_csv(self) -> Path:
        """Drug name standardization mapping."""
        return self.data_dir / "drugnames.csv"

    @property
    def directory_list_csv(self) -> Path:
        """Medical specialties/directories list."""
        return self.data_dir / "directory_list.csv"

    @property
    def treatment_function_codes_csv(self) -> Path:
        """NHS treatment function code mappings."""
        return self.data_dir / "treatment_function_codes.csv"

    @property
    def drug_directory_list_csv(self) -> Path:
        """Valid drug-to-directory mappings (pipe-separated)."""
        return self.data_dir / "drug_directory_list.csv"

    @property
    def org_codes_csv(self) -> Path:
        """Provider code to organization name mapping."""
        return self.data_dir / "org_codes.csv"

    @property
    def include_csv(self) -> Path:
        """Drug filter list with default selections."""
        return self.data_dir / "include.csv"

    @property
    def default_trusts_csv(self) -> Path:
        """NHS Trust list for filter."""
        return self.data_dir / "defaultTrusts.csv"

    # Output/diagnostic files
    @property
    def na_directory_rows_csv(self) -> Path:
        """Exported rows with unresolved Directory for diagnostics."""
        return self.data_dir / "na_directory_rows.csv"

    @property
    def ta_recommendations_xlsx(self) -> Path:
        """NICE TA recommendations (downloaded from web)."""
        return self.data_dir / "ta-recommendations.xlsx"

    # UI assets
    @property
    def font_medium(self) -> Path:
        """AvenirLTStd-Medium font file."""
        return self.images_dir / "AvenirLTStd-Medium.ttf"

    @property
    def font_roman(self) -> Path:
        """AvenirLTStd-Roman font file."""
        return self.images_dir / "AvenirLTStd-Roman.ttf"

    @property
    def logo_ico(self) -> Path:
        """Application icon."""
        return self.images_dir / "logo.ico"

    @property
    def logo_png(self) -> Path:
        """Application logo."""
        return self.images_dir / "logo.png"

    def validate(self) -> list[str]:
        """
        Validate that required files and directories exist.

        Returns:
            List of error messages. Empty list means all validations passed.
        """
        errors = []

        # Check directories exist
        if not self.data_dir.exists():
            errors.append(f"Data directory not found: {self.data_dir}")
        if not self.images_dir.exists():
            errors.append(f"Images directory not found: {self.images_dir}")

        # Check required reference files
        required_files = [
            (self.drugnames_csv, "Drug names mapping"),
            (self.directory_list_csv, "Directory list"),
            (self.treatment_function_codes_csv, "Treatment function codes"),
            (self.drug_directory_list_csv, "Drug-directory mapping"),
            (self.org_codes_csv, "Organization codes"),
            (self.include_csv, "Drug include list"),
            (self.default_trusts_csv, "Default trusts"),
        ]

        for file_path, description in required_files:
            if not file_path.exists():
                errors.append(f"{description} not found: {file_path}")

        return errors

    def validate_fonts(self) -> list[str]:
        """
        Validate that font files exist (for GUI mode).

        Returns:
            List of error messages. Empty list means all validations passed.
        """
        errors = []

        font_files = [
            (self.font_medium, "Medium font"),
            (self.font_roman, "Roman font"),
        ]

        for file_path, description in font_files:
            if not file_path.exists():
                errors.append(f"{description} not found: {file_path}")

        return errors

    def as_legacy_paths(self) -> dict[str, str]:
        """
        Return paths as strings with './' prefix for backwards compatibility.

        This method eases migration by providing paths in the format
        currently used throughout the codebase.

        Returns:
            Dictionary mapping path names to legacy-format string paths.
        """
        return {
            "drugnames_csv": f"./{self.drugnames_csv.relative_to(self.base_dir)}",
            "directory_list_csv": f"./{self.directory_list_csv.relative_to(self.base_dir)}",
            "treatment_function_codes_csv": f"./{self.treatment_function_codes_csv.relative_to(self.base_dir)}",
            "drug_directory_list_csv": f"./{self.drug_directory_list_csv.relative_to(self.base_dir)}",
            "org_codes_csv": f"./{self.org_codes_csv.relative_to(self.base_dir)}",
            "include_csv": f"./{self.include_csv.relative_to(self.base_dir)}",
            "default_trusts_csv": f"./{self.default_trusts_csv.relative_to(self.base_dir)}",
            "na_directory_rows_csv": f"./{self.na_directory_rows_csv.relative_to(self.base_dir)}",
            "ta_recommendations_xlsx": f"./{self.ta_recommendations_xlsx.relative_to(self.base_dir)}",
        }


# Default instance for application-wide use
default_paths = PathConfig()
