'''
Includes all calculations in the excel sheet and functions to execute them
'''

import os
import pandas as pd
from qgis.core import QgsMessageLog, Qgis 

PLUGIN_DIR = os.path.dirname(__file__)
REFERENCE_XLSX = os.path.join(PLUGIN_DIR, "data", "SGBA_Reference.xlsx")

### HELPER FUNCTIONS

# Convert value to float and return 0.0 if conversion fails
def _safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

# Strips whitespace and converts to uppercase for safe dictionary matching.
def _clean_str(val):
    if pd.isna(val) or val is None:
        return ""
    
    # Convert to uppercase and strip outer whitespace
    cleaned = str(val).strip().upper()
    
    # Obliterate all internal spaces and dashes
    cleaned = cleaned.replace(" ", "").replace("-", "")
    
    return cleaned
    
# Convert time to strings for display
def _time_str(val):
    if pd.isna(val):
        return "Not Possible"
    s = str(val).strip()
    return "Not possible" if s in ("", "nan") else s
    
# Lookup distinctiveness score from habitat
def _dist_score(habitat_name, lookups):
    hab_clean = _clean_str(habitat_name)
    return lookups["z1"].get(hab_clean, {}).get("score", 0.0)

#Create habitat/condition key for enhancement lookup
def _make_hab_con_key(habitat, condition):
    hab = _clean_str(habitat)
    con = _clean_str(condition)
    if not hab or not con:
        return ""
    return f"{hab}/{con}"
    
### LOAD LOOKUP TABLE
def load_lookups():
    lookups = {}
    
    # Z1: HABITAT CLASS
    lookups['z1'] = {}
    try:
        z1_df = pd.read_excel(REFERENCE_XLSX, sheet_name='Z1 HAB CLASS', skiprows=2)
        
        # Forward-fill the 'Ecosystem' column to handle Excel's merged cells
        if 'Ecosystem' in z1_df.columns:
            z1_df['Ecosystem'] = z1_df['Ecosystem'].ffill()
            
        # Build category-to-score mapping from columns L-N
        category_scores = {}
        if 'CLASS' in z1_df.columns and 'VALUE' in z1_df.columns:
            for _, row in z1_df.iterrows():
                cls = _clean_str(row.get('CLASS'))
                val = row.get('VALUE')
                if cls and pd.notna(val):
                    category_scores[cls] = _safe_float(val)
        else:
            # Fallback mapping just in case the columns are named differently
            category_scores = {
                "VERY HIGH": 8.0, "HIGH": 6.0, "MODERATE": 4.0, 
                "LOW": 2.0, "VERY LOW": 1.0, "EXTREMELY LOW": 0.5, "NO VALUE": 0.0
            }
        lookups["cat_score_map"] = category_scores

        for _, row in z1_df.iterrows():
            # Using .iloc or generic gets just in case headers have trailing spaces
            sub_hab = _clean_str(row.get('Sub habitat'))
            category = _clean_str(row.get('Category')) 
            
            if sub_hab:
                lookups['z1'][sub_hab] = {
                    'ecosystem': _clean_str(row.get('Ecosystem')),
                    'category': category,
                    'score': category_scores.get(category, 0.0) 
                }
                
        # FORCE A LOUD ERROR IF IT IS EMPTY
        if len(lookups['z1']) == 0:
            cols = list(z1_df.columns)
            raise ValueError(f"Z1 is empty! Pandas found these exact columns in Excel: {cols}")
            
    except Exception as e:
        QgsMessageLog.logMessage(f"CRITICAL EXCEL ERROR: {str(e)}", 'SGBA', level=Qgis.Critical)
        raise ValueError(f"Failed to read Excel file. Error: {str(e)}")

        # 2. Map the habitats to their corresponding category score
        for _, row in z1_df.iterrows():
            sub_hab = _clean_str(row.get('Sub habitat'))
            category = _clean_str(row.get('Category')) # e.g., "Very high"
            
            if sub_hab:
                lookups['z1'][sub_hab] = {
                    'ecosystem': _clean_str(row.get('Ecosystem')),
                    'category': category,
                    # This is the crucial fix: It matches the habitat's class to the distinctiveness score
                    'score': category_scores.get(category, 0.0) 
                }
    except Exception as e:
        print(f"Error loading Z1: {e}")

    # Z3: CONDITION VALUE
    try:
        df3 = pd.read_excel(REFERENCE_XLSX, sheet_name = "Z3 CONDITION VALUE", header = None, skiprows = 2)
        z3 = {}
        lookups["z3"] = z3
    except Exception as e:
        print(f"Error loading Z3: {e}")
        lookups["z3"] = {"GOOD": 3.0, "MODERATE": 2.0, "POOR": 1.0, "NA": 0.0}

    for _, row in df3.iterrows():
        if pd.notna(row[0]) and pd.notna(row[1]): # Checks if both the condition text and value exist
            z3[_clean_str(row[0])] = _safe_float(row[1]) # Store condition score
    
    #Z7: TARGET CREATION
    df7 = pd.read_excel(REFERENCE_XLSX, sheet_name="Z7 TARGET CREATION", header=None, skiprows=2)
    z7 = {}
    
    for _, row in df7.iterrows():
        sub = _clean_str(row[1]) # Clean habitat name from column B
        if not sub or sub == "SUB HABITAT": # Skip empty or header rows
            continue
    
        z7[sub] = {
            "multiplier": _safe_float(row[7]), # Column H
            "difficulty": str(row[8]).strip() if pd.notna(row[8]) else "Not possible", # Extracts text difficulty
            # Extract time-to-target
            "YEARS_GOOD": _time_str(row[2]), 
            "YEARS_MODERATE": _time_str(row[3]), 
            "YEARS_POOR": _time_str(row[4]), 
        }
    lookups["z7"] = z7
    
    #Z8: TARGET ENH 
    df8_mults = pd.read_excel(REFERENCE_XLSX, sheet_name="Z8 TARGET ENH", header=None, usecols="FH:FJ")
    z8_data = {}

    for _, row in df8_mults.iterrows():
        sub = _clean_str(row.iloc[0])

        if not sub or sub in ("SUB HABITAT", "START CONDITION", "#ERROR!", "NAN", "HABITAT"):
            continue

        mult_val = row.iloc[1]
        diff_val = row.iloc[2]

        z8_data[sub] = {
            "multiplier": _safe_float(mult_val) if pd.notna(mult_val) else 1.0,  
            "difficulty": str(diff_val).strip() if pd.notna(diff_val) else "Standard",
        }

    lookups["z8_data"] = z8_data

    # ENH POSSIBILITY
    enh_df = pd.read_excel(REFERENCE_XLSX, sheet_name="ENH POSSIBILITY")
    enh_possible = set()

    for _, row in enh_df.iterrows():
        if len(row) >= 2:
            baseline = _clean_str(row.iloc[0])  
            post_con = _clean_str(row.iloc[1])

            if baseline and post_con:
                enh_possible.add((baseline, post_con))
    
    lookups["enh_possible"] = enh_possible

    return lookups
    
