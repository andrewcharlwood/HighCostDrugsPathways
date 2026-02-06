import webbrowser
from itertools import groupby
import os
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core import AnalysisFilters, PathConfig, default_paths
from core.logging_config import get_logger
from tools import data

# Import refactored analysis functions
from analysis.pathway_analyzer import (
    generate_icicle_chart as _generate_icicle_chart,
    prepare_data as _prepare_data,
    calculate_statistics as _calculate_statistics,
    build_hierarchy as _build_hierarchy,
    prepare_chart_data as _prepare_chart_data,
)

# Import visualization functions
from visualization.plotly_generator import (
    create_icicle_figure as _create_icicle_figure,
    save_figure_html as _save_figure_html,
    figure_legacy as _figure_legacy,
)

logger = get_logger(__name__)

pd.options.mode.chained_assignment = None  # default='warn'
def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

def main(dir, paths: Optional[PathConfig] = None):
    """
    Load and process patient intervention data from a file.

    Uses the FileDataLoader abstraction to handle CSV/Parquet file loading
    with all necessary transformations (patient_id, drug_names, department_identification).

    Args:
        dir: Path to CSV or Parquet file
        paths: PathConfig for reference data locations (uses default_paths if None)

    Returns:
        DataFrame with processed patient intervention data
    """
    from data_processing.loader import FileDataLoader

    if paths is None:
        paths = default_paths

    loader = FileDataLoader(file_path=dir, paths=paths)
    result = loader.load()

    logger.info("Initial data processing complete.")
    return result.df


def drop_duplicate_treatments(df, ascending):
    df.sort_values(by=['Intervention Date'], ascending=ascending, inplace=True)
    df_treatment_steps = df.drop_duplicates(subset="UPIDTreatment", keep="first")
    if not ascending:
        df_treatment_steps.sort_values(by=['Intervention Date'], ascending=True, inplace=True)
    return df_treatment_steps


def row_function(row):
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


def count_list_values(x):
    return [len(list(group)) for key, group in groupby(sorted(x))]


def sum_list_values(x):
    sum_list = []
    for count in range(len(x["Drug Name"])):
        if count == 0:
            sum_list.append(sum(x["Price Actual"][ : x["Drug Name"][count]]))
        else:
            sum_list.append(sum(x["Price Actual"][x["Drug Name"][count-1] : (x["Drug Name"][count-1] + x["Drug Name"][count])]))
    return sum_list


def remove_nan_string(y):
    return [x for x in y if str(x) != 'nan']


def min_max_treatment_dates(ice_df, row):
    ids = row[2]
    min_max = ice_df[ice_df["ids"].str.contains(ids)]
    min_date = str(min_max["First seen"].min().strftime('%Y-%m-%d'))
    max_date = str(min_max["Last seen"].max().strftime('%Y-%m-%d'))
    return min_date + ',' + max_date


def start_date_drug(df, x):
    drug_count = x.notnull().sum()
    date_string = []
    for d in range(drug_count):
        UPID_date_var = str(x.name) + str(x[d])
        date = df.loc[UPID_date_var, "Intervention Date"]
        date_string.append(date)
    return date_string


def end_date_drug(df, x):
    drug_count = x.notnull().sum()
    date_string = []
    # Need to -1 from drug count as start date gets counted from notnull above
    for d in range(drug_count - 1):
        UPID_date_var = str(x.name) + str(x[d])
        date = df.loc[UPID_date_var, "Intervention Date"]
        date_string.append(date)
    return date_string


