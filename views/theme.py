"""Paleta oscura estilo Vercel/GitHub — minimal, limpia, moderna."""
import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication


# Contraste calibrado contra referencias de UI oscura reales (GitHub/Vercel/
# Linear). Para texto se usa la razón WCAG; para superficies contiguas se usa
# el delta de luminosidad perceptual L*, porque cerca del negro la razón WCAG
# se comprime hacia 1 y deja de describir lo que el ojo ve.
BG        = "#0a0a0b"   # lienzo (ancla, sin cambios)
SURFACE   = "#131316"   # islas/tarjetas   — dL* 3.2 sobre el lienzo
SURFACE2  = "#1b1b1f"   # controles/inset  — relleno de inputs y botones
SURFACE3  = "#26262c"   # hover/selección  — dL* 5.5 sobre SURFACE2
BORDER    = "#303038"   # divisores        — dL* 17.4 (nivel GitHub dark)
BORDER_STRONG = "#3a3a43"  # límite de control (input/botón) — dL* 22 (Vercel)
TEXT      = "#f2f2f4"   # 17.7:1 sobre el lienzo
TEXT_SEC  = "#adadb8"   # 9.3:1  — etiquetas
TEXT_DIM  = "#8f8f9a"   # 6.2:1  — metadatos (antes 4.1:1, bajo mínimo AA)
DISABLED  = "#5f5f6b"   # inactivo: perceptible pero claramente apagado
# Superficies flotantes (menús y desplegables). Un popup se dibuja ENCIMA de
# otra superficie, así que necesita su propio nivel: con SURFACE quedaba a
# dL* 0.0 de una isla SURFACE, es decir, se fundía con el fondo de detrás.
POPUP     = "#212127"   # dL* +7.0 sobre una isla, +10.2 sobre el lienzo
POPUP_SEL = "#33333d"   # fila resaltada: dL* +8.7 sobre el propio popup
ACCENT    = "#e8e8ee"
ACCENT2   = "#8888ff"
SUCCESS   = "#22c55e"
WARNING   = "#f59e0b"
DANGER    = "#ef4444"
INFO      = "#3b82f6"

FONT_FAMILY = "'Segoe UI', 'Inter', -apple-system, sans-serif"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def pill_qss(color: str) -> str:
    """Estilo de insignia/pill: fondo tenue del color semántico, texto en ese color.
    Usado para comunicar estado (OCR, coincidencias) de forma consistente en toda la app."""
    return (
        f"background-color: {_hex_to_rgba(color, 0.14)};"
        f"color: {color};"
        f"border: 1px solid {_hex_to_rgba(color, 0.3)};"
        f"border-radius: 8px;"
        f"padding: 1px 8px;"
        f"font-size: 8pt;"
        f"font-weight: 600;"
    )


