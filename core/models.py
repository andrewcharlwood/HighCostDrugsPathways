"""
Data models for NHS High-Cost Drug Patient Pathway Analysis Tool.

Contains dataclasses for encapsulating application state and filter parameters.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class AnalysisFilters:
    """
    Encapsulates all filter state for the analysis pipeline.

    Replaces the individual parameters currently passed to generate_graph()
    and the global state managed in the GUI. This provides:
    - Type safety for filter values
    - Validation of filter combinations
    - Easy serialization for caching/persistence
    - Clear interface between GUI and analysis engine

    Attributes:
        start_date: Patient initiated start date (treatment pathway start)
        end_date: Patient initiated end date (treatment pathway start cutoff)
        last_seen_date: Minimum last seen date (filters out patients not seen recently)
        trusts: List of NHS Trust names to include (empty = all)
        drugs: List of drug names to include (empty = all)
        directories: List of medical directories/specialties to include (empty = all)
        custom_title: Optional custom title for the graph (blank = auto-generated)
        minimum_patients: Minimum number of patients for a pathway to be included
        output_dir: Directory where output files should be saved
    """

    start_date: date
    end_date: date
    last_seen_date: date
    trusts: list[str] = field(default_factory=list)
    drugs: list[str] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    custom_title: str = ""
    minimum_patients: int = 0
    output_dir: Optional[Path] = None

    def validate(self) -> list[str]:
        """
        Validate filter configuration for logical consistency.

        Returns:
            List of error messages. Empty list means all validations passed.
        """
        errors = []

        # Date range validation
        if self.end_date < self.start_date:
            errors.append(
                f"End date ({self.end_date}) cannot be before start date ({self.start_date})"
            )

        if self.last_seen_date > self.end_date:
            errors.append(
                f"Last seen date ({self.last_seen_date}) is after end date ({self.end_date}), "
                "which would exclude all patients"
            )

        # Minimum patients validation
        if self.minimum_patients < 0:
            errors.append(
                f"Minimum patients ({self.minimum_patients}) cannot be negative"
            )

        # Output directory validation
        if self.output_dir is not None and not self.output_dir.exists():
            errors.append(f"Output directory does not exist: {self.output_dir}")

        # Filter list validation (warn if empty but don't error)
        # Empty lists are valid and mean "include all"

        return errors

    @property
    def has_trust_filter(self) -> bool:
        """Check if any trust filter is applied."""
        return len(self.trusts) > 0

    @property
    def has_drug_filter(self) -> bool:
        """Check if any drug filter is applied."""
        return len(self.drugs) > 0

    @property
    def has_directory_filter(self) -> bool:
        """Check if any directory filter is applied."""
        return len(self.directories) > 0

    @property
    def title(self) -> str:
        """
        Return the display title for the graph.

        If custom_title is set, use it. Otherwise, generate a default title
        based on the date range.
        """
        if self.custom_title:
            return self.custom_title
        return f"Patients initiated from {self.start_date} to {self.end_date}"

    def summary(self) -> str:
        """
        Return a human-readable summary of the filter configuration.

        Useful for logging and display in the GUI.
        """
        lines = [
            f"Date range: {self.start_date} to {self.end_date}",
            f"Last seen after: {self.last_seen_date}",
            f"Minimum patients: {self.minimum_patients}",
        ]

        if self.trusts:
            lines.append(f"Trusts: {len(self.trusts)} selected")
        else:
            lines.append("Trusts: All")

        if self.drugs:
            lines.append(f"Drugs: {len(self.drugs)} selected")
        else:
            lines.append("Drugs: All")

        if self.directories:
            lines.append(f"Directories: {len(self.directories)} selected")
        else:
            lines.append("Directories: All")

        if self.custom_title:
            lines.append(f"Custom title: {self.custom_title}")

        return "\n".join(lines)
