"""
Data loader abstractions for NHS High-Cost Drug Patient Pathway Analysis Tool.

Provides a unified interface for loading patient intervention data from:
- CSV/Parquet files (current behavior)
- SQLite database (new, faster approach)
- Snowflake (future, direct from warehouse)

The DataLoader ABC defines the contract for all loader implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from core import PathConfig, default_paths
from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class LoadResult:
    """Result of a data load operation.

    Attributes:
        df: The loaded DataFrame with processed patient intervention data
        source: Description of the data source (e.g., "file:/path/to/file.csv")
        row_count: Number of rows loaded
        columns: List of column names in the DataFrame
        load_time_seconds: Time taken to load the data
    """
    df: pd.DataFrame
    source: str
    row_count: int
    columns: list[str] = field(default_factory=list)
    load_time_seconds: float = 0.0

    def __post_init__(self):
        if not self.columns:
            self.columns = list(self.df.columns)


# Expected columns in a processed DataFrame
# These are the columns that generate_graph() expects to receive
REQUIRED_COLUMNS = [
    "UPID",           # Unique Patient ID (Provider Code prefix + PersonKey)
    "Drug Name",      # Standardized drug name
    "Intervention Date",  # Date of intervention
    "Price Actual",   # Cost of intervention
    "OrganisationName",  # NHS Trust name
    "Directory",      # Medical specialty/directory
    "Provider Code",  # NHS provider code
    "PersonKey",      # Patient identifier within provider
]

# Additional columns that are useful but not strictly required
OPTIONAL_COLUMNS = [
    "UPIDTreatment",  # UPID + Drug Name combo (created by generate_graph)
    "Treatment Function Code",  # NHS treatment function code
    "Additional Detail 1",
    "Additional Detail 2",
    "Additional Detail 3",
    "Additional Detail 4",
    "Additional Detail 5",
]


class DataLoader(ABC):
    """Abstract base class for data loaders.

    All data loaders must implement the load() method which returns
    a DataFrame ready for use by generate_graph().

    The returned DataFrame must contain REQUIRED_COLUMNS at minimum.
    """

    @abstractmethod
    def load(self) -> LoadResult:
        """Load and process patient intervention data.

        Returns:
            LoadResult containing the processed DataFrame and metadata.
            The DataFrame must contain all REQUIRED_COLUMNS.

        Raises:
            FileNotFoundError: If the data source doesn't exist
            ValueError: If the data is malformed or missing required columns
        """
        pass

    @abstractmethod
    def validate_source(self) -> tuple[bool, str]:
        """Check if the data source is valid and accessible.

        Returns:
            Tuple of (is_valid, message).
            If is_valid is False, message explains the issue.
        """
        pass

    @property
    @abstractmethod
    def source_description(self) -> str:
        """Human-readable description of the data source."""
        pass

    def validate_dataframe(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """Validate that a DataFrame has all required columns.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (is_valid, missing_columns).
            If is_valid is False, missing_columns lists what's missing.
        """
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        return len(missing) == 0, missing


class FileDataLoader(DataLoader):
    """Loads data from CSV or Parquet files.

    This replicates the current behavior of dashboard_gui.main():
    1. Read CSV or Parquet file
    2. Apply patient_id() transformation
    3. Convert dates
    4. Apply drug_names() standardization
    5. Clean organization names
    6. Apply department_identification()

    Args:
        file_path: Path to the CSV or Parquet file
        paths: PathConfig for reference data file locations (uses default_paths if None)
    """

    def __init__(
        self,
        file_path: Path | str,
        paths: Optional[PathConfig] = None,
    ):
        self.file_path = Path(file_path)
        self.paths = paths or default_paths

    def validate_source(self) -> tuple[bool, str]:
        """Check if the file exists and has a supported extension."""
        if not self.file_path.exists():
            return False, f"File not found: {self.file_path}"

        ext = self.file_path.suffix.lower()
        if ext not in ('.csv', '.parquet'):
            return False, f"Unsupported file type: {ext}. Must be .csv or .parquet"

        return True, "OK"

    @property
    def source_description(self) -> str:
        return f"file:{self.file_path}"

    def load(self) -> LoadResult:
        """Load and process data from CSV or Parquet file.

        Applies the same transformation pipeline as the original
        dashboard_gui.main() function.
        """
        import time
        from data_processing import transforms as data

        start_time = time.time()

        # Validate source before loading
        is_valid, msg = self.validate_source()
        if not is_valid:
            raise FileNotFoundError(msg)

        # Read file based on extension
        ext = self.file_path.suffix.lower()
        logger.info(f"Reading {ext} file: {self.file_path}")

        if ext == '.csv':
            df_raw = pd.read_csv(self.file_path, low_memory=False)
        else:  # .parquet
            df_raw = pd.read_parquet(self.file_path)

        logger.info(f"File read successfully. {len(df_raw)} rows.")

        # Apply transformations (same as dashboard_gui.main())
        df = data.patient_id(df_raw)
        logger.info("Patient ID processing complete.")

        df['Intervention Date'] = pd.to_datetime(df['Intervention Date'], format="%Y-%m-%d")
        logger.info("Date conversion complete.")

        # Preserve original drug name before standardization (for SQLite storage)
        df['Drug Name Raw'] = df['Drug Name'].copy()

        df = data.drug_names(df, self.paths)
        logger.info("Drug name processing complete.")

        df['OrganisationName'] = df['OrganisationName'].str.replace(',', '')
        logger.info("Organisation name cleaning complete.")

        df = data.department_identification(df, self.paths)
        logger.info("Department identification complete.")

        # Validate result
        is_valid, missing = self.validate_dataframe(df)
        if not is_valid:
            raise ValueError(f"Processed DataFrame missing required columns: {missing}")

        load_time = time.time() - start_time
        logger.info(f"Data loading complete. {len(df)} rows in {load_time:.2f}s")

        return LoadResult(
            df=df,
            source=self.source_description,
            row_count=len(df),
            load_time_seconds=load_time,
        )


def get_loader(
    source: str | Path,
    paths: Optional[PathConfig] = None,
    **kwargs
) -> DataLoader:
    """Factory function to create the appropriate DataLoader.

    Args:
        source: File path (CSV/Parquet)
        paths: PathConfig for reference data (used by FileDataLoader)
        **kwargs: Additional arguments passed to the loader constructor

    Returns:
        Appropriate DataLoader instance

    Examples:
        >>> loader = get_loader("data/activity.csv")
        >>> loader = get_loader("data/activity.parquet")
    """
    path = Path(source)
    return FileDataLoader(file_path=path, paths=paths)
