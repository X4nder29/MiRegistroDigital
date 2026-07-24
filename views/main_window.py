"""Ventana principal — pantalla de inicio + barra superior + stacked pages."""
from __future__ import annotations
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QSizePolicy, QApplication,
    QFileDialog, QMessageBox, QProgressDialog,
    QDialog, QProgressBar,
)
from PySide6.QtCore import Qt, Slot, Signal, QSize, QObject, QTimer, QRunnable, QThreadPool
from PySide6.QtGui import QIcon, QKeySequence

from models.scan_model import ScanModel
from models.config_model import ConfigModel
from models.job_model import Job, JobStatus
from models.project_model import (
    save as save_project,
    load as load_project,
    get_autosave_path,
    clear_autosave,
    load_autosave,
)
from controllers.scan_controller import ScanController
from controllers.ocr_controller import OCRController
from controllers.export_controller import ExportController
from controllers.visualization_controller import VisualizationController
from views.digitization_page import DigitizationPage
from views.pdf_page import EditorPage
from views.settings_page import SettingsPage
from views.visualization_page import VisualizationPage
from views.home_page import HomePage
from views.widgets import ProcessListDialog
from views.theme import BG, SURFACE, SURFACE2, SURFACE3, BORDER, TEXT, TEXT_DIM, TEXT_SEC, ACCENT2, INFO, WARNING

logger = logging.getLogger("docscan.main")


_NAV = [
    ("documentos",     "\U0001f4c4  Digitalizaci\u00f3n"),
    ("pdf",            "\U0001f4cb  Editor"),
    ("visualizacion",  "\U0001f441\ufe0f  Visualizaci\u00f3n"),
]

_HOME_SIZE = (960, 680)
_TOOL_MIN_SIZE = (1080, 700)
_UNBOUNDED = 16777215  # QWIDGETSIZE_MAX


