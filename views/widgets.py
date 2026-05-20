"""Widgets reutilizables."""
from __future__ import annotations
import numpy as np
from PySide6.QtWidgets import (
    QLabel, QFrame, QWidget, QScrollArea, QGridLayout,
    QVBoxLayout, QHBoxLayout, QSizePolicy, QPushButton,
    QMenu, QDialog, QToolBar, QRubberBand, QCheckBox,
    QInputDialog,
)
from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint, QMimeData, QEvent, QTimer
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QDrag, QPainter

from utils.image_utils import ndarray_to_qpixmap
from views.theme import (
    SURFACE, SURFACE2, SURFACE3, BORDER,
    ACCENT, TEXT, TEXT_SEC, TEXT_DIM, BG, SUCCESS, DANGER, WARNING, INFO,
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
            self._preview_band = QRubberBand(QRubberBand.Rectangle, self)
            self._preview_band.setStyleSheet(
                f"QRubberBand {{ border: 2px solid {INFO}; background: rgba(59, 130, 246, 30); }}")
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
                f"QRubberBand {{ border: 2px dashed {SUCCESS}; background: rgba(34, 197, 94, 25); }}")
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
    bookmark_changed = Signal(int, str)

    def __init__(self, pages_data: list, start: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vista completa")
        self.resize(1000, 750)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._pages = pages_data
        self._idx   = start

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
        self._bm_label = QLabel()
        self._bm_label.setCursor(Qt.PointingHandCursor)
        self._bm_label.setStyleSheet(
            f"color:{INFO}; border:1px solid {BORDER}; border-radius:4px; "
            f"padding:2px 8px; font-size:9pt;")
        self._bm_label.mousePressEvent = lambda e: self._edit_bookmark()

        tb.addAction(act_prev)
        tb.addAction(act_next)
        tb.addSeparator()
        tb.addWidget(self._page_label)
        tb.addSeparator()
        tb.addWidget(self._bm_label)
        tb.addSeparator()
        tb.addAction(act_close)
        layout.addWidget(tb)

        self._viewer = ImageViewer()
        layout.addWidget(self._viewer)
        self._show_current()

    def _show_current(self):
        if self._pages:
            p = self._pages[self._idx]
            self._viewer.set_image(p.display_image)
            bm = p.bookmark
            self._bm_label.setText(f"  {bm}  " if bm else "  + Marcador  ")
        self._page_label.setText(f"  Página {self._idx + 1} de {len(self._pages)}  ")

    def _edit_bookmark(self):
        p = self._pages[self._idx]
        text, ok = QInputDialog.getText(
            self, "Marcador",
            "Nombre del marcador (vacío para quitar):",
            text=p.bookmark)
        if ok:
            label = text.strip()
            p.bookmark = label
            self._bm_label.setText(f"  {label}  " if label else "  + Marcador  ")
            self.bookmark_changed.emit(p.index, label)

    def _prev(self):
        if self._idx > 0:
            self._idx -= 1
            self._show_current()

    def _next(self):
        if self._idx < len(self._pages) - 1:
            self._idx += 1
            self._show_current()


THUMB_W, THUMB_H = 140, 196

class ThumbnailCard(QFrame):
    clicked              = Signal(int)
    cut_toggled          = Signal(int)
    delete_requested     = Signal(int)
    fullscreen_requested = Signal(int)
    checked_toggled      = Signal(int, bool)
    bookmark_clicked     = Signal(int)

    def __init__(self, index: int, image: np.ndarray, parent=None):
        super().__init__(parent)
        self.page_index = index
        self._selected  = False
        self._is_cut    = False
        self._press_pos = QPoint()

        self.setFixedWidth(THUMB_W + 16)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)

        self._num = QLabel(str(index + 1))
        self._num.setStyleSheet(f"color: {TEXT_DIM}; font-size:8pt; border:none;")

        self._check = QCheckBox()
        self._check.setFixedSize(16, 16)
        self._check.setStyleSheet("QCheckBox { border:none; background:transparent; } "
                                  "QCheckBox::indicator { width:14px; height:14px; }")
        self._check.stateChanged.connect(self._on_check_changed)

        hdr.addWidget(self._num)
        hdr.addStretch()
        hdr.addWidget(self._check)

        self._img_lbl = QLabel()
        self._img_lbl.setFixedSize(THUMB_W, THUMB_H)
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet(f"background:{SURFACE2}; border-radius:4px;")

        self._bookmark_lbl = QLabel()
        self._bookmark_lbl.setAlignment(Qt.AlignCenter)
        self._bookmark_lbl.setStyleSheet(
            f"font-size:7pt; color:{INFO}; background:{BG}; "
            f"border:1px solid {BORDER}; border-radius:4px; padding:1px 4px;")
        self._bookmark_lbl.hide()

        self._serial_lbl = QLabel("—")
        self._serial_lbl.setAlignment(Qt.AlignCenter)
        self._serial_lbl.setStyleSheet(f"font-size:8pt; color: {TEXT_DIM}; border:none;")

        layout.addLayout(hdr)
        layout.addWidget(self._img_lbl)
        layout.addWidget(self._bookmark_lbl)
        layout.addWidget(self._serial_lbl)

        self.set_image(image)
        self._update_style()

    def _on_check_changed(self, state):
        self.checked_toggled.emit(self.page_index, bool(state))

    def set_checked(self, v: bool):
        self._check.blockSignals(True)
        self._check.setChecked(v)
        self._check.blockSignals(False)

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def set_bookmark(self, text: str):
        if text:
            self._bookmark_lbl.setText(f"{text}")
            self._bookmark_lbl.show()
        else:
            self._bookmark_lbl.hide()

    def set_image(self, image: np.ndarray):
        h, w = image.shape[:2]
        if w > THUMB_W or h > THUMB_H:
            import cv2
            scale = min(THUMB_W / w, THUMB_H / h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            image = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
        px = ndarray_to_qpixmap(image)
        self._img_lbl.setPixmap(px)

    def set_serial(self, serial: str, confidence: float = 0.0):
        if serial:
            color = SUCCESS if confidence >= 0.7 else WARNING if confidence > 0 else TEXT_SEC
            self._serial_lbl.setText(serial)
        else:
            color = DANGER
            self._serial_lbl.setText("Sin serial")
        self._serial_lbl.setStyleSheet(
            f"font-size:8pt; font-weight:bold; color: {color}; border:none;")

    def set_selected(self, v: bool):
        self._selected = v
        self._update_style()

    def set_cut_point(self, v: bool):
        self._is_cut = v
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if (event.pos() - self._press_pos).manhattanLength() > 10:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(str(self.page_index))
                drag.setMimeData(mime)
                pix = self.grab()
                drag.setPixmap(pix.scaled(THUMB_W//2, THUMB_H//2,
                                          Qt.KeepAspectRatio, Qt.SmoothTransformation))
                drag.setHotSpot(event.pos())
                drag.exec(Qt.MoveAction)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.fullscreen_requested.emit(self.page_index)

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        act_bm = menu.addAction("Añadir/quitar marcador…")
        menu.addSeparator()
        cut_lbl = "Quitar punto de corte" if self._is_cut else "Marcar como punto de corte"
        act_cut = menu.addAction(cut_lbl)
        menu.addSeparator()
        act_full = menu.addAction("Ver a pantalla completa")
        menu.addSeparator()
        act_del = menu.addAction("Eliminar página")
        action = menu.exec(self.mapToGlobal(pos))
        if action == act_bm:
            self.bookmark_clicked.emit(self.page_index)
        elif action == act_cut:
            self.cut_toggled.emit(self.page_index)
        elif action == act_full:
            self.fullscreen_requested.emit(self.page_index)
        elif action == act_del:
            self.delete_requested.emit(self.page_index)

    def _update_style(self):
        if self._is_cut:
            bg = SURFACE
            border = f"1px solid {WARNING}"
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
    reorder_requested    = Signal(int, int)
    bookmark_requested   = Signal(int, str)
    checked_changed      = Signal(set)

    CARD_W = THUMB_W + 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet("border: none;")

        self._container = QWidget()
        self._container.setAcceptDrops(True)
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._grid.setSpacing(8)
        self.setWidget(self._container)

        self._cards: list[ThumbnailCard] = []
        self._selected: int = -1
        self._cols: int = 4
        self._checked: set[int] = set()

        self._drop_indicator = QFrame(self._container)
        self._drop_indicator.setStyleSheet(f"background:{INFO}; border:none; border-radius:1px;")
        self._drop_indicator.setFixedWidth(3)
        self._drop_indicator.hide()

        self.viewport().setAcceptDrops(True)
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.viewport():
            t = event.type()
            if t == QEvent.DragEnter:
                self._on_drag_enter(event)
                return True
            elif t == QEvent.DragMove:
                self._on_drag_move(event)
                return True
            elif t == QEvent.Drop:
                self._on_drop(event)
                return True
            elif t == QEvent.DragLeave:
                self._drop_indicator.hide()
                return True
        return super().eventFilter(obj, event)

    def _on_drag_enter(self, event):
        if event.mimeData().hasText():
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def _on_drag_move(self, event):
        if event.mimeData().hasText():
            event.setDropAction(Qt.MoveAction)
            event.accept()
            self._update_drop_indicator(event.pos())
        else:
            event.ignore()

    def _on_drop(self, event):
        if event.mimeData().hasText():
            from_idx = int(event.mimeData().text())
            to_idx = self._target_index_from_pos(
                self._container.mapFrom(self.viewport(), event.pos()))
            event.setDropAction(Qt.MoveAction)
            event.accept()
            self._drop_indicator.hide()
            if from_idx != to_idx:
                self.reorder_requested.emit(from_idx, to_idx)
        else:
            event.ignore()

    def _update_drop_indicator(self, viewport_pos: QPoint):
        pos = self._container.mapFrom(self.viewport(), viewport_pos)
        idx = self._target_index_from_pos(pos)
        if idx < len(self._cards) and idx >= 0:
            geo = self._cards[idx].geometry()
            self._drop_indicator.setGeometry(geo.left() - 2, geo.top(), 3, geo.height())
            self._drop_indicator.raise_()
            self._drop_indicator.show()
        elif idx >= len(self._cards) and self._cards:
            geo = self._cards[-1].geometry()
            self._drop_indicator.setGeometry(geo.right() - 1, geo.top(), 3, geo.height())
            self._drop_indicator.raise_()
            self._drop_indicator.show()
        else:
            self._drop_indicator.hide()

    def _target_index_from_pos(self, container_pos: QPoint) -> int:
        if not self._cards:
            return 0
        best_i = 0
        best_d = float("inf")
        for i, c in enumerate(self._cards):
            d = (container_pos - c.geometry().center()).manhattanLength()
            if d < best_d:
                best_d = d
                best_i = i
        g = self._cards[best_i].geometry()
        if container_pos.x() < g.center().x():
            return best_i
        else:
            return best_i + 1

    def add_page(self, index: int, image: np.ndarray) -> ThumbnailCard:
        card = ThumbnailCard(index, image)
        card.clicked.connect(self._on_clicked)
        card.cut_toggled.connect(self.cut_toggled)
        card.delete_requested.connect(self.page_deleted)
        card.fullscreen_requested.connect(self.fullscreen_requested)
        card.checked_toggled.connect(self._on_checked_toggled)
        card.bookmark_clicked.connect(self._on_card_bookmark)
        self._cards.append(card)
        i = len(self._cards) - 1
        self._grid.addWidget(card, i // self._cols, i % self._cols)
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        return card

    def _on_card_bookmark(self, index: int):
        card = self._card(index)
        current = card._bookmark_lbl.text() if card and card._bookmark_lbl.isVisible() else ""
        text, ok = QInputDialog.getText(
            self, "Marcador", "Nombre del marcador (vacío para quitar):", text=current)
        if ok:
            self.bookmark_requested.emit(index, text.strip())

    def _on_checked_toggled(self, index: int, checked: bool):
        if checked:
            self._checked.add(index)
        else:
            self._checked.discard(index)
        self.checked_changed.emit(self._checked.copy())

    def check_all(self):
        for card in self._cards:
            card.set_checked(True)
            self._checked.add(card.page_index)
        self.checked_changed.emit(self._checked.copy())

    def uncheck_all(self):
        for card in self._cards:
            card.set_checked(False)
        self._checked.clear()
        self.checked_changed.emit(set())

    def get_checked_indices(self) -> set[int]:
        return self._checked.copy()

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

    def set_bookmark(self, index: int, label: str):
        c = self._card(index)
        if c:
            c.set_bookmark(label)

    def reorder_cards(self, from_idx: int, to_idx: int):
        if from_idx == to_idx:
            return
        if 0 <= from_idx < len(self._cards) and 0 <= to_idx <= len(self._cards):
            card = self._cards.pop(from_idx)
            self._cards.insert(to_idx, card)
            for i, c in enumerate(self._cards):
                c.page_index = i
                c._num.setText(str(i + 1))
            self._relayout()

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
        self._checked.clear()

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
