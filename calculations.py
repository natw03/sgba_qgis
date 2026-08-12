'''
Includes all calculations in the excel sheet and functions to execute them
'''

import datetime
import logging
import os
import pandas as pd

log = logging.getLogger(__name__)

_container_xlsx = '/data/SGBA_Reference.xlsx'
_local_xlsx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "SGBA_Reference.xlsx")
REFERENCE_XLSX = _container_xlsx if os.path.exists(_container_xlsx) else _local_xlsx

### HELPER FUNCTIONS

# Convert value to float and return 0.0 if conversion fails
def _safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

# Strips whitespace and converts to uppercase for safe dictionary matching.
def _clean_str(val):
    if val is None:
        return ""

    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    
    # Convert to uppercase and strip outer whitespace
    cleaned = str(val).strip().upper()
    
    # Obliterate all internal spaces and dashes
    cleaned = cleaned.replace(" ", "").replace("-", "")
    
    return cleaned
    
# Convert time to strings for display
def _time_str(val):
    try:
        if pd.isna(val):
            return "Not Possible"
    except (TypeError, ValueError):
        pass
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
            
        if 'Broad habitat' in z1_df.columns:
            z1_df['Broad habitat'] = z1_df['Broad habitat'].ffill()
            
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
        
        # Trading requirement column name
        trading_col = 'Trading acceptable? Trading and Offset Requirement'

        for _, row in z1_df.iterrows():
            # Using .iloc or generic gets just in case headers have trailing spaces
            sub_hab = _clean_str(row.get('Sub habitat'))
            category = _clean_str(row.get('Category')) 
            
            broad_raw = row.get('Broad habitat')
            broad_habitat = str(broad_raw).strip() if pd.notna(broad_raw) else ""
            
            trading_raw = row.get(trading_col)
            trading_requirement = str(trading_raw).strip() if pd.notna(trading_raw) else ""
            
            if sub_hab:
                lookups['z1'][sub_hab] = {
                    'ecosystem': _clean_str(row.get('Ecosystem')),
                    'broad_habitat': broad_habitat,
                    'category': str(row.get('category', '')).strip(),
                    'score': category_scores.get(category, 0.0),
                    'trading_requirement': trading_requirement,
                }
                
        # FORCE A LOUD ERROR IF IT IS EMPTY
        if len(lookups['z1']) == 0:
            cols = list(z1_df.columns)
            raise ValueError(f"Z1 is empty! Found these exact columns in Excel: {cols}")
            
    except Exception as e:
        log.critical(f"CRITICAL EXCEL ERROR: {str(e)}")
        raise ValueError(f"Failed to read Excel file. Error: {str(e)}")  

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
    df7 = pd.read_excel(REFERENCE_XLSX, sheet_name="Z7 TARGET CREATION", header = None, skiprows = 2)
    z7 = {}
    
    for _, row in df7.iterrows():
        sub = _clean_str(row[1]) # Clean habitat name from column B
        if not sub or sub == "SUBHABITAT": # Skip empty or header rows
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
    df8_mults = pd.read_excel(REFERENCE_XLSX, sheet_name="Z8 TARGET ENH", header = None, usecols = "FH:FJ")
    z8_data = {}

    for _, row in df8_mults.iterrows():
        sub = _clean_str(row.iloc[0])

        if not sub or sub in ("SUBHABITAT", "STARTCONDITION", "#ERROR!", "NAN", "HABITAT"):
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
    enh_rows = [] 

    for _, row in enh_df.iterrows():
        if len(row) >= 2:
            baseline_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            post_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            baseline = _clean_str(baseline_raw)
            post_con = _clean_str(post_raw)

            if baseline and post_con:
                enh_possible.add((baseline, post_con))
                
                # Get baseline habitat name
                baseline_hab_raw = baseline_raw.rsplit("/", 1)[0].strip() if "/" in baseline_raw else baseline_raw
                
                # Look up baseline ecosystem
                eco_entry = lookups['z1'].get(_clean_str(baseline_hab_raw), {})
                ecosystem = eco_entry.get("ecosystem", "TERRESTRIAL")
                
                enh_rows.append({
                    "Ecosystem": ecosystem, 
                        "Baseline Habitat / Condition": baseline_raw,
                        "Post Habitat / Condition": post_raw,
                })
    
    lookups["enh_possible"] = enh_possible
    lookups["enh_rows"] = enh_rows

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
        log.warning(f"'{post_hab}' missing from Z7. Defaulting multiplier to 1.0")

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
        log.warning(f"'{post_hab}' missing from Z8. Defaulting multiplier to 1.0")

    z8_entry = lookups["z8_data"].get(hab_clean, {}) 
    
    # Change defaults from 0.0 to 1.0
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
    
    # Z1 entries for pre and post habitats
    pre_z1 = lookups["z1"].get(_clean_str(pre_hab), {})
    post_z1 = lookups ["z1"].get(_clean_str(post_hab), {})
    
    pre_ecosystem = pre_z1.get("ecosystem", "TERRESTRIAL") if pre_hab else ""
    post_ecosystem = post_z1.get("ecosystem", "TERRESTRIAL") if post_hab else ""
    # For backward compatibility internally if ever needed
    ecosystem = post_ecosystem if post_ecosystem else pre_ecosystem
    
    # Calculate baseline units (use pre_area)
    base_units, base_dist_score, base_cond_score = calculate_baseline_units(
        pre_area, pre_hab, pre_con, lookups
    )
    base_dist_category = pre_z1.get("category", "")

    # Post-development calculations
    post_units = 0.0
    time_to_target = "N/A"
    mult = 1.0
    difficulty = ""
    
    # Post distinctiveness/condition (defaults from Z1 lookup; overridden below for CREATED/ENHANCED)
    post_dist_score = post_z1.get("score", 0.0)
    post_dist_category = post_z1.get("category", "")
    post_cond_score = lookups["z3"].get(_clean_str(post_con), 0.0)
    
    # Calculate post-development units based on status
    if post_stat == "RETAINED":  # Same habitat, same condition
        post_units, _, _ = calculate_baseline_units(post_area, pre_hab, pre_con, lookups)
        time_to_target = "0"  # Already at target
    
    elif post_stat == "CREATED":  # New habitat
        post_units, _, _, _, time_to_target = calculate_creation_units(
            post_area, post_hab, post_con, lookups
        )
        difficulty = lookups["z7"].get(_clean_str(post_hab), {}).get("difficulty", "")
    
    elif post_stat == "ENHANCED":  # Improved condition
            post_units, p_dist, p_cond, mult, time_to_target = calculate_enhancement_units(
                post_area, pre_hab, pre_con, post_hab, post_con, lookups
            )
            difficulty = lookups["z8_data"].get(_clean_str(post_hab), {}).get("difficulty", "")
    
    else:  # LOSS or unknown
        post_units = 0.0
        time_to_target = "N/A"
    
    # ── Trading warnings ──────────────────────────────────────────────────────
    pre_trading_req = pre_z1.get("trading_requirement", "")
    post_trading_req = post_z1.get("trading_requirement", "")
    trading_warning = ""

    if pre_hab and post_stat not in ("RETAINED",):
        post_is_unknown = bool(post_hab) and _clean_str(post_hab) not in lookups["z1"]
        post_label = f" → '{post_hab}' (unrecognised habitat)" if post_is_unknown else (f" → '{post_hab}'" if post_hab else " → [LOSS]")

        if "Irreplaceable" in pre_trading_req:
            trading_warning = f"{pre_hab}{post_label}: {pre_trading_req}"

        elif "Like-for-like" in pre_trading_req:
            if _clean_str(pre_hab) != _clean_str(post_hab):
                trading_warning = f"{pre_hab}{post_label}: {pre_trading_req}"

        elif "Same broad habitat" in pre_trading_req:
            pre_broad = pre_z1.get("broad_habitat", "")
            post_broad = post_z1.get("broad_habitat", "")
            pre_score = pre_z1.get("score", 0.0)
            if post_broad != pre_broad and post_dist_score < pre_score:
                trading_warning = f"{pre_hab}{post_label}: {pre_trading_req}"

        elif "Replace habitat with low" in pre_trading_req:
            # Requires post distinctiveness >= Low (score >= 2.0)
            if post_dist_score < 2.0:
                trading_warning = f"{pre_hab}{post_label}: {pre_trading_req}"
    
    # Return results
    return {
        "pre_ecosystem": pre_ecosystem,
        "post_ecosystem": post_ecosystem,
        "ecosystem": ecosystem,
        "status": post_stat,
        # Baseline fields
        "base_dist_score": round(base_dist_score, 4),
        "base_cond_score": round(base_cond_score, 4),
        "base_dist_category": base_dist_category,
        "baseline_units": base_units,
        # Post-development fields
        "post_dist_score": round(post_dist_score, 4),
        "post_cond_score": round(post_cond_score, 4),
        "post_dist_category": post_dist_category,
        "post_units": post_units,
        "net_change": post_units - base_units,
        "time_to_target": time_to_target,
        "mult": mult,
        "difficulty": difficulty,
        # Trading info
        "pre_trading_req": pre_trading_req,
        "post_trading_req": post_trading_req,
        "trading_warning": trading_warning,
    }


