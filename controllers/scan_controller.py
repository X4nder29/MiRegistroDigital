"""ImportController — importación de archivos + corrección en hilos."""
from __future__ import annotations
import concurrent.futures
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel
from models.scan_settings import ScanSettings
from models.config_model import ConfigModel
from utils.image_utils import detect_corners, correct_perspective, deskew
from utils.file_utils import IMAGE_EXTS, PDF_EXT

logger = logging.getLogger("docscan.scan")

_fitz_lock = threading.Lock()

try:
    import twain
    _TWAIN_AVAILABLE = True
except ImportError:
    twain = None
    _TWAIN_AVAILABLE = False


class _ImportWorker(QRunnable):
    class S(QObject):
        page     = Signal(np.ndarray, str, int, str, list)  # image, source, src_page, comment, bookmarks
        progress = Signal(int, int)
        done     = Signal()
        error    = Signal(str)

    def __init__(self, paths: list[Path], pdf_dpi: int):
        super().__init__()
        self.s = _ImportWorker.S()
        self.paths, self.pdf_dpi = paths, pdf_dpi
        self._stop = False

    def cancel(self):
        self._stop = True

    @staticmethod
    def _render_single_page(path: str, pdf_dpi: int, pg: int,
                            annots_text: str = "") -> Optional[np.ndarray]:
        try:
            import fitz
            with _fitz_lock:
                doc = fitz.open(path)
                try:
                    mat = fitz.Matrix(pdf_dpi / 72, pdf_dpi / 72)
                    pix = doc[pg].get_pixmap(matrix=mat, colorspace=fitz.csRGB, annots=False)
                    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
                    return img[:, :, ::-1].copy()
                finally:
                    doc.close()
        except ImportError:
            pass
        try:
            from pdf2image import convert_from_path
            imgs = convert_from_path(path, dpi=pdf_dpi,
                                     first_page=pg + 1, last_page=pg + 1)
            return np.array(imgs[0].convert("RGB"))[:, :, ::-1] if imgs else None
        except ImportError:
            raise RuntimeError("Instala pymupdf o pdf2image para importar PDFs.")

    @staticmethod
    def _extract_annots(path: str, pg: int) -> str:
        try:
            import fitz
            with _fitz_lock:
                doc = fitz.open(path)
                try:
                    texts = []
                    for a in doc[pg].annots():
                        if a.type[0] in (fitz.PDF_ANNOT_TEXT, fitz.PDF_ANNOT_FREE_TEXT):
                            info = a.info
                            t = info.get("content", "") or info.get("title", "")
                            if t:
                                texts.append(t.strip())
                    return "\n".join(texts)
                finally:
                    doc.close()
        except Exception:
            return ""

    @staticmethod
    def _get_toc(path: str) -> list:
        try:
            import fitz
            with _fitz_lock:
                doc = fitz.open(path)
                try:
                    return doc.get_toc()
                finally:
                    doc.close()
        except Exception:
            return []

    def run(self):
        try:
            tasks: list[tuple[Path, Optional[int]]] = []
            for p in self.paths:
                ext = p.suffix.lower()
                if ext in IMAGE_EXTS:
                    tasks.append((p, None))
                elif ext == PDF_EXT:
                    for i in range(self._pdf_count(p)):
                        tasks.append((p, i))

            total = len(tasks)
            if total == 0:
                self.s.done.emit()
                return

            buffer: dict[int, tuple[np.ndarray, str, list]] = {}
            next_expected = 0
            lock = threading.Lock()

            pdf_toc_cache: dict[str, list] = {}

            def try_emit():
                nonlocal next_expected
                while next_expected in buffer:
                    img, comment_text, bmarks = buffer.pop(next_expected)
                    path, pg = tasks[next_expected]
                    self.s.page.emit(img, str(path), pg if pg is not None else -1,
                                     comment_text, bmarks)
                    self.s.progress.emit(next_expected + 1, total)
                    next_expected += 1

            for i, (path, pg) in enumerate(tasks):
                if self._stop:
                    break
                if pg is None:
                    try:
                        img = self._load_img(path)
                        if img is not None:
                            with lock:
                                buffer[i] = (img, "", [])
                                try_emit()
                    except Exception as e:
                        self.s.error.emit(f"{path.name}: {e}")

            pdf_tasks = [(i, str(path), pg) for i, (path, pg) in enumerate(tasks)
                         if pg is not None and not self._stop]

            for _, p_str, _ in pdf_tasks:
                if p_str not in pdf_toc_cache:
                    pdf_toc_cache[p_str] = self._get_toc(p_str)

            if pdf_tasks:
                max_workers = min(4, os.cpu_count() or 4)
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                    def render(task_idx: int, path: str, pg: int):
                        if self._stop:
                            return
                        try:
                            annot_text = self._extract_annots(path, pg)
                            img = self._render_single_page(path, self.pdf_dpi, pg, annot_text)
                            if img is not None:
                                toc = pdf_toc_cache.get(path, [])
                                page_bmarks = [(level, title) for level, title, pnum in toc
                                               if pnum == pg + 1]
                                with lock:
                                    if not self._stop:
                                        buffer[task_idx] = (img, annot_text, page_bmarks)
                                        try_emit()
                        except Exception as e:
                            self.s.error.emit(f"{Path(path).name} p.{pg + 1}: {e}")

                    futures = [pool.submit(render, idx, p, pg) for idx, p, pg in pdf_tasks]
                    concurrent.futures.wait(futures)
        except Exception as e:
            self.s.error.emit(str(e))
        finally:
            self.s.done.emit()

    def _load_img(self, path: Path) -> Optional[np.ndarray]:
        import cv2
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            from PIL import Image
            img = np.array(Image.open(path).convert("RGB"))[:, :, ::-1]
        return img

    def _pdf_count(self, path: Path) -> int:
        try:
            import fitz
            doc = fitz.open(str(path))
            n = len(doc)
            doc.close()
            return n
        except ImportError:
            pass
        try:
            from pypdf import PdfReader
            return len(PdfReader(str(path)).pages)
        except Exception:
            return 1


