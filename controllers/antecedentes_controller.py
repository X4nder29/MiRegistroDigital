"""
AntecedentesController — Divide páginas por puntos de corte y genera PDFs
numerados a partir de un serial inicial configurable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel, PageData
from models.pdf_model import PDFModel
from models.config_model import ConfigModel
from utils.file_utils import serial_from_counter, timestamped_zip_name, unique_path


class AntecedentesWorker(QRunnable):
    """Genera los PDFs de grupos en segundo plano."""

    class Signals(QObject):
        progress = Signal(int, int)
        finished = Signal(str)
        error = Signal(str)

    def __init__(
        self,
        groups: list[list[dict]],   # [[{"image": ndarray, "dpi": int}, ...], ...]
        output_path: Path,
        serial_inicial: int,
        serial_padding: int,
        pdf_dpi: int,
    ):
        super().__init__()
        self.signals = AntecedentesWorker.Signals()
        self.groups = groups
        self.output_path = output_path
        self.serial_inicial = serial_inicial
        self.serial_padding = serial_padding
        self.pdf_dpi = pdf_dpi

    @Slot()
    def run(self):
        try:
            pdf_model = PDFModel()
            total = len(self.groups)
            counter = self.serial_inicial

            for i, group in enumerate(self.groups):
                self.signals.progress.emit(i + 1, total)
                images = [item["image"] for item in group]
                pdf_bytes = pdf_model.create_multipage_pdf(images, self.pdf_dpi)
                name = serial_from_counter(counter, self.serial_padding)
                pdf_model.add_pdf(name, pdf_bytes)
                counter += 1

            pdf_model.build_zip(self.output_path)
            self.signals.finished.emit(str(self.output_path))

        except Exception as exc:
            self.signals.error.emit(str(exc))


class AntecedentesController(QObject):
    """
    Signals
    -------
    progress(int, int)      — progreso por grupo
    export_done(str)        — ZIP generado
    export_error(str)       — error
    groups_changed(int)     — cantidad de grupos tras cambio de cortes
    """

    progress = Signal(int, int)
    export_done = Signal(str)
    export_error = Signal(str)
    groups_changed = Signal(int)

    def __init__(
        self,
        scan_model: ScanModel,
        pdf_model: PDFModel,
        config: ConfigModel,
        parent=None,
    ):
        super().__init__(parent)
        self._scan = scan_model
        self._pdf = pdf_model
        self._config = config
        self._pool = QThreadPool.globalInstance()

    # ── Gestión de cortes ─────────────────────────────────────────────────────

    def toggle_cut_point(self, page_index: int) -> bool:
        """Activa/desactiva un punto de corte. Retorna el nuevo estado."""
        new_state = self._scan.toggle_cut_point(page_index)
        groups = self._scan.get_groups()
        self.groups_changed.emit(len(groups))
        return new_state

    def set_cut_points(self, indices: list[int]) -> None:
        """Establece los puntos de corte a partir de una lista de índices."""
        for page in self._scan.pages:
            page.is_cut_point = page.index in indices
        groups = self._scan.get_groups()
        self.groups_changed.emit(len(groups))

    def get_groups_preview(self) -> list[list[int]]:
        """Retorna lista de listas de índices de páginas por grupo."""
        return [[p.index for p in g] for g in self._scan.get_groups()]

    # ── Exportación ───────────────────────────────────────────────────────────

    def export(
        self,
        output_folder: Optional[Path] = None,
        serial_inicial: Optional[int] = None,
        desde: Optional[int] = None,
        hasta: Optional[int] = None,
    ):
        """
        Genera los PDFs de grupos y los empaqueta en ZIP.

        Parámetros
        ----------
        serial_inicial : primer número del serial (sobreescribe config)
        desde / hasta  : rango de páginas 1-indexed (sobreescribe config)
        """
        if self._scan.count == 0:
            self.export_error.emit("No hay páginas para exportar.")
            return

        cfg = self._config
        _serial = serial_inicial if serial_inicial is not None else cfg.get("antecedentes", "serial_inicial", 1)
        _padding = cfg.get("antecedentes", "serial_padding", 5)
        _desde = desde if desde is not None else cfg.get("antecedentes", "desde", 1)
        _hasta = hasta if hasta is not None else cfg.get("antecedentes", "hasta", 0)

        # Filtrar rango
        pages = self._scan.pages
        if _hasta and _hasta > 0:
            pages = [p for p in pages if _desde <= p.index + 1 <= _hasta]
        else:
            pages = [p for p in pages if p.index + 1 >= _desde]

        if not pages:
            self.export_error.emit("El rango seleccionado no contiene páginas.")
            return

        # Construir grupos a partir de las páginas filtradas
        groups = self._build_groups_from_pages(pages)

        if not groups:
            self.export_error.emit("No se encontraron grupos válidos.")
            return

        folder = output_folder or Path(cfg.get("output", "default_folder", "."))
        folder.mkdir(parents=True, exist_ok=True)
        zip_name = timestamped_zip_name("antecedentes")
        zip_path = unique_path(folder / zip_name)
        pdf_dpi = cfg.get("output", "pdf_dpi", 200)

        raw_groups = [
            [{"image": p.display_image, "dpi": p.dpi} for p in group]
            for group in groups
        ]

        worker = AntecedentesWorker(raw_groups, zip_path, _serial, _padding, pdf_dpi)
        worker.signals.progress.connect(self.progress)
        worker.signals.finished.connect(self.export_done)
        worker.signals.error.connect(self.export_error)
        self._pool.start(worker)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_groups_from_pages(pages: list[PageData]) -> list[list[PageData]]:
        """Divide una lista de páginas usando sus marcas is_cut_point."""
        if not pages:
            return []
        groups: list[list[PageData]] = []
        current: list[PageData] = []
        for page in pages:
            if page.is_cut_point and current:
                groups.append(current)
                current = [page]
            else:
                current.append(page)
        if current:
            groups.append(current)
        return groups
