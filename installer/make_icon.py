"""Rasteriza resources/app_icon.svg a resources/app_icon.ico (multi-resolucion).

Ejecutar una sola vez (o cuando cambie el SVG):
    python installer/make_icon.py
"""
import io
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

SIZES = [16, 32, 48, 64, 128, 256]


def render_png_bytes(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    buf_bytes = io.BytesIO()
    ba = image.bits().tobytes()
    img = Image.frombuffer("RGBA", (size, size), ba, "raw", "BGRA", 0, 1)
    img.save(buf_bytes, format="PNG")
    return buf_bytes.getvalue()


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    svg_path = root / "resources" / "app_icon.svg"
    ico_path = root / "resources" / "app_icon.ico"

    if not svg_path.exists():
        print(f"ERROR: no existe {svg_path}")
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        print(f"ERROR: SVG invalido: {svg_path}")
        return 1

    frames = []
    for size in SIZES:
        png_bytes = render_png_bytes(renderer, size)
        frames.append(Image.open(io.BytesIO(png_bytes)).convert("RGBA"))

    frames[-1].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[:-1],
    )
    print(f"Icono generado: {ico_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
