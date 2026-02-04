"""
Large dataset performance tests for the Patient Pathway Analysis tool.

This module tests the system's ability to handle realistic workloads:
1. Full dataset analysis (all drugs, trusts, directories)
2. Memory usage under load
3. Scalability characteristics

Run with: python -m pytest tests/test_large_dataset_performance.py -v
"""

import gc
import time
import tracemalloc
from datetime import date
from pathlib import Path

import pytest

# Mark all tests in this module as large dataset tests
pytestmark = pytest.mark.largedata


class TestLargeDatasetPerformance:
    """Performance tests with full dataset."""

    @pytest.fixture(autouse=True)
    def setup_paths(self):
        """Set up paths and verify data exists."""
        from core import default_paths
        from data_processing import get_loader

        # Check if database exists
        db_path = default_paths.data_dir / "pathways.db"
        if not db_path.exists():
            pytest.skip("SQLite database not found")

        self.paths = default_paths
        self.loader = get_loader('sqlite')

        # Load data once
        result = self.loader.load()
        if result is None or result.df is None or len(result.df) == 0:
            pytest.skip("No data available in database")

        self.df = result.df
        self.row_count = result.row_count

    def test_data_load_time_acceptable(self):
        """Data loading should complete in under 5 seconds."""
        from data_processing import get_loader

        gc.collect()
        start = time.perf_counter()
        loader = get_loader('sqlite')
        result = loader.load()
        elapsed = time.perf_counter() - start

        assert result is not None, "Data loading failed"
        assert result.row_count > 0, "No data loaded"
        # Allow 5 seconds for data loading
        assert elapsed < 5.0, f"Data loading took {elapsed:.2f}s (target: <5s)"

    def test_analysis_pipeline_completes(self):
        """Full analysis pipeline should complete without error."""
        from analysis.pathway_analyzer import generate_icicle_chart
        import pandas as pd

        # Get available filters from actual data
        trusts = self.df['Provider Code'].unique().tolist()[:20]
        drugs = self.df['Drug Name'].dropna().unique().tolist()[:10]
        directories = self.df['Directory'].dropna().unique().tolist()

        # Load org codes for trust name mapping
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = []
        for t in trusts:
            if t in org_codes.index:
                trust_names.append(org_codes.loc[t, 'Name'])
        if not trust_names:
            trust_names = org_codes['Name'].tolist()[:20]

        # Run analysis with reasonable filter
        ice_df, title = generate_icicle_chart(
            df=self.df,
            start_date="2020-01-01",
            end_date="2025-01-01",
            last_seen_date="2020-01-01",
            trust_filter=trust_names,
            drug_filter=drugs,
            directory_filter=directories,
            minimum_num_patients=1,
            title="Large Dataset Test",
            paths=self.paths,
        )

        # Should produce some results
        assert ice_df is not None, "Analysis produced no results"
        assert len(ice_df) > 0, "Analysis produced empty results"

    def test_analysis_pipeline_time_acceptable(self):
        """Analysis pipeline should complete in under 60 seconds."""
        from analysis.pathway_analyzer import generate_icicle_chart
        import pandas as pd

        # Get available filters from actual data
        trusts = self.df['Provider Code'].unique().tolist()[:20]
        drugs = self.df['Drug Name'].dropna().unique().tolist()[:10]
        directories = self.df['Directory'].dropna().unique().tolist()

        # Load org codes for trust name mapping
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = []
        for t in trusts:
            if t in org_codes.index:
                trust_names.append(org_codes.loc[t, 'Name'])
        if not trust_names:
            trust_names = org_codes['Name'].tolist()[:20]

        gc.collect()
        start = time.perf_counter()

        ice_df, title = generate_icicle_chart(
            df=self.df,
            start_date="2020-01-01",
            end_date="2025-01-01",
            last_seen_date="2020-01-01",
            trust_filter=trust_names,
            drug_filter=drugs,
            directory_filter=directories,
            minimum_num_patients=1,
            title="Performance Test",
            paths=self.paths,
        )

        elapsed = time.perf_counter() - start

        # Allow 60 seconds for full analysis (observed ~19s with 440K rows)
        assert elapsed < 60.0, f"Analysis took {elapsed:.2f}s (target: <60s)"
        print(f"\n  Analysis completed in {elapsed:.2f}s with {len(ice_df) if ice_df is not None else 0} result rows")

    def test_memory_usage_acceptable(self):
        """Memory usage should not exceed 500MB during analysis."""
        from analysis.pathway_analyzer import generate_icicle_chart
        import pandas as pd

        # Get available filters from actual data
        trusts = self.df['Provider Code'].unique().tolist()[:15]
        drugs = self.df['Drug Name'].dropna().unique().tolist()[:5]
        directories = self.df['Directory'].dropna().unique().tolist()

        # Load org codes for trust name mapping
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = []
        for t in trusts:
            if t in org_codes.index:
                trust_names.append(org_codes.loc[t, 'Name'])
        if not trust_names:
            trust_names = org_codes['Name'].tolist()[:15]

        gc.collect()
        tracemalloc.start()

        ice_df, title = generate_icicle_chart(
            df=self.df,
            start_date="2020-01-01",
            end_date="2025-01-01",
            last_seen_date="2020-01-01",
            trust_filter=trust_names,
            drug_filter=drugs,
            directory_filter=directories,
            minimum_num_patients=1,
            title="Memory Test",
            paths=self.paths,
        )

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        # Allow 500MB peak memory
        assert peak_mb < 500, f"Peak memory {peak_mb:.1f}MB exceeds 500MB limit"
        print(f"\n  Peak memory usage: {peak_mb:.1f}MB")

    def test_figure_creation_scales(self):
        """Figure creation time should scale linearly with result size."""
        from visualization.plotly_generator import create_icicle_figure
        import pandas as pd
        import numpy as np

        # Test with different sizes
        sizes = [100, 500, 1000, 2000]
        times = []

        for n_rows in sizes:
            sample_data = {
                'parents': ['N&WICS'] * n_rows,
                'ids': [f'N&WICS - Test{i}' for i in range(n_rows)],
                'labels': [f'Test{i}' for i in range(n_rows)],
                'value': np.random.randint(1, 100, n_rows),
                'colour': np.random.random(n_rows),
                'cost': np.random.randint(1000, 100000, n_rows),
                'costpp': np.random.randint(100, 10000, n_rows),
                'cost_pp_pa': [str(np.random.randint(100, 10000)) for _ in range(n_rows)],
                'First seen': pd.to_datetime(['2024-01-01'] * n_rows),
                'Last seen': pd.to_datetime(['2024-12-31'] * n_rows),
                'First seen (Parent)': ['2024-01-01'] * n_rows,
                'Last seen (Parent)': ['2024-12-31'] * n_rows,
                'average_spacing': ['Test spacing'] * n_rows,
                'avg_days': pd.to_timedelta([100] * n_rows, unit='D'),
            }
            sample_df = pd.DataFrame(sample_data)

            gc.collect()
            start = time.perf_counter()
            fig = create_icicle_figure(sample_df, f"Scale Test {n_rows}")
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Check that time scaling is roughly linear (not exponential)
        # If time doubles when size doubles, it's linear
        # We allow some variance, so check that 10x data doesn't take more than 20x time
        time_ratio = times[-1] / times[0]
        size_ratio = sizes[-1] / sizes[0]

        # Allow 3x the expected linear scaling
        max_allowed_ratio = size_ratio * 3

        assert time_ratio < max_allowed_ratio, (
            f"Figure creation doesn't scale well: "
            f"{sizes[-1]} rows took {times[-1]:.3f}s vs {sizes[0]} rows at {times[0]:.3f}s "
            f"(ratio {time_ratio:.1f}x, expected <{max_allowed_ratio:.1f}x)"
        )

        print(f"\n  Figure scaling: {sizes[0]} rows: {times[0]*1000:.1f}ms, "
              f"{sizes[-1]} rows: {times[-1]*1000:.1f}ms (ratio: {time_ratio:.1f}x)")


