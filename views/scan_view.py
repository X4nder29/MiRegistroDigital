"""
ScanView — Panel de previsualización del escaneo con controles de corrección.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QSplitter, QFrame,
    QSlider, QSizePolicy, QProgressBar, QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from utils.image_utils import numpy_to_qimage
from views.thumbnail_strip import ThumbnailStrip
from views.theme import TEXT_DIM


# Extensiones reconocidas (para el filtro del diálogo)
_IMG_FILTER = (
    "Imágenes (*.jpg *.jpeg *.png *.tiff *.tif *.bmp *.webp);;"
    "PDF (*.pdf);;"
    "Todos los archivos (*.*)"
)


class ImageViewer(QLabel):
    """Visor de imagen con zoom básico."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setText("Escanea o carga archivos para comenzar")
        self.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px;")
        self._pixmap: QPixmap | None = None

    def set_image(self, image: np.ndarray):
        qimg = numpy_to_qimage(image)
        self._pixmap = QPixmap.fromImage(qimg)
        self._resize_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_pixmap()

    def _resize_pixmap(self):
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.setPixmap(scaled)


class ScanView(QWidget):
    """
    Vista de escaneo/importación.

    Signals
    -------
    scan_requested()                  — usuario presiona "Escanear"
    files_import_requested(list)      — lista de Path para importar
    correction_requested(int)         — aplicar corrección a página
    rotation_changed(int, float)
    reset_correction_requested(int)   — revertir corrección de página
    page_selected(int)
    cut_toggled(int)
    page_deleted(int)
    mode_selected(str)                — "civil" | "antecedentes"
    """

    scan_requested            = Signal()
    files_import_requested    = Signal(list)   # list[Path]
    correction_requested      = Signal(int)
    rotation_changed          = Signal(int, float)
    reset_correction_requested = Signal(int)
    page_selected             = Signal(int)
    cut_toggled               = Signal(int)
    page_deleted              = Signal(int)
    mode_selected             = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_page: int = -1
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar superior ─────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # ── Barra de progreso de importación (oculta por defecto) ────────────
        self.import_progress_bar = QProgressBar()
        self.import_progress_bar.setVisible(False)
        self.import_progress_bar.setFixedHeight(5)
        self.import_progress_bar.setTextVisible(False)
        self.import_progress_bar.setObjectName("importProgressBar")
        root.addWidget(self.import_progress_bar)

        # ── Splitter: tira izq + visor central + panel derecho ───────────────
        splitter = QSplitter(Qt.Horizontal)

        # Tira de miniaturas (vertical, izquierda)
        self.strip = ThumbnailStrip(Qt.Vertical)
        self.strip.page_selected.connect(self._on_page_selected)
        self.strip.cut_toggled.connect(self.cut_toggled)
        self.strip.page_deleted.connect(self.page_deleted)
        splitter.addWidget(self.strip)

        # Visor central
        self.viewer = ImageViewer()
        splitter.addWidget(self.viewer)

        # Panel de corrección (derecha)
        right_panel = self._build_correction_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([180, 700, 220])
        root.addWidget(splitter)

        # ── Barra de estado ───────────────────────────────────────────────────
        status_bar = self._build_status_bar()
        root.addWidget(status_bar)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("scanToolbar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # ── Grupo: escáner ────────────────────────────────────────────────────
        self.btn_scan = QPushButton("▶  Escanear")
        self.btn_scan.setObjectName("primaryBtn")
        self.btn_scan.setFixedHeight(36)
        self.btn_scan.clicked.connect(self.scan_requested)

        self.source_combo = QComboBox()
        self.source_combo.setFixedWidth(200)
        self.source_combo.setToolTip("Fuente TWAIN")

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        self.dpi_spin.setFixedWidth(90)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["Color", "Grises", "B/N"])
        self.color_combo.setFixedWidth(90)

        layout.addWidget(self.btn_scan)
        layout.addWidget(QLabel("Fuente:"))
        layout.addWidget(self.source_combo)
        layout.addWidget(QLabel("DPI:"))
        layout.addWidget(self.dpi_spin)
        layout.addWidget(self.color_combo)

        # ── Separador visual ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setObjectName("navSeparator")
        sep.setFixedWidth(2)
        layout.addWidget(sep)

        # ── Grupo: importar archivos ──────────────────────────────────────────
        self.btn_import_images = QPushButton("🖼  Abrir imágenes")
        self.btn_import_images.setObjectName("importBtn")
        self.btn_import_images.setFixedHeight(36)
        self.btn_import_images.setToolTip(
            "Importar archivos de imagen ya escaneados (JPG, PNG, TIFF, BMP, WEBP)"
        )
        self.btn_import_images.clicked.connect(self._on_import_images_clicked)

        self.btn_import_pdf = QPushButton("📄  Abrir PDF")
        self.btn_import_pdf.setObjectName("importBtn")
        self.btn_import_pdf.setFixedHeight(36)
        self.btn_import_pdf.setToolTip(
            "Importar un PDF multipágina — cada página se convierte en imagen"
        )
        self.btn_import_pdf.clicked.connect(self._on_import_pdf_clicked)

        layout.addWidget(self.btn_import_images)
        layout.addWidget(self.btn_import_pdf)

        layout.addStretch()

        # ── Grupo: modo destino ───────────────────────────────────────────────
        self.btn_civil = QPushButton("Registros Civiles")
        self.btn_civil.setObjectName("modeBtn")
        self.btn_civil.setFixedHeight(36)
        self.btn_civil.clicked.connect(lambda: self.mode_selected.emit("civil"))
        self.btn_ant = QPushButton("Antecedentes")
        self.btn_ant.setObjectName("modeBtn")
        self.btn_ant.setFixedHeight(36)
        self.btn_ant.clicked.connect(lambda: self.mode_selected.emit("antecedentes"))

        layout.addWidget(self.btn_civil)
        layout.addWidget(self.btn_ant)

        return bar

    def _build_correction_panel(self) -> QGroupBox:
        panel = QGroupBox("Corrección")
        panel.setFixedWidth(210)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        self.btn_auto_persp = QPushButton("Auto perspectiva")
        self.btn_auto_persp.setToolTip("Detectar y corregir perspectiva automáticamente")
        self.btn_auto_persp.clicked.connect(
            lambda: self.correction_requested.emit(self._current_page)
        )

        rot_label = QLabel("Rotación manual:")
        self.rotation_slider = QSlider(Qt.Horizontal)
        self.rotation_slider.setRange(-45, 45)
        self.rotation_slider.setValue(0)
        self.rotation_slider.setTickInterval(5)
        self.rotation_slider.setTickPosition(QSlider.TicksBelow)
        self.rot_value_label = QLabel("0°")
        self.rot_value_label.setAlignment(Qt.AlignCenter)
        self.rotation_slider.valueChanged.connect(self._on_rotation_changed)

        self.btn_reset = QPushButton("Restablecer original")
        self.btn_reset.setObjectName("dangerBtn")
        self.btn_reset.clicked.connect(
            lambda: self.reset_correction_requested.emit(self._current_page)
        )

        layout.addWidget(self.btn_auto_persp)
        layout.addSpacing(8)
        layout.addWidget(rot_label)
        layout.addWidget(self.rotation_slider)
        layout.addWidget(self.rot_value_label)
        layout.addSpacing(8)
        layout.addWidget(self.btn_reset)
        layout.addStretch()

        return panel

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(28)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 2, 12, 2)

        self.status_label = QLabel("Sin páginas")
        self.import_status_label = QLabel("")
        self.import_status_label.setObjectName("importStatusLabel")
        self.page_info_label = QLabel("")
        self.page_info_label.setAlignment(Qt.AlignRight)

        layout.addWidget(self.status_label)
        layout.addWidget(self.import_status_label)
        layout.addStretch()
        layout.addWidget(self.page_info_label)

        return bar

    # ── API pública ───────────────────────────────────────────────────────────

    def add_page(self, index: int, image: np.ndarray):
        self.strip.add_page(index, image)
        self.strip.select(index)
        self.viewer.set_image(image)
        self._current_page = index
        self._update_status()

    def update_page_image(self, index: int, image: np.ndarray):
        self.strip.update_page(index, image)
        if index == self._current_page:
            self.viewer.set_image(image)

    def set_serial(self, index: int, serial: str, confidence: float = 0.0):
        self.strip.set_serial(index, serial, confidence)

    def set_sources(self, sources: list[str]):
        self.source_combo.clear()
        self.source_combo.addItems(sources)

    def show_scan_progress(self, scanning: bool):
        self.btn_scan.setEnabled(not scanning)
        self.btn_scan.setText("Escaneando…" if scanning else "▶  Escanear")

    def show_import_progress(self, current: int, total: int):
        """Muestra el progreso de la importación de archivos."""
        if total <= 0:
            self.import_progress_bar.setVisible(False)
            self.import_status_label.setText("")
            return
        self.import_progress_bar.setVisible(True)
        self.import_progress_bar.setMaximum(total)
        self.import_progress_bar.setValue(current)
        self.import_status_label.setText(f"Importando… {current}/{total}")
        if current >= total:
            self.import_progress_bar.setVisible(False)
            self.import_status_label.setText("")

    def show_import_busy(self, busy: bool):
        """Muestra barra indeterminada mientras se calcula el total de páginas."""
        self.btn_import_images.setEnabled(not busy)
        self.btn_import_pdf.setEnabled(not busy)
        if busy:
            self.import_progress_bar.setVisible(True)
            self.import_progress_bar.setRange(0, 0)   # indeterminado
            self.import_status_label.setText("Cargando archivos…")
        else:
            self.import_progress_bar.setRange(0, 1)
            self.import_progress_bar.setVisible(False)
            self.import_status_label.setText("")

    def set_cut_point_visual(self, index: int, is_cut: bool):
        self.strip.set_cut_point(index, is_cut)

    def clear_pages(self):
        self.strip.clear()
        self.viewer.setText("Escanea o carga archivos para comenzar")
        self._current_page = -1
        self._update_status()

    # ── Diálogos de importación ───────────────────────────────────────────────

    def _on_import_images_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar imágenes escaneadas",
            "",
            "Imágenes (*.jpg *.jpeg *.png *.tiff *.tif *.bmp *.webp);;"
            "Todos los archivos (*.*)",
        )
        if paths:
            from pathlib import Path
            self.files_import_requested.emit([Path(p) for p in paths])

    def _on_import_pdf_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar PDF(s) escaneados",
            "",
            "PDF (*.pdf);;Todos los archivos (*.*)",
        )
        if paths:
            from pathlib import Path
            self.files_import_requested.emit([Path(p) for p in paths])

    # ── Internos ──────────────────────────────────────────────────────────────

    def _on_page_selected(self, index: int):
        self._current_page = index
        self.page_selected.emit(index)

    def _on_rotation_changed(self, value: int):
        self.rot_value_label.setText(f"{value}°")
        if self._current_page >= 0:
            self.rotation_changed.emit(self._current_page, float(value))

    def _update_status(self):
        n = len(self.strip._items)
        self.status_label.setText(
            f"{n} página(s)" if n else "Sin páginas"
        )
        if self._current_page >= 0:
            self.page_info_label.setText(f"Página {self._current_page + 1} de {n}")
        else:
            self.page_info_label.setText("")

