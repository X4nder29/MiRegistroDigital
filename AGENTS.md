# MiRegistroDigital (DocScan Pro)

Aplicación de escritorio Python/PySide6 para digitalización de documentos con escáner TWAIN, OCR (EasyOCR) y exportación a PDF.

## Comandos

```bash
.venv\Scripts\activate
pip install -r requirements.txt   # Python 3.11+ requerido
python main.py                    # Ejecutar (única forma de verificar)
installer\build.bat               # Compilar a .exe (multi-archivo)
installer\build_onefile.bat       # Compilar a .exe (un solo archivo)
```

No hay tests, linter, typechecker ni CI configurados.

## Arquitectura

- **Entrypoint**: `main.py` → `views/main_window.py:MainWindow`. `MainWindow` es el pegamento MVC que conecta señales entre páginas y controladores.
- **UI unificada**: `views/document_page.py` — sidebar con 3 items (Documentos, Trabajos, Ajustes). `DocumentPage` integra importación, corrección, OCR, marcadores/comentarios y exportación en una sola vista con toolbar + thumbnails + viewer + panel derecho de 4 tabs (Info/Corrección/OCR/Exportar).
- **Dos UIs paralelas (legacy)**: `views/` (Widgets PySide6 — activa) y `backend/` + `qml/` (QML QtQuick). La lógica de negocio duplicada en ambos lados. Cambios en `controllers/` deben replicarse en `backend/controllers/`.
- **Patrón señal/controlador**: Vistas emiten `Signal`, `MainWindow` las conecta a controladores (`QObject`). Exportación usa `QRunnable` + `QThreadPool` para concurrencia.
- **Pipeline imágenes**: Todo el stack usa `numpy.ndarray` BGR (OpenCV). Las imágenes nunca se guardan en disco durante el flujo — residen en `ScanModel` en memoria.
- **Config persistente**: `ConfigModel` guarda en `~/.miregistrodigital/config.json`. Se persiste automáticamente al cerrar (`MainWindow.closeEvent`).

## Convenciones

- `from __future__ import annotations` en todos los `.py`
- Señales Qt (`Signal`, `Slot`) para flujo asíncrono. Workers exportación son `QRunnable` con clase interna `S(QObject)` para señales.
- `PageData` (dataclass) mantiene `original_image` y `corrected_image`. `display_image` property retorna la corregida si existe.
- Temas oscuros definidos en `views/theme.py` (paleta + stylesheet QSS). Variables de color reusadas vía `from views.theme import BG, SURFACE, ...`.

## Peculiaridades

- **Archivos legacy**: `views/scan_page.py`, `views/registos_section.py`, `views/antecedentes_page.py` existen pero ya no se importan. La UI activa es `document_page.py`. Ídem `controllers/antecedentes_controller.py`, `controllers/civil_controller.py`, `controllers/file_import_controller.py` sin usar. La lógica activa está en `controllers/export_controller.py` y `controllers/ocr_controller.py`.
- **OCR**: EasyOCR con GPU configurable (`ConfigModel: ocr.gpu`, default CPU). Descarga modelos ~1.5GB al primer uso. `parallel_workers` default 4.
- **Sin tests**: Toda verificación es manual via `python main.py`.
- **Windows-only**: `pytwain` (TWAIN), batch files, paths Windows. Sin soporte cross-platform.
- **Fuente**: `fonts/JetBrainsMonoNerdFont-Regular.ttf` opcional, no en git (`.gitignore` lo excluye). Se ignora si falta.
- **Formato imagen**: Corrección de perspectiva y deskew con OpenCV (`image_utils.py`). OCR usa `enhance_for_ocr()` (CLAHE + binarización + morfología).
- **Build**: `build.bat` referencia `docscan_pro.spec` — ese archivo no existe en repo (generado por PyInstaller). Puede fallar si no se ha generado antes. Preferir `build_onefile.bat` para builds limpias.