class _TwainScan:
    """Runs a TWAIN acquisition. Must be run synchronously on the Qt main thread —
    pytwain's modal loop pumps the calling thread's raw Win32 message queue, which
    only receives messages for windows owned by that same thread."""

    class S(QObject):
        page  = Signal(np.ndarray, str, int, str, list)  # image, source, src_page, comment, bookmarks
        count = Signal(int)
        done  = Signal()
        error = Signal(str)

    def __init__(self, settings: ScanSettings, parent_hwnd: int = 0):
        self.s = _TwainScan.S()
        self.settings = settings
        self.parent_hwnd = parent_hwnd
        self._stop = False

    def cancel(self):
        self._stop = True

    NO_SCANNER_MSG = ("No se detectó ningún escáner. Conectá un dispositivo TWAIN "
                      "(por ejemplo, por USB) y volvé a intentar.")

    def run(self):
        if not _TWAIN_AVAILABLE:
            self.s.error.emit(self.NO_SCANNER_MSG)
            return
        try:
            with twain.SourceManager(self.parent_hwnd or None) as sm:
                if not list(sm.source_list):
                    self.s.error.emit(self.NO_SCANNER_MSG)
                    return
                src = sm.open_source(self.settings.device_name or None)
                if src is None:
                    self.s.error.emit("No se pudo abrir el escáner seleccionado. "
                                     "Verificá que esté encendido y conectado.")
                    return
                with src:
                    self._configure(src)
                    count = 0

                    def after(image, remaining):
                        nonlocal count
                        if self._stop:
                            image.close()
                            raise twain.exceptions.CancelAll
                        fd, tmp_path = tempfile.mkstemp(".bmp")
                        os.close(fd)
                        try:
                            image.save(tmp_path)
                            arr = cv2.imread(tmp_path, cv2.IMREAD_COLOR)
                        finally:
                            image.close()
                            try:
                                os.remove(tmp_path)
                            except OSError:
                                pass
                        if arr is not None:
                            count += 1
                            self.s.page.emit(arr, "scanner", -1, "", [])
                            self.s.count.emit(count)

                    src.acquire_natively(after=after, show_ui=False, modal=False)
            self.s.done.emit()
        except twain.exceptions.CancelAll:
            self.s.done.emit()
        except Exception as e:
            logger.exception("Error durante el escaneo TWAIN")
            self.s.error.emit(self._friendly_error(e))

    _NO_DRIVER_EXCEPTIONS = (
        "SMLoadFileFailed", "SMOpenFailed", "SMGetProcAddressFailed",
        "NoDataSourceError",
    )

    def _friendly_error(self, e: Exception) -> str:
        if type(e).__name__ in self._NO_DRIVER_EXCEPTIONS:
            return self.NO_SCANNER_MSG
        return f"Error del escáner: {e}"

    def _configure(self, src):
        dpi = float(self.settings.dpi)
        src.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, dpi)
        src.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, dpi)
        pixel_type = {"color": twain.TWPT_RGB, "grayscale": twain.TWPT_GRAY,
                     "bw": twain.TWPT_BW}.get(self.settings.color_mode, twain.TWPT_RGB)
        try:
            src.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, pixel_type)
        except Exception:
            logger.warning("El escáner no admite cambiar el modo de color")
        if self.settings.source == "adf":
            try:
                src.set_capability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
                src.set_capability(twain.CAP_XFERCOUNT, twain.TWTY_INT16, -1)
            except Exception:
                logger.warning("El escáner no admite el alimentador automático (ADF)")
            try:
                src.set_capability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, self.settings.duplex)
            except Exception:
                logger.warning("El escáner no admite dúplex")
        else:
            try:
                src.set_capability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, False)
            except Exception:
                pass


