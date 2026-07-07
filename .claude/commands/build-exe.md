---
description: Build the MiRegistroDigital distributable executable via PyInstaller
---

Build the Windows executable for this project and report the result.

1. Run `installer\build.bat` from the project root (via PowerShell or `cmd /c`, with stdin redirected from NUL so the script's trailing `pause` doesn't hang, e.g. `cmd /c "installer\build.bat < NUL"`). This cleans the previous `dist\MiRegistroDigital` and `build\docscan_pro` directories, then runs PyInstaller against `docscan_pro.spec`.
2. If the build fails, show the actual PyInstaller error output (don't swallow it) and stop — do not attempt fixes without being asked.
3. If it succeeds, confirm `dist\MiRegistroDigital\MiRegistroDigital.exe` exists and report its path, file size, and the total size of the `dist\MiRegistroDigital` folder (this is a onedir build — the whole folder must be distributed together, e.g. zipped).
4. Mention that `installer\build_installer.bat` can additionally produce a polished Inno Setup installer (`MiRegistroDigital_Installer.exe`), but only if Inno Setup 6 is installed (https://jrsoftware.org/isdl.php) — don't run it unless asked.

**Warning:** `dist\MiRegistroDigital\MiRegistroDigital.exe` is the only valid, runnable build. Anything under `build\` (e.g. `build\docscan_pro\`) is PyInstaller's intermediate work directory — it can contain a bootloader `.exe` copy with the same name/size but no `_internal` folder next to it, which fails with "Failed to load Python DLL" if launched directly. `build.bat` already deletes `build\docscan_pro` on every successful run to prevent this; never point users at anything under `build\`.

Note: the build bundles heavy dependencies (PyTorch, EasyOCR, OpenCV) and can take several minutes.
