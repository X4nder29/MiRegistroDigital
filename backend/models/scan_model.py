"""Almacén central de páginas de la sesión."""
from __future__ import annotations
from typing import Optional
import numpy as np
from .page_data import PageData


class ScanModel:
    def __init__(self):
        self._pages: list[PageData] = []

    @property
    def pages(self) -> list[PageData]:
        return self._pages

    @property
    def count(self) -> int:
        return len(self._pages)

    def add_page(self, image: np.ndarray, dpi: int = 300, source_path: str = "") -> PageData:
        page = PageData(index=len(self._pages), original_image=image, dpi=dpi, source_path=source_path)
        self._pages.append(page)
        return page

    def remove_page(self, index: int) -> None:
        if 0 <= index < len(self._pages):
            self._pages.pop(index)
            for i, p in enumerate(self._pages):
                p.index = i

    def get(self, index: int) -> Optional[PageData]:
        return self._pages[index] if 0 <= index < len(self._pages) else None

    def set_corrected(self, index: int, image: np.ndarray, angle: float = 0.0):
        p = self.get(index)
        if p:
            p.corrected_image = image
            p.rotation_angle = angle

    def set_serial(self, index: int, serial: str, confidence: float = 0.0):
        p = self.get(index)
        if p:
            p.serial = serial
            p.serial_confidence = confidence

    def toggle_cut(self, index: int) -> bool:
        p = self.get(index)
        if p:
            p.is_cut_point = not p.is_cut_point
            return p.is_cut_point
        return False

    def set_cuts(self, indices: set[int]):
        for p in self._pages:
            p.is_cut_point = p.index in indices

    def get_groups(self) -> list[list[PageData]]:
        if not self._pages:
            return []
        groups, cur = [], []
        for p in self._pages:
            if p.is_cut_point and cur:
                groups.append(cur)
                cur = [p]
            else:
                cur.append(p)
        if cur:
            groups.append(cur)
        return groups

    def clear(self):
        self._pages.clear()
