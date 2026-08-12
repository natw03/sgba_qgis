'''
QGIS requirement. Puts everything together
'''

import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QFileDialog
from qgis.core import QgsMessageLog, Qgis, QgsDistanceArea, QgsProject
 
# Import UI Dialog
from .sgba_dialog import SGBADialog
from .spatial_ops import execute_pipeline, get_safe_attributes
from .calculations import load_lookups, _clean_str, export_to_excel

class SGBAPlugin:
    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None

    def initGui(self):
        self.action = QAction("Run Calculation", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&SGBA Metric", self.action)

    # Removes the plugin menu item and icon when QGIS is closed
    def unload(self):
        self.iface.removePluginMenu("&SGBA Metric", self.action)
        self.iface.removeToolBarIcon(self.action)

    # Runs plugin when button is clicked
    def run(self):
        # Initialise and show UI dialog
        dialog = SGBADialog(self.iface.mainWindow())

        # Wait for user to select layers and click Run
        if dialog.exec_():
            baseline_shp = dialog.get_baseline_layer()
            post_shp = dialog.get_post_layer()
            metadata = dialog.get_metadata()

            if not baseline_shp or not post_shp:
                QMessageBox.warning(self.iface.mainWindow(), "Error",
                                    "Please select both a baseline and post-construction layer.")
                return

            global_warnings = []

            # --- START VALIDATIONS ---
            calc = QgsDistanceArea()
            calc.setSourceCrs(baseline_shp.crs(), QgsProject.instance().transformContext())
            calc.setEllipsoid(QgsProject.instance().ellipsoid())

            #Calculate total baseline area
            base_area = sum(
                calc.measureArea(f.geometry())
                for f in baseline_shp.getFeatures()
                if f.geometry() and not f.geometry().isEmpty()
            ) / 10000.0
            
            #Calculate total post-construction area
            calc.setSourceCrs(post_shp.crs(), QgsProject.instance().transformContext())
            post_area = sum(
                calc.measureArea(f.geometry())
                for f in post_shp.getFeatures()
                if f.geometry() and not f.geometry().isEmpty()
            ) / 10000.0
            
            #Check if baseline area = post-construction area
            if abs(base_area - post_area) > 0.01:
                msg = (f"Total area of baseline ({base_area:.2f} ha) does not equal "
                       f"total area of post-construction ({post_area:.2f} ha).")
                reply = QMessageBox.warning(
                    self.iface.mainWindow(), "Area Mismatch",
                    f"{msg}\n\nDo you want to continue anyway?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
                global_warnings.append(("Area Mismatch", msg))

            #Check if there are any invalid habitats
            try:
                lookups = load_lookups()
            except Exception as e:
                QMessageBox.critical(self.iface.mainWindow(), "Error", str(e))
                return

            valid_habs = set(lookups["z1"].keys())
            invalid_habs = set()

            for f in baseline_shp.getFeatures():
                h = get_safe_attributes(f, "pre_hab")
                ch = _clean_str(h)
                if ch and ch not in valid_habs:
                    invalid_habs.add(h)

            for f in post_shp.getFeatures():
                h = get_safe_attributes(f, "post_hab")
                ch = _clean_str(h)
                if ch and ch not in valid_habs:
                    invalid_habs.add(h)

            if invalid_habs:
                reply = QMessageBox.warning(
                    self.iface.mainWindow(), "Unrecognized Habitats",
                    f"The following habitat types are not in the SGBA Reference Excel sheet:"
                    f"\n\n{', '.join(sorted(invalid_habs))}"
                    f"\n\nThey will be calculated with a 0 distinctiveness score. Continue?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
                for hab in sorted(invalid_habs):
                    global_warnings.append(
                        ("Unknown Habitat",
                         f'Unrecognized habitat not found in reference data: "{hab}"')
                    )
            # --- END VALIDATIONS ---

            # Ask user where to save final excel report
            save_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                "Save SGBA Results As",
                os.path.expanduser("~"),
                "Excel Files(*.xlsx)"
            )
            if not save_path:
                return

            try:
                self.iface.messageBar().pushMessage("SGBA", "Running...",
                                                    level=Qgis.Info, duration=3)

                # execute_pipeline now returns (results, lookups)
                final_dataset, lookups = execute_pipeline(baseline_shp, post_shp)

                # Collect trading warnings from results
                seen = set()
                for r in final_dataset:
                    w = r.get("trading_warning", "")
                    if w and w not in seen:
                        seen.add(w)
                        global_warnings.append(("Habitat Trading", w))

                export_to_excel(final_dataset, metadata, save_path,
                                lookups=lookups, global_warnings=global_warnings)

                self.iface.messageBar().pushMessage(
                    "SGBA", f"Success! Results saved to {save_path}",
                    level=Qgis.Success, duration=5
                )
                QgsMessageLog.logMessage("updated", "SGBA", level=Qgis.Info)

            except ValueError as ve:
                QMessageBox.critical(self.iface.mainWindow(), "Validation Error", str(ve))

            except Exception as e:
                QgsMessageLog.logMessage(f"SGBA Plugin Error: {str(e)}", 'SGBA',
                                         level=Qgis.Critical)
                QMessageBox.critical(self.iface.mainWindow(), "Unexpected Error",
                                     f"An error occurred:\n{str(e)}")
