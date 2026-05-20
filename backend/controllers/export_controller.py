"""
ExportController — gestiona múltiples trabajos de exportación concurrentes.
Cada llamada a exportCivil/exportAnt crea un Job independiente que corre
en el ThreadPool sin bloquear los demás.
"""
from __future__ import annotations
import io, zipfile
from pathlib import Path
from typing import Optional
import numpy as np
from PIL import Image

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from backend.models.scan_model import ScanModel, PageData
from backend.models.job_model import Job, JobType, JobStatus, JobRegistry
from backend.models.config_model import ConfigModel
from backend.utils.file_utils import sanitize, serial_str, ts_name, unique


# ── Helpers de PDF/ZIP ────────────────────────────────────────────────────────

def _to_pil(img: np.ndarray) -> Image.Image:
    if img.ndim == 2: return Image.fromarray(img, "L")
    if img.shape[2] == 4: return Image.fromarray(img, "RGBA").convert("RGB")
    return Image.fromarray(img[:, :, ::-1])   # BGR→RGB

def _pages_to_pdf(images: list[np.ndarray], dpi: int) -> bytes:
    pils = [_to_pil(i) for i in images]
    buf  = io.BytesIO()
    pils[0].save(buf, format="PDF", resolution=dpi, save_all=True, append_images=pils[1:])
    return buf.getvalue()

