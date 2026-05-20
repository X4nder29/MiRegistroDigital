"""OCRController — EasyOCR en hilos secundarios."""
from __future__ import annotations
import logging
import re
import threading
import numpy as np
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel
from models.config_model import ConfigModel
from utils.image_utils import crop_right_margin, crop_to_area, enhance_for_ocr

logger = logging.getLogger("docscan.ocr")

SERIAL_RE = re.compile(r"\b\d{8}\b")

try:
    import easyocr
    _HAS_EASYOCR = True
except ImportError:
    _HAS_EASYOCR = False
    logger.warning("easyocr no instalado — usando simulación")


class _OCRWorkerSignals(QObject):
    result = Signal(int, str, float)
    error  = Signal(int, str)


class _OCRWorker(QRunnable):
    _instances: list[_OCRWorker] = []
    _cancel_all = False
    _reader = None
    _reader_lock = threading.Lock()
    _reader_langs: list[str] | None = None
    _reader_gpu: bool | None = None

    @classmethod
    def cancel_all_instances(cls):
        logger.info("Cancelando todos los workers OCR (%d instancias)", len(cls._instances))
        cls._cancel_all = True

    @classmethod
    def reset_reader(cls):
        cls._reader = None

    @classmethod
    def clear_instances(cls):
        cls._instances.clear()

    @classmethod
    def _get_reader(cls, langs: list[str], gpu: bool):
        if (cls._reader is None or cls._reader_langs != langs or cls._reader_gpu != gpu):
            with cls._reader_lock:
                if (cls._reader is None or cls._reader_langs != langs or cls._reader_gpu != gpu):
                    logger.info("Creando nuevo reader EasyOCR (langs=%s gpu=%s)", langs, gpu)
                    cls._reader = easyocr.Reader(langs, gpu=gpu, verbose=False)
                    cls._reader_langs = langs
                    cls._reader_gpu = gpu
                    logger.info("Reader EasyOCR creado")
        return cls._reader

    def __init__(self, index: int, image: np.ndarray,
                 langs: list, pct: float, gpu: bool,
                 ocr_area: tuple[float, float, float, float] | None = None):
        super().__init__()
        self.s = _OCRWorkerSignals()
        self.index, self.image = index, image
        self.langs, self.pct, self.gpu = langs, pct, gpu
        self.ocr_area = ocr_area
        self._stopped = False
        _OCRWorker._instances.append(self)
        logger.debug("Worker creado para página %d", index)

    def run(self):
        logger.debug("Worker %d: iniciando", self.index)
        try:
            if self._cancel_all:
                logger.debug("Worker %d: cancelado al inicio", self.index)
                return
            if self.ocr_area:
                region = crop_to_area(self.image, self.ocr_area)
                logger.debug("Worker %d: crop_to_area aplicado", self.index)
            else:
                region = crop_right_margin(self.image, self.pct)
            if self._cancel_all:
                logger.debug("Worker %d: cancelado tras crop", self.index)
                return
            enhanced = enhance_for_ocr(region)
            if self._cancel_all:
                logger.debug("Worker %d: cancelado tras enhance", self.index)
                return
            if not _HAS_EASYOCR:
                logger.debug("Worker %d: simulación (sin easyocr)", self.index)
                self.s.result.emit(self.index, "12345678", 0.99)
                return
            reader = self._get_reader(self.langs, self.gpu)
            if self._cancel_all:
                logger.debug("Worker %d: cancelado tras reader", self.index)
                return
            raw = reader.readtext(
                enhanced,
                allowlist='0123456789',
                min_size=5,
            )
            text = " ".join(t for _, t, _ in raw)
            confs = [c for _, _, c in raw]
            conf = sum(confs) / len(confs) if confs else 0.0
            result = ""
            if text.strip():
                m = SERIAL_RE.search(text)
                if m:
                    result = m.group()
                else:
                    digits = "".join(ch for ch in text if ch.isdigit())
                    if digits:
                        result = digits[:20]
            logger.debug("Worker %d: resultado serial=%s conf=%.2f", self.index, result, conf)
            self.s.result.emit(self.index, result, conf)
        except ImportError:
            logger.warning("Worker %d: easyocr no disponible — simulación", self.index)
            self.s.result.emit(self.index, "12345678", 0.99)
        except Exception as e:
            logger.error("Worker %d: error %s", self.index, e, exc_info=True)
            self.s.error.emit(self.index, str(e))
        finally:
            try:
                _OCRWorker._instances.remove(self)
            except ValueError:
                pass


