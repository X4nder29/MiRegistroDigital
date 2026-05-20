# DocScan Pro

Aplicación de escritorio en **Python + PySide6** (Widgets) para escanear, importar y organizar documentos físicos en dos modos especializados.

---

## Estructura del proyecto

```
docscan_pro/
├── main.py                      # Punto de entrada
├── requirements.txt
│
├── models/                      # Datos puros (sin UI)
│   ├── page_data.py             # Página escaneada + metadatos
│   ├── scan_model.py            # Lista de páginas de la sesión
│   ├── job_model.py             # Trabajos de exportación
│   └── config_model.py          # Configuración persistente (JSON)
│
├── controllers/                 # Lógica en hilos secundarios
│   ├── scan_controller.py       # TWAIN + importación de archivos
│   ├── ocr_controller.py        # EasyOCR por página o en batch
│   └── export_controller.py     # Exportación civil/antecedentes concurrente
│
├── views/                       # Interfaz PySide6 Widgets
│   ├── theme.py                 # Paleta en grises + QSS completo
│   ├── widgets.py               # ThumbnailGrid, ImageViewer, FullscreenViewer…
│   ├── scan_page.py             # Escaneo, importación, corrección
│   ├── registos_section.py      # Contenedor con sub-navegación
│   │   ├── civil_page.py        # Exportar PDF individual por serial OCR
│   │   ├── registos_bookmarks_page.py  # PDF único con marcadores por serial
│   │   └── registos_merge_page.py      # Unir PDFs con marcadores por archivo
│   ├── antecedentes_page.py     # Grid con cortes, área expandible
│   ├── jobs_page.py             # Trabajos concurrentes en tiempo real
│   ├── settings_page.py         # Configuración
│   └── main_window.py           # Ventana principal + sidebar + MVC glue
│
├── utils/
│   ├── image_utils.py           # OpenCV: perspectiva, rotación, OCR crop
│   └── file_utils.py            # ZIP, PDF, nombres de archivo
│
└── installer/
    └── build.bat                # Compilación a .exe con PyInstaller
```

---

## Instalación

```bash
# Python 3.11 recomendado
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Para importar PDFs (instala uno):
pip install pymupdf
```

## Ejecutar

```bash
python main.py
```

## Compilar a .exe

```bash
installer\build.bat
# → dist\DocScanPro\DocScanPro.exe
```

---

## Modos de uso

### Escanear / Importar
- **▶ Escanear** — usa el escáner TWAIN seleccionado (sin TWAIN entra en modo simulación).
- **🖼 Imágenes** — importa JPG, PNG, TIFF, BMP, WEBP (selección múltiple).
- **📄 PDF** — importa PDFs multipágina (requiere `pymupdf` o `pdf2image`).

### Registros Civiles
Tres sub-modos dentro de la sección **Registros**:

- **Exportar PDFs** — Cada página → un PDF individual cuyo nombre es el serial extraído por OCR. Los seriales son editables antes de exportar.
- **PDF con marcadores** — Genera un único PDF con todas las páginas; cada página tiene un marcador (bookmark) con su serial OCR.
- **Unir PDFs** — Selecciona una carpeta con PDFs y los fusiona en un solo documento; cada PDF original aparece como marcador en el resultado.

### Antecedentes
- Clic derecho en una miniatura → **Marcar como punto de corte** para separar grupos.
- **⊞ Ampliar área** oculta el panel lateral para ver más miniaturas.
- Doble clic en cualquier miniatura → **visor a pantalla completa** con navegación entre páginas.
- Se pueden lanzar varios trabajos de exportación a la vez.

### Trabajos
Panel **↻ Trabajos** muestra el progreso de todos los trabajos en tiempo real. Puedes lanzar exportaciones civiles y de antecedentes simultáneamente sin esperar a que termine ninguna.