class TestDataVolumeStress:
    """Stress tests to verify system handles various data volumes."""

    @pytest.fixture(autouse=True)
    def setup_paths(self):
        """Set up paths and verify data exists."""
        from core import default_paths
        from data_processing import get_loader

        # Check if database exists
        db_path = default_paths.data_dir / "pathways.db"
        if not db_path.exists():
            pytest.skip("SQLite database not found")

        self.paths = default_paths
        self.loader = get_loader('sqlite')

        # Load data once
        result = self.loader.load()
        if result is None or result.df is None or len(result.df) == 0:
            pytest.skip("No data available in database")

        self.df = result.df

    def test_handles_all_drugs(self):
        """Analysis can handle filtering by all drugs."""
        from analysis.pathway_analyzer import prepare_data
        import pandas as pd

        all_drugs = self.df['Drug Name'].dropna().unique().tolist()

        # Load org codes
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = org_codes['Name'].tolist()[:5]

        result = prepare_data(
            df=self.df,
            trust_filter=trust_names,
            drug_filter=all_drugs,
            directory_filter=self.df['Directory'].dropna().unique().tolist(),
            paths=self.paths,
        )

        # Should complete without error (returns tuple)
        assert result is not None
        assert len(result) == 3  # (df, org_codes, directory_df)

    def test_handles_all_trusts(self):
        """Analysis can handle filtering by all trusts."""
        from analysis.pathway_analyzer import prepare_data
        import pandas as pd

        # Load org codes
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        all_trust_names = org_codes['Name'].tolist()

        result = prepare_data(
            df=self.df,
            trust_filter=all_trust_names,
            drug_filter=['ADALIMUMAB', 'ETANERCEPT'],
            directory_filter=self.df['Directory'].dropna().unique().tolist(),
            paths=self.paths,
        )

        # Should complete without error (returns tuple)
        assert result is not None
        assert len(result) == 3  # (df, org_codes, directory_df)

    def test_handles_wide_date_range(self):
        """Analysis can handle a wide date range via generate_icicle_chart."""
        from analysis.pathway_analyzer import generate_icicle_chart
        import pandas as pd

        # Load org codes
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = org_codes['Name'].tolist()[:10]

        # Use very wide date range via full pipeline
        ice_df, title = generate_icicle_chart(
            df=self.df,
            start_date="2010-01-01",
            end_date="2030-01-01",
            last_seen_date="2010-01-01",
            trust_filter=trust_names,
            drug_filter=self.df['Drug Name'].dropna().unique().tolist()[:5],
            directory_filter=self.df['Directory'].dropna().unique().tolist(),
            minimum_num_patients=1,
            title="Wide Date Range Test",
            paths=self.paths,
        )

        # Should complete without error
        assert ice_df is not None or ice_df is None  # Just verifying no exception

    def test_handles_minimum_patient_threshold(self):
        """Analysis correctly applies minimum patient threshold."""
        from analysis.pathway_analyzer import generate_icicle_chart
        import pandas as pd

        # Load org codes
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = org_codes['Name'].tolist()[:10]

        # Run with minimum 50 patients
        ice_df_50, _ = generate_icicle_chart(
            df=self.df,
            start_date="2020-01-01",
            end_date="2025-01-01",
            last_seen_date="2020-01-01",
            trust_filter=trust_names,
            drug_filter=self.df['Drug Name'].dropna().unique().tolist()[:5],
            directory_filter=self.df['Directory'].dropna().unique().tolist(),
            minimum_num_patients=50,
            title="Threshold Test 50",
            paths=self.paths,
        )

        # Run with minimum 1 patient
        ice_df_1, _ = generate_icicle_chart(
            df=self.df,
            start_date="2020-01-01",
            end_date="2025-01-01",
            last_seen_date="2020-01-01",
            trust_filter=trust_names,
            drug_filter=self.df['Drug Name'].dropna().unique().tolist()[:5],
            directory_filter=self.df['Directory'].dropna().unique().tolist(),
            minimum_num_patients=1,
            title="Threshold Test 1",
            paths=self.paths,
        )

        # Higher threshold should produce fewer or equal results
        len_50 = len(ice_df_50) if ice_df_50 is not None else 0
        len_1 = len(ice_df_1) if ice_df_1 is not None else 0

        assert len_50 <= len_1, (
            f"Higher minimum threshold should produce fewer results: "
            f"min=50 gave {len_50} rows, min=1 gave {len_1} rows"
        )


