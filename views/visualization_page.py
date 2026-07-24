"""Página de Visualización — empareja Registros con Antecedentes por serial, combina PDFs y muestra estadísticas."""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QSplitter, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QComboBox, QLineEdit, QGroupBox, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QDialog, QProgressBar, QMenu,
)

from models.config_model import ConfigModel
from models.visualization_model import Category, MatchPair, ScanResult, CategoryBatch
from controllers.visualization_controller import VisualizationController
from views.theme import (
    SURFACE, SURFACE2, BORDER, TEXT, TEXT_DIM, TEXT_SEC, SUCCESS, WARNING, DANGER,
    pill_qss, COMPACT_LIST_QSS,
)

CATEGORY_LABELS: dict[Category, str] = {
    Category.DEFUNCION: "Defunción",
    Category.NACIMIENTO: "Nacimiento",
    Category.MATRIMONIO: "Matrimonio",
}
STATUS_LABELS = {
    "matched": ("Emparejado", SUCCESS),
    "orphan_registro": ("Sin antecedente", WARNING),
    "orphan_antecedente": ("Sin registro", WARNING),
    "cancelado": ("Anulado", DANGER),
}
STATUS_SORT_ORDER = {
    "orphan_registro": 0,
    "orphan_antecedente": 1,
    "cancelado": 2,
    "matched": 3,
}
SORT_OPTIONS = [("Serial", "serial"), ("Estado", "estado")]

_INSERT_BATCH_SIZE = 150


def _serial_sort_key(serial: str):
    return (0, int(serial)) if serial.isdigit() else (1, serial)


