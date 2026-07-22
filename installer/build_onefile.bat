@echo off
REM ============================================================
REM  MiRegistroDigital - Build ONE-FILE (un solo .exe)
REM  Mas portable pero mas lento al iniciar y ocupa mas RAM.
REM ============================================================
title MiRegistroDigital - One-File Build
cd /d "%~dp0.."
echo.
echo  MiRegistroDigital - One-File Build
echo  ====================================
echo.

if not exist "main.py" (
    echo ERROR: No se encuentra main.py en %CD%
    pause & exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    set PY=".venv\Scripts\python.exe"
) else (
    set PY=python
)

%PY% -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Instalando PyInstaller...
    %PY% -m pip install pyinstaller>=6.6.0
    if errorlevel 1 (
        echo ERROR: No se pudo instalar PyInstaller.
        pause & exit /b 1
    )
)

if exist "dist\MiRegistroDigital.exe" del /f /q "dist\MiRegistroDigital.exe"

REM --- Agregar fonts solo si existen ---
set FONTS_ARG=
if exist "fonts\*" set FONTS_ARG=--add-data "fonts;fonts"

echo  Ejecutando PyInstaller (one-file)...
echo.

%PY% -m PyInstaller main.py ^
    --onefile ^
    --windowed ^
    --name MiRegistroDigital ^
    %FONTS_ARG% ^
    --hidden-import controllers ^
    --hidden-import controllers.scan_controller ^
    --hidden-import controllers.ocr_controller ^
    --hidden-import controllers.export_controller ^
    --hidden-import views ^
    --hidden-import views.main_window ^
    --hidden-import views.widgets ^
    --hidden-import views.theme ^
    --hidden-import views.jobs_page ^
    --hidden-import views.settings_page ^
    --hidden-import models ^
    --hidden-import models.scan_model ^
    --hidden-import models.page_data ^
    --hidden-import models.config_model ^
    --hidden-import models.job_model ^
    --hidden-import utils ^
    --hidden-import utils.image_utils ^
    --hidden-import utils.file_utils ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtCore ^
    --hidden-import easyocr ^
    --hidden-import PIL ^
    --hidden-import pypdf ^
    --hidden-import fitz ^
    --hidden-import numpy ^
    --noconfirm

if errorlevel 1 (
    echo.
    echo  ERROR en la compilacion.
    pause & exit /b 1
)

echo.
echo  ==========================================
echo   LISTO: dist\MiRegistroDigital.exe
echo  ==========================================
echo.
pause
