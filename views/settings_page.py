"""Página de configuración."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QCheckBox, QLineEdit, QFileDialog,
    QFormLayout, QFrame, QScrollArea, QKeySequenceEdit,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence

from models.config_model import ConfigModel
from views.theme import SURFACE, SUCCESS


class SettingsPage(QWidget):
    settings_saved = Signal()

    def __init__(self, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._cfg = config
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(50)
        # Selector por id: una regla sin selector se propaga a los hijos y pisa
        # la hoja global, dejando el botón "Guardar" sin relleno ni borde.
        header.setObjectName("settingsHeader")
        header.setStyleSheet(f"#settingsHeader {{ background:{SURFACE}; border:none; }}")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Configuración")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")
        btn_save = QPushButton("Guardar")
        btn_save.setProperty("primary", True)
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._save)
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(btn_save)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        container = QWidget()
        cv = QVBoxLayout(container)
        cv.setContentsMargins(24, 20, 24, 20)
        cv.setSpacing(16)

        cv.addWidget(self._import_group())
        cv.addWidget(self._correction_group())
        cv.addWidget(self._ocr_group())
        cv.addWidget(self._output_group())
        cv.addWidget(self._ant_group())
        cv.addWidget(self._visualization_group())
        cv.addWidget(self._shortcuts_group())
        cv.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)

        self._banner = QLabel("Configuración guardada")
        self._banner.setAlignment(Qt.AlignCenter)
        self._banner.setFixedHeight(30)
        self._banner.setStyleSheet(
            f"background:{SURFACE}; color:{SUCCESS}; border:none; font-size:9pt;")
        self._banner.setVisible(False)
        root.addWidget(self._banner)

    def _correction_group(self) -> QGroupBox:
        box = QGroupBox("Corrección")
        f = QFormLayout(box)
        self._auto_persp = QCheckBox("Corregir perspectiva automáticamente")
        f.addRow("", self._auto_persp)
        self._auto_rot = QCheckBox("Corregir rotación automáticamente")
        f.addRow("", self._auto_rot)
        return box

    def _import_group(self) -> QGroupBox:
        box = QGroupBox("Importaci\u00f3n")
        f = QFormLayout(box)
        self._import_dpi = QSpinBox(); self._import_dpi.setRange(72, 600); self._import_dpi.setSuffix(" DPI"); self._import_dpi.setFixedWidth(100)
        f.addRow("DPI de PDFs importados:", self._import_dpi)
        return box

    def _ocr_group(self) -> QGroupBox:
        box = QGroupBox("OCR")
        f = QFormLayout(box)
        self._margin = QSpinBox(); self._margin.setRange(5, 40); self._margin.setSuffix(" %"); self._margin.setFixedWidth(80)
        f.addRow("Ancho margen derecho:", self._margin)
        self._conf = QSpinBox(); self._conf.setRange(0, 100); self._conf.setSuffix(" %"); self._conf.setFixedWidth(80)
        f.addRow("Umbral de confianza:", self._conf)
        self._gpu = QCheckBox("Usar GPU (requiere CUDA)")
        f.addRow("", self._gpu)
        self._parallel = QSpinBox(); self._parallel.setRange(1, 16); self._parallel.setFixedWidth(80)
        f.addRow("Trabajos en paralelo:", self._parallel)
        return box

    def _output_group(self) -> QGroupBox:
        box = QGroupBox("Salida")
        f = QFormLayout(box)
        row = QHBoxLayout()
        self._out_folder = QLineEdit(); self._out_folder.setPlaceholderText("Carpeta por defecto…")
        btn = QPushButton("Examinar"); btn.setFixedHeight(32)
        btn.clicked.connect(lambda: self._browse(self._out_folder))
        row.addWidget(self._out_folder); row.addWidget(btn)
        f.addRow("Carpeta de destino:", row)
        self._pdf_dpi = QSpinBox(); self._pdf_dpi.setRange(72, 600); self._pdf_dpi.setSuffix(" DPI"); self._pdf_dpi.setFixedWidth(100)
        f.addRow("DPI de PDFs:", self._pdf_dpi)
        return box

    def _ant_group(self) -> QGroupBox:
        box = QGroupBox("Antecedentes")
        f = QFormLayout(box)
        self._serial_ini = QSpinBox(); self._serial_ini.setRange(1, 999999); self._serial_ini.setFixedWidth(100)
        f.addRow("Serial inicial:", self._serial_ini)
        self._padding = QSpinBox(); self._padding.setRange(1, 10); self._padding.setFixedWidth(80)
        f.addRow("Dígitos del serial:", self._padding)
        return box

    def _visualization_group(self) -> QGroupBox:
        box = QGroupBox("Visualización")
        f = QFormLayout(box)
        row = QHBoxLayout()
        self._viz_root = QLineEdit(); self._viz_root.setPlaceholderText("Carpeta raíz de Registros Civiles…")
        btn = QPushButton("Examinar"); btn.setFixedHeight(32)
        btn.clicked.connect(lambda: self._browse(self._viz_root))
        row.addWidget(self._viz_root); row.addWidget(btn)
        f.addRow("Carpeta raíz:", row)
        return box

    def _shortcuts_group(self) -> QGroupBox:
        box = QGroupBox("Atajos de teclado")
        f = QFormLayout(box)
        self._shortcut_import_pdf = QKeySequenceEdit()
        self._shortcut_import_pdf.setFixedWidth(220)
        f.addRow("Importar PDF:", self._shortcut_import_pdf)
        self._shortcut_scan = QKeySequenceEdit()
        self._shortcut_scan.setFixedWidth(220)
        f.addRow("Escanear:", self._shortcut_scan)
        return box

    def _load(self):
        c = self._cfg
        self._import_dpi.setValue(c.get("import", "pdf_dpi", 300))
        self._auto_persp.setChecked(c.get("correction", "auto_perspective", True))
        self._auto_rot.setChecked(c.get("correction", "auto_rotation", True))
        self._margin.setValue(int(c.get("ocr", "margin_right_pct", 0.15) * 100))
        self._conf.setValue(int(c.get("ocr", "confidence_threshold", 0.4) * 100))
        self._gpu.setChecked(c.get("ocr", "gpu", False))
        self._parallel.setValue(c.get("ocr", "parallel_workers", 4))
        self._out_folder.setText(c.get("output", "default_folder", ""))
        self._pdf_dpi.setValue(c.get("output", "pdf_dpi", 200))
        self._serial_ini.setValue(c.get("antecedentes", "serial_inicial", 1))
        self._padding.setValue(c.get("antecedentes", "serial_padding", 5))
        self._viz_root.setText(c.get("visualization", "root_folder", ""))
        self._shortcut_import_pdf.setKeySequence(QKeySequence(c.get("shortcuts", "import_pdf", "Ctrl+P")))
        self._shortcut_scan.setKeySequence(QKeySequence(c.get("shortcuts", "scan", "Ctrl+K")))

    def _save(self):
        c = self._cfg
        c.set("import",       "pdf_dpi",               self._import_dpi.value())
        c.set("correction",   "auto_perspective",      self._auto_persp.isChecked())
        c.set("correction",   "auto_rotation",         self._auto_rot.isChecked())
        c.set("ocr",          "margin_right_pct",      self._margin.value() / 100)
        c.set("ocr",          "confidence_threshold",  self._conf.value() / 100)
        c.set("ocr",          "gpu",                   self._gpu.isChecked())
        c.set("ocr",          "parallel_workers",      self._parallel.value())
        c.set("output",       "default_folder",        self._out_folder.text().strip())
        c.set("output",       "pdf_dpi",               self._pdf_dpi.value())
        c.set("antecedentes", "serial_inicial",        self._serial_ini.value())
        c.set("antecedentes", "serial_padding",        self._padding.value())
        c.set("visualization", "root_folder",          self._viz_root.text().strip())
        c.set("shortcuts",    "import_pdf",              self._shortcut_import_pdf.keySequence().toString())
        c.set("shortcuts",    "scan",                    self._shortcut_scan.keySequence().toString())
        c.save()
        self._banner.setVisible(True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: self._banner.setVisible(False))
        self.settings_saved.emit()

    def _browse(self, field: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            field.setText(folder)
