"""Paleta oscura clara — más luminosa, moderna, equilibrada."""
from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication


BG        = "#141418"
SURFACE   = "#1c1c22"
SURFACE2  = "#24242b"
SURFACE3  = "#2e2e36"
TEXT      = "#e8e8ee"
TEXT_SEC  = "#94949e"
TEXT_DIM  = "#5c5c68"
ACCENT    = "#c8c8d0"
ACCENT2   = "#8888ff"
SUCCESS   = "#56c98e"
WARNING   = "#e8b04c"
DANGER    = "#e85858"
INFO      = "#689cf8"

FONT_FAMILY = "'JetBrainsMono NF', 'Segoe UI'"


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

QPushButton {{
    background-color: {SURFACE2};
    color: {TEXT_SEC};
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {SURFACE3};
    color: {TEXT};
}}
QPushButton:pressed {{
    background-color: {BG};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
}}

QPushButton[primary="true"] {{
    background-color: {SURFACE3};
    color: {TEXT};
}}
QPushButton[primary="true"]:hover {{
    background-color: #383840;
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {SURFACE3};
}}

QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: none;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 26px;
    selection-background-color: {SURFACE3};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: none;
    border-radius: 4px;
    selection-background-color: {SURFACE3};
    color: {TEXT};
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 5px 10px;
    border-radius: 4px;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {SURFACE3};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 4px;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE3};
    border-radius: 2px;
    min-height: 24px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE3};
    border-radius: 2px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
}}

QTableWidget {{
    background-color: transparent;
    alternate-background-color: {SURFACE};
    gridline-color: transparent;
    border: none;
    color: {TEXT};
    selection-background-color: {SURFACE3};
}}
QTableWidget::item {{
    padding: 5px 10px;
    border-radius: 4px;
}}
QHeaderView::section {{
    background-color: transparent;
    color: {TEXT_SEC};
    border: none;
    border-bottom: 1px solid {SURFACE3};
    padding: 7px 10px;
    font-size: 9pt;
}}

QGroupBox {{
    border: none;
    border-radius: 8px;
    background-color: {SURFACE};
    margin-top: 12px;
    padding: 16px;
    font-size: 9pt;
    color: {TEXT_SEC};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0;
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
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    background: {SURFACE2};
}}
QCheckBox::indicator:checked {{
    background: {SURFACE3};
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
    background: {SURFACE3};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

QStatusBar {{
    background: {SURFACE};
    color: {TEXT_SEC};
    border: none;
    font-size: 9pt;
}}

QToolTip {{
    background: {SURFACE2};
    color: {TEXT};
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
}}

QMessageBox {{
    background: {SURFACE};
}}

QMenu {{
    background-color: {SURFACE};
    border: none;
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {SURFACE3};
    color: {TEXT};
}}
QMenu::separator {{
    background: {SURFACE3};
    height: 1px;
    margin: 4px 8px;
}}
"""
