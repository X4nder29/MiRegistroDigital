"""
CivilView — Vista del modo Registros Civiles.
Muestra tabla de páginas con serial OCR, permite corrección manual y exporta.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QProgressBar, QFrame, QLineEdit, QAbstractItemView,
    QFileDialog, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from views.theme import SUCCESS as _OK, WARNING as _WARN, DANGER as _ERR, INFO as _INFO


class CivilView(QWidget):
    """
    Vista Registros Civiles.

    Signals
    -------
    ocr_all_requested()              — ejecutar OCR en todas las páginas
    ocr_page_requested(int)          — ejecutar OCR en una página
    serial_corrected(int, str)       — usuario corrigió serial de página
    export_requested(str)            — exportar a ZIP en la carpeta indicada
    """

    ocr_all_requested = Signal()
    ocr_page_requested = Signal(int)
    serial_corrected = Signal(int, str)
    export_requested = Signal(str)

    COL_NUM     = 0
    COL_SERIAL  = 1
    COL_CONF    = 2
    COL_ESTADO  = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_count = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Encabezado ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Registros Civiles")
        title.setObjectName("viewTitle")
        header.addWidget(title)
        header.addStretch()

        self.btn_ocr_all = QPushButton("🔍  OCR a todas las páginas")
        self.btn_ocr_all.setObjectName("primaryBtn")
        self.btn_ocr_all.setFixedHeight(36)
        self.btn_ocr_all.clicked.connect(self.ocr_all_requested)
        header.addWidget(self.btn_ocr_all)

        root.addLayout(header)

        # ── Descripción ───────────────────────────────────────────────────────
        desc = QLabel(
            "Cada página escaneada se guardará como un PDF individual. "
            "El nombre del archivo será el serial de 8 dígitos extraído del margen derecho. "
            "Puedes corregir manualmente cualquier serial haciendo doble clic en la celda."
        )
        desc.setWordWrap(True)
        desc.setObjectName("descLabel")
        root.addWidget(desc)

        # ── Tabla de páginas ──────────────────────────────────────────────────
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Página", "Serial OCR", "Confianza", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_item_changed)

        root.addWidget(self.table)

        # ── Panel inferior ────────────────────────────────────────────────────
        bottom = QHBoxLayout()

        # Resumen OCR
        self.ocr_summary = QLabel("Páginas: 0 | Seriales OK: 0 | Pendientes: 0")
        self.ocr_summary.setObjectName("summaryLabel")
        bottom.addWidget(self.ocr_summary)
        bottom.addStretch()

        # Botón OCR página seleccionada
        self.btn_ocr_page = QPushButton("OCR página seleccionada")
        self.btn_ocr_page.setFixedHeight(32)
        self.btn_ocr_page.clicked.connect(self._request_ocr_page)
        bottom.addWidget(self.btn_ocr_page)

        root.addLayout(bottom)

        # ── Barra de progreso ─────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        root.addWidget(self.progress_bar)

        # ── Panel de exportación ──────────────────────────────────────────────
        export_box = self._build_export_panel()
        root.addWidget(export_box)

    def _build_export_panel(self) -> QGroupBox:
        box = QGroupBox("Exportar")
        layout = QHBoxLayout(box)

        layout.addWidget(QLabel("Carpeta de destino:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Selecciona una carpeta…")
        layout.addWidget(self.folder_edit)

        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(36)
        btn_browse.clicked.connect(self._browse_folder)
        layout.addWidget(btn_browse)

        self.btn_export = QPushButton("💾  Generar ZIP")
        self.btn_export.setObjectName("primaryBtn")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setFixedWidth(140)
        self.btn_export.clicked.connect(self._request_export)
        layout.addWidget(self.btn_export)

        return box

    # ── API pública ───────────────────────────────────────────────────────────

    def add_page(self, index: int):
        """Agrega una fila para una nueva página."""
        self._block_signals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)

        num_item = QTableWidgetItem(str(index + 1))
        num_item.setTextAlignment(Qt.AlignCenter)
        num_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        num_item.setData(Qt.UserRole, index)

        serial_item = QTableWidgetItem("—")
        serial_item.setTextAlignment(Qt.AlignCenter)

        conf_item = QTableWidgetItem("—")
        conf_item.setTextAlignment(Qt.AlignCenter)
        conf_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        estado_item = QTableWidgetItem("Pendiente OCR")
        estado_item.setTextAlignment(Qt.AlignCenter)
        estado_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        estado_item.setForeground(QColor(_WARN))

        self.table.setItem(row, self.COL_NUM, num_item)
        self.table.setItem(row, self.COL_SERIAL, serial_item)
        self.table.setItem(row, self.COL_CONF, conf_item)
        self.table.setItem(row, self.COL_ESTADO, estado_item)

        self._page_count += 1
        self._block_signals(False)
        self._refresh_summary()

    def set_ocr_result(self, page_index: int, serial: str, confidence: float):
        """Actualiza la fila con el resultado del OCR."""
        self._block_signals(True)
        row = self._row_for_page(page_index)
        if row < 0:
            self._block_signals(False)
            return

        self.table.item(row, self.COL_SERIAL).setText(serial or "Sin serial")

        conf_pct = f"{confidence:.0%}"
        conf_item = self.table.item(row, self.COL_CONF)
        conf_item.setText(conf_pct)

        estado_item = self.table.item(row, self.COL_ESTADO)
        if serial:
            color = _OK if confidence >= 0.7 else _WARN
            estado_item.setText("OK" if confidence >= 0.7 else "Baja confianza")
            estado_item.setForeground(QColor(color))
            self.table.item(row, self.COL_SERIAL).setForeground(QColor(color))
        else:
            estado_item.setText("Sin serial")
            estado_item.setForeground(QColor(_ERR))
            self.table.item(row, self.COL_SERIAL).setForeground(QColor(_ERR))

        self._block_signals(False)
        self._refresh_summary()

    def set_ocr_error(self, page_index: int, msg: str):
        row = self._row_for_page(page_index)
        if row < 0:
            return
        self.table.item(row, self.COL_ESTADO).setText("Error OCR")
        self.table.item(row, self.COL_ESTADO).setForeground(QColor(_ERR))
        self.table.item(row, self.COL_SERIAL).setText("—")
        self._refresh_summary()

    def show_progress(self, current: int, total: int):
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        if current >= total:
            self.progress_bar.setVisible(False)

    def ocr_started(self):
        self.btn_ocr_all.setEnabled(False)
        self.btn_ocr_all.setText("Procesando OCR…")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Modo indeterminado

    def ocr_finished(self):
        self.btn_ocr_all.setEnabled(True)
        self.btn_ocr_all.setText("🔍  OCR a todas las páginas")
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
        self.table.setRowCount(0)
        self._page_count = 0
        self._refresh_summary()

    # ── Internos ──────────────────────────────────────────────────────────────

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != self.COL_SERIAL:
            return
        row = item.row()
        num_item = self.table.item(row, self.COL_NUM)
        if num_item is None:
            return
        page_index = num_item.data(Qt.UserRole)
        serial = item.text().strip()
        estado = self.table.item(row, self.COL_ESTADO)
        if estado:
            estado.setText("Corregido manualmente")
            estado.setForeground(QColor(_INFO))
        self.serial_corrected.emit(page_index, serial)
        self._refresh_summary()

    def _request_ocr_page(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = self.table.currentRow()
        num_item = self.table.item(row, self.COL_NUM)
        if num_item:
            page_index = num_item.data(Qt.UserRole)
            self.ocr_page_requested.emit(page_index)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
        if folder:
            self.folder_edit.setText(folder)

    def _request_export(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Carpeta requerida", "Por favor selecciona una carpeta de destino.")
            return
        self.export_requested.emit(folder)

    def _row_for_page(self, page_index: int) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, self.COL_NUM)
            if item and item.data(Qt.UserRole) == page_index:
                return row
        return -1

    def _block_signals(self, block: bool):
        self.table.blockSignals(block)

    def _refresh_summary(self):
        total = self.table.rowCount()
        ok = 0
        pending = 0
        for row in range(total):
            estado = self.table.item(row, self.COL_ESTADO)
            if estado:
                txt = estado.text()
                if txt in ("OK", "Corregido manualmente"):
                    ok += 1
                else:
                    pending += 1
        self.ocr_summary.setText(
            f"Páginas: {total} | Seriales OK: {ok} | Pendientes: {pending}"
        )
