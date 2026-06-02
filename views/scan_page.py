"""Página de importación."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFrame, QProgressBar, QFileDialog,
    QSlider,
)
from PySide6.QtCore import Qt, Signal

from views.widgets import ThumbnailGrid, ImageViewer
from views.theme import TEXT_DIM, SURFACE, SURFACE3, DANGER


class ScanPage(QWidget):
    import_images_requested = Signal(list)
    import_pdf_requested    = Signal(list)
    import_cancel_requested = Signal()
    cut_toggled            = Signal(int)
    page_deleted           = Signal(int)
    fullscreen_requested   = Signal(int)
    navigate               = Signal(str)
    correction_requested   = Signal(int)
    rotation_changed       = Signal(int, float)
    reset_correction       = Signal(int)
    page_reordered         = Signal(int, int)
    bookmark_set           = Signal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: int = -1
        self._rot_angle: float = 0.0
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._toolbar())

        self._prog = QProgressBar()
        self._prog.setFixedHeight(3)
        self._prog.setTextVisible(False)
        self._prog.setVisible(False)
        root.addWidget(self._prog)

        self._empty = QLabel("  Importa un PDF o imágenes para comenzar")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(f"color:{TEXT_DIM}; font-size:12pt; border:none; margin:80px;")
        root.addWidget(self._empty)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {SURFACE3}; }}")

        self.grid = ThumbnailGrid()
        self.grid.page_selected.connect(self._on_page_selected)
        self.grid.cut_toggled.connect(self.cut_toggled)
        self.grid.page_deleted.connect(self.page_deleted)
        self.grid.fullscreen_requested.connect(self.fullscreen_requested)
        self.grid.reorder_requested.connect(self.page_reordered)
        self.grid.bookmark_requested.connect(self.bookmark_set)
        splitter.addWidget(self.grid)

        self.viewer = ImageViewer()
        splitter.addWidget(self.viewer)

        self._correction_panel = self._build_correction_panel()
        splitter.addWidget(self._correction_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 700, 200])
        splitter.setVisible(False)
        self._splitter = splitter
        root.addWidget(splitter)

    def _toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background:{SURFACE}; border:none;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(8)

        btn_pdf = QPushButton("  PDF")
        btn_pdf.setProperty("primary", True)
        btn_pdf.setFixedHeight(34)
        btn_pdf.setToolTip("Importar PDF multipágina")
        btn_pdf.clicked.connect(self._open_pdf)

        btn_img = QPushButton("  Imágenes")
        btn_img.setFixedHeight(34)
        btn_img.setToolTip("Importar imágenes (JPG, PNG, TIFF, BMP, WEBP)")
        btn_img.clicked.connect(self._open_images)

        lay.addWidget(btn_pdf)
        lay.addWidget(btn_img)

        self._btn_cancel_import = QPushButton("Cancelar")
        self._btn_cancel_import.setFixedHeight(30)
        self._btn_cancel_import.setStyleSheet(f"color:{DANGER};")
        self._btn_cancel_import.setVisible(False)
        self._btn_cancel_import.clicked.connect(self.import_cancel_requested)
        lay.addWidget(self._btn_cancel_import)

        lay.addStretch()

        self._page_count_lbl = QLabel("")
        self._page_count_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        lay.addWidget(self._page_count_lbl)

        def nav(key):
            return lambda: self.navigate.emit(key)

        btn_civil = QPushButton("  Registros")
        btn_civil.setFixedHeight(32)
        btn_civil.clicked.connect(nav("civil"))
        btn_ant = QPushButton("  Antecedentes")
        btn_ant.setFixedHeight(32)
        btn_ant.clicked.connect(nav("antecedentes"))
        lay.addWidget(btn_civil)
        lay.addWidget(btn_ant)
        return bar

    def add_page(self, index: int, image):
        self._empty.setVisible(False)
        self._splitter.setVisible(True)
        self.grid.add_page(index, image)
        self.viewer.set_image(image)
        self._current = index
        self._update_status()

    def update_page(self, index: int, image):
        self.grid.update_image(index, image)
        if index == self._current:
            self.viewer.set_image(image)

    def show_page(self, index: int, image):
        self._current = index
        self.viewer.set_image(image)
        self.grid.select(index)

    def set_serial(self, index: int, serial: str, conf: float):
        self.grid.set_serial(index, serial, conf)

    def set_bookmark(self, index: int, label: str):
        self.grid.set_bookmark(index, label)

    def set_bookmarks(self, index: int, labels: list[tuple[int, str]]):
        self.grid.set_bookmarks(index, labels)

    def reorder_cards(self, from_idx: int, to_idx: int):
        self.grid.reorder_cards(from_idx, to_idx)
        if self._current == from_idx:
            self._current = to_idx

    def rebuild(self, pages_data: list):
        self.grid.blockSignals(True)
        self.grid.clear_all()
        for pd in pages_data:
            c = self.grid.add_page(pd.index, pd.display_image)
            if pd.serial:
                c.set_serial(pd.serial, pd.serial_confidence)
            if pd.is_cut_point:
                c.set_cut_point(True)
            if pd.bookmarks:
                first = pd.bookmarks[0][1] if pd.bookmarks else ""
                n = len(pd.bookmarks)
                display = f"{first} 📑{n}" if n > 1 else first
                c.set_bookmark(display)
            elif pd.bookmark:
                c.set_bookmark(pd.bookmark)
        self._update_status()
        self.grid.blockSignals(False)

    def remove_page(self, index: int):
        self.grid.remove_page(index)
        self._update_status()
        if len(self.grid._cards) == 0:
            self._empty.setVisible(True)
            self._splitter.setVisible(False)

    def set_cut(self, index: int, is_cut: bool):
        self.grid.set_cut(index, is_cut)

    def show_import_progress(self, current: int, total: int):
        self._prog.setVisible(True)
        self._prog.setMaximum(total)
        self._prog.setValue(current)
        if current >= total:
            self._prog.setVisible(False)

    def import_busy(self, busy: bool):
        self._prog.setVisible(busy)
        self._btn_cancel_import.setVisible(busy)
        if busy:
            self._prog.setRange(0, 0)
        else:
            self._prog.setRange(0, 1)
            self._prog.setVisible(False)

    def _build_correction_panel(self) -> QFrame:
        panel = QFrame()
        panel.setMinimumWidth(180)
        panel.setStyleSheet(f"background:{SURFACE}; border:none;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("Corrección")
        title.setStyleSheet("font-size:10pt; font-weight:bold; border:none;")
        lay.addWidget(title)

        lbl = QLabel("Rotación fina")
        lbl.setStyleSheet("font-size:9pt; border:none;")
        lay.addWidget(lbl)

        self._rot_slider = QSlider(Qt.Horizontal)
        self._rot_slider.setRange(-45, 45)
        self._rot_slider.setValue(0)
        self._rot_slider.valueChanged.connect(self._on_slider_rot)
        lay.addWidget(self._rot_slider)

        btn_row = QHBoxLayout()
        for angle, text in [(-90, "-90°"), (90, "90°"), (180, "180°")]:
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, a=angle: self._on_quick_rot(a))
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        btn_auto = QPushButton("Auto perspectiva")
        btn_auto.setFixedHeight(32)
        btn_auto.clicked.connect(self._on_auto_perspective)
        lay.addWidget(btn_auto)

        btn_full = QPushButton("Ver completa")
        btn_full.setFixedHeight(32)
        btn_full.clicked.connect(lambda: self.fullscreen_requested.emit(self._current))
        lay.addWidget(btn_full)

        btn_reset = QPushButton("Restablecer")
        btn_reset.setFixedHeight(32)
        btn_reset.clicked.connect(self._on_reset)
        lay.addWidget(btn_reset)

        lay.addStretch()
        return panel

    def _on_slider_rot(self, value: int):
        self._rot_angle = float(value)
        self.rotation_changed.emit(self._current, self._rot_angle)

    def _on_quick_rot(self, delta: float):
        self._rot_angle += delta
        self.rotation_changed.emit(self._current, self._rot_angle)

    def _on_auto_perspective(self):
        self._rot_angle = 0.0
        self._rot_slider.setValue(0)
        self.correction_requested.emit(self._current)

    def _on_reset(self):
        self._rot_angle = 0.0
        self._rot_slider.setValue(0)
        self.reset_correction.emit(self._current)

    def _on_page_selected(self, index: int):
        self._current = index
        self._rot_angle = 0.0
        self._rot_slider.setValue(0)

    def _open_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar imágenes",
            "", "Imágenes (*.jpg *.jpeg *.png *.tiff *.tif *.bmp *.webp);;Todos (*.*)")
        if paths:
            self.import_images_requested.emit([Path(p) for p in paths])

    def _open_pdf(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar PDF", "", "PDF (*.pdf);;Todos (*.*)")
        if paths:
            self.import_pdf_requested.emit([Path(p) for p in paths])

    def _update_status(self):
        n = len(self.grid._cards)
        self._page_count_lbl.setText(f"{n} página(s)" if n else "")
