# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

MiRegistroDigital (DocScan Pro) is a Windows-only Python/PySide6 desktop app for scanning/importing documents (TWAIN scanner or image/PDF import), running OCR (EasyOCR) to extract a serial number per page, and exporting to PDF in bulk. It also has a "Visualización" section that cross-references a civil-registry folder structure on disk (Registros vs. Antecedentes, matched by serial number).

## Commands

```bash
.venv\Scripts\activate
pip install -r requirements.txt   # Python 3.11+ required
python main.py                    # Run the app — the only way to verify changes
installer\build.bat               # Build .exe (onedir) — or use the /build-exe slash command
installer\build_onefile.bat       # Build .exe (single file, alternate/less-maintained path)
```

There are no tests, linter, or type checker configured in this project. All verification is manual, by running `python main.py` and exercising the affected feature in the UI.

Building: `installer\build.bat` cleans `dist\MiRegistroDigital` and PyInstaller's intermediate `build\docscan_pro` work directory, then runs PyInstaller against `docscan_pro.spec` (the canonical spec, tracked in git). Only `dist\MiRegistroDigital\MiRegistroDigital.exe` (plus its `_internal\` folder) is a valid, runnable build — anything under `build\` is PyInstaller scratch space and will fail with "Failed to load Python DLL" if launched directly. Prefer `build.bat` / `/build-exe` over `build_onefile.bat`, which duplicates PyInstaller flags manually and can drift from the `.spec`.

## Architecture

**Entrypoint**: `main.py` → `views/main_window.py:MainWindow`. `MainWindow` is the MVC glue: it owns the `ConfigModel` and `ScanModel`, constructs one controller per concern, constructs one page per sidebar item, and wires page `Signal`s to controller slots in `_connect()`.

**Navigation**: sidebar buttons + a `QStackedWidget` (`MainWindow._NAV`, `_build_ui`, `_navigate`) — not tabs. There is no page registry/plugin system; adding a page means manually touching four spots in `main_window.py`: the `_NAV` list, page construction + `self._stack.addWidget(...)` in `_build_ui`, the `idx` dict in `_navigate`, and signal wiring in `_connect`.

**Active pages** (all in `views/`, constructed by `MainWindow`):
- `document_page.py` (`DocumentPage`) — the main scan/import/correct/OCR/export workflow. A toolbar + thumbnail grid + viewer, with a right-hand `QTabWidget` (Info / Corrección / OCR / Exportar tabs). This is the largest and most central page.
- `pdf_page.py` (`EditorPage`) — reorder/organize previously-imported PDF pages and regenerate an organized PDF; also handles the "merge N whole PDF files into one" feature (`MainWindow._on_merge_pdfs`, using PyMuPDF `insert_pdf` + a per-source TOC bookmark).
- `visualization_page.py` (`VisualizationPage`) — scans a configured "Registros Civiles" folder tree (`{Categoría}/{Antecedentes|Registros}/Caja N/Carpeta N/{serial}.pdf`), matches Registros to Antecedentes by serial number *within the same category only*, shows match/orphan/duplicate statistics, and combines a matched pair into one PDF (record pages first). Scanning runs in a background `QRunnable`/`QThreadPool` and streams results in per-category so the UI never blocks; results are cached to `~/.miregistrodigital/visualization_cache.json` and reloaded instantly on next open while a fresh scan refreshes in the background. Tree rows must never use `QTreeWidget.setItemWidget()` per row — it has severe non-linear cost as row count grows and will hang the UI for any realistically large registry (confirmed by direct testing: a per-row embedded button made 6000 rows hang indefinitely; removing it in favor of a right-click context menu made the same case take <1s). Row actions use a context menu (`customContextMenuRequested`) with the `MatchPair` stored via `item.setData(0, Qt.ItemDataRole.UserRole, pair)`, not an embedded widget.
- `settings_page.py` (`SettingsPage`) — one `QGroupBox` per config section, each built by a private `_xxx_group()` method; `_load()`/`_save()` mirror `ConfigModel.get/set`. Emits `settings_saved`, which other pages connect to when they need to react to a config change made outside their own UI (e.g. `VisualizationPage.on_settings_saved`).

**Legacy/unused files — do not build on these without checking they're actually imported first**: `views/scan_page.py`, `views/registos_section.py`, `views/registos_bookmarks_page.py`, `views/registos_merge_page.py`, `views/civil_page.py`, `views/civil_view.py`, `views/antecedentes_page.py`, `views/antecedentes_view.py`, `views/scan_view.py`, `views/settings_view.py`, `views/thumbnail_strip.py`; `controllers/antecedentes_controller.py`, `controllers/civil_controller.py`, `controllers/file_import_controller.py`; `models/ocr_model.py`, `models/pdf_model.py`. They still exist on disk and can be useful as *visual reference* for a layout pattern, but `main.py`/`main_window.py` never import them. Check `views/main_window.py`'s import block before assuming any `views/` or `controllers/` file is live.

**Fully separate parallel implementation (also legacy)**: `backend/` (`models/`, `controllers/`, `bridge.py`) + `qml/` is a duplicated QtQuick/QML frontend, never imported by the running app. Business logic here is NOT kept in sync with the active `controllers/`/`models/` — ignore it unless explicitly asked to maintain the QML variant too.

