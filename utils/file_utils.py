from __future__ import annotations
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
import numpy as np

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
PDF_EXT    = ".pdf"


def sanitize(name: str) -> str:
    return _BAD.sub("_", name).strip(". ") or "archivo"


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


def combine_registro_antecedente(registro_path: Path, antecedente_path: Path, out_path: Path) -> Path:
    """Combina registro_path y antecedente_path en un solo PDF, registro primero.

    Misma lógica que MainWindow._on_merge_pdfs (views/main_window.py) pero fija a
    exactamente estas dos fuentes, con marcadores "Registro"/"Antecedente".
    """
    import fitz
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dest = fitz.Document()
    tocs = []
    page_offset = 0
    for label, path in (("Registro", registro_path), ("Antecedente", antecedente_path)):
        src = fitz.Document(str(path))
        dest.insert_pdf(src)
        tocs.append([1, label, page_offset + 1])
        page_offset += src.page_count
        src.close()
    dest.set_toc(tocs)
    dest.save(str(out_path), garbage=4, deflate=True)
    dest.close()
    return out_path