def list_to_string(x):
    list = x.ids.split(' - ')
    drug_list = list[len(list) - len(x.average_cost):]
    ret_string = ""
    for y in range(len(x.average_cost)):
        if (round(x.average_spacing[y], 0) > 1) and (round(x.average_administered[y], 0) > 2.5) and (int(x.value) > 0):
            string = "<br><b>" + str(drug_list[y]) + "</b><br>On average given " + str(
                round(x.average_administered[y], 1)) + \
                     " times with a " + str(round(int(x.average_spacing[y]) / 7, 1)) + " weekly interval (" \
                     + str(round((int(x.average_spacing[y]) / 7) * round(x.average_administered[y], 1),
                                 0)) + " weeks total treatment length)" 
                     #"<br>Average annual cost per annum:" + \
                     #str(human_format(
                     #    (x.cost / x.value) / (((int(x.average_spacing[y]) / 7) * round(x.average_administered[y], 1))/ 52)))
        else:
            string = "<br><b>" + str(drug_list[y]) + "</b><br>On average given " + str(
                round(x.average_administered[y], 1)) + \
                     " times with a " + str(round(int(x.average_spacing[y]) / 7, 1)) + " weekly interval (" \
                     + str(round((int(x.average_spacing[y]) / 7) * round(x.average_administered[y], 1),
                                 0)) + " weeks total treatment length)" 
                     #"<br>Average annual cost per annum unavailable"

        ret_string += string

    return ret_string


def drug_frequency_average(x):
    drug_count = x.index.str.contains("drug_").sum()
    freq = []
    for d in range(drug_count):
        if x["freq_" + str(d)] > 1:
            duration = ((x["end_date_" + str(d)] - x["start_date_" + str(d)]) / np.timedelta64(1, 'D'))
            if duration > 0:
                freq_calc = duration / (x["freq_" + str(d)] - 1)
            else:
                freq_calc = 0
        else:
            freq_calc = 0
        freq.append(freq_calc)
    return freq


def cost_pp_pa(x):
    if x["avg_days"]/ np.timedelta64(1, 'D') > 0:
        return str(round(x["costpp"] / ((x["avg_days"] / np.timedelta64(1, 'D')) / 365), 2))
    else:
        return "N/A"