**Controllers** (`QObject` subclasses owned by `MainWindow`, one per concern):
- `scan_controller.py` — TWAIN scanning + image/PDF import (background workers).
- `ocr_controller.py` — EasyOCR, per-page or batch, with configurable GPU/CPU and parallel workers.
- `export_controller.py` — civil/antecedentes export, concurrent jobs. This is the canonical example of the worker pattern used throughout: a `QRunnable` subclass with a nested `class S(QObject)` holding the `Signal`s (so the runnable itself doesn't need to be a `QObject`), connected by the caller after construction.
- `visualization_controller.py` — background directory scan + PDF combine, following the same `QRunnable` + `S(QObject)` pattern, plus a synchronous path for single-pair combine (fast enough not to need a worker).

**Models** (`models/`, pure data — no Qt widgets):
- `page_data.py` (`PageData`) — one scanned/imported page: `original_image`/`corrected_image` (numpy BGR arrays, OpenCV), `serial`/`serial_confidence` (OCR result), `bookmark(s)`, `comment`, `is_cut_point`, `source_path`/`source_page`. `display_image` returns corrected-if-present, `final_label` returns user_label → serial → fallback.
- `scan_model.py` (`ScanModel`) — in-memory list of `PageData` for the current session; `get_groups()` splits pages into contiguous groups by `is_cut_point`, which is how "antecedentes" numbering/export groups records.
- `job_model.py` (`Job`, `JobType`, `JobStatus`) — background job tracking shown in the "Procesos" status-bar button / `ProcessListDialog` (`views/widgets.py`).
- `project_model.py` — save/load a `.miregistro` project file (zip of page metadata + images), plus autosave to `~/.miregistrodigital/autosave.miregistro`.
- `config_model.py` (`ConfigModel`) — persists to `~/.miregistrodigital/config.json`. `DEFAULTS` dict defines all sections/keys; `load()` deep-merges saved JSON into `DEFAULTS`, so adding a new key/section is forward-compatible with existing users' config files automatically — no migration code needed. Auto-saved on `MainWindow.closeEvent`.
- `visualization_model.py` — `Category`/`Subcategory` enums, `PdfEntry`, `MatchPair` (with `is_matched`/`status`), `DuplicateEntry`, `ScanResult`, `CategoryBatch` (the incremental per-category scan payload).

**Image pipeline**: everything is `numpy.ndarray` in BGR (OpenCV convention). Images live in memory in `ScanModel` and are never written to disk mid-flow — only `utils/image_utils.py` (perspective correction, deskew, `enhance_for_ocr()` = CLAHE + binarization + morphology) and PDF export touch the actual bytes.

**PDF handling**: PyMuPDF (`fitz`) is the primary PDF engine everywhere (merge, TOC/bookmarks, rasterization); `pypdf` is only used as a page-count fallback when `fitz` import fails. `utils/file_utils.py` has the shared PDF/file helpers (`sanitize`, `unique`, `build_zip`, `images_to_pdf_bytes`, `combine_registro_antecedente`). Any new "merge PDF files together" logic should reuse the exact pattern in `MainWindow._on_merge_pdfs` / `combine_registro_antecedente` (`fitz.Document()` → `insert_pdf(src)` per source in order → build a TOC list → `save(..., garbage=4, deflate=True)`), not reinvent it.

**Directory scanning**: `utils/scan_utils.py` (`scan_root`, `normalize_name`/`match_category`/`match_subcategory`, `save_cache`/`load_cache`) is pure, Qt-free, and unit-testable in isolation (no app needed — `python -c "from utils.scan_utils import scan_root; ..."` against a temp directory tree is the fastest way to verify a change here). Category/subcategory folder-name matching is case/accent-insensitive via NFKD normalization, but does not correct genuine misspellings — an unrecognized folder name is silently skipped, not an error.

## Conventions

- `from __future__ import annotations` at the top of every `.py` file.
- Views emit `Signal`s; `MainWindow` connects them to controllers in `_connect()`. Views never call controllers directly. Background work uses `QRunnable` + `QThreadPool.globalInstance()`, with a nested `class S(QObject)` for signals when the runnable itself isn't a `QObject` (see `export_controller.py` / `visualization_controller.py` for the canonical shape).
- Colors/styling come from `views/theme.py` (`BG, SURFACE, SURFACE2, SURFACE3, BORDER, TEXT, TEXT_SEC, TEXT_DIM, ACCENT, ACCENT2, SUCCESS, WARNING, DANGER, INFO`); the global `STYLESHEET` is applied once in `main.py` so most standard widgets need no per-widget CSS. Page layout convention: `QVBoxLayout(self)` with zero margins, a fixed-height header `QFrame` (title + action buttons), then the main content area.
- A `QPushButton` is made "primary" via `btn.setProperty("primary", True)` (matches the `QPushButton[primary="true"]` QSS selector).
- Config: add new keys under a new or existing top-level section in `ConfigModel.DEFAULTS` (`models/config_model.py`); expose them via a new `_xxx_group()` method in `SettingsPage` following the existing `_output_group()`/`_visualization_group()` pattern (a `QLineEdit` + "Examinar" button calling `QFileDialog.getExistingDirectory`, wired through the page's private `_browse()` helper).
- OCR: EasyOCR downloads ~1.5GB of models on first use; GPU is configurable (`ocr.gpu`, default CPU/False) via `parallel_workers` (default 4).
- Font: `fonts/JetBrainsMonoNerdFont-Regular.ttf` is optional and gitignored — the app must handle its absence gracefully (it already does; don't add a hard dependency on it).
- A project-level Claude Code slash command exists at `.claude/commands/build-exe.md` for rebuilding the executable — use it instead of re-deriving the PyInstaller invocation from scratch.
