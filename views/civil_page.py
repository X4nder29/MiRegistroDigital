"""Página de Registros Civiles — con preview y selección de área OCR."""
from __future__ import annotations
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar, QFrame, QLineEdit, QFileDialog, QMessageBox,
    QSplitter,
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSpinBox, QInputDialog, QMenu

from views.widgets import ImageViewer
from views.theme import SURFACE, TEXT_DIM, TEXT_SEC, SUCCESS, DANGER, WARNING, SURFACE2, BG, INFO


class CivilPage(QWidget):
    ocr_all_requested        = Signal()
    ocr_page_requested       = Signal(int)
    ocr_cancel_requested     = Signal()
    serial_corrected         = Signal(int, str)
    export_requested         = Signal(str)
    ocr_area_saved           = Signal(int, float, float, float, float)
    parallel_workers_changed = Signal(int)
    page_reordered           = Signal(int, int)
    page_reordered_seq       = Signal(list)
    bookmark_set             = Signal(int, str)

    COL_NUM, COL_SERIAL, COL_CONF, COL_STATUS, COL_BOOKMARK = 0, 1, 2, 3, 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_preview: int = -1
        self._debug_active = False
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

        title = QLabel("Registros Civiles")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")

        self._btn_ocr = QPushButton("  OCR todas")
        self._btn_ocr.setProperty("primary", True)
        self._btn_ocr.setFixedHeight(34)
        self._btn_ocr.clicked.connect(self.ocr_all_requested)

        self._btn_cancel_ocr = QPushButton("Cancelar OCR")
        self._btn_cancel_ocr.setFixedHeight(30)
        self._btn_cancel_ocr.setStyleSheet(f"color:{DANGER};")
        self._btn_cancel_ocr.setVisible(False)
        self._btn_cancel_ocr.clicked.connect(self.ocr_cancel_requested)

        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._btn_cancel_ocr)
        hl.addWidget(self._btn_ocr)
        root.addWidget(header)

        desc = QLabel("Cada página se exporta como PDF individual nombrado con el serial de 8 dígitos. "
                      "Haz doble clic en el serial para editarlo.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none; padding:4px 24px 4px 24px;")
        root.addWidget(desc)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Página", "Serial OCR", "Confianza", "Estado", "Marcador"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 70)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._table.setColumnWidth(4, 120)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setDragEnabled(True)
        self._table.setAcceptDrops(True)
        self._table.setDragDropMode(QAbstractItemView.InternalMove)
        self._table.setDropIndicatorShown(True)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._table_context_menu)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.installEventFilter(self)
        lv.addWidget(self._table, 1)

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
        btn_browse.setToolTip("Seleccionar carpeta")
        btn_browse.clicked.connect(self._browse)

        self._btn_export = QPushButton("  Generar ZIP")
        self._btn_export.setProperty("primary", True)
        self._btn_export.setFixedHeight(34)
        self._btn_export.clicked.connect(self._do_export)

        btn_ocr_sel = QPushButton("  OCR página")
        btn_ocr_sel.setFixedHeight(32)
        btn_ocr_sel.clicked.connect(self._ocr_selected)

        bl.addWidget(self._summary)
        bl.addWidget(self._prog)
        bl.addStretch()
        bl.addWidget(btn_ocr_sel)
        bl.addWidget(QLabel("Destino:"))
        bl.addWidget(self._folder_edit)
        bl.addWidget(btn_browse)
        bl.addWidget(self._btn_export)
        lv.addWidget(bottom)

        splitter.addWidget(left)

        self._preview_panel = self._build_preview_panel()
        splitter.addWidget(self._preview_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([500, 400])

        root.addWidget(splitter, 1)

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setMinimumWidth(280)
        panel.setStyleSheet(f"background:{SURFACE}; border:none;")
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        header_row = QHBoxLayout()
        self._preview_title = QLabel("Previsualización")
        self._preview_title.setStyleSheet("font-size:11pt; font-weight:bold; border:none;")
        self._preview_idx = QLabel("")
        self._preview_idx.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        header_row.addWidget(self._preview_title)
        header_row.addWidget(self._preview_idx)
        header_row.addStretch()
        v.addLayout(header_row)

        self._preview_viewer = ImageViewer()
        self._preview_viewer.setMinimumSize(260, 300)
        v.addWidget(self._preview_viewer, 1)

        self._btn_area = QPushButton("  Área OCR")
        self._btn_area.setFixedHeight(32)
        self._btn_area.setToolTip("Delimitar área del serial en la imagen")
        self._btn_area.clicked.connect(self._select_area)
        v.addWidget(self._btn_area)

        self._area_status = QLabel("Selecciona una página para previsualizar")
        self._area_status.setWordWrap(True)
        self._area_status.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        v.addWidget(self._area_status)

        self._btn_debug = QPushButton("  Debug área OCR")
        self._btn_debug.setFixedHeight(32)
        self._btn_debug.setCheckable(True)
        self._btn_debug.setToolTip("Muestra el área exacta que se recorta para OCR")
        self._btn_debug.toggled.connect(self._toggle_debug)
        v.addWidget(self._btn_debug)

        self._debug_status = QLabel("")
        self._debug_status.setWordWrap(True)
        self._debug_status.setStyleSheet(f"color:{WARNING}; font-size:8pt; border:none;")
        self._debug_status.setVisible(False)
        v.addWidget(self._debug_status)

        v.addSpacing(8)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{SURFACE2}; border:none;")
        v.addWidget(sep)
        v.addSpacing(4)

        cores_row = QHBoxLayout()
        cores_lbl = QLabel("OCR en paralelo:")
        cores_lbl.setStyleSheet("font-size:9pt; border:none;")
        self._cores_spin = QSpinBox()
        self._cores_spin.setRange(1, 16)
        self._cores_spin.setValue(4)
        self._cores_spin.setFixedWidth(60)
        self._cores_spin.valueChanged.connect(self._on_cores_changed)
        cores_row.addWidget(cores_lbl)
        cores_row.addWidget(self._cores_spin)
        cores_row.addStretch()
        v.addLayout(cores_row)

        return panel

    def eventFilter(self, obj, event):
        if obj is self._table and event.type() == QEvent.Drop:
            QTimer.singleShot(0, self._detect_new_order)
        return super().eventFilter(obj, event)

    def _detect_new_order(self):
        order = []
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                order.append(item.data(Qt.UserRole))
        if order:
            self.page_reordered_seq.emit(order)

    def _table_context_menu(self, pos):
        item = self._table.itemAt(pos)
        if not item:
            return
        row = item.row()
        n_item = self._table.item(row, 0)
        if not n_item:
            return
        idx = n_item.data(Qt.UserRole)
        menu = QMenu(self)
        act_bm = menu.addAction("Añadir/quitar marcador…")
        menu.addSeparator()
        action = menu.exec(self._table.mapToGlobal(pos))
        if action == act_bm:
            current = self._table.item(row, self.COL_BOOKMARK)
            cur_text = current.text() if current and current.text() not in ("", "—") else ""
            text, ok = QInputDialog.getText(
                self, "Marcador",
                "Nombre del marcador (vacío para quitar):",
                text=cur_text)
            if ok:
                self._table.blockSignals(True)
                if self._table.item(row, self.COL_BOOKMARK):
                    self._table.item(row, self.COL_BOOKMARK).setText(text.strip())
                self._table.blockSignals(False)
                self.bookmark_set.emit(idx, text.strip())

    def add_page(self, index: int, image: np.ndarray | None = None, bookmark: str = ""):
        self._table.blockSignals(True)
        row = self._table.rowCount()
        self._table.insertRow(row)

        n = QTableWidgetItem(str(index + 1))
        n.setTextAlignment(Qt.AlignCenter)
        n.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        n.setData(Qt.UserRole, index)

        s = QTableWidgetItem("—")
        s.setTextAlignment(Qt.AlignCenter)

        c = QTableWidgetItem("—")
        c.setTextAlignment(Qt.AlignCenter)
        c.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        e = QTableWidgetItem("Pendiente")
        e.setTextAlignment(Qt.AlignCenter)
        e.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        e.setForeground(QColor(TEXT_DIM))

        b = QTableWidgetItem(bookmark)
        b.setTextAlignment(Qt.AlignCenter)
        if bookmark:
            b.setForeground(QColor(INFO))

        self._table.setItem(row, 0, n)
        self._table.setItem(row, 1, s)
        self._table.setItem(row, 2, c)
        self._table.setItem(row, 3, e)
        self._table.setItem(row, 4, b)
        self._table.blockSignals(False)
        self._refresh_summary()

    def set_image(self, index: int, image: np.ndarray):
        if index == self._current_preview:
            self._preview_viewer.set_image(image)

    def set_bookmark(self, page_index: int, label: str):
        self._table.blockSignals(True)
        row = self._row_for(page_index)
        if row >= 0:
            item = self._table.item(row, self.COL_BOOKMARK)
            if item:
                item.setText(label)
                item.setForeground(QColor(INFO) if label else QColor(TEXT_DIM))
        self._table.blockSignals(False)

    def rebuild(self, pages_data: list):
        self.clear()
        for pd in pages_data:
            self.add_page(pd.index, pd.display_image, pd.bookmark)
            if pd.serial:
                self.set_ocr_result(pd.index, pd.serial, pd.serial_confidence)

    def set_ocr_result(self, page_index: int, serial: str, conf: float):
        self._table.blockSignals(True)
        row = self._row_for(page_index)
        if row < 0:
            self._table.blockSignals(False)
            return
        self._table.item(row, 1).setText(serial or "Sin serial")
        self._table.item(row, 2).setText(f"{conf:.0%}" if conf > 0 else "—")
        e = self._table.item(row, 3)
        if serial:
            color = SUCCESS if conf >= 0.7 else WARNING
            e.setText("OK" if conf >= 0.7 else "Baja confianza")
            e.setForeground(QColor(color))
            self._table.item(row, 1).setForeground(QColor(color))
        else:
            e.setText("Sin serial")
            e.setForeground(QColor(DANGER))
            self._table.item(row, 1).setForeground(QColor(DANGER))
        self._table.blockSignals(False)
        self._refresh_summary()

    def set_ocr_error(self, page_index: int, msg: str):
        row = self._row_for(page_index)
        if row >= 0:
            self._table.item(row, 3).setText("Error")
            self._table.item(row, 3).setForeground(QColor(DANGER))

    def ocr_started(self):
        self._btn_ocr.setEnabled(False)
        self._btn_ocr.setText("Procesando…")
        self._btn_cancel_ocr.setVisible(True)
        self._prog.setRange(0, 0)
        self._prog.setVisible(True)

    def ocr_finished(self):
        self._btn_ocr.setEnabled(True)
        self._btn_ocr.setText("  OCR todas")
        self._btn_cancel_ocr.setVisible(False)
        self._prog.setVisible(False)
        self._refresh_summary()

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

    def remove_page(self, index: int):
        row = self._row_for(index)
        if row >= 0:
            self._table.removeRow(row)
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item:
                item.setData(Qt.UserRole, r)
                item.setText(str(r + 1))
        self._refresh_summary()
        if index == self._current_preview:
            self._clear_preview()

    def clear(self):
        self._table.setRowCount(0)
        self._current_preview = -1
        self._clear_preview()
        self._refresh_summary()

    def _clear_preview(self):
        self._preview_viewer.set_image(None)
        self._preview_viewer.set_ocr_area_preview(None)
        self._preview_viewer.set_debug_ocr_rect(None)
        self._preview_idx.setText("")
        self._area_status.setText("Selecciona una página para previsualizar")

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 1:
            return
        row = item.row()
        n_item = self._table.item(row, 0)
        if n_item is None:
            return
        idx = n_item.data(Qt.UserRole)
        serial = item.text().strip()
        e = self._table.item(row, 3)
        if e:
            e.setText("Corregido")
            e.setForeground(QColor(TEXT_SEC))
        self.serial_corrected.emit(idx, serial)
        self._refresh_summary()

    def _on_selection_changed(self):
        row = self._table.currentRow()
        if row < 0:
            return
        n = self._table.item(row, 0)
        if n is None:
            return
        idx = n.data(Qt.UserRole)
        self._current_preview = idx
        from models.scan_model import ScanModel
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        page = mw._model.get(idx) if mw and hasattr(mw, '_model') else None
        if page:
            self._preview_viewer.set_image(page.display_image)
            self._preview_idx.setText(f"Página {idx + 1}")
            if page.ocr_area:
                self._preview_viewer.set_ocr_area_preview(page.ocr_area)
                self._area_status.setText("Área OCR definida")
            else:
                self._preview_viewer.set_ocr_area_preview(None)
                self._area_status.setText("Sin área OCR")
            self._update_debug_overlay()
        else:
            self._clear_preview()

    def _ocr_selected(self):
        row = self._table.currentRow()
        if row < 0:
            return
        n = self._table.item(row, 0)
        if n:
            self.ocr_page_requested.emit(n.data(Qt.UserRole))

    def _select_area(self):
        if self._current_preview < 0:
            return
        self._preview_viewer.set_ocr_area_preview(None)
        self._preview_viewer.enable_area_selection(True)
        self._area_status.setText("Dibuja un rectángulo sobre el área del serial")
        self._btn_area.setText("Cancelar selección")
        self._btn_area.clicked.disconnect()
        self._btn_area.clicked.connect(self._cancel_area_selection)
        self._preview_viewer.area_selected.connect(self._on_area_selected)

    def _cancel_area_selection(self):
        self._preview_viewer.enable_area_selection(False)
        self._preview_viewer.area_selected.disconnect(self._on_area_selected)
        self._btn_area.setText("  Área OCR")
        self._btn_area.clicked.disconnect()
        self._btn_area.clicked.connect(self._select_area)
        self._area_status.setText("Selección cancelada")
        self._on_selection_changed()

    def _toggle_debug(self, active: bool):
        self._debug_active = active
        self._debug_status.setVisible(active)
        if active:
            self._debug_status.setText("Calculando…")
        else:
            self._preview_viewer.set_debug_ocr_rect(None)
            self._debug_status.setText("")
        self._update_debug_overlay()

    def _get_ocr_crop_rect(self, page_index: int) -> tuple[float, float, float, float] | None:
        from models.scan_model import ScanModel
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model'):
            return None
        page = mw._model.get(page_index)
        if page is None:
            return None
        if page.ocr_area:
            return page.ocr_area
        if hasattr(mw, '_cfg'):
            pct = mw._cfg.get("ocr", "margin_right_pct", 0.15)
        else:
            pct = 0.15
        return (1.0 - pct, 0.0, 1.0, 1.0)

    def _update_debug_overlay(self):
        if not self._debug_active or self._current_preview < 0:
            self._preview_viewer.set_debug_ocr_rect(None)
            return
        rect = self._get_ocr_crop_rect(self._current_preview)
        if rect:
            self._preview_viewer.set_debug_ocr_rect(rect)
            pct = round((rect[2] - rect[0]) * 100, 1)
            self._debug_status.setText(
                f"Área OCR: ({rect[0]:.2f}, {rect[1]:.2f}) → ({rect[2]:.2f}, {rect[3]:.2f})\n"
                f"Ancho: {pct}% de la imagen")
        else:
            self._preview_viewer.set_debug_ocr_rect(None)
            self._debug_status.setText("No se pudo determinar el área OCR")

    def _on_area_selected(self, x1: float, y1: float, x2: float, y2: float):
        self._preview_viewer.area_selected.disconnect(self._on_area_selected)
        self._btn_area.setText("  Área OCR")
        self._btn_area.clicked.disconnect()
        self._btn_area.clicked.connect(self._select_area)
        self.ocr_area_saved.emit(self._current_preview, x1, y1, x2, y2)
        self._preview_viewer.set_ocr_area_preview((x1, y1, x2, y2))
        self._area_status.setText(f"Área OCR guardada para página {self._current_preview + 1}")

    def set_parallel_workers(self, n: int):
        self._cores_spin.blockSignals(True)
        self._cores_spin.setValue(n)
        self._cores_spin.blockSignals(False)

    def _on_cores_changed(self, value: int):
        self.parallel_workers_changed.emit(value)

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
        self.export_requested.emit(folder)

    def _row_for(self, page_index: int) -> int:
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.data(Qt.UserRole) == page_index:
                return r
        return -1

    def _refresh_summary(self):
        total  = self._table.rowCount()
        ok     = sum(1 for r in range(total)
                     if self._table.item(r, 3) and
                     self._table.item(r, 3).text() in ("OK", "Corregido"))
        pend   = total - ok
        self._summary.setText(f"{total} páginas · {ok} OK · {pend} pendientes")
