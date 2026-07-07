"""Widgets reutilizables."""
from __future__ import annotations
from collections import OrderedDict
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QLabel, QFrame, QWidget, QScrollArea, QGridLayout,
    QVBoxLayout, QHBoxLayout, QSizePolicy, QPushButton,
    QMenu, QToolBar, QRubberBand, QCheckBox, QApplication,
    QInputDialog, QDialog, QMessageBox, QProgressBar, QListWidget, QListWidgetItem,
    QPlainTextEdit, QLineEdit, QSpinBox, QStackedWidget, QDialogButtonBox,
    QListView, QAbstractItemView, QStyledItemDelegate,
)
from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint, QMimeData, QEvent, QTimer, QModelIndex, QAbstractListModel
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QDrag, QPainter, QWheelEvent, QDesktopServices, QIntValidator, QPen, QColor, QFont
from PySide6.QtCore import QUrl

from utils.image_utils import ndarray_to_qpixmap
from models.config_model import ConfigModel
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
        self._zoom_enabled = False
        self._zoom_level = 1.0
        self._panning = False
        self._pan_start = QPoint()
        self._zoom_cache: dict[tuple[int, int], QPixmap] = {}

    def set_pixmap(self, pixmap: QPixmap | None):
        self._zoom_cache.clear()
        self._pixmap = pixmap
        if pixmap is None:
            self.setText("Sin imagen")
            return
        self.setText("")
        if not self._zoom_enabled:
            self._zoom_level = 1.0
        self._panning = False
        self._rescale()

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

    def set_zoom_enabled(self, enabled: bool):
        self._zoom_enabled = enabled
        if not enabled:
            self._zoom_level = 1.0
            self._panning = False
        self._rescale()

    def zoom_in(self):
        if self._zoom_enabled:
            self._zoom_level = min(self._zoom_level * 1.4, 10.0)
            self._rescale()

    def zoom_out(self):
        if self._zoom_enabled:
            self._zoom_level = max(self._zoom_level / 1.4, 0.2)
            self._rescale()

    def zoom_fit(self):
        if self._zoom_enabled:
            self._zoom_level = 1.0
            self._panning = False
            self._rescale()

    def set_image(self, image: np.ndarray | None):
        self._zoom_cache.clear()
        if image is None:
            self.set_pixmap(None)
            self.setText("Sin imagen")
            if self._rubber_band:
                self._rubber_band.deleteLater()
                self._rubber_band = None
            if self._preview_band:
                self._preview_band.deleteLater()
                self._preview_band = None
            if self._debug_band:
                self._debug_band.deleteLater()
                self._debug_band = None
            return
        self.set_pixmap(ndarray_to_qpixmap(image))

    def wheelEvent(self, event: QWheelEvent):
        if self._zoom_enabled and event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self._zoom_enabled and self._zoom_level > 1.0 and event.button() == Qt.LeftButton and not self._selecting and self._pixmap:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if self._selecting and event.button() == Qt.LeftButton and self._pixmap:
            self._origin = event.pos()
            if not self._rubber_band:
                self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(QRect(self._origin, QSize()))
            self._rubber_band.show()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            scroll = self._find_scroll_area()
            if scroll:
                hsb = scroll.horizontalScrollBar()
                vsb = scroll.verticalScrollBar()
                hsb.setValue(hsb.value() - delta.x())
                vsb.setValue(vsb.value() - delta.y())
            return
        if self._selecting and self._rubber_band and self._rubber_band.isVisible():
            rect = QRect(self._origin, event.pos()).normalized()
            self._rubber_band.setGeometry(rect)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() == Qt.LeftButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return
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

    def _find_scroll_area(self):
        p = self.parent()
        while p:
            if isinstance(p, QScrollArea):
                return p
            p = p.parent()
        return None

    def _pixmap_rect(self) -> QRect:
        if not self._pixmap:
            return QRect()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw == 0 or ph == 0:
            return QRect()
        if self._zoom_enabled:
            pix = self.pixmap()
            if pix:
                return QRect(0, 0, pix.width(), pix.height())
            return QRect(0, 0, pw, ph)
        sw, sh = self.width(), self.height()
        scale = min(sw / pw, sh / ph, 1.0)
        dw, dh = int(pw * scale), int(ph * scale)
        x = (sw - dw) // 2
        y = (sh - dh) // 2
        return QRect(x, y, dw, dh)

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

    def _viewport_size(self) -> tuple[int, int]:
        scroll = self._find_scroll_area()
        if scroll:
            vp = scroll.viewport()
            return vp.width(), vp.height()
        return self.width(), self.height()

    def _rescale(self):
        if not self._pixmap:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if self._zoom_enabled:
            sw, sh = self._viewport_size()
            fit_scale = min(sw / pw, sh / ph, 1.0)
            scale = fit_scale * self._zoom_level
            new_w = max(1, int(pw * scale))
            new_h = max(1, int(ph * scale))
            key = (id(self._pixmap), new_w, new_h)
            if key in self._zoom_cache:
                scaled = self._zoom_cache[key]
            else:
                scaled = self._pixmap.scaled(
                    new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._zoom_cache[key] = scaled
            QLabel.setPixmap(self, scaled)
            self.setFixedSize(new_w, new_h)
        else:
            QLabel.setPixmap(self, self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.setMinimumSize(0, 0)
            self.setMaximumSize(QSize(16777215, 16777215))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()
        self._update_preview_band()
        self._update_debug_band()


class BookmarkDialog(QDialog):
    def __init__(self, parent, page_index: int, current: list[tuple[int, str]]):
        super().__init__(parent)
        self.setWindowTitle(f"Marcadores — Página {page_index + 1}")
        self.setMinimumSize(420, 320)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.setDefaultDropAction(Qt.MoveAction)
        self._list.setStyleSheet(
            f"QListWidget {{ background:{SURFACE2}; border:1px solid {BORDER}; "
            f"border-radius:6px; padding:4px; }}"
            f"QListWidget::item {{ padding:6px 10px; border-radius:4px; }}"
            f"QListWidget::item:selected {{ background:{SURFACE3}; }}"
        )
        layout.addWidget(QLabel("Arrastra para reordenar:"))
        layout.addWidget(self._list, 1)

        for level, title in current:
            item = QListWidgetItem(self._format_item(level, title))
            item.setData(Qt.UserRole, (level, title))
            self._list.addItem(item)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Añadir")
        btn_add.setFixedHeight(30)
        btn_add.clicked.connect(self._add)
        btn_edit = QPushButton("✏️ Editar")
        btn_edit.setFixedHeight(30)
        btn_edit.clicked.connect(self._edit)
        btn_remove = QPushButton("🗑️ Quitar")
        btn_remove.setFixedHeight(30)
        btn_remove.clicked.connect(self._remove)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _format_item(level: int, title: str) -> str:
        prefix = "├─ " * (level - 1) + "• " if level > 1 else ""
        return f"{prefix}{title}"

    def _add(self):
        dlg = _BookmarkItemDialog(self, titulo="", nivel=1)
        if dlg.exec() == QDialog.Accepted:
            level, title = dlg.get_values()
            item = QListWidgetItem(self._format_item(level, title))
            item.setData(Qt.UserRole, (level, title))
            self._list.addItem(item)

    def _edit(self):
        item = self._list.currentItem()
        if not item:
            return
        level, title = item.data(Qt.UserRole)
        dlg = _BookmarkItemDialog(self, titulo=title, nivel=level)
        if dlg.exec() == QDialog.Accepted:
            level, title = dlg.get_values()
            item.setText(self._format_item(level, title))
            item.setData(Qt.UserRole, (level, title))

    def _remove(self):
        item = self._list.currentItem()
        if item:
            self._list.takeItem(self._list.row(item))

    def get_bookmarks(self) -> list[tuple[int, str]]:
        result = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            result.append(item.data(Qt.UserRole))
        return result


class _BookmarkItemDialog(QDialog):
    def __init__(self, parent, titulo: str = "", nivel: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Marcador")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Nivel:"))
        self._level = QSpinBox()
        self._level.setRange(1, 9)
        self._level.setValue(nivel)
        layout.addWidget(self._level)

        layout.addWidget(QLabel("Título:"))
        self._title = QLineEdit(titulo)
        layout.addWidget(self._title)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[int, str]:
        return self._level.value(), self._title.text().strip()


class CommentDialog(QDialog):
    def __init__(self, parent, page_index: int, current: str, image=None):
        super().__init__(parent)
        self.setWindowTitle(f"Comentario — Página {page_index + 1}")
        self.setMinimumSize(400, 350)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self._editor = QPlainTextEdit(current)
        self._editor.setPlaceholderText("Escribe un comentario para esta página…")
        self._editor.setFixedHeight(120)
        layout.addWidget(self._editor)

        self._char_counter = QLabel(f"Caracteres: {len(current)}/500")
        self._char_counter.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none;")
        layout.addWidget(self._char_counter)
        self._editor.textChanged.connect(self._on_text_changed)

        self._preview_check = QCheckBox("Mostrar vista previa")
        self._preview_check.toggled.connect(self._toggle_preview)
        layout.addWidget(self._preview_check)

        self._preview_lbl = QLabel()
        self._preview_lbl.setFixedHeight(120)
        self._preview_lbl.setAlignment(Qt.AlignCenter)
        self._preview_lbl.setStyleSheet(
            f"background:{SURFACE2}; border:1px solid {BORDER}; border-radius:6px;")
        self._preview_lbl.setVisible(False)
        layout.addWidget(self._preview_lbl)

        self._image = image

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_text_changed(self):
        text = self._editor.toPlainText()
        if len(text) > 500:
            self._editor.blockSignals(True)
            self._editor.setPlainText(text[:500])
            self._editor.moveCursor(self._editor.textCursor().End)
            self._editor.blockSignals(False)
            text = text[:500]
        self._char_counter.setText(f"Caracteres: {len(text)}/500")
        if self._preview_check.isChecked() and self._image is not None:
            self._render_preview(text)

    def _toggle_preview(self, checked: bool):
        if checked and self._image is not None:
            self._render_preview(self._editor.toPlainText())
        self._preview_lbl.setVisible(checked)

    def _render_preview(self, text: str):
        from utils.image_utils import overlay_comment
        img = overlay_comment(self._image, text)
        h, w = img.shape[:2]
        scale = min(380 / w, 110 / h, 1.0)
        if scale < 1.0:
            import cv2
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        px = ndarray_to_qpixmap(img)
        self._preview_lbl.setPixmap(px)

    def get_comment(self) -> str:
        return self._editor.toPlainText().strip()


class FullscreenViewer(QDialog):
    bookmark_changed = Signal(int, list)
    comment_changed  = Signal(int, str)

    def __init__(self, pages_data: list, start: int = 0, parent=None, config: ConfigModel | None = None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Vista completa")
        self.resize(1000, 750)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._pages = pages_data
        self._idx   = start
        self._dual_mode = False
        self._config = config

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")
        self._viewer = ImageViewer()
        self._viewer.set_zoom_enabled(True)
        self._scroll.setWidget(self._viewer)
        main_layout.addWidget(self._scroll, 1)

        self._bm_sidebar = self._build_bookmark_sidebar()
        self._bm_sidebar.setVisible(False)
        main_layout.addWidget(self._bm_sidebar)

        self._cm_sidebar = self._build_comment_sidebar()
        self._cm_sidebar.setVisible(False)
        main_layout.addWidget(self._cm_sidebar)

        self._build_main_sidebar()
        main_layout.addWidget(self._sidebar)

        self._setup_shortcuts()
        self._pixmap_cache: OrderedDict[int, QPixmap] = OrderedDict()
        self._MAX_CACHE = 10
        self._cm_thumb: np.ndarray | None = None
        self._cm_preview_timer = QTimer(self)
        self._cm_preview_timer.setSingleShot(True)
        self._cm_preview_timer.setInterval(120)
        self._cm_preview_timer.timeout.connect(self._cm_do_preview)
        self._show_current()

    # ── Bookmark sidebar ──

    def _build_bookmark_sidebar(self):
        f = QFrame()
        f.setFixedWidth(280)
        f.setStyleSheet(f"background:{SURFACE2}; border-right:1px solid {BORDER};")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(40)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        self._bm_title = QLabel()
        self._bm_title.setStyleSheet(
            f"color:{TEXT}; font-weight:bold; font-size:10pt; border:none; background:transparent;")
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none; border-radius:4px; "
            f"color:{TEXT}; font-size:11pt; }}"
            f"QPushButton:hover {{ background:{SURFACE3}; }}")
        btn_close.clicked.connect(self._hide_bookmark_sidebar)
        hl.addWidget(self._bm_title)
        hl.addStretch()
        hl.addWidget(btn_close)
        lay.addWidget(hdr)
        lay.addWidget(self._sep())

        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(12, 12, 12, 12)
        wl.setSpacing(6)

        lbl = QLabel("Arrastra para reordenar:")
        lbl.setStyleSheet(f"color:{TEXT_SEC}; font-size:9pt; border:none; background:transparent;")
        wl.addWidget(lbl)

        self._bm_list = QListWidget()
        self._bm_list.setDragDropMode(QListWidget.InternalMove)
        self._bm_list.setDefaultDropAction(Qt.MoveAction)
        self._bm_list.setStyleSheet(
            f"QListWidget {{ background:{SURFACE3}; border:1px solid {BORDER}; "
            f"border-radius:6px; padding:4px; }}"
            f"QListWidget::item {{ padding:6px 10px; border-radius:4px; color:{TEXT}; }}"
            f"QListWidget::item:selected {{ background:{SURFACE}; }}")
        wl.addWidget(self._bm_list, 1)

        bl = QHBoxLayout()
        bl.setSpacing(4)
        b_add = QPushButton("➕ Añadir")
        b_add.setFixedHeight(30)
        b_add.clicked.connect(self._bm_add)
        b_ed = QPushButton("✏️ Editar")
        b_ed.setFixedHeight(30)
        b_ed.clicked.connect(self._bm_edit)
        b_rm = QPushButton("🗑️ Quitar")
        b_rm.setFixedHeight(30)
        b_rm.clicked.connect(self._bm_remove)
        for b in (b_add, b_ed, b_rm):
            b.setStyleSheet(
                f"QPushButton {{ background:{SURFACE3}; border:1px solid {BORDER}; "
                f"border-radius:4px; color:{TEXT}; }}"
                f"QPushButton:hover {{ background:{SURFACE}; }}")
        bl.addWidget(b_add)
        bl.addWidget(b_ed)
        bl.addWidget(b_rm)
        bl.addStretch()
        wl.addLayout(bl)

        lay.addWidget(w, 1)
        return f

    # ── Comment sidebar ──

    def _build_comment_sidebar(self):
        f = QFrame()
        f.setFixedWidth(280)
        f.setStyleSheet(f"background:{SURFACE2}; border-right:1px solid {BORDER};")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(40)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        self._cm_title = QLabel()
        self._cm_title.setStyleSheet(
            f"color:{TEXT}; font-weight:bold; font-size:10pt; border:none; background:transparent;")
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none; border-radius:4px; "
            f"color:{TEXT}; font-size:11pt; }}"
            f"QPushButton:hover {{ background:{SURFACE3}; }}")
        btn_close.clicked.connect(self._hide_comment_sidebar)
        hl.addWidget(self._cm_title)
        hl.addStretch()
        hl.addWidget(btn_close)
        lay.addWidget(hdr)
        lay.addWidget(self._sep())

        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(12, 12, 12, 12)
        wl.setSpacing(6)

        self._cm_editor = QPlainTextEdit()
        self._cm_editor.setPlaceholderText("Escribe un comentario para esta página…")
        self._cm_editor.setFixedHeight(120)
        self._cm_editor.setStyleSheet(
            f"QPlainTextEdit {{ background:{SURFACE3}; color:{TEXT}; "
            f"border:1px solid {BORDER}; border-radius:6px; padding:8px; }}")
        wl.addWidget(self._cm_editor)

        self._cm_counter = QLabel("Caracteres: 0/500")
        self._cm_counter.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:8pt; border:none; background:transparent;")
        wl.addWidget(self._cm_counter)
        self._cm_editor.textChanged.connect(self._cm_on_text_changed)

        self._cm_preview_check = QCheckBox("Mostrar vista previa")
        self._cm_preview_check.setStyleSheet(
            f"QCheckBox {{ color:{TEXT}; border:none; background:transparent; }}"
            f"QCheckBox::indicator {{ width:14px; height:14px; }}")
        self._cm_preview_check.toggled.connect(self._cm_toggle_preview)
        wl.addWidget(self._cm_preview_check)

        self._cm_preview_lbl = QLabel()
        self._cm_preview_lbl.setFixedHeight(120)
        self._cm_preview_lbl.setAlignment(Qt.AlignCenter)
        self._cm_preview_lbl.setStyleSheet(
            f"background:{SURFACE3}; border:1px solid {BORDER}; border-radius:6px;")
        self._cm_preview_lbl.setVisible(False)
        wl.addWidget(self._cm_preview_lbl)

        cn = QHBoxLayout()
        prev_cm = QPushButton("◀ Anterior")
        prev_cm.setFixedHeight(28)
        prev_cm.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid {BORDER}; "
            f"border-radius:4px; color:{INFO}; font-size:8pt; }}"
            f"QPushButton:hover {{ background:{SURFACE3}; }}")
        prev_cm.clicked.connect(self._prev_comment)
        next_cm = QPushButton("Siguiente ▶")
        next_cm.setFixedHeight(28)
        next_cm.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid {BORDER}; "
            f"border-radius:4px; color:{INFO}; font-size:8pt; }}"
            f"QPushButton:hover {{ background:{SURFACE3}; }}")
        next_cm.clicked.connect(self._next_comment)
        cn.addWidget(prev_cm)
        cn.addWidget(next_cm)
        wl.addLayout(cn)

        b_ok = QPushButton("✅ Aceptar")
        b_ok.setFixedHeight(34)
        b_ok.setStyleSheet(
            f"QPushButton {{ background:{ACCENT}; border:none; border-radius:6px; "
            f"color:white; font-weight:bold; }}"
            f"QPushButton:hover {{ background:#5b9cf6; }}")
        b_ok.clicked.connect(self._cm_accept)
        wl.addWidget(b_ok)
        wl.addStretch()
        lay.addWidget(w, 1)
        return f

    # ── Main sidebar ──

    def _build_main_sidebar(self):
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(80)
        self._sidebar.setStyleSheet(f"background:{SURFACE2}; border-left:1px solid {BORDER};")
        sb = QVBoxLayout(self._sidebar)
        sb.setContentsMargins(4, 8, 4, 8)
        sb.setSpacing(6)
        sb.setAlignment(Qt.AlignCenter)

        self._page_edit = QLineEdit(str(self._idx + 1))
        self._page_edit.setAlignment(Qt.AlignCenter)
        self._page_edit.setValidator(QIntValidator(1, max(len(self._pages), 1), self))
        self._page_edit.setFixedWidth(44)
        self._page_edit.setStyleSheet(
            f"QLineEdit {{ background:{SURFACE3}; color:{TEXT}; "
            f"border:1px solid {BORDER}; border-radius:4px; "
            f"padding:2px; font-size:14pt; font-weight:bold; }}")
        self._page_edit.returnPressed.connect(self._go_to_page_input)

        lbl_total = QLabel(str(len(self._pages)))
        lbl_total.setStyleSheet(
            f"color:{TEXT_DIM}; font-size:9pt; border:none; background:transparent;")

        btn_prev = QPushButton("◀")
        btn_prev.setFixedSize(44, 44)
        btn_prev.setToolTip("Página anterior (←)")
        btn_prev.clicked.connect(self._prev)
        self._style_btn(btn_prev)

        btn_next = QPushButton("▶")
        btn_next.setFixedSize(44, 44)
        btn_next.setToolTip("Siguiente página (→)")
        btn_next.clicked.connect(self._next)
        self._style_btn(btn_next)

        sb.addWidget(self._page_edit, 0, Qt.AlignCenter)
        sb.addWidget(lbl_total, 0, Qt.AlignCenter)
        sb.addWidget(btn_prev, 0, Qt.AlignCenter)
        sb.addWidget(btn_next, 0, Qt.AlignCenter)

        sb.addWidget(self._sep())

        for txt, tip, slot in [
            ("🔍−", "Alejar (Ctrl+-)", self._zoom_out),
            ("🔍+", "Acercar (Ctrl++)", self._zoom_in),
            ("🔍", "Ajustar (Ctrl+0)", self._zoom_fit),
        ]:
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            b.setFixedSize(44, 36)
            self._style_btn(b)
            sb.addWidget(b, 0, Qt.AlignCenter)

        sb.addWidget(self._sep())

        self._btn_dual = QPushButton("📄")
        self._btn_dual.setCheckable(True)
        self._btn_dual.setToolTip("Página doble (Ctrl+D)")
        self._btn_dual.toggled.connect(self._toggle_dual)
        self._btn_dual.setFixedSize(44, 36)
        self._style_btn(self._btn_dual)
        sb.addWidget(self._btn_dual, 0, Qt.AlignCenter)

        sb.addWidget(self._sep())

        self._btn_bookmark = QPushButton("🔖")
        self._btn_bookmark.setCheckable(True)
        self._btn_bookmark.setToolTip("Editar Marcadores")
        self._btn_bookmark.clicked.connect(self._toggle_bookmark_sidebar)
        self._btn_bookmark.setFixedSize(44, 36)
        self._style_btn(self._btn_bookmark)
        sb.addWidget(self._btn_bookmark, 0, Qt.AlignCenter)

        self._btn_comment = QPushButton("💬")
        self._btn_comment.setCheckable(True)
        self._btn_comment.setToolTip("Editar Comentario (Ctrl+M)")
        self._btn_comment.clicked.connect(self._toggle_comment_sidebar)
        self._btn_comment.setFixedSize(44, 36)
        self._style_btn(self._btn_comment)
        sb.addWidget(self._btn_comment, 0, Qt.AlignCenter)

        sb.addStretch()

    def _style_btn(self, btn):
        btn.setStyleSheet(
            f"QPushButton {{ background:transparent; border:1px solid transparent; "
            f"border-radius:6px; color:{TEXT}; font-size:16pt; padding:0px; }}"
            f"QPushButton:hover {{ background:{SURFACE3}; border:1px solid {BORDER}; }}"
            f"QPushButton:checked {{ background:{SURFACE3}; border:1px solid {ACCENT}; }}"
            f"QPushButton:pressed {{ background:{SURFACE}; }}")

    def _sep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setStyleSheet(f"color:{BORDER}; background:{BORDER}; border:none;")
        f.setFixedHeight(1)
        return f

    def _setup_shortcuts(self):
        bk_key = self._config.get("shortcuts", "fullscreen_bookmark", "Insert") if self._config else "Insert"
        ab_key = self._config.get("shortcuts", "fullscreen_autobookmark", "Up") if self._config else "Up"
        pairs = [
            (Qt.Key_Left,             self._prev),
            (Qt.Key_Right,            self._next),
            (Qt.CTRL | Qt.Key_Plus,   self._zoom_in),
            (Qt.CTRL | Qt.Key_Minus,  self._zoom_out),
            (Qt.CTRL | Qt.Key_0,      self._zoom_fit),
            (Qt.CTRL | Qt.Key_D,      self._btn_dual.toggle),
            (Qt.CTRL | Qt.Key_M,      self._toggle_comment_sidebar),
            (QKeySequence(bk_key),    self._quick_bookmark),
            (QKeySequence(ab_key),    self._auto_bookmark),
            (Qt.Key_Escape,           self._on_escape),
        ]
        for seq, slot in pairs:
            a = QAction(self)
            a.setShortcut(QKeySequence(seq))
            a.triggered.connect(slot)
            self.addAction(a)

    # ── Sidebar toggles ──

    def _toggle_bookmark_sidebar(self):
        v = not self._bm_sidebar.isVisible()
        self._bm_sidebar.setVisible(v)
        self._btn_bookmark.setChecked(v)
        if v:
            self._bm_title.setText(f"🔖 Marcadores — Pág {self._idx + 1}")
            self._refresh_bookmark_panel()

    def _toggle_comment_sidebar(self):
        v = not self._cm_sidebar.isVisible()
        self._cm_sidebar.setVisible(v)
        self._btn_comment.setChecked(v)
        if v:
            self._cm_title.setText(f"💬 Comentario — Pág {self._idx + 1}")
            self._refresh_comment_panel()

    def _hide_bookmark_sidebar(self):
        self._bm_sidebar.setVisible(False)
        self._btn_bookmark.setChecked(False)

    def _hide_comment_sidebar(self):
        self._cm_sidebar.setVisible(False)
        self._btn_comment.setChecked(False)

    def _on_escape(self):
        if self._bm_sidebar.isVisible():
            self._hide_bookmark_sidebar()
        elif self._cm_sidebar.isVisible():
            self._hide_comment_sidebar()
        else:
            self.close()

    # ── Bookmark panel logic ──

    def _refresh_bookmark_panel(self):
        p = self._pages[self._idx]
        self._bm_list.clear()
        bm = p.bookmarks
        if not bm and p.bookmark:
            bm = [(1, p.bookmark)]
        for lvl, title in (bm or []):
            item = QListWidgetItem(BookmarkDialog._format_item(lvl, title))
            item.setData(Qt.UserRole, (lvl, title))
            self._bm_list.addItem(item)

    def _bm_add(self):
        dlg = _BookmarkItemDialog(self, titulo="", nivel=1)
        if dlg.exec() == QDialog.Accepted:
            lvl, title = dlg.get_values()
            p = self._pages[self._idx]
            labels = list(p.bookmarks or [])
            labels.append((lvl, title))
            p.bookmarks = labels
            p.bookmark = labels[0][1] if labels else ""
            self.bookmark_changed.emit(p.index, labels)
            self._refresh_bookmark_panel()

    def _bm_edit(self):
        row = self._bm_list.currentRow()
        if row < 0:
            return
        item = self._bm_list.item(row)
        lvl, title = item.data(Qt.UserRole)
        dlg = _BookmarkItemDialog(self, titulo=title, nivel=lvl)
        if dlg.exec() == QDialog.Accepted:
            new_lvl, new_title = dlg.get_values()
            p = self._pages[self._idx]
            labels = list(p.bookmarks or [])
            if row < len(labels):
                labels[row] = (new_lvl, new_title)
            p.bookmarks = labels
            p.bookmark = labels[0][1] if labels else ""
            self.bookmark_changed.emit(p.index, labels)
            self._refresh_bookmark_panel()

    def _bm_remove(self):
        row = self._bm_list.currentRow()
        if row < 0:
            return
        item = self._bm_list.item(row)
        lvl, title = item.data(Qt.UserRole)
        disp = BookmarkDialog._format_item(lvl, title)
        confirm = QMessageBox.question(
            self, "Eliminar marcador",
            f"¿Eliminar marcador \"{disp}\"?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        p = self._pages[self._idx]
        labels = list(p.bookmarks or [])
        if row < len(labels):
            labels.pop(row)
        p.bookmarks = labels
        p.bookmark = labels[0][1] if labels else ""
        self.bookmark_changed.emit(p.index, labels)
        self._refresh_bookmark_panel()

    # ── Comment panel logic ──

    def _refresh_comment_panel(self):
        p = self._pages[self._idx]
        self._cm_editor.blockSignals(True)
        self._cm_editor.setPlainText(p.comment)
        self._cm_editor.blockSignals(False)
        self._cm_counter.setText(f"Caracteres: {len(p.comment)}/500")
        self._cm_preview_lbl.setVisible(False)
        self._cm_preview_check.setChecked(False)
        self._cm_image = p.display_image
        h, w = self._cm_image.shape[:2]
        scale = min(240 / w, 110 / h, 1.0)
        if scale < 1.0:
            self._cm_thumb = cv2.resize(
                self._cm_image, (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_AREA)
        else:
            self._cm_thumb = self._cm_image

    def _cm_on_text_changed(self):
        text = self._cm_editor.toPlainText()
        if len(text) > 500:
            self._cm_editor.blockSignals(True)
            self._cm_editor.setPlainText(text[:500])
            self._cm_editor.moveCursor(self._cm_editor.textCursor().End)
            self._cm_editor.blockSignals(False)
            text = text[:500]
        self._cm_counter.setText(f"Caracteres: {len(text)}/500")
        if self._cm_preview_check.isChecked() and self._cm_thumb is not None:
            self._cm_preview_timer.start()

    def _cm_do_preview(self):
        text = self._cm_editor.toPlainText()
        if self._cm_thumb is not None:
            self._cm_render_preview(text)

    def _cm_toggle_preview(self, checked: bool):
        if checked and self._cm_thumb is not None:
            self._cm_render_preview(self._cm_editor.toPlainText())
        self._cm_preview_lbl.setVisible(checked)

    def _cm_render_preview(self, text: str):
        from utils.image_utils import overlay_comment
        img = overlay_comment(self._cm_thumb, text)
        px = ndarray_to_qpixmap(img)
        self._cm_preview_lbl.setPixmap(px)

    def _cm_accept(self):
        p = self._pages[self._idx]
        text = self._cm_editor.toPlainText().strip()
        p.comment = text
        self.comment_changed.emit(p.index, text)
        self._hide_comment_sidebar()

    # ── Display ──

    def _toggle_dual(self, checked: bool):
        self._dual_mode = checked
        self._show_current()

    def _go_to_page_input(self):
        text = self._page_edit.text().strip()
        try:
            page = int(text)
        except ValueError:
            page = self._idx + 1
        page = max(1, min(page, len(self._pages)))
        self._idx = page - 1
        self._show_current()

    def _show_current(self):
        if not self._pages:
            return
        key: int | tuple = self._idx
        if self._dual_mode:
            key = (self._idx, True)
        if key in self._pixmap_cache:
            self._pixmap_cache.move_to_end(key)
            self._viewer.set_pixmap(self._pixmap_cache[key])
        elif self._dual_mode:
            self._show_dual()
        else:
            p = self._pages[self._idx]
            px = ndarray_to_qpixmap(p.display_image)
            self._pixmap_cache[key] = px
            if len(self._pixmap_cache) > self._MAX_CACHE:
                self._pixmap_cache.popitem(last=False)
            self._viewer.set_pixmap(px)
        self._page_edit.setText(str(self._idx + 1))
        if self._bm_sidebar.isVisible():
            self._bm_title.setText(f"🔖 Marcadores — Pág {self._idx + 1}")
            self._refresh_bookmark_panel()
        if self._cm_sidebar.isVisible():
            self._cm_title.setText(f"💬 Comentario — Pág {self._idx + 1}")
            self._refresh_comment_panel()

    def _show_dual(self):
        p1 = self._pages[self._idx]
        img1 = p1.display_image
        h1, w1 = img1.shape[:2]
        if self._idx + 1 < len(self._pages):
            p2 = self._pages[self._idx + 1]
            img2 = p2.display_image
            h2, w2 = img2.shape[:2]
            target_h = max(h1, h2)
            if h1 != target_h:
                s = target_h / h1
                img1 = cv2.resize(img1, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if h2 != target_h:
                s = target_h / h2
                img2 = cv2.resize(img2, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            img = np.hstack([img1, img2])
        else:
            img = img1
        px = ndarray_to_qpixmap(img)
        key = (self._idx, True)
        self._pixmap_cache[key] = px
        if len(self._pixmap_cache) > self._MAX_CACHE:
            self._pixmap_cache.popitem(last=False)
        self._viewer.set_pixmap(px)

    def _quick_bookmark(self):
        p = self._pages[self._idx]
        text, ok = QInputDialog.getText(
            self, "Marcador rápido",
            "Nombre del marcador (nivel 1):",
            text=p.bookmark)
        if ok:
            label = text.strip()
            labels = [(1, label)] if label else []
            p.bookmarks = labels
            p.bookmark = label
        self.bookmark_changed.emit(p.index, labels)
        self._refresh_bookmark_panel()

    def _auto_bookmark(self):
        p = self._pages[self._idx]
        last_num = None
        for i in range(self._idx - 1, -1, -1):
            prev = self._pages[i]
            bm = prev.bookmark
            if bm and bm.strip():
                try:
                    last_num = int(bm.strip())
                    break
                except ValueError:
                    pass
        if last_num is None:
            return
        label = str(last_num + 1)
        labels = [(1, label)]
        p.bookmarks = labels
        p.bookmark = label
        self.bookmark_changed.emit(p.index, labels)
        self._refresh_bookmark_panel()

    # ── Navigation ──

    def _prev_comment(self):
        for i in range(self._idx - 1, -1, -1):
            if self._pages[i].comment:
                self._idx = i
                self._show_current()
                return

    def _next_comment(self):
        for i in range(self._idx + 1, len(self._pages)):
            if self._pages[i].comment:
                self._idx = i
                self._show_current()
                return

    def _zoom_in(self):
        self._viewer.zoom_in()

    def _zoom_out(self):
        self._viewer.zoom_out()

    def _zoom_fit(self):
        self._viewer.zoom_fit()

    def _prev(self):
        if self._idx > 0:
            step = 2 if self._dual_mode else 1
            if self._idx - step >= 0:
                self._idx -= step
                self._show_current()

    def _next(self):
        step = 2 if self._dual_mode else 1
        if self._idx + step < len(self._pages):
            self._idx += step
            self._show_current()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()
            event.accept()
            return
        super().wheelEvent(event)


class ProcessItem(QFrame):
    def __init__(self, job_id: str, label: str, total: int, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.setFixedHeight(60)
        self.setStyleSheet(f"background:{SURFACE2}; border:none; border-radius:6px;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)

        info = QWidget()
        info.setStyleSheet("border:none; background:transparent;")
        iv = QVBoxLayout(info)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(4)

        self._title = QLabel(label)
        self._title.setStyleSheet("font-size:9pt; border:none;")
        iv.addWidget(self._title)

        self._prog = QProgressBar()
        self._prog.setFixedHeight(4)
        self._prog.setTextVisible(False)
        self._prog.setRange(0, max(total, 1))
        self._prog.setValue(0)
        iv.addWidget(self._prog)

        self._status = QLabel("En cola…")
        self._status.setStyleSheet(f"font-size:8pt; color:{TEXT_DIM}; border:none;")
        iv.addWidget(self._status)
        lay.addWidget(info, 1)

        self._btn = QPushButton("✕")
        self._btn.setFixedSize(24, 24)
        self._btn.setVisible(False)
        lay.addWidget(self._btn)

    def update(self, current: int, total: int, status_text: str,
               status_color: str = TEXT_DIM, done: bool = False):
        self._prog.setMaximum(max(total, 1))
        self._prog.setValue(current)
        self._status.setText(status_text)
        self._status.setStyleSheet(f"font-size:8pt; color:{status_color}; border:none;")


class ProcessListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Procesos activos")
        self.resize(480, 360)
        self.setAttribute(Qt.WA_DeleteOnClose)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        title = QLabel("Procesos en ejecución")
        title.setStyleSheet("font-size:13pt; font-weight:bold; border:none;")
        root.addWidget(title)

        self._placeholder = QLabel("Sin procesos activos")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(f"color:{TEXT_DIM}; font-size:10pt; border:none;")
        root.addWidget(self._placeholder)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")

        self._content = QWidget()
        self._content.setStyleSheet("border:none; background:transparent;")
        self._list = QVBoxLayout(self._content)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(6)
        self._list.addStretch()
        scroll.setWidget(self._content)
        root.addWidget(scroll, 1)

        btn_close = QPushButton("Cerrar")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self.accept)
        root.addWidget(btn_close)

        self._items: dict[str, ProcessItem] = {}

    def add_job(self, job_id: str, label: str, total: int):
        self._placeholder.setVisible(False)
        item = ProcessItem(job_id, label, total)
        self._items[job_id] = item
        self._list.insertWidget(self._list.count() - 1, item)

    def update_job(self, job_id: str, current: int, total: int):
        item = self._items.get(job_id)
        if item:
            item.update(current, total, f"{current}/{total} páginas")

    def set_job_done(self, job_id: str, path: str):
        item = self._items.get(job_id)
        if item:
            item.update(1, 1, "Completado", TEXT_DIM, done=True)
            item._btn.setVisible(True)

    def set_job_error(self, job_id: str, msg: str):
        item = self._items.get(job_id)
        if item:
            item.update(0, 1, f"Error: {msg}", DANGER)

    def set_job_cancelled(self, job_id: str):
        item = self._items.get(job_id)
        if item:
            item.update(0, 1, "Cancelado", TEXT_DIM)

    def remove_job(self, job_id: str):
        item = self._items.pop(job_id, None)
        if item:
            self._list.removeWidget(item)
            item.deleteLater()
        if not self._items:
            self._placeholder.setVisible(True)


THUMB_W, THUMB_H = 140, 196
CARD_W = THUMB_W + 30
CARD_H = THUMB_H + 80

_PIXMAP_ROLE = Qt.UserRole + 1
_SERIAL_ROLE = Qt.UserRole + 2
_CONFIDENCE_ROLE = Qt.UserRole + 3
_BOOKMARK_ROLE = Qt.UserRole + 4
_COMMENT_ROLE = Qt.UserRole + 5
_CHECKED_ROLE = Qt.UserRole + 6
_CUT_ROLE = Qt.UserRole + 7
_SELECTED_ROLE = Qt.UserRole + 8


class _PageItem:
    __slots__ = ('index', 'image', 'serial', 'confidence', 'bookmark_labels',
                 'bookmark_display', 'comment', 'checked', 'is_cut', 'selected', '_pixmap')

    def __init__(self, index: int, image: np.ndarray | None):
        self.index = index
        self.image = image
        self.serial = ''
        self.confidence = 0.0
        self.bookmark_labels: list[tuple[int, str]] = []
        self.bookmark_display = ''
        self.comment = ''
        self.checked = False
        self.is_cut = False
        self.selected = False
        self._pixmap: QPixmap | None = None


class ThumbnailModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[_PageItem] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == _PIXMAP_ROLE:
            if item._pixmap is None and item.image is not None:
                item._pixmap = _make_thumbnail_pixmap(item.image)
            return item._pixmap
        if role == Qt.DisplayRole or role == _SERIAL_ROLE:
            return item.serial
        if role == _CONFIDENCE_ROLE:
            return item.confidence
        if role == _BOOKMARK_ROLE:
            return item.bookmark_display
        if role == _COMMENT_ROLE:
            return item.comment
        if role == _CHECKED_ROLE:
            return item.checked
        if role == _CUT_ROLE:
            return item.is_cut
        if role == _SELECTED_ROLE:
            return item.selected
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or index.row() >= len(self._items):
            return False
        item = self._items[index.row()]
        if role == _CHECKED_ROLE:
            item.checked = bool(value)
            self.dataChanged.emit(index, index, [role])
            return True
        if role == _SELECTED_ROLE:
            item.selected = bool(value)
            self.dataChanged.emit(index, index, [role])
            return True
        if role == _CUT_ROLE:
            item.is_cut = bool(value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    # ---- Public mutations ----

    def add_page(self, index: int, image: np.ndarray) -> int:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(_PageItem(index, image))
        self.endInsertRows()
        return row

    def remove_page(self, index: int):
        for i, item in enumerate(self._items):
            if item.index == index:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._items.pop(i)
                self.endRemoveRows()
                self._renumber()
                return

    def update_image(self, index: int, image: np.ndarray):
        item = self._by_index(index)
        if item is None:
            return
        item.image = image
        item._pixmap = None
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [_PIXMAP_ROLE])

    def set_serial(self, index: int, serial: str, confidence: float):
        item = self._by_index(index)
        if item is None:
            return
        item.serial = serial
        item.confidence = confidence
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0),
                              [_SERIAL_ROLE, _CONFIDENCE_ROLE])

    def set_cut(self, index: int, is_cut: bool):
        item = self._by_index(index)
        if item is None:
            return
        item.is_cut = is_cut
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [_CUT_ROLE])

    def set_bookmark(self, index: int, display: str):
        item = self._by_index(index)
        if item is None:
            return
        item.bookmark_display = display
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [_BOOKMARK_ROLE])

    def set_bookmarks(self, index: int, labels: list[tuple[int, str]]):
        item = self._by_index(index)
        if item is None:
            return
        item.bookmark_labels = labels
        first = labels[0][1] if labels else ''
        n = len(labels)
        item.bookmark_display = f"{first} 📑{n}" if n > 1 else first
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [_BOOKMARK_ROLE])

    def set_checked(self, index: int, checked: bool):
        item = self._by_index(index)
        if item is None:
            return
        item.checked = checked
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [_CHECKED_ROLE])

    def set_selected(self, index: int, selected: bool):
        item = self._by_index(index)
        if item is None:
            return
        item.selected = selected
        row = self._items.index(item)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [_SELECTED_ROLE])

    def set_all_checked(self, checked: bool):
        for item in self._items:
            item.checked = checked
        n = len(self._items)
        if n:
            self.dataChanged.emit(self.index(0, 0), self.index(n - 1, 0), [_CHECKED_ROLE])

    def clear_all(self):
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def reorder(self, from_idx: int, to_idx: int):
        if from_idx == to_idx:
            return
        n = len(self._items)
        if not (0 <= from_idx < n and 0 <= to_idx <= n):
            return
        dest = to_idx if to_idx > from_idx else from_idx
        self.beginMoveRows(QModelIndex(), from_idx, from_idx, QModelIndex(), dest)
        item = self._items.pop(from_idx)
        self._items.insert(to_idx, item)
        self.endMoveRows()
        self._renumber()

    def _renumber(self):
        for i, item in enumerate(self._items):
            item.index = i

    def _by_index(self, index: int) -> _PageItem | None:
        for item in self._items:
            if item.index == index:
                return item
        return None