### EXCEL EXPORT

def export_to_excel(results, metadata, output_path, lookups=None, global_warnings=None):
    if not results:
        raise ValueError("No overlapping areas found to calculate")

    global_warnings = global_warnings or []

    # ── Ecosystem summary ─────────────────────────────────────────────────
    summary = {
        "TERRESTRIAL": {"base_units": 0.0, "post_units": 0.0},
        "FRESHWATER":  {"base_units": 0.0, "post_units": 0.0},
        "MARINE":      {"base_units": 0.0, "post_units": 0.0},
    }

    for row in results:
        # Base units tracked under pre_ecosystem
        pre_eco = row.get("pre_ecosystem", "").upper()
        if pre_eco:
            if pre_eco not in summary:
                pre_eco = "TERRESTRIAL"
            if row.get("pre_hab"):
                summary[pre_eco]["base_units"] += row.get("baseline_units", 0.0)

        # Post units tracked under post_ecosystem
        post_eco = row.get("post_ecosystem", "").upper()
        if post_eco:
            if post_eco not in summary:
                post_eco = "TERRESTRIAL"
            if row.get("post_hab"):
                summary[post_eco]["post_units"] += row.get("post_units", 0.0)

    for eco in summary.values():
        eco["net_change"] = eco["post_units"] - eco["base_units"]
        eco["net_pct"] = (
            eco["net_change"] / eco["base_units"] * 100
            if eco["base_units"] > 0 else 0.0
        )

    total_base = sum(s["base_units"] for s in summary.values())
    total_post = sum(s["post_units"] for s in summary.values())
    total_net = total_post - total_base
    total_pct = (total_net / total_base * 100) if total_base > 0 else 0.0

    date_str = metadata.get("date") or datetime.date.today().isoformat()

    # ── Metadata ──────────────────────────────────────────────────────────
    meta_data = [
        {"Field": "PROJECT NAME:", "Value": metadata.get("project_name", "")},
        {"Field": "PROJECT STAGE:", "Value": metadata.get("project_stage", "")},
        {"Field": "ASSESSOR:", "Value": metadata.get("assessor", "")},
        {"Field": "REVIEWER:", "Value": metadata.get("reviewer", "")},
        {"Field": "DATE OF ASSESSMENT:", "Value": date_str},
    ]
    df_meta = pd.DataFrame(meta_data)

    # ── Ecosystem summary table ────────────────────────────────────────────
    summary_data = []
    for eco in ["TERRESTRIAL", "FRESHWATER", "MARINE"]:
        summary_data.append({
            "Ecosystem": eco,
            "Baseline Units": round(summary[eco]["base_units"], 1),
            "Post Development Units": round(summary[eco]["post_units"], 1),
            "Net Change": round(summary[eco]["net_change"], 1),
            "Net % Change": f"{summary[eco]['net_pct']:.1f}%",
        })
    summary_data.append({
        "Ecosystem": "TOTAL",
        "Baseline Units": round(total_base, 1),
        "Post Development Units": round(total_post, 1),
        "Net Change": round(total_net, 1),
        "Net % Change": f"{total_pct:.1f}%",
    })
    df_summary = pd.DataFrame(summary_data)

    # ── Warnings table ────────────────────────────────────────────────────
    if global_warnings:
        df_warnings = pd.DataFrame(global_warnings, columns=["Warning Type", "Details"])
    else:
        df_warnings = pd.DataFrame([{"Warning Type": "None", "Details": "No warnings."}])

    # ── Baseline sheet ────────────────────────────────────────────────────
    baseline_rows = []
    for r in results:
        if not r.get("pre_hab"):
            continue
        status = r.get("status", "")
        area = r.get("pre_area", 0.0)
        bu = r.get("baseline_units", 0.0)
        is_lost = status in ("LOSS", "CREATED")
        baseline_rows.append({
            "Ecosystem": r.get("pre_ecosystem", ""),
            "Baseline Habitat Type": r.get("pre_hab", ""),
            "Area (ha)": area,
            "Distinctiveness Category": r.get("base_dist_category", ""),
            "Distinctiveness Score": r.get("base_dist_score", 0.0),
            "Condition": r.get("pre_con", ""),
            "Condition Score": r.get("base_cond_score", 0.0),
            "Baseline Units": bu,
            "Area Retained (ha)": area if status == "RETAINED" else 0.0,
            "Baseline Units Retained": bu if status == "RETAINED" else 0.0,
            "Area Enhanced (ha)": area if status == "ENHANCED" else 0.0,
            "Baseline Units Enhanced": bu if status == "ENHANCED" else 0.0,
            "Area Lost (ha)": area if is_lost else 0.0,
            "Units Lost": bu if is_lost else 0.0,
        })

    col_order_base = ["Ecosystem", "Baseline Habitat Type", "Area (ha)",
                      "Distinctiveness Category", "Distinctiveness Score", "Condition",
                      "Condition Score", "Baseline Units",
                      "Area Retained (ha)", "Baseline Units Retained",
                      "Area Enhanced (ha)", "Baseline Units Enhanced",
                      "Area Lost (ha)", "Units Lost"]

    if baseline_rows:
        df_baseline = pd.DataFrame(baseline_rows)
        group_cols = ["Ecosystem", "Baseline Habitat Type", "Distinctiveness Category",
                      "Distinctiveness Score", "Condition", "Condition Score"]
        df_baseline = df_baseline.groupby(group_cols, dropna=False, as_index=False).sum()[col_order_base]
        df_baseline["Notes"] = df_baseline["Area (ha)"].apply(
            lambda x: f"<0.5 sqm (actual: {x:.6f} ha)" if round(x, 4) == 0.0 else ""
        )
        for c in ["Area (ha)", "Baseline Units", "Area Retained (ha)", "Baseline Units Retained",
                  "Area Enhanced (ha)", "Baseline Units Enhanced", "Area Lost (ha)", "Units Lost"]:
            df_baseline[c] = df_baseline[c].round(4)
    else:
        df_baseline = pd.DataFrame(columns=col_order_base + ["Notes"])

    # ── Created sheet ──────────────────────────────────────────────────────
    created_rows = []
    for r in results:
        if r.get("status") != "CREATED" or not r.get("post_hab"):
            continue
        created_rows.append({
            "Ecosystem": r.get("post_ecosystem", ""),
            "Pre-habitat Type": r.get("pre_hab", ""),
            "Proposed Habitat": r.get("post_hab", ""),
            "Area (ha)": r.get("post_area", 0.0),
            "Distinctiveness Category": r.get("post_dist_category", ""),
            "Distinctiveness Score": r.get("post_dist_score", 0.0),
            "Condition": r.get("post_con", ""),
            "Condition Score": r.get("post_cond_score", 0.0),
            "Time to Target (Years)": r.get("time_to_target", ""),
            "Difficulty of Creation": r.get("difficulty", ""),
            "Difficulty Multiplier": r.get("mult", 1.0),
            "Units Delivered": r.get("post_units", 0.0),
            "Trading Warning": r.get("trading_warning", ""),
        })

    col_order_created = ["Ecosystem", "Pre-habitat Type", "Proposed Habitat", "Area (ha)",
                         "Distinctiveness Category", "Distinctiveness Score", "Condition",
                         "Condition Score", "Time to Target (Years)", "Difficulty of Creation",
                         "Difficulty Multiplier", "Units Delivered", "Trading Warning"]

    if created_rows:
        df_created = pd.DataFrame(created_rows)
        group_cols = ["Ecosystem", "Pre-habitat Type", "Proposed Habitat", "Distinctiveness Category",
                      "Distinctiveness Score", "Condition", "Condition Score",
                      "Time to Target (Years)", "Difficulty of Creation", "Difficulty Multiplier", "Trading Warning"]
        df_created = df_created.groupby(group_cols, dropna=False, as_index=False).sum()[col_order_created]
        df_created["Notes"] = df_created["Area (ha)"].apply(
            lambda x: f"<0.5 sqm (actual: {x:.6f} ha)" if round(x, 4) == 0.0 else ""
        )
        for c in ["Area (ha)", "Units Delivered"]:
            df_created[c] = df_created[c].round(4)
    else:
        df_created = pd.DataFrame(columns=col_order_created + ["Notes"])

    # ── Enhanced sheet ─────────────────────────────────────────────────────
    enhanced_rows = []
    for r in results:
        if r.get("status") != "ENHANCED":
            continue
        base_dist = r.get("base_dist_score", 0.0)
        base_cond = r.get("base_cond_score", 0.0)
        post_dist = r.get("post_dist_score", 0.0)
        post_cond = r.get("post_cond_score", 0.0)
        enhanced_rows.append({
            "Ecosystem": r.get("post_ecosystem", ""),
            "Baseline Habitat": r.get("pre_hab", ""),
            "Baseline Distinctiveness Score": base_dist,
            "Baseline Condition Score": base_cond,
            "Proposed Habitat": r.get("post_hab", ""),
            "Change in Distinctiveness Score": round(post_dist - base_dist, 4),
            "Change in Condition Score": round(post_cond - base_cond, 4),
            "Area (ha)": r.get("post_area", 0.0),
            "Post Distinctiveness Category": r.get("post_dist_category", ""),
            "Post Distinctiveness Score": post_dist,
            "Post Condition": r.get("post_con", ""),
            "Post Condition Score": post_cond,
            "Time to Target (Years)": r.get("time_to_target", ""),
            "Difficulty Multiplier": r.get("mult", 1.0),
            "Units Delivered": r.get("post_units", 0.0),
            "Trading Warning": r.get("trading_warning", ""),
        })
        
    col_order_enhanced = ["Ecosystem", "Baseline Habitat", "Baseline Distinctiveness Score",
                          "Baseline Condition Score", "Proposed Habitat",
                          "Change in Distinctiveness Score", "Change in Condition Score",
                          "Area (ha)", "Post Distinctiveness Category", "Post Distinctiveness Score",
                          "Post Condition", "Post Condition Score", "Time to Target (Years)",
                          "Difficulty Multiplier", "Units Delivered", "Trading Warning"]

    if enhanced_rows:
        df_enhanced = pd.DataFrame(enhanced_rows)
        group_cols = ["Ecosystem", "Baseline Habitat", "Baseline Distinctiveness Score",
                      "Baseline Condition Score", "Proposed Habitat",
                      "Change in Distinctiveness Score", "Change in Condition Score",
                      "Post Distinctiveness Category", "Post Distinctiveness Score",
                      "Post Condition", "Post Condition Score", "Time to Target (Years)",
                      "Difficulty Multiplier", "Trading Warning"]
        df_enhanced = df_enhanced.groupby(group_cols, dropna=False, as_index=False).sum()[col_order_enhanced]
        df_enhanced["Notes"] = df_enhanced["Area (ha)"].apply(
            lambda x: f"<0.5 sqm (actual: {x:.6f} ha)" if round(x, 4) == 0.0 else ""
        )
        for c in ["Area (ha)", "Units Delivered"]:
            df_enhanced[c] = df_enhanced[c].round(4)
    else:
        df_enhanced = pd.DataFrame(columns=col_order_enhanced + ["Notes"])

    # ── Acceptable Conversions sheet ───────────────────────────────────────
    # All valid enhancement pathways from ENH POSSIBILITY, labelled by ecosystem.
    if lookups and lookups.get("enh_rows"):
        df_conversions = pd.DataFrame(lookups["enh_rows"])
        eco_order = {"MARINE": 0, "FRESHWATER": 1, "TERRESTRIAL": 2}
        df_conversions["_sort"] = df_conversions["Ecosystem"].map(
            lambda e: eco_order.get(e.upper(), 3)
        )
        df_conversions = (df_conversions.sort_values("_sort")
                          .drop(columns=["_sort"])
                          .reset_index(drop=True))
        df_conversions.index = df_conversions.index + 1
    else:
        df_conversions = pd.DataFrame(
            columns=["Ecosystem", "Baseline Habitat / Condition", "Post Habitat / Condition"]
        )

    # ── Write Excel ───────────────────────────────────────────────────────
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:

        # Summary sheet: metadata, unit summary, then warnings
        df_meta.to_excel(writer, sheet_name='Summary', index=False, header=False, startrow=0)
        next_row = len(df_meta) + 2
        df_summary.to_excel(writer, sheet_name='Summary', index=False, startrow=next_row)
        next_row += len(df_summary) + 3

        # Warnings header label
        pd.DataFrame([["WARNINGS"]], columns=[""]).to_excel(
            writer, sheet_name='Summary', index=False, header=False, startrow=next_row
        )
        df_warnings.to_excel(writer, sheet_name='Summary', index=False, startrow=next_row + 1)

        # Habitat detail sheets (terrestrial, freshwater and marine grouped together)
        df_baseline.to_excel(writer, sheet_name='Baseline', index=False)
        df_created.to_excel(writer, sheet_name='Created', index=False)
        df_enhanced.to_excel(writer, sheet_name='Enhanced', index=False)

        # Acceptable habitat conversions reference sheet
        df_conversions.to_excel(writer, sheet_name='Acceptable Conversions',
                                index=True, index_label="#")

        # Auto-fit column widths across all sheets
        for sheet in writer.sheets.values():
            for col_cells in sheet.columns:
                max_len = 0
                col_letter = col_cells[0].column_letter
                for cell in col_cells:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                sheet.column_dimensions[col_letter].width = min(max_len + 4, 60)

    log.info(f"Excel report saved to: {output_path}")