### CORE SGBA CALCULATIONS

def determine_status(pre_hab, pre_con, post_hab, post_con, lookups):
    p_hab = _clean_str(pre_hab)
    f_hab = _clean_str(post_hab)
    p_con = _clean_str(pre_con)
    f_con = _clean_str(post_con)
    
    if not p_hab: return "CREATED"
    if not f_hab: return "LOSS"
    
    if p_hab == f_hab and p_con == f_con:  # Same habitat AND condition
        return "RETAINED"  # No change
        
    # Build habitat/condition keys for enhancement lookup
    baseline_key = _make_hab_con_key(p_hab, p_con)
    post_key = _make_hab_con_key(f_hab, f_con)

    if (baseline_key, post_key) in lookups["enh_possible"]:
        return "ENHANCED"  # Valid enhancement pathway
    
    return "CREATED"

def calculate_baseline_units(area_ha, pre_hab, pre_con, lookups):
    dist = _dist_score(pre_hab, lookups) 
    cond = lookups["z3"].get(_clean_str(pre_con), 0.0) 
    units = area_ha * dist * cond 
    return units, dist, cond
    
def calculate_creation_units(area_ha, post_hab, post_con, lookups):
    dist = _dist_score(post_hab, lookups) 
    target_cond_clean = _clean_str(post_con)
    cond = lookups["z3"].get(target_cond_clean, 0.0)
    
    hab_clean = _clean_str(post_hab)
    
    # Alert the user if the habitat spelling is missing from the Z7 Excel sheet
    if hab_clean and hab_clean not in lookups["z7"]:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(f"WARNING: '{hab_clean}' missing from Z7. Defaulting multiplier to 1.0", 'SGBA', level=Qgis.Warning)

    z7_entry = lookups["z7"].get(hab_clean, {}) 
    
    # FIX: Change defaults from 0.0 to 1.0 so the math doesn't nuke itself on a typo
    mult = z7_entry.get("multiplier", 1.0) 
    diff = z7_entry.get("difficulty", "Standard") 
    years = z7_entry.get(f"YEARS_{target_cond_clean}", "Not possible")
    
    if diff == "Not possible" or mult == 0.0:
        units = 0.0 
    else:
        units = area_ha * dist * cond * mult 
    return units, dist, cond, mult, years
        