class VisualizationPage(QWidget):
    def __init__(self, config: ConfigModel, controller: VisualizationController, parent=None):
        super().__init__(parent)
        self._cfg = config
        self._ctl = controller
        self._result: ScanResult | None = None
        self._last_root: str = ""
        self._sort_key: str = "serial"
        self._status_font = QFont()
        self._status_font.setBold(True)

        # Cola de inserción diferida para no bloquear la UI con árboles grandes.
        self._category_items: dict[Category, QTreeWidgetItem] = {}
        self._category_pending: dict[Category, int] = {}
        self._insert_queue: list[tuple[Category, MatchPair]] = []
        self._insert_timer = QTimer(self)
        # Un intervalo de 0 hace que Qt reprograme el timer apenas se vacia la
        # cola de eventos, lo que puede acaparar el bucle de eventos y dejar sin
        # turno a otros timers/entrada de usuario. Un intervalo pequeño y > 0
        # garantiza que la UI siga respondiendo entre lotes.
        self._insert_timer.setInterval(10)
        self._insert_timer.timeout.connect(self._drain_insert_queue)

        self._build()

        self._ctl.scan_category_ready.connect(self._on_category_ready)
        self._ctl.scan_done.connect(self._on_scan_done)
        self._ctl.scan_error.connect(self._on_scan_error)
        self._ctl.combine_progress.connect(self._on_combine_progress)
        self._ctl.combine_done.connect(self._on_combine_done)
        self._ctl.combine_error.connect(self._on_combine_error)

    # ---------------------------------------------------------------- build
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._stack = QStackedWidget()
        self._empty_widget = self._build_empty_state()
        self._content_widget = self._build_content()
        self._stack.addWidget(self._empty_widget)
        self._stack.addWidget(self._content_widget)
        root.addWidget(self._stack, 1)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(56)
        header.setObjectName("vizHeader")
        header.setStyleSheet(f"#vizHeader {{ background:{SURFACE}; border:none; }}")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(10)

        title = QLabel("Visualización")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")
        hl.addWidget(title)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        hl.addWidget(self._path_label)

        self._change_btn = QPushButton("Cambiar")
        self._change_btn.setFixedHeight(30)
        self._change_btn.clicked.connect(self._select_folder)
        self._change_btn.setVisible(False)
        hl.addWidget(self._change_btn)

        hl.addStretch()

        self._filter_combo = QComboBox()
        self._filter_combo.addItem("Todas", None)
        for cat, label in CATEGORY_LABELS.items():
            self._filter_combo.addItem(label, cat)
        self._filter_combo.setFixedWidth(140)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        hl.addWidget(self._filter_combo)

        self._refresh_btn = QPushButton("Actualizar")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.clicked.connect(self._ctl.start_scan)
        hl.addWidget(self._refresh_btn)

        self._bulk_btn = QPushButton("Combinar todos los emparejados")
        self._bulk_btn.setProperty("primary", True)
        self._bulk_btn.setFixedHeight(30)
        self._bulk_btn.setEnabled(False)
        self._bulk_btn.clicked.connect(self._on_bulk_combine_clicked)
        hl.addWidget(self._bulk_btn)

        return header

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)

        icon = QLabel("📁")
        icon.setStyleSheet("font-size:40pt; border:none;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        msg = QLabel(
            "Configura la carpeta raíz de Registros Civiles para comenzar.\n"
            "Se espera la estructura: Categoría / Antecedentes|Registros / Caja N / Carpeta N / serial.pdf"
        )
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(f"color:{TEXT_SEC}; border:none;")
        lay.addWidget(msg)

        btn = QPushButton("Seleccionar carpeta")
        btn.setProperty("primary", True)
        btn.setFixedHeight(36)
        btn.setFixedWidth(220)
        btn.clicked.connect(self._select_folder)
        lay.addWidget(btn, alignment=Qt.AlignCenter)

        return w

    def _build_content(self) -> QWidget:
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 16, 8, 16)
        lv.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar por serial…")
        self._search.textChanged.connect(self._apply_search_filter)
        search_row.addWidget(self._search, 1)

        self._sort_combo = QComboBox()
        for label, key in SORT_OPTIONS:
            self._sort_combo.addItem(label, key)
        self._sort_combo.setFixedWidth(130)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        search_row.addWidget(self._sort_combo)
        lv.addLayout(search_row)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Serial", "Estado", "Caja/Carpeta (Registro)", "Caja/Carpeta (Antecedente)"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        lv.addWidget(self._tree, 1)

        splitter.addWidget(left)

        right = QScrollArea()
        right.setWidgetResizable(True)
        right.setStyleSheet("border:none;")
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(8, 16, 16, 16)
        pv.setSpacing(16)

        self._summary_group, self._summary_labels = self._make_summary_group()
        pv.addWidget(self._summary_group)

        self._by_category_group, self._by_category_layout = self._make_by_category_group()
        pv.addWidget(self._by_category_group)

        self._orphan_registro_group, self._orphan_registro_list = self._make_list_group("Huérfanos — Registros sin antecedente")
        self._orphan_registro_list.itemDoubleClicked.connect(self._on_orphan_registro_double_clicked)
        pv.addWidget(self._orphan_registro_group)

        self._orphan_antecedente_group, self._orphan_antecedente_list = self._make_list_group("Huérfanos — Antecedentes sin registro")
        self._orphan_antecedente_list.itemDoubleClicked.connect(self._on_orphan_antecedente_double_clicked)
        pv.addWidget(self._orphan_antecedente_group)

        self._duplicates_group, self._duplicates_list = self._make_list_group("Duplicados")
        self._duplicates_list.itemDoubleClicked.connect(self._on_duplicate_double_clicked)
        pv.addWidget(self._duplicates_group)

        pv.addStretch()
        right.setWidget(panel)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _make_summary_group(self) -> tuple[QGroupBox, dict[str, QLabel]]:
        box = QGroupBox("Resumen")
        grid = QGridLayout(box)
        grid.setSpacing(8)
        labels = {}
        # (clave, etiqueta, color) — el color da a cada cifra su propio peso semántico
        # en vez de una lista uniforme de números idénticos.
        rows = [
            ("total_registros", "Registros", TEXT_SEC),
            ("total_antecedentes", "Antecedentes", TEXT_SEC),
            ("matched", "Emparejados", SUCCESS),
            ("orphan_registro", "Sin antecedente", WARNING),
            ("orphan_antecedente", "Sin registro", WARNING),
            ("cancelado", "Anulados", DANGER),
            ("duplicates", "Series duplicados", WARNING),
        ]
        for i, (key, label, color) in enumerate(rows):
            tile = QFrame()
            tile.setStyleSheet(f"""
                QFrame {{
                    background-color: {SURFACE2};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                }}
            """)
            tv = QVBoxLayout(tile)
            tv.setContentsMargins(10, 8, 10, 8)
            tv.setSpacing(1)
            val = QLabel("0")
            val.setStyleSheet(f"font-size:17pt; font-weight:700; color:{color}; border:none;")
            tv.addWidget(val)
            cap = QLabel(label)
            cap.setStyleSheet(f"font-size:8pt; color:{TEXT_DIM}; border:none;")
            tv.addWidget(cap)
            labels[key] = val
            grid.addWidget(tile, i // 2, i % 2)
        return box, labels

    def _make_by_category_group(self) -> tuple[QGroupBox, QVBoxLayout]:
        box = QGroupBox("Por categoría")
        lay = QVBoxLayout(box)
        lay.setSpacing(8)
        return box, lay

    def _make_list_group(self, title: str) -> tuple[QGroupBox, QListWidget]:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lst = QListWidget()
        lst.setFixedHeight(140)
        lst.setStyleSheet(COMPACT_LIST_QSS)
        lay.addWidget(lst)
        return box, lst

    # ------------------------------------------------------------- lifecycle
    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_state()

    def on_settings_saved(self):
        self._refresh_state()

    def _refresh_state(self):
        root = self._ctl.root_folder()
        valid = bool(root) and Path(root).exists()
        if not valid:
            self._stack.setCurrentWidget(self._empty_widget)
            self._change_btn.setVisible(False)
            self._path_label.setText("")
            self._last_root = root
            return

        self._stack.setCurrentWidget(self._content_widget)
        self._change_btn.setVisible(True)
        self._path_label.setText(root)
        if root != self._last_root:
            self._last_root = root
            self._reset_view()
            cached = self._ctl.load_cached_result()
            if cached is not None:
                self._result = cached
                self._populate_tree()
                self._populate_stats()
            self._ctl.start_scan()

    def _reset_view(self):
        self._result = None
        self._tree.clear()
        self._category_items.clear()
        self._category_pending.clear()
        self._insert_queue.clear()
        if self._insert_timer.isActive():
            self._insert_timer.stop()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta raíz de Registros Civiles")
        if not folder:
            return
        self._ctl.set_root_folder(folder)
        self._refresh_state()

    # ----------------------------------------------------------------- scan
    def _on_category_ready(self, batch: CategoryBatch):
        if self._result is None:
            self._result = ScanResult(root=Path(self._ctl.root_folder() or "."))
        if batch.category not in self._result.scanned_categories:
            self._result.scanned_categories.append(batch.category)
        self._result.pairs[batch.category] = batch.pairs
        self._result.duplicates = (
            [d for d in self._result.duplicates if d.category != batch.category] + batch.duplicates
        )
        self._populate_stats()

        cat_filter = self._current_category_filter()
        if cat_filter is None or cat_filter == batch.category:
            self._enqueue_pairs(batch.category, batch.pairs)

    def _on_scan_done(self, result: ScanResult):
        self._result = result
        self._populate_stats()

    def _on_scan_error(self, msg: str):
        QMessageBox.warning(self, "Error al escanear", msg)

    def _current_category_filter(self) -> Category | None:
        return self._filter_combo.currentData()

    def _on_filter_changed(self, _index: int):
        self._populate_tree()
        self._populate_stats()

    def _pairs_in_scope(self) -> list[MatchPair]:
        if not self._result:
            return []
        cat = self._current_category_filter()
        if cat is None:
            return self._result.pairs_flat()
        return self._result.pairs.get(cat, [])

    # ------------------------------------------------------- lazy tree fill
    def _populate_tree(self):
        """Reconstruye el árbol completo (cambio de filtro / precarga de caché) de forma diferida."""
        self._tree.clear()
        self._category_items.clear()
        self._category_pending.clear()
        self._insert_queue.clear()
        if self._insert_timer.isActive():
            self._insert_timer.stop()
        if not self._result:
            return

        cat_filter = self._current_category_filter()
        categories = [cat_filter] if cat_filter else list(self._result.pairs.keys())
        for cat in categories:
            self._enqueue_pairs(cat, self._result.pairs.get(cat, []))

    def _enqueue_pairs(self, category: Category, pairs: list[MatchPair]):
        item = self._category_items.get(category)
        if item is None:
            item = QTreeWidgetItem(["", "", "", ""])
            self._tree.addTopLevelItem(item)
            item.setExpanded(True)
            self._category_items[category] = item
        else:
            item.takeChildren()

        # Purga entradas de esta categoria que quedaron sin drenar de un enqueue
        # anterior (p.ej. precarga de caché seguida de un rescan en vivo) para
        # no insertar filas duplicadas/obsoletas.
        if self._insert_queue:
            self._insert_queue = [(c, p) for c, p in self._insert_queue if c != category]

        self._category_pending[category] = len(pairs)
        self._update_category_header(category)

        if pairs:
            self._insert_queue.extend((category, p) for p in pairs)
            if not self._insert_timer.isActive():
                self._insert_timer.start()

    def _drain_insert_queue(self):
        batch = self._insert_queue[:_INSERT_BATCH_SIZE]
        del self._insert_queue[:_INSERT_BATCH_SIZE]
        for category, pair in batch:
            self._insert_pair_row(category, pair)
        if not self._insert_queue:
            self._insert_timer.stop()
            self._apply_search_filter(self._search.text())

    def _insert_pair_row(self, category: Category, pair: MatchPair):
        item = self._category_items.get(category)
        if item is None:
            return
        label, color = STATUS_LABELS[pair.status]
        reg = f"{pair.registro.box} / {pair.registro.folder}" if pair.registro else "—"
        ant = f"{pair.antecedente.box} / {pair.antecedente.folder}" if pair.antecedente else "—"
        child = QTreeWidgetItem([pair.serial, label, reg, ant])
        child.setForeground(1, self._color(color))
        child.setFont(1, self._status_font)
        child.setData(0, Qt.ItemDataRole.UserRole, pair)
        item.addChild(child)

        pending = self._category_pending.get(category, 0) - 1
        self._category_pending[category] = pending
        if pending <= 0:
            self._update_category_header(category)

    def _update_category_header(self, category: Category):
        item = self._category_items.get(category)
        if item is None:
            return
        if self._category_pending.get(category, 0) > 0:
            item.setText(0, f"{CATEGORY_LABELS[category]} (cargando…)")
            return
        pairs = self._result.pairs.get(category, []) if self._result else []
        matched_n = sum(1 for p in pairs if p.is_matched)
        orphan_n = len(pairs) - matched_n
        item.setText(0, f"{CATEGORY_LABELS[category]} ({matched_n} emparejados, {orphan_n} huérfanos)")
        self._sort_category_children(category)

    def _sort_key_fn(self, pair: MatchPair):
        if self._sort_key == "estado":
            return (STATUS_SORT_ORDER[pair.status], _serial_sort_key(pair.serial))
        return _serial_sort_key(pair.serial)

    def _sort_category_children(self, category: Category):
        item = self._category_items.get(category)
        if item is None or item.childCount() == 0:
            return
        scrollbar = self._tree.verticalScrollBar()
        scroll_pos = scrollbar.value()
        children = item.takeChildren()
        children.sort(key=lambda c: self._sort_key_fn(c.data(0, Qt.ItemDataRole.UserRole)))
        item.addChildren(children)
        scrollbar.setValue(scroll_pos)

    def _on_sort_changed(self, _index: int):
        self._sort_key = self._sort_combo.currentData()
        for category in self._category_items:
            self._sort_category_children(category)

    def _color(self, hex_color: str):
        from PySide6.QtGui import QColor
        return QColor(hex_color)

    def _apply_search_filter(self, text: str):
        text = text.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            cat_item = self._tree.topLevelItem(i)
            visible_children = 0
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                match = (not text) or (text in child.text(0).lower())
                child.setHidden(not match)
                if match:
                    visible_children += 1
            cat_item.setHidden(visible_children == 0 and cat_item.childCount() > 0)

    def _populate_stats(self):
        if not self._result:
            return
        cat = self._current_category_filter()
        counts = self._result.counts(cat)
        dup_in_scope = [d for d in self._result.duplicates if cat is None or d.category == cat]

        self._summary_labels["total_registros"].setText(str(counts["total_registros"]))
        self._summary_labels["total_antecedentes"].setText(str(counts["total_antecedentes"]))
        self._summary_labels["matched"].setText(str(counts["matched"]))
        self._summary_labels["orphan_registro"].setText(str(counts["orphan_registro"]))
        self._summary_labels["orphan_antecedente"].setText(str(counts["orphan_antecedente"]))
        self._summary_labels["cancelado"].setText(str(counts["cancelado"]))
        self._summary_labels["duplicates"].setText(str(len(dup_in_scope)))

        while self._by_category_layout.count():
            item = self._by_category_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._by_category_group.setVisible(cat is None)
        if cat is None:
            for c in self._result.pairs.keys():
                cc = self._result.counts(c)
                self._by_category_layout.addWidget(self._build_category_row(c, cc))

        pairs = self._pairs_in_scope()
        self._orphan_registro_list.clear()
        for p in pairs:
            if p.is_orphan_registro:
                item = QListWidgetItem(f"{CATEGORY_LABELS[p.category]} / {p.serial} — {p.registro.box}, {p.registro.folder}")
                item.setData(Qt.ItemDataRole.UserRole, p)
                self._orphan_registro_list.addItem(item)
        self._set_empty_placeholder(self._orphan_registro_list, "Sin huérfanos — todo emparejado")

        self._orphan_antecedente_list.clear()
        for p in pairs:
            if p.is_orphan_antecedente:
                item = QListWidgetItem(f"{CATEGORY_LABELS[p.category]} / {p.serial} — {p.antecedente.box}, {p.antecedente.folder}")
                item.setData(Qt.ItemDataRole.UserRole, p)
                self._orphan_antecedente_list.addItem(item)
        self._set_empty_placeholder(self._orphan_antecedente_list, "Sin huérfanos — todo emparejado")

        self._duplicates_list.clear()
        for d in dup_in_scope:
            item = QListWidgetItem(f"{CATEGORY_LABELS[d.category]} / {d.subcategory.value} / {d.serial} ({len(d.paths)} archivos)")
            item.setData(Qt.ItemDataRole.UserRole, d)
            self._duplicates_list.addItem(item)
        self._set_empty_placeholder(self._duplicates_list, "Sin series duplicados")

        self._bulk_btn.setEnabled(any(p.is_matched for p in pairs))

    def _build_category_row(self, category: Category, counts: dict[str, int]) -> QFrame:
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE2};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        rl = QVBoxLayout(row)
        rl.setContentsMargins(10, 8, 10, 8)
        rl.setSpacing(6)

        name = QLabel(CATEGORY_LABELS[category])
        name.setStyleSheet(f"font-size:9pt; font-weight:600; color:{TEXT}; border:none;")
        rl.addWidget(name)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        for key, label, color in (
            ("matched", "emparejados", SUCCESS),
            ("orphan_registro", "sin antecedente", WARNING),
            ("orphan_antecedente", "sin registro", WARNING),
            ("cancelado", "anulados", DANGER),
        ):
            chip = QLabel(f"{counts[key]} {label}")
            chip.setStyleSheet(pill_qss(color))
            chips.addWidget(chip)
        chips.addStretch()
        rl.addLayout(chips)
        return row

    def _set_empty_placeholder(self, list_widget: QListWidget, text: str):
        if list_widget.count() == 0:
            item = QListWidgetItem(text)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(self._color(TEXT_DIM))
            list_widget.addItem(item)

    # -------------------------------------------------------------- combine
    def _on_tree_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if item is None:
            return
        pair = item.data(0, Qt.ItemDataRole.UserRole)
        if pair is None:
            return

        menu = QMenu(self)
        open_reg_action = menu.addAction("Abrir Registro") if pair.registro else None
        open_ant_action = menu.addAction("Abrir Antecedente") if pair.antecedente else None

        combine_action = None
        cancel_action = None
        if pair.is_matched:
            menu.addSeparator()
            combine_action = menu.addAction("Combinar")
        elif pair.status in ("orphan_registro", "cancelado"):
            menu.addSeparator()
            cancel_action = menu.addAction("Quitar anulación" if pair.cancelado else "Marcar como anulado")

        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == open_reg_action:
            self._open_path(pair.registro.path)
        elif chosen == open_ant_action:
            self._open_path(pair.antecedente.path)
        elif chosen == combine_action:
            self._on_combine_clicked(pair)
        elif chosen == cancel_action:
            self._on_toggle_cancelled(pair, item)

    def _open_path(self, path: Path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_orphan_registro_double_clicked(self, item: QListWidgetItem):
        pair = item.data(Qt.ItemDataRole.UserRole)
        if pair and pair.registro:
            self._open_path(pair.registro.path)

    def _on_orphan_antecedente_double_clicked(self, item: QListWidgetItem):
        pair = item.data(Qt.ItemDataRole.UserRole)
        if pair and pair.antecedente:
            self._open_path(pair.antecedente.path)

    def _on_duplicate_double_clicked(self, item: QListWidgetItem):
        dup = item.data(Qt.ItemDataRole.UserRole)
        if dup:
            for path in dup.paths:
                self._open_path(path)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        pair = item.data(0, Qt.ItemDataRole.UserRole)
        if pair is None:
            return
        if pair.registro:
            self._open_path(pair.registro.path)
        elif pair.antecedente:
            self._open_path(pair.antecedente.path)

    def _on_toggle_cancelled(self, pair: MatchPair, item: QTreeWidgetItem):
        self._ctl.set_cancelled(pair, not pair.cancelado)
        label, color = STATUS_LABELS[pair.status]
        item.setText(1, label)
        item.setForeground(1, self._color(color))
        self._update_category_header(pair.category)
        self._populate_stats()

    def _on_combine_clicked(self, pair: MatchPair):
        default_path = str(Path(pair.registro.path).parent / f"{pair.serial}.pdf")
        out_path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF combinado", default_path, "PDF (*.pdf)")
        if not out_path:
            return
        try:
            self._ctl.combine_single(pair, Path(out_path))
            QMessageBox.information(self, "Combinado", f"PDF combinado generado:\n{out_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo combinar:\n{e}")

    def _on_bulk_combine_clicked(self):
        pairs = [p for p in self._pairs_in_scope() if p.is_matched]
        if not pairs:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Carpeta de destino para PDFs combinados")
        if not out_dir:
            return
        prefix = self._current_category_filter() is None
        self._bulk_btn.setEnabled(False)
        self._progress_dialog = self._make_progress_dialog(len(pairs))
        self._progress_dialog.show()
        self._ctl.start_bulk_combine(pairs, Path(out_dir), prefix_category=prefix)

    def _make_progress_dialog(self, total: int) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("Combinando PDFs")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setFixedSize(380, 130)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        lbl = QLabel(f"Combinando 0 de {total}…")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        bar = QProgressBar()
        bar.setRange(0, total)
        lay.addWidget(bar)
        dlg._label = lbl
        dlg._bar = bar
        return dlg

    def _on_combine_progress(self, current: int, total: int):
        dlg = getattr(self, "_progress_dialog", None)
        if dlg:
            dlg._bar.setValue(current)
            dlg._label.setText(f"Combinando {current} de {total}…")

    def _on_combine_done(self, ok: int, fail: int):
        dlg = getattr(self, "_progress_dialog", None)
        if dlg:
            dlg.close()
            self._progress_dialog = None
        self._bulk_btn.setEnabled(True)
        QMessageBox.information(self, "Combinación masiva", f"{ok} combinados, {fail} con error.")

    def _on_combine_error(self, msg: str):
        dlg = getattr(self, "_progress_dialog", None)
        if dlg:
            dlg.close()
            self._progress_dialog = None
        self._bulk_btn.setEnabled(True)
        QMessageBox.warning(self, "Error", msg)
