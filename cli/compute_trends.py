"""
CLI command for computing historical trend snapshots.

This command fetches all activity data from Snowflake once, then replays the
pathway computation for ~10 historical 6-month endpoints (2021-06-30 through
2025-12-31). For each period, level-3 node summaries (drug × directory) are
extracted and stored in a `pathway_trends` table in pathways.db.

The Dash "Trends" tab then queries this table to show how drug patient counts,
costs, and cost-per-patient have changed over time.

Usage:
    python -m cli.compute_trends
    python -m cli.compute_trends --start 2022-01-01 --end 2025-06-30
    python -m cli.compute_trends --interval 12  # 12-month steps
    python -m cli.compute_trends --dry-run -v

Run `python -m cli.compute_trends --help` for full options.
"""

import argparse
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path when run as `python -m cli.compute_trends`
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core import PathConfig, default_paths
from core.logging_config import get_logger, setup_logging
from data_processing.pathway_pipeline import (
    DateFilterConfig,
    fetch_and_transform_data,
    process_pathway_for_date_filter,
    extract_denormalized_fields,
)

logger = get_logger(__name__)

# Use the all_6mo config: all years initiated, last seen within 6 months
TREND_FILTER_CONFIG = DateFilterConfig(
    id="all_6mo", initiated_years=None, last_seen_months=6
)

CREATE_TRENDS_TABLE = """
CREATE TABLE IF NOT EXISTS pathway_trends (
    period_end   TEXT    NOT NULL,
    drug         TEXT    NOT NULL,
    directory    TEXT    NOT NULL,
    patients     INTEGER NOT NULL,
    total_cost   REAL    NOT NULL,
    cost_pp_pa   REAL,
    PRIMARY KEY (period_end, drug, directory)
)
"""


def generate_period_endpoints(
    start: date,
    end: date,
    interval_months: int = 6,
) -> list[date]:
    """Generate period end-dates from start to end at interval_months steps."""
    endpoints = []
    current = start
    while current <= end:
        endpoints.append(current)
        # Advance by interval_months
        month = current.month + interval_months
        year = current.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        # Use last day of the target month or keep day if valid
        import calendar
        max_day = calendar.monthrange(year, month)[1]
        day = min(current.day, max_day)
        current = date(year, month, day)
    return endpoints


def extract_level3_summaries(ice_df) -> list[dict]:
    """Extract level-3 (drug) node summaries from ice_df DataFrame.

    Returns list of dicts with: drug, directory, patients, total_cost, cost_pp_pa
    """
    import pandas as pd

    level3 = ice_df[ice_df["level"] == 3].copy()
    if level3.empty:
        return []

    # Extract denormalized fields to get drug and directory
    level3 = extract_denormalized_fields(level3)

    rows = []
    for _, row in level3.iterrows():
        drug_seq = row.get("drug_sequence", "")
        directory = row.get("directory", "")
        if not drug_seq or not directory:
            continue

        cost_pp_pa = row.get("cost_pp_pa")
        try:
            cost_pp_pa = float(cost_pp_pa) if pd.notna(cost_pp_pa) and cost_pp_pa != "" else None
        except (ValueError, TypeError):
            cost_pp_pa = None

        rows.append({
            "drug": drug_seq,
            "directory": directory,
            "patients": int(row.get("value", 0)),
            "total_cost": float(row.get("cost", 0)),
            "cost_pp_pa": cost_pp_pa,
        })

    return rows


