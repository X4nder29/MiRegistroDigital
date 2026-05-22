"""Ventana principal — sidebar minimal + stacked pages."""
from __future__ import annotations
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame,
    QSizePolicy, QStyle, QApplication,
)
from PySide6.QtCore import Qt, Slot, QSize, QObject, QTimer
from PySide6.QtGui import QFont, QIcon

from models.scan_model import ScanModel
from models.config_model import ConfigModel
from models.job_model import Job, JobStatus
from controllers.scan_controller import ScanController
from controllers.ocr_controller import OCRController
from controllers.export_controller import ExportController
from views.scan_page import ScanPage
from views.registos_section import RegistosSection
from views.antecedentes_page import AntecedentesPage
from views.jobs_page import JobsPage
from views.settings_page import SettingsPage
from views.widgets import FullscreenViewer, ProcessListDialog
from views.theme import BG, SURFACE, SURFACE2, SURFACE3, BORDER, TEXT, TEXT_DIM, TEXT_SEC, ACCENT2, INFO, SUCCESS, DANGER

logger = logging.getLogger("docscan.main")


_NAV = [
    ("import",       "   Importar"),
    ("civil",        "   Registros"),
    ("antecedentes", "   Antecedentes"),
    ("jobs",         "   Trabajos"),
    ("settings",     "   Ajustes"),
]


