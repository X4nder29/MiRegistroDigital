"""
Bridge — único QObject expuesto a QML.
QML llama métodos en este objeto; este reenvía a los controllers
y emite señales que QML escucha.
"""
from __future__ import annotations
import base64
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl

from backend.models.scan_model import ScanModel
from backend.models.config_model import ConfigModel
from backend.models.job_model import JobType
from backend.controllers.scan_controller import ScanController
from backend.controllers.ocr_controller import OCRController
from backend.controllers.export_controller import ExportController
from backend.utils.image_utils import ndarray_to_bytes


class Bridge(QObject):
    # ── Señales hacia QML ─────────────────────────────────────────────────────
    pageAdded       = Signal(int, str, str)    # (index, base64_thumb, source_path)
    pageUpdated     = Signal(int, str)          # (index, base64_thumb)
    pageDeleted     = Signal(int)
    scanDone        = Signal()
    importDone      = Signal()
    importProgress  = Signal(int, int)
    sourcesLoaded   = Signal(list)

    ocrResult       = Signal(int, str, float)  # (index, serial, conf)
    ocrAllDone      = Signal()
    ocrError        = Signal(int, str)

    jobCreated      = Signal(str, str, str)    # (id, tipo, label)
    jobProgress     = Signal(str, int, int)
    jobDone         = Signal(str, str)          # (id, output_path)
    jobError        = Signal(str, str)

    appError        = Signal(str)
    cutPointChanged = Signal(int, bool)         # (index, is_cut)

    # ── Init ──────────────────────────────────────────────────────────────────
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model   = ScanModel()
        self._config  = ConfigModel()
        self._scan    = ScanController(self._model, self._config, self)
        self._ocr     = OCRController(self._model, self._config, self)
        self._export  = ExportController(self._model, self._config, self)

        # Conectar controllers → bridge
        self._scan.pageAdded.connect(self._onPageAdded)
        self._scan.scanDone.connect(self.scanDone)
        self._scan.importDone.connect(self.importDone)
        self._scan.importProgress.connect(self.importProgress)
        self._scan.sourcesLoaded.connect(self.sourcesLoaded)
        self._scan.error.connect(self.appError)
        self._scan.correctionDone.connect(self._onCorrectionDone)

        self._ocr.ocrResult.connect(self._onOcrResult)
        self._ocr.ocrAllDone.connect(self.ocrAllDone)
        self._ocr.ocrError.connect(self.ocrError)

        self._export.jobCreated.connect(self.jobCreated)
        self._export.jobProgress.connect(self.jobProgress)
        self._export.jobDone.connect(self.jobDone)
        self._export.jobError.connect(self.jobError)

    # ── Propiedades QML ───────────────────────────────────────────────────────

    @Property(int, constant=False, notify=scanDone)
    def pageCount(self) -> int:
        return self._model.count

    # ── Escáner / Importación ─────────────────────────────────────────────────

    @Slot()
    def loadSources(self):
        self._scan.loadSources()

    @Slot(str, int, str)
    def startScan(self, source: str, dpi: int, color: str):
        self._config.set("scanner","source",source)
        self._config.set("scanner","dpi",dpi)
        self._config.set("scanner","color_mode",color)
        self._scan.startScan()

    @Slot()
    def cancelScan(self):
        self._scan.cancelScan()

    @Slot(list)
    def importFiles(self, paths: list):
        """paths: lista de strings (file:// URLs o rutas absolutas)."""
        clean = [_url_to_path(p) for p in paths]
        self._scan.importFiles(clean)

    @Slot()
    def cancelImport(self):
        self._scan.cancelImport()

    # ── Páginas ───────────────────────────────────────────────────────────────

    @Slot(int)
    def deletePage(self, index: int):
        self._scan.deletePage(index)
        self.pageDeleted.emit(index)

    @Slot(int, result=str)
    def getPageImageB64(self, index: int) -> str:
        """Devuelve imagen completa en base64 JPEG (para visor pantalla completa)."""
        page = self._model.get(index)
        if not page: return ""
        return _to_b64(page.display_image, quality=92)

    @Slot(int)
    def autoCorrect(self, index: int):
        self._scan.autoCorrect(index)

    @Slot(int, float)
    def rotateManual(self, index: int, angle: float):
        self._scan.rotateManual(index, angle)

    @Slot(int)
    def resetCorrection(self, index: int):
        self._scan.resetCorrection(index)

    # ── Puntos de corte ───────────────────────────────────────────────────────

    @Slot(int)
    def toggleCut(self, index: int):
        is_cut = self._model.toggle_cut(index)
        self.cutPointChanged.emit(index, is_cut)

    @Slot(list)
    def setCuts(self, indices: list):
        self._model.set_cuts(set(int(i) for i in indices))

    @Slot()
    def clearCuts(self):
        self._model.set_cuts(set())

    @Slot(result=list)
    def getGroupsPreview(self) -> list:
        """Devuelve lista de listas de índices de páginas por grupo."""
        return [[p.index for p in g] for g in self._model.get_groups()]

    # ── OCR ───────────────────────────────────────────────────────────────────

    @Slot(int)
    def runOcrPage(self, index: int):
        self._ocr.runPage(index)

    @Slot()
    def runOcrAll(self):
        self._ocr.runAll()

    @Slot(int, str)
    def overrideSerial(self, index: int, serial: str):
        self._ocr.override(index, serial)

    # ── Exportación ───────────────────────────────────────────────────────────

    @Slot(str, str)
    def exportCivil(self, folder: str, label: str = ""):
        self._export.exportCivil(_url_to_path(folder), label)

    @Slot(str, int, int, int, int, str)
    def exportAnt(self, folder: str, serialIni: int, padding: int,
                  desde: int, hasta: int, label: str):
        self._export.exportAnt(_url_to_path(folder), serialIni, padding, desde, hasta, label)

    @Slot(str)
    def removeJob(self, job_id: str):
        self._export.removeJob(job_id)

    @Slot(result=list)
    def getJobs(self) -> list:
        return [
            {"id": j.id, "type": j.job_type.value, "label": j.label,
             "status": j.status.value, "current": j.current, "total": j.total,
             "output": j.output_path, "error": j.error_msg}
            for j in self._export.allJobs()
        ]

    # ── Config ────────────────────────────────────────────────────────────────

    @Slot(str, str, result="QVariant")
    def cfgGet(self, section: str, key: str):
        return self._config.get(section, key)

    @Slot(str, str, "QVariant")
    def cfgSet(self, section: str, key: str, value):
        self._config.set(section, key, value)

    @Slot()
    def cfgSave(self):
        self._config.save()

    # ── Internos ──────────────────────────────────────────────────────────────

    def _onPageAdded(self, page):
        thumb = _to_b64(page.display_image, size=(160, 220))
        self.pageAdded.emit(page.index, thumb, page.source_path)

    def _onCorrectionDone(self, index: int):
        page = self._model.get(index)
        if not page: return
        thumb = _to_b64(page.display_image, size=(160, 220))
        self.pageUpdated.emit(index, thumb)

    def _onOcrResult(self, index: int, serial: str, conf: float):
        page = self._model.get(index)
        if page and serial:
            page.serial = serial
            page.serial_confidence = conf
        self.ocrResult.emit(index, serial, conf)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_b64(image: np.ndarray, size: Optional[tuple] = None, quality: int = 82) -> str:
    if size:
        image = _fit(image, size)
    data = ndarray_to_bytes(image, ".jpg", quality)
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()

def _fit(image: np.ndarray, size: tuple) -> np.ndarray:
    h, w = image.shape[:2]
    tw, th = size
    scale = min(tw/w, th/h)
    nw, nh = max(1, int(w*scale)), max(1, int(h*scale))
    return cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)

def _url_to_path(s: str) -> str:
    if s.startswith("file:///"):
        return s[8:]
    if s.startswith("file://"):
        return s[7:]
    return s