def _build_zip(entries: dict[str, bytes], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


# ── Worker Civil ──────────────────────────────────────────────────────────────

class _CivilWorker(QRunnable):
    class S(QObject):
        progress = Signal(str, int, int)   # (job_id, current, total)
        done     = Signal(str, str)         # (job_id, output_path)
        error    = Signal(str, str)
    def __init__(self, job: Job, pages: list[PageData], zip_path: Path, dpi: int):
        super().__init__(); self.s = _CivilWorker.S()
        self.job, self.pages, self.zip_path, self.dpi = job, pages, zip_path, dpi

    def run(self):
        try:
            entries: dict[str, bytes] = {}
            used: dict[str, int] = {}
            for i, page in enumerate(self.pages):
                self.s.progress.emit(self.job.id, i+1, len(self.pages))
                base = sanitize(page.final_label)
                if base in used:
                    used[base] += 1; base = f"{base}_{used[base]}"
                else:
                    used[base] = 0
                entries[base + ".pdf"] = _pages_to_pdf([page.display_image], self.dpi)
            _build_zip(entries, self.zip_path)
            self.s.done.emit(self.job.id, str(self.zip_path))
        except Exception as e:
            self.s.error.emit(self.job.id, str(e))


# ── Worker Antecedentes ───────────────────────────────────────────────────────

class _AntWorker(QRunnable):
    class S(QObject):
        progress = Signal(str, int, int)
        done     = Signal(str, str)
        error    = Signal(str, str)
    def __init__(self, job: Job, groups: list[list[PageData]], zip_path: Path,
                 dpi: int, serial_ini: int, padding: int):
        super().__init__(); self.s = _AntWorker.S()
        self.job = job; self.groups = groups; self.zip_path = zip_path
        self.dpi = dpi; self.serial_ini = serial_ini; self.padding = padding

    def run(self):
        try:
            entries: dict[str, bytes] = {}
            for i, group in enumerate(self.groups):
                self.s.progress.emit(self.job.id, i+1, len(self.groups))
                name = serial_str(self.serial_ini + i, self.padding) + ".pdf"
                entries[name] = _pages_to_pdf([p.display_image for p in group], self.dpi)
            _build_zip(entries, self.zip_path)
            self.s.done.emit(self.job.id, str(self.zip_path))
        except Exception as e:
            self.s.error.emit(self.job.id, str(e))


# ── Controller ────────────────────────────────────────────────────────────────

class ExportController(QObject):
    """
    Signals
    -------
    jobCreated(str, str, str)          — (job_id, tipo, label)
    jobProgress(str, int, int)         — (job_id, current, total)
    jobDone(str, str)                  — (job_id, output_path)
    jobError(str, str)                 — (job_id, mensaje)
    """
    jobCreated  = Signal(str, str, str)
    jobProgress = Signal(str, int, int)
    jobDone     = Signal(str, str)
    jobError    = Signal(str, str)

    def __init__(self, scan_model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._m     = scan_model
        self._cfg   = config
        self._reg   = JobRegistry()
        self._pool  = QThreadPool.globalInstance()

    # ── API pública ───────────────────────────────────────────────────────────

    @Slot(str, str)
    def exportCivil(self, folder: str, label: str = ""):
        """Un PDF por página. Corre como nuevo Job independiente."""
        pages = list(self._m.pages)
        if not pages:
            return
        job = Job(job_type=JobType.CIVIL, label=label or f"Civil #{len(self._reg.all())+1}",
                  total=len(pages))
        self._reg.add(job)
        self.jobCreated.emit(job.id, "civil", job.label)

        zip_path = unique(Path(folder) / ts_name("registros_civiles"))
        dpi      = self._cfg.get("output", "pdf_dpi", 200)

        w = _CivilWorker(job, pages, zip_path, dpi)
        w.s.progress.connect(self._onProgress)
        w.s.done.connect(self._onDone)
        w.s.error.connect(self._onError)
        self._pool.start(w)

    @Slot(str, int, int, int, int, int)
    def exportAnt(self, folder: str, serial_ini: int, padding: int,
                  desde: int = 0, hasta: int = 0, label: str = ""):
        """Grupos de páginas separados por puntos de corte."""
        # filtrar rango
        pages = self._m.pages
        if hasta > 0:
            pages = [p for p in pages if desde <= p.index+1 <= hasta]
        elif desde > 1:
            pages = [p for p in pages if p.index+1 >= desde]

        groups = self._groups_from(pages)
        if not groups:
            return

        job = Job(job_type=JobType.ANTECEDENTES,
                  label=label or f"Antecedentes #{len(self._reg.all())+1}",
                  total=len(groups))
        self._reg.add(job)
        self.jobCreated.emit(job.id, "antecedentes", job.label)

        zip_path = unique(Path(folder) / ts_name("antecedentes"))
        dpi      = self._cfg.get("output", "pdf_dpi", 200)

        w = _AntWorker(job, groups, zip_path, dpi, serial_ini, padding)
        w.s.progress.connect(self._onProgress)
        w.s.done.connect(self._onDone)
        w.s.error.connect(self._onError)
        self._pool.start(w)

    @Slot(str)
    def removeJob(self, job_id: str):
        self._reg.remove(job_id)

    def allJobs(self) -> list[Job]:
        return self._reg.all()

    # ── Interno ───────────────────────────────────────────────────────────────

    @Slot(str, int, int)
    def _onProgress(self, job_id: str, cur: int, tot: int):
        job = self._reg.get(job_id)
        if job:
            job.current, job.status = cur, JobStatus.RUNNING
        self.jobProgress.emit(job_id, cur, tot)

    @Slot(str, str)
    def _onDone(self, job_id: str, path: str):
        job = self._reg.get(job_id)
        if job:
            job.status, job.output_path = JobStatus.DONE, path
        self.jobDone.emit(job_id, path)

    @Slot(str, str)
    def _onError(self, job_id: str, msg: str):
        job = self._reg.get(job_id)
        if job:
            job.status, job.error_msg = JobStatus.ERROR, msg
        self.jobError.emit(job_id, msg)

    @staticmethod
    def _groups_from(pages: list) -> list[list]:
        if not pages: return []
        groups, cur = [], []
        for p in pages:
            if p.is_cut_point and cur:
                groups.append(cur); cur = [p]
            else:
                cur.append(p)
        if cur: groups.append(cur)
        return groups