def _make_thumbnail_pixmap(image: np.ndarray) -> QPixmap:
    h, w = image.shape[:2]
    if w > THUMB_W or h > THUMB_H:
        scale = min(THUMB_W / w, THUMB_H / h)
        nw = max(1, int(w * scale))
        nh = max(1, int(h * scale))
        image = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
    return ndarray_to_qpixmap(image)


class ThumbnailDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._font_num = QFont()
        self._font_num.setPointSize(8)
        self._font_bm = QFont()
        self._font_bm.setPointSize(7)
        self._font_ser = QFont()
        self._font_ser.setPointSize(8)
        self._font_ser.setBold(True)

    def paint(self, painter, option, index):
        model = index.model()
        is_cut = bool(model.data(index, _CUT_ROLE) or False)
        is_sel = bool(model.data(index, _SELECTED_ROLE) or False)
        is_chk = bool(model.data(index, _CHECKED_ROLE) or False)
        serial = model.data(index, _SERIAL_ROLE) or ''
        conf = model.data(index, _CONFIDENCE_ROLE) or 0.0
        bm = model.data(index, _BOOKMARK_ROLE) or ''
        comment = model.data(index, _COMMENT_ROLE) or ''
        pix = model.data(index, _PIXMAP_ROLE)

        r = option.rect
        cx = r.x() + 8
        cy = r.y() + 8
        cw = r.width() - 16
        ch = r.height() - 16

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # background + border
        if is_cut:
            brd = QColor(WARNING)
            bg = QColor(SURFACE)
        elif is_sel:
            brd = QColor(SURFACE3)
            bg = QColor(SURFACE2)
        else:
            brd = QColor(0, 0, 0, 0)
            bg = QColor(SURFACE)
        painter.setBrush(bg)
        painter.setPen(QPen(brd, 2 if (is_cut or is_sel) else 1))
        painter.drawRoundedRect(cx, cy, cw, ch, 8, 8)

        # header: page number
        painter.setPen(QColor(TEXT_DIM))
        painter.setFont(self._font_num)
        painter.drawText(cx + 8, cy + 4, cw - 24, 16,
                         Qt.AlignLeft | Qt.AlignVCenter, str(index.row() + 1))

        # checkbox
        check_rect = QRect(cx + cw - 22, cy + 5, 16, 16)
        _draw_checkbox(painter, check_rect, is_chk)

        # thumbnail area
        tx = cx + 4
        ty = cy + 24
        tw = cw - 8
        th = THUMB_H
        painter.setBrush(QColor(SURFACE2))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(tx, ty, tw, th, 4, 4)

        if pix is not None and not pix.isNull():
            scaled = pix.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            ox = tx + (tw - scaled.width()) // 2
            oy = ty + (th - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

        # bookmark
        bm_y = ty + th + 4
        if bm:
            painter.setPen(QColor(INFO))
            painter.setFont(self._font_bm)
            r_bm = QRect(cx + 4, bm_y, cw - 8, 16)
            painter.drawText(r_bm, Qt.AlignCenter, bm)

        # serial
        if serial:
            ser_y = bm_y + (18 if bm else 4)
            s_color = SUCCESS if conf >= 0.7 else (WARNING if conf > 0 else TEXT_SEC)
            painter.setPen(QColor(s_color))
            painter.setFont(self._font_ser)
            r_ser = QRect(cx + 4, ser_y, cw - 8, 18)
            painter.drawText(r_ser, Qt.AlignCenter, serial)

        # comment dot
        if comment:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(INFO))
            painter.drawEllipse(cx + cw - 14, cy + 24, 8, 8)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(CARD_W, CARD_H)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            r = option.rect
            cx = r.x() + 8
            cy = r.y() + 8
            cw = r.width() - 16
            check_rect = QRect(cx + cw - 22, cy + 5, 16, 16)
            if check_rect.contains(event.pos()):
                checked = bool(model.data(index, _CHECKED_ROLE) or False)
                model.setData(index, not checked, _CHECKED_ROLE)
                return True
        return super().editorEvent(event, model, option, index)


