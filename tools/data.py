import numpy as np
import pandas as pd
import csv
import urllib.request
import io # Added for StringIO
import re # Added for regex escape and word boundaries
from typing import Optional

from core import PathConfig, default_paths
from core.logging_config import get_logger

logger = get_logger(__name__)

def drug_names(df, paths: Optional[PathConfig] = None):
    # Generate dictionary to convert drug names from activity data to generic standardisation
    if paths is None:
        paths = default_paths

    d = {}
    with open(paths.drugnames_csv, 'r', newline='') as f:
        reader = csv.reader(f, delimiter=',')
        for drug_name, generic in reader:
            d[drug_name.upper()] = generic.upper()

    # Map drug names with dictionary generated earlier
    df["Drug Name"] = df["Drug Name"].str.upper().map(d)

    # Remove (Left eye) or (Right eye) from Drug Name, including whitespace
    df["Drug Name"] = df["Drug Name"].str.replace(r'\(LEFT EYE\)', '', regex=True) # Escaped parentheses
    df["Drug Name"] = df["Drug Name"].str.replace(r'\(RIGHT EYE\)', '', regex=True) # Escaped parentheses
    df["Drug Name"] = df["Drug Name"].str.strip()
    return df


def patient_id(df):
    # Generate unique patient ID
    df["UPID"] = df["Provider Code"].str[:3] + df["PersonKey"].astype(str)
    return df


def compress_csv(filepath):
    df = pd.read_csv(filepath)
    compressed_path = filepath.replace(".csv", "_bz2.csv")
    df.to_csv(compressed_path, compression="bz2", index=False)
    return compressed_path


