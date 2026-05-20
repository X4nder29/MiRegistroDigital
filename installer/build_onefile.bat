@echo off
REM ============================================================
REM  DocScan Pro — Build ONE-FILE (un solo .exe)
REM  Más portable pero más lento al iniciar y ocupa más RAM.
REM ============================================================
title DocScan Pro — One-File Build
cd /d "%~dp0.."
echo.
echo  DocScan Pro — One-File Build
echo  =============================
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

if exist "dist\DocScanPro.exe" del /f /q "dist\DocScanPro.exe"

echo  Ejecutando PyInstaller (one-file)...
echo.

%PY% -m PyInstaller main.py ^
    --onefile ^
    --windowed ^
    --name DocScanPro ^
    --add-data "fonts;fonts" ^
    --hidden-import controllers ^
    --hidden-import views ^
    --hidden-import models ^
    --hidden-import utils ^
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
    echo  ERROR en la compilación.
    pause & exit /b 1
)

echo.
echo  ========================================
echo   LISTO: dist\DocScanPro.exe
echo  ========================================
echo.
pause
