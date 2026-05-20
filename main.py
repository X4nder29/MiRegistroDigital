"""MiRegistroDigital — Punto de entrada."""
import logging
import sys
import traceback
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase

from views.main_window import MainWindow
from views.theme import apply_palette, STYLESHEET


def exception_hook(exc_type, exc_value, exc_tb):
    logger = logging.getLogger("docscan")
    logger.critical("Excepción no capturada",
                    exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    sys.excepthook = exception_hook

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logger = logging.getLogger("docscan")

    # Capturar warnings de Qt
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType

    def qt_message_handler(msg_type, context, message):
        level = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.CRITICAL,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
            QtMsgType.QtInfoMsg: logging.INFO,
        }.get(msg_type, logging.WARNING)
        logger.log(level, "[Qt] %s", message)

    qInstallMessageHandler(qt_message_handler)
    logger = logging.getLogger("docscan")
    logger.info("=" * 60)
    logger.info("MiRegistroDigital iniciando")
    logger.info("=" * 60)

    app = QApplication(sys.argv)
    app.setApplicationName("MiRegistroDigital")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MiRegistroDigital")

    # ── Cargar fuente ──────────────────────────────────────────────
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    font_path = base / "fonts" / "JetBrainsMonoNerdFont-Regular.ttf"
    if font_path.exists():
        fid = QFontDatabase.addApplicationFont(str(font_path))
        if fid >= 0:
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                app.setFont(QFontDatabase.font(families[0], "Regular", 10))
                logger.info("Font JetBrainsMono NF cargado")
    else:
        logger.warning("Font JetBrainsMono NF no encontrado en %s", font_path)

    apply_palette(app)
    app.setStyleSheet(STYLESHEET)
    logger.info("Tema aplicado")

    window = MainWindow()
    window.showMaximized()
    logger.info("Ventana principal mostrada")
    try:
        exit_code = app.exec()
        logger.info("App finalizada con código %d", exit_code)
        sys.exit(exit_code)
    except Exception as e:
        logger.critical("Excepción no capturada en app.exec", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