def generate_graph(
    df1,
    start_date=None,
    end_date=None,
    last_seen=None,
    save_dir=None,
    trustFilter=None,
    drugFilter=None,
    directorateFilter=None,
    title=None,
    minimum_num_patients=None,
    *,
    filters: Optional[AnalysisFilters] = None,
    paths: Optional[PathConfig] = None,
):
    """
    Generate patient pathway icicle chart.

    This function can be called in two ways:
    1. New style: Pass filters=AnalysisFilters(...) with all parameters encapsulated
    2. Legacy style: Pass individual parameters (start_date, end_date, etc.)

    If both are provided, the filters object takes precedence.

    Args:
        df1: DataFrame with processed patient data
        filters: AnalysisFilters object with all filter parameters (preferred)
        paths: PathConfig object for file paths (optional, uses default_paths if not provided)

        Legacy parameters (used if filters is None):
        start_date, end_date, last_seen, save_dir, trustFilter, drugFilter,
        directorateFilter, title, minimum_num_patients
    """
    # Use PathConfig for file paths
    if paths is None:
        paths = default_paths

    # Extract parameters from AnalysisFilters if provided
    if filters is not None:
        start_date = filters.start_date
        end_date = filters.end_date
        last_seen = filters.last_seen_date
        save_dir = filters.output_dir
        trustFilter = filters.trusts
        drugFilter = filters.drugs
        directorateFilter = filters.directories
        title = filters.custom_title
        minimum_num_patients = filters.minimum_patients

    df1["UPIDTreatment"] = df1["UPID"] + df1["Drug Name"]

    # Get average number of doses count
    org_codes = pd.read_csv(paths.org_codes_csv, index_col=1)
    df1["Provider Code"] = df1["Provider Code"].map(org_codes["Name"])
    #df1.to_csv("./df1.csv", index=False)

    df1 = df1[(df1["Provider Code"].isin(trustFilter)) & (df1["Drug Name"].isin(drugFilter)) & (df1["Directory"].isin(directorateFilter))]

    if len(df1) == 0:
        logger.warning("No data found for selected filters.")
        return

    # Find total cost for each patient - Total cost is ~£110Mil, about 30% is unattributable to a patient (no UPID)
    cost_df = df1[["UPID", "Price Actual"]]
    total_costs = pd.DataFrame(cost_df.groupby("UPID").sum())
    total_costs.rename(columns={"Price Actual": "Total cost"}, inplace=True)

    # Series to map directory
    directory_df = df1[["UPID", "Directory"]]
    directory_df.drop_duplicates("UPID", inplace=True)
    directory_df.set_index("UPID", inplace=True)
    logger.info("Filtering unrelated interventions")

    df_end_dates = drop_duplicate_treatments(df1, False)
    df1_unique = drop_duplicate_treatments(df1, True)
    logger.info("Identifying unique patients and interventions used")
    # Create list of total number of that drug for each patient
    df_drug_freq = df1.groupby("UPID").agg({"Drug Name": lambda x: list(x)}).reset_index().set_index("UPID")
    df_drug_cost = df1.groupby("UPID").agg({"Price Actual": lambda x: list(x)}).reset_index().set_index("UPID")
    df_drug_freq["Price Actual"] = df_drug_freq.index.map(df_drug_cost["Price Actual"])
    #df_drug_freq["Price Actual"] = df_drug_freq["Price Actual"].map(df_drug_cost)
    df_drug_freq["Drug Name"] = df_drug_freq["Drug Name"].apply(count_list_values)
    df_drug_freq["Drug cost total"] = df_drug_freq.apply(lambda x: sum_list_values(x), axis=1)


    # Aggregate interventions & dates of interventions into transposed list by UPID
    df_drugs = df1_unique.groupby("UPID").agg({"Drug Name": lambda x: list(x)}).reset_index().set_index("UPID")
    df_dates = df1_unique.groupby("UPID").agg({"Intervention Date": lambda x: list(x)}).reset_index().set_index("UPID")
    df_end_dates = df_end_dates.groupby("UPID").agg({"Intervention Date": lambda x: list(x)}).reset_index().set_index("UPID")

    logger.info("Calculating each unique patient's intervention average frequency, cost and duration of each intervention")
    # The following sh*t show is to unwrap the lists into columns for different drugs, start/end dates, and average
    # frequency/average total injections of each one
    df_dates_unwrapped = pd.DataFrame(df_dates["Intervention Date"].values.tolist(), index=df_dates.index).add_prefix(
        'date_')
    df_end_dates_unwrapped = pd.DataFrame(df_end_dates["Intervention Date"].values.tolist(), index=df_end_dates.index).add_prefix(
        'date_end_')
    df_drugs_unwrapped = pd.DataFrame(df_drugs["Drug Name"].values.tolist(), index=df_drugs.index).add_prefix('drug_')

    df_freq_unwrapped = pd.DataFrame(df_drug_freq["Drug Name"].values.tolist(), index=df_drug_freq.index).add_prefix(
        'freq_')
    start_dates = df1[["UPIDTreatment", "Intervention Date"]].sort_values(by=["Intervention Date"], ascending=True,
                                                                               inplace=False,
                                                                               ignore_index=True).drop_duplicates(
        subset="UPIDTreatment").set_index("UPIDTreatment")
    end_dates = df1[["UPIDTreatment", "Intervention Date"]].sort_values(by=["Intervention Date"], ascending=False,
                                                                             inplace=False,
                                                                             ignore_index=True).drop_duplicates(
        subset="UPIDTreatment").set_index("UPIDTreatment")



    df_drugs_unwrapped["start_dates"] = df_drugs_unwrapped.apply(lambda x: start_date_drug(start_dates, x), axis=1)

    df_ddrugs_unwrapped = pd.DataFrame(df_drugs_unwrapped["start_dates"].values.tolist(),
                                       index=df_drugs_unwrapped.index).add_prefix(
        'start_date_')
    df_drugs_unwrapped.drop(["start_dates"], inplace=True, axis=1)
    df_drugs_unwrapped["end_dates"] = df_drugs_unwrapped.apply(lambda x: start_date_drug(end_dates, x), axis=1)
    df_dddrugs_unwrapped = pd.DataFrame(df_drugs_unwrapped["end_dates"].values.tolist(),
                                       index=df_drugs_unwrapped.index).add_prefix(
        'end_date_')

    df_drugs_unwrapped.drop(["end_dates"], inplace=True, axis=1)
    df_drugs_unwrapped = pd.merge(df_drugs_unwrapped, df_ddrugs_unwrapped, left_index=True, right_index=True)
    df_drugs_unwrapped = pd.merge(df_drugs_unwrapped, df_dddrugs_unwrapped, left_index=True, right_index=True)
    df_dddddrugs_unwrapped = pd.DataFrame(df_drug_freq["Drug Name"].values.tolist(),
                                          index=df_drugs_unwrapped.index).add_prefix(
        'freq_')
    df_drugs_unwrapped = pd.merge(df_drugs_unwrapped, df_dddddrugs_unwrapped, left_index=True, right_index=True)
    df_drugs_unwrapped["frequency"] = df_drugs_unwrapped.apply(lambda x: drug_frequency_average(x), axis=1)

    df_ddddddrugs_unwrapped = pd.DataFrame(df_drugs_unwrapped["frequency"].values.tolist(),
                                           index=df_drugs_unwrapped.index).add_prefix(
        'spacing_')
    df_drugs_unwrapped = pd.merge(df_drugs_unwrapped, df_ddddddrugs_unwrapped, left_index=True, right_index=True)
    df_dddddddrugs_unwrapped = pd.DataFrame(df_drug_freq["Drug cost total"].values.tolist(),
                                           index=df_drugs_unwrapped.index).add_prefix('total_cost_drug_')
    df_drugs_unwrapped = pd.merge(df_drugs_unwrapped, df_dddddddrugs_unwrapped, left_index=True, right_index=True)
    df_drugs_unwrapped.drop(["frequency"], inplace=True, axis=1)

    # Insert first & last date seen into df (need to add last date seen)
    df_drugs_unwrapped.insert(0, "First seen", df_dates_unwrapped.min(axis=1))
    df_drugs_unwrapped.insert(1, "Last seen", df_end_dates_unwrapped.max(axis=1))

    # Merge info from activity data with grouped info, and total cost info
    patient_info = df1.drop_duplicates(subset="UPID", keep="first").set_index("UPID")
    patient_info = pd.merge(patient_info, df_drugs_unwrapped, left_index=True, right_index=True)
    patient_info = pd.merge(patient_info, df_freq_unwrapped, left_index=True, right_index=True)
    patient_info = pd.merge(patient_info, total_costs, left_index=True, right_index=True)

    #patient_info.to_csv("patient_info.csv", index=False)

    # Filter initiation based on years provided
    patient_info = patient_info[(patient_info['First seen'] >= str(start_date)) & (
                patient_info['First seen'] < str(end_date))]
    if title == "":
        title = "Patients initiated from " + str(start_date) + " to " + str(end_date)

    # Filter last seen based on date provided
    patient_info = patient_info[patient_info['Last seen'] > str(last_seen)]

    # Remove patients with 0 drug, by filling blanks with NaN & dropping rows
    patient_info.drug_0.replace('N/A', np.nan, inplace=True)
    patient_info.dropna(subset=['drug_0'], inplace=True)

    # Calculate duation of treatment
    patient_info['Days treated'] = patient_info["Last seen"] - patient_info["First seen"]
    date_df = patient_info[["First seen", "Last seen", 'Days treated']]

    # Create df for ice chart with hierarchy of plot
    number_of_drugs = np.count_nonzero(patient_info.columns.str.startswith('drug_'))
    final_drug_index = patient_info.columns.to_list().index("drug_" + str(number_of_drugs - 1))

    upid_drugs_df = patient_info.iloc[:, (final_drug_index - number_of_drugs + 1):final_drug_index + 1]

    upid_drugs_df.insert(0, "Trust", upid_drugs_df.index.str[:3])
    upid_drugs_df.insert(1, "Directory", upid_drugs_df.index)

    upid_drugs_df["Trust"] = upid_drugs_df["Trust"].map(org_codes["Name"])
    upid_drugs_df["Directory"] = upid_drugs_df["Directory"].map(directory_df["Directory"])

    l_df = pd.DataFrame()
    ice_df2 = pd.DataFrame()
    ice_df = pd.DataFrame()

    upid_drugs_df["value"] = upid_drugs_df.apply(lambda x: row_function(x), axis=1)
    # Merge in date info
    upid_drugs_df = pd.merge(upid_drugs_df, date_df, left_index=True, right_index=True)

    upid_drugs_df["ids"] = upid_drugs_df["value"].str.split(',').str[2]
    avg_treatment_dfs = pd.DataFrame(upid_drugs_df.groupby("ids", as_index=False)["Days treated"].mean()).set_index("ids")
    value_dfs = pd.DataFrame(upid_drugs_df.groupby("value", as_index=False).size()).reset_index()
    first_seen_treatment_dfs = pd.DataFrame(upid_drugs_df.groupby("ids", as_index=False)["First seen"].min()).set_index(
        "ids")
    last_seen_treatment_dfs = pd.DataFrame(upid_drugs_df.groupby("ids", as_index=False)["Last seen"].max()).set_index(
        "ids")

    # Calculate total cost for parents
    upid_drugs_df["Cost"] = upid_drugs_df.index.map(total_costs["Total cost"])
    cost_dfs = pd.DataFrame(upid_drugs_df.groupby("value", as_index=False)['Cost'].sum()).set_index("value", drop=True)

    # Calculate average dosing for each drug
    upid_drugs_df = pd.merge(upid_drugs_df, df_drugs_unwrapped, left_index=True, right_index=True)
    # frequency_dfs = pd.DataFrame(upid_drugs_df.groupby("value", as_index=False)['Cost'].sum()).set_index("value", drop=True)

    # Calculate average spacing between drugs
    spacing_average = pd.DataFrame(upid_drugs_df.groupby("value", as_index=False)[
                                       [col for col in upid_drugs_df.columns if 'spacing_' in col]].mean()).set_index(
        "value", drop=True)
    spacing_average = spacing_average.round()
    spacing_average['combined'] = spacing_average.values.tolist()
    spacing_average["ids"] = spacing_average.index
    spacing_average["ids"] = spacing_average["ids"].str.split(',').str[2]
    spacing_average.set_index("ids", inplace=True)

    # Calculate average cost for each drug
    cost_average = pd.DataFrame(upid_drugs_df.groupby("value", as_index=False)[
                                       [col for col in upid_drugs_df.columns if 'total_cost_drug_' in col]].mean()).set_index(
        "value", drop=True)
    cost_average = cost_average.round(2)
    cost_average['combined'] = cost_average.values.tolist()
    cost_average["ids"] = cost_average.index
    cost_average["ids"] = cost_average["ids"].str.split(',').str[2]
    cost_average.set_index("ids", inplace=True)


    # Calculate average number of doses
    freq_average = pd.DataFrame(upid_drugs_df.groupby("ids", as_index=False)[
                                    [col for col in upid_drugs_df.columns if 'freq_' in col]].mean()).set_index("ids",
                                                                                                                drop=True)
    # freq_average = freq_average.round()
    freq_average['combined'] = freq_average.values.tolist()

    # Remove negative totals from "Cost" column
    num = cost_dfs._get_numeric_data()
    num[num < 0] = 0

    value_dfs["Cost"] = value_dfs["value"].map(cost_dfs["Cost"])

    ice_df[['parents', 'labels', 'ids']] = value_dfs["value"].str.split(',', expand=True)
    # ice_df["index"] = ice_df.ids
    # ice_df.set_index("index", inplace=True)

    ice_df["average_administered"] = ice_df["ids"].map(freq_average["combined"])
    ice_df["cost"] = value_dfs["Cost"]
    ice_df["value"] = value_dfs["size"]

    ice_df["average_cost"] = ice_df["ids"].map(cost_average["combined"])
    ice_df["average_cost"] = ice_df["average_cost"].apply(remove_nan_string)

    ice_df["average_spacing"] = ice_df["ids"].map(spacing_average["combined"])
    ice_df["average_spacing"] = ice_df["average_spacing"].apply(remove_nan_string)
    ice_df["average_spacing"] = ice_df.apply(lambda x: list_to_string(x), axis=1)
    ice_df["average_spacing"] = ice_df["average_spacing"].str.replace("nan", "N/A")


    logger.info("Building graph dataframe structure.")
    # Add very top level of Trust
    new_row = pd.DataFrame({'parents': '', 'ids': "N&WICS", 'labels': 'N&WICS', 'value': 0, "cost": 0}, index=[0])
    ice_df = pd.concat(objs=[ice_df, new_row], ignore_index=True, axis=0)

    # need to add parents as blocks...
    l3 = [x for x in ice_df.parents.unique() if x not in ice_df.ids]
    while len(l3) > 1:
        for l in l3:
            z = l.rfind("-")
            if z > 0:
                l_dict = {"parents": l[:z - 1], "ids": l, "value": 0, "labels": l[z + 2:], "cost": 0}
                l_df = pd.concat([l_df, pd.DataFrame(l_dict, index=[0])], ignore_index=True)
        ice_df2 = pd.concat([ice_df, l_df], ignore_index=True)
        l3 = [x for x in ice_df2.parents.unique() if x not in ice_df2.ids.unique()]
    ice_df = ice_df2.drop_duplicates("ids")

    ice_df["level"] = ice_df["ids"].str.count('-')
    ice_df = ice_df[~ice_df['labels'].isin(["COST", "CHARGE", "N/A"])]
    ice_df.sort_values(by=["level"], ascending=False, inplace=True, ignore_index=True)

    for index, row in ice_df.iterrows():
        lookup_index = ice_df.index[ice_df['ids'] == row['parents']]
        ice_df.loc[lookup_index, 'value'] = ice_df.loc[lookup_index, "value"] + ice_df.loc[index, "value"]
        ice_df.loc[lookup_index, 'cost'] = ice_df.loc[lookup_index, "cost"] + ice_df.loc[index, 'cost']

    # Sum of parent values to create denominator for percentage - FOR PATIENT NUMBER COLOUR GRADING
    colour_df = pd.DataFrame(ice_df.groupby(["parents"])["value"].sum())
    ice_df['colour'] = ice_df["parents"].map(colour_df["value"])
    ice_df['colour'] = ice_df['value']/ice_df['colour']

    # Sum of parent values to create denominator for percentage - FOR COST COLOUR GRADING
    #colour_df = pd.DataFrame(ice_df.groupby(["parents"])["cost"].sum())
    #ice_df['colour'] = ice_df["parents"].map(colour_df["cost"])
    #ice_df['colour'] = ice_df['cost'] / ice_df['colour']


    ice_df['costpp'] = ice_df['cost'] / ice_df['value']
    # Treatment length info
    ice_df['avg_days'] = ice_df["ids"].map(avg_treatment_dfs["Days treated"])
    ice_df['First seen'] = ice_df["ids"].map(first_seen_treatment_dfs["First seen"])
    ice_df['Last seen'] = ice_df["ids"].map(last_seen_treatment_dfs["Last seen"])

    ice_df["dates"] = ice_df.apply(lambda x: min_max_treatment_dates(ice_df, x), axis=1)
    ice_df[['First seen (Parent)', 'Last seen (Parent)']] = ice_df["dates"].str.split(',', expand=True)

    # Sort labels to be alphabetical
    # ice_df.sort_values(by=["labels"], ascending=True, inplace=True, ignore_index=True)
    ice_df['First seen'] = pd.to_datetime(ice_df['First seen'])
    ice_df['Last seen'] = pd.to_datetime(ice_df['Last seen'])
    ice_df["cost_pp_pa"] = ice_df.apply(lambda x: cost_pp_pa(x), axis=1)

    # Filter out rows where value is less than minimum number of patients
    ice_df = ice_df[ice_df['value'] >= minimum_num_patients]

    logger.info("Generating graph.")

    figure(ice_df, title, save_dir)
    return


