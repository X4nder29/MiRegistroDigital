"""Sub-sección: Unir PDFs con marcadores por nombre de archivo."""
from __future__ import annotations
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QProgressBar, QFrame,
    QLineEdit, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from views.theme import SURFACE, TEXT_DIM, TEXT_SEC

logger = logging.getLogger("docscan.registos_merge")


class RegistosMergePage(QWidget):
    merge_requested = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf_paths: list[Path] = []
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

        title = QLabel("Unir PDFs")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")
        hl.addWidget(title)
        hl.addStretch()

        root.addWidget(header)

        desc = QLabel(
            "Selecciona una carpeta con archivos PDF para unirlos en un solo documento. "
            "Cada PDF original aparecerá como un marcador (bookmark) en el PDF resultante."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none; padding:4px 24px 4px 24px;")
        root.addWidget(desc)

        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(24, 8, 24, 8)

        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Ruta de la carpeta con PDFs…")
        self._folder_edit.textChanged.connect(self._on_folder_changed)

        btn_browse = QPushButton("Examinar")
        btn_browse.setFixedHeight(32)
        btn_browse.clicked.connect(self._browse)

        folder_row.addWidget(QLabel("Carpeta:"))
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(btn_browse)
        root.addLayout(folder_row)

        list_label = QLabel("PDFs encontrados:")
        list_label.setStyleSheet(f"color:{TEXT_SEC}; font-size:9pt; border:none; padding:4px 24px 0 24px;")
        root.addWidget(list_label)

        self._pdf_list = QListWidget()
        self._pdf_list.setAlternatingRowColors(True)
        root.addWidget(self._pdf_list, 1)

        bottom = QFrame()
        bottom.setFixedHeight(56)
        bottom.setStyleSheet(f"background:{SURFACE}; border:none;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(24, 0, 24, 0)
        bl.setSpacing(8)

        self._summary = QLabel("0 archivos")
        self._summary.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")

        self._prog = QProgressBar()
        self._prog.setFixedHeight(3)
        self._prog.setTextVisible(False)
        self._prog.setVisible(False)
        self._prog.setFixedWidth(150)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Nombre del PDF de salida…")
        self._output_edit.setMinimumWidth(180)
        self._output_edit.setText("unificado.pdf")

        self._btn_merge = QPushButton("  Unir PDFs")
        self._btn_merge.setProperty("primary", True)
        self._btn_merge.setFixedHeight(34)
        self._btn_merge.setEnabled(False)
        self._btn_merge.clicked.connect(self._do_merge)

        bl.addWidget(self._summary)
        bl.addWidget(self._prog)
        bl.addStretch()
        bl.addWidget(QLabel("Salida:"))
        bl.addWidget(self._output_edit)
        bl.addWidget(self._btn_merge)
        root.addWidget(bottom)

    def _on_folder_changed(self, folder: str):
        self._pdf_paths.clear()
        self._pdf_list.clear()
        folder_path = Path(folder)
        if not folder_path.is_dir():
            self._summary.setText("0 archivos")
            self._btn_merge.setEnabled(False)
            return
        pdfs = sorted(folder_path.glob("*.pdf"))
        self._pdf_paths = pdfs
        for pdf in pdfs:
            item = QListWidgetItem(f"{pdf.name}  ({pdf.stat().st_size / 1024:.0f} KB)")
            item.setToolTip(str(pdf))
            self._pdf_list.addItem(item)
        self._summary.setText(f"{len(pdfs)} archivo(s)")
        self._btn_merge.setEnabled(len(pdfs) > 0)

    def merge_started(self):
        self._btn_merge.setEnabled(False)
        self._btn_merge.setText("Uniendo…")
        self._prog.setRange(0, 0)
        self._prog.setVisible(True)

    def merge_finished(self, path: str):
        self._btn_merge.setEnabled(True)
        self._btn_merge.setText("  Unir PDFs")
        self._prog.setVisible(False)

    def merge_error(self, msg: str):
        self._btn_merge.setEnabled(True)
        self._btn_merge.setText("  Unir PDFs")
        self._prog.setVisible(False)

    def show_progress(self, current: int, total: int):
        self._prog.setVisible(True)
        self._prog.setRange(0, total)
        self._prog.setValue(current)
        if current >= total:
            self._prog.setVisible(False)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta con PDFs")
        if folder:
            self._folder_edit.setText(folder)

    def _do_merge(self):
        if not self._pdf_paths:
            QMessageBox.warning(self, "Sin archivos",
                                "No hay PDFs en la carpeta seleccionada.")
            return
        output_name = self._output_edit.text().strip()
        if not output_name:
            output_name = "unificado.pdf"
        if not output_name.lower().endswith(".pdf"):
            output_name += ".pdf"
        output_path = str(Path(self._folder_edit.text().strip()) / output_name)
        self.merge_requested.emit(self._pdf_paths, output_path)
