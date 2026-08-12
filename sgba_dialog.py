from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QFormLayout, QLineEdit
from qgis.gui import QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt.QtCore import QDate

class SGBADialog(QDialog):
    def __init__(self, parent=None):
        super(SGBADialog, self).__init__(parent)
        self.setWindowTitle("Singapore Biodiversity Accounting Calculator")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # -- Layer Dropdown ──
        layer_form = QFormLayout()
        
        self.baseline_combo = QgsMapLayerComboBox(self)
        self.baseline_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layer_form.addRow("Baseline Layer:", self.baseline_combo)
        
        self.post_combo = QgsMapLayerComboBox(self)
        self.post_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layer_form.addRow("Post-development Layer:", self.post_combo)
        
        layout.addLayout(layer_form)
        
        # ── OK / Cancel Buttons ──
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Ok).setText("Run Calculation")
        layout.addWidget(self.button_box)

    def get_baseline_layer(self):
        return self.baseline_combo.currentLayer()
        
    def get_post_layer(self):
        return self.post_combo.currentLayer()
        
    def get_metadata(self):
        return{
            "project_name": "",
            "project_stage": "",
            "assessor": "",
            "reviewer": "",
            "date": QDate.currentDate().toString("dd MMM yyyy")
        }
        