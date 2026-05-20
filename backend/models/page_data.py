"""Datos de una página escaneada/importada."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class PageData:
    index: int
    original_image: np.ndarray
    corrected_image: Optional[np.ndarray] = None
    serial: Optional[str] = None
    serial_confidence: float = 0.0
    user_label: Optional[str] = None
    is_cut_point: bool = False
    rotation_angle: float = 0.0
    dpi: int = 300
    source_path: str = ""          # ruta de origen si fue importado

    @property
    def display_image(self) -> np.ndarray:
        return self.corrected_image if self.corrected_image is not None else self.original_image

    @property
    def final_label(self) -> str:
        if self.user_label:
            return self.user_label
        if self.serial:
            return self.serial
        return f"pagina_{self.index + 1:04d}"
