@echo off
REM ============================================================
REM  MiRegistroDigital - Build + Installer
REM
REM  1. Compila el .exe con PyInstaller (multi-archivo)
REM  2. Empaqueta el instalador con Inno Setup
REM
REM  Requisito: Inno Setup 6+ instalado en %ProgramFiles%
REM  Descargar: https://jrsoftware.org/isdl.php
REM ============================================================
title MiRegistroDigital - Build + Installer
cd /d "%~dp0.."
echo.
echo  MiRegistroDigital - Build + Installer
echo  =======================================
echo.

REM --- Paso 1: Build PyInstaller ---
echo  [1/2] Compilando .exe con PyInstaller...
echo.
call installer\build.bat
if errorlevel 1 (
    echo ERROR: Fallo en la compilacion PyInstaller.
    pause & exit /b 1
)

REM --- Paso 2: Compilar instalador ---
echo.
echo  [2/2] Compilando instalador con Inno Setup...
echo.
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\iscc.exe"
if not exist %ISCC% (
    set ISCC="%ProgramFiles%\Inno Setup 6\iscc.exe"
)
if not exist %ISCC% (
    echo.
    echo  ERROR: Inno Setup no encontrado.
    echo  Instalalo desde https://jrsoftware.org/isdl.php
    echo  o ejecuta solo installer\build.bat para obtener el .exe.
    pause & exit /b 1
)

%ISCC% installer\setup.iss
if errorlevel 1 (
    echo ERROR: Fallo al compilar el instalador.
    pause & exit /b 1
)

echo.
echo  ==========================================
echo   LISTO:
echo     .exe:    dist\MiRegistroDigital\MiRegistroDigital.exe
echo     instalador: dist\MiRegistroDigital_Installer.exe
echo  ==========================================
echo.
pause
