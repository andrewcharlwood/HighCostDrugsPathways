"""
NHS High-Cost Drug Patient Pathway Analysis Tool - Reflex Application.

This is the main Reflex application module containing state management
and page components for the pathway analysis tool.
"""

import reflex as rx
from datetime import date, timedelta
from typing import Optional
import pandas as pd
import numpy as np
from pathlib import Path
import plotly.graph_objects as go
import traceback
import os

from rxconfig import config
from pathways_app.components.layout import main_layout, content_area


# NHS Color constants
NHS_BLUE = "rgb(0, 94, 184)"
NHS_DARK_BLUE = "rgb(0, 48, 135)"

# Supported file extensions
SUPPORTED_EXTENSIONS = [".csv", ".parquet", ".pq"]


class State(rx.State):
    """
    Application state for the NHS High-Cost Drug Patient Pathway Analysis Tool.

    Manages all filter variables, reference data, and analysis state.
    This corresponds to the AnalysisFilters dataclass in core/models.py
    but is adapted for Reflex's reactive state system.
    """

    # Date filter state
    start_date: str = ""  # ISO format YYYY-MM-DD
    end_date: str = ""
    last_seen_date: str = ""

    # Selection filters (list of selected items)
    selected_trusts: list[str] = []
    selected_drugs: list[str] = []
    selected_directories: list[str] = []

    # Analysis parameters
    minimum_patients: int = 0
    custom_title: str = ""

    # Reference data (available options loaded from CSV/SQLite)
    available_trusts: list[str] = []
    available_drugs: list[str] = []
    available_directories: list[str] = []

    # Drug default selections (Include=1 in include.csv)
    default_drugs: list[str] = []

    # Analysis state
    analysis_running: bool = False
    status_message: str = ""
    error_message: str = ""

    # Chart state - the Plotly figure
    chart_data: go.Figure = go.Figure()
    has_chart: bool = False

    # Data source state
    data_file_path: str = ""
    data_source: str = "file"  # "file", "sqlite", "snowflake"
    data_loaded: bool = False
    data_row_count: int = 0

    # Snowflake connection state
    snowflake_available: bool = False
    snowflake_configured: bool = False
    snowflake_connected: bool = False

    # File upload state
    uploaded_file_name: str = ""
    uploaded_file_size: int = 0  # bytes
    file_upload_error: str = ""
    file_upload_success: bool = False
    file_processing: bool = False

    # SQLite database state
    sqlite_available: bool = False
    sqlite_row_count: int = 0
    sqlite_patient_count: int = 0

    # Search/filter state for selection pages
    drug_search: str = ""
    trust_search: str = ""
    directory_search: str = ""

    # Export state
    last_export_path: str = ""
    export_message: str = ""
    export_error: str = ""

    # Indication validation state
    indication_validation_enabled: bool = True
    indication_validation_running: bool = False
    indication_validation_results: dict = {}  # drug_name -> {total, matched, rate}
    indication_validation_summary: str = ""

    # Store the underlying data for export
    _analysis_data: pd.DataFrame = pd.DataFrame()

    def _set_default_dates(self):
        """Set default date values based on typical analysis period."""
        today = date.today()
        one_year_ago = today - timedelta(days=365)

        self.start_date = one_year_ago.isoformat()
        self.end_date = today.isoformat()
        self.last_seen_date = one_year_ago.isoformat()

    def load_reference_data(self):
        """
        Load reference data from CSV files.

        This loads the available drugs, trusts, and directories
        that can be selected in the filters.
        """
        data_dir = Path("data")

        # Load drugs from include.csv
        try:
            drugs_df = pd.read_csv(data_dir / "include.csv")
            self.available_drugs = sorted(drugs_df.iloc[:, 0].astype(str).tolist())
            # Get default selections (Include=1)
            if "Include" in drugs_df.columns:
                self.default_drugs = drugs_df[drugs_df["Include"] == 1].iloc[:, 0].astype(str).tolist()
                self.selected_drugs = self.default_drugs.copy()
            self.status_message = f"Loaded {len(self.available_drugs)} drugs"
        except Exception as e:
            self.error_message = f"Failed to load drugs: {e}"

        # Load trusts from defaultTrusts.csv
        try:
            trusts_df = pd.read_csv(data_dir / "defaultTrusts.csv")
            self.available_trusts = sorted(trusts_df.iloc[:, 0].astype(str).tolist())
            # By default, no trusts selected (include all)
            self.selected_trusts = []
        except Exception as e:
            self.error_message = f"Failed to load trusts: {e}"

        # Load directories from directory_list.csv
        try:
            dirs_df = pd.read_csv(data_dir / "directory_list.csv")
            self.available_directories = sorted(dirs_df.iloc[:, 0].astype(str).tolist())
            # By default, no directories selected (include all)
            self.selected_directories = []
        except Exception as e:
            self.error_message = f"Failed to load directories: {e}"

        # Set default dates
        self._set_default_dates()

        # Check Snowflake availability
        try:
            from data_processing.snowflake_connector import is_snowflake_available, is_snowflake_configured
            self.snowflake_available = is_snowflake_available()
            self.snowflake_configured = is_snowflake_configured()
        except ImportError:
            self.snowflake_available = False
            self.snowflake_configured = False

        # Check SQLite database status
        self.check_sqlite_status()

        # Auto-select best data source
        if self.sqlite_available and self.sqlite_row_count > 0:
            self.data_source = "sqlite"
        elif self.snowflake_configured:
            self.data_source = "snowflake"
        else:
            self.data_source = "file"

    # Date setters
    def set_start_date(self, value: str):
        """Set the start date for analysis."""
        self.start_date = value

    def set_end_date(self, value: str):
        """Set the end date for analysis."""
        self.end_date = value

    def set_last_seen_date(self, value: str):
        """Set the last seen date filter."""
        self.last_seen_date = value

    # Selection setters
    def set_selected_trusts(self, trusts: list[str]):
        """Set the selected NHS trusts."""
        self.selected_trusts = trusts

    def toggle_trust(self, trust: str):
        """Toggle a trust selection."""
        if trust in self.selected_trusts:
            self.selected_trusts = [t for t in self.selected_trusts if t != trust]
        else:
            self.selected_trusts = self.selected_trusts + [trust]

    def select_all_trusts(self):
        """Select all available trusts."""
        self.selected_trusts = self.available_trusts.copy()

    def clear_trusts(self):
        """Clear all trust selections."""
        self.selected_trusts = []

    def set_selected_drugs(self, drugs: list[str]):
        """Set the selected drugs."""
        self.selected_drugs = drugs

    def toggle_drug(self, drug: str):
        """Toggle a drug selection."""
        if drug in self.selected_drugs:
            self.selected_drugs = [d for d in self.selected_drugs if d != drug]
        else:
            self.selected_drugs = self.selected_drugs + [drug]

    def select_all_drugs(self):
        """Select all available drugs."""
        self.selected_drugs = self.available_drugs.copy()

    def select_default_drugs(self):
        """Select only the default drugs (Include=1)."""
        self.selected_drugs = self.default_drugs.copy()

    def clear_drugs(self):
        """Clear all drug selections."""
        self.selected_drugs = []

    def set_selected_directories(self, directories: list[str]):
        """Set the selected directories."""
        self.selected_directories = directories

    def toggle_directory(self, directory: str):
        """Toggle a directory selection."""
        if directory in self.selected_directories:
            self.selected_directories = [d for d in self.selected_directories if d != directory]
        else:
            self.selected_directories = self.selected_directories + [directory]

    def select_all_directories(self):
        """Select all available directories."""
        self.selected_directories = self.available_directories.copy()

    def clear_directories(self):
        """Clear all directory selections."""
        self.selected_directories = []

    # Analysis parameter setters
    def set_minimum_patients(self, value: int):
        """Set the minimum patients threshold."""
        self.minimum_patients = max(0, value)

    def set_minimum_patients_from_input(self, value: str):
        """Set minimum patients threshold from string input."""
        try:
            self.minimum_patients = max(0, int(value)) if value else 0
        except ValueError:
            pass  # Ignore invalid input

    def set_minimum_patients_from_slider(self, values: list[float]):
        """Set minimum patients threshold from slider value (list)."""
        if values:
            self.minimum_patients = max(0, int(values[0]))

    def set_custom_title(self, value: str):
        """Set a custom title for the analysis."""
        self.custom_title = value

    # Data source methods
    def set_data_file_path(self, path: str):
        """Set the data file path for analysis."""
        self.data_file_path = path

    def set_data_source(self, source: str):
        """Set the data source type (file, sqlite, snowflake)."""
        if source in ("file", "sqlite", "snowflake"):
            self.data_source = source

    # Status methods
    def set_status(self, message: str):
        """Update the status message."""
        self.status_message = message

    def set_error(self, message: str):
        """Set an error message."""
        self.error_message = message

    def clear_error(self):
        """Clear the error message."""
        self.error_message = ""

    # File handling methods
    async def handle_file_upload(self, files: list[rx.UploadFile]):
        """
        Handle file upload for CSV/Parquet data files.

        This accepts uploaded files and processes them for analysis.
        """
        self.file_upload_error = ""
        self.file_upload_success = False

        if not files:
            self.file_upload_error = "No file selected"
            return

        file = files[0]  # Take first file only
        file_name = file.filename
        file_ext = Path(file_name).suffix.lower()

        # Validate file extension
        if file_ext not in SUPPORTED_EXTENSIONS:
            self.file_upload_error = f"Unsupported file type: {file_ext}. Please upload CSV or Parquet files."
            return

        self.file_processing = True
        self.status_message = f"Processing {file_name}..."
        yield  # Update UI

        try:
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            self.uploaded_file_size = file_size

            # Save to uploads directory
            upload_dir = Path("data/uploads")
            upload_dir.mkdir(parents=True, exist_ok=True)

            upload_path = upload_dir / file_name
            with open(upload_path, "wb") as f:
                f.write(file_content)

            self.uploaded_file_name = file_name
            self.data_file_path = str(upload_path)
            self.data_source = "file"
            self.file_upload_success = True

            # Format file size for display
            if file_size < 1024:
                size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"

            self.status_message = f"Uploaded {file_name} ({size_str})"

        except Exception as e:
            self.file_upload_error = f"Upload failed: {str(e)}"
            self.file_upload_success = False

        finally:
            self.file_processing = False

    def clear_uploaded_file(self):
        """Clear the uploaded file and reset file state."""
        self.uploaded_file_name = ""
        self.uploaded_file_size = 0
        self.data_file_path = ""
        self.file_upload_success = False
        self.file_upload_error = ""
        self.status_message = "File cleared"

    def check_sqlite_status(self):
        """Check if SQLite database is available and get statistics."""
        try:
            from data_processing.database import default_db_manager
            from data_processing.patient_data import get_patient_data_stats

            if default_db_manager.exists:
                stats = get_patient_data_stats(default_db_manager)
                self.sqlite_available = stats.get("total_rows", 0) > 0
                self.sqlite_row_count = stats.get("total_rows", 0)
                self.sqlite_patient_count = stats.get("unique_patients", 0)

                if self.sqlite_available:
                    self.status_message = f"SQLite database: {self.sqlite_row_count:,} rows, {self.sqlite_patient_count:,} patients"
                else:
                    self.status_message = "SQLite database exists but has no data"
            else:
                self.sqlite_available = False
                self.sqlite_row_count = 0
                self.sqlite_patient_count = 0
                self.status_message = "SQLite database not found"
        except ImportError:
            self.sqlite_available = False
            self.status_message = "Data processing module not available"
        except Exception as e:
            self.sqlite_available = False
            self.status_message = f"Error checking SQLite: {str(e)}"

    def use_sqlite_source(self):
        """Set data source to SQLite database."""
        self.data_source = "sqlite"
        self.data_file_path = ""
        self.status_message = "Using SQLite database as data source"

    def use_file_source(self):
        """Set data source to uploaded file."""
        if self.uploaded_file_name:
            self.data_source = "file"
            self.status_message = f"Using uploaded file: {self.uploaded_file_name}"
        else:
            self.status_message = "No file uploaded. Please upload a file first."

    def use_snowflake_source(self):
        """Set data source to Snowflake (if available)."""
        if self.snowflake_configured:
            self.data_source = "snowflake"
            self.status_message = "Using Snowflake as data source"
        else:
            self.status_message = "Snowflake is not configured. Check config/snowflake.toml"

    @rx.var
    def data_source_display(self) -> str:
        """Human-readable data source description."""
        if self.data_source == "file":
            if self.uploaded_file_name:
                return f"File: {self.uploaded_file_name}"
            return "File: No file selected"
        elif self.data_source == "sqlite":
            if self.sqlite_available:
                return f"SQLite: {self.sqlite_row_count:,} rows"
            return "SQLite: Not available"
        elif self.data_source == "snowflake":
            if self.snowflake_configured:
                return "Snowflake: Ready"
            return "Snowflake: Not configured"
        return "Unknown"

    @rx.var
    def file_size_display(self) -> str:
        """Human-readable file size."""
        if self.uploaded_file_size == 0:
            return ""
        if self.uploaded_file_size < 1024:
            return f"{self.uploaded_file_size} bytes"
        elif self.uploaded_file_size < 1024 * 1024:
            return f"{self.uploaded_file_size / 1024:.1f} KB"
        else:
            return f"{self.uploaded_file_size / (1024 * 1024):.1f} MB"

    # Validation
    def validate_filters(self) -> list[str]:
        """
        Validate the current filter configuration.

        Returns a list of error messages (empty if valid).
        """
        errors = []

        # Check dates are set
        if not self.start_date:
            errors.append("Start date is required")
        if not self.end_date:
            errors.append("End date is required")
        if not self.last_seen_date:
            errors.append("Last seen date is required")

        # Check date order
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors.append("End date cannot be before start date")

        if self.last_seen_date and self.end_date:
            if self.last_seen_date > self.end_date:
                errors.append("Last seen date is after end date (would exclude all patients)")

        # Check minimum patients
        if self.minimum_patients < 0:
            errors.append("Minimum patients cannot be negative")

        # Check at least some drugs are selected (warning, not error)
        # Empty selection means "include all"

        return errors

    @rx.var
    def filter_summary(self) -> str:
        """Generate a summary of current filter settings."""
        lines = []

        if self.start_date and self.end_date:
            lines.append(f"Date range: {self.start_date} to {self.end_date}")
        if self.last_seen_date:
            lines.append(f"Last seen after: {self.last_seen_date}")
        lines.append(f"Minimum patients: {self.minimum_patients}")

        if self.selected_trusts:
            lines.append(f"Trusts: {len(self.selected_trusts)} selected")
        else:
            lines.append("Trusts: All")

        if self.selected_drugs:
            lines.append(f"Drugs: {len(self.selected_drugs)} selected")
        else:
            lines.append("Drugs: All")

        if self.selected_directories:
            lines.append(f"Directories: {len(self.selected_directories)} selected")
        else:
            lines.append("Directories: All")

        return "\n".join(lines)

    @rx.var
    def display_title(self) -> str:
        """Generate the display title for the analysis."""
        if self.custom_title:
            return self.custom_title
        if self.start_date and self.end_date:
            return f"Patients initiated from {self.start_date} to {self.end_date}"
        return "Patient Pathway Analysis"

    @rx.var
    def drug_selection_count(self) -> str:
        """Display count of selected drugs."""
        return f"{len(self.selected_drugs)} of {len(self.available_drugs)} drugs selected"

    @rx.var
    def trust_selection_count(self) -> str:
        """Display count of selected trusts."""
        if not self.selected_trusts:
            return f"All {len(self.available_trusts)} trusts (none selected)"
        return f"{len(self.selected_trusts)} of {len(self.available_trusts)} trusts selected"

    @rx.var
    def directory_selection_count(self) -> str:
        """Display count of selected directories."""
        if not self.selected_directories:
            return f"All {len(self.available_directories)} directories (none selected)"
        return f"{len(self.selected_directories)} of {len(self.available_directories)} directories selected"

    # Search setters
    def set_drug_search(self, value: str):
        """Set the drug search filter text."""
        self.drug_search = value

    def set_trust_search(self, value: str):
        """Set the trust search filter text."""
        self.trust_search = value

    def set_directory_search(self, value: str):
        """Set the directory search filter text."""
        self.directory_search = value

    def clear_drug_search(self):
        """Clear the drug search filter."""
        self.drug_search = ""

    def clear_trust_search(self):
        """Clear the trust search filter."""
        self.trust_search = ""

    def clear_directory_search(self):
        """Clear the directory search filter."""
        self.directory_search = ""

    @rx.var
    def filtered_drugs(self) -> list[str]:
        """Get the list of drugs filtered by search text."""
        if not self.drug_search:
            return self.available_drugs
        search_lower = self.drug_search.lower()
        return [d for d in self.available_drugs if search_lower in d.lower()]

    @rx.var
    def filtered_trusts(self) -> list[str]:
        """Get the list of trusts filtered by search text."""
        if not self.trust_search:
            return self.available_trusts
        search_lower = self.trust_search.lower()
        return [t for t in self.available_trusts if search_lower in t.lower()]

    @rx.var
    def filtered_directories(self) -> list[str]:
        """Get the list of directories filtered by search text."""
        if not self.directory_search:
            return self.available_directories
        search_lower = self.directory_search.lower()
        return [d for d in self.available_directories if search_lower in d.lower()]

    @rx.var
    def drug_search_result_count(self) -> str:
        """Display count of drugs matching search."""
        total = len(self.available_drugs)
        filtered = len(self.filtered_drugs)
        if not self.drug_search:
            return f"{total} drugs"
        return f"Showing {filtered} of {total} drugs"

    @rx.var
    def trust_search_result_count(self) -> str:
        """Display count of trusts matching search."""
        total = len(self.available_trusts)
        filtered = len(self.filtered_trusts)
        if not self.trust_search:
            return f"{total} trusts"
        return f"Showing {filtered} of {total} trusts"

    @rx.var
    def directory_search_result_count(self) -> str:
        """Display count of directories matching search."""
        total = len(self.available_directories)
        filtered = len(self.filtered_directories)
        if not self.directory_search:
            return f"{total} directories"
        return f"Showing {filtered} of {total} directories"

    # Analysis methods
    def run_analysis(self):
        """
        Run the patient pathway analysis with current filter settings.

        This is an async generator that yields state updates for progress indication.
        Uses the existing analysis pipeline from tools/dashboard_gui.py.
        """
        # Validate filters first
        errors = self.validate_filters()
        if errors:
            self.error_message = "Validation errors:\n" + "\n".join(errors)
            return

        self.analysis_running = True
        self.error_message = ""
        self.status_message = "Starting analysis..."
        self.has_chart = False
        yield  # Update UI to show running state

        try:
            # Import analysis modules
            from core import AnalysisFilters, PathConfig, default_paths
            from data_processing.data_source import get_data
            from tools.dashboard_gui import generate_graph

            # Get the data using fallback chain (cache -> Snowflake -> SQLite -> file)
            self.status_message = "Loading patient data..."
            yield

            # Build filter parameters
            trusts = self.selected_trusts if self.selected_trusts else self.available_trusts
            drugs = self.selected_drugs if self.selected_drugs else self.available_drugs
            directories = self.selected_directories if self.selected_directories else self.available_directories

            # Get data from the data source manager
            result = get_data(
                start_date=self.start_date,
                end_date=self.end_date,
                trusts=trusts,
                drugs=drugs,
                directories=directories,
            )

            if result.df is None or len(result.df) == 0:
                self.error_message = "No data available. Please check your data source configuration."
                self.analysis_running = False
                return

            self.data_source = result.source_type.value
            self.data_row_count = len(result.df)
            self.status_message = f"Loaded {self.data_row_count:,} rows from {self.data_source}"
            yield

            # Create AnalysisFilters object for generate_graph
            self.status_message = "Processing pathways..."
            yield

            # Generate the chart data (without writing to file)
            # We'll create the figure data directly instead of calling generate_graph
            # which writes to file and opens browser
            fig_data = self._generate_chart_data(
                df=result.df,
                trusts=trusts,
                drugs=drugs,
                directories=directories,
            )

            if fig_data is not None:
                self.chart_data = fig_data
                self.has_chart = True
                self.status_message = f"Analysis complete! Showing {self.data_row_count:,} interventions."
            else:
                self.error_message = "No data found matching the selected filters."
                self.has_chart = False

        except Exception as e:
            self.error_message = f"Analysis failed: {str(e)}\n\n{traceback.format_exc()}"
            self.has_chart = False

        finally:
            self.analysis_running = False

        yield  # Final UI update

    def _generate_chart_data(
        self,
        df: pd.DataFrame,
        trusts: list[str],
        drugs: list[str],
        directories: list[str],
    ) -> Optional[go.Figure]:
        """
        Generate Plotly chart data from processed DataFrame.

        This replicates the core logic of generate_graph() and figure() but
        returns the figure dict instead of writing to file and opening browser.
        This is a workaround to avoid modifying generate_graph() internals
        (which is deferred to Phase 5).
        """
        from core import default_paths

        # Use the org_codes mapping
        org_codes = pd.read_csv(default_paths.org_codes_csv, index_col=1)

        # Make a copy to avoid modifying original
        df1 = df.copy()

        # Create UPID + Treatment column for deduplication
        df1["UPIDTreatment"] = df1["UPID"] + df1["Drug Name"]

        # Map provider codes to names
        df1["Provider Code"] = df1["Provider Code"].map(org_codes["Name"])

        # Apply filters
        df1 = df1[
            (df1["Provider Code"].isin(trusts)) &
            (df1["Drug Name"].isin(drugs)) &
            (df1["Directory"].isin(directories))
        ]

        if len(df1) == 0:
            return None

        # Apply date filters
        df1 = df1[
            (df1["Intervention Date"] >= self.start_date) &
            (df1["Intervention Date"] <= self.end_date)
        ]

        if len(df1) == 0:
            return None

        # Add indication validation columns (if enabled and Snowflake available)
        df1 = self._add_indication_validation(df1)

        # Store filtered data for CSV export (now includes indication columns)
        self._analysis_data = df1.copy()

        # Build a simplified hierarchy for the icicle chart
        # Group by Trust -> Directory -> Drug to get patient counts
        hierarchy_data = self._build_hierarchy(df1, org_codes)

        if hierarchy_data.empty:
            return None

        # Apply minimum patients filter
        hierarchy_data = hierarchy_data[hierarchy_data['value'] >= self.minimum_patients]

        if hierarchy_data.empty:
            return None

        # Create the Plotly icicle figure
        fig = go.Figure(go.Icicle(
            labels=hierarchy_data['labels'].tolist(),
            ids=hierarchy_data['ids'].tolist(),
            parents=hierarchy_data['parents'].tolist(),
            values=hierarchy_data['value'].tolist(),
            branchvalues="total",
            marker=dict(
                colors=hierarchy_data['colour'].tolist() if 'colour' in hierarchy_data.columns else None,
                colorscale='Viridis',
            ),
            maxdepth=3,
            texttemplate='<b>%{label}</b><br>Patients: %{value}',
            hovertemplate='<b>%{label}</b><br>Patients: %{value}<extra></extra>',
        ))

        # Set chart title
        title_text = self.custom_title if self.custom_title else f"Patients initiated {self.start_date} to {self.end_date}"

        fig.update_layout(
            margin=dict(t=60, l=1, r=1, b=60),
            title=f"Norfolk & Waveney ICS High-Cost Drug Patient Pathways - {title_text}",
            title_x=0.5,
            hoverlabel=dict(font_size=16),
        )

        # Return figure for rx.plotly()
        return fig

    def _build_hierarchy(self, df: pd.DataFrame, org_codes: pd.DataFrame) -> pd.DataFrame:
        """
        Build a hierarchical dataframe for icicle chart.

        Creates Trust -> Directory -> Drug hierarchy with patient counts.
        """
        # Create directory mapping from UPID
        directory_df = df[["UPID", "Directory"]].drop_duplicates("UPID").set_index("UPID")

        # Get unique patients per drug
        patient_drugs = df[["UPID", "Drug Name", "Provider Code", "Directory"]].drop_duplicates(subset=["UPID", "Drug Name"])

        # Build hierarchy: Trust -> Directory -> Drug
        rows = []

        # Root node
        total_patients = patient_drugs["UPID"].nunique()
        rows.append({
            'parents': '',
            'ids': 'N&WICS',
            'labels': 'N&WICS',
            'value': total_patients,
            'colour': 1.0,
        })

        # Trust level
        trust_counts = patient_drugs.groupby("Provider Code")["UPID"].nunique().reset_index()
        trust_counts.columns = ["trust", "count"]

        for _, row in trust_counts.iterrows():
            trust = row["trust"]
            if pd.isna(trust):
                continue
            rows.append({
                'parents': 'N&WICS',
                'ids': f'N&WICS - {trust}',
                'labels': trust,
                'value': row["count"],
                'colour': row["count"] / total_patients,
            })

        # Directory level (under each trust)
        trust_dir_counts = patient_drugs.groupby(["Provider Code", "Directory"])["UPID"].nunique().reset_index()
        trust_dir_counts.columns = ["trust", "directory", "count"]

        for _, row in trust_dir_counts.iterrows():
            trust = row["trust"]
            directory = row["directory"]
            if pd.isna(trust) or pd.isna(directory):
                continue
            trust_total = trust_counts[trust_counts["trust"] == trust]["count"].values
            trust_total = trust_total[0] if len(trust_total) > 0 else 1
            rows.append({
                'parents': f'N&WICS - {trust}',
                'ids': f'N&WICS - {trust} - {directory}',
                'labels': directory,
                'value': row["count"],
                'colour': row["count"] / trust_total,
            })

        # Drug level (under each trust-directory)
        trust_dir_drug_counts = patient_drugs.groupby(["Provider Code", "Directory", "Drug Name"])["UPID"].nunique().reset_index()
        trust_dir_drug_counts.columns = ["trust", "directory", "drug", "count"]

        for _, row in trust_dir_drug_counts.iterrows():
            trust = row["trust"]
            directory = row["directory"]
            drug = row["drug"]
            if pd.isna(trust) or pd.isna(directory) or pd.isna(drug):
                continue
            dir_total = trust_dir_counts[
                (trust_dir_counts["trust"] == trust) &
                (trust_dir_counts["directory"] == directory)
            ]["count"].values
            dir_total = dir_total[0] if len(dir_total) > 0 else 1
            rows.append({
                'parents': f'N&WICS - {trust} - {directory}',
                'ids': f'N&WICS - {trust} - {directory} - {drug}',
                'labels': drug,
                'value': row["count"],
                'colour': row["count"] / dir_total,
            })

        return pd.DataFrame(rows)

    def _add_indication_validation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add indication validation columns to the DataFrame.

        Adds columns:
        - Indication_Valid: Boolean indicating if patient has valid GP diagnosis
        - Indication_Source: "GP_SNOMED" | "NONE" | "NOT_CHECKED"
        - Indication_Cluster: The matched SNOMED cluster ID (if any)

        This requires Snowflake connectivity for GP record lookups.
        If Snowflake is not available, columns are added with "NOT_CHECKED" status.
        """
        # Initialize columns with default values
        df = df.copy()
        df["Indication_Valid"] = False
        df["Indication_Source"] = "NOT_CHECKED"
        df["Indication_Cluster"] = ""

        # Check if indication validation is enabled and Snowflake is available
        if not self.indication_validation_enabled:
            return df

        try:
            from data_processing.snowflake_connector import (
                is_snowflake_available,
                is_snowflake_configured,
                get_connector,
            )
            from data_processing.diagnosis_lookup import (
                get_drug_cluster_ids,
                patient_has_indication,
            )

            if not is_snowflake_available() or not is_snowflake_configured():
                # Snowflake not available - can't validate indications
                self.indication_validation_summary = "Indication validation skipped (Snowflake not configured)"
                return df

            self.indication_validation_running = True

            # Get unique patient-drug pairs
            patient_drug_pairs = df[["UPID", "Drug Name"]].drop_duplicates()
            total_pairs = len(patient_drug_pairs)

            # Cache drug clusters to avoid repeated lookups
            drug_clusters_cache = {}

            # Track results for summary
            validation_results = {}  # drug -> {total, matched}
            connector = get_connector()

            for idx, (_, row) in enumerate(patient_drug_pairs.iterrows()):
                upid = row["UPID"]
                drug_name = row["Drug Name"]

                # Get drug clusters (cached)
                drug_upper = drug_name.upper() if drug_name else ""
                if drug_upper not in drug_clusters_cache:
                    drug_clusters_cache[drug_upper] = get_drug_cluster_ids(drug_name)

                cluster_ids = drug_clusters_cache[drug_upper]

                # Initialize drug in results tracking
                if drug_upper not in validation_results:
                    validation_results[drug_upper] = {"total": 0, "matched": 0, "name": drug_name}

                validation_results[drug_upper]["total"] += 1

                if not cluster_ids:
                    # No cluster mapping for this drug - mark as NONE
                    mask = (df["UPID"] == upid) & (df["Drug Name"] == drug_name)
                    df.loc[mask, "Indication_Source"] = "NONE"
                    continue

                # Check patient indication in GP records
                # Note: We use the UPID as patient identifier - this may need mapping to pseudonymised NHS number
                # For now, assume UPID can be used directly or is already the pseudonymised ID
                has_indication, matched_cluster, _, _ = patient_has_indication(
                    patient_pseudonym=upid,
                    cluster_ids=cluster_ids,
                    connector=connector,
                )

                # Update dataframe for this patient-drug combination
                mask = (df["UPID"] == upid) & (df["Drug Name"] == drug_name)
                df.loc[mask, "Indication_Valid"] = has_indication
                df.loc[mask, "Indication_Source"] = "GP_SNOMED" if has_indication else "NONE"
                if matched_cluster:
                    df.loc[mask, "Indication_Cluster"] = matched_cluster

                if has_indication:
                    validation_results[drug_upper]["matched"] += 1

            # Store validation results and create summary
            self.indication_validation_results = {
                drug: {
                    "drug_name": data["name"],
                    "total_patients": data["total"],
                    "patients_with_indication": data["matched"],
                    "match_rate": round(data["matched"] / data["total"] * 100, 1) if data["total"] > 0 else 0,
                }
                for drug, data in validation_results.items()
            }

            # Create summary text
            total_patients = sum(d["total"] for d in validation_results.values())
            matched_patients = sum(d["matched"] for d in validation_results.values())
            overall_rate = round(matched_patients / total_patients * 100, 1) if total_patients > 0 else 0

            self.indication_validation_summary = (
                f"GP Indication Validation: {matched_patients}/{total_patients} "
                f"({overall_rate}%) patients have valid GP diagnosis"
            )

        except Exception as e:
            self.indication_validation_summary = f"Indication validation error: {str(e)}"
            # Don't fail the whole analysis - just leave columns as NOT_CHECKED

        finally:
            self.indication_validation_running = False

        return df

    def toggle_indication_validation(self):
        """Toggle indication validation on/off."""
        self.indication_validation_enabled = not self.indication_validation_enabled

    @rx.var
    def indication_validation_status(self) -> str:
        """Get human-readable indication validation status."""
        if self.indication_validation_running:
            return "Validating patient indications..."
        if self.indication_validation_summary:
            return self.indication_validation_summary
        if self.indication_validation_enabled:
            return "Enabled (will check GP records)"
        return "Disabled"

    @rx.var
    def indication_results_list(self) -> list[dict]:
        """
        Get indication validation results as a list for display.

        Returns list of dicts with: drug_name, total_patients, patients_with_indication, match_rate
        Sorted by match rate ascending (worst first) for easy identification of issues.
        """
        if not self.indication_validation_results:
            return []

        results = []
        for drug_key, data in self.indication_validation_results.items():
            results.append({
                "drug_name": data.get("drug_name", drug_key),
                "total_patients": data.get("total_patients", 0),
                "patients_with_indication": data.get("patients_with_indication", 0),
                "match_rate": data.get("match_rate", 0),
            })

        # Sort by match rate ascending (lowest first to highlight issues)
        results.sort(key=lambda x: x["match_rate"])
        return results

    @rx.var
    def has_indication_results(self) -> bool:
        """Check if there are indication validation results to display."""
        return len(self.indication_validation_results) > 0

    def export_chart_html(self):
        """
        Export the current chart as an interactive HTML file.

        The file is saved to data/exports/ directory with a timestamped filename.
        """
        if not self.has_chart:
            self.export_error = "No chart to export. Please run analysis first."
            return

        self.export_error = ""
        self.export_message = ""

        try:
            from datetime import datetime

            # Create exports directory
            export_dir = Path("data/exports")
            export_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pathway_chart_{timestamp}.html"
            filepath = export_dir / filename

            # Export the chart to HTML
            self.chart_data.write_html(
                str(filepath),
                include_plotlyjs=True,
                full_html=True,
            )

            self.last_export_path = str(filepath)
            self.export_message = f"Chart exported to {filename}"

        except Exception as e:
            self.export_error = f"Export failed: {str(e)}"

    def export_data_csv(self):
        """
        Export the underlying analysis data as a CSV file.

        The file is saved to data/exports/ directory with a timestamped filename.
        """
        if self._analysis_data is None or len(self._analysis_data) == 0:
            self.export_error = "No data to export. Please run analysis first."
            return

        self.export_error = ""
        self.export_message = ""

        try:
            from datetime import datetime

            # Create exports directory
            export_dir = Path("data/exports")
            export_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pathway_data_{timestamp}.csv"
            filepath = export_dir / filename

            # Export the data to CSV
            self._analysis_data.to_csv(filepath, index=False)

            self.last_export_path = str(filepath)
            self.export_message = f"Data exported to {filename}"

        except Exception as e:
            self.export_error = f"Export failed: {str(e)}"

    def clear_export_messages(self):
        """Clear export status messages."""
        self.export_message = ""
        self.export_error = ""


# =============================================================================
# Page Components
# =============================================================================

def info_card(title: str, value: str, icon: str) -> rx.Component:
    """Create an info card showing a statistic."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=20, color=NHS_BLUE),
                rx.text(title, size="2", color="gray"),
                spacing="2",
                align="center",
            ),
            rx.text(value, size="5", weight="bold"),
            spacing="1",
            align="start",
        ),
        padding="16px",
        background="white",
        border_radius="8px",
        border="1px solid rgb(229, 231, 235)",
        width="100%",
    )


