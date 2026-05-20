"""Helpers de archivos, nombres y ZIPs."""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

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
    while (p := path.with_stem(f"{path.stem}_{i}")).exists():
        i += 1
    return p

IMAGE_EXTS = {".jpg",".jpeg",".png",".tiff",".tif",".bmp",".webp"}
PDF_EXT    = ".pdf"
