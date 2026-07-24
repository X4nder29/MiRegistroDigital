"""Página unificada — importar, corregir, OCR y exportar en una sola vista."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFrame, QProgressBar, QFileDialog,
    QSlider, QTabWidget, QGroupBox, QSpinBox, QFormLayout,
    QCheckBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QListWidget,
    QListWidgetItem, QPlainTextEdit, QScrollArea, QComboBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import (
    QColor, QFont, QKeySequence, QShortcut, QIcon, QPixmap, QPainter,
    QTransform,
)

from views.widgets import ThumbnailGrid, ImageViewer
from models.config_model import ConfigModel
from models.scan_settings import ScanSettings
from views.theme import (
    SURFACE, SURFACE2, SURFACE3, BG, BORDER,
    TEXT, TEXT_SEC, TEXT_DIM, SUCCESS, DANGER, WARNING, INFO,
    ACCENT2, pill_qss, COMPACT_LIST_QSS, _hex_to_rgba,
)


def _emoji_icon(emoji: str, size: int = 20) -> QIcon:
    """Renderiza un emoji a un QIcon, rotado 90° para orientarlo correctamente
    en la barra de pestañas West (barra lateral izquierda)."""
    box = size + 10
    pm = QPixmap(box, box)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    f = QFont()
    f.setPointSize(size)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, emoji)
    p.end()
    pm = pm.transformed(QTransform().rotate(90), Qt.SmoothTransformation)
    return QIcon(pm)


class DigitizationPage(QWidget):
    # ── Import ──
    import_images_requested = Signal(list)
    import_pdf_requested    = Signal(list)
    open_project_requested  = Signal()

    # ── Scan (TWAIN) ──
    scan_sources_refresh_requested = Signal()
    scan_requested                 = Signal(object)   # ScanSettings
    scan_cancel_requested          = Signal()

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

    # ── Export ──
    export_civil_requested       = Signal(str)
    export_bookmark_requested    = Signal(str)
    export_original_pdf_requested = Signal(str)

    export_ant_single_pdf         = Signal(dict)
    export_ant_split_bookmark     = Signal(dict)

    merge_requested            = Signal(list, str)

    # Tabla OCR: 4 columnas. Marcador/Comentario se muestran en la pestaña Info
    # y en las miniaturas, no aquí.
    COL_NUM, COL_SERIAL, COL_CONF, COL_STATUS = 0, 1, 2, 3

    def __init__(self, parent=None, config: ConfigModel | None = None):
        super().__init__(parent)
        self._cfg = config
        self._current_idx = -1
        self._rot_angle = 0.0
        self._building = False
        self._status_font = QFont()
        self._status_font.setBold(True)
        self._build()

    # ═══════════════════════════════════════════════════════════════
    #  BUILD
    # ═══════════════════════════════════════════════════════════════

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._apply_import_shortcut()

        self._empty = self._build_empty_state()
        root.addWidget(self._empty)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: Thumbnail grid ──
        # Sin tope superior de ancho: el usuario puede expandir el panel con el
        # divisor tanto como permitan los mínimos del visor/panel derecho
        # (QListView.Adjust reorganiza las miniaturas en varias columnas).
        self.grid = ThumbnailGrid()
        self.grid.setMinimumWidth(150)
        self.grid.page_selected.connect(self._on_page_selected)
        self.grid.cut_toggled.connect(self.cut_toggled)
        self.grid.page_deleted.connect(self.page_deleted)
        self.grid.reorder_requested.connect(self.page_reordered)
        self.grid.bookmark_requested.connect(self._on_bookmark_requested)
        self.grid.comment_requested.connect(self._on_comment_requested)
        splitter.addWidget(self.grid)

        # ── Center: Viewer (with zoom/pan) ──
        splitter.addWidget(self._build_viewer_panel())

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

        scan_seq = "Ctrl+K"
        if self._cfg:
            scan_seq = self._cfg.get("shortcuts", "scan", scan_seq)
        QShortcut(QKeySequence(scan_seq), self, self._start_scan)

        # Atajo para añadir marcador a la página actual — recupera la función
        # que tenía la antigua "Vista completa" (FullscreenViewer, Ctrl+B).
        bm_seq = "Ctrl+B"
        if self._cfg:
            bm_seq = self._cfg.get("shortcuts", "bookmark", bm_seq)
        QShortcut(QKeySequence(bm_seq), self, self._shortcut_add_bookmark)

    def _shortcut_add_bookmark(self):
        """Añade un marcador a la página en vista previa (mismo flujo que el
        botón "Añadir" de la pestaña Info). No hace nada sin página activa."""
        if self._current_idx >= 0:
            self._info_add_bookmark()

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)

        icon = QLabel("📄")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size:40pt; border:none;")
        lay.addWidget(icon)

        msg = QLabel("Importa un PDF, o escanea para comenzar")
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(f"color:{TEXT_SEC}; font-size:12pt; border:none;")
        lay.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn = QPushButton("📄  Importar")
        btn.setProperty("primary", True)
        btn.setFixedHeight(36)
        btn.setFixedWidth(190)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(self._open_pdf)
        btn_row.addWidget(btn)

        self._btn_scan = QPushButton("🖨  Escanear")
        self._btn_scan.setFixedHeight(36)
        self._btn_scan.setFixedWidth(190)
        self._btn_scan.setFocusPolicy(Qt.NoFocus)
        self._btn_scan.setToolTip("Configurar y escanear con un dispositivo TWAIN")
        self._btn_scan.clicked.connect(self._show_scanner_tab)
        btn_row.addWidget(self._btn_scan)

        btn_open = QPushButton("📂  Abrir proyecto")
        btn_open.setFixedHeight(36)
        btn_open.setFixedWidth(190)
        btn_open.setFocusPolicy(Qt.NoFocus)
        btn_open.clicked.connect(self.open_project_requested)
        btn_row.addWidget(btn_open)

        lay.addLayout(btn_row)

        return w

    # ── Viewer panel (center, with zoom/pan) ──

    def _build_viewer_panel(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # La barra de zoom vive ahora al pie de la tira de pestañas (ver
        # _build_zoom_controls / setCornerWidget), no en una barra superior.
        self.viewer = ImageViewer()
        self.viewer.set_zoom_enabled(True)
        self.viewer.page_nav.connect(self._navigate_page)
        self.viewer.area_selected.connect(self._on_viewer_area_selected)
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setWidget(self.viewer)
        v.addWidget(scroll, 1)

        for seq in ("Ctrl++", "Ctrl+=", "Ctrl+-", "Ctrl+0"):
            slot = self._zoom_fit if seq == "Ctrl+0" else (self._zoom_out if seq == "Ctrl+-" else self._zoom_in)
            QShortcut(QKeySequence(seq), self, slot)

        return panel

    def _zoom_in(self):
        self.viewer.zoom_in()

    def _zoom_out(self):
        self.viewer.zoom_out()

    def _zoom_fit(self):
        self.viewer.zoom_fit()

    # ── Right tabbed panel ──

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        # Sin tope superior de ancho: el usuario puede expandir el panel derecho
        # con el divisor tanto como permitan los mínimos del visor/panel izquierdo.
        panel.setMinimumWidth(300)
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.West)
        self._tabs.setIconSize(QSize(22, 22))
        # Banda contrastante a lo alto de todo el panel: el fondo del QTabWidget
        # (SURFACE2) se ve en toda la columna izquierda, mientras el panel de
        # contenido (pane) pinta BG encima — así la tira de pestañas lee como
        # una franja distinta de arriba a abajo, no solo detrás de cada botón.
        self._tabs.setStyleSheet(f"""
            QTabWidget {{ background: {SURFACE2}; }}
            QTabWidget::pane {{
                border: none; border-left: 1px solid {BORDER}; background: {BG};
            }}
            QTabBar {{ background: transparent; }}
            QTabBar::tab {{
                background: transparent; color: {TEXT_DIM};
                border: none;
                /* Celdas CUADRADAS (~{self._TAB_STRIP_W}px de lado): el ancho de
                   contenido (min-width) + el indicador de 3px = ancho de tira;
                   el padding vertical iguala la altura al ancho. El indicador de
                   selección se reserva en TODOS los estados (transparent) para
                   que el icono no se desplace ni la celda cambie de tamaño. */
                border-right: 3px solid transparent;
                padding: 5px 0px;
                min-width: {self._TAB_STRIP_W - 3}px;
                min-height: 22px;
            }}
            QTabBar::tab:selected {{
                color: {TEXT}; background: {BG};
                border-right: 3px solid {ACCENT2};
            }}
            QTabBar::tab:hover:!selected {{
                background: {SURFACE3};
            }}
        """)

        # Iconos (emoji rasterizados a QIcon) en vez de texto — con 5 pestañas,
        # texto horizontal desborda el panel (300-420px). Un icono NO se rota en
        # posición West (solo el texto sí), por eso se ven verticales/derechos.
        self._tabs.addTab(self._build_info_tab(), _emoji_icon("ℹ️"), "")
        self._tabs.setTabToolTip(0, "Info")
        self._tabs.addTab(self._build_correction_tab(), _emoji_icon("📐"), "")
        self._tabs.setTabToolTip(1, "Corrección")
        self._scanner_tab = self._build_scanner_tab()
        self._tabs.addTab(self._scanner_tab, _emoji_icon("🖨"), "")
        self._tabs.setTabToolTip(2, "Escáner")
        self._tabs.addTab(self._build_ocr_tab(), _emoji_icon("🔤"), "")
        self._tabs.setTabToolTip(3, "OCR")
        self._tabs.addTab(self._build_export_tab(), _emoji_icon("📤"), "")
        self._tabs.setTabToolTip(4, "Exportar")

        v.addWidget(self._tabs, 1)

        # Columna de zoom anclada al PIE de la tira de pestañas West. Qt no
        # coloca cornerWidgets en pestañas West (quedan con geometría 0), así que
        # se superpone como hijo del QTabWidget, reposicionado en eventFilter.
        # Ancho = ancho de la tira (STRIP_W) para que continúe la banda SURFACE2.
        self._zoom_bar = self._build_zoom_controls()
        self._zoom_bar.setParent(self._tabs)
        self._zoom_bar.setFixedWidth(self._TAB_STRIP_W)
        self._tabs.installEventFilter(self)
        self._reposition_zoom_bar()
        return panel

    _TAB_STRIP_W = 48  # lado de la celda cuadrada de pestaña = ancho de la tira West

    def _build_zoom_controls(self) -> QWidget:
        """Columna de botones de zoom anclada al fondo de la tira de pestañas.
        Fondo TRANSPARENTE: se superpone sobre el QTabWidget (banda SURFACE2), así
        que los botones se funden con la misma tira continua que los iconos de
        pestaña, sin recuadro. Glifos monocromos (+ / − / ⤢) que renderizan
        limpios, en vez de los emoji-lupa anteriores."""
        w = QWidget()
        # Sin fondo propio (transparent → deja ver la banda SURFACE2 del
        # QTabWidget). Botones también transparentes; hover/pressed discretos
        # (utilidad, no acción focal). Estrategia de profundidad: solo bordes.
        w.setStyleSheet(f"""
            QWidget {{ background: transparent; }}
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: none; border-radius: 7px;
                font-size: 15pt; font-weight: 500;
                padding: 0;
            }}
            QPushButton:hover {{ background: {SURFACE3}; color: {TEXT}; }}
            QPushButton:pressed {{ background: {BORDER}; color: {TEXT}; }}
        """)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(5, 8, 5, 10)
        lay.setSpacing(4)
        # Separador superior: marca dónde terminan las pestañas y empiezan
        # los controles, dentro de la misma banda.
        top_border = QFrame()
        top_border.setFixedHeight(1)
        top_border.setStyleSheet(f"background: {BORDER}; border: none;")
        lay.addWidget(top_border)
        lay.addSpacing(4)
        # Zoom +/− son las acciones frecuentes: van juntas. "Ajustar" es
        # secundaria, separada por un pequeño hueco.
        for glyph, tip, slot, gap_after in [
            ("+",  "Acercar (Ctrl++)", self._zoom_in,  False),
            ("−",  "Alejar (Ctrl+-)",  self._zoom_out, True),
            ("⤢",  "Ajustar (Ctrl+0)", self._zoom_fit, False),
        ]:
            b = QPushButton(glyph)
            b.setFixedSize(40, 32)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(slot)
            lay.addWidget(b, 0, Qt.AlignHCenter)
            if gap_after:
                lay.addSpacing(6)
        return w

    def _reposition_zoom_bar(self):
        """Ancla la columna de zoom al fondo-izquierda del QTabWidget (sobre la
        parte baja, vacía, de la banda de pestañas)."""
        if not hasattr(self, "_zoom_bar"):
            return
        h = self._zoom_bar.sizeHint().height()
        self._zoom_bar.setGeometry(0, max(0, self._tabs.height() - h),
                                   self._TAB_STRIP_W, h)
        self._zoom_bar.raise_()
        self._zoom_bar.show()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._tabs and event.type() == QEvent.Resize:
            self._reposition_zoom_bar()
        return super().eventFilter(obj, event)

    # ── Tab: Info ──

    def _build_info_tab(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(16)

        # Serial — el dato más importante de la página: tamaño/peso propios,
        # no una fila más de un QFormLayout genérico.
        serial_grp = QGroupBox("Serial OCR")
        sv = QVBoxLayout(serial_grp)
        sv.setSpacing(8)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(10)
        self._info_serial = QLabel("—")
        self._info_serial.setStyleSheet(f"font-size:20pt; font-weight:700; color:{TEXT}; border:none;")
        hero_row.addWidget(self._info_serial)
        hero_row.addStretch()
        self._info_conf = QLabel("—")
        self._info_conf.setStyleSheet(pill_qss(TEXT_DIM))
        hero_row.addWidget(self._info_conf, 0, Qt.AlignVCenter)
        sv.addLayout(hero_row)

        sv.addSpacing(8)  # separa la lectura (serial) de la acción (corregir)
        self._btn_override = QPushButton("Corregir serial…")
        self._btn_override.setFixedHeight(32)
        self._btn_override.clicked.connect(self._info_override_serial)
        sv.addWidget(self._btn_override)
        v.addWidget(serial_grp)

        # Bookmarks
        bm_grp = QGroupBox("Marcadores")
        bml = QVBoxLayout(bm_grp)
        bml.setSpacing(8)
        self._bm_list = QListWidget()
        self._bm_list.setFixedHeight(80)
        self._bm_list.setStyleSheet(COMPACT_LIST_QSS)
        bml.addWidget(self._bm_list)
        bm_btns = QHBoxLayout()
        bm_btns.setSpacing(8)
        btn_bm_add = QPushButton("Añadir")
        btn_bm_add.setFixedHeight(32)
        btn_bm_add.clicked.connect(self._info_add_bookmark)
        btn_bm_edit = QPushButton("Editar")
        btn_bm_edit.setFixedHeight(32)
        btn_bm_edit.clicked.connect(self._info_edit_bookmark)
        btn_bm_del = QPushButton("Quitar")
        btn_bm_del.setFixedHeight(32)
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
        btn_clear_cuts.setFixedHeight(32)
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
        v.setSpacing(16)

        rot_grp = QGroupBox("Rotación fina")
        rl = QVBoxLayout(rot_grp)
        rl.setSpacing(8)
        slider_row = QHBoxLayout()
        self._rot_slider = QSlider(Qt.Horizontal)
        self._rot_slider.setRange(-45, 45)
        self._rot_slider.setValue(0)
        self._rot_slider.valueChanged.connect(self._on_slider_rot)
        slider_row.addWidget(self._rot_slider, 1)
        self._rot_angle_lbl = QLabel("0°")
        self._rot_angle_lbl.setFixedWidth(36)
        self._rot_angle_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._rot_angle_lbl.setStyleSheet(f"color:{TEXT}; font-size:9pt; font-weight:600; border:none;")
        slider_row.addWidget(self._rot_angle_lbl)
        rl.addLayout(slider_row)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        ang_btns = [(-90, "-90°"), (90, "90°"), (180, "180°")]
        for a, t in ang_btns:
            btn = QPushButton(t)
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked, aa=a: self._on_quick_rot(aa))
            quick_row.addWidget(btn)
        rl.addLayout(quick_row)
        v.addWidget(rot_grp)

        self._btn_auto = QPushButton("Auto corrección (perspectiva + deskew)")
        self._btn_auto.setProperty("primary", True)
        self._btn_auto.setFixedHeight(34)
        self._btn_auto.clicked.connect(self._on_auto_correct)
        v.addWidget(self._btn_auto)

        self._btn_reset = QPushButton("Restablecer original")
        self._btn_reset.setProperty("danger", True)
        self._btn_reset.setFixedHeight(34)
        self._btn_reset.clicked.connect(self._on_reset_correction)
        v.addWidget(self._btn_reset)

        v.addStretch()
        scroll.setWidget(c)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(scroll)
        return w

    # ── Tab: Scanner (TWAIN) ──

    def _build_scanner_tab(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(16)

        cfg = self._cfg.section("scanner") if self._cfg else {}

        # ── Isla de opciones ──
        # Un QFormLayout alinea todas las etiquetas a la izquierda de forma
        # consistente (antes se mezclaba "etiqueta arriba" con "etiqueta en
        # línea"). El título de la isla es "Opciones de escaneo": la pestaña ya
        # aporta el contexto "Escáner", repetirlo era redundante.
        grp = QGroupBox("Opciones de escaneo")
        form = QFormLayout(grp)
        form.setSpacing(10)
        form.setContentsMargins(0, 4, 0, 0)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Device
        self._scan_device = QComboBox()
        self._scan_device.setEditable(False)
        form.addRow("Dispositivo:", self._scan_device)

        # DPI
        self._scan_dpi = QSpinBox()
        self._scan_dpi.setRange(100, 1200)
        self._scan_dpi.setSingleStep(50)
        self._scan_dpi.setValue(cfg.get("dpi", 300))
        form.addRow("Resolución (DPI):", self._scan_dpi)

        # Color mode
        self._scan_color = QComboBox()
        self._scan_color.addItem("Color", "color")
        self._scan_color.addItem("Escala de grises", "grayscale")
        self._scan_color.addItem("Blanco y negro", "bw")
        idx = max(0, self._scan_color.findData(cfg.get("color_mode", "color")))
        self._scan_color.setCurrentIndex(idx)
        form.addRow("Modo de color:", self._scan_color)

        # Source (ADF / Flatbed)
        self._scan_source = QComboBox()
        self._scan_source.addItem("Alimentador automático (ADF)", "adf")
        self._scan_source.addItem("Cristal (Flatbed)", "flatbed")
        idx = max(0, self._scan_source.findData(cfg.get("source", "adf")))
        self._scan_source.setCurrentIndex(idx)
        self._scan_source.currentIndexChanged.connect(self._on_scan_source_changed)
        form.addRow("Origen:", self._scan_source)

        # Duplex — fila sin etiqueta; el checkbox pinta transparente (regla
        # global QCheckBox) para no mostrar un recuadro de fondo distinto.
        self._scan_duplex = QCheckBox("Escaneo dúplex (ambas caras)")
        self._scan_duplex.setChecked(cfg.get("duplex", True))
        form.addRow("", self._scan_duplex)
        self._on_scan_source_changed()

        v.addWidget(grp)

        # Actualizar escáneres — acción secundaria prominente (antes solo un
        # icono 🔄 diminuto junto al combo). Reusa scan_sources_refresh_requested.
        self._btn_scan_refresh = QPushButton("🔄  Actualizar escáneres")
        self._btn_scan_refresh.setFixedHeight(32)
        self._btn_scan_refresh.setToolTip("Volver a detectar los dispositivos TWAIN conectados")
        self._btn_scan_refresh.clicked.connect(self.scan_sources_refresh_requested)
        v.addWidget(self._btn_scan_refresh)

        self._btn_scan_tab = QPushButton("🖨  Escanear")
        self._btn_scan_tab.setProperty("primary", True)
        self._btn_scan_tab.setFixedHeight(34)
        self._btn_scan_tab.clicked.connect(self._start_scan)
        v.addWidget(self._btn_scan_tab)

        # Botón contorneado (outline): borde rojo visible sobre fondo
        # transparente para que lea claramente como acción de cancelar.
        self._btn_scan_cancel = QPushButton("Cancelar escaneo")
        self._btn_scan_cancel.setProperty("danger", True)
        self._btn_scan_cancel.setFixedHeight(32)
        self._btn_scan_cancel.setVisible(False)
        self._btn_scan_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {DANGER};
                border: 1px solid {DANGER};
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background: {_hex_to_rgba(DANGER, 0.12)};
                border-color: {DANGER};
            }}
        """)
        self._btn_scan_cancel.clicked.connect(self.scan_cancel_requested)
        v.addWidget(self._btn_scan_cancel)

        self._scan_status_lbl = QLabel("")
        self._scan_status_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none;")
        v.addWidget(self._scan_status_lbl)

        v.addStretch()
        scroll.setWidget(c)
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(scroll)
        return w

    def _on_scan_source_changed(self):
        is_adf = self._scan_source.currentData() == "adf"
        self._scan_duplex.setEnabled(is_adf)

    # ── Tab: OCR ──

    def _build_ocr_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Table
        self._ocr_table = QTableWidget(0, 4)
        self._ocr_table.setHorizontalHeaderLabels(
            ["Página", "Serial OCR", "Confianza", "Estado"])
        self._ocr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._ocr_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._ocr_table.setColumnWidth(0, 55)
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

        # Selector de área OCR: al activarlo, el usuario dibuja un rectángulo
        # sobre la vista previa; ese área (normalizada) se aplica a TODAS las
        # páginas para acotar dónde busca el serial el OCR.
        self._btn_ocr_area = QPushButton("Área OCR")
        self._btn_ocr_area.setFixedHeight(32)
        self._btn_ocr_area.setCheckable(True)
        self._btn_ocr_area.setToolTip(
            "Selecciona en la vista previa la zona donde el OCR buscará el serial "
            "(se aplica a todas las páginas)")
        self._btn_ocr_area.toggled.connect(self._toggle_ocr_area)

        btn_ocr_page = QPushButton("OCR página")
        btn_ocr_page.setFixedHeight(32)
        btn_ocr_page.clicked.connect(self._ocr_selected)

        # OCR de todas las páginas — se procesan en paralelo según "Hilos".
        self._btn_ocr_all = QPushButton("OCR todo")
        self._btn_ocr_all.setProperty("primary", True)
        self._btn_ocr_all.setFixedHeight(32)
        self._btn_ocr_all.setToolTip(
            "Ejecuta OCR en todas las páginas pendientes en paralelo")
        self._btn_ocr_all.clicked.connect(self.ocr_all_requested)

        self._ocr_cores_spin = QSpinBox()
        self._ocr_cores_spin.setRange(1, 16)
        self._ocr_cores_spin.setValue(4)
        self._ocr_cores_spin.setFixedWidth(68)
        self._ocr_cores_spin.valueChanged.connect(self._on_cores_changed)
        cores_lbl = QLabel("Hilos:")
        cores_lbl.setStyleSheet(f"font-size:8pt; border:none; color:{TEXT_DIM};")

        bl.addWidget(self._ocr_summary)
        bl.addWidget(self._ocr_prog)
        bl.addStretch()
        bl.addWidget(self._btn_ocr_area)
        bl.addWidget(btn_ocr_page)
        bl.addWidget(self._btn_ocr_all)
        bl.addWidget(cores_lbl)
        bl.addWidget(self._ocr_cores_spin)
        v.addWidget(bottom)

        return w

    def _toggle_ocr_area(self, checked: bool):
        """Activa/desactiva el modo de selección de área sobre la vista previa."""
        self.viewer.enable_area_selection(checked)
        if checked:
            self._tabs.setCurrentIndex(3)  # asegura visible la pestaña OCR

    def _on_viewer_area_selected(self, x1: float, y1: float, x2: float, y2: float):
        """El usuario terminó de dibujar el área en la vista previa."""
        idx = self._current_idx if self._current_idx >= 0 else 0
        self.ocr_area_saved.emit(idx, x1, y1, x2, y2)
        self._btn_ocr_area.setChecked(False)
        self.viewer.enable_area_selection(False)

    # ── Tab: Export ──

    def _build_export_tab(self) -> QWidget:
        w = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(16)

        # ── Folder destination (shared) ──
        folder_grp = QGroupBox("Destino")
        fl = QHBoxLayout(folder_grp)
        self._export_folder = QLineEdit()
        self._export_folder.setPlaceholderText("Carpeta de destino…")
        btn_browse = QPushButton("Examinar")
        btn_browse.setFixedHeight(32)
        btn_browse.clicked.connect(self._export_browse)
        fl.addWidget(self._export_folder, 1)
        fl.addWidget(btn_browse)
        v.addWidget(folder_grp)

        # ── Registros Civiles ──
        civil_grp = QGroupBox("Registros Civiles")
        al = QVBoxLayout(civil_grp)
        al.setSpacing(8)

        rng_row = QHBoxLayout()
        rng_row.setSpacing(8)
        self._ant_chk_range = QCheckBox("Rango")
        self._ant_chk_range.stateChanged.connect(self._toggle_ant_range)
        self._ant_desde = QSpinBox()
        self._ant_desde.setRange(1, 9999)
        self._ant_desde.setEnabled(False)
        self._ant_desde.setFixedWidth(78)
        self._ant_hasta = QSpinBox()
        self._ant_hasta.setRange(1, 9999)
        self._ant_hasta.setValue(100)
        self._ant_hasta.setEnabled(False)
        self._ant_hasta.setFixedWidth(78)
        rng_row.addWidget(self._ant_chk_range)
        rng_row.addWidget(QLabel("Desde:"))
        rng_row.addWidget(self._ant_desde)
        rng_row.addWidget(QLabel("Hasta:"))
        rng_row.addWidget(self._ant_hasta)
        rng_row.addStretch()
        al.addLayout(rng_row)

        al.addSpacing(8)  # separa el filtro (rango) de las acciones de exportación

        self._btn_exp_civil = QPushButton("ZIP — un PDF por página (serial)")
        self._btn_exp_civil.setProperty("primary", True)
        self._btn_exp_civil.setFixedHeight(32)
        self._btn_exp_civil.clicked.connect(self._do_export_civil)
        al.addWidget(self._btn_exp_civil)

        self._btn_exp_civil_bm = QPushButton("ZIP — un PDF por página (marcador)")
        self._btn_exp_civil_bm.setFixedHeight(32)
        self._btn_exp_civil_bm.clicked.connect(self._do_export_civil_bookmark)
        al.addWidget(self._btn_exp_civil_bm)

        self._btn_exp_ant_single = QPushButton("PDF único con marcadores")
        self._btn_exp_ant_single.setFixedHeight(32)
        self._btn_exp_ant_single.clicked.connect(self._do_export_ant_single)
        al.addWidget(self._btn_exp_ant_single)

        self._btn_exp_ant_split = QPushButton("Varios PDFs por marcador")
        self._btn_exp_ant_split.setFixedHeight(32)
        self._btn_exp_ant_split.clicked.connect(self._do_export_ant_split)
        al.addWidget(self._btn_exp_ant_split)

        self._btn_exp_ant_orig = QPushButton("Exportar PDF original")
        self._btn_exp_ant_orig.setFixedHeight(32)
        self._btn_exp_ant_orig.clicked.connect(self._do_export_original)
        al.addWidget(self._btn_exp_ant_orig)

        self._btn_exp_merge = QPushButton("Unir PDFs externos…")
        self._btn_exp_merge.setFixedHeight(32)
        self._btn_exp_merge.clicked.connect(self._switch_merge_tab)
        al.addWidget(self._btn_exp_merge)

        v.addWidget(civil_grp)
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
        self._update_viewer_current()
        self._refresh_info_tab()

    def _update_viewer_current(self):
        """Muestra en el visor central la página seleccionada. Antes el visor
        solo se actualizaba al añadir páginas, no al cambiar de selección."""
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model') or self._current_idx < 0:
            return
        page = mw._model.get(self._current_idx)
        if page is not None:
            self.viewer.set_image(page.display_image)

    def _navigate_page(self, delta: int):
        """Navegación con flechas ← / →: selecciona la página anterior/siguiente
        por la misma vía que un clic en la miniatura, acotada a los extremos."""
        n = self.grid.count
        if n == 0:
            return
        # Sin selección previa, la primera flecha lleva a la página 0.
        new = 0 if self._current_idx < 0 else max(0, min(self._current_idx + delta, n - 1))
        if new == self._current_idx:
            return
        self.grid.select(new)
        self._on_page_selected(new)
        self.viewer.setFocus()

    def keyPressEvent(self, event):
        # Red de seguridad: si el foco está en la zona de página (no en un
        # campo de texto/spin, que consumen las flechas), ← / → navegan.
        if event.key() == Qt.Key_Left:
            self._navigate_page(-1)
            event.accept()
            return
        if event.key() == Qt.Key_Right:
            self._navigate_page(1)
            event.accept()
            return
        super().keyPressEvent(event)

    def _refresh_info_tab(self):
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        if not mw or not hasattr(mw, '_model'):
            return
        page = mw._model.get(self._current_idx) if self._current_idx >= 0 else None
        if page is None:
            self._info_serial.setText("—")
            self._info_conf.setText("—")
            self._info_conf.setStyleSheet(pill_qss(TEXT_DIM))
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
        self._info_conf.setText(f"{conf:.0%}" if conf > 0 else "—")
        self._info_conf.setStyleSheet(pill_qss(conf_color))

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
        self._rot_angle_lbl.setText(f"{value}°")
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
            e.setForeground(QColor(INFO))
            e.setFont(self._status_font)
        self.serial_corrected.emit(idx, serial)
        self._refresh_ocr_summary()

    def _ocr_selected(self):
        # Actúa sobre la página mostrada en la vista previa (miniatura/visor),
        # no sobre una fila que haya que seleccionar aparte en la tabla OCR.
        # _current_idx usa la misma convención de índice de página que el rol
        # Qt.UserRole de COL_NUM (ver add_ocr_row / _ocr_row_for).
        if self._current_idx >= 0:
            idx = self._current_idx
        else:
            # Fallback: fila seleccionada en la tabla OCR (si no hay vista previa).
            row = self._ocr_table.currentRow()
            if row < 0:
                return
            n_item = self._ocr_table.item(row, self.COL_NUM)
            if n_item is None:
                return
            idx = n_item.data(Qt.UserRole)
        # Mantener la tabla OCR coherente con la vista previa.
        tbl_row = self._ocr_row_for(idx)
        if tbl_row >= 0:
            self._ocr_table.selectRow(tbl_row)
        self.ocr_page_requested.emit(idx)

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

    def _do_export_ant_single(self):
        f = self._export_get_folder()
        if not f:
            return
        params = {
            "folder": f,
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
            "desde": self._ant_desde.value() if self._ant_chk_range.isChecked() else 0,
            "hasta": self._ant_hasta.value() if self._ant_chk_range.isChecked() else 0,
        }
        self.export_ant_split_bookmark.emit(params)

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: Import helpers
    # ═══════════════════════════════════════════════════════════════

    def _open_pdf(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar PDF", "", "PDF (*.pdf);;Todos (*.*)")
        if paths:
            self.import_pdf_requested.emit([Path(p) for p in paths])

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL: Scan helpers
    # ═══════════════════════════════════════════════════════════════

    def _show_scanner_tab(self):
        """Escanear desde el estado vacío no dispara el escaneo directamente —
        primero muestra la vista de trabajo en la pestaña Escáner para que el
        usuario revise/ajuste el dispositivo y las opciones antes de escanear."""
        self._empty.setVisible(False)
        self._splitter.setVisible(True)
        self._tabs.setCurrentWidget(self._scanner_tab)

    def _start_scan(self):
        settings = self.get_scan_settings()
        if self._cfg:
            for k, v in settings.to_dict().items():
                self._cfg.set("scanner", k, v)
        self.scan_requested.emit(settings)

    def get_scan_settings(self) -> ScanSettings:
        return ScanSettings(
            device_name=self._scan_device.currentText() if self._scan_device.count() else "",
            dpi=self._scan_dpi.value(),
            color_mode=self._scan_color.currentData(),
            duplex=self._scan_duplex.isChecked(),
            source=self._scan_source.currentData(),
        )

    def set_scan_settings(self, s: ScanSettings):
        if s.device_name:
            i = self._scan_device.findText(s.device_name)
            if i >= 0:
                self._scan_device.setCurrentIndex(i)
        self._scan_dpi.setValue(s.dpi)
        i = self._scan_color.findData(s.color_mode)
        if i >= 0:
            self._scan_color.setCurrentIndex(i)
        i = self._scan_source.findData(s.source)
        if i >= 0:
            self._scan_source.setCurrentIndex(i)
        self._scan_duplex.setChecked(s.duplex)
        self._on_scan_source_changed()

    def set_scanner_sources(self, names: list[str]):
        current = self._scan_device.currentText()
        self._scan_device.clear()
        self._scan_device.addItems(names)
        if current and current in names:
            self._scan_device.setCurrentText(current)
        else:
            for i, name in enumerate(names):
                low = name.lower()
                if "s2070" in low or "kodak" in low:
                    self._scan_device.setCurrentIndex(i)
                    break

    def set_scanning(self, active: bool):
        self._btn_scan.setEnabled(not active)
        self._btn_scan_tab.setEnabled(not active)
        self._btn_scan_cancel.setVisible(active)
        if not active:
            self._scan_status_lbl.setText("")

    def set_scan_progress(self, count: int):
        self._scan_status_lbl.setText(f"Escaneando… {count} página(s)")

    # ═══════════════════════════════════════════════════════════════
    #  PUBLIC API (called by MainWindow)
    # ═══════════════════════════════════════════════════════════════

    def add_page(self, index: int, image):
        self._empty.setVisible(False)
        self._splitter.setVisible(True)
        self.grid.add_page(index, image)
        self.viewer.set_image(image)
        self._current_idx = index
        self._ocr_table.blockSignals(True)
        self._add_ocr_row(index, image)
        self._ocr_table.blockSignals(False)
        self._refresh_ocr_summary()
        self._update_scanner_tab_visible()

    def _update_scanner_tab_visible(self):
        """La pestaña Escáner SIEMPRE está visible — tenga o no contenido el
        documento (PDF/proyecto abierto o páginas escaneadas), el usuario debe
        poder escanear/añadir páginas en cualquier momento. Este método solo
        garantiza que la pestaña esté presente; nunca la oculta."""
        if self._tabs.indexOf(self._scanner_tab) == -1:
            self._tabs.insertTab(2, self._scanner_tab, _emoji_icon("🖨"), "")
            self._tabs.setTabToolTip(2, "Escáner")

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
        e.setForeground(QColor(TEXT_DIM))
        e.setFont(self._status_font)
        self._ocr_table.setItem(row, self.COL_NUM, n)
        self._ocr_table.setItem(row, self.COL_SERIAL, s)
        self._ocr_table.setItem(row, self.COL_CONF, c)
        self._ocr_table.setItem(row, self.COL_STATUS, e)

    def _ensure_ocr_cells(self, row: int):
        """Garantiza que la fila tenga las celdas Serial/Confianza/Estado. Una
        celda de QTableWidget puede ser None si nunca se pobló; sin esto los
        setters (set_ocr_result/set_serial) lanzan AttributeError. COL_NUM está
        garantizada por _ocr_row_for, que localiza la fila justamente por ella."""
        for col, text in ((self.COL_SERIAL, "—"),
                          (self.COL_CONF, "—"),
                          (self.COL_STATUS, "Pendiente")):
            if self._ocr_table.item(row, col) is None:
                it = QTableWidgetItem(text)
                it.setTextAlignment(Qt.AlignCenter)
                if col != self.COL_SERIAL:  # Serial es editable
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._ocr_table.setItem(row, col, it)

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
        if self.grid.count == 0:
            self._empty.setVisible(True)
            self._splitter.setVisible(False)
            self._current_idx = -1
            self.viewer.set_image(None)
            self._refresh_info_tab()
        self._update_scanner_tab_visible()

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
            self._apply_ocr_row(row, serial, conf)
            self._refresh_ocr_summary()
        if index == self._current_idx:
            self._refresh_info_tab()

    def _apply_ocr_row(self, row: int, serial: str, conf: float):
        """Escribe serial/confianza/estado en una fila de la tabla OCR de forma
        segura ante celdas None y preservando el estado de bloqueo de señales
        (no lo desbloquea si el llamador —p.ej. rebuild— lo tenía bloqueado)."""
        self._ensure_ocr_cells(row)
        prev_blocked = self._ocr_table.signalsBlocked()
        self._ocr_table.blockSignals(True)
        s_item = self._ocr_table.item(row, self.COL_SERIAL)
        c_item = self._ocr_table.item(row, self.COL_CONF)
        e_item = self._ocr_table.item(row, self.COL_STATUS)
        s_item.setText(serial or "Sin serial")
        c_item.setText(f"{conf:.0%}" if conf > 0 else "—")
        e_item.setFont(self._status_font)
        if serial:
            c = SUCCESS if conf >= 0.7 else WARNING
            e_item.setText("OK" if conf >= 0.7 else "Baja confianza")
            e_item.setForeground(QColor(c))
            s_item.setForeground(QColor(c))
        else:
            e_item.setText("Sin serial")
            e_item.setForeground(QColor(DANGER))
            s_item.setForeground(QColor(DANGER))
        self._ocr_table.blockSignals(prev_blocked)

    def set_bookmark(self, index: int, display: str):
        # El marcador ya no se muestra en la tabla OCR; se refleja en la
        # miniatura y en la pestaña Info.
        self.grid.set_bookmark(index, display)
        if index == self._current_idx:
            self._refresh_info_tab()

    def set_comment(self, index: int, display: str):
        # El comentario ya no se muestra en la tabla OCR; se refleja en la
        # pestaña Info (el dato vive en PageData).
        if index == self._current_idx:
            self._refresh_info_tab()

    def rebuild(self, pages_data: list, progress_callback=None):
        # Recordar la página vista para restaurarla al final: reconstruir NO
        # debe saltar siempre a la página 1.
        prev_idx = self._current_idx
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
            if progress_callback:
                progress_callback(i + 1, total)
        self._ocr_table.blockSignals(False)
        self._refresh_ocr_summary()
        if pages_data:
            self._empty.setVisible(False)
            self._splitter.setVisible(True)
            # Restaurar la selección previa (acotada), no la página 0. Si no
            # había selección previa, mostrar la primera por defecto.
            restore = prev_idx if prev_idx >= 0 else 0
            restore = max(0, min(restore, len(pages_data) - 1))
            self._current_idx = restore
            self.grid.select(restore)
            self.viewer.set_image(pages_data[restore].display_image)
        else:
            self._empty.setVisible(True)
            self._splitter.setVisible(False)
            self._current_idx = -1
            self.viewer.set_image(None)
        self.grid.blockSignals(False)
        self._refresh_info_tab()
        self._update_scanner_tab_visible()

    def set_ocr_result(self, index: int, serial: str, conf: float):
        row = self._ocr_row_for(index)
        if row < 0:
            return
        self._apply_ocr_row(row, serial, conf)
        self._refresh_ocr_summary()
        if index == self._current_idx:
            self._refresh_info_tab()

    def ocr_started(self):
        self._ocr_prog.setRange(0, 0)
        self._ocr_prog.setVisible(True)

    def ocr_finished(self):
        self._ocr_prog.setVisible(False)

    def set_parallel_workers(self, n: int):
        self._ocr_cores_spin.blockSignals(True)
        self._ocr_cores_spin.setValue(n)
        self._ocr_cores_spin.blockSignals(False)

    def clear(self):
        self.grid.clear_all()
        self._ocr_table.setRowCount(0)
        self._current_idx = -1
        self.viewer.set_image(None)
        self._empty.setVisible(True)
        self._splitter.setVisible(False)
        self._rot_slider.setValue(0)
        self._export_folder.clear()
        self._ant_chk_range.setChecked(False)
        self._ant_desde.setValue(1)
        self._ant_hasta.setValue(100)
        self._refresh_ocr_summary()
        self._refresh_info_tab()
        self._update_scanner_tab_visible()

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
        self._btn_exp_ant_orig.setEnabled(False)
        self._btn_exp_ant_orig.setText("Generando…")

    def export_original_finished(self, path: str):
        self._btn_exp_ant_orig.setEnabled(True)
        self._btn_exp_ant_orig.setText("Exportar PDF original")

    def export_original_error(self, msg: str):
        self._btn_exp_ant_orig.setEnabled(True)
        self._btn_exp_ant_orig.setText("Exportar PDF original")

    def merge_started(self):
        pass

    def merge_finished(self, path: str):
        pass

    def merge_error(self, msg: str):
        pass

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

    def _set_export_buttons(self, enabled: bool, text: str | None = None):
        btns = [
            self._btn_exp_civil, self._btn_exp_civil_bm,
            self._btn_exp_ant_single, self._btn_exp_ant_split,
            self._btn_exp_ant_orig,
        ]
        for b in btns:
            b.setEnabled(enabled)
        if text and not enabled:
            self._btn_exp_civil.setText(text)
