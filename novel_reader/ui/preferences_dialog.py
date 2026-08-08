from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QDoubleSpinBox,
    QSpinBox, QVBoxLayout
)

class PreferencesDialog(QDialog):
    def __init__(self, *, font_size=20, content_width=760, line_height=1.72,
                 ascii_enabled=True, ascii_width=38, ascii_height=18, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferências de leitura")
        layout = QVBoxLayout(self); form = QFormLayout()
        self.font_size = QSpinBox(); self.font_size.setRange(12,40); self.font_size.setValue(font_size)
        self.content_width = QSpinBox(); self.content_width.setRange(480,1200); self.content_width.setSuffix(" px"); self.content_width.setValue(content_width)
        self.line_height = QDoubleSpinBox(); self.line_height.setRange(1.2,2.4); self.line_height.setSingleStep(.1); self.line_height.setValue(line_height)
        self.ascii_enabled = QCheckBox("Mostrar capa ASCII"); self.ascii_enabled.setChecked(ascii_enabled)
        self.ascii_width = QSpinBox(); self.ascii_width.setRange(20,80); self.ascii_width.setValue(ascii_width)
        self.ascii_height = QSpinBox(); self.ascii_height.setRange(8,40); self.ascii_height.setValue(ascii_height)
        form.addRow("Tamanho da fonte", self.font_size)
        form.addRow("Largura da coluna", self.content_width)
        form.addRow("Espaçamento de linha", self.line_height)
        form.addRow("", self.ascii_enabled)
        form.addRow("Largura da capa ASCII", self.ascii_width)
        form.addRow("Altura da capa ASCII", self.ascii_height)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {
            "font_size": self.font_size.value(),
            "content_width": self.content_width.value(),
            "line_height": self.line_height.value(),
            "ascii_enabled": self.ascii_enabled.isChecked(),
            "ascii_width": self.ascii_width.value(),
            "ascii_height": self.ascii_height.value(),
        }
