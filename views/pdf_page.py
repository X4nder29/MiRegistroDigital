"""Página Editor — Organizar, Split, Merge."""
from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, Signal, QPoint, QMimeData, QEvent
from PySide6.QtGui import QPixmap, QImage, QColor, QDrag, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QFrame, QFileDialog,
    QGridLayout, QStackedWidget, QMessageBox, QSplitter,
    QListWidget, QListWidgetItem, QAbstractItemView, QMenu, QInputDialog,
)

from views.theme import BG, SURFACE, SURFACE2, SURFACE3, BORDER, TEXT, TEXT_DIM, TEXT_SEC, ACCENT2, DANGER, INFO

logger = logging.getLogger("docscan.pdf_page")

_PALETTE = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
            "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"]


@dataclass
class _PageEntry:
    source_path: str
    source_page: int
    pdf_color: QColor
    pdf_label: str
    thumbnail: QPixmap


@dataclass
class _PdfSource:
    path: str
    label: str
    page_count: int
    color: QColor


class _SidebarList(QListWidget):
    """QListWidget que emite MIME data con formato pdf:{index} para drag."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setDefaultDropAction(Qt.CopyAction)

    def mimeData(self, items):
        mime = QMimeData()
        if items:
            idx = items[0].data(Qt.UserRole)
            if idx is not None:
                mime.setText(f"pdf:{int(idx)}")
        return mime

    def mimeTypes(self):
        return ["text/plain"]


class OrganizeCard(QFrame):
    delete_clicked = Signal(int)
    move_before_requested = Signal(int)
    move_after_requested = Signal(int)

    def __init__(self, index: int, entry: _PageEntry, parent=None):
        super().__init__(parent)
        self._entry = entry
        self._idx = index
        self._press_pos = QPoint()

        self.setFixedSize(150, 200)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            OrganizeCard {{
                background: {SURFACE2};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
            OrganizeCard:hover {{
                border-color: {ACCENT2};
            }}
        """)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        strip = QFrame()
        strip.setFixedWidth(4)
        strip.setStyleSheet(f"background:{entry.pdf_color.name()}; border:none;")
        root.addWidget(strip)

        content = QVBoxLayout()
        content.setContentsMargins(6, 4, 6, 4)
        content.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        page_label = QLabel(f"Pág. {entry.source_page + 1}")
        page_label.setStyleSheet(f"color:{TEXT_SEC}; font-size:8pt; border:none; background:transparent;")
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(20, 20)
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; color:{TEXT_DIM};
                font-size:10pt; font-weight:700;
            }}
            QPushButton:hover {{ color:{DANGER}; }}
        """)
        btn_del.clicked.connect(self._on_delete_clicked)
        top.addWidget(page_label)
        top.addStretch()
        top.addWidget(btn_del)
        content.addLayout(top)

        thumb_label = QLabel()
        thumb_label.setAlignment(Qt.AlignCenter)
        pix = entry.thumbnail
        scaled = pix.scaled(130, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumb_label.setPixmap(scaled)
        thumb_label.setFixedHeight(min(scaled.height(), 140))
        thumb_label.setStyleSheet("background:transparent; border:none;")
        content.addWidget(thumb_label, 1)

        src_label = QLabel()
        fm = QFontMetrics(src_label.font())
        elided = fm.elidedText(entry.pdf_label, Qt.ElideRight, 130)
        src_label.setText(elided)
        src_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:7pt; border:none; background:transparent;")
        src_label.setToolTip(entry.pdf_label)
        content.addWidget(src_label)

        root.addLayout(content, 1)

    def _on_delete_clicked(self):
        self.delete_clicked.emit(self._idx)

    def update_index(self, idx: int):
        self._idx = idx

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if (event.pos() - self._press_pos).manhattanLength() > 10:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(str(self._idx))
                drag.setMimeData(mime)
                pix = self.grab()
                drag.setPixmap(pix.scaled(75, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                drag.setHotSpot(event.pos())
                drag.exec(Qt.MoveAction)
        super().mouseMoveEvent(event)

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        act_before = menu.addAction("Mover antes de\u2026")
        act_after  = menu.addAction("Mover despu\u00e9s de\u2026")
        menu.addSeparator()
        act_del = menu.addAction("Eliminar p\u00e1gina")
        action = menu.exec(self.mapToGlobal(pos))
        if action == act_before:
            self.move_before_requested.emit(self._idx)
        elif action == act_after:
            self.move_after_requested.emit(self._idx)
        elif action == act_del:
            self.delete_clicked.emit(self._idx)


class OrganizeWidget(QWidget):
    pdf_generated = Signal(str)

    _CARD_W = 158

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[_PageEntry] = []
        self._cards: list[OrganizeCard] = []
        self._loaded_pdfs: list[_PdfSource] = []
        self._color_idx = 0
        self._cols = 4
        self._build()

    def _build(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        left_panel = QWidget()
        left_panel.setStyleSheet(f"background:{BG};")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setFixedHeight(44)
        toolbar.setStyleSheet(f"background:{BG}; border:none;")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 6, 16, 6)

        self._btn_load = QPushButton("Cargar PDFs")
        self._btn_load.clicked.connect(self._load_pdfs)

        self._btn_clear = QPushButton("Limpiar")
        self._btn_clear.setProperty("danger", True)
        self._btn_clear.clicked.connect(self._clear_all)

        self._btn_generate = QPushButton("Generar PDF")
        self._btn_generate.setProperty("primary", True)
        self._btn_generate.clicked.connect(self._generate_pdf)
        self._btn_generate.setEnabled(False)

        self._info_label = QLabel("0 p\u00e1ginas")
        self._info_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none; background:transparent;")

        tb.addWidget(self._btn_load)
        tb.addWidget(self._btn_clear)
        tb.addStretch()
        tb.addWidget(self._btn_generate)
        tb.addSpacing(12)
        tb.addWidget(self._info_label)
        left_layout.addWidget(toolbar)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._build_empty_state())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border:none; background:{BG}; }}")

        self._container = QWidget()
        self._container.setStyleSheet(f"background:{BG};")
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._grid.setSpacing(8)
        scroll.setWidget(self._container)

        self._drop_indicator = QFrame(self._container)
        self._drop_indicator.setStyleSheet(f"background:{INFO}; border:none; border-radius:1px;")
        self._drop_indicator.setFixedWidth(3)
        self._drop_indicator.hide()

        scroll.viewport().setAcceptDrops(True)
        scroll.viewport().installEventFilter(self)

        self._scroll = scroll
        self._content_stack.addWidget(scroll)

        left_layout.addWidget(self._content_stack, 1)

        self._container.installEventFilter(self)

        right_panel = QFrame()
        right_panel.setFixedWidth(220)
        right_panel.setStyleSheet(f"background:{SURFACE}; border-left:1px solid {BORDER};")

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        sidebar_header = QLabel("Fuentes PDF")
        sidebar_header.setContentsMargins(12, 0, 0, 0)
        sidebar_header.setFixedHeight(36)
        sidebar_header.setStyleSheet(f"color:{TEXT_SEC}; font-size:9pt; font-weight:600; border-bottom:1px solid {BORDER};")
        right_layout.addWidget(sidebar_header)

        self._sidebar = _SidebarList()
        self._sidebar.setStyleSheet(f"""
            QListWidget {{
                background:transparent; border:none; font-size:9pt;
                color:{TEXT};
            }}
            QListWidget::item {{
                padding:6px 8px; border-bottom:1px solid {SURFACE2};
            }}
            QListWidget::item:hover {{
                background:{SURFACE2};
            }}
        """)
        right_layout.addWidget(self._sidebar, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        main.addWidget(splitter)

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)

        icon = QLabel("🗂️")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size:40pt; border:none;")
        lay.addWidget(icon)

        msg = QLabel(
            "Cargá uno o más PDFs para comenzar.\n"
            "Podés reordenar las páginas arrastrándolas — cada PDF origen\n"
            "se muestra con un color distintivo."
        )
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(f"color:{TEXT_SEC}; font-size:10pt; border:none;")
        lay.addWidget(msg)

        btn = QPushButton("Cargar PDFs")
        btn.setProperty("primary", True)
        btn.setFixedHeight(36)
        btn.setFixedWidth(200)
        btn.clicked.connect(self._load_pdfs)
        lay.addWidget(btn, alignment=Qt.AlignCenter)

        return w

    # ── Event filter ──────────────────────────────────────────────

    def eventFilter(self, obj, event):
        t = event.type()
        if obj is self._scroll.viewport():
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
        if obj is self._container and t == QEvent.Resize:
            self._reflow()
        return super().eventFilter(obj, event)

    # ── Drag & drop handlers ─────────────────────────────────────

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
        mime = event.mimeData()
        if not mime.hasText():
            event.ignore()
            return
        text = mime.text()
        target = self._target_index_from_pos(
            self._container.mapFrom(self._scroll.viewport(), event.pos()))
        event.setDropAction(Qt.MoveAction)
        event.accept()
        self._drop_indicator.hide()

        if text.startswith("pdf:"):
            pdf_idx = int(text[4:])
            self._insert_pdf_at(pdf_idx, target)
        else:
            from_idx = int(text)
            if from_idx != target:
                self._reorder(from_idx, target)

    def _update_drop_indicator(self, viewport_pos):
        pos = self._container.mapFrom(self._scroll.viewport(), viewport_pos)
        idx = self._target_index_from_pos(pos)
        if 0 <= idx < len(self._cards):
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

    # ── Grid reflow ──────────────────────────────────────────────

    def _reflow(self):
        if not self._cards:
            return

        for i in range(self._grid.count() - 1, -1, -1):
            item = self._grid.itemAt(i)
            if item and item.widget():
                self._grid.removeWidget(item.widget())

        available = self._container.width() - 20
        if available > 10:
            self._cols = max(1, (available + 8) // self._CARD_W)

        for i, card in enumerate(self._cards):
            self._grid.addWidget(card, i // self._cols, i % self._cols)
        self._grid.setRowStretch(self._grid.rowCount(), 1)

    # ── PDF loading ──────────────────────────────────────────────

    def _load_pdfs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar PDFs", "", "PDF (*.pdf)")
        if not paths:
            return
        for path in paths:
            self._add_pdf(path)

    def _add_pdf(self, path: str):
        import fitz
        try:
            doc = fitz.open(path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir {Path(path).name}:\n{e}")
            return
        n = len(doc)
        if n == 0:
            doc.close()
            return
        color = QColor(_PALETTE[self._color_idx % len(_PALETTE)])
        self._color_idx += 1
        label = Path(path).name

        src = _PdfSource(path=path, label=label, page_count=n, color=color)
        self._loaded_pdfs.append(src)

        for i in range(n):
            try:
                page = doc[i]
                mat = fitz.Matrix(0.5, 0.5)
                pix = page.get_pixmap(matrix=mat)
                h, w, ch = pix.height, pix.width, pix.n
                samples = pix.samples
                if isinstance(samples, memoryview):
                    samples = bytes(samples)
                arr = np.frombuffer(samples, dtype=np.uint8).reshape(h, w, ch).copy()
                if ch >= 3:
                    qimg = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888)
                else:
                    qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
                thumb = QPixmap.fromImage(qimg)
            except Exception:
                thumb = QPixmap(130, 170)
                thumb.fill(QColor(SURFACE2))

            self._entries.append(_PageEntry(
                source_path=path,
                source_page=i,
                pdf_color=color,
                pdf_label=label,
                thumbnail=thumb,
            ))

        doc.close()
        self._refresh()

    def _insert_pdf_at(self, pdf_idx: int, target_idx: int):
        if pdf_idx < 0 or pdf_idx >= len(self._loaded_pdfs):
            return
        src = self._loaded_pdfs[pdf_idx]
        import fitz
        try:
            doc = fitz.open(src.path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo leer {src.label}:\n{e}")
            return

        new_entries: list[_PageEntry] = []
        for i in range(src.page_count):
            try:
                page = doc[i]
                mat = fitz.Matrix(0.5, 0.5)
                pix = page.get_pixmap(matrix=mat)
                h, w, ch = pix.height, pix.width, pix.n
                samples = pix.samples
                if isinstance(samples, memoryview):
                    samples = bytes(samples)
                arr = np.frombuffer(samples, dtype=np.uint8).reshape(h, w, ch).copy()
                if ch >= 3:
                    qimg = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888)
                else:
                    qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
                thumb = QPixmap.fromImage(qimg)
            except Exception:
                thumb = QPixmap(130, 170)
                thumb.fill(QColor(SURFACE2))

            new_entries.append(_PageEntry(
                source_path=src.path,
                source_page=i,
                pdf_color=src.color,
                pdf_label=src.label,
                thumbnail=thumb,
            ))

        doc.close()

        target_idx = max(0, min(target_idx, len(self._entries)))
        self._entries[target_idx:target_idx] = new_entries
        self._refresh()

    # ── Refresh UI ───────────────────────────────────────────────

    def _refresh_sidebar(self):
        self._sidebar.clear()
        for i, src in enumerate(self._loaded_pdfs):
            pix = QPixmap(12, 12)
            pix.fill(src.color)
            item = QListWidgetItem(pix, f"{src.label} ({src.page_count} p\u00e1gs.)")
            item.setData(Qt.UserRole, i)
            self._sidebar.addItem(item)
        if not self._loaded_pdfs:
            placeholder = QListWidgetItem("Sin PDFs cargados")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QColor(TEXT_DIM))
            self._sidebar.addItem(placeholder)

    def _refresh(self):
        for i in range(self._grid.count() - 1, -1, -1):
            item = self._grid.itemAt(i)
            if item:
                w = item.widget()
                if w:
                    self._grid.removeWidget(w)
                    w.deleteLater()
        self._cards.clear()

        for i, entry in enumerate(self._entries):
            card = OrganizeCard(i, entry)
            card.delete_clicked.connect(self._on_delete)
            card.move_before_requested.connect(self._on_move_before)
            card.move_after_requested.connect(self._on_move_after)
            self._cards.append(card)

        self._reflow()
        self._refresh_sidebar()

        count = len(self._entries)
        self._info_label.setText(f"{count} p\u00e1gina{'s' if count != 1 else ''}")
        self._btn_generate.setEnabled(count > 0)
        self._content_stack.setCurrentIndex(1 if count > 0 else 0)

    # ── Actions ──────────────────────────────────────────────────

    def _on_delete(self, idx: int):
        if 0 <= idx < len(self._entries):
            self._entries.pop(idx)
            self._refresh()

    def _on_move_before(self, from_idx: int):
        n = len(self._entries)
        target, ok = QInputDialog.getInt(
            self, "Mover p\u00e1gina",
            f"Mover p\u00e1gina {from_idx + 1} antes de la p\u00e1gina:",
            minValue=1, maxValue=n, value=from_idx + 1)
        if not ok or target == from_idx + 1:
            return
        target_idx = target - 1
        to_idx = target_idx - (1 if from_idx < target_idx else 0)
        self._reorder(from_idx, to_idx)

    def _on_move_after(self, from_idx: int):
        n = len(self._entries)
        target, ok = QInputDialog.getInt(
            self, "Mover p\u00e1gina",
            f"Mover p\u00e1gina {from_idx + 1} despu\u00e9s de la p\u00e1gina:",
            minValue=1, maxValue=n, value=from_idx + 1)
        if not ok or target == from_idx + 1:
            return
        target_idx = target - 1
        to_idx = target_idx + (1 if from_idx > target_idx else 0)
        self._reorder(from_idx, to_idx)

    def _reorder(self, from_idx: int, to_idx: int):
        if from_idx == to_idx:
            return
        entry = self._entries.pop(from_idx)
        self._entries.insert(to_idx, entry)
        self._refresh()

    def _clear_all(self):
        if not self._entries:
            return
        ret = QMessageBox.question(
            self, "Limpiar todo",
            "\u00bfEliminar todas las p\u00e1ginas cargadas?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self._entries.clear()
            self._loaded_pdfs.clear()
            self._color_idx = 0
            self._refresh()

    def _generate_pdf(self):
        if not self._entries:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF organizado", "", "PDF (*.pdf)")
        if not path:
            return

        import fitz
        dest = fitz.Document()
        sources: OrderedDict[str, fitz.Document] = OrderedDict()
        page_origins: list[tuple[str, int]] = []

        try:
            for entry in self._entries:
                if entry.source_path not in sources:
                    sources[entry.source_path] = fitz.open(entry.source_path)
                src = sources[entry.source_path]
                dest.insert_pdf(src, from_page=entry.source_page, to_page=entry.source_page)
                page_origins.append((entry.source_path, entry.source_page))

            page_map: dict[tuple[str, int], int] = {}
            for dest_idx, (spath, spage) in enumerate(page_origins):
                key = (spath, spage)
                if key not in page_map:
                    page_map[key] = dest_idx + 1

            toc: list[list] = []
            for spath, src in sources.items():
                try:
                    src_toc = src.get_toc()
                except Exception:
                    continue
                for entry in src_toc:
                    level, title, src_page = entry[0], entry[1], entry[2]
                    key = (spath, src_page - 1)
                    if key in page_map:
                        toc.append([level, title, page_map[key]])

            if toc:
                toc.sort(key=lambda x: x[2])
                dest.set_toc(toc)

            if Path(path).suffix.lower() != ".pdf":
                path += ".pdf"
            dest.save(path, garbage=4, deflate=True)
        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"No se pudo generar el PDF:\n{e}")
        finally:
            dest.close()
            for s in sources.values():
                s.close()

        self.pdf_generated.emit(path)
        QMessageBox.information(
            self, "PDF generado",
            f"PDF guardado correctamente:\n{path}")


class EditorPage(QWidget):
    """Página principal de herramientas PDF con tabs."""

    pdf_generated = Signal(str)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._cfg = config
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background:{SURFACE}; border-bottom:1px solid {BORDER};")
        hdr = QHBoxLayout(header)
        hdr.setContentsMargins(16, 0, 16, 0)

        title = QLabel("Editor")
        title.setStyleSheet(f"font-size:13pt; font-weight:700; color:{TEXT}; border:none; background:transparent;")
        hdr.addWidget(title)

        self._tab_bar = QFrame()
        self._tab_bar.setStyleSheet("background:transparent; border:none;")
        tab_layout = QHBoxLayout(self._tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(2)

        self._tab_btns: dict[str, QPushButton] = {}
        tabs = [
            ("organize", "Organizar"),
            ("split", "Dividir"),
            ("merge", "Combinar"),
        ]
        for key, label in tabs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; border:none;
                    color:{TEXT_DIM}; font-size:9pt;
                    padding:0 14px; border-radius:4px;
                }}
                QPushButton:hover {{ color:{TEXT_SEC}; background:{SURFACE2}; }}
                QPushButton:checked {{
                    color:{TEXT}; background:{SURFACE2};
                    border-bottom:2px solid {ACCENT2};
                }}
            """)
            btn.clicked.connect(lambda checked, k=key: self._switch_tab(k))
            self._tab_btns[key] = btn
            tab_layout.addWidget(btn)

        hdr.addSpacing(24)
        hdr.addWidget(self._tab_bar)
        hdr.addStretch()
        layout.addWidget(header)

        self._tool_stack = QStackedWidget()

        self._organize_widget = OrganizeWidget()
        self._tool_stack.addWidget(self._organize_widget)
        self._organize_widget.pdf_generated.connect(self.pdf_generated)

        self._tool_stack.addWidget(self._build_stub("\u2702\ufe0f", "Dividir PDF", "Pr\u00f3ximamente"))
        self._tool_stack.addWidget(self._build_stub("\ud83e\udde9", "Combinar PDFs", "Pr\u00f3ximamente \u2014 hoy pod\u00e9s arrastrar un PDF completo desde el panel Organizar."))

        layout.addWidget(self._tool_stack, 1)

        self._tab_btns["organize"].setChecked(True)
        self._tool_stack.setCurrentIndex(0)

    def _switch_tab(self, key: str):
        idx_map = {"organize": 0, "split": 1, "merge": 2}
        for k, btn in self._tab_btns.items():
            btn.setChecked(k == key)
        self._tool_stack.setCurrentIndex(idx_map.get(key, 0))

    def _build_stub(self, icon: str, title: str, subtitle: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size:32pt; border:none;")
        lay.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color:{TEXT_SEC}; font-size:12pt; font-weight:600; border:none;")
        lay.addWidget(title_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setWordWrap(True)
        sub_lbl.setFixedWidth(360)
        sub_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        lay.addWidget(sub_lbl)

        return w
