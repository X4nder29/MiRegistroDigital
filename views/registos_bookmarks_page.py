"""Sub-sección: PDF con marcadores por serial OCR."""
from __future__ import annotations
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QFrame, QLineEdit, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from views.theme import SURFACE, TEXT_DIM, SUCCESS

logger = logging.getLogger("docscan.registos_bookmarks")


class RegistosBookmarksPage(QWidget):
    export_requested = Signal(list, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages_data: list[dict] = []
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

        title = QLabel("PDF con marcadores")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")
        hl.addWidget(title)
        hl.addStretch()

        root.addWidget(header)

        desc = QLabel(
            "Genera un único PDF con todas las páginas escaneadas. "
            "Cada página tendrá un marcador (bookmark) con su serial OCR."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none; padding:4px 24px 4px 24px;")
        root.addWidget(desc)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Página", "Serial OCR", "Estado"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 70)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        root.addWidget(self._table, 1)

        bottom = QFrame()
        bottom.setFixedHeight(56)
        bottom.setStyleSheet(f"background:{SURFACE}; border:none;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(24, 0, 24, 0)
        bl.setSpacing(8)

        self._summary = QLabel("0 páginas")
        self._summary.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")

        self._prog = QProgressBar()
        self._prog.setFixedHeight(3)
        self._prog.setTextVisible(False)
        self._prog.setVisible(False)
        self._prog.setFixedWidth(150)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Carpeta de destino…")
        self._folder_edit.setMinimumWidth(160)

        btn_browse = QPushButton("Examinar")
        btn_browse.setFixedHeight(32)
        btn_browse.clicked.connect(self._browse)

        self._btn_export = QPushButton("  Generar PDF con marcadores")
        self._btn_export.setProperty("primary", True)
        self._btn_export.setFixedHeight(34)
        self._btn_export.clicked.connect(self._do_export)

        bl.addWidget(self._summary)
        bl.addWidget(self._prog)
        bl.addStretch()
        bl.addWidget(QLabel("Destino:"))
        bl.addWidget(self._folder_edit)
        bl.addWidget(btn_browse)
        bl.addWidget(self._btn_export)
        root.addWidget(bottom)

    def set_pages_data(self, pages_data: list[dict]):
        self._pages_data = pages_data
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for i, item in enumerate(pages_data):
            row = self._table.rowCount()
            self._table.insertRow(row)
            n = QTableWidgetItem(str(i + 1))
            n.setTextAlignment(Qt.AlignCenter)
            n.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            s = QTableWidgetItem(item["label"])
            s.setTextAlignment(Qt.AlignCenter)
            s.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            e = QTableWidgetItem("Listo")
            e.setTextAlignment(Qt.AlignCenter)
            e.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            e.setForeground(QColor(SUCCESS))
            self._table.setItem(row, 0, n)
            self._table.setItem(row, 1, s)
            self._table.setItem(row, 2, e)
        self._table.blockSignals(False)
        self._summary.setText(f"{len(pages_data)} páginas")

    def set_ocr_result(self, page_index: int, serial: str, conf: float):
        for i, item in enumerate(self._pages_data):
            if item.get("index") == page_index:
                item["label"] = serial or f"pagina_{page_index + 1:04d}"
                break
        self._refresh_table()

    def _refresh_table(self):
        self.set_pages_data(self._pages_data)

    def export_started(self):
        self._btn_export.setEnabled(False)
        self._btn_export.setText("Generando…")
        self._prog.setRange(0, 0)
        self._prog.setVisible(True)

    def export_finished(self, path: str):
        self._btn_export.setEnabled(True)
        self._btn_export.setText("  Generar PDF con marcadores")
        self._prog.setVisible(False)

    def export_error(self, msg: str):
        self._btn_export.setEnabled(True)
        self._btn_export.setText("  Generar PDF con marcadores")
        self._prog.setVisible(False)

    def show_progress(self, current: int, total: int):
        self._prog.setVisible(True)
        self._prog.setRange(0, total)
        self._prog.setValue(current)
        if current >= total:
            self._prog.setVisible(False)

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
        if not self._pages_data:
            QMessageBox.warning(self, "Sin datos",
                                "No hay páginas para exportar.")
            return
        self.export_requested.emit(self._pages_data, folder, 300)
