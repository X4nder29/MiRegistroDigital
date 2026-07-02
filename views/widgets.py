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
)
from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint, QMimeData, QEvent, QTimer
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QDrag, QPainter, QWheelEvent, QDesktopServices, QIntValidator
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

class ThumbnailCard(QFrame):
    clicked              = Signal(int)
    cut_toggled          = Signal(int)
    delete_requested     = Signal(int)
    fullscreen_requested = Signal(int)
    checked_toggled      = Signal(int, bool)
    bookmark_clicked     = Signal(int)
    comment_clicked      = Signal(int)
    move_before_requested = Signal(int)
    move_after_requested  = Signal(int)

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

    def set_comment(self, text: str):
        if text:
            preview = text[:40] + "…" if len(text) > 40 else text
            self._num.setToolTip(f"💬 Comentario: {preview}")
        else:
            self._num.setToolTip("")

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
        act_cm = menu.addAction("Añadir/quitar comentario…")
        menu.addSeparator()
        cut_lbl = "Quitar punto de corte" if self._is_cut else "Marcar como punto de corte"
        act_cut = menu.addAction(cut_lbl)
        menu.addSeparator()
        act_full = menu.addAction("Ver a pantalla completa")
        menu.addSeparator()
        act_move_before = menu.addAction("Mover antes de…")
        act_move_after  = menu.addAction("Mover después de…")
        menu.addSeparator()
        act_del = menu.addAction("Eliminar página")
        action = menu.exec(self.mapToGlobal(pos))
        if action == act_bm:
            self.bookmark_clicked.emit(self.page_index)
        elif action == act_cm:
            self.comment_clicked.emit(self.page_index)
        elif action == act_cut:
            self.cut_toggled.emit(self.page_index)
        elif action == act_full:
            self.fullscreen_requested.emit(self.page_index)
        elif action == act_move_before:
            self.move_before_requested.emit(self.page_index)
        elif action == act_move_after:
            self.move_after_requested.emit(self.page_index)
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
    bookmark_requested   = Signal(int, list)
    comment_requested    = Signal(int, str)
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
        card.comment_clicked.connect(self._on_card_comment)
        card.move_before_requested.connect(self._on_move_before)
        card.move_after_requested.connect(self._on_move_after)
        self._cards.append(card)
        i = len(self._cards) - 1
        self._grid.addWidget(card, i // self._cols, i % self._cols)
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        return card

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
        n = len(self._cards)
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
        n = len(self._cards)
        target, ok = QInputDialog.getInt(
            self, "Mover página",
            f"Mover página {from_idx + 1} después de la página:",
            minValue=1, maxValue=n, value=from_idx + 1)
        if not ok or target == from_idx + 1:
            return
        target_idx = target - 1
        to_idx = target_idx + (1 if from_idx > target_idx else 0)
        self.reorder_requested.emit(from_idx, to_idx)

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

    def set_bookmarks(self, index: int, labels: list[tuple[int, str]]):
        c = self._card(index)
        if c:
            first = labels[0][1] if labels else ""
            n = len(labels)
            display = f"{first} 📑{n}" if n > 1 else first
            c.set_bookmark(display)

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
