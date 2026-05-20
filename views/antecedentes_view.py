"""
AntecedentesView — Vista del modo Antecedentes.
Muestra miniaturas con marcas de corte, controles de rango, serial inicial y exportación.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QProgressBar, QFrame, QScrollArea,
    QFileDialog, QMessageBox, QSizePolicy, QCheckBox, QToolTip,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

import numpy as np
from views.thumbnail_strip import ThumbnailStrip, ThumbnailItem


class GroupPreviewItem(QFrame):
    """Representa visualmente un grupo de páginas."""

    def __init__(self, group_num: int, page_indices: list[int], serial_label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("groupItem")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        icon = QLabel("📄")
        icon.setFixedWidth(24)
        layout.addWidget(icon)

        num_label = QLabel(f"Grupo {group_num}")
        num_label.setObjectName("groupNum")
        num_label.setFixedWidth(70)
        layout.addWidget(num_label)

        pages_label = QLabel(
            f"Páginas: {', '.join(str(i + 1) for i in page_indices)}"
        )
        pages_label.setObjectName("groupPages")
        layout.addWidget(pages_label, 1)

        serial_label_w = QLabel(f"→ {serial_label}.pdf")
        serial_label_w.setObjectName("groupSerial")
        serial_label_w.setAlignment(Qt.AlignRight)
        layout.addWidget(serial_label_w)


class AntecedentesView(QWidget):
    """
    Vista Antecedentes.

    Signals
    -------
    cut_toggle_requested(int)       — toggle punto de corte en página
    export_requested(dict)          — exportar; dict con folder, serial_inicial, desde, hasta
    clear_cuts_requested()          — limpiar todos los cortes
    """

    cut_toggle_requested = Signal(int)
    export_requested = Signal(dict)
    clear_cuts_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_count = 0
        self._groups: list[list[int]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Encabezado ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Antecedentes")
        title.setObjectName("viewTitle")
        header.addWidget(title)
        header.addStretch()

        self.btn_clear_cuts = QPushButton("Limpiar cortes")
        self.btn_clear_cuts.clicked.connect(self.clear_cuts_requested)
        header.addWidget(self.btn_clear_cuts)

        root.addLayout(header)

        # ── Descripción ───────────────────────────────────────────────────────
        desc = QLabel(
            "Haz clic derecho en una miniatura y selecciona 'Marcar como punto de corte' "
            "para indicar dónde comienza cada nuevo registro. "
            "Cada grupo de páginas se exportará como un PDF numerado secuencialmente."
        )
        desc.setWordWrap(True)
        desc.setObjectName("descLabel")
        root.addWidget(desc)

        # ── Tira de miniaturas ────────────────────────────────────────────────
        strip_box = QGroupBox("Páginas escaneadas — clic derecho para marcar puntos de corte")
        strip_layout = QVBoxLayout(strip_box)
        strip_layout.setContentsMargins(4, 4, 4, 4)

        self.strip = ThumbnailStrip(Qt.Horizontal)
        self.strip.cut_toggled.connect(self.cut_toggle_requested)
        self.strip.setFixedHeight(ThumbnailItem.THUMB_SIZE + 90)
        strip_layout.addWidget(self.strip)

        root.addWidget(strip_box)

        # ── Parámetros de exportación ─────────────────────────────────────────
        params_layout = QHBoxLayout()

        # Rango de páginas
        range_box = QGroupBox("Rango de páginas (opcional)")
        range_layout = QHBoxLayout(range_box)

        self.chk_range = QCheckBox("Activar rango")
        self.chk_range.stateChanged.connect(self._on_range_toggled)
        range_layout.addWidget(self.chk_range)

        range_layout.addWidget(QLabel("Desde:"))
        self.spin_desde = QSpinBox()
        self.spin_desde.setRange(1, 9999)
        self.spin_desde.setValue(1)
        self.spin_desde.setEnabled(False)
        self.spin_desde.setFixedWidth(70)
        range_layout.addWidget(self.spin_desde)

        range_layout.addWidget(QLabel("Hasta:"))
        self.spin_hasta = QSpinBox()
        self.spin_hasta.setRange(1, 9999)
        self.spin_hasta.setValue(1)
        self.spin_hasta.setEnabled(False)
        self.spin_hasta.setFixedWidth(70)
        range_layout.addWidget(self.spin_hasta)

        params_layout.addWidget(range_box)

        # Serial inicial
        serial_box = QGroupBox("Numeración de salida")
        serial_layout = QHBoxLayout(serial_box)

        serial_layout.addWidget(QLabel("Serial inicial:"))
        self.spin_serial = QSpinBox()
        self.spin_serial.setRange(1, 999999)
        self.spin_serial.setValue(1)
        self.spin_serial.setFixedWidth(90)
        serial_layout.addWidget(self.spin_serial)

        serial_layout.addWidget(QLabel("Dígitos:"))
        self.spin_padding = QSpinBox()
        self.spin_padding.setRange(1, 10)
        self.spin_padding.setValue(5)
        self.spin_padding.setFixedWidth(60)
        serial_layout.addWidget(self.spin_padding)

        self._preview_label = QLabel("Ej: 00001.pdf")
        self._preview_label.setObjectName("previewLabel")
        serial_layout.addWidget(self._preview_label)

        self.spin_serial.valueChanged.connect(self._update_serial_preview)
        self.spin_padding.valueChanged.connect(self._update_serial_preview)

        params_layout.addWidget(serial_box)

        root.addLayout(params_layout)

        # ── Vista previa de grupos ────────────────────────────────────────────
        groups_box = QGroupBox("Vista previa de grupos")
        groups_layout = QVBoxLayout(groups_box)

        self.groups_scroll = QScrollArea()
        self.groups_scroll.setWidgetResizable(True)
        self.groups_scroll.setFixedHeight(140)
        self._groups_container = QWidget()
        self._groups_inner = QVBoxLayout(self._groups_container)
        self._groups_inner.setContentsMargins(4, 4, 4, 4)
        self._groups_inner.setSpacing(4)
        self._groups_inner.addStretch()
        self.groups_scroll.setWidget(self._groups_container)
        groups_layout.addWidget(self.groups_scroll)

        self.groups_count_label = QLabel("0 grupos definidos")
        self.groups_count_label.setObjectName("summaryLabel")
        groups_layout.addWidget(self.groups_count_label)

        root.addWidget(groups_box)

        # ── Barra de progreso ─────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        root.addWidget(self.progress_bar)

        # ── Exportación ───────────────────────────────────────────────────────
        export_layout = QHBoxLayout()

        export_layout.addWidget(QLabel("Carpeta de destino:"))
        from PySide6.QtWidgets import QLineEdit
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Selecciona una carpeta…")
        export_layout.addWidget(self.folder_edit)

        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(36)
        btn_browse.clicked.connect(self._browse_folder)
        export_layout.addWidget(btn_browse)

        self.btn_export = QPushButton("💾  Generar ZIP")
        self.btn_export.setObjectName("primaryBtn")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setFixedWidth(140)
        self.btn_export.clicked.connect(self._request_export)
        export_layout.addWidget(self.btn_export)

        root.addLayout(export_layout)

    # ── API pública ───────────────────────────────────────────────────────────

    def add_page(self, index: int, image: np.ndarray):
        self.strip.add_page(index, image)
        self._page_count += 1
        self.spin_hasta.setMaximum(self._page_count)
        self.spin_hasta.setValue(self._page_count)

    def update_groups(self, groups: list[list[int]]):
        """Recibe lista de grupos (cada grupo es lista de índices de página)."""
        self._groups = groups
        self._rebuild_groups_preview()
        self.groups_count_label.setText(f"{len(groups)} grupo(s) definido(s)")

    def set_cut_point_visual(self, index: int, is_cut: bool):
        self.strip.set_cut_point(index, is_cut)

    def show_progress(self, current: int, total: int):
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        if current >= total:
            self.progress_bar.setVisible(False)

    def export_started(self):
        self.btn_export.setEnabled(False)
        self.btn_export.setText("Generando…")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

    def export_finished(self, zip_path: str):
        self.btn_export.setEnabled(True)
        self.btn_export.setText("💾  Generar ZIP")
        self.progress_bar.setVisible(False)
        QMessageBox.information(
            self,
            "Exportación completada",
            f"ZIP generado exitosamente:\n{zip_path}",
        )

    def export_error(self, msg: str):
        self.btn_export.setEnabled(True)
        self.btn_export.setText("💾  Generar ZIP")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error al exportar", msg)

    def clear(self):
        self.strip.clear()
        self._page_count = 0
        self._groups = []
        self._rebuild_groups_preview()
        self.groups_count_label.setText("0 grupos definidos")

    # ── Internos ──────────────────────────────────────────────────────────────

    def _on_range_toggled(self, state: int):
        enabled = state == Qt.Checked
        self.spin_desde.setEnabled(enabled)
        self.spin_hasta.setEnabled(enabled)

    def _update_serial_preview(self):
        val = self.spin_serial.value()
        pad = self.spin_padding.value()
        preview = str(val).zfill(pad) + ".pdf"
        self._preview_label.setText(f"Ej: {preview}")

    def _rebuild_groups_preview(self):
        # Limpiar
        while self._groups_inner.count() > 1:
            item = self._groups_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        serial_ini = self.spin_serial.value()
        pad = self.spin_padding.value()

        for i, group in enumerate(self._groups):
            serial_label = str(serial_ini + i).zfill(pad)
            item_widget = GroupPreviewItem(i + 1, group, serial_label)
            self._groups_inner.insertWidget(self._groups_inner.count() - 1, item_widget)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
        if folder:
            self.folder_edit.setText(folder)

    def _request_export(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Carpeta requerida", "Por favor selecciona una carpeta de destino.")
            return

        params = {
            "folder": folder,
            "serial_inicial": self.spin_serial.value(),
            "serial_padding": self.spin_padding.value(),
            "desde": self.spin_desde.value() if self.chk_range.isChecked() else None,
            "hasta": self.spin_hasta.value() if self.chk_range.isChecked() else None,
        }
        self.export_requested.emit(params)