def figure(ice_df4, dir_string, save_dir):
    """
    Create and display icicle figure (legacy interface).

    This function delegates to visualization.plotly_generator.figure_legacy()
    for backward compatibility.

    Args:
        ice_df4: DataFrame with chart data
        dir_string: Title string (used for filename and chart title)
        save_dir: Directory to save the HTML file
    """
    _figure_legacy(ice_df4, dir_string, save_dir)
    return


# fig = go.Figure(go.Icicle(
#         labels=ice_df4.labels,
#         ids=ice_df4.ids,
#         # count="branches",
#         parents=ice_df4.parents,
#         customdata=np.stack((ice_df4.value, ice_df4.colour, ice_df4.cost, ice_df4.costpp, first_seen, last_seen,
#                              first_seen_parent, last_seen_parent, average_spacing, ice_df4.cost_pp_pa), axis=1),
#         values=ice_df4.value,
#         branchvalues="total",
#         marker=dict(
#             colors=ice_df4.colour,
#             colorscale='Viridis'),
#         maxdepth=3,
#         texttemplate='<b>%{label}</b> '
#                       '<br><b>Total patients:</b> %{customdata[0]} - %{customdata[1]:.3p} of patients in level'
#                       '<br><b>Total cost:</b> £%{customdata[2]:.3~s}'
#                       '<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}'
#                       '<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}',
#         hovertemplate='<b>%{label}</b>'
#                       '<br><b>Total patients:</b> %{customdata[0]} - %{customdata[1]:.3p} of patients in level'
#                       '<br><b>Total cost:</b> £%{customdata[2]:.3~s}'
#                       '<br><b>Average cost per patient:</b> £%{customdata[3]:.3~s}'
#                       '<br><b>Average cost per patient per annum:</b> £%{customdata[9]:.3~s}'
#                       '<br><b>First seen:</b> %{customdata[4]}'
#                       '<br><b>Last seen (including further treatments):</b> %{customdata[7]}'
#                       '<br><b>Average treatment duration:</b>'
#                       '%{customdata[8]}'
#                       '<extra></extra>',
#     ))
#
#import os 
#def main():
#    input = "ice_df.csv"
#    save_dir = os.path.dirname(os.path.abspath(__file__))
#    dir = "debugging"
#    ice_df4 = pd.read_csv(input)
#    
#    ice_df4['First seen'] = pd.to_datetime(ice_df4['First seen'])
#    ice_df4['avg_days'] = pd.to_timedelta(ice_df4['avg_days'])
#    ice_df4['Last seen'] = pd.to_datetime(ice_df4['Last seen'])
#    figure(ice_df4, dir, save_dir)
#
#if __name__ == "__main__":
#    main()


