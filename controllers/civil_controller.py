"""
CivilController — Genera un PDF por página con nombre = serial OCR.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.scan_model import ScanModel
from models.ocr_model import OCRModel
from models.pdf_model import PDFModel
from models.config_model import ConfigModel
from utils.file_utils import sanitize_filename, timestamped_zip_name, unique_path


class CivilWorker(QRunnable):
    """Genera los PDFs en segundo plano."""

    class Signals(QObject):
        progress = Signal(int, int)     # (actual, total)
        finished = Signal(str)          # ruta del ZIP generado
        error = Signal(str)

    def __init__(
        self,
        pages_data: list[dict],         # [{"image": ndarray, "label": str, "dpi": int}]
        output_path: Path,
        pdf_dpi: int,
    ):
        super().__init__()
        self.signals = CivilWorker.Signals()
        self.pages_data = pages_data
        self.output_path = output_path
        self.pdf_dpi = pdf_dpi

    @Slot()
    def run(self):
        try:
            pdf_model = PDFModel()
            total = len(self.pages_data)
            used_names: dict[str, int] = {}

            for i, item in enumerate(self.pages_data):
                self.signals.progress.emit(i + 1, total)

                raw_label = item["label"]
                base_name = sanitize_filename(raw_label)

                # Evitar nombres duplicados
                if base_name in used_names:
                    used_names[base_name] += 1
                    base_name = f"{base_name}_{used_names[base_name]}"
                else:
                    used_names[base_name] = 0

                pdf_bytes = pdf_model.create_single_page_pdf(item["image"], self.pdf_dpi)
                pdf_model.add_pdf(base_name, pdf_bytes)

            count = pdf_model.build_zip(self.output_path)
            self.signals.finished.emit(str(self.output_path))

        except Exception as exc:
            self.signals.error.emit(str(exc))


class CivilController(QObject):
    """
    Signals
    -------
    progress(int, int)      — progreso (actual, total)
    export_done(str)        — ZIP generado, ruta completa
    export_error(str)       — mensaje de error
    """

    progress = Signal(int, int)
    export_done = Signal(str)
    export_error = Signal(str)

    def __init__(
        self,
        scan_model: ScanModel,
        ocr_model: OCRModel,
        pdf_model: PDFModel,
        config: ConfigModel,
        parent=None,
    ):
        super().__init__(parent)
        self._scan = scan_model
        self._ocr = ocr_model
        self._pdf = pdf_model
        self._config = config
        self._pool = QThreadPool.globalInstance()

    def export(self, output_folder: Optional[Path] = None):
        """
        Genera un PDF por página nombrado con el serial OCR
        y empaqueta todo en un ZIP.
        """
        if self._scan.count == 0:
            self.export_error.emit("No hay páginas para exportar.")
            return

        folder = output_folder or Path(self._config.get("output", "default_folder", "."))
        folder.mkdir(parents=True, exist_ok=True)
        zip_name = timestamped_zip_name("registros_civiles")
        zip_path = unique_path(folder / zip_name)
        pdf_dpi = self._config.get("output", "pdf_dpi", 200)

        pages_data = []
        for page in self._scan.pages:
            label = page.final_label
            pages_data.append({
                "image": page.display_image,
                "label": label,
                "dpi": page.dpi,
            })

        worker = CivilWorker(pages_data, zip_path, pdf_dpi)
        worker.signals.progress.connect(self.progress)
        worker.signals.finished.connect(self.export_done)
        worker.signals.error.connect(self.export_error)
        self._pool.start(worker)

    def get_pending_labels(self) -> list[tuple[int, str]]:
        """
        Retorna lista de (page_index, label) para páginas sin serial OCR válido.
        Permite que la UI solicite corrección manual antes de exportar.
        """
        result = []
        for page in self._scan.pages:
            if not page.serial and not page.user_label:
                result.append((page.index, page.final_label))
        return result
