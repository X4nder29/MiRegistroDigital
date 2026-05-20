"""Página de trabajos de exportación."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from models.job_model import Job, JobStatus
from views.theme import SURFACE, TEXT_DIM, SUCCESS, DANGER, TEXT_SEC, BG, SURFACE3


class JobCard(QFrame):
    remove_requested = Signal(str)
    cancel_requested = Signal(str)

    def __init__(self, job: Job, parent=None):
        super().__init__(parent)
        self.job_id = job.id
        self.setFixedHeight(70)
        self.setStyleSheet(f"background:{SURFACE}; border:none; border-radius:6px;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(12)

        center = QWidget()
        center.setStyleSheet("border:none; background:transparent;")
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(4)

        self._title = QLabel(job.label)
        self._title.setStyleSheet("font-size:10pt; border:none;")
        cv.addWidget(self._title)

        self._prog = QProgressBar()
        self._prog.setFixedHeight(3)
        self._prog.setTextVisible(False)
        self._prog.setRange(0, max(job.total, 1))
        self._prog.setValue(job.current)
        cv.addWidget(self._prog)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"font-size:9pt; color:{TEXT_DIM}; border:none;")
        cv.addWidget(self._status_lbl)
        lay.addWidget(center, 1)

        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setFixedHeight(28)
        self._btn_cancel.setVisible(False)
        self._btn_cancel.clicked.connect(lambda: self.cancel_requested.emit(self.job_id))
        lay.addWidget(self._btn_cancel)

        self._btn_open   = QPushButton("Abrir carpeta")
        self._btn_open.setFixedHeight(28)
        self._btn_open.setVisible(False)
        self._btn_open.clicked.connect(self._open_folder)
        lay.addWidget(self._btn_open)

        self._btn_remove = QPushButton("✕")
        self._btn_remove.setFixedSize(28, 28)
        self._btn_remove.setVisible(False)
        self._btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.job_id))
        lay.addWidget(self._btn_remove)

        self._output = ""
        self.update_job(job)

    def update_job(self, job: Job):
        self._prog.setMaximum(max(job.total, 1))
        self._prog.setValue(job.current)
        self._output = job.output_path
        self._btn_cancel.setVisible(False)
        self._btn_open.setVisible(False)
        self._btn_remove.setVisible(False)

        if job.status == JobStatus.RUNNING:
            self._prog.setRange(0, max(job.total, 1))
            self._status_lbl.setText(f"{job.current}/{job.total} páginas")
            self._status_lbl.setStyleSheet(f"font-size:9pt; color:{TEXT_DIM}; border:none;")
            self._btn_cancel.setVisible(True)
        elif job.status == JobStatus.QUEUED:
            self._prog.setRange(0, 0)
            self._status_lbl.setText("En cola…")
            self._btn_cancel.setVisible(True)
        elif job.status == JobStatus.DONE:
            self._prog.setRange(0, 1); self._prog.setValue(1)
            self._status_lbl.setText("Completado")
            self._status_lbl.setStyleSheet(f"font-size:9pt; color:{SUCCESS}; border:none;")
            self._btn_open.setVisible(bool(job.output_path))
            self._btn_remove.setVisible(True)
        elif job.status == JobStatus.ERROR:
            self._prog.setRange(0, 1); self._prog.setValue(0)
            self._status_lbl.setText(f"Error: {job.error_msg}")
            self._status_lbl.setStyleSheet(f"font-size:9pt; color:{DANGER}; border:none;")
            self._btn_remove.setVisible(True)
        elif job.status == JobStatus.CANCELLED:
            self._prog.setRange(0, 1); self._prog.setValue(0)
            self._status_lbl.setText("Cancelado")
            self._status_lbl.setStyleSheet(f"font-size:9pt; color:{TEXT_DIM}; border:none;")
            self._btn_remove.setVisible(True)

    def _open_folder(self):
        if self._output:
            from pathlib import Path
            folder = str(Path(self._output).parent)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class JobsPage(QWidget):
    cancel_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, JobCard] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background:{SURFACE}; border:none;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Trabajos")
        title.setStyleSheet("font-size:15pt; font-weight:bold; border:none;")
        self._active_lbl = QLabel("Sin trabajos activos")
        self._active_lbl.setStyleSheet(f"color:{TEXT_DIM}; font-size:9pt; border:none;")
        btn_clear = QPushButton("Limpiar completados")
        btn_clear.setFixedHeight(32)
        btn_clear.clicked.connect(self._clear_done)
        hl.addWidget(title)
        hl.addSpacing(12)
        hl.addWidget(self._active_lbl)
        hl.addStretch()
        hl.addWidget(btn_clear)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")

        self._content = QWidget()
        self._content.setStyleSheet(f"background:{BG}; border:none;")
        self._list_lay = QVBoxLayout(self._content)
        self._list_lay.setContentsMargins(20, 16, 20, 16)
        self._list_lay.setSpacing(8)
        self._list_lay.addStretch()
        scroll.setWidget(self._content)
        root.addWidget(scroll)

        self._placeholder = QLabel("Los trabajos de exportación aparecerán aquí")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(f"color:{TEXT_DIM}; font-size:10pt; border:none;")
        self._list_lay.insertWidget(0, self._placeholder)

    def add_job(self, job: Job):
        self._placeholder.setVisible(False)
        card = JobCard(job)
        card.remove_requested.connect(self._on_remove)
        card.cancel_requested.connect(self.cancel_requested)
        self._cards[job.id] = card
        self._list_lay.insertWidget(self._list_lay.count() - 1, card)
        self._update_active()

    def update_job(self, job: Job):
        card = self._cards.get(job.id)
        if card:
            card.update_job(job)
        self._update_active()

    def _on_remove(self, job_id: str):
        card = self._cards.pop(job_id, None)
        if card:
            self._list_lay.removeWidget(card)
            card.deleteLater()
        if not self._cards:
            self._placeholder.setVisible(True)
        self._update_active()

    def _clear_done(self):
        done = [jid for jid, card in self._cards.items()
                if not card._btn_cancel.isVisible() and card._btn_remove.isVisible()]
        for jid in done:
            self._on_remove(jid)

    def _update_active(self):
        active = sum(1 for c in self._cards.values()
                     if c._btn_cancel.isVisible())
        self._active_lbl.setText(
            f"{active} activo(s)" if active else "Sin trabajos activos")