def _resource_dir() -> Path:
    """Carpeta `resources/` tanto en desarrollo como en el .exe de PyInstaller."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root / "resources"


_RES = _resource_dir()
_CHEVRONS = ("chevron_up.svg", "chevron_down.svg",
             "chevron_up_dim.svg", "chevron_down_dim.svg")


def _chevron_url(name: str) -> str:
    return f'url("{(_RES / name).as_posix()}")'


# Ancho de la columna de los botones +/- del QSpinBox. Estrecha a propósito:
# varios spinboxes de la app miden solo 55-80 px y el número es el contenido,
# los steppers son secundarios.
_STEPPER_W = 18

# Estilo de los botones de incremento/decremento de TODOS los campos numéricos.
# Qt deja de dibujar la flecha nativa en cuanto se aplica cualquier regla a
# ::up-button, así que las flechas son SVG propios (probado: el truco CSS del
# triángulo con bordes se dibuja como un rectángulo en Qt, no como flecha).
# Si los SVG faltasen, se deja el render nativo en vez de un botón sin flecha.
if all((_RES / n).exists() for n in _CHEVRONS):
    _SPINBOX_STEPPER_QSS = f"""
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    background: transparent;
    border: none;
    border-left: 1px solid {BORDER};
    width: {_STEPPER_W}px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
    margin: 1px 1px 0 0;
    border-top-right-radius: 5px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
    margin: 0 1px 1px 0;
    border-bottom-right-radius: 5px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {SURFACE3};
}}
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background: #2f2f36;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: {_chevron_url("chevron_up.svg")};
    width: 10px;
    height: 6px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: {_chevron_url("chevron_down.svg")};
    width: 10px;
    height: 6px;
}}
QSpinBox::up-arrow:off, QSpinBox::up-arrow:disabled,
QDoubleSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:disabled {{
    image: {_chevron_url("chevron_up_dim.svg")};
}}
QSpinBox::down-arrow:off, QSpinBox::down-arrow:disabled,
QDoubleSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:disabled {{
    image: {_chevron_url("chevron_down_dim.svg")};
}}
"""
else:
    _SPINBOX_STEPPER_QSS = ""


COMPACT_LIST_QSS = f"""
    QListWidget {{
        background-color: {SURFACE2};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 2px;
        font-size: 8pt;
    }}
    QListWidget::item {{
        padding: 3px 6px;
        border-radius: 4px;
    }}
    QListWidget::item:selected {{
        background-color: {SURFACE3};
        color: {TEXT};
    }}
