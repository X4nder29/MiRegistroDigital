@echo off
REM ============================================================
REM  MiRegistroDigital - Compilar a .exe (multi-archivo)
REM  Ejecutar desde la raiz del proyecto.
REM  Usa .venv si existe, si no usa el Python del sistema.
REM ============================================================
title MiRegistroDigital - Build
cd /d "%~dp0.."
echo.
echo  MiRegistroDigital - Build
echo  ==========================
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
REM  El directorio de trabajo de PyInstaller se llama como el .spec (docscan_pro),
REM  no como el "name=" definido dentro de este.
if exist "dist\MiRegistroDigital"  rmdir /s /q "dist\MiRegistroDigital"
if exist "build\docscan_pro"       rmdir /s /q "build\docscan_pro"

REM --- Build con el spec ---
echo.
echo  Ejecutando PyInstaller...
echo.

%PY% -m PyInstaller docscan_pro.spec

if errorlevel 1 (
    echo.
    echo  ERROR en la compilacion.
    pause & exit /b 1
)

REM --- Limpiar directorio de trabajo intermedio ---
REM  build\docscan_pro contiene una copia del bootloader SIN la carpeta
REM  _internal (esta solo se genera en dist\). Ejecutarla directamente
REM  falla con "Failed to load Python DLL". Se borra para no dejar un
REM  .exe roto junto al valido en dist\MiRegistroDigital\.
if exist "build\docscan_pro" rmdir /s /q "build\docscan_pro"

echo.
echo  ==========================================
echo   LISTO: dist\MiRegistroDigital\MiRegistroDigital.exe
echo  ==========================================
echo.
pause
