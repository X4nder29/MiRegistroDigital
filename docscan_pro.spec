# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para MiRegistroDigital.
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Colección de datos de dependencias pesadas ──────────────────────
easyocr_datas, easyocr_bins, easyocr_hidden = collect_all("easyocr")
torch_datas,   torch_bins,   torch_hidden   = collect_all("torch")
cv2_datas,     cv2_bins,     cv2_hidden     = collect_all("cv2")

# ── Paquetes propios que PyInstaller no detecta automáticamente ─────
HIDDEN = [
    "controllers",
    "views",
    "models",
    "utils",
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "PySide6.QtCore",
    "easyocr",
    "PIL",
    "pypdf",
    "fitz",
    "numpy",
    *easyocr_hidden,
    *torch_hidden,
    *cv2_hidden,
    *collect_submodules("sklearn"),
]

# ── Datos adicionales (fonts, etc.) ─────────────────────────────────
font_path = Path("fonts")
DATAS = [("fonts", "fonts")] if font_path.exists() and any(font_path.iterdir()) else []

DATAS += easyocr_datas + torch_datas + cv2_datas

BINS = easyocr_bins + torch_bins + cv2_bins

# ── Análisis ───────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=BINS,
    datas=DATAS,
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "IPython", "jupyter",
        "notebook", "test", "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MiRegistroDigital",
    debug=False,
    icon=None,
    upx=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MiRegistroDigital",
)