def date_input(label: str, value: rx.Var, on_change, help_text: str = "", input_id: str = "") -> rx.Component:
    """Create a labeled date input component with accessibility support."""
    # Generate a unique ID if not provided
    label_id = f"{input_id}-label" if input_id else ""
    help_id = f"{input_id}-help" if input_id else ""

    return rx.vstack(
        rx.el.label(
            label,
            html_for=input_id,
            font_size="14px",
            font_weight="500",
            color=NHS_DARK_BLUE,
        ),
        rx.input(
            type="date",
            value=value,
            on_change=on_change,
            width="100%",
            id=input_id,
            aria_describedby=help_id if help_text else "",
        ),
        rx.cond(
            help_text != "",
            rx.text(help_text, size="1", color="gray", id=help_id),
        ),
        spacing="1",
        align="start",
        width="100%",
    )


def data_source_selector() -> rx.Component:
    """Data source selector with file upload, SQLite, and Snowflake options."""
    return rx.box(
        rx.vstack(
            rx.heading("Data Source", size="5", color=NHS_DARK_BLUE),
            rx.text(
                "Select where to load patient data from",
                size="2",
                color="gray",
            ),
            rx.divider(margin_y="8px"),
            # Current data source display
            rx.hstack(
                rx.text("Current source:", weight="medium"),
                rx.badge(
                    State.data_source_display,
                    color_scheme=rx.cond(
                        State.data_source == "sqlite",
                        "green",
                        rx.cond(
                            State.data_source == "snowflake",
                            "blue",
                            "gray",
                        ),
                    ),
                    size="2",
                ),
                spacing="2",
                align="center",
            ),
            rx.divider(margin_y="8px"),
            # Data source options
            rx.vstack(
                # SQLite option
                rx.box(
                    rx.hstack(
                        rx.icon("database", size=20, color=NHS_BLUE),
                        rx.vstack(
                            rx.hstack(
                                rx.text("SQLite Database", weight="medium"),
                                rx.cond(
                                    State.sqlite_available,
                                    rx.badge("Available", color_scheme="green", size="1"),
                                    rx.badge("No data", color_scheme="gray", size="1"),
                                ),
                                spacing="2",
                            ),
                            rx.cond(
                                State.sqlite_available,
                                rx.text(
                                    f"Contains pre-loaded patient data",
                                    size="1",
                                    color="gray",
                                ),
                                rx.text(
                                    "Run data migration to populate",
                                    size="1",
                                    color="gray",
                                ),
                            ),
                            spacing="1",
                            align="start",
                        ),
                        rx.spacer(),
                        rx.button(
                            "Use SQLite",
                            on_click=State.use_sqlite_source,
                            variant=rx.cond(State.data_source == "sqlite", "solid", "outline"),
                            color_scheme="green",
                            size="2",
                            disabled=~State.sqlite_available,
                        ),
                        spacing="3",
                        align="center",
                        width="100%",
                    ),
                    padding="12px",
                    background=rx.cond(
                        State.data_source == "sqlite",
                        "rgba(0, 94, 184, 0.05)",
                        "transparent",
                    ),
                    border_radius="6px",
                    border=rx.cond(
                        State.data_source == "sqlite",
                        "1px solid rgb(0, 94, 184)",
                        "1px solid transparent",
                    ),
                    width="100%",
                ),
                # File upload option
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("upload", size=20, color=NHS_BLUE),
                            rx.vstack(
                                rx.hstack(
                                    rx.text("Upload File", weight="medium"),
                                    rx.cond(
                                        State.file_upload_success,
                                        rx.badge(State.file_size_display, color_scheme="green", size="1"),
                                    ),
                                    spacing="2",
                                ),
                                rx.text(
                                    "Upload CSV or Parquet file",
                                    size="1",
                                    color="gray",
                                ),
                                spacing="1",
                                align="start",
                            ),
                            rx.spacer(),
                            rx.cond(
                                State.file_upload_success,
                                rx.hstack(
                                    rx.button(
                                        "Use File",
                                        on_click=State.use_file_source,
                                        variant=rx.cond(State.data_source == "file", "solid", "outline"),
                                        color_scheme="blue",
                                        size="2",
                                    ),
                                    rx.button(
                                        rx.icon("x", size=14),
                                        on_click=State.clear_uploaded_file,
                                        variant="ghost",
                                        color_scheme="red",
                                        size="1",
                                    ),
                                    spacing="1",
                                ),
                            ),
                            spacing="3",
                            align="center",
                            width="100%",
                        ),
                        rx.cond(
                            State.file_upload_success,
                            rx.text(
                                State.uploaded_file_name,
                                size="2",
                                color=NHS_BLUE,
                                font_family="monospace",
                            ),
                            rx.upload(
                                rx.vstack(
                                    rx.cond(
                                        State.file_processing,
                                        rx.spinner(size="2"),
                                        rx.icon("file-up", size=24, color="gray"),
                                    ),
                                    rx.text(
                                        "Drag & drop or click to browse",
                                        size="2",
                                        color="gray",
                                    ),
                                    rx.text(
                                        "Supports CSV, Parquet",
                                        size="1",
                                        color="gray",
                                    ),
                                    spacing="2",
                                    align="center",
                                    padding="16px",
                                ),
                                id="file_upload",
                                accept={
                                    "text/csv": [".csv"],
                                    "application/octet-stream": [".parquet", ".pq"],
                                },
                                max_files=1,
                                border="1px dashed rgb(200, 200, 200)",
                                border_radius="6px",
                                padding="4px",
                                width="100%",
                                on_drop=State.handle_file_upload(rx.upload_files(upload_id="file_upload")),
                            ),
                        ),
                        rx.cond(
                            State.file_upload_error != "",
                            rx.text(
                                State.file_upload_error,
                                size="2",
                                color="red",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    padding="12px",
                    background=rx.cond(
                        (State.data_source == "file") & State.file_upload_success,
                        "rgba(0, 94, 184, 0.05)",
                        "transparent",
                    ),
                    border_radius="6px",
                    border=rx.cond(
                        (State.data_source == "file") & State.file_upload_success,
                        "1px solid rgb(0, 94, 184)",
                        "1px solid transparent",
                    ),
                    width="100%",
                ),
                # Snowflake option
                rx.box(
                    rx.hstack(
                        rx.icon("cloud", size=20, color=NHS_BLUE),
                        rx.vstack(
                            rx.hstack(
                                rx.text("Snowflake", weight="medium"),
                                rx.cond(
                                    State.snowflake_configured,
                                    rx.badge("Configured", color_scheme="blue", size="1"),
                                    rx.badge("Not configured", color_scheme="gray", size="1"),
                                ),
                                spacing="2",
                            ),
                            rx.text(
                                "Query live data from Snowflake",
                                size="1",
                                color="gray",
                            ),
                            spacing="1",
                            align="start",
                        ),
                        rx.spacer(),
                        rx.button(
                            "Use Snowflake",
                            on_click=State.use_snowflake_source,
                            variant=rx.cond(State.data_source == "snowflake", "solid", "outline"),
                            color_scheme="blue",
                            size="2",
                            disabled=~State.snowflake_configured,
                        ),
                        spacing="3",
                        align="center",
                        width="100%",
                    ),
                    padding="12px",
                    background=rx.cond(
                        State.data_source == "snowflake",
                        "rgba(0, 94, 184, 0.05)",
                        "transparent",
                    ),
                    border_radius="6px",
                    border=rx.cond(
                        State.data_source == "snowflake",
                        "1px solid rgb(0, 94, 184)",
                        "1px solid transparent",
                    ),
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        padding="20px",
        background="white",
        border_radius="8px",
        border="1px solid rgb(229, 231, 235)",
        width="100%",
    )


def filter_controls() -> rx.Component:
    """Filter controls section with date pickers, minimum patients, and custom title."""
    return rx.box(
        rx.vstack(
            rx.heading("Analysis Settings", size="5", color=NHS_DARK_BLUE, id="analysis-settings-heading"),
            # Date range row
            rx.hstack(
                date_input(
                    "Start Date",
                    State.start_date,
                    State.set_start_date,
                    "Include patients initiated from this date",
                    input_id="start-date",
                ),
                date_input(
                    "End Date",
                    State.end_date,
                    State.set_end_date,
                    "Include patients initiated until this date",
                    input_id="end-date",
                ),
                date_input(
                    "Last Seen After",
                    State.last_seen_date,
                    State.set_last_seen_date,
                    "Only include patients seen after this date",
                    input_id="last-seen-date",
                ),
                spacing="4",
                width="100%",
                flex_wrap="wrap",
                role="group",
                aria_label="Date range filters",
            ),
            rx.divider(margin_y="12px"),
            # Additional settings row
            rx.hstack(
                # Minimum patients
                rx.vstack(
                    rx.el.label(
                        "Minimum Patients",
                        html_for="min-patients",
                        font_size="14px",
                        font_weight="500",
                        color=NHS_DARK_BLUE,
                    ),
                    rx.hstack(
                        rx.input(
                            type="number",
                            value=State.minimum_patients.to_string(),
                            on_change=State.set_minimum_patients_from_input,
                            min="0",
                            max="1000",
                            width="100px",
                            id="min-patients",
                            aria_describedby="min-patients-help",
                        ),
                        rx.slider(
                            value=[State.minimum_patients],
                            on_change=State.set_minimum_patients_from_slider,
                            min=0,
                            max=100,
                            step=1,
                            width="150px",
                            aria_label="Minimum patients slider",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    rx.text(
                        "Hide pathways with fewer patients",
                        size="1",
                        color="gray",
                        id="min-patients-help",
                    ),
                    spacing="1",
                    align="start",
                ),
                # Custom title
                rx.vstack(
                    rx.el.label(
                        "Custom Title (Optional)",
                        html_for="custom-title",
                        font_size="14px",
                        font_weight="500",
                        color=NHS_DARK_BLUE,
                    ),
                    rx.input(
                        placeholder="Leave empty for auto-generated title",
                        value=State.custom_title,
                        on_change=State.set_custom_title,
                        width="300px",
                        id="custom-title",
                        aria_describedby="custom-title-help",
                    ),
                    rx.text(
                        "Override the default chart title",
                        size="1",
                        color="gray",
                        id="custom-title-help",
                    ),
                    spacing="1",
                    align="start",
                ),
                spacing="6",
                width="100%",
                flex_wrap="wrap",
                align="start",
            ),
            spacing="4",
            align="start",
            width="100%",
        ),
        padding="20px",
        background="white",
        border_radius="8px",
        border="1px solid rgb(229, 231, 235)",
        width="100%",
        role="region",
        aria_labelledby="analysis-settings-heading",
    )


def indication_result_row(result: dict) -> rx.Component:
    """Render a single row in the indication validation results table."""
    match_rate = result["match_rate"]
    # Color code: green for high match rates, amber for moderate, red for low
    # Use .to(int) to cast Reflex Var for comparison (rx.foreach items are Vars)
    rate_color = rx.cond(
        match_rate.to(int) >= 80,
        "green",
        rx.cond(match_rate.to(int) >= 50, "orange", "red"),
    )
    return rx.table.row(
        rx.table.cell(rx.text(result["drug_name"], weight="medium")),
        rx.table.cell(result["total_patients"].to_string()),
        rx.table.cell(result["patients_with_indication"].to_string()),
        rx.table.cell(
            rx.hstack(
                rx.progress(
                    value=match_rate,
                    max=100,
                    width="60px",
                    height="8px",
                    color_scheme=rate_color,
                ),
                rx.text(
                    match_rate.to_string() + "%",
                    size="2",
                    color=rate_color,
                    weight="medium",
                ),
                spacing="2",
                align="center",
            )
        ),
    )


def indication_validation_summary() -> rx.Component:
    """
    Component to display indication validation results per drug.

    Shows a collapsible section with a table of per-drug match rates,
    helping users identify which drugs have good vs poor GP diagnosis coverage.
    """
    return rx.cond(
        State.has_indication_results,
        rx.el.section(
            rx.vstack(
                # Header with overall summary
                rx.hstack(
                    rx.hstack(
                        rx.icon("clipboard-check", size=20, color=NHS_DARK_BLUE, aria_hidden="true"),
                        rx.heading(
                            "GP Indication Validation Results",
                            size="5",
                            color=NHS_DARK_BLUE,
                            id="indication-results-heading",
                        ),
                        spacing="2",
                        align="center",
                    ),
                    rx.spacer(),
                    rx.badge(
                        State.indication_validation_summary,
                        color_scheme="blue",
                        size="2",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.text(
                    "Shows the percentage of patients with valid GP diagnoses matching their prescribed drug's indication. "
                    "Lower rates may indicate prescribing for off-label use, data quality issues, or patients treated across multiple providers.",
                    size="2",
                    color="gray",
                ),
                # Results table
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Drug Name"),
                            rx.table.column_header_cell("Total Patients"),
                            rx.table.column_header_cell("With GP Indication"),
                            rx.table.column_header_cell("Match Rate"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(State.indication_results_list, indication_result_row)
                    ),
                    width="100%",
                    size="2",
                ),
                # Legend
                rx.hstack(
                    rx.text("Legend:", size="1", color="gray", weight="medium"),
                    rx.hstack(
                        rx.badge("80%+", color_scheme="green", size="1"),
                        rx.text("Good coverage", size="1", color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    rx.hstack(
                        rx.badge("50-79%", color_scheme="orange", size="1"),
                        rx.text("Moderate", size="1", color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    rx.hstack(
                        rx.badge("<50%", color_scheme="red", size="1"),
                        rx.text("Low coverage", size="1", color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    spacing="4",
                    flex_wrap="wrap",
                ),
                spacing="3",
                width="100%",
                align="start",
            ),
            padding="20px",
            background="white",
            border_radius="8px",
            border="1px solid rgb(229, 231, 235)",
            width="100%",
            aria_labelledby="indication-results-heading",
        ),
    )


def home_content() -> rx.Component:
    """Home page content with filter configuration and analysis controls."""
    return rx.vstack(
        # Hero section
        rx.box(
            rx.vstack(
                rx.image(
                    src="/logo.png",
                    height="60px",
                    alt="NHS Logo",
                ),
                rx.heading(
                    "Patient Pathway Analysis",
                    size="8",
                    color=NHS_DARK_BLUE,
                ),
                rx.text(
                    "Analyze secondary care treatment pathways for high-cost drugs",
                    size="4",
                    color="gray",
                ),
                spacing="3",
                align="center",
            ),
            padding="32px",
            background="white",
            border_radius="12px",
            border="1px solid rgb(229, 231, 235)",
            width="100%",
            text_align="center",
        ),
        # Status cards
        rx.hstack(
            info_card("Drugs Loaded", State.drug_selection_count, "pill"),
            info_card("Trusts", State.trust_selection_count, "building"),
            info_card("Directories", State.directory_selection_count, "folder"),
            spacing="4",
            width="100%",
            flex_wrap="wrap",
        ),
        # Data source selector
        data_source_selector(),
        # Filter controls (date pickers, minimum patients, custom title)
        filter_controls(),
        # Filter summary
        rx.box(
            rx.vstack(
                rx.heading("Current Filter Settings", size="4", color=NHS_DARK_BLUE),
                rx.text(
                    State.filter_summary,
                    white_space="pre-wrap",
                    font_family="monospace",
                    font_size="13px",
                    color="gray",
                ),
                spacing="2",
                align="start",
                width="100%",
            ),
            padding="20px",
            background="white",
            border_radius="8px",
            border="1px solid rgb(229, 231, 235)",
            width="100%",
        ),
        # Action buttons
        rx.hstack(
            rx.button(
                rx.icon("database", size=16, aria_hidden="true"),
                "Load Reference Data",
                on_click=State.load_reference_data,
                color_scheme="blue",
                size="3",
                disabled=State.analysis_running,
                aria_label="Load reference data from CSV files",
            ),
            rx.button(
                rx.cond(
                    State.analysis_running,
                    rx.hstack(
                        rx.spinner(size="1"),
                        rx.text("Running..."),
                        spacing="2",
                        align="center",
                    ),
                    rx.hstack(
                        rx.icon("play", size=16, aria_hidden="true"),
                        rx.text("Run Analysis"),
                        spacing="2",
                        align="center",
                    ),
                ),
                on_click=State.run_analysis,
                color_scheme="green",
                size="3",
                disabled=State.analysis_running,
                aria_label="Run patient pathway analysis",
                aria_busy=State.analysis_running,
            ),
            spacing="3",
            role="toolbar",
            aria_label="Analysis actions",
        ),
        # Messages with live regions for screen readers
        rx.cond(
            State.status_message != "",
            rx.callout(
                State.status_message,
                icon="info",
                color="blue",
                role="status",
                aria_live="polite",
            ),
        ),
        rx.cond(
            State.error_message != "",
            rx.callout(
                State.error_message,
                icon="triangle-alert",
                color="red",
                role="alert",
                aria_live="assertive",
            ),
        ),
        # Chart display
        rx.cond(
            State.has_chart,
            rx.el.section(
                rx.vstack(
                    rx.hstack(
                        rx.heading("Patient Pathway Chart", size="5", color=NHS_DARK_BLUE, id="chart-heading"),
                        rx.spacer(),
                        rx.hstack(
                            rx.button(
                                rx.icon("download", size=14, aria_hidden="true"),
                                "Export HTML",
                                on_click=State.export_chart_html,
                                variant="outline",
                                size="2",
                                aria_label="Export chart as interactive HTML file",
                            ),
                            rx.button(
                                rx.icon("file-spreadsheet", size=14, aria_hidden="true"),
                                "Export CSV",
                                on_click=State.export_data_csv,
                                variant="outline",
                                size="2",
                                aria_label="Export data as CSV spreadsheet",
                            ),
                            spacing="2",
                            role="toolbar",
                            aria_label="Export options",
                        ),
                        width="100%",
                        align="center",
                    ),
                    rx.text(
                        "Click on sections to zoom in. Use the toolbar for additional options.",
                        size="2",
                        color="gray",
                    ),
                    # Export messages
                    rx.cond(
                        State.export_message != "",
                        rx.callout(
                            State.export_message,
                            icon="check",
                            color="green",
                            role="status",
                            aria_live="polite",
                        ),
                    ),
                    rx.cond(
                        State.export_error != "",
                        rx.callout(
                            State.export_error,
                            icon="triangle-alert",
                            color="red",
                            role="alert",
                        ),
                    ),
                    rx.el.figure(
                        rx.plotly(data=State.chart_data),
                        aria_label="Interactive patient pathway icicle chart showing treatment hierarchy",
                    ),
                    spacing="3",
                    width="100%",
                ),
                padding="20px",
                background="white",
                border_radius="8px",
                border="1px solid rgb(229, 231, 235)",
                width="100%",
                aria_labelledby="chart-heading",
            ),
        ),
        # Indication validation results (shown after chart)
        indication_validation_summary(),
        spacing="5",
        width="100%",
        align="start",
    )


def selection_page_content(
    title: str,
    description: str,
    items: rx.Var,
    selected_items: rx.Var,
    toggle_handler,
    select_all_handler,
    clear_handler,
    count_text: rx.Var,
    search_value: rx.Var,
    search_handler,
    clear_search_handler,
    search_result_text: rx.Var,
    extra_buttons: list[rx.Component] = None,
    page_id: str = "selection",
) -> rx.Component:
    """Generic selection page content for drugs, trusts, directories with search and accessibility."""
    heading_id = f"{page_id}-heading"
    search_id = f"{page_id}-search"
    list_id = f"{page_id}-list"

    buttons = [
        rx.button(
            "Select All",
            on_click=select_all_handler,
            variant="outline",
            size="2",
            aria_label=f"Select all {title.lower()}",
        ),
        rx.button(
            "Clear All",
            on_click=clear_handler,
            variant="outline",
            size="2",
            aria_label=f"Clear all {title.lower()} selections",
        ),
    ]
    if extra_buttons:
        buttons.extend(extra_buttons)

    return rx.vstack(
        # Header
        rx.el.header(
            rx.vstack(
                rx.heading(title, size="6", color=NHS_DARK_BLUE, id=heading_id),
                rx.text(description, color="gray"),
                rx.el.div(
                    count_text,
                    font_weight="500",
                    color=NHS_BLUE,
                    aria_live="polite",
                    aria_atomic="true",
                ),
                spacing="2",
                align="start",
            ),
            padding="20px",
            background="white",
            border_radius="8px",
            border="1px solid rgb(229, 231, 235)",
            width="100%",
        ),
        # Search input
        rx.box(
            rx.hstack(
                rx.icon("search", size=16, color="gray", aria_hidden="true"),
                rx.input(
                    placeholder=f"Search {title.lower()}...",
                    value=search_value,
                    on_change=search_handler,
                    width="100%",
                    id=search_id,
                    aria_label=f"Search {title.lower()}",
                    aria_controls=list_id,
                ),
                rx.cond(
                    search_value != "",
                    rx.button(
                        rx.icon("x", size=14, aria_hidden="true"),
                        on_click=clear_search_handler,
                        variant="ghost",
                        color_scheme="gray",
                        size="1",
                        aria_label="Clear search",
                    ),
                ),
                spacing="2",
                align="center",
                width="100%",
            ),
            padding="12px 16px",
            background="white",
            border_radius="8px",
            border="1px solid rgb(229, 231, 235)",
            width="100%",
            role="search",
        ),
        # Action buttons and search result count
        rx.hstack(
            rx.hstack(*buttons, spacing="2", role="toolbar", aria_label="Selection actions"),
            rx.spacer(),
            rx.el.div(
                search_result_text,
                font_size="14px",
                color="gray",
                aria_live="polite",
            ),
            spacing="3",
            width="100%",
            align="center",
        ),
        # Selection grid
        rx.box(
            rx.vstack(
                rx.foreach(
                    items,
                    lambda item: rx.box(
                        rx.checkbox(
                            item,
                            checked=selected_items.contains(item),
                            on_change=lambda: toggle_handler(item),
                            size="2",
                        ),
                        padding="8px 12px",
                        background=rx.cond(
                            selected_items.contains(item),
                            "rgba(0, 94, 184, 0.1)",
                            "transparent",
                        ),
                        border_radius="4px",
                        width="100%",
                    ),
                ),
                spacing="1",
                width="100%",
                max_height="500px",
                overflow_y="auto",
                id=list_id,
                role="group",
                aria_labelledby=heading_id,
            ),
            padding="16px",
            background="white",
            border_radius="8px",
            border="1px solid rgb(229, 231, 235)",
            width="100%",
        ),
        spacing="4",
        width="100%",
        align="start",
    )


def drugs_content() -> rx.Component:
    """Drug selection page content."""
    return selection_page_content(
        title="Drug Selection",
        description="Select which high-cost drugs to include in the analysis",
        items=State.filtered_drugs,
        selected_items=State.selected_drugs,
        toggle_handler=State.toggle_drug,
        select_all_handler=State.select_all_drugs,
        clear_handler=State.clear_drugs,
        count_text=State.drug_selection_count,
        search_value=State.drug_search,
        search_handler=State.set_drug_search,
        clear_search_handler=State.clear_drug_search,
        search_result_text=State.drug_search_result_count,
        extra_buttons=[
            rx.button(
                "Select Defaults",
                on_click=State.select_default_drugs,
                variant="outline",
                size="2",
                aria_label="Select default drugs (Include=1)",
            ),
        ],
        page_id="drugs",
    )


def trusts_content() -> rx.Component:
    """Trust selection page content."""
    return selection_page_content(
        title="Trust Selection",
        description="Select NHS trusts to include (leave empty for all trusts)",
        items=State.filtered_trusts,
        selected_items=State.selected_trusts,
        toggle_handler=State.toggle_trust,
        select_all_handler=State.select_all_trusts,
        clear_handler=State.clear_trusts,
        count_text=State.trust_selection_count,
        search_value=State.trust_search,
        search_handler=State.set_trust_search,
        clear_search_handler=State.clear_trust_search,
        search_result_text=State.trust_search_result_count,
        page_id="trusts",
    )


def directories_content() -> rx.Component:
    """Directory selection page content."""
    return selection_page_content(
        title="Directory Selection",
        description="Select medical directories/specialties to include (leave empty for all)",
        items=State.filtered_directories,
        selected_items=State.selected_directories,
        toggle_handler=State.toggle_directory,
        select_all_handler=State.select_all_directories,
        clear_handler=State.clear_directories,
        count_text=State.directory_selection_count,
        search_value=State.directory_search,
        search_handler=State.set_directory_search,
        clear_search_handler=State.clear_directory_search,
        search_result_text=State.directory_search_result_count,
        page_id="directories",
    )


# =============================================================================
# Page Definitions
# =============================================================================

def index() -> rx.Component:
    """Home page."""
    return main_layout(
        content_area(home_content(), page_title="Home"),
        current_page="home",
    )


def drugs_page() -> rx.Component:
    """Drug selection page."""
    return main_layout(
        content_area(drugs_content(), page_title=""),
        current_page="drugs",
    )


def trusts_page() -> rx.Component:
    """Trust selection page."""
    return main_layout(
        content_area(trusts_content(), page_title=""),
        current_page="trusts",
    )


def directories_page() -> rx.Component:
    """Directory selection page."""
    return main_layout(
        content_area(directories_content(), page_title=""),
        current_page="directories",
    )


# =============================================================================
# App Configuration
# =============================================================================

app = rx.App(
    theme=rx.theme(
        accent_color="blue",
        gray_color="slate",
        radius="medium",
    ),
)

# Add pages
app.add_page(index, route="/", title="Home | NHS HCD Analysis")
app.add_page(drugs_page, route="/drugs", title="Drug Selection | NHS HCD Analysis")
app.add_page(trusts_page, route="/trusts", title="Trust Selection | NHS HCD Analysis")
app.add_page(directories_page, route="/directories", title="Directory Selection | NHS HCD Analysis")