def compute_trends(
    start: date = date(2021, 6, 30),
    end: date = date(2025, 12, 31),
    interval_months: int = 6,
    minimum_patients: int = 5,
    db_path: Optional[Path] = None,
    paths: Optional[PathConfig] = None,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Main function: fetch data, replay pathway computation for each period, store summaries.

    Args:
        start: First period endpoint
        end: Last period endpoint
        interval_months: Months between endpoints
        minimum_patients: Min patients for pathway inclusion
        db_path: Path to pathways.db (uses default if None)
        paths: PathConfig for reference files
        dry_run: If True, compute but don't write to DB

    Returns:
        (success, message) tuple
    """
    if paths is None:
        paths = default_paths

    if db_path is None:
        db_path = paths.data_dir / "pathways.db"

    endpoints = generate_period_endpoints(start, end, interval_months)
    logger.info(f"Will compute trends for {len(endpoints)} periods: "
                f"{endpoints[0].isoformat()} to {endpoints[-1].isoformat()}")

    # Load default filters (same as refresh_pathways)
    from cli.refresh_pathways import get_default_filters
    trust_filter, drug_filter, directory_filter = get_default_filters(paths)

    if not drug_filter:
        return False, "No drugs found in default filters"

    logger.info(f"Filters: {len(trust_filter)} trusts, {len(drug_filter)} drugs, "
                f"{len(directory_filter)} directories")

    start_time = time.time()

    # Step 1: Fetch all activity data from Snowflake (one-time)
    logger.info("Step 1: Fetching all activity data from Snowflake...")
    df = fetch_and_transform_data(paths=paths)

    if df.empty:
        return False, "No data returned from Snowflake"

    logger.info(f"Fetched {len(df)} records")

    # Step 2: Create trends table
    if not dry_run:
        conn = sqlite3.connect(str(db_path))
        conn.execute(CREATE_TRENDS_TABLE)
        conn.commit()
        logger.info("Created pathway_trends table (if not exists)")
    else:
        conn = None

    # Step 3: Process each historical endpoint
    total_rows = 0
    period_stats = []

    for i, endpoint in enumerate(endpoints, 1):
        logger.info(f"Period {i}/{len(endpoints)}: computing pathways as of {endpoint.isoformat()}...")

        ice_df = process_pathway_for_date_filter(
            df=df,
            config=TREND_FILTER_CONFIG,
            trust_filter=trust_filter,
            drug_filter=drug_filter,
            directory_filter=directory_filter,
            minimum_patients=minimum_patients,
            max_date=endpoint,
            paths=paths,
        )

        if ice_df is None:
            logger.warning(f"  No data for period ending {endpoint.isoformat()}")
            period_stats.append((endpoint, 0))
            continue

        summaries = extract_level3_summaries(ice_df)
        period_stats.append((endpoint, len(summaries)))
        total_rows += len(summaries)

        logger.info(f"  {len(summaries)} drug×directory rows for {endpoint.isoformat()}")

        if not dry_run and conn and summaries:
            # Insert/replace rows for this period
            conn.executemany(
                "INSERT OR REPLACE INTO pathway_trends "
                "(period_end, drug, directory, patients, total_cost, cost_pp_pa) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        endpoint.isoformat(),
                        s["drug"],
                        s["directory"],
                        s["patients"],
                        s["total_cost"],
                        s["cost_pp_pa"],
                    )
                    for s in summaries
                ],
            )
            conn.commit()

    if conn:
        conn.close()

    elapsed = time.time() - start_time

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info(f"Trend computation complete in {elapsed:.1f}s")
    logger.info(f"Periods processed: {len(endpoints)}")
    logger.info(f"Total rows: {total_rows}")
    for ep, count in period_stats:
        logger.info(f"  {ep.isoformat()}: {count} rows")
    if dry_run:
        logger.info("(DRY RUN — no data written)")
    logger.info("=" * 50)

    return True, f"Computed {total_rows} trend rows across {len(endpoints)} periods in {elapsed:.1f}s"


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compute historical trend snapshots for pathway analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Default: 6-month intervals from 2021-06-30 to 2025-12-31
    python -m cli.compute_trends

    # Custom date range
    python -m cli.compute_trends --start 2022-01-01 --end 2025-06-30

    # 12-month intervals
    python -m cli.compute_trends --interval 12

    # Dry run
    python -m cli.compute_trends --dry-run -v
        """,
    )

    parser.add_argument(
        "--start",
        type=str,
        default="2021-06-30",
        help="First period endpoint (ISO date, default: 2021-06-30)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2025-12-31",
        help="Last period endpoint (ISO date, default: 2025-12-31)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=6,
        help="Months between endpoints (default: 6)",
    )
    parser.add_argument(
        "--minimum-patients",
        type=int,
        default=5,
        help="Min patients per pathway (default: 5)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to pathways.db (default: data/pathways.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute but don't write to database",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    import logging
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    db_path_arg = Path(args.db_path) if args.db_path else None

    success, message = compute_trends(
        start=start_date,
        end=end_date,
        interval_months=args.interval,
        minimum_patients=args.minimum_patients,
        db_path=db_path_arg,
        dry_run=args.dry_run,
    )

    if success:
        print(f"\n[OK] {message}")
        return 0
    else:
        print(f"\n[FAILED] {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