def generate_graph_v2(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    last_seen_date: str,
    save_dir: str,
    trust_filter: list[str],
    drug_filter: list[str],
    directory_filter: list[str],
    minimum_num_patients: int = 0,
    title: str = "",
    paths: Optional[PathConfig] = None,
) -> Optional[go.Figure]:
    """
    Generate patient pathway icicle chart using refactored pipeline.

    This is the modern API that uses the refactored analysis functions.
    It provides cleaner parameter names and returns the figure instead of
    automatically opening it in a browser.

    Args:
        df: DataFrame with processed patient intervention data
        start_date: Start date for patient initiation filter (YYYY-MM-DD)
        end_date: End date for patient initiation filter (YYYY-MM-DD)
        last_seen_date: Filter for patients last seen after this date
        save_dir: Directory to save the HTML file
        trust_filter: List of trust names to include
        drug_filter: List of drug names to include
        directory_filter: List of directories to include
        minimum_num_patients: Minimum number of patients to include a pathway
        title: Chart title (auto-generated from dates if empty)
        paths: PathConfig for file paths (uses default if None)

    Returns:
        Plotly Figure object, or None if no data
    """
    if paths is None:
        paths = default_paths

    ice_df, final_title = _generate_icicle_chart(
        df=df,
        start_date=start_date,
        end_date=end_date,
        last_seen_date=last_seen_date,
        trust_filter=trust_filter,
        drug_filter=drug_filter,
        directory_filter=directory_filter,
        minimum_num_patients=minimum_num_patients,
        title=title,
        paths=paths,
    )

    if ice_df is None or len(ice_df) == 0:
        return None

    fig = create_icicle_figure(ice_df, final_title)

    if save_dir:
        fig.write_html(f"{save_dir}/{final_title}.html")
        logger.info(f"Success! File saved to {save_dir}/{final_title}.html")

    return fig


def create_icicle_figure(ice_df: pd.DataFrame, title: str) -> go.Figure:
    """
    Create Plotly icicle figure from prepared DataFrame.

    This function delegates to visualization.plotly_generator.create_icicle_figure()
    for the actual figure generation.

    Args:
        ice_df: DataFrame with parents, ids, labels, value, colour etc.
        title: Chart title

    Returns:
        Plotly Figure object
    """
    return _create_icicle_figure(ice_df, title)
