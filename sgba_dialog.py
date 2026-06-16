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
        
        # -- Metadata Input --
        form_layout = QFormLayout()
        
        self.proj_name_input = QLineEdit(self)
        form_layout.addRow("Project Name:", self.proj_name_input)
        
        self.proj_stage_input = QLineEdit(self)
        form_layout.addRow("Project Stage:", self.proj_stage_input)
        
        self.assessor_input = QLineEdit(self)
        form_layout.addRow("Assessor:", self.assessor_input)
        
        self.reviewer_input = QLineEdit(self)
        form_layout.addRow("Reviewer:", self.reviewer_input)
        
        self.date_input = QLineEdit(self)
        self.date_input.setText(QDate.currentDate().toString("dd MMM yyyy"))
        form_layout.addRow("Date of Assessment:", self.date_input)
        
        layout.addLayout(form_layout)
        
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
            "project_name": self.proj_name_input.text(),
            "project_stage": self.proj_stage_input.text(),
            "assessor": self.assessor_input.text(),
            "reviewer": self.reviewer_input.text(),
            "date": self.date_input.text()
        }
        