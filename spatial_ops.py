import processing
from qgis.core import QgsProject, QgsDistanceArea, QgsField, QgsVectorLayer, QgsFeature
from qgis.PyQt.QtCore import QVariant

# Import lookups and math from calculations
from .calculations import load_lookups, process_polygon_feature

# Ensure that all input shapefiles are in SVY21 
def validate_crs(layer):
    crs_auth_id = layer.crs().authid().upper()
    return crs_auth_id == 'EPSG:3414'
    
# Convert multipart polygons to singlepart to ensure no double-counting of area
def run_multipart_to_singlepart(layer):
    params = {
        'INPUT': layer,
        'OUTPUT': 'memory:Singlepart_Temp'
    }
    result = processing.run("native:multiparttosingleparts", params)
    return result['OUTPUT']

# Union baseline and post-construction habitat layers & return temp layer
def run_union(baseline_shp, post_shp):
    params = {
        'INPUT': baseline_shp,
        'OVERLAY': post_shp,
        'OUTPUT': 'memory:SGBA_Union_Temp'
    } 
    result = processing.run("native:union", params)
    union = result['OUTPUT']
    return union
    
# Extract attribute from QGIS feature. If field is NULL or missing then return empty string.
def get_safe_attributes(feature, field_name):
    try:
        val = feature[field_name]
        if not (isinstance(val, QVariant) and val.isNull()):
            return str(val).strip()
    except KeyError:
        pass

    for field in feature.fields():
        if field.name().lower() == field_name.lower():
            val = feature[field.name()]
            if not (isinstance(val, QVariant) and val.isNull()):
                return str(val).strip()
    return ""

def create_combined_fields(union_layer):
    union_layer.startEditing()
    field_pre = QgsField("pre_hab_con", QVariant.String, len=255)
    field_post = QgsField("post_hab_con", QVariant.String, len=255)
    union_layer.addAttribute(field_pre)
    union_layer.addAttribute(field_post)
    union_layer.commitChanges()
    
    union_layer.startEditing()
    idx_pre_hab_con = union_layer.fields().indexFromName("pre_hab_con")
    idx_post_hab_con = union_layer.fields().indexFromName("post_hab_con")

    for feat in union_layer.getFeatures():
        fid = feat.id()
        
        # Use our new bulletproof function to extract the data
        pre_hab_str = get_safe_attributes(feat, "pre_hab").upper()
        pre_con_str = get_safe_attributes(feat, "pre_con").upper()
        post_hab_str = get_safe_attributes(feat, "post_hab").upper()
        post_con_str = get_safe_attributes(feat, "post_con").upper()

        if pre_hab_str and pre_con_str:
            pre_combined = f"{pre_hab_str}/{pre_con_str}"
        else:
            pre_combined = ""  
        
        if post_hab_str and post_con_str:
            post_combined = f"{post_hab_str}/{post_con_str}"
        else:
            post_combined = ""

        union_layer.changeAttributeValue(fid, idx_pre_hab_con, pre_combined)
        union_layer.changeAttributeValue(fid, idx_post_hab_con, post_combined)

    union_layer.commitChanges()
    return union_layer
        
# Interate through intersected polygons, calculate areas & extract EIA attributes. Pipe to calculations.py
def process_union(union, lookups):
    calc = QgsDistanceArea()
    calc.setSourceCrs(union.crs(), QgsProject.instance().transformContext())
    calc.setEllipsoid(QgsProject.instance().ellipsoid())
    
    final_dataset = []
    
    for feat in union.getFeatures():
        geom = feat.geometry()
        if geom is None or geom.isEmpty() or calc.measureArea(geom) < 0.1:
            continue
        
        area_ha = calc.measureArea(geom) / 10000.0
        
        feature_dict = {
            'pre_area': area_ha,
            'pre_hab': get_safe_attributes(feat, 'pre_hab'),
            'pre_con': get_safe_attributes(feat, 'pre_con'),
            'post_area': area_ha,
            'post_hab': get_safe_attributes(feat, 'post_hab'),
            'post_con': get_safe_attributes(feat, 'post_con'),
        }
        
        math_results = process_polygon_feature(feature_dict, lookups)
        
        combined_row = {**feature_dict, **math_results}
        final_dataset.append(combined_row)
        
    return final_dataset
    
# Master function that does the entire process
def execute_pipeline(baseline_shp, post_shp):
    # Ensure correct CRS
    if not validate_crs(baseline_shp):
        raise ValueError("Baseline layer is NOT in SVY21")
    if not validate_crs(post_shp):
        raise ValueError("Post-construction layer is NOT in SVY21")
    
    # Multipart to singlepart
    baseline_single = run_multipart_to_singlepart(baseline_shp)
    post_single = run_multipart_to_singlepart(post_shp)
        
    # Load lookup tables
    lookups = load_lookups()
    
    # Run Union
    union = run_union(baseline_single, post_single)
    union_single = run_multipart_to_singlepart(union) #to singlepart
    union_with_fields = create_combined_fields(union_single) #add combined fields
    final_results = process_union(union_with_fields, lookups)
    
    return final_results
        