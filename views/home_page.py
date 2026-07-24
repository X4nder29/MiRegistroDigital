"""Pantalla de inicio — selector de las tres herramientas principales."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from views.theme import BG, SURFACE, SURFACE2, BORDER, TEXT, TEXT_SEC, ACCENT2


_TOOLS = [
    ("documentos",    "\U0001f4c4", "Digitalización"),
    ("pdf",           "\U0001f4cb", "Editor"),
    ("visualizacion", "\U0001f441️", "Visualización"),
]


class ToolCard(QFrame):
    """Tarjeta clicable con icono y texto explícitamente centrados (QVBoxLayout + AlignCenter,
    en vez de depender del layout interno de QToolButton para icono+texto)."""
    clicked = Signal()

    def __init__(self, emoji: str, label: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 170)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                background-color: {SURFACE2};
                border-color: {ACCENT2};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(12)

        icon = QLabel(emoji)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size:40pt; background:transparent; border:none;")
        lay.addWidget(icon, 0, Qt.AlignHCenter)

        text = QLabel(label)
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet(f"font-size:11pt; font-weight:600; color:{TEXT}; background:transparent; border:none;")
        lay.addWidget(text, 0, Qt.AlignHCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HomePage(QWidget):
    """Pantalla mostrada al iniciar la app: tres tarjetas para las herramientas principales."""
    tool_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeRoot")
        self.setStyleSheet(f"#homeRoot {{ background-color:{BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addStretch(2)

        title = QLabel("MiRegistroDigital")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size:28pt; font-weight:700; color:{TEXT}; letter-spacing:-0.5px;")
        root.addWidget(title)

        root.addSpacing(48)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(24)
        cards_row.addStretch(1)
        for key, emoji, label in _TOOLS:
            card = ToolCard(emoji, label)
            card.clicked.connect(lambda checked=False, k=key: self.tool_selected.emit(k))
            cards_row.addWidget(card)
        cards_row.addStretch(1)
        root.addLayout(cards_row)

        root.addStretch(3)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 24, 20)
        footer.addStretch(1)
        settings_btn = QPushButton("⚙️  Ajustes")
        settings_btn.setFixedHeight(32)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setFocusPolicy(Qt.NoFocus)
        settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SURFACE2};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 9pt;
                color: {TEXT_SEC};
            }}
            QPushButton:hover {{
                color: {TEXT};
                border-color: {ACCENT2};
            }}
        """)
        settings_btn.clicked.connect(lambda: self.tool_selected.emit("settings"))
        footer.addWidget(settings_btn)
        root.addLayout(footer)
