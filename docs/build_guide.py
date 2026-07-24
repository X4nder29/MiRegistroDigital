"""Genera docs/Guia_de_Usuario.pdf — captura screenshots reales de la app
(Digitalización y Visualización) y arma un manual paginado en español con fitz.Story.

Uso:
    .venv\\Scripts\\python.exe docs\\build_guide.py

No requiere escáner ni una carpeta real de Registros Civiles: construye datos de
muestra sintéticos (páginas "escaneadas" con PIL, un pequeño árbol de PDFs de
Registros Civiles con fitz) y una config aislada en un directorio temporal, así
que nunca toca ~/.miregistrodigital del usuario real.
"""
from __future__ import annotations

import base64
import io
import os
import re
import sys
import tempfile
from pathlib import Path

# ── Aislar la config ANTES de importar cualquier módulo de la app: ConfigModel
# y utils/scan_utils.py resuelven Path.home() al importarse (constantes de
# módulo), así que hay que redirigir HOME/USERPROFILE primero. ──
_SANDBOX = Path(tempfile.mkdtemp(prefix="miregistro_guide_"))
os.environ["USERPROFILE"] = str(_SANDBOX)
os.environ["HOME"] = str(_SANDBOX)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import fitz

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QBuffer, QIODevice, QEventLoop, QTimer
from PySide6.QtGui import QColor

DOCS_DIR = Path(__file__).resolve().parent
OUT_PDF = DOCS_DIR / "Guia_de_Usuario.pdf"


# ═══════════════════════════════════════════════════════════════════════════
#  Datos de muestra
# ═══════════════════════════════════════════════════════════════════════════

def make_sample_page(serial: str, title: str, tag_color: tuple[int, int, int]) -> np.ndarray:
    """Genera una imagen tipo 'documento escaneado' (BGR, como espera la app)."""
    W, H = 850, 1100
    img = Image.new("RGB", (W, H), (250, 249, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, W - 20, H - 20], outline=(60, 60, 60), width=3)
    try:
        f_title = ImageFont.truetype("arial.ttf", 30)
        f_body = ImageFont.truetype("arial.ttf", 16)
        f_serial = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        f_title = f_body = f_serial = ImageFont.load_default()
    d.text((60, 70), title, fill=(20, 20, 20), font=f_title)
    d.line([60, 120, W - 60, 120], fill=(150, 150, 150), width=2)
    y = 170
    for _ in range(16):
        w = np.random.randint(300, W - 140)
        d.rectangle([60, y, 60 + w, y + 10], fill=(210, 210, 205))
        y += 30
    d.rectangle([0, H - 90, W, H], fill=tag_color)
    if serial:
        d.text((W - 260, H - 65), f"N.º {serial}", fill=(255, 255, 255), font=f_serial)
    else:
        d.text((W - 260, H - 65), "(sin número visible)", fill=(255, 255, 255), font=f_body)
    arr = np.array(img)  # RGB
    return arr[:, :, ::-1].copy()  # -> BGR


def make_sample_pages():
    return [
        make_sample_page("00123456", "Acta de Nacimiento", (34, 139, 89)),
        make_sample_page("00123457", "Acta de Defunción", (217, 119, 6)),
        make_sample_page("", "Acta de Matrimonio", (185, 28, 28)),
        make_sample_page("00987654", "Acta de Nacimiento", (34, 139, 89)),
    ]


