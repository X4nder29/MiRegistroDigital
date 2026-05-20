"""ImportController — importación de archivos + corrección en hilos."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import numpy as np
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel
from models.config_model import ConfigModel
from utils.image_utils import detect_corners, correct_perspective, deskew
from utils.file_utils import IMAGE_EXTS, PDF_EXT

logger = logging.getLogger("docscan.scan")


class _ImportWorker(QRunnable):
    class S(QObject):
        page     = Signal(np.ndarray, str)
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
            for n, (path, pg) in enumerate(tasks):
                if self._stop:
                    break
                try:
                    img = self._load_pdf(path, pg) if pg is not None else self._load_img(path)
                    if img is not None:
                        self.s.progress.emit(n + 1, total)
                        self.s.page.emit(img, str(path))
                except Exception as e:
                    self.s.error.emit(f"{path.name}: {e}")
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

    def _load_pdf(self, path: Path, pg: int) -> Optional[np.ndarray]:
        try:
            import fitz
            doc = fitz.open(str(path))
            mat = fitz.Matrix(self.pdf_dpi / 72, self.pdf_dpi / 72)
            pix = doc[pg].get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
            doc.close()
            return img[:, :, ::-1]
        except ImportError:
            pass
        try:
            from pdf2image import convert_from_path
            imgs = convert_from_path(str(path), dpi=self.pdf_dpi,
                                     first_page=pg + 1, last_page=pg + 1)
            return np.array(imgs[0].convert("RGB"))[:, :, ::-1] if imgs else None
        except ImportError:
            raise RuntimeError("Instala pymupdf o pdf2image para importar PDFs.")

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


class ScanController(QObject):
    page_added      = Signal(object)
    import_done     = Signal()
    import_progress = Signal(int, int)
    error           = Signal(str)
    correction_done = Signal(int)
    order_changed    = Signal()
    bookmark_updated = Signal(int, str)

    def __init__(self, model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._m    = model
        self._cfg  = config
        self._pool = QThreadPool.globalInstance()
        self._imp_w:  Optional[_ImportWorker] = None
        logger.info("ScanController inicializado")

    @Slot(list)
    def import_files(self, paths: list[Path]):
        logger.info("Importando %d archivos", len(paths))
        w = _ImportWorker(paths, self._cfg.get("output", "pdf_dpi", 200))
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

    @Slot(int, str)
    def set_bookmark(self, index: int, label: str):
        logger.info("Bookmark página %d: %s", index, label or "(sin)")
        self._m.set_bookmark(index, label)
        self.bookmark_updated.emit(index, label)

    @Slot(int)
    def reset_correction(self, index: int):
        logger.info("Reset corrección página %d", index)
        self._m.set_corrected(index, None, 0.0)
        self.correction_done.emit(index)

    @Slot(np.ndarray, str)
    def _on_page_src(self, image: np.ndarray, src: str):
        self._process_and_add(image, src)

    def _process_and_add(self, image: np.ndarray, src: str):
        page = self._m.add_page(image, 300, src)
        logger.debug("Página añadida al modelo: index=%d, src=%s", page.index, src)
        self.page_added.emit(page)