def _draw_checkbox(painter, rect, checked):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(BORDER), 1))
    painter.setBrush(QColor(BG) if not checked else QColor(ACCENT))
    painter.drawRoundedRect(rect, 3, 3)
    if checked:
        painter.setPen(QPen(QColor(TEXT), 2))
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        painter.drawLine(x + 3, y + h // 2, x + w // 2, y + h - 3)
        painter.drawLine(x + w // 2, y + h - 3, x + w - 3, y + 3)
    painter.restore()


class ThumbnailGrid(QListView):
    page_selected        = Signal(int)
    cut_toggled          = Signal(int)
    page_deleted         = Signal(int)
    fullscreen_requested = Signal(int)
    reorder_requested    = Signal(int, int)
    bookmark_requested   = Signal(int, list)
    comment_requested    = Signal(int, str)
    checked_changed      = Signal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ThumbnailModel(self)
        self.setModel(self._model)

        self._delegate = ThumbnailDelegate(self)
        self.setItemDelegate(self._delegate)

        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setGridSize(QSize(CARD_W, CARD_H))
        self.setSpacing(8)
        self.setMovement(QListView.Static)

        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

        self._selected: int = -1
        self._checked: set[int] = set()

        self._drop_indicator = QFrame(self.viewport())
        self._drop_indicator.setStyleSheet(f"background:{INFO}; border:none; border-radius:1px;")
        self._drop_indicator.setFixedWidth(3)
        self._drop_indicator.hide()

        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)
        self._model.dataChanged.connect(self._on_model_data_changed)
        self.viewport().installEventFilter(self)

    # ---- Drag / Drop ----

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
            to_idx = self._target_index_from_pos(event.pos())
            event.setDropAction(Qt.MoveAction)
            event.accept()
            self._drop_indicator.hide()
            if from_idx != to_idx:
                self.reorder_requested.emit(from_idx, to_idx)
        else:
            event.ignore()

    def _update_drop_indicator(self, viewport_pos: QPoint):
        idx = self.indexAt(viewport_pos)
        if idx.isValid():
            rect = self.visualRect(idx)
            mid = rect.x() + rect.width() // 2
            x = rect.x() if viewport_pos.x() < mid else rect.right()
            self._drop_indicator.setGeometry(x - 1, rect.y(), 3, rect.height())
            self._drop_indicator.raise_()
            self._drop_indicator.show()
        else:
            n = self._model.rowCount()
            if n:
                last = self._model.index(n - 1, 0)
                lr = self.visualRect(last)
                self._drop_indicator.setGeometry(lr.right() - 1, lr.y(), 3, lr.height())
                self._drop_indicator.raise_()
                self._drop_indicator.show()
            else:
                self._drop_indicator.hide()

    def _target_index_from_pos(self, viewport_pos: QPoint) -> int:
        idx = self.indexAt(viewport_pos)
        if idx.isValid():
            rect = self.visualRect(idx)
            if viewport_pos.x() < rect.x() + rect.width() // 2:
                return idx.row()
            return idx.row() + 1
        return self._model.rowCount()

    # ---- Context menu ----

    def _ctx_menu(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        item = self._model._items[row]

        menu = QMenu(self)
        act_bm = menu.addAction("Añadir/quitar marcador…")
        act_cm = menu.addAction("Añadir/quitar comentario…")
        menu.addSeparator()
        cut_lbl = "Quitar punto de corte" if item.is_cut else "Marcar como punto de corte"
        act_cut = menu.addAction(cut_lbl)
        menu.addSeparator()
        act_full = menu.addAction("Ver a pantalla completa")
        menu.addSeparator()
        act_move_before = menu.addAction("Mover antes de…")
        act_move_after  = menu.addAction("Mover después de…")
        menu.addSeparator()
        act_del = menu.addAction("Eliminar página")
        action = menu.exec(self.viewport().mapToGlobal(pos))

        if action == act_bm:
            self._on_card_bookmark(row)
        elif action == act_cm:
            self._on_card_comment(row)
        elif action == act_cut:
            self.cut_toggled.emit(row)
        elif action == act_full:
            self.fullscreen_requested.emit(row)
        elif action == act_move_before:
            self._on_move_before(row)
        elif action == act_move_after:
            self._on_move_after(row)
        elif action == act_del:
            self.page_deleted.emit(row)

    # ---- Signal helpers ----

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        if _CHECKED_ROLE in roles:
            for row in range(top_left.row(), bottom_right.row() + 1):
                item = self._model._items[row]
                if item.checked:
                    self._checked.add(item.index)
                else:
                    self._checked.discard(item.index)
            self.checked_changed.emit(self._checked.copy())

    def _on_card_bookmark(self, index: int):
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        if mw and hasattr(mw, '_model'):
            p = mw._model.get(index)
            current = p.bookmarks if p and p.bookmarks else []
        else:
            current = []
        dlg = BookmarkDialog(self, index, current)
        if dlg.exec() == QDialog.Accepted:
            labels = dlg.get_bookmarks()
            self.bookmark_requested.emit(index, labels)

    def _on_card_comment(self, index: int):
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        image = None
        cur = ""
        if mw and hasattr(mw, '_model'):
            p = mw._model.get(index)
            if p:
                cur = p.comment
                image = p.display_image
        dlg = CommentDialog(self, index, cur, image)
        if dlg.exec() == QDialog.Accepted:
            text = dlg.get_comment()
            self.comment_requested.emit(index, text)

    def _on_move_before(self, from_idx: int):
        n = self._model.rowCount()
        target, ok = QInputDialog.getInt(
            self, "Mover página",
            f"Mover página {from_idx + 1} antes de la página:",
            minValue=1, maxValue=n, value=from_idx + 1)
        if not ok or target == from_idx + 1:
            return
        target_idx = target - 1
        to_idx = target_idx - (1 if from_idx < target_idx else 0)
        self.reorder_requested.emit(from_idx, to_idx)

    def _on_move_after(self, from_idx: int):
        n = self._model.rowCount()
        target, ok = QInputDialog.getInt(
            self, "Mover página",
            f"Mover página {from_idx + 1} después de la página:",
            minValue=1, maxValue=n, value=from_idx + 1)
        if not ok or target == from_idx + 1:
            return
        target_idx = target - 1
        to_idx = target_idx + (1 if from_idx > target_idx else 0)
        self.reorder_requested.emit(from_idx, to_idx)

    def _on_clicked(self, index: QModelIndex):
        self.select(index.row())
        self.page_selected.emit(index.row())

    def _on_double_clicked(self, index: QModelIndex):
        self.fullscreen_requested.emit(index.row())

    # ---- Public API ----

    @property
    def count(self) -> int:
        return self._model.rowCount()

    def add_page(self, index: int, image: np.ndarray):
        self._model.add_page(index, image)

    def remove_page(self, index: int):
        self._model.remove_page(index)
        self._checked.discard(index)
        if self._selected >= self._model.rowCount():
            self._selected = self._model.rowCount() - 1

    def update_image(self, index: int, image: np.ndarray):
        self._model.update_image(index, image)

    def set_serial(self, index: int, serial: str, confidence: float):
        self._model.set_serial(index, serial, confidence)

    def set_cut(self, index: int, is_cut: bool):
        self._model.set_cut(index, is_cut)

    def set_bookmark(self, index: int, label: str):
        self._model.set_bookmark(index, label)

    def set_bookmarks(self, index: int, labels: list[tuple[int, str]]):
        self._model.set_bookmarks(index, labels)

    def select(self, index: int):
        if 0 <= self._selected < self._model.rowCount():
            self._model.set_selected(self._selected, False)
        self._selected = index
        if 0 <= index < self._model.rowCount():
            self._model.set_selected(index, True)
            self.scrollTo(self._model.index(index, 0))

    def reorder_cards(self, from_idx: int, to_idx: int):
        self._model.reorder(from_idx, to_idx)
        if self._selected == from_idx:
            self._selected = to_idx
        elif from_idx < self._selected <= to_idx:
            self._selected -= 1
        elif from_idx > self._selected >= to_idx:
            self._selected += 1

    def clear_all(self):
        self._model.clear_all()
        self._selected = -1
        self._checked.clear()

    def check_all(self):
        self._model.set_all_checked(True)
        self._checked = set(range(self._model.rowCount()))
        self.checked_changed.emit(self._checked.copy())

    def uncheck_all(self):
        self._model.set_all_checked(False)
        self._checked.clear()
        self.checked_changed.emit(set())

    def get_checked_indices(self) -> set[int]:
        return self._checked.copy()