class TestConcurrentOperations:
    """Tests for handling multiple operations."""

    @pytest.fixture(autouse=True)
    def setup_paths(self):
        """Set up paths and verify data exists."""
        from core import default_paths
        from data_processing import get_loader

        # Check if database exists
        db_path = default_paths.data_dir / "pathways.db"
        if not db_path.exists():
            pytest.skip("SQLite database not found")

        self.paths = default_paths

    def test_multiple_data_loads(self):
        """Multiple data loads should not cause issues."""
        from data_processing import get_loader

        results = []
        for i in range(3):
            loader = get_loader('sqlite')
            result = loader.load()
            if result is not None:
                results.append(result.row_count)

        # All loads should return same row count
        assert len(set(results)) == 1, f"Inconsistent row counts: {results}"

    def test_sequential_analyses(self):
        """Multiple sequential analyses should complete."""
        from analysis.pathway_analyzer import generate_icicle_chart
        from data_processing import get_loader
        import pandas as pd

        # Load data
        loader = get_loader('sqlite')
        result = loader.load()
        if result is None or result.df is None:
            pytest.skip("No data available")

        df = result.df

        # Load org codes
        org_codes = pd.read_csv(self.paths.org_codes_csv, index_col=1)
        trust_names = org_codes['Name'].tolist()[:5]

        # Run multiple analyses
        for i in range(3):
            ice_df, title = generate_icicle_chart(
                df=df,
                start_date="2020-01-01",
                end_date="2025-01-01",
                last_seen_date="2020-01-01",
                trust_filter=trust_names,
                drug_filter=['ADALIMUMAB'],
                directory_filter=df['Directory'].dropna().unique().tolist(),
                minimum_num_patients=1,
                title=f"Sequential Test {i+1}",
                paths=self.paths,
            )

            # Each should complete
            assert ice_df is not None or ice_df is None  # Just check no error