class ScanController(QObject):
    page_added      = Signal(object)
    import_done     = Signal()
    import_progress = Signal(int, int)
    error           = Signal(str)
    correction_done = Signal(int)
    order_changed    = Signal()
    bookmark_updated = Signal(int, list)
    scan_progress    = Signal(int)
    scan_done        = Signal()
    scan_error       = Signal(str)

    def __init__(self, model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._m    = model
        self._cfg  = config
        self._pool = QThreadPool.globalInstance()
        self._imp_w:  Optional[_ImportWorker] = None
        self._scan_w: Optional[_TwainScan] = None
        logger.info("ScanController inicializado")

    @Slot(list)
    def import_files(self, paths: list[Path]):
        logger.info("Importando %d archivos", len(paths))
        w = _ImportWorker(paths, self._cfg.get("import", "pdf_dpi", 300))
        w.s.page.connect(self._on_page_src)
        w.s.progress.connect(self.import_progress)
        w.s.done.connect(self.import_done)
        w.s.error.connect(self.error)
        self._imp_w = w
        self._pool.start(w)

    @Slot()
    def cancel_import(self):
        logger.info("Importación cancelada")
        if self._imp_w:
            self._imp_w.cancel()

    def is_twain_available(self) -> bool:
        return _TWAIN_AVAILABLE

    def list_scanner_sources(self) -> list[str]:
        if not _TWAIN_AVAILABLE:
            return []
        try:
            with twain.SourceManager() as sm:
                return list(sm.source_list)
        except Exception:
            logger.exception("Error listando escáneres TWAIN")
            return []

    def start_scan(self, settings: ScanSettings, parent_hwnd: int = 0):
        """Must be called on the Qt main thread — see _TwainScan docstring."""
        logger.info("Iniciando escaneo TWAIN: %s", settings)
        w = _TwainScan(settings, parent_hwnd)
        w.s.page.connect(self._on_scan_page_src)
        w.s.count.connect(self.scan_progress)
        w.s.done.connect(self.scan_done)
        w.s.error.connect(self.scan_error)
        self._scan_w = w
        w.run()

    @Slot()
    def cancel_scan(self):
        logger.info("Escaneo cancelado")
        if self._scan_w:
            self._scan_w.cancel()

    @Slot(int)
    def auto_correct(self, index: int):
        logger.info("Auto-corrección solicitada para página %d", index)
        page = self._m.get(index)
        if not page:
            logger.warning("auto_correct: página %d no encontrada", index)
            return
        img = page.original_image.copy()
        corners = detect_corners(img)
        if corners is not None:
            img = correct_perspective(img, corners)
        img, angle = deskew(img)
        self._m.set_corrected(index, img, angle)
        self.correction_done.emit(index)

    @Slot(int, float)
    def rotate_manual(self, index: int, angle: float):
        logger.info("Rotación manual página %d: %.1f°", index, angle)
        page = self._m.get(index)
        if not page:
            logger.warning("rotate_manual: página %d no encontrada", index)
            return
        img, a = deskew(page.original_image.copy(), angle)
        self._m.set_corrected(index, img, a)
        self.correction_done.emit(index)

    @Slot(int, int)
    def reorder_page(self, from_idx: int, to_idx: int):
        logger.info("Reorden página %d -> %d", from_idx, to_idx)
        self._m.reorder(from_idx, to_idx)
        self.order_changed.emit()

    @Slot(list, int)
    def reorder_batch(self, indices: list[int], to_idx: int):
        logger.info("Reorden batch %s -> %d", indices, to_idx)
        self._m.reorder_batch(indices, to_idx)
        self.order_changed.emit()

    @Slot(list)
    def reorder_to_sequence(self, indices_in_order: list[int]):
        logger.info("Reorden a secuencia: %s", indices_in_order)
        self._m.reorder_to_sequence(indices_in_order)
        self.order_changed.emit()

    @Slot(int, list)
    def set_bookmark(self, index: int, labels: list):
        logger.info("Bookmark página %d: %s", index, labels[0][1] if labels else "(sin)")
        self._m.set_bookmark(index, labels)
        self.bookmark_updated.emit(index, labels)

    @Slot(int)
    def reset_correction(self, index: int):
        logger.info("Reset corrección página %d", index)
        self._m.set_corrected(index, None, 0.0)
        self.correction_done.emit(index)

    @Slot(np.ndarray, str, int, str, list)
    def _on_page_src(self, image: np.ndarray, src: str, src_page: int,
                     comment: str = "", bookmarks: list = []):
        self._process_and_add(image, src, src_page, comment, bookmarks)

    @Slot(np.ndarray, str, int, str, list)
    def _on_scan_page_src(self, image: np.ndarray, src: str, src_page: int,
                          comment: str = "", bookmarks: list = []):
        dpi = self._scan_w.settings.dpi if self._scan_w else 300
        self._process_and_add(image, src, src_page, comment, bookmarks, dpi=dpi)

    def _process_and_add(self, image: np.ndarray, src: str, src_page: int = -1,
                         comment: str = "", bookmarks: list | None = None,
                         dpi: int | None = None):
        bmarks = bookmarks or []
        if dpi is None:
            dpi = self._cfg.get("import", "pdf_dpi", 300)
        page = self._m.add_page(image, dpi, src, source_page=src_page,
                                comment=comment, bookmarks=bmarks)
        logger.debug("Página añadida al modelo: index=%d, src=%s, comment=%s, bookmarks=%d",
                     page.index, src, comment[:30] if comment else "", len(bmarks))
        self.page_added.emit(page)