"""


def apply_palette(app: QApplication):
    app.setFont(QFont(FONT_FAMILY, 10))
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(BG))
    p.setColor(QPalette.WindowText,      QColor(TEXT))
    p.setColor(QPalette.Base,            QColor(SURFACE2))
    p.setColor(QPalette.AlternateBase,   QColor(SURFACE3))
    p.setColor(QPalette.Text,            QColor(TEXT))
    p.setColor(QPalette.Button,          QColor(SURFACE))
    p.setColor(QPalette.ButtonText,      QColor(TEXT))
    p.setColor(QPalette.Highlight,       QColor(SURFACE3))
    p.setColor(QPalette.HighlightedText, QColor(TEXT))
    p.setColor(QPalette.PlaceholderText, QColor(TEXT_DIM))
    p.setColor(QPalette.Disabled, QPalette.Text,       QColor(TEXT_DIM))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(TEXT_DIM))
    app.setPalette(p)


STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: {FONT_FAMILY};
    font-size: 10pt;
}}
QMainWindow, QDialog {{
    background-color: {BG};
}}
QLabel {{
    background: transparent;
}}

/* Un botón debe leerse como un objeto, no como una etiqueta flotante: lleva
   relleno propio además del borde. Antes era transparente con un borde de
   1.3:1, prácticamente invisible sobre el lienzo. */
QPushButton {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    /* min-height + padding fijan un mínimo de 32 px (20+10+2). Antes daba 42 px
       y, como el min-height de la hoja de estilo gana sobre setFixedHeight(),
       ningún botón respetaba su altura explícita: los de 32/34 px se dibujaban
       a 42 y se salían de las barras de 44 px. */
    padding: 5px 16px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {SURFACE3};
    border-color: #4a4a55;
    color: {TEXT};
}}
QPushButton:pressed {{
    background-color: #2f2f36;
}}
QPushButton:disabled {{
    background-color: {SURFACE};
    color: {DISABLED};
    border-color: {BORDER};
}}

/* La acción primaria gana por inversión de valor, no por un gris un punto más
   claro: relleno claro sobre lienzo oscuro, 16:1. Es el único elemento de la
   pantalla que invierte, así que no compite con nada. */
QPushButton[primary="true"] {{
    background-color: {ACCENT};
    color: {BG};
    border: 1px solid {ACCENT};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background-color: #ffffff;
    border-color: #ffffff;
}}
QPushButton[primary="true"]:pressed {{
    background-color: #d4d4dc;
    border-color: #d4d4dc;
}}
QPushButton[primary="true"]:disabled {{
    background-color: {SURFACE3};
    color: {DISABLED};
    border-color: {BORDER};
}}

/* Acciones apiladas a ancho completo en los paneles laterales. Centrar
   etiquetas de largo dispar crea un arranque irregular y obliga al ojo a
   volver a buscar el inicio de cada texto; alineadas a la izquierda la
   columna se lee de un vistazo, como un menú. */
QPushButton[align="left"] {{
    text-align: left;
    padding-left: 12px;
}}

QPushButton[danger="true"] {{
    color: {DANGER};
    border-color: {DANGER};
}}
QPushButton[danger="true"]:hover {{
    background-color: {_hex_to_rgba(DANGER, 0.12)};
    border-color: {DANGER};
    color: {DANGER};
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {SURFACE3};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    color: {DISABLED};
    border-color: {BORDER};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {INFO};
}}

QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 26px;
    selection-background-color: {SURFACE3};
}}
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {DISABLED};
    border-color: {BORDER};
}}
/* Sin padding-right: Qt ya descuenta el ancho de los botones del área de
   texto. Añadirlo aquí lo restaría dos veces y recortaría el número. */
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {INFO};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {POPUP};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    selection-background-color: {POPUP_SEL};
    color: {TEXT};
    padding: 4px;
    outline: none;              /* sin recuadro punteado de foco */
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
    color: {TEXT_SEC};
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {SURFACE3};
    color: {TEXT};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {POPUP_SEL};
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #55555f;
}}
QScrollBar::handle:vertical:pressed {{
    background: #6b6b76;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #55555f;
}}
QScrollBar::handle:horizontal:pressed {{
    background: #6b6b76;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

QTableWidget {{
    background-color: transparent;
    alternate-background-color: {SURFACE};
    gridline-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT};
    selection-background-color: {SURFACE3};
}}
QTableWidget::item {{
    padding: 6px 12px;
    border-radius: 4px;
}}
QHeaderView::section {{
    background-color: transparent;
    color: {TEXT_SEC};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 12px;
    font-size: 9pt;
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {SURFACE};
    /* Margen amplio arriba: separa el título del contenido anterior y le da
       aire al nombre de la isla; padding generoso para que las opciones no
       queden pegadas al borde ni al título. */
    margin-top: 22px;
    padding: 20px 18px 18px 18px;
    font-size: 9pt;
    color: {TEXT_SEC};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 2px 8px;
    font-weight: 600;
}}

QProgressBar {{
    background: {SURFACE2};
    border: none;
    border-radius: 2px;
    height: 3px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 2px;
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT};
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_STRONG};
    background: {SURFACE2};
}}
QCheckBox::indicator:hover {{
    border-color: #55555f;
}}
QCheckBox:disabled {{
    color: {DISABLED};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT2};
    border-color: {ACCENT2};
}}

QSlider::groove:horizontal {{
    height: 3px;
    background: {SURFACE2};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -6px 0;
    background: {ACCENT};
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {SURFACE3};
    border-radius: 2px;
}}

QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

QStatusBar {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    border-top: 1px solid {BORDER};
    font-size: 8pt;
}}
QStatusBar::item {{
    border: none;
}}

/* Mismo nivel flotante que menús y desplegables: un tooltip también se dibuja
   encima de otra superficie y necesita despegarse de ella. */
QToolTip {{
    background: {POPUP};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    padding: 6px 10px;
    border-radius: 4px;
}}

QMessageBox {{
    background: {SURFACE};
}}

QMenu {{
    background-color: {POPUP};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 4px;
    color: {TEXT_SEC};
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {POPUP_SEL};
    color: {TEXT};
}}
QMenu::item:disabled {{
    color: {DISABLED};
}}
QMenu::separator {{
    background: {BORDER_STRONG};
    height: 1px;
    margin: 4px 8px;
}}
""" + _SPINBOX_STEPPER_QSS
