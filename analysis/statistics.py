"""
Statistical calculation functions for patient pathway analysis.

This module contains functions for calculating:
- Drug frequency counts and averages
- Cost aggregations (total, per patient, per annum)
- Treatment duration calculations
- Dosing interval calculations

These functions are extracted from the analysis pipeline to enable:
- Independent testing
- Reuse across different analysis contexts
- Clearer separation of concerns
"""

from itertools import groupby
from typing import Optional

import numpy as np
import pandas as pd


def count_consecutive_values(values: list) -> list[int]:
    """
    Count consecutive occurrences of each value in a sorted list.

    Used to count how many times each drug was administered.

    Args:
        values: List of values (typically drug names)

    Returns:
        List of counts for each unique value in sorted order

    Example:
        >>> count_consecutive_values(['A', 'A', 'B', 'A'])
        [3, 1]  # 'A' appears 3 times, 'B' appears 1 time (sorted)
    """
    return [len(list(group)) for key, group in groupby(sorted(values))]


def calculate_drug_costs(drug_counts: list[int], prices: list[float]) -> list[float]:
    """
    Calculate total cost for each drug based on counts and prices.

    Splits the price list based on drug administration counts and sums
    each drug's portion.

    Args:
        drug_counts: List of administration counts per drug (from count_consecutive_values)
        prices: List of individual administration prices (Price Actual values)

    Returns:
        List of total costs per drug

    Example:
        >>> calculate_drug_costs([3, 2], [100, 100, 100, 200, 200])
        [300.0, 400.0]  # Drug 1: 3x$100 = $300, Drug 2: 2x$200 = $400
    """
    sum_list = []
    cumulative = 0
    for count in drug_counts:
        drug_cost = sum(prices[cumulative:cumulative + count])
        sum_list.append(float(drug_cost))
        cumulative += count
    return sum_list


