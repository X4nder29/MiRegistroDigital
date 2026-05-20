"""Paleta oscura estilo Vercel/GitHub — minimal, limpia, moderna."""
from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication


BG        = "#0a0a0b"
SURFACE   = "#111113"
SURFACE2  = "#18181b"
SURFACE3  = "#202023"
BORDER    = "#27272a"
TEXT      = "#ededef"
TEXT_SEC  = "#a1a1aa"
TEXT_DIM  = "#71717a"
ACCENT    = "#e8e8ee"
ACCENT2   = "#8888ff"
SUCCESS   = "#22c55e"
WARNING   = "#f59e0b"
DANGER    = "#ef4444"
INFO      = "#3b82f6"

FONT_FAMILY = "'Segoe UI', 'Inter', -apple-system, sans-serif"


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
    background-color: transparent;
    color: {TEXT_SEC};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 16px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {SURFACE};
    border-color: {SURFACE3};
    color: {TEXT};
}}
QPushButton:pressed {{
    background-color: {SURFACE2};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: transparent;
}}

QPushButton[primary="true"] {{
    background-color: {SURFACE3};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QPushButton[primary="true"]:hover {{
    background-color: #2a2a2e;
    border-color: #3a3a3e;
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {SURFACE3};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {INFO};
}}

QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 26px;
    selection-background-color: {SURFACE3};
}}
QSpinBox:focus, QComboBox:focus {{
    border-color: {INFO};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
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
    width: 8px;
    margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3f3f46;
}}
QScrollBar::handle:vertical:pressed {{
    background: #52525b;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #3f3f46;
}}
QScrollBar::handle:horizontal:pressed {{
    background: #52525b;
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
    border: 1px solid {BORDER};
    background: {SURFACE2};
}}
QCheckBox::indicator:hover {{
    border-color: {SURFACE3};
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
    font-size: 8pt;
}}

QToolTip {{
    background: {SURFACE2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 10px;
    border-radius: 4px;
}}

QMessageBox {{
    background: {SURFACE};
}}

QMenu {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
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
    background: {BORDER};
    height: 1px;
    margin: 4px 8px;
}}
"""
