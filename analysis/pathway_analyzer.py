"""
Patient pathway analysis pipeline.

This module contains functions extracted from the original generate_graph() function
to improve maintainability and testability. The functions follow this pipeline:

1. prepare_data() - Apply filters, create composite keys, load reference data
2. calculate_statistics() - Calculate patient costs, drug frequencies, treatment durations
3. build_hierarchy() - Build the Trust → Directory → Drug → Pathway hierarchy
4. prepare_chart_data() - Finalize data for Plotly icicle chart

The generate_icicle_chart() function orchestrates the full pipeline.
"""

from typing import Optional

import numpy as np
import pandas as pd

from core import PathConfig, default_paths
from core.logging_config import get_logger
from analysis.statistics import (
    count_consecutive_values,
    calculate_drug_costs,
    calculate_dosing_frequency,
    calculate_cost_per_patient_per_annum,
    remove_nan_values,
)

logger = get_logger(__name__)


def prepare_data(
    df: pd.DataFrame,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    paths: Optional[PathConfig] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Prepare data for analysis by applying filters and loading reference data.

    Args:
        df: DataFrame with processed patient intervention data
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        paths: PathConfig for file paths (uses default if None)

    Returns:
        Tuple of (filtered_df, org_codes_df, directory_df) or (None, None, None) if no data
    """
    if paths is None:
        paths = default_paths

    df["UPIDTreatment"] = df["UPID"] + df["Drug Name"]

    org_codes = pd.read_csv(paths.org_codes_csv, index_col=1)
    df["Provider Code"] = df["Provider Code"].map(org_codes["Name"])

    df = df[
        (df["Provider Code"].isin(trust_filter))
        & (df["Drug Name"].isin(drug_filter))
        & (df["Directory"].isin(directory_filter))
    ]

    if len(df) == 0:
        logger.warning("No data found for selected filters.")
        return None, None, None

    directory_df = df[["UPID", "Directory"]].drop_duplicates("UPID").set_index("UPID")

    logger.info("Filtering unrelated interventions")
    return df, org_codes, directory_df


def _count_list_values(x):
    """Count consecutive occurrences of each value in a sorted list."""
    return count_consecutive_values(x)


def _sum_list_values(x):
    """Calculate sum of price_actual for each drug's portion of the list."""
    return calculate_drug_costs(x["Drug Name"], x["Price Actual"])


def _start_date_drug(start_dates_df: pd.DataFrame, x: pd.Series) -> list:
    """Get start dates for each drug in a patient's treatment."""
    drug_count = x.notnull().sum()
    date_string = []
    for d in range(drug_count):
        UPID_date_var = str(x.name) + str(x[d])
        date = start_dates_df.loc[UPID_date_var, "Intervention Date"]
        date_string.append(date)
    return date_string


def _end_date_drug(end_dates_df: pd.DataFrame, x: pd.Series) -> list:
    """Get end dates for each drug in a patient's treatment."""
    drug_count = x.notnull().sum()
    date_string = []
    for d in range(drug_count - 1):
        UPID_date_var = str(x.name) + str(x[d])
        date = end_dates_df.loc[UPID_date_var, "Intervention Date"]
        date_string.append(date)
    return date_string


def _drug_frequency_average(x: pd.Series) -> list[float]:
    """Calculate average dosing frequency for each drug."""
    drug_count = x.index.str.contains("drug_").sum()
    freq = []
    for d in range(drug_count):
        freq_val = x.get(f"freq_{d}", 0)
        if pd.isna(freq_val):
            freq_val = 0
        else:
            freq_val = int(freq_val)

        if freq_val > 1:
            start_date = x.get(f"start_date_{d}")
            end_date = x.get(f"end_date_{d}")
            if pd.notna(start_date) and pd.notna(end_date):
                freq_calc = calculate_dosing_frequency(freq_val, start_date, end_date)
            else:
                freq_calc = 0.0
        else:
            freq_calc = 0.0
        freq.append(freq_calc)
    return freq


def _drop_duplicate_treatments(df: pd.DataFrame, ascending: bool) -> pd.DataFrame:
    """Drop duplicate treatments keeping first/last based on date sort order."""
    df_sorted = df.sort_values(by=["Intervention Date"], ascending=ascending)
    df_treatment_steps = df_sorted.drop_duplicates(subset="UPIDTreatment", keep="first")
    if not ascending:
        df_treatment_steps = df_treatment_steps.sort_values(by=["Intervention Date"], ascending=True)
    return df_treatment_steps


def calculate_statistics(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    last_seen_date: str,
    title: str,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Calculate patient statistics: costs, drug frequencies, treatment durations.

    Args:
        df: Filtered DataFrame from prepare_data()
        start_date: Start date for patient initiation filter
        end_date: End date for patient initiation filter
        last_seen_date: Filter for patients last seen after this date
        title: Chart title (auto-generated if empty)

    Returns:
        Tuple of (patient_info_df, date_df, final_title) or (None, None, "") if no valid data
    """
    cost_df = df[["UPID", "Price Actual"]]
    total_costs = pd.DataFrame(cost_df.groupby("UPID").sum())
    total_costs.rename(columns={"Price Actual": "Total cost"}, inplace=True)

    df_end_dates = _drop_duplicate_treatments(df, False)
    df1_unique = _drop_duplicate_treatments(df, True)
    logger.info("Identifying unique patients and interventions used")

    df_drug_freq = (
        df.groupby("UPID")
        .agg({"Drug Name": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_drug_cost = (
        df.groupby("UPID")
        .agg({"Price Actual": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_drug_freq["Price Actual"] = df_drug_freq.index.map(df_drug_cost["Price Actual"])
    df_drug_freq["Drug Name"] = df_drug_freq["Drug Name"].apply(_count_list_values)
    df_drug_freq["Drug cost total"] = df_drug_freq.apply(lambda x: _sum_list_values(x), axis=1)

    df_drugs = (
        df1_unique.groupby("UPID")
        .agg({"Drug Name": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_dates = (
        df1_unique.groupby("UPID")
        .agg({"Intervention Date": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_end_dates_grouped = (
        df_end_dates.groupby("UPID")
        .agg({"Intervention Date": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )

    logger.info(
        "Calculating each unique patient's intervention average frequency, cost and duration of each intervention"
    )

    df_dates_unwrapped = pd.DataFrame(
        df_dates["Intervention Date"].values.tolist(), index=df_dates.index
    ).add_prefix("date_")
    df_end_dates_unwrapped = pd.DataFrame(
        df_end_dates_grouped["Intervention Date"].values.tolist(),
        index=df_end_dates_grouped.index,
    ).add_prefix("date_end_")
    df_drugs_unwrapped = pd.DataFrame(
        df_drugs["Drug Name"].values.tolist(), index=df_drugs.index
    ).add_prefix("drug_")

    df_freq_unwrapped = pd.DataFrame(
        df_drug_freq["Drug Name"].values.tolist(), index=df_drug_freq.index
    ).add_prefix("freq_")

    start_dates = (
        df[["UPIDTreatment", "Intervention Date"]]
        .sort_values(by=["Intervention Date"], ascending=True)
        .drop_duplicates(subset="UPIDTreatment")
        .set_index("UPIDTreatment")
    )
    end_dates = (
        df[["UPIDTreatment", "Intervention Date"]]
        .sort_values(by=["Intervention Date"], ascending=False)
        .drop_duplicates(subset="UPIDTreatment")
        .set_index("UPIDTreatment")
    )

    df_drugs_unwrapped["start_dates"] = df_drugs_unwrapped.apply(
        lambda x: _start_date_drug(start_dates, x), axis=1
    )
    df_start_dates_unwrapped = pd.DataFrame(
        df_drugs_unwrapped["start_dates"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("start_date_")
    df_drugs_unwrapped.drop(["start_dates"], inplace=True, axis=1)

    df_drugs_unwrapped["end_dates"] = df_drugs_unwrapped.apply(
        lambda x: _start_date_drug(end_dates, x), axis=1
    )
    df_end_dates_unwrapped_2 = pd.DataFrame(
        df_drugs_unwrapped["end_dates"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("end_date_")
    df_drugs_unwrapped.drop(["end_dates"], inplace=True, axis=1)

    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_start_dates_unwrapped, left_index=True, right_index=True
    )
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_end_dates_unwrapped_2, left_index=True, right_index=True
    )

    df_freq_for_merge = pd.DataFrame(
        df_drug_freq["Drug Name"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("freq_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_freq_for_merge, left_index=True, right_index=True
    )
    df_drugs_unwrapped["frequency"] = df_drugs_unwrapped.apply(
        lambda x: _drug_frequency_average(x), axis=1
    )

    df_spacing_unwrapped = pd.DataFrame(
        df_drugs_unwrapped["frequency"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("spacing_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_spacing_unwrapped, left_index=True, right_index=True
    )

    df_cost_unwrapped = pd.DataFrame(
        df_drug_freq["Drug cost total"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("total_cost_drug_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_cost_unwrapped, left_index=True, right_index=True
    )
    df_drugs_unwrapped.drop(["frequency"], inplace=True, axis=1)

    df_drugs_unwrapped.insert(0, "First seen", df_dates_unwrapped.min(axis=1))
    df_drugs_unwrapped.insert(1, "Last seen", df_end_dates_unwrapped.max(axis=1))

    patient_info = df.drop_duplicates(subset="UPID", keep="first").set_index("UPID")
    patient_info = pd.merge(patient_info, df_drugs_unwrapped, left_index=True, right_index=True)
    patient_info = pd.merge(patient_info, df_freq_unwrapped, left_index=True, right_index=True)
    patient_info = pd.merge(patient_info, total_costs, left_index=True, right_index=True)

    patient_info = patient_info[
        (patient_info["First seen"] >= str(start_date))
        & (patient_info["First seen"] < str(end_date))
    ]

    if title == "":
        title = f"Patients initiated from {start_date} to {end_date}"

    patient_info = patient_info[patient_info["Last seen"] > str(last_seen_date)]

    patient_info["drug_0"] = patient_info["drug_0"].replace("N/A", np.nan)
    patient_info.dropna(subset=["drug_0"], inplace=True)

    if len(patient_info) == 0:
        logger.warning("No patients remaining after date filters.")
        return None, None, ""

    patient_info["Days treated"] = patient_info["Last seen"] - patient_info["First seen"]
    date_df = patient_info[["First seen", "Last seen", "Days treated"]]

    return patient_info, date_df, title


def _row_function(row: pd.Series) -> str:
    """Build composite parent-label-id string for hierarchy."""
    ids = ""
    parents = "N&WICS"
    count = row.count()
    for c in range(count):
        v = row[c]
        if type(v) != str:
            v = row[c + 1]
        if c == count - 1:
            ids = parents + " - " + v
            continue
        parents += " - " + v
    label = row[count - 1]
    value = parents + "," + label + "," + ids
    return value


def _remove_nan_string(y) -> list:
    """Remove 'nan' strings from list."""
    return remove_nan_values(y)


def _list_to_string(x: pd.Series) -> str:
    """Format drug statistics into readable string."""
    list_parts = x.ids.split(" - ")
    drug_list = list_parts[len(list_parts) - len(x.average_cost) :]
    ret_string = ""
    for y in range(len(x.average_cost)):
        if (
            (round(x.average_spacing[y], 0) > 1)
            and (round(x.average_administered[y], 0) > 2.5)
            and (int(x.value) > 0)
        ):
            string = (
                f"<br><b>{drug_list[y]}</b><br>On average given "
                f"{round(x.average_administered[y], 1)} times with a "
                f"{round(int(x.average_spacing[y]) / 7, 1)} weekly interval ("
                f"{round((int(x.average_spacing[y]) / 7) * round(x.average_administered[y], 1), 0)} weeks total treatment length)"
            )
        else:
            string = (
                f"<br><b>{drug_list[y]}</b><br>On average given "
                f"{round(x.average_administered[y], 1)} times with a "
                f"{round(int(x.average_spacing[y]) / 7, 1)} weekly interval ("
                f"{round((int(x.average_spacing[y]) / 7) * round(x.average_administered[y], 1), 0)} weeks total treatment length)"
            )
        ret_string += string
    return ret_string


def _min_max_treatment_dates(ice_df: pd.DataFrame, row: pd.Series) -> str:
    """Get min/max dates for a pathway."""
    ids = row["ids"]
    min_max = ice_df[ice_df["ids"].str.contains(ids, regex=False)]
    if len(min_max) == 0:
        return "N/A,N/A"

    # Handle NaT (Not a Time) values
    first_seen_min = min_max["First seen"].min()
    last_seen_max = min_max["Last seen"].max()

    if pd.isna(first_seen_min):
        min_date = "N/A"
    else:
        min_date = str(first_seen_min.strftime("%Y-%m-%d"))

    if pd.isna(last_seen_max):
        max_date = "N/A"
    else:
        max_date = str(last_seen_max.strftime("%Y-%m-%d"))

    return f"{min_date},{max_date}"


def _cost_pp_pa(x: pd.Series) -> str:
    """Calculate cost per patient per annum."""
    result = calculate_cost_per_patient_per_annum(x["costpp"], x["avg_days"])
    if result is not None:
        return str(round(result, 2))
    else:
        return "N/A"


def build_hierarchy(
    patient_info: pd.DataFrame,
    date_df: pd.DataFrame,
    df: pd.DataFrame,
    org_codes: pd.DataFrame,
    directory_df: pd.DataFrame,
    total_costs: pd.DataFrame,
    df_drugs_unwrapped: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the hierarchical structure for the icicle chart.

    Args:
        patient_info: DataFrame with calculated patient statistics
        date_df: DataFrame with first/last seen dates
        df: Original filtered DataFrame
        org_codes: Organization codes lookup
        directory_df: Directory assignments by UPID
        total_costs: Total costs by UPID
        df_drugs_unwrapped: Drug data with dates and frequencies unwrapped

    Returns:
        DataFrame with parents, ids, labels, value, colour for icicle chart
    """
    number_of_drugs = np.count_nonzero(patient_info.columns.str.startswith("drug_"))
    final_drug_index = patient_info.columns.to_list().index("drug_" + str(number_of_drugs - 1))

    upid_drugs_df = patient_info.iloc[
        :, (final_drug_index - number_of_drugs + 1) : final_drug_index + 1
    ]
    upid_drugs_df = upid_drugs_df.copy()

    upid_drugs_df.insert(0, "Trust", upid_drugs_df.index.str[:3])
    upid_drugs_df.insert(1, "Directory", upid_drugs_df.index)

    upid_drugs_df["Trust"] = upid_drugs_df["Trust"].map(org_codes["Name"])
    upid_drugs_df["Directory"] = upid_drugs_df["Directory"].map(directory_df["Directory"])

    upid_drugs_df["value"] = upid_drugs_df.apply(lambda x: _row_function(x), axis=1)
    upid_drugs_df = pd.merge(upid_drugs_df, date_df, left_index=True, right_index=True)

    upid_drugs_df["ids"] = upid_drugs_df["value"].str.split(",").str[2]

    avg_treatment_dfs = pd.DataFrame(
        upid_drugs_df.groupby("ids", as_index=False)["Days treated"].mean()
    ).set_index("ids")
    value_dfs = pd.DataFrame(
        upid_drugs_df.groupby("value", as_index=False).size()
    ).reset_index()
    first_seen_treatment_dfs = pd.DataFrame(
        upid_drugs_df.groupby("ids", as_index=False)["First seen"].min()
    ).set_index("ids")
    last_seen_treatment_dfs = pd.DataFrame(
        upid_drugs_df.groupby("ids", as_index=False)["Last seen"].max()
    ).set_index("ids")

    upid_drugs_df["Cost"] = upid_drugs_df.index.map(total_costs["Total cost"])
    cost_dfs = pd.DataFrame(
        upid_drugs_df.groupby("value", as_index=False)["Cost"].sum()
    ).set_index("value", drop=True)

    upid_drugs_df = pd.merge(upid_drugs_df, df_drugs_unwrapped, left_index=True, right_index=True)

    spacing_average = pd.DataFrame(
        upid_drugs_df.groupby("value", as_index=False)[
            [col for col in upid_drugs_df.columns if "spacing_" in col]
        ].mean()
    ).set_index("value", drop=True)
    spacing_average = spacing_average.round()
    spacing_average["combined"] = spacing_average.values.tolist()
    spacing_average["ids"] = spacing_average.index
    spacing_average["ids"] = spacing_average["ids"].str.split(",").str[2]
    spacing_average.set_index("ids", inplace=True)

    cost_average = pd.DataFrame(
        upid_drugs_df.groupby("value", as_index=False)[
            [col for col in upid_drugs_df.columns if "total_cost_drug_" in col]
        ].mean()
    ).set_index("value", drop=True)
    cost_average = cost_average.round(2)
    cost_average["combined"] = cost_average.values.tolist()
    cost_average["ids"] = cost_average.index
    cost_average["ids"] = cost_average["ids"].str.split(",").str[2]
    cost_average.set_index("ids", inplace=True)

    freq_average = pd.DataFrame(
        upid_drugs_df.groupby("ids", as_index=False)[
            [col for col in upid_drugs_df.columns if "freq_" in col]
        ].mean()
    ).set_index("ids", drop=True)
    freq_average["combined"] = freq_average.values.tolist()

    num = cost_dfs._get_numeric_data()
    num[num < 0] = 0

    value_dfs["Cost"] = value_dfs["value"].map(cost_dfs["Cost"])

    ice_df = pd.DataFrame()
    ice_df[["parents", "labels", "ids"]] = value_dfs["value"].str.split(",", expand=True)

    ice_df["average_administered"] = ice_df["ids"].map(freq_average["combined"])
    ice_df["cost"] = value_dfs["Cost"]
    ice_df["value"] = value_dfs["size"]

    ice_df["average_cost"] = ice_df["ids"].map(cost_average["combined"])
    ice_df["average_cost"] = ice_df["average_cost"].apply(_remove_nan_string)

    ice_df["average_spacing"] = ice_df["ids"].map(spacing_average["combined"])
    ice_df["average_spacing"] = ice_df["average_spacing"].apply(_remove_nan_string)
    ice_df["average_spacing"] = ice_df.apply(lambda x: _list_to_string(x), axis=1)
    ice_df["average_spacing"] = ice_df["average_spacing"].str.replace("nan", "N/A")

    logger.info("Building graph dataframe structure.")

    new_row = pd.DataFrame(
        {"parents": "", "ids": "N&WICS", "labels": "N&WICS", "value": 0, "cost": 0}, index=[0]
    )
    ice_df = pd.concat(objs=[ice_df, new_row], ignore_index=True, axis=0)

    l_df = pd.DataFrame()
    ice_df2 = pd.DataFrame()
    l3 = [x for x in ice_df.parents.unique() if x not in ice_df.ids]
    while len(l3) > 1:
        for l in l3:
            z = l.rfind("-")
            if z > 0:
                l_dict = {
                    "parents": l[: z - 1],
                    "ids": l,
                    "value": 0,
                    "labels": l[z + 2 :],
                    "cost": 0,
                }
                l_df = pd.concat([l_df, pd.DataFrame(l_dict, index=[0])], ignore_index=True)
        ice_df2 = pd.concat([ice_df, l_df], ignore_index=True)
        l3 = [x for x in ice_df2.parents.unique() if x not in ice_df2.ids.unique()]
    if len(ice_df2) > 0:
        ice_df = ice_df2.drop_duplicates("ids")

    ice_df["level"] = ice_df["ids"].str.count("-")
    ice_df = ice_df[~ice_df["labels"].isin(["COST", "CHARGE", "N/A"])]
    ice_df.sort_values(by=["level"], ascending=False, inplace=True, ignore_index=True)

    for index, row in ice_df.iterrows():
        lookup_index = ice_df.index[ice_df["ids"] == row["parents"]]
        ice_df.loc[lookup_index, "value"] = (
            ice_df.loc[lookup_index, "value"] + ice_df.loc[index, "value"]
        )
        ice_df.loc[lookup_index, "cost"] = (
            ice_df.loc[lookup_index, "cost"] + ice_df.loc[index, "cost"]
        )

    colour_df = pd.DataFrame(ice_df.groupby(["parents"])["value"].sum())
    ice_df["colour"] = ice_df["parents"].map(colour_df["value"])
    ice_df["colour"] = ice_df["value"] / ice_df["colour"]

    ice_df["costpp"] = ice_df["cost"] / ice_df["value"]
    ice_df["avg_days"] = ice_df["ids"].map(avg_treatment_dfs["Days treated"])
    ice_df["First seen"] = ice_df["ids"].map(first_seen_treatment_dfs["First seen"])
    ice_df["Last seen"] = ice_df["ids"].map(last_seen_treatment_dfs["Last seen"])

    ice_df["dates"] = ice_df.apply(lambda x: _min_max_treatment_dates(ice_df, x), axis=1)
    ice_df[["First seen (Parent)", "Last seen (Parent)"]] = ice_df["dates"].str.split(
        ",", expand=True
    )

    ice_df["First seen"] = pd.to_datetime(ice_df["First seen"])
    ice_df["Last seen"] = pd.to_datetime(ice_df["Last seen"])
    ice_df["cost_pp_pa"] = ice_df.apply(lambda x: _cost_pp_pa(x), axis=1)

    return ice_df


def prepare_chart_data(
    ice_df: pd.DataFrame,
    minimum_num_patients: int,
) -> pd.DataFrame:
    """
    Prepare final chart data by applying patient threshold filter.

    Args:
        ice_df: DataFrame from build_hierarchy()
        minimum_num_patients: Minimum number of patients to include a pathway

    Returns:
        Filtered DataFrame ready for chart generation
    """
    ice_df = ice_df[ice_df["value"] >= minimum_num_patients]
    logger.info("Generating graph.")
    return ice_df


def generate_icicle_chart(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    last_seen_date: str,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    minimum_num_patients: int,
    title: str = "",
    paths: Optional[PathConfig] = None,
) -> tuple[pd.DataFrame, str]:
    """
    Generate icicle chart data using the refactored pipeline.

    This is the main entry point that orchestrates the full analysis pipeline.

    Args:
        df: DataFrame with processed patient intervention data
        start_date: Start date for patient initiation filter
        end_date: End date for patient initiation filter
        last_seen_date: Filter for patients last seen after this date
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        minimum_num_patients: Minimum number of patients to include a pathway
        title: Chart title (auto-generated if empty)
        paths: PathConfig for file paths (uses default if None)

    Returns:
        Tuple of (ice_df for chart, final_title) or (None, "") if no data
    """
    if paths is None:
        paths = default_paths

    result = prepare_data(df, trust_filter, drug_filter, directory_filter, paths)
    if result[0] is None:
        return None, ""
    filtered_df, org_codes, directory_df = result

    cost_df = filtered_df[["UPID", "Price Actual"]]
    total_costs = pd.DataFrame(cost_df.groupby("UPID").sum())
    total_costs.rename(columns={"Price Actual": "Total cost"}, inplace=True)

    result = calculate_statistics(filtered_df, start_date, end_date, last_seen_date, title)
    if result[0] is None:
        return None, ""
    patient_info, date_df, final_title = result

    df_drug_freq = (
        filtered_df.groupby("UPID")
        .agg({"Drug Name": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_drug_cost = (
        filtered_df.groupby("UPID")
        .agg({"Price Actual": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_drug_freq["Price Actual"] = df_drug_freq.index.map(df_drug_cost["Price Actual"])
    df_drug_freq["Drug Name"] = df_drug_freq["Drug Name"].apply(_count_list_values)
    df_drug_freq["Drug cost total"] = df_drug_freq.apply(lambda x: _sum_list_values(x), axis=1)

    df1_unique = _drop_duplicate_treatments(filtered_df, True)
    df_drugs = (
        df1_unique.groupby("UPID")
        .agg({"Drug Name": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_dates = (
        df1_unique.groupby("UPID")
        .agg({"Intervention Date": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )

    df_dates_unwrapped = pd.DataFrame(
        df_dates["Intervention Date"].values.tolist(), index=df_dates.index
    ).add_prefix("date_")
    df_drugs_unwrapped = pd.DataFrame(
        df_drugs["Drug Name"].values.tolist(), index=df_drugs.index
    ).add_prefix("drug_")

    start_dates = (
        filtered_df[["UPIDTreatment", "Intervention Date"]]
        .sort_values(by=["Intervention Date"], ascending=True)
        .drop_duplicates(subset="UPIDTreatment")
        .set_index("UPIDTreatment")
    )
    end_dates = (
        filtered_df[["UPIDTreatment", "Intervention Date"]]
        .sort_values(by=["Intervention Date"], ascending=False)
        .drop_duplicates(subset="UPIDTreatment")
        .set_index("UPIDTreatment")
    )

    df_drugs_unwrapped["start_dates"] = df_drugs_unwrapped.apply(
        lambda x: _start_date_drug(start_dates, x), axis=1
    )
    df_start_dates_unwrapped = pd.DataFrame(
        df_drugs_unwrapped["start_dates"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("start_date_")
    df_drugs_unwrapped.drop(["start_dates"], inplace=True, axis=1)

    df_drugs_unwrapped["end_dates"] = df_drugs_unwrapped.apply(
        lambda x: _start_date_drug(end_dates, x), axis=1
    )
    df_end_dates_unwrapped_2 = pd.DataFrame(
        df_drugs_unwrapped["end_dates"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("end_date_")
    df_drugs_unwrapped.drop(["end_dates"], inplace=True, axis=1)

    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_start_dates_unwrapped, left_index=True, right_index=True
    )
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_end_dates_unwrapped_2, left_index=True, right_index=True
    )

    df_freq_for_merge = pd.DataFrame(
        df_drug_freq["Drug Name"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("freq_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_freq_for_merge, left_index=True, right_index=True
    )
    df_drugs_unwrapped["frequency"] = df_drugs_unwrapped.apply(
        lambda x: _drug_frequency_average(x), axis=1
    )

    df_spacing_unwrapped = pd.DataFrame(
        df_drugs_unwrapped["frequency"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("spacing_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_spacing_unwrapped, left_index=True, right_index=True
    )

    df_cost_unwrapped = pd.DataFrame(
        df_drug_freq["Drug cost total"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("total_cost_drug_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_cost_unwrapped, left_index=True, right_index=True
    )
    df_drugs_unwrapped.drop(["frequency"], inplace=True, axis=1)

    ice_df = build_hierarchy(
        patient_info,
        date_df,
        filtered_df,
        org_codes,
        directory_df,
        total_costs,
        df_drugs_unwrapped,
    )

    ice_df = prepare_chart_data(ice_df, minimum_num_patients)

    return ice_df, final_title


def generate_icicle_chart_indication(
    df: pd.DataFrame,
    indication_df: pd.DataFrame,
    start_date: str,
    end_date: str,
    last_seen_date: str,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    minimum_num_patients: int,
    title: str = "",
    paths: Optional[PathConfig] = None,
) -> tuple[pd.DataFrame, str]:
    """
    Generate icicle chart data with indication-based grouping.

    This is a variant of generate_icicle_chart() that groups by Search_Term
    (from GP diagnosis match) instead of Directory. For patients without
    a GP diagnosis match, the fallback directorate is used with a "(no GP dx)"
    suffix to distinguish them.

    Hierarchy: Trust → Indication_Group → Drug → Pathway

    Args:
        df: DataFrame with processed patient intervention data
        indication_df: DataFrame mapping UPID → Indication_Group
                      Must have 'UPID' as index and 'Indication_Group' column
                      Values are either Search_Term or "Directory (no GP dx)"
        start_date: Start date for patient initiation filter
        end_date: End date for patient initiation filter
        last_seen_date: Filter for patients last seen after this date
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        minimum_num_patients: Minimum number of patients to include a pathway
        title: Chart title (auto-generated if empty)
        paths: PathConfig for file paths (uses default if None)

    Returns:
        Tuple of (ice_df for chart, final_title) or (None, "") if no data
    """
    if paths is None:
        paths = default_paths

    # Prepare data - use standard prepare_data function
    result = prepare_data(df, trust_filter, drug_filter, directory_filter, paths)
    if result[0] is None:
        return None, ""
    filtered_df, org_codes, directory_df = result

    # For indication charts, we replace directory_df with indication_df
    # First, ensure indication_df has the correct format (UPID as index)
    if indication_df is not None and not indication_df.empty:
        if 'UPID' in indication_df.columns:
            indication_df = indication_df.set_index('UPID')
        # Rename column for compatibility with build_hierarchy()
        if 'Indication_Group' in indication_df.columns:
            indication_df = indication_df.rename(columns={'Indication_Group': 'Directory'})
        elif 'indication_group' in indication_df.columns:
            indication_df = indication_df.rename(columns={'indication_group': 'Directory'})
    else:
        # Fall back to directory if no indication data provided
        logger.warning("No indication data provided, falling back to directory grouping")
        indication_df = directory_df

    cost_df = filtered_df[["UPID", "Price Actual"]]
    total_costs = pd.DataFrame(cost_df.groupby("UPID").sum())
    total_costs.rename(columns={"Price Actual": "Total cost"}, inplace=True)

    result = calculate_statistics(filtered_df, start_date, end_date, last_seen_date, title)
    if result[0] is None:
        return None, ""
    patient_info, date_df, final_title = result

    df_drug_freq = (
        filtered_df.groupby("UPID")
        .agg({"Drug Name": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_drug_cost = (
        filtered_df.groupby("UPID")
        .agg({"Price Actual": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_drug_freq["Price Actual"] = df_drug_freq.index.map(df_drug_cost["Price Actual"])
    df_drug_freq["Drug Name"] = df_drug_freq["Drug Name"].apply(_count_list_values)
    df_drug_freq["Drug cost total"] = df_drug_freq.apply(lambda x: _sum_list_values(x), axis=1)

    df1_unique = _drop_duplicate_treatments(filtered_df, True)
    df_drugs = (
        df1_unique.groupby("UPID")
        .agg({"Drug Name": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )
    df_dates = (
        df1_unique.groupby("UPID")
        .agg({"Intervention Date": lambda x: list(x)})
        .reset_index()
        .set_index("UPID")
    )

    df_dates_unwrapped = pd.DataFrame(
        df_dates["Intervention Date"].values.tolist(), index=df_dates.index
    ).add_prefix("date_")
    df_drugs_unwrapped = pd.DataFrame(
        df_drugs["Drug Name"].values.tolist(), index=df_drugs.index
    ).add_prefix("drug_")

    start_dates = (
        filtered_df[["UPIDTreatment", "Intervention Date"]]
        .sort_values(by=["Intervention Date"], ascending=True)
        .drop_duplicates(subset="UPIDTreatment")
        .set_index("UPIDTreatment")
    )
    end_dates = (
        filtered_df[["UPIDTreatment", "Intervention Date"]]
        .sort_values(by=["Intervention Date"], ascending=False)
        .drop_duplicates(subset="UPIDTreatment")
        .set_index("UPIDTreatment")
    )

    df_drugs_unwrapped["start_dates"] = df_drugs_unwrapped.apply(
        lambda x: _start_date_drug(start_dates, x), axis=1
    )
    df_start_dates_unwrapped = pd.DataFrame(
        df_drugs_unwrapped["start_dates"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("start_date_")
    df_drugs_unwrapped.drop(["start_dates"], inplace=True, axis=1)

    df_drugs_unwrapped["end_dates"] = df_drugs_unwrapped.apply(
        lambda x: _start_date_drug(end_dates, x), axis=1
    )
    df_end_dates_unwrapped_2 = pd.DataFrame(
        df_drugs_unwrapped["end_dates"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("end_date_")
    df_drugs_unwrapped.drop(["end_dates"], inplace=True, axis=1)

    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_start_dates_unwrapped, left_index=True, right_index=True
    )
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_end_dates_unwrapped_2, left_index=True, right_index=True
    )

    df_freq_for_merge = pd.DataFrame(
        df_drug_freq["Drug Name"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("freq_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_freq_for_merge, left_index=True, right_index=True
    )
    df_drugs_unwrapped["frequency"] = df_drugs_unwrapped.apply(
        lambda x: _drug_frequency_average(x), axis=1
    )

    df_spacing_unwrapped = pd.DataFrame(
        df_drugs_unwrapped["frequency"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("spacing_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_spacing_unwrapped, left_index=True, right_index=True
    )

    df_cost_unwrapped = pd.DataFrame(
        df_drug_freq["Drug cost total"].values.tolist(), index=df_drugs_unwrapped.index
    ).add_prefix("total_cost_drug_")
    df_drugs_unwrapped = pd.merge(
        df_drugs_unwrapped, df_cost_unwrapped, left_index=True, right_index=True
    )
    df_drugs_unwrapped.drop(["frequency"], inplace=True, axis=1)

    # Build hierarchy with indication_df instead of directory_df
    ice_df = build_hierarchy(
        patient_info,
        date_df,
        filtered_df,
        org_codes,
        indication_df,  # Use indication mapping instead of directory
        total_costs,
        df_drugs_unwrapped,
    )

    ice_df = prepare_chart_data(ice_df, minimum_num_patients)

    return ice_df, final_title