class OCRController(QObject):
    ocr_result  = Signal(int, str, float)   # (page_index, serial, confidence)
    ocr_all_done = Signal()
    ocr_error   = Signal(int, str)

    def __init__(self, model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._m    = model
        self._cfg  = config
        self._pool = QThreadPool.globalInstance()
        n = config.get("ocr", "parallel_workers", 4)
        self._pool.setMaxThreadCount(n)
        self._pending = 0
        logger.info("OCRController iniciado, max threads=%d, easyocr=%s", n, _HAS_EASYOCR)

    @Slot(int)
    def run_page(self, index: int):
        logger.info("run_page %d solicitado", index)
        _OCRWorker._cancel_all = False
        page = self._m.get(index)
        if not page:
            logger.warning("run_page %d: página no encontrada", index)
            return
        self._submit(index, page.display_image)

    @Slot()
    def run_all(self):
        logger.info("run_all solicitado")
        _OCRWorker._cancel_all = False
        pages = [p for p in self._m.pages if not p.serial]
        if not pages:
            logger.info("run_all: sin páginas pendientes")
            self.ocr_all_done.emit()
            return
        self._pending = len(pages)
        logger.info("run_all: %d páginas pendientes", self._pending)
        for p in pages:
            self._submit(p.index, p.display_image)

    @Slot()
    def set_parallel_workers(self, n: int):
        logger.info("set_parallel_workers %d", n)
        self._pool.setMaxThreadCount(n)

    def cancel_all(self):
        logger.info("cancel_all solicitado (pending=%d)", self._pending)
        _OCRWorker.cancel_all_instances()
        self._pending = 0

    @Slot(int, str)
    def override(self, index: int, serial: str):
        logger.info("override página %d -> %s", index, serial)
        self._m.set_serial(index, serial, 1.0)
        self.ocr_result.emit(index, serial, 1.0)

    def _submit(self, index: int, image: np.ndarray):
        page = self._m.get(index)
        ocr_area = page.ocr_area if page else None
        w = _OCRWorker(index, image,
                       self._cfg.get("ocr", "languages", ["es", "en"]),
                       self._cfg.get("ocr", "margin_right_pct", 0.15),
                       self._cfg.get("ocr", "gpu", False),
                       ocr_area=ocr_area)
        w.s.result.connect(self._on_result)
        w.s.error.connect(self._on_error)
        self._pool.start(w)
        logger.debug("Worker %d enviado al pool", index)

    @Slot(int, str, float)
    def _on_result(self, index: int, serial: str, conf: float):
        logger.debug("_on_result página %d serial=%s conf=%.2f", index, serial, conf)
        if serial:
            self._m.set_serial(index, serial, conf)
        self.ocr_result.emit(index, serial, conf)
        self._dec()

    @Slot(int, str)
    def _on_error(self, index: int, msg: str):
        logger.warning("_on_error página %d: %s", index, msg)
        self.ocr_error.emit(index, msg)
        self._dec()

    def _dec(self):
        if self._pending <= 0:
            logger.warning("_dec: pending ya era %d (llamado de más)", self._pending)
            return
        self._pending -= 1
        logger.debug("_dec: pending=%d", self._pending)
        if self._pending == 0:
            logger.info("OCR completado — todas las páginas procesadas")
            self.ocr_all_done.emit()
