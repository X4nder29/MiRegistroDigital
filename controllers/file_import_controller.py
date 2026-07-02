"""
FileImportController — Importa archivos ya escaneados (imágenes y PDFs) al modelo.

Soporta:
  - Imágenes individuales: JPG, JPEG, PNG, TIFF, TIF, BMP, WEBP
  - PDFs multipágina: cada página se convierte en imagen

Emite las mismas señales que ScanController para que MainWindow las maneje
de forma transparente con el mismo slot _on_page_added.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel, PageData
from models.config_model import ConfigModel
from utils.image_utils import correct_perspective, deskew, detect_document_corners


# ── Formatos soportados ───────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
PDF_EXTENSION = ".pdf"


# ── Worker ────────────────────────────────────────────────────────────────────

class ImportWorker(QRunnable):
    """
    Carga una lista de rutas (imágenes y/o PDFs) y emite cada página como ndarray.
    El orden de emisión sigue el orden de la lista de rutas.
    """

    class Signals(QObject):
        page_ready = Signal(np.ndarray, str)   # (imagen, ruta_origen)
        progress = Signal(int, int)             # (páginas_emitidas, total_estimado)
        finished = Signal()
        error = Signal(str)

    def __init__(
        self,
        paths: list[Path],
        pdf_dpi: int = 200,
        auto_perspective: bool = True,
        auto_rotation: bool = True,
    ):
        super().__init__()
        self.signals = ImportWorker.Signals()
        self.paths = paths
        self.pdf_dpi = pdf_dpi
        self.auto_perspective = auto_perspective
        self.auto_rotation = auto_rotation
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @Slot()
    def run(self):
        try:
            # Expandir PDFs para estimar el total antes de emitir
            tasks: list[tuple[str, int | None]] = []   # (ruta_str, página_pdf | None)
            for path in self.paths:
                ext = path.suffix.lower()
                if ext == PDF_EXTENSION:
                    count = self._pdf_page_count(path)
                    for i in range(count):
                        tasks.append((str(path), i))
                elif ext in IMAGE_EXTENSIONS:
                    tasks.append((str(path), None))

            total = len(tasks)
            emitted = 0

            for path_str, pdf_page in tasks:
                if self._cancelled:
                    break

                try:
                    if pdf_page is not None:
                        img = self._load_pdf_page(Path(path_str), pdf_page)
                    else:
                        img = self._load_image(Path(path_str))

                    if img is not None:
                        emitted += 1
                        self.signals.progress.emit(emitted, total)
                        self.signals.page_ready.emit(img, path_str)

                except Exception as exc:
                    self.signals.error.emit(f"Error cargando {path_str}: {exc}")

        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()

    # ── Carga de imágenes ─────────────────────────────────────────────────────

    def _load_image(self, path: Path) -> Optional[np.ndarray]:
        import cv2
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            # Fallback con Pillow (mejor soporte de TIFF/WEBP)
            from PIL import Image
            pil = Image.open(path).convert("RGB")
            import numpy as np
            img = np.array(pil)[:, :, ::-1]  # RGB → BGR para OpenCV
        return img

    # ── Carga de PDF ──────────────────────────────────────────────────────────

    def _load_pdf_page(self, path: Path, page_index: int) -> Optional[np.ndarray]:
        """Rasteriza una página de PDF a ndarray usando pypdf + Pillow."""
        try:
            # Intentar con pdf2image si está disponible (mejor calidad)
            from pdf2image import convert_from_path
            images = convert_from_path(
                str(path),
                dpi=self.pdf_dpi,
                first_page=page_index + 1,
                last_page=page_index + 1,
            )
            if images:
                import numpy as np
                return np.array(images[0].convert("RGB"))[:, :, ::-1]
        except ImportError:
            pass

        # Fallback: pypdf (solo texto/metadatos) → usar pymupdf si disponible
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(path))
            page = doc[page_index]
            mat = fitz.Matrix(self.pdf_dpi / 72, self.pdf_dpi / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            import numpy as np
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, 3
            )
            doc.close()
            return img[:, :, ::-1].copy()  # RGB → BGR
        except ImportError:
            pass

        raise RuntimeError(
            "Para importar PDFs instala una de estas librerías:\n"
            "  pip install pdf2image\n"
            "  pip install pymupdf\n"
            "(pdf2image también requiere poppler en el PATH)"
        )

    def _pdf_page_count(self, path: Path) -> int:
        """Cuenta las páginas de un PDF sin rasterizar."""
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


# ── Controller ────────────────────────────────────────────────────────────────

class FileImportController(QObject):
    """
    Signals  (misma interfaz que ScanController para compatibilidad)
    -------
    page_added(PageData)      — página cargada y lista
    import_finished()         — todas las páginas cargadas
    import_error(str)         — error durante la carga
    import_progress(int, int) — (cargadas, total)
    correction_done(int)      — corrección aplicada (reusado por MainWindow)
    """

    page_added        = Signal(object)   # PageData
    import_finished   = Signal()
    import_error      = Signal(str)
    import_progress   = Signal(int, int)
    correction_done   = Signal(int)

    def __init__(self, scan_model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._model  = scan_model
        self._config = config
        self._pool   = QThreadPool.globalInstance()
        self._worker: Optional[ImportWorker] = None

    # ── API pública ───────────────────────────────────────────────────────────

    def import_files(self, paths: list[Path]):
        """
        Inicia la importación de una lista de rutas.
        Las rutas pueden ser imágenes sueltas o PDFs (o mezcla de ambos).
        """
        if not paths:
            return

        worker = ImportWorker(
            paths=paths,
            pdf_dpi=self._config.get("output", "pdf_dpi", 200),
            auto_perspective=self._config.get("correction", "auto_perspective", True),
            auto_rotation=self._config.get("correction", "auto_rotation", True),
        )
        worker.signals.page_ready.connect(self._on_page_ready)
        worker.signals.progress.connect(self.import_progress)
        worker.signals.finished.connect(self.import_finished)
        worker.signals.error.connect(self.import_error)
        self._worker = worker
        self._pool.start(worker)

    def cancel(self):
        if self._worker:
            self._worker.cancel()

    @staticmethod
    def split_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
        """Divide una lista en (imágenes, pdfs)."""
        imgs = [p for p in paths if p.suffix.lower() in IMAGE_EXTENSIONS]
        pdfs = [p for p in paths if p.suffix.lower() == PDF_EXTENSION]
        return imgs, pdfs

    # ── Interno ───────────────────────────────────────────────────────────────

    @Slot(np.ndarray, str)
    def _on_page_ready(self, image: np.ndarray, source_path: str):
        """Aplica correcciones y agrega la página al modelo."""
        corrected, angle = self._apply_corrections(image)
        page = self._model.add_page(image, dpi=self._config.get("scanner", "dpi", 300))
        page.user_label = None  # Sin serial aún
        self._model.set_corrected(page.index, corrected, angle)
        self.page_added.emit(page)

    def _apply_corrections(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        result = image.copy()
        angle = 0.0
        if self._config.get("correction", "auto_perspective", True):
            corners = detect_document_corners(result)
            if corners is not None:
                result = correct_perspective(result, corners)
        if self._config.get("correction", "auto_rotation", True):
            result, angle = deskew(result)
        return result, angle
