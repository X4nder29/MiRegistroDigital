"""
PDFModel — Generación de archivos PDF a partir de imágenes y empaquetado en ZIP.
"""
import io
import zipfile
from pathlib import Path
from typing import Optional
from PIL import Image
import numpy as np


class PDFModel:
    """
    Genera PDFs de una o varias páginas y los empaqueta en ZIP.
    No escribe archivos temporales al disco; trabaja en memoria.
    """

    def __init__(self):
        self._generated: dict[str, bytes] = {}  # nombre_archivo → bytes del PDF

    def clear(self) -> None:
        self._generated.clear()

    # ── Generación ────────────────────────────────────────────────────────────

    def create_single_page_pdf(
        self,
        image: np.ndarray,
        dpi: int = 300,
    ) -> bytes:
        """
        Crea un PDF de una sola página en memoria y retorna los bytes.
        """
        pil_img = self._to_pil(image)
        buf = io.BytesIO()
        pil_img.save(buf, format="PDF", resolution=dpi)
        return buf.getvalue()

    def create_multipage_pdf(
        self,
        images: list[np.ndarray],
        dpi: int = 300,
    ) -> bytes:
        """
        Crea un PDF de múltiples páginas en memoria y retorna los bytes.
        """
        if not images:
            raise ValueError("La lista de imágenes está vacía.")

        pil_images = [self._to_pil(img) for img in images]
        first = pil_images[0]
        rest = pil_images[1:] if len(pil_images) > 1 else []

        buf = io.BytesIO()
        first.save(
            buf,
            format="PDF",
            resolution=dpi,
            save_all=True,
            append_images=rest,
        )
        return buf.getvalue()

    def add_pdf(self, name: str, data: bytes) -> None:
        """Registra un PDF generado con su nombre."""
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        self._generated[name] = data

    # ── Empaquetado ZIP ───────────────────────────────────────────────────────

    def build_zip(self, output_path: Path) -> int:
        """
        Empaqueta todos los PDFs generados en un ZIP.
        Retorna la cantidad de archivos incluidos.
        """
        if not self._generated:
            raise ValueError("No hay PDFs generados para empaquetar.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in self._generated.items():
                zf.writestr(name, data)

        return len(self._generated)

    def build_zip_bytes(self) -> bytes:
        """
        Empaqueta todos los PDFs generados en un ZIP en memoria.
        Retorna los bytes del ZIP.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in self._generated.items():
                zf.writestr(name, data)
        return buf.getvalue()

    # ── Utilidades ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_pil(image: np.ndarray) -> Image.Image:
        """Convierte ndarray a PIL Image en modo adecuado."""
        if image.ndim == 2:
            return Image.fromarray(image, mode="L")
        if image.shape[2] == 4:
            return Image.fromarray(image, mode="RGBA").convert("RGB")
        return Image.fromarray(image, mode="RGB")

    def sanitize_filename(self, name: str) -> str:
        """Elimina caracteres no válidos para nombres de archivo."""
        invalid = r'\/:*?"<>|'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip()

    @property
    def generated_count(self) -> int:
        return len(self._generated)

    @property
    def pdf_names(self) -> list[str]:
        return list(self._generated.keys())
