"""RegistosSection — Contenedor con sub-navegación para Registros Civiles."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal

from views.civil_page import CivilPage
from views.registos_bookmarks_page import RegistosBookmarksPage
from views.registos_merge_page import RegistosMergePage
from views.theme import BG, SURFACE, SURFACE2, SURFACE3, BORDER, TEXT, TEXT_DIM, TEXT_SEC, ACCENT2


class SubNavButton(QPushButton):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setText(label)
        self.setCheckable(True)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                color: {TEXT_DIM};
                text-align: center;
                padding: 0 20px;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ background: transparent; color: {TEXT_SEC}; }}
            QPushButton:checked {{
                border-bottom: 2px solid {TEXT};
                color: {TEXT};
            }}
        """)


class RegistosSection(QWidget):
    # Forward signals from CivilPage
    ocr_all_requested       = Signal()
    ocr_page_requested      = Signal(int)
    ocr_cancel_requested    = Signal()
    serial_corrected        = Signal(int, str)
    export_requested        = Signal(str)
    ocr_area_saved          = Signal(int, float, float, float, float)
    parallel_workers_changed = Signal(int)

    # Signals for bookmarks page
    bookmarks_export_requested = Signal(list, str, int)

    # Signals for merge page
    merge_requested = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected_idx = -1
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        subnav = QFrame()
        subnav.setFixedHeight(42)
        subnav.setStyleSheet(f"background:{BG}; border-bottom: 1px solid {BORDER};")
        nav_layout = QHBoxLayout(subnav)
        nav_layout.setContentsMargins(24, 0, 24, 0)
        nav_layout.setSpacing(4)

        self._civil_page = CivilPage()
        self._bookmarks_page = RegistosBookmarksPage()
        self._merge_page = RegistosMergePage()

        self._btn_civil = SubNavButton("Exportar PDFs")
        self._btn_bookmarks = SubNavButton("PDF con marcadores")
        self._btn_merge = SubNavButton("Unir PDFs")

        self._btn_civil.clicked.connect(lambda: self._navigate(0))
        self._btn_bookmarks.clicked.connect(lambda: self._navigate(1))
        self._btn_merge.clicked.connect(lambda: self._navigate(2))

        nav_layout.addWidget(self._btn_civil)
        nav_layout.addWidget(self._btn_bookmarks)
        nav_layout.addWidget(self._btn_merge)
        nav_layout.addStretch()

        root.addWidget(subnav)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._civil_page)
        self._stack.addWidget(self._bookmarks_page)
        self._stack.addWidget(self._merge_page)
        root.addWidget(self._stack, 1)

        self._navigate(0)

    def _navigate(self, idx: int):
        self._btn_civil.setChecked(idx == 0)
        self._btn_bookmarks.setChecked(idx == 1)
        self._btn_merge.setChecked(idx == 2)
        self._stack.setCurrentIndex(idx)
        self._sync_signals(idx)

    def _sync_signals(self, idx: int):
        if self._connected_idx == idx:
            return

        if self._connected_idx == 0:
            cp = self._civil_page
            cp.ocr_all_requested.disconnect(self.ocr_all_requested)
            cp.ocr_page_requested.disconnect(self.ocr_page_requested)
            cp.ocr_cancel_requested.disconnect(self.ocr_cancel_requested)
            cp.serial_corrected.disconnect(self.serial_corrected)
            cp.export_requested.disconnect(self.export_requested)
            cp.ocr_area_saved.disconnect(self.ocr_area_saved)
            cp.parallel_workers_changed.disconnect(self.parallel_workers_changed)
        elif self._connected_idx == 1:
            self._bookmarks_page.export_requested.disconnect(self.bookmarks_export_requested)
        elif self._connected_idx == 2:
            self._merge_page.merge_requested.disconnect(self.merge_requested)

        if idx == 0:
            cp = self._civil_page
            cp.ocr_all_requested.connect(self.ocr_all_requested)
            cp.ocr_page_requested.connect(self.ocr_page_requested)
            cp.ocr_cancel_requested.connect(self.ocr_cancel_requested)
            cp.serial_corrected.connect(self.serial_corrected)
            cp.export_requested.connect(self.export_requested)
            cp.ocr_area_saved.connect(self.ocr_area_saved)
            cp.parallel_workers_changed.connect(self.parallel_workers_changed)
        elif idx == 1:
            self._bookmarks_page.export_requested.connect(self.bookmarks_export_requested)
        elif idx == 2:
            self._merge_page.merge_requested.connect(self.merge_requested)

        self._connected_idx = idx

    # ── Delegated API ─────────────────────────────────────────────────

    @property
    def civil_page(self) -> CivilPage:
        return self._civil_page

    @property
    def bookmarks_page(self) -> RegistosBookmarksPage:
        return self._bookmarks_page

    @property
    def merge_page(self) -> RegistosMergePage:
        return self._merge_page
