from __future__ import annotations
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
PDF_EXT    = ".pdf"


def sanitize(name: str) -> str:
    return _BAD.sub("_", name).strip(". ") or "archivo"


def serial_str(n: int, padding: int = 5) -> str:
    return str(n).zfill(padding)


def ts_name(prefix: str, ext: str = ".zip") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_stem(f"{path.stem}_{i}")
        if not candidate.exists():
            return candidate
        i += 1


def images_to_pdf_bytes(images: list[np.ndarray], dpi: int = 200) -> bytes:
    """Convierte lista de ndarray BGR a un PDF multipágina en memoria."""
    from PIL import Image
    pils = []
    for img in images:
        if img.ndim == 2:
            pils.append(Image.fromarray(img, "L"))
        elif img.shape[2] == 4:
            pils.append(Image.fromarray(img[:, :, :3][:, :, ::-1]))
        else:
            pils.append(Image.fromarray(img[:, :, ::-1]))  # BGR→RGB
    buf = io.BytesIO()
    pils[0].save(buf, format="PDF", resolution=dpi, save_all=True, append_images=pils[1:])
    return buf.getvalue()


def build_zip(entries: dict[str, bytes], path: Path):
    """Escribe un ZIP con los entries {nombre: bytes} en path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
