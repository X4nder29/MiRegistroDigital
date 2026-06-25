from __future__ import annotations
import json
import zipfile
import io
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import cv2
from models.page_data import PageData

PROJECT_EXT = ".miregistro"
_AUTOSAVE_DIR = Path.home() / ".miregistrodigital"
_AUTOSAVE_NAME = "autosave.miregistro"
_CURRENT_VERSION = 1


def get_autosave_path() -> Path:
    return _AUTOSAVE_DIR / _AUTOSAVE_NAME


def save(path: Path, pages: list[PageData]) -> None:
    metadata = {
        "version": _CURRENT_VERSION,
        "created": datetime.now().isoformat(),
        "pages": [],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, p in enumerate(pages):
            entry = {
                "index": p.index,
                "serial": p.serial,
                "serial_confidence": p.serial_confidence,
                "user_label": p.user_label,
                "bookmark": p.bookmark,
                "bookmarks": p.bookmarks,
                "comment": p.comment,
                "is_cut_point": p.is_cut_point,
                "rotation_angle": p.rotation_angle,
                "dpi": p.dpi,
                "source_path": p.source_path,
                "source_page": p.source_page,
                "ocr_area": list(p.ocr_area) if p.ocr_area else None,
            }
            metadata["pages"].append(entry)
            success, buf = cv2.imencode(".jpg", p.original_image,
                                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            if success:
                zf.writestr(f"pages/{i:04d}.jpg", buf.tobytes())

        zf.writestr("metadata.json", json.dumps(metadata, indent=2, ensure_ascii=False))


def load(path: Path, progress_callback: Optional[Callable[[int, int], None]] = None) -> list[PageData]:
    with zipfile.ZipFile(path, "r") as zf:
        metadata = json.loads(zf.read("metadata.json"))
        pages = []
        total = len(metadata["pages"])
        for i, entry in enumerate(metadata["pages"]):
            idx = entry["index"]
            img_data = zf.read(f"pages/{idx:04d}.jpg")
            buf = np.frombuffer(img_data, dtype=np.uint8)
            original = cv2.imdecode(buf, cv2.IMREAD_COLOR)

            angle = entry.get("rotation_angle", 0.0)
            if abs(angle) > 0.5:
                h, w = original.shape[:2]
                M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
                original = cv2.warpAffine(original, M, (w, h),
                                          flags=cv2.INTER_CUBIC,
                                          borderMode=cv2.BORDER_REPLICATE)

            oa = entry.get("ocr_area")
            ocr_area = tuple(oa) if oa else None

            page = PageData(
                index=idx,
                original_image=original,
                serial=entry.get("serial"),
                serial_confidence=entry.get("serial_confidence", 0.0),
                user_label=entry.get("user_label"),
                bookmark=entry.get("bookmark", ""),
                bookmarks=[(l, t) for l, t in entry.get("bookmarks", [])],
                comment=entry.get("comment", ""),
                is_cut_point=entry.get("is_cut_point", False),
                rotation_angle=0.0,
                dpi=entry.get("dpi", 300),
                source_path=entry.get("source_path", ""),
                source_page=entry.get("source_page", -1),
                ocr_area=ocr_area,
            )
            pages.append(page)
            if progress_callback:
                progress_callback(i + 1, total)
    return pages


def save_autosave(pages: list[PageData]) -> None:
    save(get_autosave_path(), pages)


def load_autosave() -> Optional[list[PageData]]:
    p = get_autosave_path()
    return load(p) if p.exists() else None


def clear_autosave():
    p = get_autosave_path()
    if p.exists():
        p.unlink()
