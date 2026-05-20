"""Página de Antecedentes."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QCheckBox, QFrame, QLineEdit,
    QFileDialog, QMessageBox, QSplitter, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal

from views.widgets import ThumbnailGrid
from views.theme import SURFACE, TEXT_DIM, ACCENT, TEXT_SEC, DANGER


class AntecedentesPage(QWidget):
    cut_toggle_requested = Signal(int)
    clear_cuts_requested = Signal()
    export_requested     = Signal(dict)
    fullscreen_requested = Signal(int)
    page_deleted         = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(f"background:{SURFACE}; border:none;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(10)

        title = QLabel("Antecedentes")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")
        self._groups_lbl = QLabel("0 grupos")
        self._groups_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")

        self._btn_expand = QPushButton("Ampliar")
        self._btn_expand.setFixedHeight(32)
        self._btn_expand.clicked.connect(self._toggle_expand)

        btn_clear = QPushButton("Limpiar cortes")
        btn_clear.setFixedHeight(32)
        btn_clear.clicked.connect(self.clear_cuts_requested)

        hl.addWidget(title)
        hl.addWidget(self._groups_lbl)
        hl.addStretch()
        hl.addWidget(self._btn_expand)
        hl.addWidget(btn_clear)
        root.addWidget(header)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(1)

        self.grid = ThumbnailGrid()
        self.grid.cut_toggled.connect(self.cut_toggle_requested)
        self.grid.page_deleted.connect(self.page_deleted)
        self.grid.fullscreen_requested.connect(self.fullscreen_requested)
        self._splitter.addWidget(self.grid)

        self._right_panel = self._build_right_panel()
        self._splitter.addWidget(self._right_panel)
        self._splitter.setSizes([800, 300])

        root.addWidget(self._splitter)

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(260)
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(12)

        grp_box = QGroupBox("Grupos")
        gb_lay = QVBoxLayout(grp_box)
        self._groups_list = QListWidget()
        self._groups_list.setFixedHeight(140)
        gb_lay.addWidget(self._groups_list)
        v.addWidget(grp_box)

        num_box = QGroupBox("Numeración")
        nl = QVBoxLayout(num_box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Serial inicial:"))
        self._spin_serial = QSpinBox()
        self._spin_serial.setRange(1, 999999)
        self._spin_serial.setValue(1)
        self._spin_serial.setFixedWidth(90)
        self._spin_serial.valueChanged.connect(self._refresh_groups)
        row1.addWidget(self._spin_serial)
        nl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Dígitos:"))
        self._spin_pad = QSpinBox()
        self._spin_pad.setRange(1, 10)
        self._spin_pad.setValue(5)
        self._spin_pad.setFixedWidth(60)
        self._spin_pad.valueChanged.connect(self._refresh_groups)
        row2.addWidget(self._spin_pad)
        row2.addStretch()
        self._preview_lbl = QLabel("Ej: 00001.pdf")
        self._preview_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        row2.addWidget(self._preview_lbl)
        nl.addLayout(row2)
        v.addWidget(num_box)

        rng_box = QGroupBox("Rango (opcional)")
        rl = QVBoxLayout(rng_box)
        self._chk_range = QCheckBox("Activar rango")
        self._chk_range.stateChanged.connect(self._toggle_range)
        rl.addWidget(self._chk_range)

        rng_row = QHBoxLayout()
        rng_row.addWidget(QLabel("Desde:"))
        self._spin_desde = QSpinBox()
        self._spin_desde.setRange(1, 9999)
        self._spin_desde.setEnabled(False)
        self._spin_desde.setFixedWidth(65)
        rng_row.addWidget(self._spin_desde)
        rng_row.addWidget(QLabel("Hasta:"))
        self._spin_hasta = QSpinBox()
        self._spin_hasta.setRange(1, 9999)
        self._spin_hasta.setValue(100)
        self._spin_hasta.setEnabled(False)
        self._spin_hasta.setFixedWidth(65)
        rng_row.addWidget(self._spin_hasta)
        rl.addLayout(rng_row)
        v.addWidget(rng_box)

        exp_box = QGroupBox("Exportar")
        el = QVBoxLayout(exp_box)

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Carpeta de destino…")
        btn_browse = QPushButton("Examinar")
        btn_browse.setFixedHeight(32)
        btn_browse.setToolTip("Seleccionar carpeta")
        btn_browse.clicked.connect(self._browse)
        folder_row.addWidget(self._folder_edit)
        folder_row.addWidget(btn_browse)
        el.addLayout(folder_row)

        self._btn_export = QPushButton("  Generar ZIP")
        self._btn_export.setProperty("primary", True)
        self._btn_export.setFixedHeight(34)
        self._btn_export.clicked.connect(self._do_export)
        el.addWidget(self._btn_export)
        v.addWidget(exp_box)

        v.addStretch()
        return panel

    def add_page(self, index: int, image):
        self.grid.add_page(index, image)
        self._spin_hasta.setMaximum(index + 2)

    def update_page(self, index: int, image):
        self.grid.update_image(index, image)

    def set_cut(self, index: int, is_cut: bool):
        self.grid.set_cut(index, is_cut)

    def remove_page(self, index: int):
        self.grid.remove_page(index)

    def update_groups(self, groups: list[list[int]]):
        self._groups_list.clear()
        serial  = self._spin_serial.value()
        padding = self._spin_pad.value()
        for i, group in enumerate(groups):
            label = f"Grupo {i+1}  [{len(group)} pág.]  → {str(serial+i).zfill(padding)}.pdf"
            self._groups_list.addItem(QListWidgetItem(label))
        self._groups_lbl.setText(f"{len(groups)} grupo(s)")
        self._preview_lbl.setText(f"Ej: {str(serial).zfill(padding)}.pdf")

    def export_started(self):
        self._btn_export.setEnabled(False)
        self._btn_export.setText("Generando…")

    def export_finished(self, path: str):
        self._btn_export.setEnabled(True)
        self._btn_export.setText("  Generar ZIP")
        QMessageBox.information(self, "Exportación completada",
                                f"ZIP generado:\n{path}")

    def export_error(self, msg: str):
        self._btn_export.setEnabled(True)
        self._btn_export.setText("  Generar ZIP")
        QMessageBox.critical(self, "Error al exportar", msg)

    def clear(self):
        self.grid.clear_all()
        self._groups_list.clear()
        self._groups_lbl.setText("0 grupos")

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._right_panel.setVisible(not self._expanded)
        self._btn_expand.setText("Compactar" if self._expanded else "Ampliar")

    def _toggle_range(self, state: int):
        enabled = state == Qt.Checked
        self._spin_desde.setEnabled(enabled)
        self._spin_hasta.setEnabled(enabled)

    def _refresh_groups(self):
        serial  = self._spin_serial.value()
        padding = self._spin_pad.value()
        self._preview_lbl.setText(f"Ej: {str(serial).zfill(padding)}.pdf")

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if folder:
            self._folder_edit.setText(folder)

    def _do_export(self):
        folder = self._folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Carpeta requerida",
                                "Selecciona una carpeta de destino.")
            return
        params = {
            "folder":     folder,
            "serial_ini": self._spin_serial.value(),
            "padding":    self._spin_pad.value(),
            "desde":      self._spin_desde.value() if self._chk_range.isChecked() else 0,
            "hasta":      self._spin_hasta.value() if self._chk_range.isChecked() else 0,
        }
        self.export_requested.emit(params)
