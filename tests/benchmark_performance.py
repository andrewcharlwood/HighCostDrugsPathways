"""
Performance benchmark for the Patient Pathway Analysis tool.

This script measures:
1. Module import time
2. Data loading time (SQLite)
3. Analysis pipeline execution time
4. Peak memory usage

Run with: python -m tests.benchmark_performance
"""

import gc
import sys
import time
import tracemalloc
from datetime import date
from pathlib import Path
from typing import Any

# Store results for final report
results: dict[str, Any] = {}


def measure_time(func, *args, **kwargs):
    """Measure execution time of a function."""
    gc.collect()  # Clean up before timing
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


def measure_memory(func, *args, **kwargs):
    """Measure peak memory usage of a function."""
    gc.collect()  # Clean up before measuring
    tracemalloc.start()

    result = func(*args, **kwargs)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return result, peak


def benchmark_imports():
    """Benchmark module import times."""
    print("\n" + "=" * 60)
    print("1. MODULE IMPORT BENCHMARKS")
    print("=" * 60)

    import_times = {}

    # Benchmark core imports
    start = time.perf_counter()
    from core import PathConfig, AnalysisFilters, default_paths
    import_times['core'] = time.perf_counter() - start

    # Benchmark data_processing imports
    start = time.perf_counter()
    from data_processing import DatabaseManager, get_loader
    import_times['data_processing'] = time.perf_counter() - start

    # Benchmark analysis imports
    start = time.perf_counter()
    from analysis.pathway_analyzer import generate_icicle_chart
    import_times['analysis'] = time.perf_counter() - start

    # Benchmark visualization imports
    start = time.perf_counter()
    from visualization.plotly_generator import create_icicle_figure
    import_times['visualization'] = time.perf_counter() - start

    # Benchmark pandas/numpy
    start = time.perf_counter()
    import pandas as pd
    import numpy as np
    import_times['pandas+numpy'] = time.perf_counter() - start

    total_import_time = sum(import_times.values())

    print(f"\n{'Module':<25} {'Time (ms)':<15}")
    print("-" * 40)
    for module, elapsed in import_times.items():
        print(f"{module:<25} {elapsed*1000:>10.1f} ms")
    print("-" * 40)
    print(f"{'TOTAL':<25} {total_import_time*1000:>10.1f} ms")

    results['import_times'] = import_times
    results['total_import_time'] = total_import_time

    return import_times


def benchmark_data_loading():
    """Benchmark data loading from different sources."""
    print("\n" + "=" * 60)
    print("2. DATA LOADING BENCHMARKS")
    print("=" * 60)

    from data_processing import get_loader
    from core import default_paths
    import pandas as pd

    load_times = {}
    row_counts = {}

    # Check if SQLite database exists
    db_path = default_paths.data_dir / "pathways.db"
    if db_path.exists():
        print(f"\nLoading from SQLite: {db_path}")

        # SQLite loading
        loader = get_loader('sqlite')
        result, elapsed = measure_time(loader.load)
        load_times['sqlite'] = elapsed
        row_counts['sqlite'] = result.row_count if result is not None else 0

        print(f"  Rows loaded: {row_counts['sqlite']:,}")
        print(f"  Time: {elapsed*1000:.1f} ms ({elapsed:.2f} seconds)")
        print(f"  Internal load time: {result.load_time_seconds*1000:.1f} ms")

        # Store for later use
        results['loaded_df'] = result.df
    else:
        print(f"SQLite database not found at {db_path}")
        load_times['sqlite'] = None

    results['load_times'] = load_times
    results['row_counts'] = row_counts

    return load_times