class NavButton(QPushButton):
    """Pesta\u00f1a de la barra superior \u2014 borde inferior de acento cuando est\u00e1 activa."""
    def __init__(self, label: str, icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setText(label)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(16, 16))
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                color: {TEXT_DIM};
                text-align: center;
                padding: 0 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background: transparent; color: {TEXT_SEC}; }}
            QPushButton:checked {{
                border-bottom: 2px solid {ACCENT2};
                color: {TEXT};
            }}
        """)


class _AutosaveWorker(QRunnable):
    class _S(QObject):
        done  = Signal()
        error = Signal(str)

    def __init__(self, pages: list, path: Path, scan_settings: dict | None = None):
        super().__init__()
        self.pages = pages
        self.path  = path
        self.scan_settings = scan_settings
        self.s     = self._S()

    def run(self):
        try:
            from models.project_model import save as save_project
            save_project(self.path, self.pages, scan_settings=self.scan_settings)
            self.s.done.emit()
        except Exception as e:
            self.s.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._project_path: Path | None = None
        self._dirty = False
        self._update_title()
        self._apply_window_icon()
        logger.info("MainWindow inicializando")

        self._cfg    = ConfigModel()
        self._model  = ScanModel()

        self._scan   = ScanController(self._model, self._cfg, self)
        self._ocr    = OCRController(self._model, self._cfg, self)
        self._export = ExportController(self._model, self._cfg, self)
        self._viz    = VisualizationController(self._cfg, self)

        self._pending_pages: list = []
        self._process_dialog: ProcessListDialog | None = None
        self._import_progress_dlg: QProgressDialog | None = None
        self._custom_handlers: dict[str, tuple] = {}

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(5000)
        self._autosave_timer.timeout.connect(self._do_autosave)
        self._autosave_running = False
        self._autosave_pending = False
        self._autosave_worker: _AutosaveWorker | None = None

        self._build_ui()
        self._connect()

        # Unified permanent status bar
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setAttribute(Qt.WA_StyledBackground, True)
        self.statusBar().setContentsMargins(8, 8, 8, 8)
        self._sb_page = QLabel("")
        self._sb_page.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none; padding:0 4px;")
        self._sb_serial = QLabel("")
        self._sb_serial.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none; padding:0 4px;")
        self._sb_cut = QLabel("")
        self._sb_cut.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none; padding:0 4px;")
        self._viz_status = QLabel("")
        self._viz_status.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none; padding:0 4px;")
        self.statusBar().addPermanentWidget(self._viz_status)
        self._btn_processes = QPushButton("Procesos")
        self._btn_processes.setFocusPolicy(Qt.NoFocus)
        self._btn_processes.setStyleSheet(
            f"QPushButton {{ background: {SURFACE2}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 6px 12px; min-height: 0; font-size:8pt; color:{TEXT}; }}"
            f"QPushButton:hover {{ background: {SURFACE3}; }}")
        self._btn_processes.clicked.connect(self._open_process_dialog)
        self.statusBar().addPermanentWidget(self._btn_processes)
        self._update_status_bar()

        self.statusBar().showMessage("Listo")
        self._check_startup_autosave()
        # Poblar la lista de escáneres apenas arranca la app (no al construir la
        # ventana) para no demorar el primer paint con la enumeración TWAIN, y así
        # el combo del dispositivo ya tiene una selección antes de escanear —
        # evita que open_source(None) muestre el selector nativo de TWAIN.
        QTimer.singleShot(0, self._on_refresh_scanners)
        logger.info("MainWindow inicializada")

    def _apply_window_icon(self):
        """Fija el icono de la ventana (además del de la QApplication) para que
        el taskbar de Windows lo muestre. Prefiere el .ico (tamaños ráster
        reales); cae a svg/png. Resuelve rutas en desarrollo y PyInstaller."""
        import sys
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        for name in ("app_icon.ico", "app_icon.svg", "app_icon.png"):
            p = base / "resources" / name
            if p.exists():
                icon = QIcon(str(p))
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    return

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        mb = self._build_menu_bar()

        self._top_bar = self._build_top_bar(mb)
        root.addWidget(self._top_bar)

        self._stack = QStackedWidget()
        self._home_page  = HomePage()
        self._doc_page   = DigitizationPage(config=self._cfg)
        self._pdf_page   = EditorPage(config=self._cfg)
        self._viz_page   = VisualizationPage(self._cfg, self._viz)
        self._sett_page  = SettingsPage(self._cfg)

        for page in (self._home_page, self._doc_page, self._pdf_page, self._viz_page, self._sett_page):
            self._stack.addWidget(page)

        root.addWidget(self._stack, 1)

    def _build_menu_bar(self):
        from PySide6.QtWidgets import QMenu
        # Botón + QMenu en vez de QMenuBar: un QMenuBar se "acopla" solo como tira
        # superior propia dentro de un QMainWindow incluso sin setMenuBar(), lo que
        # impedía unificarlo en la misma fila que las pestañas/Ajustes.
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:{SURFACE}; border:1px solid {BORDER};
                     padding:4px; font-size:9pt; color:{TEXT}; }}
            QMenu::item {{ padding:4px 14px; }}
            QMenu::item:selected {{ background:{SURFACE2}; }}
        """)
        menu.addAction("Abrir proyecto\u2026", self._open_project, QKeySequence.Open)
        menu.addAction("Guardar", self._save_project, QKeySequence.Save)
        menu.addAction("Guardar como\u2026", self._save_project_as, QKeySequence("Ctrl+Shift+S"))
        menu.addAction("Cerrar proyecto", self._close_project, QKeySequence("Ctrl+W"))
        menu.addSeparator()
        self._close_tool_action = menu.addAction(
            "Cerrar herramienta", lambda: self._navigate("home"))
        menu.addSeparator()
        menu.addAction("Salir", self.close, QKeySequence("Ctrl+Q"))
        # Registrar las acciones en la ventana para que los atajos de teclado
        # funcionen aunque el menú desplegable no esté abierto/visible.
        self.addActions(menu.actions())

        btn = QPushButton("Archivo")
        btn.setFlat(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(30)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                color: {TEXT_SEC};
                font-size: 9pt;
                padding: 0 10px;
            }}
            QPushButton:hover {{ background: {SURFACE2}; color: {TEXT}; }}
            QPushButton::menu-indicator {{ image: none; }}
        """)
        btn.setMenu(menu)
        return btn

    def _open_process_dialog(self):
        if self._safe_process_dialog() is None:
            self._process_dialog = ProcessListDialog(self)
            self._process_dialog.finished.connect(self._on_process_dialog_closed)
            for j in self._export.all_jobs():
                self._process_dialog.add_job(j.id, j.label, j.total)
                if j.status == JobStatus.RUNNING:
                    self._process_dialog.update_job(j.id, j.current, j.total)
                elif j.status == JobStatus.DONE:
                    self._process_dialog.set_job_done(j.id, j.output_path)
                elif j.status == JobStatus.ERROR:
                    self._process_dialog.set_job_error(j.id, j.error_msg)
                elif j.status == JobStatus.CANCELLED:
                    self._process_dialog.set_job_cancelled(j.id)
            self._process_dialog.show()

    def _on_process_dialog_closed(self):
        self._process_dialog = None

    def _update_title(self):
        if getattr(self, "_current_nav_key", None) == "home":
            self.setWindowTitle("MiRegistroDigital")
            return
        name = self._project_path.name if self._project_path else "Sin t\u00edtulo"
        suffix = " *" if self._dirty else ""
        self.setWindowTitle(f"MiRegistroDigital \u2014 {name}{suffix}")

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_title()
        if self._autosave_running:
            self._autosave_pending = True
        else:
            self._autosave_timer.start()

    def _do_autosave(self):
        if self._autosave_running:
            return
        if not self._dirty or not self._model.pages:
            return
        self._autosave_running = True
        self._autosave_pending = False
        autopath = get_autosave_path()
        autopath.parent.mkdir(parents=True, exist_ok=True)
        worker = _AutosaveWorker(self._model.pages.copy(), autopath,
                                 self._doc_page.get_scan_settings().to_dict())
        worker.s.done.connect(self._on_autosave_done)
        worker.s.error.connect(self._on_autosave_error)
        self._autosave_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_autosave_done(self):
        self._autosave_worker = None
        self._autosave_running = False
        if self._autosave_pending:
            self._autosave_timer.start()
        else:
            if not self._dirty:
                try:
                    clear_autosave()
                except OSError:
                    pass
            self._dirty = False
            self.statusBar().clearMessage()
            self._update_title()

    def _on_autosave_error(self, err: str):
        self._autosave_worker = None
        self._autosave_running = False
        logger.error("Error en autoguardado: %s", err)
        if self._autosave_pending:
            self._autosave_timer.start()

    def _confirm_save(self) -> bool:
        """Returns False if the operation was cancelled."""
        if not self._dirty:
            return True
        ret = QMessageBox.question(
            self, "Guardar cambios",
            "Hay cambios sin guardar. \u00bfDesea guardarlos?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if ret == QMessageBox.Save:
            self._save_project()
            return True
        elif ret == QMessageBox.Discard:
            return True
        return False

    def _save_project(self):
        if self._project_path:
            dlg = QDialog(self)
            dlg.setWindowTitle("Guardando proyecto")
            dlg.setWindowModality(Qt.WindowModal)
            dlg.setFixedSize(420, 170)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(16, 14, 16, 14)
            lay.setSpacing(12)
            lbl = QLabel("Guardando proyecto\u2026")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 0)
            lay.addWidget(bar)
            dlg.show()
            QApplication.processEvents()
            try:
                def _on_progress(c: int, t: int):
                    if bar.minimum() == bar.maximum():
                        bar.setRange(0, t)
                    bar.setValue(c)
                    lbl.setText(f"Comprimiendo página {c} de {t}\u2026")
                    QApplication.processEvents()
                save_project(self._project_path, self._model.pages,
                             scan_settings=self._doc_page.get_scan_settings().to_dict(),
                             progress_callback=_on_progress)
                self._dirty = False
                self._update_title()
                self.statusBar().showMessage(f"Proyecto guardado: {self._project_path.name}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo guardar:\n{e}")
            finally:
                dlg.close()
        else:
            self._save_project_as()

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar proyecto como", "", "MiRegistroDigital (*.miregistro)")
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".miregistro":
            p = p.with_suffix(".miregistro")
        dlg = QDialog(self)
        dlg.setWindowTitle("Guardando proyecto")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setFixedSize(420, 170)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        lbl = QLabel("Guardando proyecto\u2026")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        bar = QProgressBar()
        bar.setRange(0, 0)
        lay.addWidget(bar)
        dlg.show()
        QApplication.processEvents()
        try:
            def _on_progress(c: int, t: int):
                if bar.minimum() == bar.maximum():
                    bar.setRange(0, t)
                bar.setValue(c)
                lbl.setText(f"Comprimiendo página {c} de {t}\u2026")
                QApplication.processEvents()
            save_project(p, self._model.pages,
                         scan_settings=self._doc_page.get_scan_settings().to_dict(),
                         progress_callback=_on_progress)
            self._project_path = p
            self._dirty = False
            self._update_title()
            self.statusBar().showMessage(f"Proyecto guardado: {p.name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar:\n{e}")
        finally:
            dlg.close()

    def _open_project(self):
        if not self._confirm_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", "MiRegistroDigital (*.miregistro)")
        if not path:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Abriendo proyecto")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setFixedSize(420, 170)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        lbl = QLabel("Cargando proyecto\u2026")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        bar = QProgressBar()
        bar.setRange(0, 0)
        lay.addWidget(bar)
        dlg.show()
        QApplication.processEvents()

        try:
            def _on_progress(current: int, total: int):
                if bar.minimum() == bar.maximum():
                    bar.setRange(0, total)
                bar.setValue(current)
                lbl.setText(f"Decodificando página {current} de {total}\u2026")
                QApplication.processEvents()

            result = load_project(Path(path), progress_callback=_on_progress)
            pages = result.pages

            self._model.load_pages(pages)
            self._project_path = Path(path)
            self._dirty = False
            self._update_title()
            clear_autosave()

            lbl.setText("Reconstruyendo interfaz\u2026")
            QApplication.processEvents()

            def _on_rebuild(current: int, total: int):
                if bar.minimum() == bar.maximum():
                    bar.setRange(0, total)
                bar.setValue(current)
                lbl.setText(f"Reconstruyendo interfaz\u2026 {current}/{total}")
                QApplication.processEvents()

            self._doc_page.rebuild(pages, progress_callback=_on_rebuild)
            if result.scan_settings:
                from models.scan_settings import ScanSettings
                self._doc_page.set_scan_settings(ScanSettings.from_dict(result.scan_settings))
        except Exception as e:
            dlg.close()
            QMessageBox.warning(self, "Error", f"No se pudo abrir el proyecto:\n{e}")
            return
        finally:
            dlg.close()

        self.statusBar().showMessage(f"Proyecto cargado: {self._project_path.name}")

    def _close_project(self):
        if not self._confirm_save():
            return
        self._cleanup_project()

    def _cleanup_project(self):
        self._autosave_timer.stop()

        self._scan.cancel_import()
        self._ocr.cancel_all()
        for jid in list(self._export._workers):
            self._export.cancel_export(jid)
        self._export._jobs.clear()
        self._export._workers.clear()
        QThreadPool.globalInstance().clear()

        self._pending_pages.clear()
        self._custom_handlers.clear()
        self._autosave_worker = None

        if self._process_dialog:
            try:
                self._process_dialog.close()
            except RuntimeError:
                pass
            self._process_dialog = None

        if self._import_progress_dlg:
            try:
                self._import_progress_dlg.close()
            except RuntimeError:
                pass
            self._import_progress_dlg = None

        self._model.clear()
        self._project_path = None
        self._dirty = False
        self._update_title()
        try:
            clear_autosave()
        except OSError:
            pass
        self._doc_page.clear()
        self.statusBar().showMessage("Proyecto cerrado")

    def _check_startup_autosave(self):
        ap = get_autosave_path()
        if ap.exists():
            ret = QMessageBox.question(
                self, "Recuperar autoguardado",
                "Se encontr\u00f3 un archivo de recuperaci\u00f3n. \u00bfDesea restaurarlo?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret == QMessageBox.Yes:
                try:
                    result = load_autosave()
                    if result and result.pages:
                        self._model.load_pages(result.pages)
                        self._dirty = True
                        self._update_title()
                        self._refresh_all_views()
                        if result.scan_settings:
                            from models.scan_settings import ScanSettings
                            self._doc_page.set_scan_settings(
                                ScanSettings.from_dict(result.scan_settings))
                        self.statusBar().showMessage(
                            "Proyecto recuperado del autoguardado")
                        return
                except Exception as e:
                    logger.exception("Error cargando autoguardado: %s", e)
            clear_autosave()

    def _refresh_all_views(self):
        pages = self._model.pages
        self._doc_page.rebuild(pages)

    def _build_top_bar(self, menu_bar) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setObjectName("topBar")
        bar.setStyleSheet(
            f"#topBar {{ background:{BG}; border-bottom: 1px solid {BORDER}; }}")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(4)

        h.addWidget(menu_bar)

        self._nav_btns: dict[str, NavButton] = {}
        for key, label in _NAV:
            btn = NavButton(label)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self._nav_btns[key] = btn
            h.addWidget(btn)

        h.addStretch()

        settings_btn = QPushButton("⚙️  Ajustes")
        settings_btn.setFixedHeight(30)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE2};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 9pt;
                color: {TEXT_SEC};
            }}
            QPushButton:hover {{ color: {TEXT}; border-color: {ACCENT2}; }}
            QPushButton:checked {{ color: {TEXT}; border-color: {ACCENT2}; }}
        """)
        settings_btn.setCheckable(True)
        settings_btn.setFocusPolicy(Qt.NoFocus)
        settings_btn.clicked.connect(lambda: self._navigate("settings"))
        self._settings_btn = settings_btn
        h.addWidget(settings_btn)

        return bar

    def _navigate(self, key: str):
        idx = {"home": 0, "documentos": 1, "pdf": 2, "visualizacion": 3, "settings": 4}
        for k, btn in self._nav_btns.items():
            btn.setChecked(k == key)
        self._settings_btn.setChecked(key == "settings")
        self._stack.setCurrentIndex(idx.get(key, 0))
        self._top_bar.setVisible(key != "home")
        self.statusBar().setVisible(key != "home")
        self._close_tool_action.setEnabled(key != "home")

        came_from_home = getattr(self, "_current_nav_key", None) == "home"
        if key == "home":
            # Pantalla principal: tamaño fijo, sin maximizar ni redimensionar.
            if self.isMaximized():
                self.showNormal()
            # Alternar el flag explícitamente (en vez de solo min==max) fuerza a Qt a
            # recomputar el estilo nativo de Windows y quitar el botón de maximizar.
            self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
            self.setFixedSize(*_HOME_SIZE)
            self._center_on_screen()
            self.show()
        else:
            # Pantallas de herramientas: redimensionables libremente.
            self.setMinimumSize(*_TOOL_MIN_SIZE)
            self.setMaximumSize(_UNBOUNDED, _UNBOUNDED)
            if came_from_home:
                # Igual que arriba: min==max en Home deja el botón de maximizar
                # deshabilitado a nivel nativo; solo cambiar minimumSize/maximumSize
                # después no se lo devuelve de forma fiable — hay que re-activar el
                # flag explícitamente y volver a mostrar la ventana para que Windows
                # recalcule el marco (borde de redimensión + botón maximizar).
                self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
                self.show()
                self.showMaximized()
        self._current_nav_key = key
        self._update_title()

        self._cfg.set("ui", "last_page", key)

    def _center_on_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w, h = _HOME_SIZE
        self.move(geo.x() + (geo.width() - w) // 2, geo.y() + (geo.height() - h) // 2)

    def _connect(self):
        logger.info("Conectando se\u00f1ales\u2026")
        dp = self._doc_page

        # Import
        dp.import_images_requested.connect(self._on_import)
        dp.import_pdf_requested.connect(self._on_import)
        dp.open_project_requested.connect(self._open_project)

        # Scan (TWAIN)
        dp.scan_sources_refresh_requested.connect(self._on_refresh_scanners)
        dp.scan_requested.connect(self._on_scan)
        dp.scan_cancel_requested.connect(self._scan.cancel_scan)

        # Correction
        dp.correction_requested.connect(self._scan.auto_correct)
        dp.rotation_changed.connect(self._scan.rotate_manual)
        dp.reset_correction.connect(self._scan.reset_correction)

        # Page management
        dp.cut_toggled.connect(self._on_cut_toggled)
        dp.page_deleted.connect(self._on_page_deleted)
        dp.page_reordered.connect(self._scan.reorder_page)

        # Bookmarks / Comments
        dp.bookmark_set.connect(self._scan.set_bookmark)
        dp.comment_set.connect(self._on_comment_set)
        dp.clear_cuts_requested.connect(self._on_clear_cuts)

        # OCR
        dp.ocr_all_requested.connect(self._on_ocr_all)
        dp.ocr_page_requested.connect(self._ocr.run_page)
        dp.ocr_cancel_requested.connect(self._on_ocr_cancel)
        dp.serial_corrected.connect(self._ocr.override)
        dp.ocr_area_saved.connect(self._on_area_saved)
        dp.parallel_workers_changed.connect(self._on_parallel_workers_changed)

        # Export
        dp.export_civil_requested.connect(self._on_civil_export)
        dp.export_bookmark_requested.connect(self._on_civil_export_bookmark)
        dp.export_original_pdf_requested.connect(self._on_export_original_pdf)
        dp.export_ant_single_pdf.connect(self._on_ant_export_single_pdf)
        dp.export_ant_split_bookmark.connect(self._on_ant_export_split_bookmark)
        dp.merge_requested.connect(self._on_merge_pdfs)

        dp.set_parallel_workers(self._cfg.get("ocr", "parallel_workers", 4))

        # Scan model signals
        self._scan.order_changed.connect(self._on_order_changed)
        self._scan.bookmark_updated.connect(self._on_bookmark_updated)
        self._scan.page_added.connect(self._on_page_queued)
        self._scan.import_done.connect(self._flush_pending_pages)
        self._scan.import_done.connect(lambda: self.statusBar().showMessage(
            f"Importaci\u00f3n completa \u2014 {self._model.count} p\u00e1gina(s)"))

        self._scan.error.connect(self._on_error)
        self._scan.correction_done.connect(self._on_correction_done)

        self._scan.scan_progress.connect(dp.set_scan_progress)
        self._scan.scan_done.connect(self._flush_pending_pages)
        self._scan.scan_done.connect(lambda: self.statusBar().showMessage(
            f"Escaneo completo — {self._model.count} página(s)"))
        self._scan.scan_error.connect(self._on_scan_error)

        # OCR signals
        self._ocr.ocr_result.connect(self._on_ocr_result)
        self._ocr.ocr_all_done.connect(dp.ocr_finished)
        self._ocr.ocr_error.connect(self._on_ocr_error_page)

        # Export signals
        self._export.job_created.connect(self._on_job_created)
        self._export.job_done.connect(self._on_job_done)
        self._export.job_error.connect(self._on_job_error)
        self._export.job_cancelled.connect(self._on_job_cancelled)
        self._export.job_created.connect(self._on_process_created)
        self._export.job_progress.connect(self._on_process_progress)
        self._export.job_done.connect(self._on_process_done)
        self._export.job_error.connect(self._on_process_error)
        self._export.job_cancelled.connect(self._on_process_cancelled)

        # Other pages
        self._sett_page.settings_saved.connect(
            lambda: self.statusBar().showMessage("Configuraci\u00f3n guardada", 3000))
        self._sett_page.settings_saved.connect(self._viz_page.on_settings_saved)
        self._viz.scan_started.connect(self._on_viz_scan_started)
        self._viz.scan_progress.connect(self._on_viz_scan_progress)
        self._viz.scan_finished.connect(self._on_viz_scan_finished)
        self._viz.scan_error.connect(
            lambda msg: self.statusBar().showMessage(f"Visualización: {msg}", 4000))
        self._pdf_page.pdf_generated.connect(
            lambda p: self.statusBar().showMessage(f"PDF organizado guardado: {Path(p).name}"))

        # Unified status bar signals
        self._doc_page.grid.page_selected.connect(lambda i: self._update_status_bar())
        self._scan.bookmark_updated.connect(lambda *a: self._update_status_bar())
        self._scan.correction_done.connect(lambda *a: self._update_status_bar())
        self._scan.import_done.connect(lambda: self._update_status_bar())
        self._scan.scan_done.connect(lambda: self._update_status_bar())
        self._scan.page_added.connect(lambda p: self._update_status_bar())
        self._scan.order_changed.connect(self._update_status_bar)
        self._ocr.ocr_result.connect(lambda *a: self._update_status_bar())
        self._doc_page.cut_toggled.connect(lambda i: self._update_status_bar())
        self._doc_page.page_deleted.connect(lambda i: self._update_status_bar())

        self._home_page.tool_selected.connect(self._navigate)

        self._navigate("home")

    def _update_status_bar(self):
        total = self._model.count
        if total == 0:
            self._sb_page.setText("")
            self._sb_serial.setText("")
            self._sb_cut.setText("")
            return
        idx = self._doc_page._current_idx
        self._sb_page.setText(f"Página {idx + 1} / {total}" if idx >= 0 else f"0 / {total}")
        page = self._model.get(idx) if idx >= 0 else None
        if page:
            self._sb_serial.setText(f"Serial: {page.serial or '—'}")
            self._sb_cut.setText("✂ Corte: ON" if page.is_cut_point else "")
            self._sb_cut.setStyleSheet(
                f"font-size:8pt; color:{WARNING if page.is_cut_point else TEXT_DIM}; border:none; padding:0 4px;")
        else:
            self._sb_serial.setText("")
            self._sb_cut.setText("")

    def _on_viz_scan_started(self):
        self._viz_status.setText("⏳ Escaneando Registros Civiles…")

    def _on_viz_scan_progress(self, count: int):
        self._viz_status.setText(f"⏳ Escaneando Registros Civiles… {count} registros")

    def _on_viz_scan_finished(self):
        self._viz_status.setText("")

    def _on_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}")

    @Slot(int, str)
    def _on_ocr_error_page(self, index: int, msg: str):
        logger.warning("OCR error p\u00e1gina %d: %s", index, msg)

    @Slot(list)
    def _on_import(self, paths: list[Path]):
        if self._import_progress_dlg is not None:
            logger.warning("Import ya en curso, ignorando nueva solicitud")
            return
        logger.info("Importando %d archivos", len(paths))
        self.statusBar().showMessage(f"Importando {len(paths)} archivo(s)\u2026")

        dlg = QDialog(self)
        dlg.setWindowTitle("Importando PDF")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setFixedSize(420, 170)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        lbl = QLabel("Importando PDF\u2026")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        bar = QProgressBar()
        bar.setRange(0, 0)
        lay.addWidget(bar)

        btn = QPushButton("Cancelar")
        btn.clicked.connect(self._scan.cancel_import)
        lay.addWidget(btn, alignment=Qt.AlignCenter)

        dlg.show()
        QApplication.processEvents()
        self._import_progress_dlg = dlg

        def _on_progress(c, t):
            if bar.minimum() == bar.maximum():
                bar.setRange(0, t)
            bar.setValue(c)
            lbl.setText(f"Importando p\u00e1gina {c} de {t}\u2026")
            QApplication.processEvents()

        self._scan.import_progress.connect(_on_progress)
        self._scan.import_done.connect(self._finish_import_progress)
        self._scan.error.connect(lambda msg: self._finish_import_progress())

        self._scan.import_files(paths)

    def _finish_import_progress(self):
        dlg = self._import_progress_dlg
        if dlg:
            self._import_progress_dlg = None
            try:
                dlg.close()
            except RuntimeError:
                pass

    def _on_refresh_scanners(self):
        names = self._scan.list_scanner_sources()
        self._doc_page.set_scanner_sources(names)
        if not names:
            self.statusBar().showMessage(
                "No se encontraron escáneres TWAIN" if self._scan.is_twain_available()
                else "pytwain no está disponible en este equipo")

    @Slot(object)
    def _on_scan(self, settings):
        self._doc_page.set_scanning(True)
        self.statusBar().showMessage("Escaneando…")
        QApplication.processEvents()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._scan.start_scan(settings, int(self.winId()))
        finally:
            QApplication.restoreOverrideCursor()

    @Slot(str)
    def _on_scan_error(self, msg: str):
        self._doc_page.set_scanning(False)
        self.statusBar().showMessage(f"Escáner: {msg}", 6000)
        QMessageBox.warning(self, "Escáner", msg)

    @Slot(object)
    def _on_page_queued(self, page):
        self._pending_pages.append(page)

    @Slot()
    def _flush_pending_pages(self):
        dp = self._doc_page
        dp.set_scanning(False)
        dp.grid.blockSignals(True)
        dp._ocr_table.blockSignals(True)
        for page in self._pending_pages:
            img = page.display_image
            dp.add_page(page.index, img)
        dp.grid.blockSignals(False)
        dp._ocr_table.blockSignals(False)
        self._pending_pages.clear()
        self._mark_dirty()

    @Slot(object)
    def _on_page_added(self, page):
        logger.debug("P\u00e1gina a\u00f1adida directa: index=%d", page.index)
        img = page.display_image
        self._doc_page.add_page(page.index, img)
        self.statusBar().showMessage(f"P\u00e1gina {page.index + 1} cargada")
        self._mark_dirty()

    @Slot(int)
    def _on_page_deleted(self, index: int):
        logger.info("P\u00e1gina eliminada: %d", index)
        self._model.remove(index)
        self._doc_page.remove_page(index)
        self._mark_dirty()

    @Slot(int)
    def _on_cut_toggled(self, index: int):
        is_cut = self._model.toggle_cut(index)
        self._doc_page.set_cut(index, is_cut)
        self._mark_dirty()

    @Slot()
    def _on_clear_cuts(self):
        self._model.set_cuts(set())
        for page in self._model.pages:
            self._doc_page.set_cut(page.index, False)

    @Slot()
    def _on_ocr_all(self):
        logger.info("OCR todas las p\u00e1ginas solicitado")
        self._doc_page.ocr_started()
        self._ocr.run_all()

    @Slot(int)
    def _on_parallel_workers_changed(self, n: int):
        logger.info("Parallel workers cambiado a %d", n)
        self._ocr.set_parallel_workers(n)
        self._cfg.set("ocr", "parallel_workers", n)
        self.statusBar().showMessage(f"OCR en paralelo: {n} trabajos")

    @Slot()
    def _on_ocr_cancel(self):
        logger.info("OCR cancelado por usuario")
        self._ocr.cancel_all()
        self._doc_page.ocr_finished()
        self.statusBar().showMessage("OCR cancelado")

    @Slot(int, str, float)
    def _on_ocr_result(self, index: int, serial: str, conf: float):
        logger.debug("Resultado OCR p\u00e1gina %d: serial=%s conf=%.2f", index, serial, conf)
        self._doc_page.set_ocr_result(index, serial, conf)
        self._doc_page.set_serial(index, serial, conf)
        self._mark_dirty()

    @Slot(int, float, float, float, float)
    def _on_area_saved(self, page_index: int, x1: float, y1: float, x2: float, y2: float):
        logger.info("\u00c1rea OCR guardada: (%.2f, %.2f, %.2f, %.2f)", x1, y1, x2, y2)
        area = (x1, y1, x2, y2)
        for page in self._model.pages:
            page.ocr_area = area
        self.statusBar().showMessage(
            f"\u00c1rea OCR global guardada \u2014 {self._model.count} p\u00e1gina(s)")

    @Slot(int, list)
    def _on_bookmark_updated(self, index: int, labels: list):
        first = labels[0][1] if labels else ""
        n = len(labels)
        display = f"{first} \U0001f4d1{n}" if n > 1 else first
        self._doc_page.set_bookmark(index, display)
        self._mark_dirty()

    @Slot()
    def _on_order_changed(self):
        pages = self._model.pages
        self._doc_page.rebuild(pages)
        self._mark_dirty()

    @Slot(str)
    def _on_civil_export(self, folder: str):
        logger.info("Exportaci\u00f3n civil solicitada -> %s", folder)
        self._doc_page.export_started()
        job_id = self._export.export_civil(folder, "Registros Civiles")
        if not job_id:
            self._doc_page.export_error("No hay p\u00e1ginas para exportar.")

    @Slot(str)
    def _on_civil_export_bookmark(self, folder: str):
        logger.info("Exportaci\u00f3n civil por marcador solicitada -> %s", folder)
        self._doc_page.export_bookmark_started()
        job_id = self._export.export_civil_bookmark(folder, "Registros por marcador")
        if not job_id:
            self._doc_page.export_bookmark_error("No hay p\u00e1ginas para exportar.")
        else:
            def done(jid: str, path: str):
                self._doc_page.export_bookmark_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                self._doc_page.export_bookmark_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(int, str)
    def _on_comment_set(self, index: int, text: str):
        self._model.set_comment(index, text)
        preview = text[:40] + "\u2026" if len(text) > 40 else text
        self._doc_page.set_comment(index, preview)
        self._mark_dirty()

    @Slot(str)
    def _on_export_original_pdf(self, folder: str):
        logger.info("Exportaci\u00f3n PDF original solicitada -> %s", folder)
        self._doc_page.export_original_started()
        job_id = self._export.export_original_pdf(folder, "PDF original")
        if not job_id:
            self._doc_page.export_original_error("No hay p\u00e1ginas para exportar.")
        else:
            def done(jid: str, path: str):
                self._doc_page.export_original_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                self._doc_page.export_original_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        i = 1
        while True:
            p = path.with_stem(f"{path.stem}_{i}")
            if not p.exists():
                return p
            i += 1

    @Slot(list, str)
    def _on_merge_pdfs(self, pdf_paths: list, output_path: str):
        logger.info("Uni\u00f3n de PDFs solicitada -> %s", output_path)
        from PySide6.QtCore import QThreadPool, QRunnable
        import fitz

        self._doc_page.merge_started()

        class _Worker(QRunnable):
            class S(QObject):
                progress = Signal(int, int)
                finished = Signal(str)
                error    = Signal(str)
            def __init__(self, paths, out):
                super().__init__()
                self.s = _Worker.S()
                self.paths, self.out = paths, out
            @Slot()
            def run(self):
                try:
                    doc = fitz.Document()
                    tocs = []
                    page_offset = 0
                    for i, p in enumerate(self.paths):
                        self.s.progress.emit(i + 1, len(self.paths))
                        src = fitz.Document(str(p))
                        doc.insert_pdf(src)
                        cnt = src.page_count
                        src.close()
                        tocs.append([1, p.stem, page_offset + 1])
                        page_offset += cnt
                    doc.set_toc(tocs)
                    doc.save(self.out, garbage=4, deflate=True)
                    doc.close()
                    self.s.finished.emit(self.out)
                except Exception as e:
                    self.s.error.emit(str(e))

        out_path = str(Path(output_path))
        w = _Worker(pdf_paths, out_path)
        w.s.progress.connect(self._doc_page.show_progress)
        w.s.finished.connect(self._doc_page.merge_finished)
        w.s.finished.connect(lambda _: self.statusBar().showMessage("PDFs unificados", 4000))
        w.s.error.connect(self._doc_page.merge_error)
        w.s.error.connect(lambda msg: self.statusBar().showMessage(msg, 4000))
        QThreadPool.globalInstance().start(w)

    @Slot(dict)
    def _on_ant_export_single_pdf(self, params: dict):
        logger.info("Antecedentes PDF \u00fanico solicitado -> %s", params.get("folder"))
        self._doc_page.export_single_started()
        output_name = self._project_path.stem + "_bookmarked.pdf" if self._project_path else None
        job_id = self._export.export_ant_single_pdf(
            params["folder"],
            params.get("desde", 0),
            params.get("hasta", 0),
            "Antecedentes PDF \u00fanico",
            output_name=output_name,
        )
        if not job_id:
            self._doc_page.export_single_error("No hay p\u00e1ginas para exportar.")
        else:
            def done(jid: str, path: str):
                self._doc_page.export_single_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                self._doc_page.export_single_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(dict)
    def _on_ant_export_split_bookmark(self, params: dict):
        logger.info("Antecedentes por marcador solicitado -> %s", params.get("folder"))
        self._doc_page.export_split_started()
        job_id = self._export.export_ant_split_bookmark(
            params["folder"],
            params.get("desde", 0),
            params.get("hasta", 0),
            "Antecedentes por marcador",
        )
        if not job_id:
            self._doc_page.export_split_error("No hay p\u00e1ginas con marcadores para dividir.")
        else:
            def done(jid: str, path: str):
                self._doc_page.export_split_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                self._doc_page.export_split_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(object)
    def _on_job_created(self, job: Job):
        logger.info("Trabajo creado: %s [%s]", job.id, job.label)
        self.statusBar().showMessage(f"Trabajo iniciado: {job.label}")

    @Slot(str, str)
    def _on_job_done(self, job_id: str, path: str):
        logger.info("Trabajo completado: %s -> %s", job_id, path)
        if job_id in self._custom_handlers:
            done, _ = self._custom_handlers[job_id]
            done(job_id, path)
        else:
            self._doc_page.export_finished(path)
        self.statusBar().showMessage("Exportaci\u00f3n completada", 4000)

    @Slot(str, str)
    def _on_job_error(self, job_id: str, msg: str):
        logger.error("Error en trabajo %s: %s", job_id, msg)
        if job_id in self._custom_handlers:
            _, err = self._custom_handlers[job_id]
            err(job_id, msg)
        else:
            self._doc_page.export_error(msg)
        self.statusBar().showMessage(msg, 4000)

    @Slot(int)
    def _on_correction_done(self, index: int):
        logger.info("Correcci\u00f3n completada para p\u00e1gina %d", index)
        page = self._model.get(index)
        if page:
            img = page.display_image
            self._doc_page.update_page(index, img)
        self._mark_dirty()

    @Slot(str)
    def _on_job_cancelled(self, job_id: str):
        logger.info("Trabajo cancelado: %s", job_id)
        self._custom_handlers.pop(job_id, None)
        self.statusBar().showMessage("Exportaci\u00f3n cancelada", 4000)

    # Process dialog updates

    def _safe_process_dialog(self) -> ProcessListDialog | None:
        if self._process_dialog is None:
            return None
        try:
            if self._process_dialog.isVisible():
                return self._process_dialog
        except RuntimeError:
            self._process_dialog = None
        return None

    @Slot(object)
    def _on_process_created(self, job):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.add_job(job.id, job.label, job.total)
        self._update_process_btn()

    @Slot(str, int, int)
    def _on_process_progress(self, job_id: str, cur: int, tot: int):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.update_job(job_id, cur, tot)

    @Slot(str, str)
    def _on_process_done(self, job_id: str, path: str):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.set_job_done(job_id, path)
        self._update_process_btn()
        self.statusBar().showMessage("Proceso completado", 4000)

    @Slot(str, str)
    def _on_process_error(self, job_id: str, msg: str):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.set_job_error(job_id, msg)
        self._update_process_btn()
        self.statusBar().showMessage(msg, 4000)

    @Slot(str)
    def _on_process_cancelled(self, job_id: str):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.set_job_cancelled(job_id)
        self._update_process_btn()
        self.statusBar().showMessage("Proceso cancelado", 4000)

    def _update_process_btn(self):
        active = sum(1 for j in self._export.all_jobs()
                     if j.status == JobStatus.RUNNING or j.status == JobStatus.QUEUED)
        if active:
            self._btn_processes.setText(f"Procesos ({active})")
            self._btn_processes.setStyleSheet(
                f"QPushButton {{ background: {SURFACE2}; border: 1px solid {INFO}; "
                f"border-radius: 4px; padding: 0 12px; font-size:9pt; color:{INFO}; }}"
                f"QPushButton:hover {{ background: {SURFACE3}; }}")
        else:
            self._btn_processes.setText("Procesos")
            self._btn_processes.setStyleSheet(
                f"QPushButton {{ background: {SURFACE2}; border: 1px solid {BORDER}; "
                f"border-radius: 4px; padding: 0 12px; font-size:9pt; color:{TEXT}; }}"
                f"QPushButton:hover {{ background: {SURFACE3}; }}")

    def closeEvent(self, event):
        self._autosave_timer.stop()
        if self._dirty:
            ret = QMessageBox.question(
                self, "Guardar cambios",
                "Hay cambios sin guardar. \u00bfDesea guardarlos?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if ret == QMessageBox.Save:
                self._save_project()
            elif ret == QMessageBox.Cancel:
                event.ignore()
                return
        self._cleanup_project()
        self._cfg.save()
        super().closeEvent(event)
