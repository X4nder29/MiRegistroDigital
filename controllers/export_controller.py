"""ExportController — múltiples trabajos de exportación concurrentes."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel, PageData
from models.job_model import Job, JobType, JobStatus
from models.config_model import ConfigModel
from utils.file_utils import (sanitize, serial_str, ts_name, unique, build_zip)

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
                entries[base + ".pdf"] = _build_pdf_bytes([page], self.dpi)
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
                entries[name] = _build_pdf_bytes(group, self.dpi)
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
                bm = ExportController._get_bookmark_label(page)
                base = sanitize(bm or page.final_label)
                if base in used:
                    used[base] += 1
                    base = f"{base}_{used[base]}"
                else:
                    used[base] = 0
                entries[base + ".pdf"] = _build_pdf_bytes([page], self.dpi)
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
                    bm = ExportController._get_bookmark_label(group[0])
                    base = sanitize(bm or f"grupo_{i+1:04d}")
                else:
                    base = f"grupo_{i+1:04d}"
                if base in used:
                    used[base] += 1
                    base = f"{base}_{used[base]}"
                else:
                    used[base] = 0
                entries[base + ".pdf"] = _build_pdf_bytes(group, self.dpi)
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
                    import fitz
                    doc = _build_pdf_doc(self.pages, self.dpi)
                    tocs = []
                    for i, page in enumerate(self.pages):
                        self.s.progress.emit(self.job.id, i + 1, len(self.pages))
                        bm = page.bookmarks if page.bookmarks else ([page.bookmark] if page.bookmark else [])
                        if bm:
                            for lvl, title in bm:
                                tocs.append([lvl, title, i + 1])
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

    def export_original_pdf(self, folder: str, label: str = "") -> str:
        pages = self._m.pages
        if not pages:
            return ""

        job = Job(job_type=JobType.CIVIL,
                  label=label or f"PDF original #{len(self._jobs) + 1}",
                  total=len(pages))
        self._jobs[job.id] = job
        self.job_created.emit(job)

        pdf_path = unique(Path(folder) / "documento_original.pdf")

        class _Worker(QRunnable):
            class S(QObject):
                progress = Signal(str, int, int)
                done     = Signal(str, str)
                error    = Signal(str, str)
            def __init__(self, j, pgs, out):
                super().__init__()
                self.s = _Worker.S()
                self.job, self.pages, self.out = j, pgs, out
            @Slot()
            def run(self):
                try:
                    import fitz
                    same_source = len({p.source_path for p in self.pages}) == 1
                    has_pdf_src = same_source and self.pages and \
                        self.pages[0].source_path.lower().endswith('.pdf') and \
                        all(p.source_page >= 0 for p in self.pages)

                    doc = fitz.Document()
                    tocs = []

                    if has_pdf_src:
                        src = fitz.open(self.pages[0].source_path)
                        for i, page in enumerate(self.pages):
                            self.s.progress.emit(self.job.id, i + 1, len(self.pages))
                            doc.insert_pdf(src, from_page=page.source_page, to_page=page.source_page)
                            if page.comment:
                                p = doc[-1]
                                r = p.rect
                                bh = min(60, r.height // 3)
                                rect = fitz.Rect(0, r.y1 - bh, r.x1, r.y1)
                                p.add_freetext_annot(
                                    rect, page.comment,
                                    fontsize=9, fontname="helv",
                                    text_color=(1, 1, 1),
                                    fill_color=(0, 0, 0),
                                    border_width=0,
                                )
                            bm = page.bookmarks if page.bookmarks else ([page.bookmark] if page.bookmark else [])
                            if bm:
                                for lvl, title in bm:
                                    tocs.append([lvl, title, i + 1])
                        src.close()
                    else:
                        from utils.image_utils import overlay_comment
                        pages_with_comment = []
                        for p in self.pages:
                            if p.comment:
                                p = PageData(
                                    index=p.index,
                                    original_image=p.original_image,
                                    corrected_image=p.corrected_image,
                                    source_path=p.source_path,
                                    source_page=p.source_page,
                                    comment=p.comment,
                                    bookmarks=p.bookmarks,
                                    bookmark=p.bookmark,
                                )
                                p.original_image = overlay_comment(p.original_image, p.comment)
                                p.corrected_image = overlay_comment(p.corrected_image, p.comment) if p.corrected_image is not None else None
                            pages_with_comment.append(p)
                        _append_to_doc(doc, pages_with_comment, 200)
                        for i, page in enumerate(self.pages):
                            self.s.progress.emit(self.job.id, i + 1, len(self.pages))
                            bm = page.bookmarks if page.bookmarks else ([page.bookmark] if page.bookmark else [])
                            if bm:
                                for lvl, title in bm:
                                    tocs.append([lvl, title, i + 1])

                    if tocs:
                        doc.set_toc(tocs)
                    doc.save(self.out, garbage=4, deflate=True)
                    doc.close()
                    self.s.done.emit(self.job.id, self.out)
                except Exception as e:
                    self.s.error.emit(self.job.id, str(e))

        w = _Worker(job, pages, str(pdf_path))
        w.s.progress.connect(self._on_progress)
        w.s.done.connect(self._on_done)
        w.s.error.connect(self._on_error)
        self._workers[job.id] = w
        self._pool.start(w)
        return job.id

    @staticmethod
    def _build_groups_by_bookmark(pages: list[PageData]) -> list[list[PageData]]:
        if not pages:
            return []
        groups, cur = [], []
        for p in pages:
            has_bm = bool(p.bookmarks) or bool(p.bookmark)
            if has_bm and cur:
                groups.append(cur)
                cur = [p]
            else:
                cur.append(p)
        if cur:
            groups.append(cur)
        return groups

    @staticmethod
    def _get_bookmark_label(p: PageData) -> str:
        if p.bookmarks:
            return p.bookmarks[0][1]
        return p.bookmark


# ── PDF build helpers ────────────────────────────────────────────────

def _build_pdf_bytes(pages: list[PageData], dpi: int) -> bytes:
    """Build PDF bytes from page data, using direct source page copy when possible."""
    import fitz
    doc = fitz.Document()
    _append_to_doc(doc, pages, dpi)
    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data


def _build_pdf_doc(pages: list[PageData], dpi: int) -> fitz.Document:
    """Build a fitz Document from page data, using direct source page copy when possible."""
    import fitz
    doc = fitz.Document()
    _append_to_doc(doc, pages, dpi)
    return doc


def _append_to_doc(doc: fitz.Document, pages: list[PageData], dpi: int):
    """Append pages to an existing fitz Document, grouping by source for direct copy."""
    from collections import defaultdict
    from pathlib import Path

    groups: dict[str, list[PageData]] = defaultdict(list)
    for p in pages:
        groups[p.source_path if p.source_path else ""].append(p)

    for src, src_pages in groups.items():
        is_pdf = src.lower().endswith('.pdf') if src else False
        src_exists = Path(src).exists() if src else False
        has_corrections = any(p.corrected_image is not None for p in src_pages)

        if is_pdf and src_exists and not has_corrections:
            _merge_pdf_src(doc, src, src_pages)
        else:
            _merge_images(doc, src_pages)


def _merge_pdf_src(doc: fitz.Document, src: str, pages: list[PageData]):
    """Copy pages directly from a source PDF (lossless)."""
    import fitz
    src_doc = fitz.open(src)
    nums = [p.source_page for p in pages if p.source_page >= 0]
    if nums:
        if len(nums) == 1:
            doc.insert_pdf(src_doc, from_page=nums[0], to_page=nums[0])
        else:
            src_doc.select(nums)
            doc.insert_pdf(src_doc)
    src_doc.close()


def _merge_images(doc: fitz.Document, pages: list[PageData]):
    """Encode pages as JPEG and insert (lossy fallback for non-PDF sources)."""
    import cv2
    for p in pages:
        img = p.display_image
        h, w = img.shape[:2]
        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        new_page = doc.new_page(width=w, height=h)
        new_page.insert_image(new_page.rect, stream=buf.tobytes())
