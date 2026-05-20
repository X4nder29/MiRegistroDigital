"""
SettingsView — Panel de configuración de la aplicación.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QComboBox, QCheckBox, QLineEdit,
    QFileDialog, QFormLayout, QFrame, QScrollArea, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from models.config_model import ConfigModel


class SettingsView(QWidget):
    """
    Vista de configuración.

    Signals
    -------
    settings_saved()   — el usuario guardó los cambios
    """

    settings_saved = Signal()

    def __init__(self, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._config = config
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(16)

        title = QLabel("Configuración")
        title.setObjectName("viewTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(16)

        c_layout.addWidget(self._build_scanner_group())
        c_layout.addWidget(self._build_correction_group())
        c_layout.addWidget(self._build_ocr_group())
        c_layout.addWidget(self._build_output_group())
        c_layout.addWidget(self._build_ant_group())
        c_layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)

        # Botones de acción
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_reset = QPushButton("Restablecer valores por defecto")
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_reset)

        btn_save = QPushButton("Guardar")
        btn_save.setObjectName("primaryBtn")
        btn_save.setFixedWidth(100)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        root.addLayout(btn_row)

    # ── Grupos ────────────────────────────────────────────────────────────────

    def _build_scanner_group(self) -> QGroupBox:
        box = QGroupBox("Escáner")
        form = QFormLayout(box)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setSuffix(" DPI")
        form.addRow("Resolución por defecto:", self.dpi_spin)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["color", "gray", "bw"])
        form.addRow("Modo de color:", self.color_combo)

        self.feeder_chk = QCheckBox("Usar alimentador automático (ADF)")
        form.addRow("", self.feeder_chk)

        return box

    def _build_correction_group(self) -> QGroupBox:
        box = QGroupBox("Corrección automática")
        form = QFormLayout(box)

        self.auto_persp_chk = QCheckBox("Corregir perspectiva automáticamente")
        form.addRow("", self.auto_persp_chk)

        self.auto_rot_chk = QCheckBox("Corregir rotación (deskew) automáticamente")
        form.addRow("", self.auto_rot_chk)

        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 10)
        self.margin_spin.setSuffix(" %")
        form.addRow("Recorte de bordes tras corrección:", self.margin_spin)

        return box

    def _build_ocr_group(self) -> QGroupBox:
        box = QGroupBox("OCR")
        form = QFormLayout(box)

        self.margin_ocr_spin = QSpinBox()
        self.margin_ocr_spin.setRange(5, 40)
        self.margin_ocr_spin.setSuffix(" %")
        form.addRow("Ancho del margen derecho para OCR:", self.margin_ocr_spin)

        self.conf_spin = QSpinBox()
        self.conf_spin.setRange(0, 100)
        self.conf_spin.setSuffix(" %")
        form.addRow("Umbral de confianza mínima:", self.conf_spin)

        self.gpu_chk = QCheckBox("Usar GPU (requiere CUDA)")
        form.addRow("", self.gpu_chk)

        return box

    def _build_output_group(self) -> QGroupBox:
        box = QGroupBox("Salida")
        form = QFormLayout(box)

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(32)
        btn_browse.clicked.connect(self._browse_output_folder)
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(btn_browse)
        form.addRow("Carpeta de destino por defecto:", folder_row)

        self.pdf_dpi_spin = QSpinBox()
        self.pdf_dpi_spin.setRange(72, 600)
        self.pdf_dpi_spin.setSuffix(" DPI")
        form.addRow("DPI de los PDFs generados:", self.pdf_dpi_spin)

        return box

    def _build_ant_group(self) -> QGroupBox:
        box = QGroupBox("Antecedentes — valores por defecto")
        form = QFormLayout(box)

        self.serial_ini_spin = QSpinBox()
        self.serial_ini_spin.setRange(1, 999999)
        form.addRow("Serial inicial:", self.serial_ini_spin)

        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(1, 10)
        form.addRow("Dígitos del serial (relleno ceros):", self.padding_spin)

        return box

    # ── Carga / Guardado ──────────────────────────────────────────────────────

    def _load_values(self):
        cfg = self._config
        self.dpi_spin.setValue(cfg.get("scanner", "dpi", 300))
        idx = self.color_combo.findText(cfg.get("scanner", "color_mode", "color"))
        self.color_combo.setCurrentIndex(max(0, idx))
        self.feeder_chk.setChecked(cfg.get("scanner", "auto_feeder", False))

        self.auto_persp_chk.setChecked(cfg.get("correction", "auto_perspective", True))
        self.auto_rot_chk.setChecked(cfg.get("correction", "auto_rotation", True))
        self.margin_spin.setValue(int(cfg.get("correction", "margin_crop_pct", 0.02) * 100))

        self.margin_ocr_spin.setValue(int(cfg.get("ocr", "margin_right_pct", 0.15) * 100))
        self.conf_spin.setValue(int(cfg.get("ocr", "confidence_threshold", 0.4) * 100))
        self.gpu_chk.setChecked(cfg.get("ocr", "gpu", False))

        self.folder_edit.setText(cfg.get("output", "default_folder", ""))
        self.pdf_dpi_spin.setValue(cfg.get("output", "pdf_dpi", 200))

        self.serial_ini_spin.setValue(cfg.get("antecedentes", "serial_inicial", 1))
        self.padding_spin.setValue(cfg.get("antecedentes", "serial_padding", 5))

    def _save(self):
        cfg = self._config
        cfg.set("scanner", "dpi", self.dpi_spin.value())
        cfg.set("scanner", "color_mode", self.color_combo.currentText())
        cfg.set("scanner", "auto_feeder", self.feeder_chk.isChecked())

        cfg.set("correction", "auto_perspective", self.auto_persp_chk.isChecked())
        cfg.set("correction", "auto_rotation", self.auto_rot_chk.isChecked())
        cfg.set("correction", "margin_crop_pct", self.margin_spin.value() / 100)

        cfg.set("ocr", "margin_right_pct", self.margin_ocr_spin.value() / 100)
        cfg.set("ocr", "confidence_threshold", self.conf_spin.value() / 100)
        cfg.set("ocr", "gpu", self.gpu_chk.isChecked())

        cfg.set("output", "default_folder", self.folder_edit.text().strip())
        cfg.set("output", "pdf_dpi", self.pdf_dpi_spin.value())

        cfg.set("antecedentes", "serial_inicial", self.serial_ini_spin.value())
        cfg.set("antecedentes", "serial_padding", self.padding_spin.value())

        cfg.save()
        self.settings_saved.emit()

    def _reset(self):
        reply = QMessageBox.question(
            self, "Restablecer",
            "¿Restablecer todos los valores a los valores por defecto?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._config.reset_to_defaults()
            self._load_values()

    def _browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de destino por defecto")
        if folder:
            self.folder_edit.setText(folder)