def calculate_enhancement_units(area_ha, pre_hab, pre_con, post_hab, post_con, lookups):
    baseline_dist = _dist_score(pre_hab, lookups)
    start_cond_clean = _clean_str(pre_con)
    baseline_cond = lookups["z3"].get(start_cond_clean, 0.0) 
    
    target_dist = _dist_score(post_hab, lookups) 
    target_cond_clean = _clean_str(post_con)
    target_cond = lookups["z3"].get(target_cond_clean, 0.0)
    
    hab_clean = _clean_str(post_hab)
    
    # Alert the user if the habitat spelling is missing from the Z8 Excel sheet
    if hab_clean and hab_clean not in lookups["z8_data"]:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(f"WARNING: '{hab_clean}' missing from Z8. Defaulting multiplier to 1.0", 'SGBA', level=Qgis.Warning)

    z8_entry = lookups["z8_data"].get(hab_clean, {}) 
    
    # FIX: Change defaults from 0.0 to 1.0
    mult = z8_entry.get("multiplier", 1.0) 
    diff = z8_entry.get("difficulty", "Standard")

    baseline_key = _make_hab_con_key(pre_hab, pre_con)
    post_key = _make_hab_con_key(post_hab, post_con)

    years = "Not possible"
    if (baseline_key, post_key) in lookups["enh_possible"]:
        years = "See ENH POSSIBILITY"

    if diff == "Not possible" or mult == 0.0:
        units = 0.0
    else:
        post_val = area_ha * target_dist * target_cond  
        base_val = area_ha * baseline_dist * baseline_cond  
        units = post_val - (base_val * mult) + base_val 
    
    return units, target_dist, target_cond, mult, years
    
### FEATURE PROCESSING
def process_polygon_feature(feature_dict, lookups):
    pre_area = feature_dict.get('pre_area', 0.0)  # Baseline area
    post_area = feature_dict.get('post_area', 0.0)  # Post-con area
    pre_hab = feature_dict.get('pre_hab', '')  # Baseline habitat
    pre_con = feature_dict.get('pre_con', '')  # Baseline condition
    post_hab = feature_dict.get('post_hab', '')  # Post-con habitat
    post_con = feature_dict.get('post_con', '')  # Post-con condition
    
    # Determine status (RETAINED/ENHANCED/CREATED/LOSS)
    post_stat = determine_status(pre_hab, pre_con, post_hab, post_con, lookups)
    
    # Get ecosystem type 
    hab_for_eco = post_hab if post_hab else pre_hab  # Use post if exists, else pre
    ecosystem = lookups["z1"].get(_clean_str(hab_for_eco), {}).get("ecosystem", "TERRESTRIAL")
    
    # Calculate baseline units (use pre_area)
    base_units, base_dist, base_cond = calculate_baseline_units(
        pre_area, pre_hab, pre_con, lookups
    )

    # Initialize post-development values
    post_units = 0.0
    time_to_target = "N/A"
    
    # Calculate post-development units based on status
    if post_stat == "RETAINED":  # Same habitat, same condition
        post_units, _, _ = calculate_baseline_units(post_area, pre_hab, pre_con, lookups)
        time_to_target = "0"  # Already at target
    
    elif post_stat == "CREATED":  # New habitat
        post_units, _, _, _, time_to_target = calculate_creation_units(
            post_area, post_hab, post_con, lookups
        )
    
    elif post_stat == "ENHANCED":  # Improved condition
            post_units, p_dist, p_cond, mult, time_to_target = calculate_enhancement_units(
                post_area, pre_hab, pre_con, post_hab, post_con, lookups
            )
    
    else:  # LOSS or unknown
        post_units = 0.0
        time_to_target = "N/A"
    
    # Return results
    return {
        "ecosystem": ecosystem,  # Terrestrial/Freshwater/Marine
        "baseline_units": base_units,  # Baseline biodiversity units
        "post_units": post_units,  # Post-development units
        "net_change": post_units - base_units,  # Change in units
        "time_to_target": time_to_target,  # Years to target (info only)
    }