def department_identification(df, paths: Optional[PathConfig] = None):
    # --- Setup ---
    if paths is None:
        paths = default_paths

    # 1. Load directory_list.csv and prepare uppercase versions/pattern
    try:
        directory_df = pd.read_csv(paths.directory_list_csv)
        directory_list = directory_df["directory"].dropna().astype(str).tolist()
        if not directory_list:
             raise ValueError("directory_list.csv is empty or contains only NA values.")
        directory_list_upper = [d.upper() for d in directory_list]
        # Use word boundaries (\b) to avoid partial matches within words, escape special regex chars
        dir_pattern_upper = r'\b({})'.format('|'.join(map(re.escape, directory_list_upper)))
    except FileNotFoundError:
         logger.error(f"File not found: {paths.directory_list_csv}. Cannot extract directories.")
         return df
    except ValueError as e:
         logger.error(f"Error loading directory list: {e}")
         return df

    # Simpler pattern for Primary_Source (no word boundaries)
    dir_pattern_primary_simple = r'({})'.format('|'.join(map(re.escape, directory_list_upper)))

    # 2. Load treatment_function_codes.csv and prepare uppercase mapping
    treatment_codes = pd.read_csv(paths.treatment_function_codes_csv)
    mapping_treatment_codes = dict(treatment_codes[['Code', 'Service']].values)
    mapping_treatment_codes_upper = {k: str(v).upper() for k, v in mapping_treatment_codes.items()}

    # 3. Load drug_directory_list.csv and parse into drug_to_valid_dirs
    drug_to_valid_dirs: dict[str, set[str]] = {}
    # Try pandas direct read - much simpler approach
    drug_dir_df = pd.read_csv(paths.drug_directory_list_csv, skipinitialspace=True)
    
    # Identify the drug name column (first column) and directory column (second column)
    drug_col = drug_dir_df.columns[0]
    dir_col = drug_dir_df.columns[1]
    
    # Process dataframe directly
    drug_to_valid_dirs = {}
    for _, row in drug_dir_df.iterrows():
        drug_name = str(row[drug_col]).strip().upper()
        try:
            # Directories are pipe-separated in the second column
            dirs_str = str(row[dir_col]) if not pd.isna(row[dir_col]) else ""
            dirs = {d.strip().upper() for d in dirs_str.split('|') if d.strip()}
            if drug_name and dirs and drug_name.lower() != 'nan':
                drug_to_valid_dirs[drug_name] = dirs
        except Exception:
            # Silently continue on row errors
            continue
    # 4. Create drug_to_single_dir map
    drug_to_single_dir = {
        drug: list(dirs)[0]
        for drug, dirs in drug_to_valid_dirs.items()
        if len(dirs) == 1
    }

    # --- Data Preprocessing ---
    # Keep original extraction columns list
    additional_detail_columns = ["Additional Detail 1", "Additional Description 1", "Additional Detail 2", "Additional Description 2",
     "Additional Detail 3", "Additional Description 3", "Additional Detail 4", "Additional Description 4",
     "Additional Detail 5", "Additional Description 5", "NCDR Treatment Function Name", "Treatment Function Desc"]

    # 6. Convert detail columns to uppercase BEFORE extraction
    for ad in additional_detail_columns:
         # Check if column exists and is object/string type before applying .str
         if ad in df.columns and pd.api.types.is_object_dtype(df[ad]):
              df[ad] = df[ad].str.upper()

    # Original extraction loop (using original case list for extraction)
    # Extract directory from specified columns
    directory_df = pd.read_csv(paths.directory_list_csv)
    directory_list = directory_df["directory"].tolist() # Reload original case list

    for ad in additional_detail_columns:
        try:
            # Ensure column is string type before cleaning
            if pd.api.types.is_string_dtype(df[ad]):
                 # Extract directly from the uppercased string column
                 extracted = df[ad].str.extract(dir_pattern_upper, expand=False)
                 df.loc[extracted.index, ad] = extracted
            else:
                 df[ad] = np.nan # Set non-string columns to NaN
        except AttributeError: # Skip columns that might not exist or are not string type
             df[ad] = np.nan # Ensure column exists but set to NaN if error
        except Exception as e: # Catch other potential errors during extract
             logger.error(f"Error processing column {ad}: {e}")
             df[ad] = np.nan

    # 7. Process Treatment Function Code
    df["Treatment Function Code"].replace(np.nan, 0, inplace=True)
    # Ensure it's int type before mapping, handle potential errors
    try:
        df["Treatment Function Code"] = df["Treatment Function Code"].astype(int)
    except ValueError:
        # Handle cases where conversion to int fails (e.g., non-numeric values)
        # Try coercing errors to NaN, then fillna with 0
        df["Treatment Function Code"] = pd.to_numeric(df["Treatment Function Code"], errors='coerce').fillna(0).astype(int)

    df["Treatment Function Code"] = df["Treatment Function Code"].map(mapping_treatment_codes_upper)
    df.rename(columns={'Treatment Function Code': 'Fallback_Source'}, inplace=True)

    # Apply replacements before combining
    df.replace('MEDICAL OPHTHALMOLOGY', 'OPHTHALMOLOGY', inplace=True)

    # --- Single Directory Assignment ---
    # 8. Apply single directory override
    # Ensure Drug Name is suitable for mapping (already done in drug_names func)
    df['Directory'] = df['Drug Name'].map(drug_to_single_dir)

    # Initialize Directory_Source column - track which fallback level was used
    df['Directory_Source'] = pd.NA
    # Mark rows where single valid directory was assigned
    df.loc[df['Directory'].notna(), 'Directory_Source'] = 'SINGLE_VALID_DIR'

    # --- Prepare Fallback Logic ---
    # 9. Create Primary source from Additional Detail 1
    if 'Additional Detail 1' in df.columns:
        df['Primary_Source'] = df['Additional Detail 1'].astype(pd.StringDtype())
        df['Primary_Source'] = df['Primary_Source'].str.upper() # Apply upper to strings
    else:
        df['Primary_Source'] = pd.NA # Use pd.NA for StringDtype

    # Extract actual directory name using the pattern
    try:
        # Use simpler pattern for primary source
        df['Extracted_Primary_Dir'] = df['Primary_Source'].str.extract(dir_pattern_primary_simple, expand=False, flags=re.IGNORECASE)
        df['Extracted_Fallback_Dir'] = df['Fallback_Source'].str.extract(dir_pattern_upper, expand=False, flags=re.IGNORECASE)
    except Exception as e:
        logger.error(f"Error during directory extraction: {e}")
        # Assign NA columns if extraction fails
        df['Extracted_Primary_Dir'] = pd.NA
        df['Extracted_Fallback_Dir'] = pd.NA

    # Strip potential whitespace from extracted directories
    if 'Extracted_Primary_Dir' in df.columns:
         df['Extracted_Primary_Dir'] = df['Extracted_Primary_Dir'].str.strip()
    if 'Extracted_Fallback_Dir' in df.columns:
         df['Extracted_Fallback_Dir'] = df['Extracted_Fallback_Dir'].str.strip()

    # 10. Combine sources, prioritizing Primary_Source
    # Combine EXTRACTED directories
    df['Primary_Directory'] = df['Extracted_Primary_Dir'].fillna(df['Extracted_Fallback_Dir'])

    # Track extraction source for Directory_Source column
    # Rows where we have Extracted_Primary_Dir will use EXTRACTED_PRIMARY
    # Rows where we only have Extracted_Fallback_Dir will use EXTRACTED_FALLBACK
    df['_extracted_source'] = pd.NA
    df.loc[df['Extracted_Primary_Dir'].notna(), '_extracted_source'] = 'EXTRACTED_PRIMARY'
    df.loc[(df['Extracted_Primary_Dir'].isna()) & (df['Extracted_Fallback_Dir'].notna()), '_extracted_source'] = 'EXTRACTED_FALLBACK'

    # 11. Clean up intermediate columns
    df.drop(columns=['Primary_Source', 'Fallback_Source', 'Extracted_Primary_Dir', 'Extracted_Fallback_Dir'], inplace=True, errors='ignore')

    # --- Identify Rows Needing Calculation ---
    # 12. Filter rows where Directory is not yet assigned
    df_to_process = df[df['Directory'].isnull()].copy()

    # --- Calculate Most Frequent Valid Directory ---
    # 13. Drop rows without a potential primary directory
    df_to_process.dropna(subset=['Primary_Directory'], inplace=True)

    # 14. Group and count potential directories
    if not df_to_process.empty:
        df_counts = df_to_process.groupby(['UPID', 'Drug Name', 'Primary_Directory'], observed=True)['Primary_Directory'].count().reset_index(name='count')

        # 15. Sort by count descending
        df_counts.sort_values(['UPID', 'Drug Name', 'count'], ascending=[True, True, False], inplace=True)

        # 16. Define helper function
        def find_first_valid_dir(group, drug_map):
            drug_name = group['Drug Name'].iloc[0]
            valid_dirs = drug_map.get(drug_name, set())
            
            if not valid_dirs:
                return np.nan
            
            for dir_candidate in group['Primary_Directory']:
                # Skip NA values
                if pd.isna(dir_candidate):
                    continue
                    
                # Check if valid directory for this drug
                if isinstance(dir_candidate, str) and dir_candidate in valid_dirs:
                    return dir_candidate
            
            return np.nan # No valid directory found in the group

        # 17. Group by UPID and Drug Name
        valid_groups = df_counts.groupby(['UPID', 'Drug Name'], observed=True, group_keys=False)

        # 18. Apply helper function to find the best valid directory
        calculated_dirs = valid_groups.apply(lambda grp: find_first_valid_dir(grp, drug_to_valid_dirs))

        # 19. Reset index to get UPID, Drug Name columns
        final_mapping = calculated_dirs.reset_index()

        # 20. Rename the resulting column
        final_mapping.columns = ['UPID', 'Drug Name', 'Calculated_Directory']

        # --- Merge Results and Finalize ---
        # 21. Merge calculated directories back to the main DataFrame
        df = pd.merge(df, final_mapping, on=['UPID', 'Drug Name'], how='left')

        # 22. Fill NaN Directories with the calculated ones and track source
        # Find rows that will be filled from Calculated_Directory
        rows_to_fill = df['Directory'].isna() & df['Calculated_Directory'].notna()
        # For these rows, set Directory_Source based on _extracted_source (where the calculated dir came from)
        # The "calculated" directory is still derived from extraction, just via frequency analysis
        df.loc[rows_to_fill, 'Directory_Source'] = df.loc[rows_to_fill, '_extracted_source'].fillna('CALCULATED_MOST_FREQ')
        # Replace with the actual value of _extracted_source or fall back to CALCULATED_MOST_FREQ
        # Actually, let's simplify: if we're using the calculated most frequent directory, that's CALCULATED_MOST_FREQ
        df.loc[rows_to_fill, 'Directory_Source'] = 'CALCULATED_MOST_FREQ'

        df['Directory'].fillna(df['Calculated_Directory'], inplace=True)

        # 23. Drop temporary columns
        df.drop(columns=['Calculated_Directory', 'Primary_Directory', '_extracted_source'], inplace=True, errors='ignore')

    else:
         # If df_to_process was empty, still need to drop temporary columns
         df.drop(columns=['Primary_Directory', '_extracted_source'], inplace=True, errors='ignore')

    # 24. Drop rows with missing UPID (original logic)
    df['UPID'].replace('', np.nan, inplace=True) # Ensure empty strings are NaN
    df_orig = df.copy() # Save before dropna for future reference if needed
    df.dropna(subset=['UPID'], inplace=True)

    # 25. Export rows with NA Directory to CSV for analysis (keep this for diagnostics)
    na_directory_rows = df[df['Directory'].isna()].copy()
    
    # Export to CSV if there are any NA Directory rows
    if len(na_directory_rows) > 0:
        na_directory_rows.to_csv(paths.na_directory_rows_csv, index=False)
    
    # 26. FALLBACK MECHANISM 1: Infer directory based on same UPID
    # Create a mapping of most frequent directory per UPID (only for UPIDs with a directory)
    if len(df[df['Directory'].isna()]) > 0:
        # First get valid directories per UPID
        valid_upid_dirs = df[df['Directory'].notna()].groupby('UPID')['Directory'].agg(
            lambda x: x.value_counts().index[0] if len(x.value_counts()) > 0 else None
        ).to_dict()

        # Apply UPID-based inference and track source
        for idx in df[df['Directory'].isna()].index:
            upid = df.loc[idx, 'UPID']
            if upid in valid_upid_dirs and valid_upid_dirs[upid] is not None:
                df.loc[idx, 'Directory'] = valid_upid_dirs[upid]
                df.loc[idx, 'Directory_Source'] = 'UPID_INFERENCE'

    # 27. FALLBACK MECHANISM 2: Label remaining NA as "Undefined"
    # Track rows that will be marked as Undefined
    rows_undefined = df['Directory'].isna()
    df.loc[rows_undefined, 'Directory_Source'] = 'UNDEFINED'
    # Fill remaining NA directories with "Undefined"
    df['Directory'].fillna("Undefined", inplace=True)

    # 28. Return the processed DataFrame
    return df



def ta_list_get(paths: Optional[PathConfig] = None):
    if paths is None:
        paths = default_paths

    link = "https://www.nice.org.uk/Media/Default/About/what-we-do/NICE-guidance/NICE-technology-appraisals/TA%20recommendations.xlsx"
    urllib.request.urlretrieve(link, paths.ta_recommendations_xlsx)
    ta_db = pd.read_excel(paths.ta_recommendations_xlsx, index_col=0)

    # Filter out TA's which are not Recommended or not Pharmaceutical
    ta_db = ta_db[ta_db["Categorisation (for specific recommendation)"].isin(["Recommended", "Optimised"])]
    ta_db = ta_db[ta_db["Technology type"] == "Pharmaceutical"]

    # Amend TA001 strings to only the integer
    ta_db["TA ID"] = ta_db["TA ID"].str.replace(r'\D+', '', regex=True).astype(int)
    ta_db["TA ID"] = "NICE TA" + ta_db["TA ID"].astype(str)
    ta_series = ta_db[["TA ID", "Indication"]].drop_duplicates()
    return ta_series




