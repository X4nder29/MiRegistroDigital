"""VisualizationController — escaneo de directorio y combinación de PDFs para la sección Visualización."""
from __future__ import annotations
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot

from models.config_model import ConfigModel
from models.visualization_model import Category, ScanResult, MatchPair, CategoryBatch
from utils.scan_utils import scan_root, save_cache, load_cache, load_cancelled, save_cancelled

logger = logging.getLogger("docscan.visualization")


class _ScanWorker(QRunnable):
    class S(QObject):
        category_ready = Signal(object)
        done = Signal(object)
        error = Signal(str)

    def __init__(self, root: Path):
        super().__init__()
        self.s = _ScanWorker.S()
        self.root = root
        self._stop = False

    def cancel(self):
        self._stop = True

    @Slot()
    def run(self):
        try:
            result = scan_root(
                self.root,
                on_category_done=lambda batch: self.s.category_ready.emit(batch),
                should_stop=lambda: self._stop,
            )
            if not self._stop:
                try:
                    save_cache(result)
                except Exception:
                    logger.warning("No se pudo guardar la caché de visualización", exc_info=True)
            self.s.done.emit(result)
        except Exception as e:
            logger.exception("Error escaneando %s", self.root)
            self.s.error.emit(str(e))


class _BulkCombineWorker(QRunnable):
    class S(QObject):
        progress = Signal(int, int)
        done = Signal(int, int)
        error = Signal(str)

    def __init__(self, pairs: list[MatchPair], out_dir: Path, prefix_category: bool):
        super().__init__()
        self.s = _BulkCombineWorker.S()
        self.pairs, self.out_dir, self.prefix_category = pairs, out_dir, prefix_category
        self._stop = False

    def cancel(self):
        self._stop = True

    @Slot()
    def run(self):
        from utils.file_utils import combine_registro_antecedente, sanitize
        try:
            ok = fail = 0
            matched = [p for p in self.pairs if p.is_matched]
            for i, pair in enumerate(matched):
                if self._stop:
                    break
                self.s.progress.emit(i + 1, len(matched))
                try:
                    name = f"{pair.category.value}_{pair.serial}.pdf" if self.prefix_category else f"{pair.serial}.pdf"
                    out_path = self.out_dir / sanitize(name)
                    combine_registro_antecedente(pair.registro.path, pair.antecedente.path, out_path)
                    ok += 1
                except Exception as e:
                    logger.warning("Fallo combinando serial %s: %s", pair.serial, e)
                    fail += 1
            self.s.done.emit(ok, fail)
        except Exception as e:
            logger.exception("Error en combinación masiva")
            self.s.error.emit(str(e))


class VisualizationController(QObject):
    scan_started = Signal()
    scan_category_ready = Signal(object)
    scan_progress = Signal(int)
    scan_done = Signal(object)
    scan_finished = Signal()
    scan_error = Signal(str)
    combine_progress = Signal(int, int)
    combine_done = Signal(int, int)
    combine_error = Signal(str)

    def __init__(self, config: ConfigModel, parent=None):
        super().__init__(parent)
        self._cfg = config
        self._pool = QThreadPool.globalInstance()
        self._scan_worker: _ScanWorker | None = None
        self._combine_worker: _BulkCombineWorker | None = None
        self.last_result: ScanResult | None = None
        self._scanned_count = 0
        self._cancelled: set[tuple[Category, str]] = load_cancelled()

    def root_folder(self) -> str:
        return self._cfg.get("visualization", "root_folder", "")

    def set_root_folder(self, path: str):
        self._cfg.set("visualization", "root_folder", path)
        self._cfg.save()

    def load_cached_result(self) -> ScanResult | None:
        """Carga el ultimo escaneo guardado en disco, solo si corresponde a la carpeta configurada."""
        cached = load_cache()
        if cached is None:
            return None
        root = self.root_folder()
        if not root or str(Path(root)) != str(cached.root):
            return None
        for pairs in cached.pairs.values():
            self._apply_cancelled(pairs)
        return cached

    def _apply_cancelled(self, pairs: list[MatchPair]):
        for p in pairs:
            p.cancelado = (p.category, p.serial) in self._cancelled

    def set_cancelled(self, pair: MatchPair, cancelled: bool):
        key = (pair.category, pair.serial)
        if cancelled:
            self._cancelled.add(key)
        else:
            self._cancelled.discard(key)
        pair.cancelado = cancelled
        save_cancelled(self._cancelled)

    def start_scan(self):
        root = self.root_folder()
        if not root:
            self.scan_error.emit("No hay carpeta configurada.")
            self.scan_finished.emit()
            return
        if self._scan_worker:
            self._scan_worker.cancel()
        self._scanned_count = 0
        w = _ScanWorker(Path(root))
        w.s.category_ready.connect(self._on_category_ready)
        w.s.done.connect(self._on_scan_done)
        w.s.error.connect(self._on_scan_error)
        self._scan_worker = w
        self.scan_started.emit()
        self._pool.start(w)

    def _on_category_ready(self, batch: CategoryBatch):
        self._apply_cancelled(batch.pairs)
        self._scanned_count += len(batch.pairs)
        self.scan_progress.emit(self._scanned_count)
        self.scan_category_ready.emit(batch)

    def _on_scan_done(self, result: ScanResult):
        self.last_result = result
        self._scan_worker = None
        self.scan_done.emit(result)
        self.scan_finished.emit()

    def _on_scan_error(self, msg: str):
        self._scan_worker = None
        self.scan_error.emit(msg)
        self.scan_finished.emit()

    def combine_single(self, pair: MatchPair, out_path: Path):
        """Sincrónico — combinar 2 PDFs es prácticamente instantáneo."""
        from utils.file_utils import combine_registro_antecedente
        combine_registro_antecedente(pair.registro.path, pair.antecedente.path, out_path)

    def start_bulk_combine(self, pairs: list[MatchPair], out_dir: Path, prefix_category: bool = False):
        w = _BulkCombineWorker(pairs, out_dir, prefix_category)
        w.s.progress.connect(self.combine_progress)
        w.s.done.connect(self.combine_done)
        w.s.error.connect(self.combine_error)
        self._combine_worker = w
        self._pool.start(w)

    def cancel_bulk_combine(self):
        if self._combine_worker:
            self._combine_worker.cancel()
