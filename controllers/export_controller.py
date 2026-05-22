"""ExportController — múltiples trabajos de exportación concurrentes."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel, PageData
from models.job_model import Job, JobType, JobStatus
from models.config_model import ConfigModel
from utils.file_utils import (sanitize, serial_str, ts_name, unique,
                                images_to_pdf_bytes, build_zip)

logger = logging.getLogger("docscan.export")


class _CivilWorker(QRunnable):
    class S(QObject):
        progress  = Signal(str, int, int)
        done      = Signal(str, str)
        error     = Signal(str, str)
        cancelled = Signal(str)

    def __init__(self, job: Job, pages: list[PageData], zip_path: Path, dpi: int):
        super().__init__()
        self.s = _CivilWorker.S()
        self.job, self.pages, self.zip_path, self.dpi = job, pages, zip_path, dpi
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            entries: dict[str, bytes] = {}
            used: dict[str, int] = {}
            for i, page in enumerate(self.pages):
                if self._cancel:
                    self.s.cancelled.emit(self.job.id)
                    return
                self.s.progress.emit(self.job.id, i + 1, len(self.pages))
                base = sanitize(page.final_label)
                if base in used:
                    used[base] += 1
                    base = f"{base}_{used[base]}"
                else:
                    used[base] = 0
                entries[base + ".pdf"] = images_to_pdf_bytes([page.display_image], self.dpi)
            build_zip(entries, self.zip_path)
            self.s.done.emit(self.job.id, str(self.zip_path))
        except Exception as e:
            self.s.error.emit(self.job.id, str(e))


class _AntWorker(QRunnable):
    class S(QObject):
        progress  = Signal(str, int, int)
        done      = Signal(str, str)
        error     = Signal(str, str)
        cancelled = Signal(str)

    def __init__(self, job: Job, groups: list[list[PageData]],
                 zip_path: Path, dpi: int, serial_ini: int, padding: int):
        super().__init__()
        self.s = _AntWorker.S()
        self.job = job
        self.groups, self.zip_path = groups, zip_path
        self.dpi, self.serial_ini, self.padding = dpi, serial_ini, padding
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            entries: dict[str, bytes] = {}
            for i, group in enumerate(self.groups):
                if self._cancel:
                    self.s.cancelled.emit(self.job.id)
                    return
                self.s.progress.emit(self.job.id, i + 1, len(self.groups))
                name = serial_str(self.serial_ini + i, self.padding) + ".pdf"
                entries[name] = images_to_pdf_bytes(
                    [p.display_image for p in group], self.dpi)
            build_zip(entries, self.zip_path)
            self.s.done.emit(self.job.id, str(self.zip_path))
        except Exception as e:
            self.s.error.emit(self.job.id, str(e))


class _BookmarkWorker(QRunnable):
    class S(QObject):
        progress  = Signal(str, int, int)
        done      = Signal(str, str)
        error     = Signal(str, str)
        cancelled = Signal(str)

    def __init__(self, job: Job, pages: list[PageData], zip_path: Path, dpi: int):
        super().__init__()
        self.s = _BookmarkWorker.S()
        self.job, self.pages, self.zip_path, self.dpi = job, pages, zip_path, dpi
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            entries: dict[str, bytes] = {}
            used: dict[str, int] = {}
            for i, page in enumerate(self.pages):
                if self._cancel:
                    self.s.cancelled.emit(self.job.id)
                    return
                self.s.progress.emit(self.job.id, i + 1, len(self.pages))
                base = sanitize(page.bookmark or page.final_label)
                if base in used:
                    used[base] += 1
                    base = f"{base}_{used[base]}"
                else:
                    used[base] = 0
                entries[base + ".pdf"] = images_to_pdf_bytes([page.display_image], self.dpi)
            build_zip(entries, self.zip_path)
            self.s.done.emit(self.job.id, str(self.zip_path))
        except Exception as e:
            self.s.error.emit(self.job.id, str(e))


class _AntBookmarkWorker(QRunnable):
    class S(QObject):
        progress  = Signal(str, int, int)
        done      = Signal(str, str)
        error     = Signal(str, str)
        cancelled = Signal(str)

    def __init__(self, job: Job, groups: list[list[PageData]],
                 zip_path: Path, dpi: int, use_bookmark: bool):
        super().__init__()
        self.s = _AntBookmarkWorker.S()
        self.job = job
        self.groups, self.zip_path = groups, zip_path
        self.dpi, self.use_bookmark = dpi, use_bookmark
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            entries: dict[str, bytes] = {}
            used: dict[str, int] = {}
            for i, group in enumerate(self.groups):
                if self._cancel:
                    self.s.cancelled.emit(self.job.id)
                    return
                self.s.progress.emit(self.job.id, i + 1, len(self.groups))
                if self.use_bookmark:
                    base = sanitize(group[0].bookmark or f"grupo_{i+1:04d}")
                else:
                    base = f"grupo_{i+1:04d}"
                if base in used:
                    used[base] += 1
                    base = f"{base}_{used[base]}"
                else:
                    used[base] = 0
                entries[base + ".pdf"] = images_to_pdf_bytes(
                    [p.display_image for p in group], self.dpi)
            build_zip(entries, self.zip_path)
            self.s.done.emit(self.job.id, str(self.zip_path))
        except Exception as e:
            self.s.error.emit(self.job.id, str(e))


class ExportController(QObject):
    job_created   = Signal(object)        # Job
    job_progress  = Signal(str, int, int) # (id, current, total)
    job_done      = Signal(str, str)      # (id, output_path)
    job_error     = Signal(str, str)      # (id, msg)
    job_cancelled = Signal(str)           # (id)

    def __init__(self, model: ScanModel, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._m       = model
        self._cfg     = config
        self._pool    = QThreadPool.globalInstance()
        self._jobs:    dict[str, Job]     = {}
        self._workers: dict[str, object]  = {}

    def export_civil(self, folder: str, label: str = "") -> str:
        """Lanza exportación civil. Retorna job_id."""
        pages = list(self._m.pages)
        if not pages:
            return ""
        job = Job(job_type=JobType.CIVIL,
                  label=label or f"Registros Civiles #{len(self._jobs) + 1}",
                  total=len(pages))
        self._jobs[job.id] = job
        self.job_created.emit(job)

        zip_path = unique(Path(folder) / ts_name("registros_civiles"))
        dpi = self._cfg.get("output", "pdf_dpi", 200)
        w = _CivilWorker(job, pages, zip_path, dpi)
        w.s.progress.connect(self._on_progress)
        w.s.done.connect(self._on_done)
        w.s.error.connect(self._on_error)
        w.s.cancelled.connect(self._on_cancelled)
        self._workers[job.id] = w
        self._pool.start(w)
        return job.id

    def export_ant(self, folder: str, serial_ini: int, padding: int,
                   desde: int = 0, hasta: int = 0, label: str = "") -> str:
        """Lanza exportación de antecedentes. Retorna job_id."""
        pages = self._m.pages
        if hasta > 0:
            pages = [p for p in pages if desde <= p.index + 1 <= hasta]
        elif desde > 1:
            pages = [p for p in pages if p.index + 1 >= desde]

        groups = self._build_groups(list(pages))
        if not groups:
            return ""

        job = Job(job_type=JobType.ANTECEDENTES,
                  label=label or f"Antecedentes #{len(self._jobs) + 1}",
                  total=len(groups))
        self._jobs[job.id] = job
        self.job_created.emit(job)

        zip_path = unique(Path(folder) / ts_name("antecedentes"))
        dpi = self._cfg.get("output", "pdf_dpi", 200)
        w = _AntWorker(job, groups, zip_path, dpi, serial_ini, padding)
        w.s.progress.connect(self._on_progress)
        w.s.done.connect(self._on_done)
        w.s.error.connect(self._on_error)
        w.s.cancelled.connect(self._on_cancelled)
        self._workers[job.id] = w
        self._pool.start(w)
        return job.id

    def export_civil_bookmark(self, folder: str, label: str = "") -> str:
        """Un PDF por página, filename = bookmark. Retorna job_id."""
        pages = list(self._m.pages)
        if not pages:
            return ""
        job = Job(job_type=JobType.CIVIL,
                  label=label or f"Registros por marcador #{len(self._jobs) + 1}",
                  total=len(pages))
        self._jobs[job.id] = job
        self.job_created.emit(job)

        zip_path = unique(Path(folder) / ts_name("registros_marcadores"))
        dpi = self._cfg.get("output", "pdf_dpi", 200)
        w = _BookmarkWorker(job, pages, zip_path, dpi)
        w.s.progress.connect(self._on_progress)
        w.s.done.connect(self._on_done)
        w.s.error.connect(self._on_error)
        w.s.cancelled.connect(self._on_cancelled)
        self._workers[job.id] = w
        self._pool.start(w)
        return job.id

    def export_ant_single_pdf(self, folder: str, serial_ini: int, padding: int,
                               desde: int = 0, hasta: int = 0, label: str = "") -> str:
        """Un solo PDF con todas las páginas y marcadores como bookmarks PDF. Retorna job_id."""
        pages = self._m.pages
        if hasta > 0:
            pages = [p for p in pages if desde <= p.index + 1 <= hasta]
        elif desde > 1:
            pages = [p for p in pages if p.index + 1 >= desde]
        if not pages:
            return ""

        job = Job(job_type=JobType.ANTECEDENTES,
                  label=label or f"Antecedentes PDF único #{len(self._jobs) + 1}",
                  total=len(pages))
        self._jobs[job.id] = job
        self.job_created.emit(job)

        pdf_path = unique(Path(folder) / "antecedentes_unico.pdf")
        dpi = self._cfg.get("output", "pdf_dpi", 200)

        class _Worker(QRunnable):
            class S(QObject):
                progress = Signal(str, int, int)
                done     = Signal(str, str)
                error    = Signal(str, str)
            def __init__(self, j, pgs, out, dp):
                super().__init__()
                self.s = _Worker.S()
                self.job, self.pages, self.out, self.dpi = j, pgs, out, dp
            @Slot()
            def run(self):
                try:
                    import cv2
                    import fitz
                    doc = fitz.Document()
                    tocs = []
                    for i, page in enumerate(self.pages):
                        self.s.progress.emit(self.job.id, i + 1, len(self.pages))
                        img = page.display_image
                        h, w = img.shape[:2]
                        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
                        p = doc.new_page(width=w, height=h)
                        p.insert_image(p.rect, stream=buf.tobytes())
                        if page.bookmark:
                            tocs.append([1, page.bookmark, i + 1])
                    if tocs:
                        doc.set_toc(tocs)
                    doc.save(self.out, garbage=4, deflate=True)
                    doc.close()
                    self.s.done.emit(self.job.id, self.out)
                except Exception as e:
                    self.s.error.emit(self.job.id, str(e))

        w = _Worker(job, pages, str(pdf_path), dpi)
        w.s.progress.connect(self._on_progress)
        w.s.done.connect(self._on_done)
        w.s.error.connect(self._on_error)
        self._workers[job.id] = w
        self._pool.start(w)
        return job.id

    def export_ant_split_bookmark(self, folder: str, serial_ini: int, padding: int,
                                   desde: int = 0, hasta: int = 0, label: str = "") -> str:
        """Múltiples PDFs usando marcadores como puntos de corte. Retorna job_id."""
        pages = self._m.pages
        if hasta > 0:
            pages = [p for p in pages if desde <= p.index + 1 <= hasta]
        elif desde > 1:
            pages = [p for p in pages if p.index + 1 >= desde]
        if not pages:
            return ""

        groups = self._build_groups_by_bookmark(list(pages))
        if not groups:
            return ""

        job = Job(job_type=JobType.ANTECEDENTES,
                  label=label or f"Antecedentes por marcador #{len(self._jobs) + 1}",
                  total=len(groups))
        self._jobs[job.id] = job
        self.job_created.emit(job)

        zip_path = unique(Path(folder) / ts_name("antecedentes_marcadores"))
        dpi = self._cfg.get("output", "pdf_dpi", 200)
        w = _AntBookmarkWorker(job, groups, zip_path, dpi, use_bookmark=True)
        w.s.progress.connect(self._on_progress)
        w.s.done.connect(self._on_done)
        w.s.error.connect(self._on_error)
        w.s.cancelled.connect(self._on_cancelled)
        self._workers[job.id] = w
        self._pool.start(w)
        return job.id

    def cancel_export(self, job_id: str):
        w = self._workers.get(job_id)
        if w and hasattr(w, "cancel"):
            w.cancel()

    def remove_job(self, job_id: str):
        self._jobs.pop(job_id, None)
        self._workers.pop(job_id, None)

    def all_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    @Slot(str, int, int)
    def _on_progress(self, job_id: str, cur: int, tot: int):
        job = self._jobs.get(job_id)
        if job:
            job.current = cur
            job.status  = JobStatus.RUNNING
        self.job_progress.emit(job_id, cur, tot)

    @Slot(str, str)
    def _on_done(self, job_id: str, path: str):
        job = self._jobs.get(job_id)
        if job:
            job.status      = JobStatus.DONE
            job.output_path = path
        self.job_done.emit(job_id, path)

    @Slot(str, str)
    def _on_error(self, job_id: str, msg: str):
        job = self._jobs.get(job_id)
        if job:
            job.status    = JobStatus.ERROR
            job.error_msg = msg
        self.job_error.emit(job_id, msg)

    @Slot(str)
    def _on_cancelled(self, job_id: str):
        job = self._jobs.get(job_id)
        if job:
            job.status    = JobStatus.CANCELLED
            job.error_msg = "Cancelado por el usuario"
        self.job_cancelled.emit(job_id)

    @staticmethod
    def _build_groups(pages: list[PageData]) -> list[list[PageData]]:
        if not pages:
            return []
        groups, cur = [], []
        for p in pages:
            if p.is_cut_point and cur:
                groups.append(cur)
                cur = [p]
            else:
                cur.append(p)
        if cur:
            groups.append(cur)
        return groups

    @staticmethod
    def _build_groups_by_bookmark(pages: list[PageData]) -> list[list[PageData]]:
        if not pages:
            return []
        groups, cur = [], []
        for p in pages:
            if p.bookmark and cur:
                groups.append(cur)
                cur = [p]
            else:
                cur.append(p)
        if cur:
            groups.append(cur)
        return groups
