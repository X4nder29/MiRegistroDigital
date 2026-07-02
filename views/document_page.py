"""Página unificada — importar, corregir, OCR y exportar en una sola vista."""
from __future__ import annotations
import numpy as np
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFrame, QProgressBar, QFileDialog,
    QSlider, QTabWidget, QGroupBox, QFormLayout, QSpinBox,
    QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QListWidget,
    QListWidgetItem, QPlainTextEdit, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QColor, QKeySequence, QShortcut

from views.widgets import ThumbnailGrid, ImageViewer
from models.config_model import ConfigModel
from views.theme import (
    SURFACE, SURFACE2, SURFACE3, BORDER, BG,
    TEXT, TEXT_SEC, TEXT_DIM, SUCCESS, DANGER, WARNING, INFO,
    ACCENT,
)


class DocumentPage(QWidget):
    # ── Import ──
    import_images_requested = Signal(list)
    import_pdf_requested    = Signal(list)
    import_cancel_requested = Signal()

    # ── Correction ──
    correction_requested   = Signal(int)
    rotation_changed       = Signal(int, float)
    reset_correction       = Signal(int)

    # ── OCR ──
    ocr_all_requested         = Signal()
    ocr_page_requested        = Signal(int)
    ocr_cancel_requested      = Signal()
    serial_corrected          = Signal(int, str)
    ocr_area_saved            = Signal(int, float, float, float, float)
    parallel_workers_changed  = Signal(int)

    # ── Bookmarks / Comments / Cuts ──
    bookmark_set       = Signal(int, list)
    comment_set        = Signal(int, str)
    cut_toggled        = Signal(int)
    clear_cuts_requested = Signal()

    # ── Page management ──
    page_deleted       = Signal(int)
    page_reordered     = Signal(int, int)
    page_reordered_seq = Signal(list)
    fullscreen_requested = Signal(int)

    # ── Export ──
    export_civil_requested       = Signal(str)
    export_bookmark_requested    = Signal(str)
    export_original_pdf_requested = Signal(str)

    export_ant_requested          = Signal(dict)
    export_ant_single_pdf         = Signal(dict)
    export_ant_split_bookmark     = Signal(dict)

    bookmarks_export_requested = Signal(list, str, int)
    merge_requested            = Signal(list, str)

    COL_NUM, COL_SERIAL, COL_CONF, COL_STATUS, COL_BOOKMARK, COL_COMMENT = 0, 1, 2, 3, 4, 5

    def __init__(self, parent=None, config: ConfigModel | None = None):
        super().__init__(parent)
        self._cfg = config
        self._current_idx = -1
        self._rot_angle = 0.0
        self._building = False
        self._build()

    # ═══════════════════════════════════════════════════════════════
    #  BUILD
    # ═══════════════════════════════════════════════════════════════

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        self._apply_import_shortcut()

        self._empty = QLabel(
            "  Importa un PDF o imágenes para comenzar\n\n"
            "  Usa los botones de la barra superior.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(f"color:{TEXT_DIM}; font-size:12pt; border:none; margin:80px;")
        root.addWidget(self._empty)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {SURFACE3}; }}")

        # ── Left: Thumbnail grid ──
        self.grid = ThumbnailGrid()
        self.grid.setMinimumWidth(170)
        self.grid.setMaximumWidth(220)
        self.grid.page_selected.connect(self._on_page_selected)
        self.grid.cut_toggled.connect(self.cut_toggled)
        self.grid.page_deleted.connect(self.page_deleted)
        self.grid.fullscreen_requested.connect(self.fullscreen_requested)
        self.grid.reorder_requested.connect(self.page_reordered)
        self.grid.bookmark_requested.connect(self._on_bookmark_requested)
        self.grid.comment_requested.connect(self._on_comment_requested)
        splitter.addWidget(self.grid)

        # ── Center: Viewer ──
        self.viewer = ImageViewer()
        splitter.addWidget(self.viewer)

        # ── Right: Tabbed panel ──
        self._right_panel = self._build_right_panel()
        splitter.addWidget(self._right_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([180, 600, 350])

        self._splitter = splitter
        splitter.setVisible(False)
        root.addWidget(splitter, 1)


    def _apply_import_shortcut(self):
        seq = "Ctrl+P"
        if self._cfg:
            seq = self._cfg.get("shortcuts", "import_pdf", seq)
        QShortcut(QKeySequence(seq), self, self._open_pdf)

    # ── Toolbar ──

    def _build_toolbar(self) -> QFrame:
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

        self._btn_cancel_import = QPushButton("Cancelar")
        self._btn_cancel_import.setFixedHeight(30)
        self._btn_cancel_import.setStyleSheet(f"color:{DANGER};")
        self._btn_cancel_import.setVisible(False)
        self._btn_cancel_import.clicked.connect(self.import_cancel_requested)

        lay.addWidget(btn_pdf)
        lay.addWidget(btn_img)
        lay.addWidget(self._btn_cancel_import)
        lay.addSpacing(12)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        sep.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(sep)
        lay.addSpacing(12)

        self._btn_ocr = QPushButton("  OCR todas")
        self._btn_ocr.setProperty("primary", True)
        self._btn_ocr.setFixedHeight(34)
        self._btn_ocr.clicked.connect(self.ocr_all_requested)

        self._btn_cancel_ocr = QPushButton("Cancelar OCR")
        self._btn_cancel_ocr.setFixedHeight(30)
        self._btn_cancel_ocr.setStyleSheet(f"color:{DANGER};")
        self._btn_cancel_ocr.setVisible(False)
        self._btn_cancel_ocr.clicked.connect(self.ocr_cancel_requested)

        lay.addWidget(self._btn_cancel_ocr)
        lay.addWidget(self._btn_ocr)

        lay.addSpacing(12)
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(28)
        sep2.setStyleSheet(f"background:{BORDER}; border:none;")
        lay.addWidget(sep2)
        lay.addSpacing(12)

        self._btn_export_menu = QPushButton("  Exportar ▼")
        self._btn_export_menu.setFixedHeight(34)
        self._btn_export_menu.setToolTip("Opciones de exportación")
        self._btn_export_menu.clicked.connect(self._switch_export_tab)

        lay.addWidget(self._btn_export_menu)
        lay.addStretch()

        self._page_count_lbl = QLabel("")
        self._page_count_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        lay.addWidget(self._page_count_lbl)

        return bar

    # ── Right tabbed panel ──

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(420)
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {BG}; }}
            QTabBar::tab {{
                background: {BG}; color: {TEXT_DIM}; border: none;
                padding: 8px 16px; font-size: 9pt;
            }}
            QTabBar::tab:selected {{
                color: {TEXT}; border-bottom: 2px solid {ACCENT};
            }}
            QTabBar::tab:hover {{
                color: {TEXT_SEC};
            }}
        """)

        self._tabs.addTab(self._build_info_tab(), "   Info   ")
        self._tabs.addTab(self._build_correction_tab(), "   Corrección   ")
        self._tabs.addTab(self._build_ocr_tab(), "   OCR   ")
        self._tabs.addTab(self._build_export_tab(), "   Exportar   ")

        v.addWidget(self._tabs, 1)
        return panel

    # ── Tab: Info ──

    def _build_info_tab(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)

        # Serial
        serial_grp = QGroupBox("Serial OCR")
        sl = QFormLayout(serial_grp)
        self._info_serial = QLabel("—")
        self._info_serial.setStyleSheet(f"font-size:14pt; font-weight:bold; color:{TEXT}; border:none;")
        self._info_conf = QLabel("—")
        self._info_conf.setStyleSheet(f"font-size:9pt; color:{TEXT_DIM}; border:none;")
        sl.addRow("Número:", self._info_serial)
        sl.addRow("Confianza:", self._info_conf)
        self._btn_override = QPushButton("Corregir serial…")
        self._btn_override.setFixedHeight(30)
        self._btn_override.clicked.connect(self._info_override_serial)
        sl.addRow("", self._btn_override)
        v.addWidget(serial_grp)

        # Bookmarks
        bm_grp = QGroupBox("Marcadores")
        bml = QVBoxLayout(bm_grp)
        self._bm_list = QListWidget()
        self._bm_list.setFixedHeight(80)
        self._bm_list.setStyleSheet(
            f"QListWidget {{ background:{SURFACE2}; border:1px solid {BORDER}; "
            f"border-radius:4px; padding:2px; }}"
            f"QListWidget::item {{ padding:3px 6px; font-size:8pt; }}")
        bml.addWidget(self._bm_list)
        bm_btns = QHBoxLayout()
        btn_bm_add = QPushButton("Añadir")
        btn_bm_add.setFixedHeight(28)
        btn_bm_add.clicked.connect(self._info_add_bookmark)
        btn_bm_edit = QPushButton("Editar")
        btn_bm_edit.setFixedHeight(28)
        btn_bm_edit.clicked.connect(self._info_edit_bookmark)
        btn_bm_del = QPushButton("Quitar")
        btn_bm_del.setFixedHeight(28)
        btn_bm_del.clicked.connect(self._info_del_bookmark)
        bm_btns.addWidget(btn_bm_add)
        bm_btns.addWidget(btn_bm_edit)
        bm_btns.addWidget(btn_bm_del)
        bm_btns.addStretch()
        bml.addLayout(bm_btns)
        v.addWidget(bm_grp)

        # Comment
        cm_grp = QGroupBox("Comentario")
        cml = QVBoxLayout(cm_grp)
        self._info_comment = QPlainTextEdit()
        self._info_comment.setPlaceholderText("Escribe un comentario…")
        self._info_comment.setFixedHeight(70)
        self._info_comment.textChanged.connect(self._info_comment_changed)
        cml.addWidget(self._info_comment)
        v.addWidget(cm_grp)

        # Cut point
        self._info_cut = QCheckBox("Punto de corte (inicia nuevo grupo)")
        self._info_cut.toggled.connect(self._info_cut_toggled)
        v.addWidget(self._info_cut)

        # Clear cuts
        btn_clear_cuts = QPushButton("Limpiar todos los cortes")
        btn_clear_cuts.setFixedHeight(30)
        btn_clear_cuts.clicked.connect(self.clear_cuts_requested)
        v.addWidget(btn_clear_cuts)

        v.addStretch()
        scroll.setWidget(c)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(scroll)
        return w

    # ── Tab: Correction ──

    def _build_correction_tab(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)

        rot_grp = QGroupBox("Rotación fina")
        rl = QVBoxLayout(rot_grp)
        self._rot_slider = QSlider(Qt.Horizontal)
        self._rot_slider.setRange(-45, 45)
        self._rot_slider.setValue(0)
        self._rot_slider.valueChanged.connect(self._on_slider_rot)
        rl.addWidget(self._rot_slider)

        quick_row = QHBoxLayout()
        ang_btns = [(-90, "-90°"), (90, "90°"), (180, "180°")]
        for a, t in ang_btns:
            btn = QPushButton(t)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, aa=a: self._on_quick_rot(aa))
            quick_row.addWidget(btn)
        rl.addLayout(quick_row)
        v.addWidget(rot_grp)

        self._btn_auto = QPushButton("  Auto corrección (perspectiva + deskew)")
        self._btn_auto.setFixedHeight(34)
        self._btn_auto.clicked.connect(self._on_auto_correct)
        v.addWidget(self._btn_auto)

        self._btn_reset = QPushButton("  Restablecer original")
        self._btn_reset.setFixedHeight(34)
        self._btn_reset.clicked.connect(self._on_reset_correction)
        v.addWidget(self._btn_reset)

        v.addStretch()
        scroll.setWidget(c)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(scroll)
        return w

    # ── Tab: OCR ──

    def _build_ocr_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Table
        self._ocr_table = QTableWidget(0, 6)
        self._ocr_table.setHorizontalHeaderLabels(
            ["Página", "Serial OCR", "Confianza", "Estado", "Marcador", "Comentario"])
        self._ocr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._ocr_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._ocr_table.setColumnWidth(0, 55)
        self._ocr_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._ocr_table.setColumnWidth(4, 100)
        self._ocr_table.setColumnWidth(5, 80)
        self._ocr_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._ocr_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self._ocr_table.verticalHeader().setVisible(False)
        self._ocr_table.setAlternatingRowColors(True)
        self._ocr_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._ocr_table.customContextMenuRequested.connect(self._ocr_table_context_menu)
        self._ocr_table.itemChanged.connect(self._ocr_on_item_changed)
        v.addWidget(self._ocr_table, 1)

        # Bottom row
        bottom = QFrame()
        bottom.setFixedHeight(50)
        bottom.setStyleSheet(f"background:{SURFACE}; border:none;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(12, 4, 12, 4)
        bl.setSpacing(6)

        self._ocr_summary = QLabel("0 páginas")
        self._ocr_summary.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none;")

        self._ocr_prog = QProgressBar()
        self._ocr_prog.setFixedHeight(3)
        self._ocr_prog.setTextVisible(False)
        self._ocr_prog.setVisible(False)
        self._ocr_prog.setFixedWidth(100)

        btn_ocr_page = QPushButton("OCR página")
        btn_ocr_page.setFixedHeight(28)
        btn_ocr_page.clicked.connect(self._ocr_selected)

        self._ocr_cores_spin = QSpinBox()
        self._ocr_cores_spin.setRange(1, 16)
        self._ocr_cores_spin.setValue(4)
        self._ocr_cores_spin.setFixedWidth(55)
        self._ocr_cores_spin.valueChanged.connect(self._on_cores_changed)
        cores_lbl = QLabel("Hilos:")
        cores_lbl.setStyleSheet(f"font-size:8pt; border:none; color:{TEXT_DIM};")

        bl.addWidget(self._ocr_summary)
        bl.addWidget(self._ocr_prog)
        bl.addStretch()
        bl.addWidget(btn_ocr_page)
        bl.addWidget(cores_lbl)
        bl.addWidget(self._ocr_cores_spin)
        v.addWidget(bottom)

        return w

    # ── Tab: Export ──

    def _build_export_tab(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(12)

        # ── Folder destination (shared) ──
        folder_grp = QGroupBox("Destino")
        fl = QHBoxLayout(folder_grp)
        self._export_folder = QLineEdit()
        self._export_folder.setPlaceholderText("Carpeta de destino…")
        btn_browse = QPushButton("Examinar")
        btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._export_browse)
        fl.addWidget(self._export_folder, 1)
        fl.addWidget(btn_browse)
        v.addWidget(folder_grp)

        # ── Civil exports ──
        civil_grp = QGroupBox("Registros Civiles")
        cl = QVBoxLayout(civil_grp)
        cl.setSpacing(6)

        self._btn_exp_civil = QPushButton("  ZIP — un PDF por página (serial)")
        self._btn_exp_civil.setFixedHeight(32)
        self._btn_exp_civil.clicked.connect(self._do_export_civil)
        cl.addWidget(self._btn_exp_civil)

        self._btn_exp_civil_bm = QPushButton("  ZIP — un PDF por página (marcador)")
        self._btn_exp_civil_bm.setFixedHeight(32)
        self._btn_exp_civil_bm.clicked.connect(self._do_export_civil_bookmark)
        cl.addWidget(self._btn_exp_civil_bm)

        self._btn_exp_orig = QPushButton("  PDF original (imágenes + comentarios)")
        self._btn_exp_orig.setFixedHeight(32)
        self._btn_exp_orig.clicked.connect(self._do_export_original)
        cl.addWidget(self._btn_exp_orig)

        self._btn_exp_merge = QPushButton("  Unir PDFs externos…")
        self._btn_exp_merge.setFixedHeight(32)
        self._btn_exp_merge.clicked.connect(self._switch_merge_tab)
        cl.addWidget(self._btn_exp_merge)

        v.addWidget(civil_grp)

        # ── Bookmarks PDF export ──
        bm_grp = QGroupBox("PDF con marcadores")
        bl = QVBoxLayout(bm_grp)
        bl.setSpacing(6)
        self._btn_exp_bookmarks = QPushButton("  Generar PDF con marcadores")
        self._btn_exp_bookmarks.setFixedHeight(32)
        self._btn_exp_bookmarks.clicked.connect(self._do_export_bookmarks_pdf)
        self._btn_exp_bookmarks_dpi_lbl = QLabel("DPI:")
        self._btn_exp_bookmarks_dpi_lbl.setStyleSheet("font-size:8pt; border:none; color:{TEXT_DIM};")
        self._bm_dpi = QSpinBox()
        self._bm_dpi.setRange(72, 600)
        self._bm_dpi.setValue(200)
        self._bm_dpi.setFixedWidth(65)
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(self._btn_exp_bookmarks_dpi_lbl)
        dpi_row.addWidget(self._bm_dpi)
        dpi_row.addStretch()
        bl.addWidget(self._btn_exp_bookmarks)
        bl.addLayout(dpi_row)
        v.addWidget(bm_grp)

        # ── Antecedentes exports ──
        ant_grp = QGroupBox("Antecedentes (agrupados por corte)")
        al = QVBoxLayout(ant_grp)
        al.setSpacing(6)

        num_row = QHBoxLayout()
        num_row.addWidget(QLabel("Serial inicial:"))
        self._ant_serial = QSpinBox()
        self._ant_serial.setRange(1, 999999)
        self._ant_serial.setValue(1)
        self._ant_serial.setFixedWidth(80)
        num_row.addWidget(self._ant_serial)
        num_row.addWidget(QLabel("Dígitos:"))
        self._ant_pad = QSpinBox()
        self._ant_pad.setRange(1, 10)
        self._ant_pad.setValue(5)
        self._ant_pad.setFixedWidth(55)
        self._ant_pad.valueChanged.connect(self._update_ant_preview)
        num_row.addWidget(self._ant_pad)
        self._ant_preview = QLabel("Ej: 00001.pdf")
        self._ant_preview.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none;")
        num_row.addWidget(self._ant_preview)
        num_row.addStretch()
        al.addLayout(num_row)

        rng_row = QHBoxLayout()
        self._ant_chk_range = QCheckBox("Rango")
        self._ant_chk_range.stateChanged.connect(self._toggle_ant_range)
        self._ant_desde = QSpinBox()
        self._ant_desde.setRange(1, 9999)
        self._ant_desde.setEnabled(False)
        self._ant_desde.setFixedWidth(55)
        self._ant_hasta = QSpinBox()
        self._ant_hasta.setRange(1, 9999)
        self._ant_hasta.setValue(100)
        self._ant_hasta.setEnabled(False)
        self._ant_hasta.setFixedWidth(55)
        rng_row.addWidget(self._ant_chk_range)
        rng_row.addWidget(QLabel("Desde:"))
        rng_row.addWidget(self._ant_desde)
        rng_row.addWidget(QLabel("Hasta:"))
        rng_row.addWidget(self._ant_hasta)
        rng_row.addStretch()
        al.addLayout(rng_row)

        # Groups list
        self._ant_groups = QListWidget()
        self._ant_groups.setFixedHeight(80)
        self._ant_groups.setStyleSheet(
            f"QListWidget {{ background:{SURFACE2}; border:1px solid {BORDER}; "
            f"border-radius:4px; padding:2px; font-size:8pt; }}")
        al.addWidget(self._ant_groups)

        self._ant_groups_lbl = QLabel("0 grupos")
        self._ant_groups_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none;")
        al.addWidget(self._ant_groups_lbl)

        self._btn_exp_ant = QPushButton("  ZIP — un PDF por grupo (serial)")
        self._btn_exp_ant.setFixedHeight(30)
        self._btn_exp_ant.clicked.connect(self._do_export_ant)
        al.addWidget(self._btn_exp_ant)

        self._btn_exp_ant_single = QPushButton("  PDF único con marcadores")
        self._btn_exp_ant_single.setFixedHeight(30)
        self._btn_exp_ant_single.clicked.connect(self._do_export_ant_single)
        al.addWidget(self._btn_exp_ant_single)

        self._btn_exp_ant_split = QPushButton("  Varios PDFs por marcador")
        self._btn_exp_ant_split.setFixedHeight(30)
        self._btn_exp_ant_split.clicked.connect(self._do_export_ant_split)
        al.addWidget(self._btn_exp_ant_split)

        self._btn_exp_ant_orig = QPushButton("  Exportar PDF original")
        self._btn_exp_ant_orig.setFixedHeight(30)
        self._btn_exp_ant_orig.clicked.connect(self._do_export_original)
        al.addWidget(self._btn_exp_ant_orig)

        v.addWidget(ant_grp)
        v.addStretch()

        scroll.setWidget(c)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(scroll)
        return w

    # ── Status bar ──

    def _on_page_selected(self, index: int):
        self._current_idx = index
        self._rot_angle = 0.0
        self._rot_slider.setValue(0)
        self._refresh_info_tab()

    def _refresh_info_tab(self):
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model'):
            return
        page = mw._model.get(self._current_idx) if self._current_idx >= 0 else None
        if page is None:
            self._info_serial.setText("—")
            self._info_conf.setText("—")
            self._info_comment.blockSignals(True)
            self._info_comment.setPlainText("")
            self._info_comment.blockSignals(False)
            self._info_cut.blockSignals(True)
            self._info_cut.setChecked(False)
            self._info_cut.blockSignals(False)
            self._bm_list.clear()
            return

        # Serial
        serial = page.serial or "—"
        conf = page.serial_confidence if page.serial else 0.0
        self._info_serial.setText(serial)
        conf_color = SUCCESS if conf >= 0.7 else WARNING if conf > 0 else TEXT_DIM
        self._info_conf.setText(f"{conf:.0%}")
        self._info_conf.setStyleSheet(f"font-size:9pt; color:{conf_color}; border:none;")

        # Bookmark
        self._refresh_bm_list(page)

        # Comment
        self._info_comment.blockSignals(True)
        self._info_comment.setPlainText(page.comment)
        self._info_comment.blockSignals(False)

        # Cut
        self._info_cut.blockSignals(True)
        self._info_cut.setChecked(page.is_cut_point)
        self._info_cut.blockSignals(False)

    def _refresh_bm_list(self, page=None):
        self._bm_list.clear()
        if page is None:
            from PySide6.QtWidgets import QApplication
            mw = QApplication.instance().activeWindow()
            if not mw or not hasattr(mw, '_model'):
                return
            page = mw._model.get(self._current_idx) if self._current_idx >= 0 else None
        if page is None:
            return
        bm = page.bookmarks
        if not bm and page.bookmark:
            bm = [(1, page.bookmark)]
        for lvl, title in (bm or []):
            prefix = "├─ " * (lvl - 1) + "• " if lvl > 1 else ""
            item = QListWidgetItem(f"{prefix}{title}")
            item.setData(Qt.UserRole, (lvl, title))
            self._bm_list.addItem(item)

    def _update_ant_preview(self):
        pad = self._ant_pad.value()
        ser = self._ant_serial.value()
        self._ant_preview.setText(f"Ej: {str(ser).zfill(pad)}.pdf")

    def _toggle_ant_range(self, state: int):
        en = state == Qt.Checked
        self._ant_desde.setEnabled(en)
        self._ant_hasta.setEnabled(en)

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: Info tab actions
    # ═══════════════════════════════════════════════════════════════

    def _info_override_serial(self):
        from PySide6.QtWidgets import QInputDialog
        serial, ok = QInputDialog.getText(
            self, "Corregir serial",
            "Nuevo serial (8 dígitos):",
            text=self._info_serial.text() if self._info_serial.text() != "—" else "")
        if ok and serial.strip():
            self.serial_corrected.emit(self._current_idx, serial.strip())
            self._refresh_info_tab()

    def _info_add_bookmark(self):
        from views.widgets import _BookmarkItemDialog
        from PySide6.QtWidgets import QDialog
        dlg = _BookmarkItemDialog(self, titulo="", nivel=1)
        if dlg.exec() == QDialog.Accepted:
            lvl, title = dlg.get_values()
            if not title:
                return
            labels = self._collect_bm_list()
            labels.append((lvl, title))
            self._emit_bookmarks(labels)

    def _info_edit_bookmark(self):
        from views.widgets import _BookmarkItemDialog
        from PySide6.QtWidgets import QDialog
        item = self._bm_list.currentItem()
        if not item:
            return
        lvl, title = item.data(Qt.UserRole)
        dlg = _BookmarkItemDialog(self, titulo=title, nivel=lvl)
        if dlg.exec() == QDialog.Accepted:
            lvl, title = dlg.get_values()
            if not title:
                return
            labels = self._collect_bm_list()
            row = self._bm_list.row(item)
            labels[row] = (lvl, title)
            self._emit_bookmarks(labels)

    def _info_del_bookmark(self):
        item = self._bm_list.currentItem()
        if not item:
            return
        labels = self._collect_bm_list()
        row = self._bm_list.row(item)
        labels.pop(row)
        self._emit_bookmarks(labels)

    def _collect_bm_list(self) -> list[tuple[int, str]]:
        result = []
        for i in range(self._bm_list.count()):
            result.append(self._bm_list.item(i).data(Qt.UserRole))
        return result

    def _emit_bookmarks(self, labels: list[tuple[int, str]]):
        self.bookmark_set.emit(self._current_idx, labels)
        self._refresh_bm_list()

    def _info_comment_changed(self):
        text = self._info_comment.toPlainText()
        if len(text) > 500:
            self._info_comment.blockSignals(True)
            self._info_comment.setPlainText(text[:500])
            self._info_comment.moveCursor(self._info_comment.textCursor().End)
            self._info_comment.blockSignals(False)
            return
        self.comment_set.emit(self._current_idx, text)

    def _info_cut_toggled(self, checked: bool):
        if self._current_idx >= 0:
            self.cut_toggled.emit(self._current_idx)

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: Correction tab
    # ═══════════════════════════════════════════════════════════════

    def _on_slider_rot(self, value: int):
        self._rot_angle = float(value)
        if self._current_idx >= 0:
            self.rotation_changed.emit(self._current_idx, self._rot_angle)

    def _on_quick_rot(self, delta: float):
        self._rot_angle += delta
        self._rot_slider.setValue(0)
        if self._current_idx >= 0:
            self.rotation_changed.emit(self._current_idx, self._rot_angle)

    def _on_auto_correct(self):
        self._rot_angle = 0.0
        self._rot_slider.setValue(0)
        if self._current_idx >= 0:
            self.correction_requested.emit(self._current_idx)

    def _on_reset_correction(self):
        self._rot_angle = 0.0
        self._rot_slider.setValue(0)
        if self._current_idx >= 0:
            self.reset_correction.emit(self._current_idx)

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: OCR tab
    # ═══════════════════════════════════════════════════════════════

    def _ocr_on_item_changed(self, item: QTableWidgetItem):
        if item.column() != self.COL_SERIAL:
            return
        row = item.row()
        n_item = self._ocr_table.item(row, self.COL_NUM)
        if n_item is None:
            return
        idx = n_item.data(Qt.UserRole)
        serial = item.text().strip()
        e = self._ocr_table.item(row, self.COL_STATUS)
        if e:
            e.setText("Corregido")
            e.setForeground(QColor(TEXT_SEC))
        self.serial_corrected.emit(idx, serial)
        self._refresh_ocr_summary()

    def _ocr_selected(self):
        row = self._ocr_table.currentRow()
        if row < 0:
            return
        n_item = self._ocr_table.item(row, self.COL_NUM)
        if n_item:
            self.ocr_page_requested.emit(n_item.data(Qt.UserRole))

    def _ocr_table_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        row = self._ocr_table.currentRow()
        if row < 0:
            return
        n_item = self._ocr_table.item(row, self.COL_NUM)
        if n_item is None:
            return
        idx = n_item.data(Qt.UserRole)
        menu = QMenu(self)
        act_ocr = menu.addAction("Ejecutar OCR en esta página")
        act = menu.exec(self._ocr_table.mapToGlobal(pos))
        if act == act_ocr:
            self.ocr_page_requested.emit(idx)

    def _on_cores_changed(self, value: int):
        self.parallel_workers_changed.emit(value)

    def _refresh_ocr_summary(self):
        total = self._ocr_table.rowCount()
        ok = sum(1 for r in range(total)
                 if self._ocr_table.item(r, self.COL_STATUS) and
                 self._ocr_table.item(r, self.COL_STATUS).text() in ("OK", "Corregido"))
        pend = total - ok
        self._ocr_summary.setText(f"{total} págs · {ok} OK · {pend} pend.")

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: Export tab
    # ═══════════════════════════════════════════════════════════════

    def _export_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if folder:
            self._export_folder.setText(folder)

    def _export_get_folder(self) -> str | None:
        folder = self._export_folder.text().strip()
        if not folder:
            QMessageBox.warning(self, "Carpeta requerida",
                                "Selecciona una carpeta de destino en la pestaña Exportar.")
            return None
        return folder

    def _do_export_civil(self):
        f = self._export_get_folder()
        if f:
            self.export_civil_requested.emit(f)

    def _do_export_civil_bookmark(self):
        f = self._export_get_folder()
        if f:
            self.export_bookmark_requested.emit(f)

    def _do_export_original(self):
        f = self._export_get_folder()
        if f:
            self.export_original_pdf_requested.emit(f)

    def _do_export_bookmarks_pdf(self):
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model'):
            return
        pages_data = []
        for page in mw._model.pages:
            pages_data.append({
                "index": page.index,
                "label": page.final_label,
                "image": page.display_image,
            })
        if not pages_data:
            QMessageBox.warning(self, "Sin datos", "No hay páginas para exportar.")
            return
        folder = self._export_get_folder()
        if folder:
            self.bookmarks_export_requested.emit(pages_data, folder, self._bm_dpi.value())

    def _switch_merge_tab(self):
        """Placeholder — merge de PDFs externos."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta con PDFs")
        if not folder:
            return
        from pathlib import Path
        pdfs = sorted(Path(folder).glob("*.pdf"))
        if not pdfs:
            QMessageBox.warning(self, "Sin PDFs", "No se encontraron archivos PDF en la carpeta.")
            return
        output = str(Path(folder) / "unificado.pdf")
        self.merge_requested.emit(pdfs, output)

    def _do_export_ant(self):
        f = self._export_get_folder()
        if not f:
            return
        params = {
            "folder": f,
            "serial_ini": self._ant_serial.value(),
            "padding": self._ant_pad.value(),
            "desde": self._ant_desde.value() if self._ant_chk_range.isChecked() else 0,
            "hasta": self._ant_hasta.value() if self._ant_chk_range.isChecked() else 0,
        }
        self.export_ant_requested.emit(params)

    def _do_export_ant_single(self):
        f = self._export_get_folder()
        if not f:
            return
        params = {
            "folder": f,
            "serial_ini": self._ant_serial.value(),
            "padding": self._ant_pad.value(),
            "desde": self._ant_desde.value() if self._ant_chk_range.isChecked() else 0,
            "hasta": self._ant_hasta.value() if self._ant_chk_range.isChecked() else 0,
        }
        self.export_ant_single_pdf.emit(params)

    def _do_export_ant_split(self):
        f = self._export_get_folder()
        if not f:
            return
        params = {
            "folder": f,
            "serial_ini": self._ant_serial.value(),
            "padding": self._ant_pad.value(),
            "desde": self._ant_desde.value() if self._ant_chk_range.isChecked() else 0,
            "hasta": self._ant_hasta.value() if self._ant_chk_range.isChecked() else 0,
        }
        self.export_ant_split_bookmark.emit(params)

    def _switch_export_tab(self):
        self._tabs.setCurrentIndex(3)

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: Import helpers
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    #  PUBLIC API (called by MainWindow)
    # ═══════════════════════════════════════════════════════════════

    def add_page(self, index: int, image):
        self._empty.setVisible(False)
        self._splitter.setVisible(True)
        self.grid.add_page(index, image)
        self.viewer.set_image(image)
        self._current_idx = index
        self._update_page_count()
        self._ocr_table.blockSignals(True)
        self._add_ocr_row(index, image)
        self._ocr_table.blockSignals(False)
        self._refresh_ocr_summary()

    def _add_ocr_row(self, index: int, image=None):
        row = self._ocr_table.rowCount()
        self._ocr_table.insertRow(row)
        n = QTableWidgetItem(str(index + 1))
        n.setTextAlignment(Qt.AlignCenter)
        n.setData(Qt.UserRole, index)
        n.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        s = QTableWidgetItem("—")
        s.setTextAlignment(Qt.AlignCenter)
        c = QTableWidgetItem("—")
        c.setTextAlignment(Qt.AlignCenter)
        c.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        e = QTableWidgetItem("Pendiente")
        e.setTextAlignment(Qt.AlignCenter)
        e.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        bm = QTableWidgetItem("")
        bm.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        cm = QTableWidgetItem("")
        cm.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self._ocr_table.setItem(row, self.COL_NUM, n)
        self._ocr_table.setItem(row, self.COL_SERIAL, s)
        self._ocr_table.setItem(row, self.COL_CONF, c)
        self._ocr_table.setItem(row, self.COL_STATUS, e)
        self._ocr_table.setItem(row, self.COL_BOOKMARK, bm)
        self._ocr_table.setItem(row, self.COL_COMMENT, cm)

    def remove_page(self, index: int):
        self.grid.remove_page(index)
        row = self._ocr_row_for(index)
        if row >= 0:
            self._ocr_table.removeRow(row)
        for r in range(self._ocr_table.rowCount()):
            item = self._ocr_table.item(r, self.COL_NUM)
            if item:
                item.setData(Qt.UserRole, r)
                item.setText(str(r + 1))
        self._refresh_ocr_summary()
        self._update_page_count()
        if self.grid.count == 0:
            self._empty.setVisible(True)
            self._splitter.setVisible(False)
            self._current_idx = -1
            self.viewer.set_image(None)
            self._refresh_info_tab()

    def update_page(self, index: int, image):
        self.grid.update_image(index, image)
        if index == self._current_idx:
            self.viewer.set_image(image)

    def show_page(self, index: int, image):
        self._current_idx = index
        self.viewer.set_image(image)
        self.grid.select(index)
        self._refresh_info_tab()

    def set_cut(self, index: int, is_cut: bool):
        self.grid.set_cut(index, is_cut)
        if index == self._current_idx:
            self._info_cut.blockSignals(True)
            self._info_cut.setChecked(is_cut)
            self._info_cut.blockSignals(False)

    def set_serial(self, index: int, serial: str, conf: float):
        self.grid.set_serial(index, serial, conf)
        row = self._ocr_row_for(index)
        if row >= 0:
            self._ocr_table.blockSignals(True)
            self._ocr_table.item(row, self.COL_SERIAL).setText(serial or "Sin serial")
            self._ocr_table.item(row, self.COL_CONF).setText(f"{conf:.0%}" if conf > 0 else "—")
            e = self._ocr_table.item(row, self.COL_STATUS)
            if serial:
                c = SUCCESS if conf >= 0.7 else WARNING
                e.setText("OK" if conf >= 0.7 else "Baja confianza")
                e.setForeground(QColor(c))
                self._ocr_table.item(row, self.COL_SERIAL).setForeground(QColor(c))
            else:
                e.setText("Sin serial")
                e.setForeground(QColor(DANGER))
                self._ocr_table.item(row, self.COL_SERIAL).setForeground(QColor(DANGER))
            self._ocr_table.blockSignals(False)
            self._refresh_ocr_summary()
        if index == self._current_idx:
            self._refresh_info_tab()

    def set_bookmark(self, index: int, display: str):
        self.grid.set_bookmark(index, display)
        row = self._ocr_row_for(index)
        if row >= 0:
            self._ocr_table.blockSignals(True)
            self._ocr_table.item(row, self.COL_BOOKMARK).setText(display)
            self._ocr_table.blockSignals(False)
        if index == self._current_idx:
            self._refresh_info_tab()

    def set_comment(self, index: int, display: str):
        row = self._ocr_row_for(index)
        if row >= 0:
            self._ocr_table.blockSignals(True)
            self._ocr_table.item(row, self.COL_COMMENT).setText(display)
            self._ocr_table.blockSignals(False)

    def rebuild(self, pages_data: list, progress_callback=None):
        self.grid.blockSignals(True)
        self.grid.clear_all()
        self._ocr_table.blockSignals(True)
        self._ocr_table.setRowCount(0)
        total = len(pages_data)
        for i, pd in enumerate(pages_data):
            self.grid.add_page(pd.index, pd.display_image)
            if pd.serial:
                self.grid.set_serial(pd.index, pd.serial, pd.serial_confidence)
            if pd.is_cut_point:
                self.grid.set_cut(pd.index, True)
            if pd.bookmarks:
                first = pd.bookmarks[0][1] if pd.bookmarks else ""
                n = len(pd.bookmarks)
                display = f"{first} 📑{n}" if n > 1 else first
                self.grid.set_bookmark(pd.index, display)
            elif pd.bookmark:
                self.grid.set_bookmark(pd.index, pd.bookmark)
            self._add_ocr_row(pd.index, pd.display_image)
            if pd.serial:
                self.set_ocr_result(pd.index, pd.serial, pd.serial_confidence)
            if pd.bookmark:
                bm_display = pd.bookmarks[0][1] if pd.bookmarks else pd.bookmark
                n = len(pd.bookmarks)
                display = f"{bm_display} 📑{n}" if n > 1 else bm_display
                self._ocr_table.item(self._ocr_table.rowCount() - 1, self.COL_BOOKMARK).setText(display)
            if pd.comment:
                preview = pd.comment[:40] + "…" if len(pd.comment) > 40 else pd.comment
                self._ocr_table.item(self._ocr_table.rowCount() - 1, self.COL_COMMENT).setText(preview)
            if progress_callback:
                progress_callback(i + 1, total)
        self._ocr_table.blockSignals(False)
        self._refresh_ocr_summary()
        self._update_page_count()
        if pages_data:
            self._empty.setVisible(False)
            self._splitter.setVisible(True)
        else:
            self._empty.setVisible(True)
            self._splitter.setVisible(False)
            self._current_idx = -1
            self.viewer.set_image(None)
        self.grid.blockSignals(False)
        self._refresh_info_tab()

    def set_ocr_result(self, index: int, serial: str, conf: float):
        row = self._ocr_row_for(index)
        if row < 0:
            return
        self._ocr_table.blockSignals(True)
        self._ocr_table.item(row, self.COL_SERIAL).setText(serial or "Sin serial")
        self._ocr_table.item(row, self.COL_CONF).setText(f"{conf:.0%}" if conf > 0 else "—")
        e = self._ocr_table.item(row, self.COL_STATUS)
        if serial:
            c = SUCCESS if conf >= 0.7 else WARNING
            e.setText("OK" if conf >= 0.7 else "Baja confianza")
            e.setForeground(QColor(c))
            self._ocr_table.item(row, self.COL_SERIAL).setForeground(QColor(c))
        else:
            e.setText("Sin serial")
            e.setForeground(QColor(DANGER))
            self._ocr_table.item(row, self.COL_SERIAL).setForeground(QColor(DANGER))
        self._ocr_table.blockSignals(False)
        self._refresh_ocr_summary()
        if index == self._current_idx:
            self._refresh_info_tab()

    def ocr_started(self):
        self._btn_ocr.setEnabled(False)
        self._btn_ocr.setText("Procesando…")
        self._btn_cancel_ocr.setVisible(True)
        self._ocr_prog.setRange(0, 0)
        self._ocr_prog.setVisible(True)

    def ocr_finished(self):
        self._btn_ocr.setEnabled(True)
        self._btn_ocr.setText("  OCR todas")
        self._btn_cancel_ocr.setVisible(False)
        self._ocr_prog.setVisible(False)

    def import_busy(self, busy: bool):
        self._btn_cancel_import.setVisible(busy)

    def update_groups(self, groups: list[list[int]]):
        self._ant_groups.clear()
        serial = self._ant_serial.value()
        padding = self._ant_pad.value()
        for i, group in enumerate(groups):
            label = f"Grupo {i+1}  [{len(group)} pág.]  → {str(serial + i).zfill(padding)}.pdf"
            self._ant_groups.addItem(QListWidgetItem(label))
        self._ant_groups_lbl.setText(f"{len(groups)} grupo(s)")

    def set_parallel_workers(self, n: int):
        self._ocr_cores_spin.blockSignals(True)
        self._ocr_cores_spin.setValue(n)
        self._ocr_cores_spin.blockSignals(False)

    def clear(self):
        self.grid.clear_all()
        self._ocr_table.setRowCount(0)
        self._ant_groups.clear()
        self._ant_groups_lbl.setText("0 grupos")
        self._current_idx = -1
        self.viewer.set_image(None)
        self._empty.setVisible(True)
        self._splitter.setVisible(False)
        self._rot_slider.setValue(0)
        self._export_folder.clear()
        self._ant_serial.setValue(1)
        self._ant_pad.setValue(5)
        self._ant_chk_range.setChecked(False)
        self._ant_desde.setValue(1)
        self._ant_hasta.setValue(100)
        self._btn_ocr.setEnabled(True)
        self._btn_ocr.setText("  OCR todas")
        self._btn_cancel_ocr.setVisible(False)
        self._btn_cancel_import.setVisible(False)
        self._update_page_count()
        self._refresh_ocr_summary()
        self._refresh_info_tab()

    # ── Export method stubs (for MainWindow feedback) ──

    def export_started(self):
        self._set_export_buttons(False, "Generando…")

    def export_finished(self, path: str):
        self._set_export_buttons(True)

    def export_error(self, msg: str):
        self._set_export_buttons(True)

    def export_bookmark_started(self):
        self._btn_exp_civil_bm.setEnabled(False)
        self._btn_exp_civil_bm.setText("Generando…")

    def export_bookmark_finished(self, path: str):
        self._btn_exp_civil_bm.setEnabled(True)
        self._btn_exp_civil_bm.setText("  ZIP — un PDF por página (marcador)")

    def export_bookmark_error(self, msg: str):
        self._btn_exp_civil_bm.setEnabled(True)
        self._btn_exp_civil_bm.setText("  ZIP — un PDF por página (marcador)")

    def export_single_started(self):
        self._btn_exp_ant_single.setEnabled(False)
        self._btn_exp_ant_single.setText("Generando…")

    def export_single_finished(self, path: str):
        self._btn_exp_ant_single.setEnabled(True)
        self._btn_exp_ant_single.setText("  PDF único con marcadores")

    def export_single_error(self, msg: str):
        self._btn_exp_ant_single.setEnabled(True)
        self._btn_exp_ant_single.setText("  PDF único con marcadores")

    def export_split_started(self):
        self._btn_exp_ant_split.setEnabled(False)
        self._btn_exp_ant_split.setText("Generando…")

    def export_split_finished(self, path: str):
        self._btn_exp_ant_split.setEnabled(True)
        self._btn_exp_ant_split.setText("  Varios PDFs por marcador")

    def export_split_error(self, msg: str):
        self._btn_exp_ant_split.setEnabled(True)
        self._btn_exp_ant_split.setText("  Varios PDFs por marcador")

    def export_original_started(self):
        self._btn_exp_orig.setEnabled(False)
        self._btn_exp_orig.setText("Generando…")

    def export_original_finished(self, path: str):
        self._btn_exp_orig.setEnabled(True)
        self._btn_exp_orig.setText("  PDF original (imágenes + comentarios)")

    def export_original_error(self, msg: str):
        self._btn_exp_orig.setEnabled(True)
        self._btn_exp_orig.setText("  PDF original (imágenes + comentarios)")

    def merge_started(self):
        pass

    def merge_finished(self, path: str):
        pass

    def merge_error(self, msg: str):
        pass

    def bookmarks_export_started(self):
        self._btn_exp_bookmarks.setEnabled(False)
        self._btn_exp_bookmarks.setText("Generando…")

    def bookmarks_export_finished(self, path: str):
        self._btn_exp_bookmarks.setEnabled(True)
        self._btn_exp_bookmarks.setText("  Generar PDF con marcadores")

    def bookmarks_export_error(self, msg: str):
        self._btn_exp_bookmarks.setEnabled(True)
        self._btn_exp_bookmarks.setText("  Generar PDF con marcadores")

    # ── Bookmark request from context menu ──

    def _on_bookmark_requested(self, index: int):
        from views.widgets import BookmarkDialog
        from PySide6.QtWidgets import QDialog, QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model'):
            return
        page = mw._model.get(index)
        if not page:
            return
        current = page.bookmarks if page.bookmarks else ([(1, page.bookmark)] if page.bookmark else [])
        dlg = BookmarkDialog(self, index, current)
        if dlg.exec() == QDialog.Accepted:
            labels = dlg.get_bookmarks()
            self.bookmark_set.emit(index, labels)

    def _on_comment_requested(self, index: int):
        from views.widgets import CommentDialog
        from PySide6.QtWidgets import QDialog, QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model'):
            return
        page = mw._model.get(index)
        if not page:
            return
        dlg = CommentDialog(self, index, page.comment, page.display_image)
        if dlg.exec() == QDialog.Accepted:
            text = dlg.get_comment()
            self.comment_set.emit(index, text)

    # ── Helpers ──

    def _ocr_row_for(self, page_index: int) -> int:
        for r in range(self._ocr_table.rowCount()):
            item = self._ocr_table.item(r, self.COL_NUM)
            if item and item.data(Qt.UserRole) == page_index:
                return r
        return -1

    def _update_page_count(self):
        n = self.grid.count
        self._page_count_lbl.setText(f"{n} página(s)" if n else "")

    def _set_export_buttons(self, enabled: bool, text: str | None = None):
        btns = [
            self._btn_exp_civil, self._btn_exp_civil_bm, self._btn_exp_orig,
            self._btn_exp_ant, self._btn_exp_ant_single, self._btn_exp_ant_split,
            self._btn_exp_ant_orig, self._btn_exp_bookmarks,
        ]
        for b in btns:
            b.setEnabled(enabled)
        if text and not enabled:
            self._btn_exp_civil.setText(text)