def calculate_dosing_frequency(
    freq: int,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> float:
    """
    Calculate average dosing interval in days.

    Computes the average number of days between administrations.

    Args:
        freq: Number of administrations
        start_date: First administration date
        end_date: Last administration date

    Returns:
        Average days between administrations, or 0 if only one dose

    Example:
        >>> start = pd.Timestamp('2024-01-01')
        >>> end = pd.Timestamp('2024-01-22')
        >>> calculate_dosing_frequency(4, start, end)
        7.0  # 21 days / (4-1) = 7 days between doses
    """
    if freq <= 1:
        return 0.0

    duration_days = (end_date - start_date) / np.timedelta64(1, "D")
    if duration_days <= 0:
        return 0.0

    return duration_days / (freq - 1)


def calculate_drug_frequency_row(row: pd.Series) -> list[float]:
    """
    Calculate average dosing frequency for each drug in a patient's treatment.

    Used with DataFrame.apply() on rows containing drug_*, freq_*, start_date_*, end_date_* columns.

    Args:
        row: Series with drug names, frequencies, start dates, and end dates

    Returns:
        List of average dosing intervals (days) for each drug
    """
    drug_count = row.index.str.contains("drug_").sum()
    frequencies = []

    for d in range(drug_count):
        freq_col = f"freq_{d}"
        start_col = f"start_date_{d}"
        end_col = f"end_date_{d}"

        freq = row.get(freq_col, 0)
        if freq is None or pd.isna(freq):
            freq = 0
        else:
            freq = int(freq)

        if freq > 1:
            start_date = row.get(start_col)
            end_date = row.get(end_col)

            if pd.notna(start_date) and pd.notna(end_date):
                interval = calculate_dosing_frequency(freq, start_date, end_date)
            else:
                interval = 0.0
        else:
            interval = 0.0

        frequencies.append(interval)

    return frequencies


def calculate_cost_per_patient_per_annum(
    total_cost: float,
    days_treated: Optional[pd.Timedelta],
) -> Optional[float]:
    """
    Calculate annualized cost per patient.

    Normalizes costs to a per-year basis to enable comparison across
    patients with different treatment durations.

    Args:
        total_cost: Total cost for the patient (can be Decimal or float)
        days_treated: Treatment duration as timedelta

    Returns:
        Annualized cost, or None if days_treated is 0 or None

    Example:
        >>> calculate_cost_per_patient_per_annum(5000, pd.Timedelta(days=182.5))
        10000.0  # Half year treatment, so annual cost is 2x
    """
    if days_treated is None or pd.isna(days_treated):
        return None

    days = days_treated / np.timedelta64(1, "D") if hasattr(days_treated, '__truediv__') else float(days_treated)

    if days <= 0:
        return None

    # Convert total_cost to float to handle Decimal from Snowflake
    return float(total_cost) / (days / 365)


def calculate_treatment_duration(
    first_seen: pd.Timestamp,
    last_seen: pd.Timestamp,
) -> pd.Timedelta:
    """
    Calculate treatment duration from first to last seen dates.

    Args:
        first_seen: Date of first treatment
        last_seen: Date of last treatment

    Returns:
        Duration as timedelta
    """
    return last_seen - first_seen


def calculate_pathway_proportion(value: int, parent_value: int) -> float:
    """
    Calculate proportion of parent value for color scaling.

    Used to determine color intensity in the icicle chart based on
    what proportion of the parent category this pathway represents.

    Args:
        value: Patient count for this pathway
        parent_value: Total patient count for the parent category

    Returns:
        Proportion (0.0 to 1.0)
    """
    if parent_value <= 0:
        return 0.0
    return value / parent_value


def aggregate_patient_costs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate total cost per patient (UPID).

    Args:
        df: DataFrame with UPID and Price Actual columns

    Returns:
        DataFrame indexed by UPID with Total cost column
    """
    cost_df = df[["UPID", "Price Actual"]]
    total_costs = cost_df.groupby("UPID").sum()
    total_costs.rename(columns={"Price Actual": "Total cost"}, inplace=True)
    return total_costs


def aggregate_drug_frequencies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate drug administration frequency per patient.

    Groups by UPID and returns counts of each drug's administrations.

    Args:
        df: DataFrame with UPID and Drug Name columns

    Returns:
        DataFrame indexed by UPID with Drug Name as list of counts
    """
    return (
        df.groupby("UPID")
        .agg({"Drug Name": lambda x: count_consecutive_values(list(x))})
        .reset_index()
        .set_index("UPID")
    )


def calculate_average_spacing_for_pathway(
    upid_drugs_df: pd.DataFrame,
    pathway_value: str,
) -> list[float]:
    """
    Calculate average dosing spacing for a treatment pathway.

    Groups patients by pathway and calculates mean spacing for each drug position.

    Args:
        upid_drugs_df: DataFrame with patient pathway data and spacing columns
        pathway_value: Pathway identifier string

    Returns:
        List of average spacing values (days) for each drug in pathway
    """
    spacing_cols = [col for col in upid_drugs_df.columns if col.startswith("spacing_")]

    pathway_data = upid_drugs_df[upid_drugs_df["value"] == pathway_value]

    if len(pathway_data) == 0:
        return []

    averages = pathway_data[spacing_cols].mean()
    return [round(v, 0) if pd.notna(v) else 0.0 for v in averages.tolist()]


def format_treatment_statistics(
    drug_names: list[str],
    average_administered: list[float],
    average_spacing: list[float],
    average_cost: list[float],
) -> str:
    """
    Format drug treatment statistics into a readable string for chart display.

    Creates an HTML-formatted string with drug name, average administrations,
    dosing interval, and total treatment length.

    Args:
        drug_names: List of drug names in treatment sequence
        average_administered: Average number of administrations per drug
        average_spacing: Average days between doses per drug
        average_cost: Average cost per drug

    Returns:
        HTML-formatted string for chart hover text
    """
    ret_string = ""

    for i, drug_name in enumerate(drug_names):
        admin_count = average_administered[i] if i < len(average_administered) else 0
        spacing_days = average_spacing[i] if i < len(average_spacing) else 0

        # Convert to weeks
        spacing_weeks = spacing_days / 7 if spacing_days > 0 else 0
        total_weeks = spacing_weeks * admin_count if admin_count > 0 else 0

        string = (
            f"<br><b>{drug_name}</b><br>On average given "
            f"{round(admin_count, 1)} times with a "
            f"{round(spacing_weeks, 1)} weekly interval ("
            f"{round(total_weeks, 0)} weeks total treatment length)"
        )
        ret_string += string

    return ret_string


def remove_nan_values(values: list) -> list:
    """
    Remove NaN string values from a list.

    Used to clean up aggregated statistics that may contain 'nan' strings.

    Args:
        values: List potentially containing 'nan' strings

    Returns:
        Filtered list without 'nan' strings
    """
    return [x for x in values if str(x).lower() != "nan"]
