"""ScanController — TWAIN + importación de archivos en segundo plano."""
from __future__ import annotations
import io
from pathlib import Path
from typing import Optional
import numpy as np
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from backend.models.scan_model import ScanModel
from backend.models.config_model import ConfigModel
from backend.utils.image_utils import correct_perspective, deskew, detect_corners
from backend.utils.file_utils import IMAGE_EXTS, PDF_EXT


# ── Workers ───────────────────────────────────────────────────────────────────

class _ScanWorker(QRunnable):
    class S(QObject):
        page   = Signal(np.ndarray, str)   # (imagen, fuente)
        done   = Signal()
        error  = Signal(str)
    def __init__(self, source: str, dpi: int, color: str):
        super().__init__(); self.s = _ScanWorker.S()
        self.source, self.dpi, self.color = source, dpi, color
        self._stop = False
    def cancel(self): self._stop = True

    def run(self):
        try:
            from io import BytesIO
            import twain
            from PIL import Image
            with twain.SourceManager(0) as sm:
                src = sm.open_source(self.source or None)
                if not src:
                    self.s.error.emit("No se pudo abrir el escáner."); return
                with src:
                    src.set_capability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(self.dpi))
                    src.set_capability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(self.dpi))
                    pt = {"color": twain.TWPT_RGB, "gray": twain.TWPT_GRAY, "bw": twain.TWPT_BW}.get(self.color, twain.TWPT_RGB)
                    src.set_capability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, pt)
                    src.request_acquire(show_ui=False, modal_ui=False)
                    while not self._stop:
                        try:
                            handle, remaining = src.xfer_image_natively()
                            bmp = twain.dib_to_bm_file(handle)
                            img = Image.open(BytesIO(bmp))
                            self.s.page.emit(np.array(img.convert("RGB")), "twain")
                            if remaining == 0: break
                        except twain.excDSTransferCancelled: break
        except ImportError:
            # Modo simulación
            import cv2
            img = np.ones((2200, 1700, 3), dtype=np.uint8) * 230
            cv2.putText(img, "PAGINA DE PRUEBA", (300, 1100), cv2.FONT_HERSHEY_SIMPLEX, 4, (80,80,80), 6)
            cv2.putText(img, "Serial: 12345678", (550, 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (50,50,50), 4)
            self.s.page.emit(img, "simulador")
        except Exception as e:
            self.s.error.emit(str(e))
        finally:
            self.s.done.emit()


class _ImportWorker(QRunnable):
    class S(QObject):
        page     = Signal(np.ndarray, str)
        progress = Signal(int, int)
        done     = Signal()
        error    = Signal(str)
    def __init__(self, paths: list[Path], pdf_dpi: int):
        super().__init__(); self.s = _ImportWorker.S()
        self.paths, self.pdf_dpi = paths, pdf_dpi
        self._stop = False
    def cancel(self): self._stop = True

    def run(self):
        try:
            tasks = []
            for p in self.paths:
                ext = p.suffix.lower()
                if ext in IMAGE_EXTS:
                    tasks.append((p, None))
                elif ext == PDF_EXT:
                    for i in range(self._pdf_count(p)):
                        tasks.append((p, i))
            total = len(tasks)
            for n, (path, pg) in enumerate(tasks):
                if self._stop: break
                try:
                    img = self._load_pdf(path, pg) if pg is not None else self._load_img(path)
                    if img is not None:
                        self.s.progress.emit(n+1, total)
                        self.s.page.emit(img, str(path))
                except Exception as e:
                    self.s.error.emit(f"{path.name}: {e}")
        except Exception as e:
            self.s.error.emit(str(e))
        finally:
            self.s.done.emit()

    def _load_img(self, path: Path):
        import cv2
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            from PIL import Image as PILImage
            img = np.array(PILImage.open(path).convert("RGB"))[:,:,::-1]
        return img

    def _load_pdf(self, path: Path, pg: int):
        try:
            import fitz
            doc = fitz.open(str(path))
            pix = doc[pg].get_pixmap(matrix=fitz.Matrix(self.pdf_dpi/72, self.pdf_dpi/72), colorspace=fitz.csRGB)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
            doc.close()
            return img[:,:,::-1]
        except ImportError: pass
        try:
            from pdf2image import convert_from_path
            imgs = convert_from_path(str(path), dpi=self.pdf_dpi, first_page=pg+1, last_page=pg+1)
            return np.array(imgs[0].convert("RGB"))[:,:,::-1] if imgs else None
        except ImportError: pass
        raise RuntimeError("Instala pymupdf o pdf2image para importar PDFs")

    def _pdf_count(self, path: Path) -> int:
        try:
            import fitz; doc = fitz.open(str(path)); n = len(doc); doc.close(); return n
        except ImportError: pass
        try:
            from pypdf import PdfReader; return len(PdfReader(str(path)).pages)
        except: return 1


# ── Controller ────────────────────────────────────────────────────────────────

class ScanController(QObject):
    pageAdded    = Signal(object)   # PageData
    scanDone     = Signal()
    importDone   = Signal()
    importProgress = Signal(int, int)
    sourcesLoaded  = Signal(list)
    error          = Signal(str)
    correctionDone = Signal(int)

    def __init__(self, model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._m, self._cfg = model, config
        self._pool = QThreadPool.globalInstance()
        self._scan_w: Optional[_ScanWorker] = None
        self._imp_w:  Optional[_ImportWorker] = None

    # ── TWAIN ─────────────────────────────────────────────────────────────────

    @Slot()
    def loadSources(self):
        try:
            import twain
            with twain.SourceManager(0) as sm:
                srcs = sm.source_list
            self.sourcesLoaded.emit(srcs or ["[Sin escáneres]"])
        except ImportError:
            self.sourcesLoaded.emit(["[Simulador]"])
        except Exception as e:
            self.sourcesLoaded.emit(["[Error]"]); self.error.emit(str(e))

    @Slot()
    def startScan(self):
        cfg = self._cfg
        w = _ScanWorker(cfg.get("scanner","source",""), cfg.get("scanner","dpi",300), cfg.get("scanner","color_mode","color"))
        w.s.page.connect(self._onPage)
        w.s.done.connect(self.scanDone)
        w.s.error.connect(self.error)
        self._scan_w = w
        self._pool.start(w)

    @Slot()
    def cancelScan(self):
        if self._scan_w: self._scan_w.cancel()

    # ── Importación ───────────────────────────────────────────────────────────

    @Slot(list)
    def importFiles(self, paths: list):
        pp = [Path(p) for p in paths]
        w = _ImportWorker(pp, self._cfg.get("output","pdf_dpi",200))
        w.s.page.connect(self._onPage)
        w.s.progress.connect(self.importProgress)
        w.s.done.connect(self.importDone)
        w.s.error.connect(self.error)
        self._imp_w = w
        self._pool.start(w)

    @Slot()
    def cancelImport(self):
        if self._imp_w: self._imp_w.cancel()

    # ── Corrección ────────────────────────────────────────────────────────────

    @Slot(int)
    def autoCorrect(self, index: int):
        page = self._m.get(index)
        if not page: return
        img = page.original_image.copy()
        corners = detect_corners(img)
        if corners is not None:
            img = correct_perspective(img, corners)
        img, angle = deskew(img)
        self._m.set_corrected(index, img, angle)
        self.correctionDone.emit(index)

    @Slot(int, float)
    def rotateManual(self, index: int, angle: float):
        page = self._m.get(index)
        if not page: return
        img, a = deskew(page.original_image.copy(), angle)
        self._m.set_corrected(index, img, a)
        self.correctionDone.emit(index)

    @Slot(int)
    def resetCorrection(self, index: int):
        self._m.set_corrected(index, None, 0.0)
        self.correctionDone.emit(index)

    @Slot(int)
    def deletePage(self, index: int):
        self._m.remove_page(index)

    # ── Interno ───────────────────────────────────────────────────────────────

    @Slot(np.ndarray, str)
    def _onPage(self, image: np.ndarray, src: str):
        result = image.copy()
        if self._cfg.get("correction","auto_perspective",True):
            corners = detect_corners(result)
            if corners is not None:
                result = correct_perspective(result, corners)
        if self._cfg.get("correction","auto_rotation",True):
            result, angle = deskew(result)
        else:
            angle = 0.0
        page = self._m.add_page(image, self._cfg.get("scanner","dpi",300), src)
        self._m.set_corrected(page.index, result, angle)
        self.pageAdded.emit(page)
