"""
Test Phase 3.4.4: Measure directory assignment "Undefined" rate with real Snowflake data.

This test fetches HCD activity data from Snowflake, runs it through the directory
assignment pipeline, and measures what percentage of records end up with "Undefined"
directory vs. successfully assigned directories.
"""

import json
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.data import patient_id, drug_names, department_identification
from core import default_paths


def load_snowflake_result(json_file: Path) -> pd.DataFrame:
    """Load Snowflake query result from JSON file and convert to DataFrame."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # The result is in format: [{"type": "text", "text": "..."}]
    # where text contains JSON with {"columns": [...], "rows": [...]}
    if isinstance(data, list) and len(data) > 0 and 'text' in data[0]:
        records_text = data[0]['text']
        result_obj = json.loads(records_text)
        # Extract rows from the result object
        if isinstance(result_obj, dict) and 'rows' in result_obj:
            records = result_obj['rows']
        else:
            records = result_obj
    else:
        records = data

    return pd.DataFrame(records)


def analyze_directory_sources(df: pd.DataFrame) -> dict:
    """Analyze the distribution of Directory_Source values."""
    if 'Directory_Source' not in df.columns:
        return {"error": "Directory_Source column not found"}

    source_counts = df['Directory_Source'].value_counts()
    total = len(df)

    result = {
        "total_records": total,
        "source_distribution": {},
        "undefined_rate": 0.0,
        "assigned_rate": 0.0
    }

    for source, count in source_counts.items():
        pct = (count / total) * 100
        result["source_distribution"][source] = {
            "count": int(count),
            "percentage": round(pct, 2)
        }

    # Calculate undefined vs assigned rates
    undefined_count = source_counts.get('UNDEFINED', 0)
    result["undefined_rate"] = round((undefined_count / total) * 100, 2) if total > 0 else 0
    result["assigned_rate"] = round(100 - result["undefined_rate"], 2)

    return result


def analyze_by_drug(df: pd.DataFrame) -> dict:
    """Analyze undefined rate by drug."""
    if 'Drug Name' not in df.columns or 'Directory_Source' not in df.columns:
        return {"error": "Required columns not found"}

    results = {}
    for drug in df['Drug Name'].dropna().unique():
        drug_df = df[df['Drug Name'] == drug]
        total = len(drug_df)
        undefined = len(drug_df[drug_df['Directory_Source'] == 'UNDEFINED'])
        results[drug] = {
            "total": total,
            "undefined": undefined,
            "undefined_rate": round((undefined / total) * 100, 2) if total > 0 else 0
        }

    return results


def main():
    """Main function to run the real data test."""
    # Path to the Snowflake result file (updated 2026-02-04)
    result_file = Path(r"C:\Users\charlwoodand\.claude\projects\C--Users-charlwoodand-Ralph-local-Tasks-Patient-pathway-analysis\2b846818-a586-47de-bfb9-a740bd07fc70\tool-results\mcp-snowflake-mcp-read_data-1770199331688.txt")

    if not result_file.exists():
        print(f"ERROR: Result file not found: {result_file}")
        return

    print("Loading Snowflake data...")
    df = load_snowflake_result(result_file)
    print(f"Loaded {len(df)} records")
    print(f"Columns: {list(df.columns)}")

    # Rename columns to match expected format for tools/data.py functions
    column_mapping = {
        'ProviderCode': 'Provider Code',
        'PersonKey': 'PersonKey',
        'DrugName': 'Drug Name',
        'InterventionDate': 'Intervention Date',
        'TreatmentFunctionCode': 'Treatment Function Code',
        'AdditionalDetail1': 'Additional Detail 1',
        'AdditionalDescription1': 'Additional Description 1',
        'AdditionalDetail2': 'Additional Detail 2',
        'AdditionalDescription2': 'Additional Description 2',
        'PriceActual': 'Price Actual',
        'OrganisationName': 'OrganisationName'
    }

    df = df.rename(columns=column_mapping)
    print(f"Renamed columns: {list(df.columns)}")

    # Step 1: Generate UPID
    print("\nStep 1: Generating UPID...")
    df = patient_id(df)
    print(f"Sample UPIDs: {df['UPID'].head(5).tolist()}")

    # Step 2: Standardize drug names
    print("\nStep 2: Standardizing drug names...")
    df = drug_names(df, default_paths)
    print(f"Unique drugs after standardization: {df['Drug Name'].dropna().unique().tolist()}")

    # Step 3: Run directory assignment
    print("\nStep 3: Running directory assignment...")
    df = department_identification(df, default_paths)

    # Step 4: Analyze results
    print("\n" + "="*60)
    print("DIRECTORY ASSIGNMENT RESULTS")
    print("="*60)

    overall_stats = analyze_directory_sources(df)

    print(f"\nTotal records processed: {overall_stats['total_records']}")
    print(f"\nDirectory Source Distribution:")
    for source, stats in sorted(overall_stats['source_distribution'].items(),
                                 key=lambda x: -x[1]['count']):
        print(f"  {source}: {stats['count']:,} ({stats['percentage']:.1f}%)")

    print(f"\n*** UNDEFINED RATE: {overall_stats['undefined_rate']:.1f}% ***")
    print(f"*** ASSIGNED RATE:  {overall_stats['assigned_rate']:.1f}% ***")

    # Analyze by drug
    print("\n" + "-"*60)
    print("UNDEFINED RATE BY DRUG")
    print("-"*60)

    drug_stats = analyze_by_drug(df)
    for drug, stats in sorted(drug_stats.items(), key=lambda x: -x[1]['undefined_rate']):
        print(f"  {drug}: {stats['undefined_rate']:.1f}% undefined ({stats['undefined']:,}/{stats['total']:,})")

    # Show sample of directory assignments
    print("\n" + "-"*60)
    print("SAMPLE DIRECTORY ASSIGNMENTS")
    print("-"*60)

    sample_cols = ['UPID', 'Drug Name', 'Directory', 'Directory_Source']
    available_cols = [c for c in sample_cols if c in df.columns]
    print(df[available_cols].head(20).to_string())

    return overall_stats, drug_stats


if __name__ == "__main__":
    main()