class NavButton(QPushButton):
    def __init__(self, label: str, icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setText(label)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(16, 16))
        self.setCheckable(True)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-left: 2px solid transparent;
                border-radius: 0;
                color: {TEXT_DIM};
                text-align: left;
                padding: 0 14px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background: transparent; color: {TEXT_SEC}; }}
            QPushButton:checked {{
                border-left: 2px solid {ACCENT2};
                color: {TEXT};
            }}
        """)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiRegistroDigital")
        self.setMinimumSize(1080, 700)
        logger.info("MainWindow inicializando")

        self._cfg    = ConfigModel()
        self._model  = ScanModel()

        self._scan   = ScanController(self._model, self._cfg, self)
        self._ocr    = OCRController(self._model, self._cfg, self)
        self._export = ExportController(self._model, self._cfg, self)

        self._pending_pages: list = []
        self._fullscreen_viewer: FullscreenViewer | None = None
        self._process_dialog: ProcessListDialog | None = None
        self._custom_handlers: dict[str, tuple] = {}

        self._build_ui()
        self._connect()

        self.statusBar().showMessage("Listo")
        logger.info("MainWindow inicializada")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        middle = QWidget()
        mid_layout = QHBoxLayout(middle)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        mid_layout.addWidget(self._build_sidebar())

        self._stack = QStackedWidget()
        self._imp_page    = ScanPage()
        self._civil_sect  = RegistosSection()
        self._ant_page    = AntecedentesPage()
        self._jobs_page   = JobsPage()
        self._sett_page   = SettingsPage(self._cfg)

        for page in (self._imp_page, self._civil_sect, self._ant_page,
                     self._jobs_page, self._sett_page):
            self._stack.addWidget(page)

        mid_layout.addWidget(self._stack)
        root.addWidget(middle, 1)

        self._bottom_bar = self._build_bottom_bar()
        root.addWidget(self._bottom_bar)

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(34)
        bar.setStyleSheet(f"background:{SURFACE}; border-top: 1px solid {BORDER};")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)

        self._status_msg = QLabel("Listo")
        self._status_msg.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        hl.addWidget(self._status_msg, 1)

        self._notif_label = QLabel()
        self._notif_label.setVisible(False)
        self._notif_label.setFixedHeight(26)
        hl.addWidget(self._notif_label)

        self._notif_timer = QTimer(self)
        self._notif_timer.setSingleShot(True)
        self._notif_timer.timeout.connect(self._hide_notification)

        self._btn_processes = QPushButton("Procesos")
        self._btn_processes.setFixedHeight(26)
        self._btn_processes.setStyleSheet(
            f"QPushButton {{ background: {SURFACE2}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 0 12px; font-size:9pt; color:{TEXT}; }}"
            f"QPushButton:hover {{ background: {SURFACE3}; }}")
        self._btn_processes.clicked.connect(self._open_process_dialog)
        hl.addWidget(self._btn_processes)

        return bar

    def _open_process_dialog(self):
        if self._safe_process_dialog() is None:
            self._process_dialog = ProcessListDialog(self)
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

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setMinimumWidth(160)
        sidebar.setMaximumWidth(220)
        sidebar.setStyleSheet(f"background:{BG}; border-right: 1px solid {BORDER};")
        v = QVBoxLayout(sidebar)
        v.setContentsMargins(0, 16, 0, 12)
        v.setSpacing(0)

        logo = QLabel("  MiRegistroDigital")
        logo.setAlignment(Qt.AlignLeft)
        logo.setFixedHeight(44)
        logo.setStyleSheet(f"font-size:14pt; font-weight:700; color:{TEXT}; border:none; padding: 0 14px; letter-spacing: -0.3px;")
        v.addWidget(logo)
        v.addSpacing(16)

        style = QApplication.style()
        icon_map = {
            "import": style.standardIcon(QStyle.SP_DialogOpenButton),
            "civil":  style.standardIcon(QStyle.SP_FileDialogDetailedView),
            "antecedentes": style.standardIcon(QStyle.SP_DirIcon),
            "jobs":   style.standardIcon(QStyle.SP_BrowserReload),
            "settings": style.standardIcon(QStyle.SP_DialogApplyButton),
        }
        self._nav_btns: dict[str, NavButton] = {}
        for key, label in _NAV:
            btn = NavButton(label, icon_map[key])
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self._nav_btns[key] = btn
            v.addWidget(btn)

        v.addStretch()
        ver = QLabel("v1.0.0")
        ver.setStyleSheet(f"color:{TEXT_DIM}; font-size:8pt; border:none; padding: 0 4px;")
        v.addWidget(ver)
        return sidebar

    def _navigate(self, key: str):
        idx = {"import": 0, "civil": 1, "antecedentes": 2, "jobs": 3, "settings": 4}
        for k, btn in self._nav_btns.items():
            btn.setChecked(k == key)
        self._stack.setCurrentIndex(idx.get(key, 0))
        self._cfg.set("ui", "last_page", key)

    def _connect(self):
        logger.info("Conectando señales…")
        ip = self._imp_page

        ip.import_images_requested.connect(self._on_import)
        ip.import_pdf_requested.connect(self._on_import)
        ip.import_cancel_requested.connect(self._scan.cancel_import)
        ip.cut_toggled.connect(self._on_cut_toggled)
        ip.page_deleted.connect(self._on_page_deleted)
        ip.fullscreen_requested.connect(self._open_fullscreen)
        ip.navigate.connect(self._navigate)
        ip.correction_requested.connect(self._scan.auto_correct)
        ip.rotation_changed.connect(self._scan.rotate_manual)
        ip.reset_correction.connect(self._scan.reset_correction)

        ip.page_reordered.connect(self._scan.reorder_page)
        ip.bookmark_set.connect(self._scan.set_bookmark)

        self._scan.order_changed.connect(self._on_order_changed)
        self._scan.bookmark_updated.connect(self._on_bookmark_updated)

        self._scan.page_added.connect(self._on_page_queued)
        self._scan.import_done.connect(self._flush_pending_pages)
        self._scan.import_done.connect(lambda: self.statusBar().showMessage(
            f"Importación completa — {self._model.count} página(s)"))
        self._scan.import_progress.connect(ip.show_import_progress)
        self._scan.error.connect(self._on_error)
        self._scan.correction_done.connect(self._on_correction_done)
        logger.debug("Señales de ScanPage/ScanController conectadas")

        cs = self._civil_sect
        cp = cs.civil_page
        cs.ocr_all_requested.connect(self._on_ocr_all)
        cs.ocr_page_requested.connect(self._ocr.run_page)
        cs.ocr_cancel_requested.connect(self._on_ocr_cancel)
        cs.serial_corrected.connect(self._ocr.override)
        cs.export_requested.connect(self._on_civil_export)
        cs.export_bookmark_requested.connect(self._on_civil_export_bookmark)
        cs.comment_set.connect(self._on_comment_set)
        cs.export_original_pdf_requested.connect(self._on_export_original_pdf)
        cs.ocr_area_saved.connect(self._on_area_saved)
        cs.parallel_workers_changed.connect(self._on_parallel_workers_changed)

        cp.page_reordered.connect(self._scan.reorder_page)
        cp.page_reordered_seq.connect(self._scan.reorder_to_sequence)
        cp.bookmark_set.connect(self._scan.set_bookmark)

        cs.bookmarks_export_requested.connect(self._on_bookmarks_export)
        cs.merge_requested.connect(self._on_merge_pdfs)

        # init from config
        cp.set_parallel_workers(self._cfg.get("ocr", "parallel_workers", 4))

        self._ocr.ocr_result.connect(self._on_ocr_result)
        self._ocr.ocr_all_done.connect(cp.ocr_finished)
        self._ocr.ocr_all_done.connect(self._sync_bookmarks_data)
        self._ocr.ocr_error.connect(cp.set_ocr_error)
        logger.debug("Señales de CivilPage/OCRController conectadas")

        self._scan.import_done.connect(self._sync_bookmarks_data)

        ap = self._ant_page
        ap.cut_toggle_requested.connect(self._on_cut_toggled)
        ap.clear_cuts_requested.connect(self._on_clear_cuts)
        ap.export_requested.connect(self._on_ant_export)
        ap.export_single_pdf.connect(self._on_ant_export_single_pdf)
        ap.export_split_bookmark.connect(self._on_ant_export_split_bookmark)
        ap.fullscreen_requested.connect(self._open_fullscreen)
        ap.page_deleted.connect(self._on_page_deleted)
        ap.page_reordered.connect(self._scan.reorder_page)
        ap.bookmark_set.connect(self._scan.set_bookmark)
        ap.comment_set.connect(self._on_comment_set)
        ap.export_original_pdf_requested.connect(self._on_export_original_pdf)

        self._export.job_created.connect(self._on_job_created)
        self._export.job_progress.connect(self._on_job_progress)
        self._export.job_done.connect(self._on_job_done)
        self._export.job_error.connect(self._on_job_error)
        self._export.job_cancelled.connect(self._on_job_cancelled)
        self._export.job_created.connect(self._on_process_created)
        self._export.job_progress.connect(self._on_process_progress)
        self._export.job_done.connect(self._on_process_done)
        self._export.job_error.connect(self._on_process_error)
        self._export.job_cancelled.connect(self._on_process_cancelled)
        logger.debug("Señales de ExportController conectadas")

        self._jobs_page.cancel_requested.connect(self._on_export_cancel)

        self._sett_page.settings_saved.connect(
            lambda: self.statusBar().showMessage("Configuración guardada", 3000))

        self._navigate("import")
        self._nav_btns["import"].setChecked(True)

    def _on_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}")

    @Slot(list)
    def _on_import(self, paths: list[Path]):
        logger.info("Importando %d archivos", len(paths))
        self._imp_page.import_busy(True)
        self.statusBar().showMessage(f"Importando {len(paths)} archivo(s)…")
        self._scan.import_files(paths)

    @Slot(object)
    def _on_page_queued(self, page):
        self._pending_pages.append(page)

    @Slot()
    def _flush_pending_pages(self):
        ip = self._imp_page
        ip.import_busy(False)
        ip.grid.blockSignals(True)
        cp = self._civil_sect.civil_page
        cp._table.blockSignals(True)
        ap = self._ant_page
        ap.grid.blockSignals(True)
        for page in self._pending_pages:
            img = page.display_image
            ip.add_page(page.index, img)
            cp.add_page(page.index, img)
            ap.add_page(page.index, img)
        ip.grid.blockSignals(False)
        cp._table.blockSignals(False)
        ap.grid.blockSignals(False)
        self._pending_pages.clear()

    @Slot(object)
    def _on_page_added(self, page):
        logger.debug("Página añadida directa: index=%d", page.index)
        img = page.display_image
        self._imp_page.add_page(page.index, img)
        self._civil_sect.civil_page.add_page(page.index, img)
        self._ant_page.add_page(page.index, img)
        self.statusBar().showMessage(f"Página {page.index + 1} cargada")

    @Slot(int)
    def _on_page_deleted(self, index: int):
        logger.info("Página eliminada: %d", index)
        self._model.remove(index)
        self._imp_page.remove_page(index)
        self._civil_sect.civil_page.remove_page(index)
        self._ant_page.remove_page(index)
        self._sync_bookmarks_data()

    @Slot(int)
    def _on_cut_toggled(self, index: int):
        is_cut = self._model.toggle_cut(index)
        self._imp_page.set_cut(index, is_cut)
        self._ant_page.set_cut(index, is_cut)
        self._ant_page.update_groups(
            [[p.index for p in g] for g in self._model.get_groups()])

    @Slot()
    def _on_clear_cuts(self):
        self._model.set_cuts(set())
        for page in self._model.pages:
            self._imp_page.set_cut(page.index, False)
            self._ant_page.set_cut(page.index, False)
        self._ant_page.update_groups([])

    @Slot()
    def _on_ocr_all(self):
        logger.info("OCR todas las páginas solicitado")
        self._civil_sect.civil_page.ocr_started()
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
        self._civil_sect.civil_page.ocr_finished()
        self.statusBar().showMessage("OCR cancelado")

    @Slot(int, str, float)
    def _on_ocr_result(self, index: int, serial: str, conf: float):
        logger.debug("Resultado OCR página %d: serial=%s conf=%.2f", index, serial, conf)
        self._civil_sect.civil_page.set_ocr_result(index, serial, conf)
        try:
            self._civil_sect.bookmarks_page.set_ocr_result(index, serial, conf)
        except Exception:
            logger.exception("Error actualizando bookmarks_page")
        self._imp_page.set_serial(index, serial, conf)

    @Slot(int, float, float, float, float)
    def _on_area_saved(self, page_index: int, x1: float, y1: float, x2: float, y2: float):
        logger.info("Área OCR guardada: (%.2f, %.2f, %.2f, %.2f)", x1, y1, x2, y2)
        area = (x1, y1, x2, y2)
        for page in self._model.pages:
            page.ocr_area = area
        self.statusBar().showMessage(
            f"Área OCR global guardada — {self._model.count} página(s)")

    def _sync_bookmarks_data(self):
        pages_data = []
        for page in self._model.pages:
            pages_data.append({
                "index": page.index,
                "label": page.final_label,
                "image": page.display_image,
            })
        self._civil_sect.bookmarks_page.set_pages_data(pages_data)

    @Slot(int, str)
    def _on_bookmark_updated(self, index: int, label: str):
        self._imp_page.set_bookmark(index, label)
        self._civil_sect.civil_page.set_bookmark(index, label)
        self._ant_page.set_bookmark(index, label)

    @Slot()
    def _on_order_changed(self):
        pages = self._model.pages
        self._imp_page.rebuild(pages)
        self._civil_sect.civil_page.rebuild(pages)
        self._ant_page.rebuild(pages)
        self._sync_bookmarks_data()

    @Slot(str)
    def _on_civil_export(self, folder: str):
        logger.info("Exportación civil solicitada -> %s", folder)
        self._civil_sect.civil_page.export_started()
        job_id = self._export.export_civil(folder, "Registros Civiles")
        if not job_id:
            self._civil_sect.civil_page.export_error("No hay páginas para exportar.")

    @Slot(str)
    def _on_civil_export_bookmark(self, folder: str):
        logger.info("Exportación civil por marcador solicitada -> %s", folder)
        cp = self._civil_sect.civil_page
        cp.export_bookmark_started()
        job_id = self._export.export_civil_bookmark(folder, "Registros por marcador")
        if not job_id:
            cp.export_bookmark_error("No hay páginas para exportar.")
        else:
            def done(jid: str, path: str):
                cp.export_bookmark_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                cp.export_bookmark_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(int, str)
    def _on_comment_set(self, index: int, text: str):
        self._model.set_comment(index, text)

    @Slot(str)
    def _on_export_original_pdf(self, folder: str):
        logger.info("Exportación PDF original solicitada -> %s", folder)
        from PySide6.QtWidgets import QApplication
        mw = QApplication.instance().activeWindow()
        cp = self._civil_sect.civil_page
        ap = self._ant_page
        cp.export_original_started()
        ap.export_original_started()
        job_id = self._export.export_original_pdf(folder, "PDF original")
        if not job_id:
            cp.export_original_error("No hay páginas para exportar.")
            ap.export_original_error("No hay páginas para exportar.")
        else:
            def done(jid: str, path: str):
                cp.export_original_finished(path)
                ap.export_original_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                cp.export_original_error(msg)
                ap.export_original_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(list, str, int)
    def _on_bookmarks_export(self, pages_data: list, folder: str, dpi: int):
        logger.info("Exportación con marcadores solicitada -> %s", folder)
        import cv2
        import fitz
        from PySide6.QtCore import QThreadPool, QRunnable

        bp = self._civil_sect.bookmarks_page
        bp.export_started()

        class _Worker(QRunnable):
            class S(QObject):
                progress = Signal(int, int)
                finished = Signal(str)
                error    = Signal(str)
            def __init__(self, pages, out, dpi):
                super().__init__()
                self.s = _Worker.S()
                self.pages, self.out, self.dpi = pages, out, dpi
            @Slot()
            def run(self):
                try:
                    doc = fitz.Document()
                    for i, item in enumerate(self.pages):
                        self.s.progress.emit(i + 1, len(self.pages))
                        img = item["image"]
                        h, w = img.shape[:2]
                        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
                        page = doc.new_page(width=w, height=h)
                        page.insert_image(page.rect, stream=buf.tobytes())
                    tocs = [[1, item["label"], i + 1] for i, item in enumerate(self.pages)]
                    doc.set_toc(tocs)
                    doc.save(self.out, garbage=4, deflate=True)
                    doc.close()
                    self.s.finished.emit(self.out)
                except Exception as e:
                    self.s.error.emit(str(e))

        output = Path(folder) / f"registros_marcadores.pdf"
        output = self._unique_path(output)
        w = _Worker(pages_data, str(output), dpi)
        w.s.progress.connect(bp.show_progress)
        w.s.finished.connect(bp.export_finished)
        w.s.finished.connect(lambda _: self._show_notification("PDF con marcadores generado"))
        w.s.error.connect(bp.export_error)
        w.s.error.connect(lambda msg: self._show_notification(msg, success=False))
        QThreadPool.globalInstance().start(w)

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
        logger.info("Unión de PDFs solicitada -> %s", output_path)
        from PySide6.QtCore import QThreadPool, QRunnable
        import fitz

        mp = self._civil_sect.merge_page
        mp.merge_started()

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
        w.s.progress.connect(mp.show_progress)
        w.s.finished.connect(mp.merge_finished)
        w.s.finished.connect(lambda _: self._show_notification("PDFs unificados"))
        w.s.error.connect(mp.merge_error)
        w.s.error.connect(lambda msg: self._show_notification(msg, success=False))
        QThreadPool.globalInstance().start(w)

    @Slot(dict)
    def _on_ant_export(self, params: dict):
        logger.info("Exportación antecedentes solicitada -> %s", params.get("folder"))
        self._ant_page.export_started()
        job_id = self._export.export_ant(
            params["folder"],
            params["serial_ini"],
            params["padding"],
            params.get("desde", 0),
            params.get("hasta", 0),
            "Antecedentes",
        )
        if not job_id:
            self._ant_page.export_error("No hay grupos de páginas para exportar.")

    @Slot(dict)
    def _on_ant_export_single_pdf(self, params: dict):
        logger.info("Antecedentes PDF único solicitado -> %s", params.get("folder"))
        ap = self._ant_page
        ap.export_single_started()
        job_id = self._export.export_ant_single_pdf(
            params["folder"],
            params["serial_ini"],
            params["padding"],
            params.get("desde", 0),
            params.get("hasta", 0),
            "Antecedentes PDF único",
        )
        if not job_id:
            ap.export_single_error("No hay páginas para exportar.")
        else:
            def done(jid: str, path: str):
                ap.export_single_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                ap.export_single_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(dict)
    def _on_ant_export_split_bookmark(self, params: dict):
        logger.info("Antecedentes por marcador solicitado -> %s", params.get("folder"))
        ap = self._ant_page
        ap.export_split_started()
        job_id = self._export.export_ant_split_bookmark(
            params["folder"],
            params["serial_ini"],
            params["padding"],
            params.get("desde", 0),
            params.get("hasta", 0),
            "Antecedentes por marcador",
        )
        if not job_id:
            ap.export_split_error("No hay páginas con marcadores para dividir.")
        else:
            def done(jid: str, path: str):
                ap.export_split_finished(path)
                self._custom_handlers.pop(jid, None)
            def err(jid: str, msg: str):
                ap.export_split_error(msg)
                self._custom_handlers.pop(jid, None)
            self._custom_handlers[job_id] = (done, err)

    @Slot(object)
    def _on_job_created(self, job: Job):
        logger.info("Trabajo creado: %s [%s]", job.id, job.label)
        self._jobs_page.add_job(job)
        self.statusBar().showMessage(f"Trabajo iniciado: {job.label}")

    @Slot(str, int, int)
    def _on_job_progress(self, job_id: str, cur: int, tot: int):
        job = self._export.all_jobs()
        for j in job:
            if j.id == job_id:
                self._jobs_page.update_job(j)
                break

    @Slot(str, str)
    def _on_job_done(self, job_id: str, path: str):
        logger.info("Trabajo completado: %s -> %s", job_id, path)
        if job_id in self._custom_handlers:
            done, _ = self._custom_handlers[job_id]
            done(job_id, path)
            for j in self._export.all_jobs():
                if j.id == job_id:
                    self._jobs_page.update_job(j)
                    break
        else:
            for j in self._export.all_jobs():
                if j.id == job_id:
                    self._jobs_page.update_job(j)
                    if j.job_type.value == "civil":
                        self._civil_sect.civil_page.export_finished(path)
                    else:
                        self._ant_page.export_finished(path)
                    break
        self._show_notification("Exportación completada")

    @Slot(str, str)
    def _on_error(self, msg: str):
        logger.error("Error: %s", msg)
        self.statusBar().showMessage(f"Error: {msg}")

    @Slot(str, str)
    def _on_job_error(self, job_id: str, msg: str):
        logger.error("Error en trabajo %s: %s", job_id, msg)
        if job_id in self._custom_handlers:
            _, err = self._custom_handlers[job_id]
            err(job_id, msg)
            for j in self._export.all_jobs():
                if j.id == job_id:
                    self._jobs_page.update_job(j)
                    break
        else:
            for j in self._export.all_jobs():
                if j.id == job_id:
                    self._jobs_page.update_job(j)
                    if j.job_type.value == "civil":
                        self._civil_sect.civil_page.export_error(msg)
                    else:
                        self._ant_page.export_error(msg)
                    break
        self._show_notification(msg, success=False)

    @Slot(int)
    def _on_correction_done(self, index: int):
        logger.info("Corrección completada para página %d", index)
        page = self._model.get(index)
        if page:
            img = page.display_image
            self._imp_page.update_page(index, img)
            self._civil_sect.civil_page.update_page(index, img)
            self._ant_page.update_page(index, img)

    @Slot(str)
    def _on_job_cancelled(self, job_id: str):
        logger.info("Trabajo cancelado: %s", job_id)
        self._custom_handlers.pop(job_id, None)
        for j in self._export.all_jobs():
            if j.id == job_id:
                self._jobs_page.update_job(j)
                break
        self._show_notification("Exportación cancelada", success=False)

    # ── Non-blocking notification ──────────────────────────────

    def _show_notification(self, text: str, success: bool = True):
        color = SUCCESS if success else DANGER
        self._notif_label.setText(text)
        self._notif_label.setStyleSheet(
            f"QLabel {{ background: {SURFACE2}; border: 1px solid {color}; "
            f"border-radius: 4px; padding: 0 10px; font-size:8pt; color:{color}; }}"
        )
        self._notif_label.setVisible(True)
        self._notif_timer.start(4000)

    def _hide_notification(self):
        self._notif_label.setVisible(False)

    # ── Process dialog updates ─────────────────────────────────

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
        self._show_notification("Proceso completado")

    @Slot(str, str)
    def _on_process_error(self, job_id: str, msg: str):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.set_job_error(job_id, msg)
        self._update_process_btn()
        self._show_notification(msg, success=False)

    @Slot(str)
    def _on_process_cancelled(self, job_id: str):
        dlg = self._safe_process_dialog()
        if dlg:
            dlg.set_job_cancelled(job_id)
        self._update_process_btn()
        self._show_notification("Proceso cancelado", success=False)

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

    @Slot(str)
    def _on_export_cancel(self, job_id: str):
        logger.info("Cancelación de exportación solicitada: %s", job_id)
        self._export.cancel_export(job_id)
        self.statusBar().showMessage("Cancelando exportación…")

    @Slot(int)
    def _open_fullscreen(self, index: int):
        pages = self._model.pages
        if not pages:
            return
        self._fullscreen_viewer = FullscreenViewer(pages, start=index, parent=self)
        self._fullscreen_viewer.bookmark_changed.connect(self._scan.set_bookmark)
        self._fullscreen_viewer.comment_changed.connect(self._on_comment_set)
        self._fullscreen_viewer.show()

    def closeEvent(self, event):
        self._cfg.save()
        super().closeEvent(event)