def benchmark_analysis_pipeline():
    """Benchmark the full analysis pipeline."""
    print("\n" + "=" * 60)
    print("3. ANALYSIS PIPELINE BENCHMARKS")
    print("=" * 60)

    from analysis.pathway_analyzer import (
        generate_icicle_chart,
        prepare_data,
        calculate_statistics,
        build_hierarchy,
        prepare_chart_data,
    )
    from core import default_paths
    import pandas as pd

    # Get loaded data or load it
    df = results.get('loaded_df')
    if df is None or len(df) == 0:
        print("No data available for analysis benchmarks")
        return {}

    analysis_times = {}

    # Get available trusts, drugs, directories from data
    trusts = df['Provider Code'].unique().tolist()[:10]  # Limit to 10 trusts
    drugs = ['ADALIMUMAB', 'ETANERCEPT', 'INFLIXIMAB', 'SECUKINUMAB', 'RITUXIMAB']
    directories = df['Directory'].dropna().unique().tolist()

    # Filter to drugs that exist in data
    available_drugs = [d for d in drugs if d in df['Drug Name'].values]
    if not available_drugs:
        available_drugs = df['Drug Name'].unique().tolist()[:5]

    print(f"\nAnalysis parameters:")
    print(f"  Trusts: {len(trusts)}")
    print(f"  Drugs: {available_drugs}")
    print(f"  Directories: {len(directories)}")
    print(f"  Data rows: {len(df):,}")

    # Load org_codes for mapping trust codes to names
    org_codes = pd.read_csv(default_paths.org_codes_csv, index_col=1)
    trust_names = []
    for t in trusts:
        if t in org_codes.index:
            trust_names.append(org_codes.loc[t, 'Name'])

    if not trust_names:
        trust_names = org_codes['Name'].tolist()[:10]

    # Benchmark full pipeline
    print("\n  Running full pipeline benchmark...")

    # Use date range that should include data
    # Look at actual data dates
    if 'Intervention Date' in df.columns:
        min_date = df['Intervention Date'].min()
        max_date = df['Intervention Date'].max()
        print(f"  Data date range: {min_date} to {max_date}")

        # Use a reasonable analysis window
        start_date = "2020-01-01"
        end_date = "2025-01-01"
        last_seen_date = "2020-01-01"
    else:
        start_date = "2020-01-01"
        end_date = "2025-01-01"
        last_seen_date = "2020-01-01"

    print(f"  Analysis window: {start_date} to {end_date}")
    print(f"  Last seen filter: > {last_seen_date}")

    # Full pipeline with memory tracking
    gc.collect()
    tracemalloc.start()
    start_time = time.perf_counter()

    try:
        ice_df, title = generate_icicle_chart(
            df=df,
            start_date=start_date,
            end_date=end_date,
            last_seen_date=last_seen_date,
            trust_filter=trust_names,
            drug_filter=available_drugs,
            directory_filter=directories,
            minimum_num_patients=1,
            title="Performance Benchmark",
            paths=default_paths,
        )

        elapsed = time.perf_counter() - start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        analysis_times['full_pipeline'] = elapsed
        results['analysis_memory_peak'] = peak

        if ice_df is not None:
            print(f"\n  Pipeline completed:")
            print(f"    Execution time: {elapsed*1000:.1f} ms ({elapsed:.2f} seconds)")
            print(f"    Peak memory: {peak / 1024 / 1024:.1f} MB")
            print(f"    Result rows: {len(ice_df)}")
            print(f"    Chart title: {title}")
        else:
            print("\n  Pipeline returned no data (likely date filtering)")
            print(f"    Execution time: {elapsed*1000:.1f} ms")

    except Exception as e:
        tracemalloc.stop()
        print(f"\n  Pipeline error: {e}")
        traceback_str = ''.join(tracemalloc.format_exc() if hasattr(tracemalloc, 'format_exc') else [])
        print(f"  {str(e)}")
        analysis_times['full_pipeline'] = None

    results['analysis_times'] = analysis_times
    return analysis_times


def benchmark_visualization():
    """Benchmark chart generation."""
    print("\n" + "=" * 60)
    print("4. VISUALIZATION BENCHMARKS")
    print("=" * 60)

    from visualization.plotly_generator import create_icicle_figure
    import pandas as pd
    import numpy as np

    viz_times = {}

    # Create sample data for visualization benchmark
    n_rows = 1000
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

    print(f"\n  Sample data: {n_rows} rows")

    # Benchmark figure creation
    fig, elapsed = measure_time(create_icicle_figure, sample_df, "Benchmark Test")
    viz_times['figure_creation'] = elapsed

    print(f"  Figure creation: {elapsed*1000:.1f} ms")

    results['viz_times'] = viz_times
    return viz_times


def print_summary():
    """Print final summary report."""
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)

    print("\nRESULTS:")

    # Import times
    if 'total_import_time' in results:
        print(f"\n  Import time (all modules): {results['total_import_time']*1000:.1f} ms")

    # Data loading
    if 'load_times' in results and results['load_times'].get('sqlite'):
        print(f"  SQLite load time: {results['load_times']['sqlite']*1000:.1f} ms")
        if 'row_counts' in results:
            print(f"  Rows loaded: {results['row_counts'].get('sqlite', 0):,}")

    # Analysis
    if 'analysis_times' in results and results['analysis_times'].get('full_pipeline'):
        print(f"  Analysis pipeline: {results['analysis_times']['full_pipeline']*1000:.1f} ms")

    # Memory
    if 'analysis_memory_peak' in results:
        print(f"  Peak memory (analysis): {results['analysis_memory_peak'] / 1024 / 1024:.1f} MB")

    # Visualization
    if 'viz_times' in results:
        print(f"  Figure creation: {results['viz_times'].get('figure_creation', 0)*1000:.1f} ms")

    # Calculate total startup time (imports + data loading)
    startup_time = results.get('total_import_time', 0)
    if results.get('load_times', {}).get('sqlite'):
        startup_time += results['load_times']['sqlite']
    print(f"\n  Estimated startup time: {startup_time*1000:.1f} ms ({startup_time:.2f} seconds)")

    print("\n" + "=" * 60)


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 60)
    print("PATIENT PATHWAY ANALYSIS - PERFORMANCE BENCHMARK")
    print("=" * 60)
    print(f"\nPython version: {sys.version}")
    print(f"Platform: {sys.platform}")

    # Run benchmarks in order
    benchmark_imports()
    benchmark_data_loading()
    benchmark_analysis_pipeline()
    benchmark_visualization()

    # Print summary
    print_summary()

    return results


if __name__ == "__main__":
    main()
