'''
QGIS requirement. Puts everything together
'''

import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QFileDialog
from qgis.core import QgsMessageLog, Qgis

# Import UI Dialog
from .sgba_dialog import SGBADialog
from .spatial_ops import execute_pipeline

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer

class SGBAPlugin:
    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        
    def initGui(self):
        self.action = QAction("Run Calculation", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&SGBA Metric", self.action) #Add to QGIS Plugins menu & toolbar 
    
    # Removes the plugin menu item and icon when QGIS is closed
    def unload(self):
        self.iface.removePluginMenu("&SGBA Metric", self.action)
        self.iface.removeToolBarIcon(self.action)
        
    # Write results to pdf file
    def export_to_pdf(self, results, metadata, output_path):
        if not results:
            raise ValueError("No overlapping areas found to calculate")
        
        summary = {
            "TERRESTRIAL": {"base_units": 0.0, "post_units": 0.0},
            "FRESHWATER":  {"base_units": 0.0, "post_units": 0.0},
            "MARINE":      {"base_units": 0.0, "post_units": 0.0}
        }
        
        for row in results:
            eco = row.get("ecosystem", "TERRESTRIAL").upper()
            if eco not in summary:
                eco = "TERRESTRIAL"
            summary[eco]["base_units"] += row.get("baseline_units", 0.0)
            summary[eco]["post_units"] += row.get("post_units", 0.0)
        
        for eco in summary.keys():
            summary[eco]["net_change"] = summary[eco]["post_units"] - summary[eco]["base_units"]
            if summary[eco]["base_units"] > 0:
                summary[eco]["net_pct"] = (summary[eco]["net_change"] / summary[eco]["base_units"]) * 100
            else:
                summary[eco]["net_pct"] = 0.0
        
        total_base = sum(s["base_units"] for s in summary.values())
        total_post = sum(s["post_units"] for s in summary.values())
        total_net = total_post - total_base
        total_pct = (total_net / total_base * 100) if total_base > 0 else 0.0
        
        # Setup PDF
    
        doc = SimpleDocTemplate(output_path, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        meta_data = [
            ["SINGAPORE BIODIVERSITY ACCOUNTING METRIC 1.1", ""],
            ["PROJECT NAME:", metadata.get("project_name", "")],
            ["PROJECT STAGE:", metadata.get("project_stage", "")],
            ["ASSESSOR:", metadata.get("assessor", "")],
            ["REVIEWER:", metadata.get("reviewer", "")],
            ["DATE OF ASSESSMENT:", metadata.get("date", "")]
        ]
        
        meta_table = Table(meta_data, colWidths=[200, 400])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#729f8f")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('SPAN', (0,0), (1,0))
        ]))
        
        elements.append(meta_table)
        elements.append(Spacer(1, 20))
        
        results_data = [
            ["BASELINE", "TERRESTRIAL UNITS", f"{summary['TERRESTRIAL']['base_units']:.2f}", "TOTAL"],
            ["", "FRESHWATER UNITS", f"{summary['FRESHWATER']['base_units']:.2f}", f"{total_base:.2f}"],
            ["", "MARINE UNITS", f"{summary['MARINE']['base_units']:.2f}", ""],
            
            ["POST DEVELOPMENT", "TERRESTRIAL UNITS", f"{summary['TERRESTRIAL']['post_units']:.2f}", "TOTAL"],
            ["", "FRESHWATER UNITS", f"{summary['FRESHWATER']['post_units']:.2f}", f"{total_post:.2f}"],
            ["", "MARINE UNITS", f"{summary['MARINE']['post_units']:.2f}", ""],
            
            ["NET CHANGE", "TERRESTRIAL UNITS", f"{summary['TERRESTRIAL']['net_change']:.2f}", ""],
            ["", "FRESHWATER UNITS", f"{summary['FRESHWATER']['net_change']:.2f}", ""],
            ["", "MARINE UNITS", f"{summary['MARINE']['net_change']:.2f}", ""],
            
            ["NET % CHANGE", "TERRESTRIAL UNITS", f"{summary['TERRESTRIAL']['net_pct']:.2f}%", ""],
            ["", "FRESHWATER UNITS", f"{summary['FRESHWATER']['net_pct']:.2f}%", ""],
            ["", "MARINE UNITS", f"{summary['MARINE']['net_pct']:.2f}%", ""],
            
            ["NET CHANGE - COMBINED", "", f"{total_net:.2f}", ""],
            ["NET % CHANGE - COMBINED", "", f"{total_pct:.2f}%", ""]
        ]

        res_table = Table(results_data, colWidths=[200, 150, 100, 150])
        res_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('SPAN', (0,0), (0,2)),
            ('SPAN', (0,3), (0,5)),
            ('SPAN', (0,6), (0,8)),
            ('SPAN', (0,9), (0,11)),
            ('SPAN', (0,12), (1,12)),
            ('SPAN', (0,13), (1,13)),
        ]))
        
        elements.append(res_table)
        
        doc.build(elements)
    
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
                QMessageBox.warning(self.iface.mainWindow(), "Error", "Please select both a baseline and post-construction layer.")
                return
            
            # Ask user where to save final csv report
            save_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                "Save SGBA Results As",
                os.path.expanduser("~"),
                "PDF Files(*.pdf)"
            )
            if not save_path:
                return
                
            try: 
                self.iface.messageBar().pushMessage("SGBA", "Running...", level=Qgis.Info, duration=3)
                final_dataset = execute_pipeline(baseline_shp, post_shp)
                self.export_to_pdf(final_dataset, metadata, save_path)
                self.iface.messageBar().pushMessage("SGBA", f"Success! Results saved to {save_path}", level=Qgis.Success, duration=5)
                
            except ValueError as ve:
                QMessageBox.critical(self.iface.mainWindow(), "Validation Error", str(ve))
                
            except Exception as e:
                QgsMessageLog.logMessage(f"SGBA Plugin Error: {str(e)}", 'SGBA', level=Qgis.Critical)
                QMessageBox.critical(self.iface.mainWindow(), "Unexpected Error", f"An error occurred:\n{str(e)}")