def make_sample_registry_tree() -> Path:
    """Construye un árbol de Registros Civiles de muestra: Categoría/Antecedentes|
    Registros/Caja N/Carpeta N/serial.pdf — con un caso emparejado, un huérfano de
    cada lado y un serial duplicado, para que las estadísticas de Visualización
    muestren contenido real."""
    root = _SANDBOX / "RegistrosCiviles"

    def make_pdf(path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        d = fitz.open()
        d.new_page(width=300, height=420)
        d.save(str(path))
        d.close()

    layout = [
        ("Defunción", "Registros",    "Caja 1", "Carpeta 1", "00045210"),
        ("Defunción", "Registros",    "Caja 1", "Carpeta 2", "00045288"),
        ("Defunción", "Antecedentes", "Caja 1", "Carpeta 1", "00045210"),
        ("Defunción", "Antecedentes", "Caja 2", "Carpeta 1", "00045340"),
        ("Defunción", "Antecedentes", "Caja 2", "Carpeta 2", "00045340"),  # duplicado
        ("Nacimiento", "Registros",    "Caja 1", "Carpeta 1", "00078001"),
        ("Nacimiento", "Antecedentes", "Caja 1", "Carpeta 1", "00078001"),
        ("Matrimonio", "Registros",    "Caja 1", "Carpeta 1", "00099120"),
        ("Matrimonio", "Antecedentes", "Caja 1", "Carpeta 1", "00099120"),
    ]
    for cat, sub, box, folder, serial in layout:
        make_pdf(root / cat / sub / box / folder / f"{serial}.pdf")
    return root


# ═══════════════════════════════════════════════════════════════════════════
#  Captura de pantallas
# ═══════════════════════════════════════════════════════════════════════════

def grab_b64(widget, max_width: int = 1100, target_width: int | None = None,
             max_aspect: float | None = None) -> str:
    """target_width scales to that exact width (up or down) — for small cropped
    panels, where CSS width:100% alone doesn't upscale a low-res source. max_width
    only caps (downscales) large full-window shots, never upscales. max_aspect
    (height/width) crops off the bottom of tall, mostly-empty panels (e.g. a
    right-side tab panel that's full window height but only has content up top) —
    fitz.Story falls back to natural (small) size instead of stretching an image
    to width:100% when the resulting height wouldn't fit on a page, so an
    un-cropped tall/narrow screenshot renders tiny instead of filling the width."""
    pix = widget.grab()
    if max_aspect and pix.height() > pix.width() * max_aspect:
        pix = pix.copy(0, 0, pix.width(), int(pix.width() * max_aspect))
    if target_width:
        pix = pix.scaledToWidth(target_width, Qt.SmoothTransformation)
    elif pix.width() > max_width:
        pix = pix.scaledToWidth(max_width, Qt.SmoothTransformation)
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pix.save(buf, "PNG")
    data = bytes(buf.data())
    buf.close()
    return base64.b64encode(data).decode("ascii")


def pump(ms: int = 150):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_signal(signal, timeout_ms: int = 20000):
    loop = QEventLoop()
    signal.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def capture_all() -> dict[str, str]:
    from views.main_window import MainWindow
    from views.theme import apply_palette, STYLESHEET, INFO
    from controllers.scan_controller import ScanController

    # La lista de dispositivos TWAIN se muestra igual con un ítem de muestra más
    # abajo, así que evitamos la llamada nativa real (twain.SourceManager) acá —
    # es una llamada síncrona a un driver físico que puede tardar o colgarse según
    # el estado del hardware/driver, algo irrelevante para capturas de pantalla.
    ScanController.list_scanner_sources = lambda self: []

    app = QApplication.instance() or QApplication(sys.argv)
    apply_palette(app)
    app.setStyleSheet(STYLESHEET)

    mw = MainWindow()
    mw.show()
    pump(300)  # deja asentar el refresco inicial de escáneres (QTimer.singleShot(0, ...))

    shots: dict[str, str] = {}

    # ── Home ──
    mw._navigate("home")
    pump(150)
    shots["home"] = grab_b64(mw)

    # ── Digitalización: estado vacío ──
    mw._navigate("documentos")
    pump(150)
    shots["dig_vacio"] = grab_b64(mw)

    # ── Digitalización: pestaña Escáner (dispositivo de muestra, no hay
    #    escáner físico en este entorno — solo para ilustrar el guía) ──
    dp = mw._doc_page
    dp._scan_device.clear()
    dp._scan_device.addItem("Kodak i2900 (TWAIN)")
    dp._show_scanner_tab()
    pump(150)
    shots["dig_escaner"] = grab_b64(dp._right_panel, target_width=820, max_aspect=1.3)

    # ── Cargar páginas de muestra ──
    pages_img = make_sample_pages()
    model = mw._model
    for pimg in pages_img:
        model.add_page(pimg, source="muestra")
    model.set_serial(0, "00123456", 0.92)
    model.set_bookmark(0, [(1, "Partida de Nacimiento")])
    model.set_comment(0, "Revisar sello borroso en la esquina inferior")
    model.toggle_cut(0)
    model.set_serial(1, "00123457", 0.55)
    model.set_serial(2, "", 0.0)
    model.set_serial(3, "00987654", 0.81)

    # NOTA: DigitizationPage.rebuild() tiene un bug de reentrancia — set_ocr_result()
    # hace blockSignals(True)/(False) por su cuenta dentro del bucle de rebuild(), lo
    # que desbloquea itemChanged a mitad de camino y puede disparar _ocr_on_item_changed
    # sobre una fila todavía a medio construir (columna inexistente -> AttributeError),
    # además de corromper el serial de esa página con "—" vía OCRController.override().
    # Se reporta aparte; acá solo evitamos pisarlo desconectando la señal temporalmente.
    dp._ocr_table.itemChanged.disconnect(dp._ocr_on_item_changed)
    dp.rebuild(model.pages)
    dp._ocr_table.itemChanged.connect(dp._ocr_on_item_changed)
    dp.show_page(0, model.get(0).display_image)
    # rebuild() solo llama a set_ocr_result() para páginas con pd.serial truthy, así
    # que un serial vacío se queda en "Pendiente" en vez de "Sin serial" — lo mismo
    # que pasaría en la app real si nunca se corrió el OCR en esa página. Para
    # ilustrar realmente el estado "Sin serial" (como si el OCR sí se hubiera
    # ejecutado y no hubiera encontrado nada), se llama al método público que usa
    # el flujo en vivo (MainWindow._on_ocr_result -> dp.set_ocr_result).
    dp.set_ocr_result(2, "", 0.0)
    # Cuarta fila: ilustrar el estado "Corregido" (edición manual de serial) sin
    # pasar por el diálogo — solo cosmético, para que la captura de la pestaña
    # OCR muestre los 4 estados posibles de una sola vez.
    row = dp._ocr_row_for(3)
    item = dp._ocr_table.item(row, dp.COL_STATUS)
    item.setText("Corregido")
    item.setForeground(QColor(INFO))
    pump(150)

    # ── Vista de trabajo completa (miniaturas + visor + panel) ──
    dp._tabs.setCurrentIndex(0)
    pump(100)
    shots["dig_loaded"] = grab_b64(mw)

    # A partir de acá, capturas recortadas solo al panel de pestañas de la derecha
    # (300-420px) — la ventana completa maximizada lo deja ilegible, apretado en
    # una franja angosta junto a un visor central mayormente vacío.
    panel = dp._right_panel

    # ── Info (pestaña 0) ──
    shots["dig_info"] = grab_b64(panel, target_width=820, max_aspect=1.3)

    # ── Corrección (pestaña 1) ──
    dp._rot_slider.setValue(6)
    dp._tabs.setCurrentIndex(1)
    pump(100)
    shots["dig_correccion"] = grab_b64(panel, target_width=820, max_aspect=1.3)

    # ── OCR (ahora en índice 2 — la pestaña Escáner se ocultó al haber páginas) ──
    dp._tabs.setCurrentIndex(2)
    pump(100)
    shots["dig_ocr"] = grab_b64(panel, target_width=820, max_aspect=1.3)

    # ── Exportar (índice 3) ──
    dp._export_folder.setText(r"C:\Documentos\MiRegistroDigital\Salida")
    dp._ant_chk_range.setChecked(True)
    dp._ant_desde.setValue(1)
    dp._ant_hasta.setValue(4)
    dp._tabs.setCurrentIndex(3)
    pump(100)
    shots["dig_exportar"] = grab_b64(panel, target_width=820, max_aspect=1.3)

    # ── Visualización ──
    viz_root = make_sample_registry_tree()
    mw._viz.set_root_folder(str(viz_root))
    mw._navigate("visualizacion")
    wait_signal(mw._viz.scan_done, timeout_ms=15000)
    pump(400)  # drenar la cola de inserción diferida del árbol (timer de 10ms)
    # Cosmético: el label ya muestra la ruta real (el sandbox temporal de esta
    # captura) — se reemplaza solo el texto mostrado por una ruta de ejemplo
    # presentable antes de la captura; no afecta el escaneo ya realizado.
    mw._viz_page._path_label.setText(r"C:\RegistrosCiviles")
    shots["viz_resultado"] = grab_b64(mw)

    # ── Ajustes (sección Visualización rellena, para mostrar dónde se configura) ──
    # Reemplaza el default_folder (que apuntaría al sandbox temporal de esta
    # captura) por una ruta de ejemplo presentable.
    mw._cfg.set("output", "default_folder", r"C:\Users\TuUsuario\Documents\MiRegistroDigital")
    mw._sett_page._load()
    mw._navigate("settings")
    pump(150)
    shots["ajustes"] = grab_b64(mw)

    mw.close()
    return shots


# ═══════════════════════════════════════════════════════════════════════════
#  Contenido del manual (HTML) y armado del PDF
# ═══════════════════════════════════════════════════════════════════════════

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; color:#1c1c22; font-size:11px; line-height:1.45; }
h1 { color:#3d3dbf; font-size:22px; border-bottom:2px solid #8888ff; padding-bottom:6px; margin-bottom:14px; }
h2 { color:#242433; font-size:16px; margin-top:22px; margin-bottom:8px; }
h3 { color:#242433; font-size:13px; margin-top:16px; margin-bottom:6px; }
p { margin:6px 0; }
ul, ol { margin:6px 0; padding-left:22px; }
li { margin:3px 0; }
.shot { display:block; width:100%; border:1px solid #b9b9c9; border-radius:4px; margin:10px 0 14px 0; }
.note { background-color:#f1f1fb; border:1px solid #8888ff; border-radius:6px; padding:10px 14px; margin:12px 0; }
.warn { background-color:#fff6e9; border:1px solid #d97706; border-radius:6px; padding:10px 14px; margin:12px 0; }
.kbd { background-color:#eeeef5; border:1px solid #c3c3d5; border-radius:3px; padding:1px 6px; font-family:'Consolas',monospace; font-size:10px; }
.tree { background-color:#f6f6fa; border:1px solid #c3c3d5; border-radius:6px; padding:10px 14px; font-family:'Consolas',monospace; font-size:10px; white-space:pre; }
table { border-collapse:collapse; width:100%; margin:8px 0; }
th, td { border:1px solid #c3c3d5; padding:4px 8px; text-align:left; font-size:10px; }
th { background-color:#eeeef5; }
.cover-title { font-size:34px; font-weight:bold; color:#3d3dbf; margin-top:160px; text-align:center; }
.cover-sub { font-size:15px; color:#55555f; text-align:center; margin-top:10px; }
.cover-tools { font-size:12px; color:#55555f; text-align:center; margin-top:60px; }
"""


_IMG_MARK = "\x00IMG:{}\x00"


def img(b64: str) -> str:
    """Placeholder token, not literal HTML — render_pdf() splits sections on this
    marker so every screenshot gets its own Story starting at the top of a fresh
    page. fitz.Story sizes a block image to *fit the remaining space on the
    current page* rather than truly stretching to width:100% — a screenshot
    placed after several paragraphs (little space left) renders tiny and
    left-aligned instead of filling the page width. Giving each image a fresh
    page guarantees a full page of room regardless of what text precedes it."""
    return _IMG_MARK.format(b64)


def build_sections(shots: dict[str, str]) -> list[tuple[str, int, str]]:
    """Devuelve [(titulo, nivel_toc, html), ...] — cada elemento arranca en página nueva."""
    sections = []

    sections.append(("Portada", 1, f"""
        <div class="cover-title">MiRegistroDigital</div>
        <div class="cover-sub">Guía de Usuario</div>
        <div class="cover-tools">Digitalización&nbsp;&nbsp;·&nbsp;&nbsp;Visualización&nbsp;&nbsp;·&nbsp;&nbsp;Bonus: VeraCrypt</div>
    """))

    sections.append(("Contenido", 1, """
        <h1>Contenido</h1>
        <ul>
            <li>Introducción</li>
            <li>Herramienta: Digitalización</li>
            <li>Herramienta: Visualización</li>
            <li>Bonus: Abrir un contenedor VeraCrypt</li>
        </ul>
    """))

    sections.append(("Introducción", 1, f"""
        <h1>Introducción</h1>
        <p>MiRegistroDigital acompaña todo el flujo de digitalización de documentos del
        Registro Civil: escanear o importar, corregir la imagen, reconocer automáticamente
        el número de serial de cada página y exportar en PDF de forma masiva — además de
        cruzar lo digitalizado contra la estructura de carpetas del Registro Civil para
        detectar qué está completo y qué falta.</p>
        <p>Al abrir la aplicación se muestra una pantalla de inicio con tres herramientas:
        <b>Digitalización</b>, <b>Editor</b> y <b>Visualización</b>. Esta guía cubre las dos
        primeras marcadas en negrita más adelante — Digitalización y Visualización — que son
        las herramientas principales del flujo de trabajo diario.</p>
        {img(shots['home'])}
        <p>Desde el menú <b>Archivo</b> (arriba a la izquierda, dentro de cualquier
        herramienta) se puede abrir y guardar el trabajo como un proyecto
        (<span class="kbd">.miregistro</span>), y volver a esta pantalla en cualquier momento
        con <b>Cerrar herramienta</b>. Los ajustes generales están disponibles desde el botón
        <b>Ajustes</b> (arriba a la derecha).</p>
    """))

    sections.append(("Herramienta: Digitalización", 1, f"""
        <h1>Herramienta: Digitalización</h1>
        <h2>Empezar</h2>
        <p>Al entrar a Digitalización sin ningún documento cargado se muestran tres opciones:</p>
        {img(shots['dig_vacio'])}
        <ul>
            <li><b>Importar</b> — abre un selector de archivos para cargar uno o varios PDF ya existentes.</li>
            <li><b>Escanear</b> — abre la vista de trabajo directamente en la pestaña Escáner, para revisar el dispositivo y las opciones antes de escanear (no dispara el escaneo de inmediato).</li>
            <li><b>Abrir proyecto</b> — retoma un proyecto <span class="kbd">.miregistro</span> guardado anteriormente.</li>
        </ul>
        <div class="note">Atajos de teclado: <span class="kbd">Ctrl+P</span> importa un PDF y
        <span class="kbd">Ctrl+K</span> inicia un escaneo directo con la configuración actual.
        Ambos son configurables desde Ajustes → Atajos de teclado.</div>

        <h2>Escanear con TWAIN</h2>
        <p>La pestaña <b>Escáner</b> (solo visible mientras no hay ninguna página cargada)
        permite elegir el dispositivo y sus opciones antes de escanear:</p>
        {img(shots['dig_escaner'])}
        <ul>
            <li><b>Dispositivo</b> — lista de escáneres TWAIN detectados; el botón de actualizar
            (junto al selector) vuelve a buscarlos. Si hay un Kodak S2070 conectado se selecciona
            automáticamente.</li>
            <li><b>Resolución (DPI)</b>, <b>Modo de color</b> (Color / Escala de grises /
            Blanco y negro) y <b>Origen</b> (Alimentador automático ADF o Cristal/Flatbed).</li>
            <li><b>Escaneo dúplex</b> — ambas caras, solo disponible con el alimentador ADF.</li>
        </ul>
        <p>El botón <b>Escanear</b> inicia la captura; <b>Cancelar escaneo</b> aparece
        mientras está en curso. Si no hay ningún escáner conectado, la aplicación lo indica con
        un mensaje claro en vez de fallar en silencio.</p>

        <h2>Revisar las páginas</h2>
        <p>Una vez hay contenido (escaneado, importado o de un proyecto abierto), la vista de
        trabajo se divide en tres paneles: la lista de miniaturas a la izquierda, el visor de
        la página actual en el centro (con zoom — <span class="kbd">Ctrl++</span>/
        <span class="kbd">Ctrl+-</span>/<span class="kbd">Ctrl+0</span>) y un panel con 5
        pestañas verticales a la derecha (con ícono; el nombre aparece al pasar el cursor).</p>
        {img(shots['dig_loaded'])}
        <p>Arrastrando una miniatura se reordenan las páginas. Con clic derecho sobre una
        miniatura aparece un menú con: añadir/quitar marcador, añadir/quitar comentario, marcar
        o quitar punto de corte, mover la página a una posición específica, y eliminar la
        página.</p>

        <h2>Pestaña Info</h2>
        {img(shots['dig_info'])}
        <p>Muestra el <b>serial detectado por OCR</b> de la página actual junto con su nivel de
        confianza, y un botón <b>Corregir serial…</b> para escribirlo manualmente si el
        reconocimiento falló. Debajo, la lista de <b>marcadores</b> de la página (con botones
        Añadir/Editar/Quitar) y un campo de <b>comentario</b> libre (hasta 500 caracteres).</p>
        <p>El checkbox <b>Punto de corte (inicia nuevo grupo)</b> marca la página actual como
        el inicio de un nuevo grupo dentro del proyecto; <b>Limpiar todos los cortes</b> quita
        todas las marcas de corte de una vez.</p>

        <h2>Pestaña Corrección</h2>
        {img(shots['dig_correccion'])}
        <p>El deslizador de <b>rotación fina</b> ajusta el ángulo de la página actual entre
        -45° y +45°; los botones <b>-90°</b>, <b>90°</b> y <b>180°</b> aplican giros rápidos de
        90 grados. <b>Auto corrección (perspectiva + deskew)</b> detecta los bordes del
        documento, endereza la perspectiva y corrige la inclinación automáticamente.
        <b>Restablecer original</b> descarta cualquier corrección y vuelve a la imagen tal como
        se escaneó o importó.</p>

        <h2>Pestaña OCR</h2>
        {img(shots['dig_ocr'])}
        <p>Cada fila de la tabla corresponde a una página, con su serial detectado, nivel de
        confianza y estado. <b>El reconocimiento de OCR no se ejecuta solo</b>: hay que
        seleccionar una fila y presionar <b>OCR página</b> (o hacer clic derecho → "Ejecutar
        OCR en esta página") para procesarla, una página a la vez. El campo de serial se puede
        editar directamente haciendo doble clic sobre la celda.</p>
        <table>
            <tr><th>Estado</th><th>Significado</th></tr>
            <tr><td>Pendiente</td><td>Todavía no se ejecutó el OCR en esa página</td></tr>
            <tr><td>OK</td><td>Serial detectado con confianza alta (≥70%)</td></tr>
            <tr><td>Baja confianza</td><td>Se detectó un serial, pero con poca certeza</td></tr>
            <tr><td>Sin serial</td><td>No se encontró ningún número en el margen analizado</td></tr>
            <tr><td>Corregido</td><td>El usuario editó el serial manualmente</td></tr>
        </table>
        <p>El campo <b>Hilos</b> controla cuántos trabajos de OCR corren en paralelo cuando se
        procesan varias páginas.</p>

        <h2>Pestaña Exportar</h2>
        {img(shots['dig_exportar'])}
        <p>Primero hay que elegir una <b>carpeta de destino</b> — todas las exportaciones la
        usan. El grupo <b>Registros Civiles</b> reúne todas las formas de exportar:</p>
        <ul>
            <li><b>Rango (Desde/Hasta)</b> — filtro opcional por número de página, aplica solo
            a "PDF único con marcadores" y "Varios PDFs por marcador".</li>
            <li><b>ZIP — un PDF por página (serial)</b> — un archivo PDF de una sola página por
            cada página del proyecto, nombrado con su serial.</li>
            <li><b>ZIP — un PDF por página (marcador)</b> — igual, pero nombrado con el
            marcador de esa página en vez del serial.</li>
            <li><b>PDF único con marcadores</b> — un solo PDF con todas las páginas del rango
            elegido, con los marcadores incrustados como índice/outline del PDF.</li>
            <li><b>Varios PDFs por marcador</b> — separa las páginas en varios PDFs: cada
            página que tiene un marcador inicia un nuevo archivo (esta exportación agrupa por
            <i>marcador</i>, no por "punto de corte" — son dos conceptos independientes).</li>
            <li><b>Exportar PDF original</b> — reconstruye el documento preservando las páginas
            PDF originales tal como se importaron, con los comentarios de cada página incluidos
            como nota al pie.</li>
            <li><b>Unir PDFs externos…</b> — una utilidad aparte: elige una carpeta cualquiera
            y une <i>todos</i> los PDF que contiene (en orden alfabético) en un solo archivo,
            sin depender del proyecto actualmente abierto.</li>
        </ul>
    """))

    sections.append(("Herramienta: Visualización", 1, f"""
        <h1>Herramienta: Visualización</h1>
        <h2>Configurar la carpeta raíz</h2>
        <p>Visualización necesita saber dónde está la carpeta de Registros Civiles en disco.
        Se configura desde <b>Ajustes → Visualización → Carpeta raíz</b>, o directamente desde
        la propia herramienta con el botón "Seleccionar carpeta" (o "Cambiar" una vez que ya
        hay una configurada).</p>
        {img(shots['ajustes'])}
        <p>La aplicación espera exactamente esta estructura de carpetas debajo de la raíz:</p>
        <div class="tree">Carpeta raíz/
  Defunción/
    Registros/
      Caja 1/Carpeta 1/00045210.pdf
    Antecedentes/
      Caja 1/Carpeta 1/00045210.pdf
  Nacimiento/
    Registros/...
    Antecedentes/...
  Matrimonio/
    Registros/...
    Antecedentes/...</div>
        <p>El nombre del archivo PDF (sin la extensión) tiene que ser un número — ese número es
        el <b>serial</b> que se usa para emparejar un Registro con su Antecedente
        correspondiente, dentro de la misma categoría.</p>

        <h2>Analizar y ver resultados</h2>
        <p>Al abrir la herramienta, o al presionar <b>Actualizar</b>, se analiza la carpeta
        raíz en segundo plano — los resultados de cada categoría van apareciendo a medida que
        se procesan, sin bloquear la interfaz.</p>
        {img(shots['viz_resultado'])}
        <p>El panel izquierdo muestra un árbol con cada serial encontrado, agrupado por
        categoría, con columnas de Serial, Estado y la ubicación (Caja/Carpeta) del Registro y
        del Antecedente. Se puede buscar por serial y ordenar por Serial o por Estado.</p>
        <p>El panel derecho resume las estadísticas: totales de Registros y Antecedentes,
        cuántos están <b>Emparejados</b>, cuántos están <b>Sin antecedente</b> o
        <b>Sin registro</b> (huérfanos de un lado), cuántos fueron marcados como
        <b>Anulados</b>, y cuántos seriales están <b>duplicados</b> dentro de la misma
        categoría/subcarpeta. Debajo hay listas navegables de huérfanos y duplicados — con
        doble clic se abre el PDF correspondiente en el visor predeterminado de Windows.</p>

        <h2>Combinar un Registro y su Antecedente</h2>
        <p>Sobre una fila emparejada, clic derecho → <b>Combinar</b> genera un solo PDF con las
        páginas del Registro primero y las del Antecedente después (con dos marcadores de PDF:
        "Registro" y "Antecedente"). Para combinar muchos pares de una sola vez, el botón
        <b>Combinar todos los emparejados</b> del encabezado pide una carpeta de destino y
        genera un archivo por cada par emparejado visible según el filtro activo.</p>
        <p>Sobre una fila huérfana o anulada, el menú contextual también permite <b>Marcar
        como anulado</b> / <b>Quitar anulación</b> — útil para descartar casos que no se van a
        resolver sin que sigan contando como pendientes.</p>

        <h2>Buscar y filtrar</h2>
        <p>El menú desplegable del encabezado filtra por categoría (Todas / Defunción /
        Nacimiento / Matrimonio) — afecta al árbol, las estadísticas y qué pares entran en la
        combinación masiva. El cuadro de búsqueda filtra el árbol en vivo por número de
        serial.</p>
    """))

    sections.append(("Bonus: VeraCrypt", 1, """
        <h1>Bonus: Abrir un contenedor VeraCrypt</h1>
        <p>VeraCrypt es una herramienta externa, independiente de MiRegistroDigital, usada para
        cifrar carpetas/archivos sensibles. Estos son los pasos generales para montar
        (abrir) un contenedor de archivo VeraCrypt ya existente:</p>
        <ol>
            <li>Abrir <b>VeraCrypt</b>.</li>
            <li>Elegir una <b>letra de unidad</b> libre en la lista (por ejemplo, <span class="kbd">Z:</span>).</li>
            <li>Presionar <b>Select File…</b> (Seleccionar archivo) y elegir el archivo contenedor VeraCrypt (por ejemplo, <span class="kbd">Registros.hc</span>).</li>
            <li>Presionar <b>Mount</b> (Montar).</li>
            <li>Escribir la <b>contraseña</b> del contenedor y confirmar.</li>
            <li>El contenido cifrado queda disponible como una unidad más en el
            <b>Explorador de Windows</b>, con la letra elegida — se puede navegar, copiar y
            abrir archivos con normalidad mientras esté montado.</li>
            <li>Al terminar de trabajar, volver a VeraCrypt, seleccionar la unidad montada y
            presionar <b>Dismount</b> (Desmontar) para cerrar el acceso — no dejar el
            contenedor montado sin necesidad.</li>
        </ol>
        <div class="warn">Esta sección es información general sobre VeraCrypt como programa de
        terceros — no forma parte de MiRegistroDigital. No incluye capturas de pantalla de
        VeraCrypt.</div>
    """))

    return sections


_IMG_SPLIT_RE = re.compile(r"\x00IMG:(.*?)\x00", re.DOTALL)


def _place_story(writer, html: str, page_count: int) -> int:
    """Renderiza un fragmento de HTML como su propio Story — begin_page() siempre
    arranca una página nueva en el writer, así que llamar a esto por fragmento es
    lo que le da a cada imagen su propia página (ver comentario en img())."""
    story = fitz.Story(html=html, user_css=CSS)
    more = 1
    while more:
        dev = writer.begin_page(fitz.paper_rect("a4"))
        more, _ = story.place(fitz.paper_rect("a4") + (40, 40, -40, -40))
        story.draw(dev)
        writer.end_page()
        page_count += 1
    return page_count


def render_pdf(sections: list[tuple[str, int, str]], out_path: Path):
    writer = fitz.DocumentWriter(str(out_path))
    toc: list[list] = []
    page_count = 0

    for title, level, html in sections:
        toc.append([level, title, page_count + 1])
        parts = _IMG_SPLIT_RE.split(html)
        # re.split with a capturing group alternates [text, mark, text, mark, ..., text]
        for i, part in enumerate(parts):
            is_image = i % 2 == 1
            if is_image:
                shot_html = f'<img class="shot" style="margin-top:0;" src="data:image/png;base64,{part}">'
                page_count = _place_story(writer, shot_html, page_count)
            elif part.strip():
                page_count = _place_story(writer, part, page_count)

    writer.close()

    doc = fitz.open(str(out_path))
    doc.set_toc(toc)
    doc.save(str(out_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    return page_count


def main():
    print(f"Sandbox de config aislado en: {_SANDBOX}")
    shots = capture_all()
    print(f"Capturadas {len(shots)} pantallas: {', '.join(shots)}")
    sections = build_sections(shots)
    pages = render_pdf(sections, OUT_PDF)
    print(f"PDF generado: {OUT_PDF} ({pages} páginas)")


if __name__ == "__main__":
    main()
