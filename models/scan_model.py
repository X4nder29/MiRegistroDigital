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

    def add_page(self, image: np.ndarray, dpi: int = 300, source: str = "",
                 source_page: int = -1, comment: str = "",
                 bookmarks: list[tuple[int, str]] | None = None) -> PageData:
        page = PageData(
            index=len(self._pages), original_image=image, dpi=dpi,
            source_path=source, source_page=source_page,
            comment=comment, bookmarks=bookmarks or [])
        if bookmarks:
            page.bookmark = bookmarks[0][1] if bookmarks else ""
        self._pages.append(page)
        return page

    def get(self, index: int) -> Optional[PageData]:
        return self._pages[index] if 0 <= index < len(self._pages) else None

    def remove(self, index: int):
        if 0 <= index < len(self._pages):
            self._pages.pop(index)
            for i, p in enumerate(self._pages):
                p.index = i

    def set_corrected(self, index: int, image: Optional[np.ndarray], angle: float = 0.0):
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

    def reorder(self, from_idx: int, to_idx: int):
        if from_idx == to_idx:
            return
        if 0 <= from_idx < len(self._pages) and 0 <= to_idx < len(self._pages):
            page = self._pages.pop(from_idx)
            self._pages.insert(to_idx, page)
            for i, p in enumerate(self._pages):
                p.index = i

    def reorder_batch(self, indices: list[int], to_idx: int):
        if not indices:
            return
        indices = sorted(set(indices), reverse=True)
        pages = [self._pages.pop(i) for i in indices]
        insert_at = min(to_idx, len(self._pages))
        for i, p in enumerate(pages):
            self._pages.insert(insert_at + i, p)
        for i, p in enumerate(self._pages):
            p.index = i

    def set_bookmark(self, index: int, labels: list[tuple[int, str]]):
        p = self.get(index)
        if p:
            p.bookmarks = list(labels)
            p.bookmark = labels[0][1] if labels else ""

    def set_comment(self, index: int, text: str):
        p = self.get(index)
        if p:
            p.comment = text

    def reorder_to_sequence(self, indices_in_order: list[int]):
        if len(indices_in_order) != len(self._pages):
            return
        if set(indices_in_order) != {p.index for p in self._pages}:
            return
        mapping = {p.index: p for p in self._pages}
        self._pages = [mapping[i] for i in indices_in_order]
        for i, p in enumerate(self._pages):
            p.index = i

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

    def load_pages(self, pages: list[PageData]):
        self._pages.clear()
        self._pages.extend(pages)
        for i, p in enumerate(self._pages):
            p.index = i

    def clear(self):
        self._pages.clear()
