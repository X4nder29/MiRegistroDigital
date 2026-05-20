"""Widgets reutilizables."""
from __future__ import annotations
import numpy as np
from PySide6.QtWidgets import (
    QLabel, QFrame, QWidget, QScrollArea, QGridLayout,
    QVBoxLayout, QHBoxLayout, QSizePolicy, QPushButton,
    QMenu, QDialog, QToolBar, QRubberBand,
)
from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint
from PySide6.QtGui import QPixmap, QAction, QKeySequence

from utils.image_utils import ndarray_to_qpixmap
from views.theme import (
    SURFACE, SURFACE2, SURFACE3,
    ACCENT, TEXT, TEXT_SEC, TEXT_DIM, BG, SUCCESS, DANGER, WARNING,
)


class ImageViewer(QLabel):
    area_selected = Signal(float, float, float, float)  # x1, y1, x2, y2 normalized [0-1]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 450)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setText("Sin imagen")
        self.setStyleSheet(f"color: {TEXT_DIM}; border:none;")
        self._pixmap: QPixmap | None = None
        self._selecting = False
        self._rubber_band: QRubberBand | None = None
        self._origin: QPoint | None = None
        self._area_preview: tuple[float, float, float, float] | None = None
        self._preview_band: QRubberBand | None = None
        self._debug_rect: tuple[float, float, float, float] | None = None
        self._debug_band: QRubberBand | None = None

    def enable_area_selection(self, enable: bool = True):
        if self._area_preview and enable:
            self.set_ocr_area_preview(None)
        self._selecting = enable
        if not enable:
            if self._rubber_band:
                self._rubber_band.hide()
            self._origin = None
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def set_ocr_area_preview(self, area: tuple[float, float, float, float] | None):
        self._area_preview = area
        if self._preview_band:
            self._preview_band.hide()
            self._preview_band.deleteLater()
            self._preview_band = None
        if area and self._pixmap:
            self._preview_band = QRubberBand(QRubberBand.Rectangle, self)
            self._preview_band.setStyleSheet(
                "QRubberBand { border: 2px solid #689cf8; background: rgba(104, 156, 248, 40); }")
            self._update_preview_band()
            self._preview_band.show()

    def _update_preview_band(self):
        if self._area_preview and self._preview_band and self._pixmap:
            prect = self._pixmap_rect()
            if prect.isValid():
                a = self._area_preview
                x1 = prect.left() + a[0] * prect.width()
                y1 = prect.top() + a[1] * prect.height()
                x2 = prect.left() + a[2] * prect.width()
                y2 = prect.top() + a[3] * prect.height()
                self._preview_band.setGeometry(
                    QRect(round(x1), round(y1), round(x2 - x1), round(y2 - y1)))

    def set_image(self, image: np.ndarray | None):
        if image is None:
            self._pixmap = None
            self.setText("Sin imagen")
            return
        self._pixmap = ndarray_to_qpixmap(image)
        self.setText("")
        self._rescale()

    def mousePressEvent(self, event):
        if self._selecting and event.button() == Qt.LeftButton and self._pixmap:
            self._origin = event.pos()
            if not self._rubber_band:
                self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(QRect(self._origin, QSize()))
            self._rubber_band.show()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._selecting and self._rubber_band and self._rubber_band.isVisible():
            rect = QRect(self._origin, event.pos()).normalized()
            self._rubber_band.setGeometry(rect)
            return
        super().mouseMoveEvent(event)

    def _pixmap_rect(self) -> QRect:
        if not self._pixmap:
            return QRect()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw == 0 or ph == 0:
            return QRect()
        sw, sh = self.width(), self.height()
        scale = min(sw / pw, sh / ph, 1.0)
        dw, dh = int(pw * scale), int(ph * scale)
        x = (sw - dw) // 2
        y = (sh - dh) // 2
        return QRect(x, y, dw, dh)

    def mouseReleaseEvent(self, event):
        if self._selecting and self._rubber_band and self._rubber_band.isVisible() and event.button() == Qt.LeftButton:
            rect = QRect(self._origin, event.pos()).normalized()
            self._rubber_band.hide()
            self._origin = None
            self.enable_area_selection(False)
            prect = self._pixmap_rect()
            if prect.isValid() and rect.width() > 10 and rect.height() > 10:
                clipped = rect.intersected(prect)
                if clipped.isValid() and clipped.width() > 5 and clipped.height() > 5:
                    x1 = (clipped.left() - prect.left()) / prect.width()
                    y1 = (clipped.top() - prect.top()) / prect.height()
                    x2 = (clipped.right() - prect.left()) / prect.width()
                    y2 = (clipped.bottom() - prect.top()) / prect.height()
                    self.area_selected.emit(x1, y1, x2, y2)
            return
        super().mouseReleaseEvent(event)

    def set_debug_ocr_rect(self, rect: tuple[float, float, float, float] | None):
        self._debug_rect = rect
        if self._debug_band:
            self._debug_band.hide()
            self._debug_band.deleteLater()
            self._debug_band = None
        if rect and self._pixmap:
            self._debug_band = QRubberBand(QRubberBand.Rectangle, self)
            self._debug_band.setStyleSheet(
                "QRubberBand { border: 2px dashed #00ff88; background: rgba(0, 255, 136, 30); }")
            self._update_debug_band()
            self._debug_band.show()

    def _update_debug_band(self):
        if self._debug_rect and self._debug_band and self._pixmap:
            prect = self._pixmap_rect()
            if prect.isValid():
                a = self._debug_rect
                x1 = prect.left() + a[0] * prect.width()
                y1 = prect.top() + a[1] * prect.height()
                x2 = prect.left() + a[2] * prect.width()
                y2 = prect.top() + a[3] * prect.height()
                self._debug_band.setGeometry(
                    QRect(round(x1), round(y1), round(x2 - x1), round(y2 - y1)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()
        self._update_preview_band()
        self._update_debug_band()

    def _rescale(self):
        if self._pixmap:
            self.setPixmap(self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class FullscreenViewer(QDialog):
    def __init__(self, images: list[np.ndarray], start: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vista completa")
        self.resize(1000, 750)
        self._images = images
        self._idx    = start

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tb = QToolBar()
        tb.setMovable(False)
        act_prev = QAction("‹  Anterior", self)
        act_prev.setShortcut(QKeySequence(Qt.Key_Left))
        act_prev.triggered.connect(self._prev)
        act_next = QAction("Siguiente  ›", self)
        act_next.setShortcut(QKeySequence(Qt.Key_Right))
        act_next.triggered.connect(self._next)
        act_close = QAction("✕  Cerrar", self)
        act_close.setShortcut(QKeySequence(Qt.Key_Escape))
        act_close.triggered.connect(self.close)
        self._page_label = QLabel()
        tb.addAction(act_prev)
        tb.addAction(act_next)
        tb.addSeparator()
        tb.addWidget(self._page_label)
        tb.addSeparator()
        tb.addAction(act_close)
        layout.addWidget(tb)

        self._viewer = ImageViewer()
        layout.addWidget(self._viewer)
        self._show_current()

    def _show_current(self):
        if self._images:
            self._viewer.set_image(self._images[self._idx])
        self._page_label.setText(f"  Página {self._idx + 1} de {len(self._images)}  ")

    def _prev(self):
        if self._idx > 0:
            self._idx -= 1
            self._show_current()

    def _next(self):
        if self._idx < len(self._images) - 1:
            self._idx += 1
            self._show_current()


THUMB_W, THUMB_H = 140, 196

class ThumbnailCard(QFrame):
    clicked            = Signal(int)
    cut_toggled        = Signal(int)
    delete_requested   = Signal(int)
    fullscreen_requested = Signal(int)

    def __init__(self, index: int, image: np.ndarray, parent=None):
        super().__init__(parent)
        self.page_index = index
        self._selected  = False
        self._is_cut    = False

        self.setFixedWidth(THUMB_W + 16)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        self._num = QLabel(str(index + 1))
        self._num.setAlignment(Qt.AlignRight)
        self._num.setStyleSheet(f"color: {TEXT_DIM}; font-size:8pt; border:none;")

        self._img_lbl = QLabel()
        self._img_lbl.setFixedSize(THUMB_W, THUMB_H)
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet(f"background:{SURFACE2}; border-radius:4px;")

        self._serial_lbl = QLabel("—")
        self._serial_lbl.setAlignment(Qt.AlignCenter)
        self._serial_lbl.setStyleSheet(f"font-size:8pt; color: {TEXT_DIM}; border:none;")

        layout.addWidget(self._num)
        layout.addWidget(self._img_lbl)
        layout.addWidget(self._serial_lbl)

        self.set_image(image)
        self._update_style()

    def set_image(self, image: np.ndarray):
        px = ndarray_to_qpixmap(image, (THUMB_W, THUMB_H))
        self._img_lbl.setPixmap(px)

    def set_serial(self, serial: str, confidence: float = 0.0):
        if serial:
            color = SUCCESS if confidence >= 0.7 else WARNING if confidence > 0 else TEXT_SEC
            self._serial_lbl.setText(serial)
        else:
            color = DANGER
            self._serial_lbl.setText("Sin serial")
        self._serial_lbl.setStyleSheet(f"font-size:8pt; font-weight:bold; color: {color}; border:none;")

    def set_selected(self, v: bool):
        self._selected = v
        self._update_style()

    def set_cut_point(self, v: bool):
        self._is_cut = v
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.page_index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.fullscreen_requested.emit(self.page_index)

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        cut_lbl  = "Quitar punto de corte" if self._is_cut else "Marcar como punto de corte"
        act_cut  = menu.addAction(cut_lbl)
        menu.addSeparator()
        act_full = menu.addAction("Ver a pantalla completa")
        menu.addSeparator()
        act_del  = menu.addAction("Eliminar página")
        action   = menu.exec(self.mapToGlobal(pos))
        if action == act_cut:
            self.cut_toggled.emit(self.page_index)
        elif action == act_full:
            self.fullscreen_requested.emit(self.page_index)
        elif action == act_del:
            self.delete_requested.emit(self.page_index)

    def _update_style(self):
        if self._is_cut:
            bg = "#1a1810"
            border = f"2px solid {ACCENT}"
        elif self._selected:
            bg = SURFACE2
            border = f"2px solid {SURFACE3}"
        else:
            bg = SURFACE
            border = "1px solid transparent"
        self.setStyleSheet(
            f"ThumbnailCard {{ border: {border}; border-radius: 8px; background: {bg}; }}")


class ThumbnailGrid(QScrollArea):
    page_selected        = Signal(int)
    cut_toggled          = Signal(int)
    page_deleted         = Signal(int)
    fullscreen_requested = Signal(int)

    CARD_W = THUMB_W + 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet("border: none;")

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._grid.setSpacing(8)
        self.setWidget(self._container)

        self._cards: list[ThumbnailCard] = []
        self._selected: int = -1
        self._cols: int = 4

    def add_page(self, index: int, image: np.ndarray) -> ThumbnailCard:
        card = ThumbnailCard(index, image)
        card.clicked.connect(self._on_clicked)
        card.cut_toggled.connect(self.cut_toggled)
        card.delete_requested.connect(self.page_deleted)
        card.fullscreen_requested.connect(self.fullscreen_requested)
        self._cards.append(card)
        self._relayout()
        return card

    def update_image(self, index: int, image: np.ndarray):
        c = self._card(index)
        if c:
            c.set_image(image)

    def set_serial(self, index: int, serial: str, confidence: float):
        c = self._card(index)
        if c:
            c.set_serial(serial, confidence)

    def set_cut(self, index: int, is_cut: bool):
        c = self._card(index)
        if c:
            c.set_cut_point(is_cut)

    def remove_page(self, index: int):
        c = self._card(index)
        if c:
            self._cards.remove(c)
            c.deleteLater()
        for i, card in enumerate(self._cards):
            card.page_index = i
            card._num.setText(str(i + 1))
        if self._selected >= len(self._cards):
            self._selected = len(self._cards) - 1
        self._relayout()

    def select(self, index: int):
        old = self._card(self._selected)
        if old:
            old.set_selected(False)
        self._selected = index
        new = self._card(index)
        if new:
            new.set_selected(True)
            self.ensureWidgetVisible(new)

    def clear_all(self):
        for c in self._cards:
            c.deleteLater()
        self._cards.clear()
        self._selected = -1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cols = max(1, self.viewport().width() // self.CARD_W)
        if cols != self._cols:
            self._cols = cols
            self._relayout()

    def _relayout(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // self._cols, i % self._cols)
        self._grid.setRowStretch(self._grid.rowCount(), 1)

    def _card(self, index: int) -> ThumbnailCard | None:
        for c in self._cards:
            if c.page_index == index:
                return c
        return None

    def _on_clicked(self, index: int):
        self.select(index)
        self.page_selected.emit(index)
