@echo off
REM ============================================================
REM  DocScan Pro — Compilar a .exe con PyInstaller
REM  Ejecutar desde la raíz del proyecto.
REM  Usa .venv si existe, si no usa el Python del sistema.
REM ============================================================
title DocScan Pro — Build
cd /d "%~dp0.."
echo.
echo  DocScan Pro — Build
echo  ===================
echo.

if not exist "main.py" (
    echo ERROR: No se encuentra main.py en %CD%
    pause & exit /b 1
)

REM --- Elegir Python del venv o del sistema ---
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

REM --- Limpiar builds anteriores ---
if exist "dist\DocScanPro"   rmdir /s /q "dist\DocScanPro"
if exist "build\DocScanPro"  rmdir /s /q "build\DocScanPro"
if exist "DocScanPro.spec"   del /f /q "DocScanPro.spec"

REM --- Build con el spec ---
echo.
echo  Ejecutando PyInstaller...
echo.

%PY% -m PyInstaller docscan_pro.spec

if errorlevel 1 (
    echo.
    echo  ERROR en la compilación.
    pause & exit /b 1
)

echo.
echo  ========================================
echo   LISTO: dist\DocScanPro\DocScanPro.exe
echo  ========================================
echo.
pause
