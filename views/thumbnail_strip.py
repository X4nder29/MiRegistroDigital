"""
ThumbnailStrip — Tira horizontal/vertical de miniaturas de páginas.
Soporta selección, marcas de corte y etiquetas OCR.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QSizePolicy, QToolButton, QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont

from utils.image_utils import numpy_to_qimage
from views.theme import SURFACE, SURFACE2, BORDER, SUCCESS, WARNING, DANGER, INFO, TEXT_DIM


class ThumbnailItem(QFrame):
    """Widget de una sola miniatura."""

    clicked = Signal(int)
    cut_toggled = Signal(int)
    delete_requested = Signal(int)

    THUMB_SIZE = 140

    def __init__(self, index: int, image: np.ndarray, parent=None):
        super().__init__(parent)
        self.page_index = index
        self._selected = False
        self._is_cut = False
        self._label_text = ""

        self.setFixedWidth(self.THUMB_SIZE + 16)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Número de página
        self._num_label = QLabel(str(index + 1))
        self._num_label.setAlignment(Qt.AlignCenter)
        self._num_label.setObjectName("pageNumber")

        # Imagen
        self._img_label = QLabel()
        self._img_label.setFixedSize(self.THUMB_SIZE, int(self.THUMB_SIZE * 1.414))
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setScaledContents(False)

        # Etiqueta OCR / serial
        self._ocr_label = QLabel("—")
        self._ocr_label.setAlignment(Qt.AlignCenter)
        self._ocr_label.setObjectName("ocrLabel")
        self._ocr_label.setWordWrap(True)

        layout.addWidget(self._num_label)
        layout.addWidget(self._img_label)
        layout.addWidget(self._ocr_label)

        self.set_image(image)
        self._update_style()

    def set_image(self, image: np.ndarray):
        qimg = numpy_to_qimage(image)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self._img_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._img_label.setPixmap(scaled)

    def set_serial(self, serial: str, confidence: float = 0.0):
        if serial:
            color = SUCCESS if confidence >= 0.7 else WARNING
            self._ocr_label.setText(serial)
            self._ocr_label.setStyleSheet(f"color: {color};")
        else:
            self._ocr_label.setText("Sin serial")
            self._ocr_label.setStyleSheet(f"color: {DANGER};")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def set_cut_point(self, is_cut: bool):
        self._is_cut = is_cut
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.page_index)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        cut_action = menu.addAction(
            "Quitar punto de corte" if self._is_cut else "Marcar como punto de corte"
        )
        del_action = menu.addAction("Eliminar página")
        action = menu.exec(self.mapToGlobal(pos))
        if action == cut_action:
            self.cut_toggled.emit(self.page_index)
        elif action == del_action:
            self.delete_requested.emit(self.page_index)

    def _update_style(self):
        border_color = INFO if self._selected else (WARNING if self._is_cut else BORDER)
        border_width = 2 if (self._selected or self._is_cut) else 1
        bg = SURFACE2 if self._selected else (SURFACE if self._is_cut else SURFACE)
        self.setStyleSheet(f"""
            ThumbnailItem {{
                border: {border_width}px solid {border_color};
                border-radius: 6px;
                background: {bg};
            }}
        """)


class ThumbnailStrip(QScrollArea):
    """
    Tira scrolleable de miniaturas.

    Signals
    -------
    page_selected(int)       — página seleccionada
    cut_toggled(int)         — punto de corte toggled
    page_deleted(int)        — página solicitó eliminación
    """

    page_selected = Signal(int)
    cut_toggled = Signal(int)
    page_deleted = Signal(int)

    def __init__(self, orientation: Qt.Orientation = Qt.Horizontal, parent=None):
        super().__init__(parent)
        self._orientation = orientation
        self._items: list[ThumbnailItem] = []
        self._selected_index: int = -1

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._container = QWidget()
        if orientation == Qt.Horizontal:
            self._layout = QHBoxLayout(self._container)
            self.setFixedHeight(ThumbnailItem.THUMB_SIZE + 80)
        else:
            self._layout = QVBoxLayout(self._container)
            self.setFixedWidth(ThumbnailItem.THUMB_SIZE + 32)

        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        self.setWidget(self._container)

    # ── API ───────────────────────────────────────────────────────────────────

    def add_page(self, index: int, image: np.ndarray):
        item = ThumbnailItem(index, image)
        item.clicked.connect(self._on_item_clicked)
        item.cut_toggled.connect(self.cut_toggled)
        item.delete_requested.connect(self.page_deleted)
        # Insertar antes del stretch
        self._layout.insertWidget(self._layout.count() - 1, item)
        self._items.append(item)

    def update_page(self, index: int, image: np.ndarray):
        item = self._get_item(index)
        if item:
            item.set_image(image)

    def set_serial(self, index: int, serial: str, confidence: float = 0.0):
        item = self._get_item(index)
        if item:
            item.set_serial(serial, confidence)

    def set_cut_point(self, index: int, is_cut: bool):
        item = self._get_item(index)
        if item:
            item.set_cut_point(is_cut)

    def select(self, index: int):
        if self._selected_index >= 0:
            old = self._get_item(self._selected_index)
            if old:
                old.set_selected(False)
        self._selected_index = index
        item = self._get_item(index)
        if item:
            item.set_selected(True)
            self.ensureWidgetVisible(item)

    def clear(self):
        for item in self._items:
            self._layout.removeWidget(item)
            item.deleteLater()
        self._items.clear()
        self._selected_index = -1

    def remove_page(self, index: int):
        item = self._get_item(index)
        if item:
            self._layout.removeWidget(item)
            item.deleteLater()
            self._items = [i for i in self._items if i.page_index != index]
            # Reindexar
            for i, it in enumerate(self._items):
                it.page_index = i
                it._num_label.setText(str(i + 1))

    # ── Interno ───────────────────────────────────────────────────────────────

    def _get_item(self, index: int) -> ThumbnailItem | None:
        for item in self._items:
            if item.page_index == index:
                return item
        return None

    def _on_item_clicked(self, index: int):
        self.select(index)
        self.page_selected.emit(index)
