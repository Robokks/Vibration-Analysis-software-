from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from nvh_design_tokens import load_tokens

from .theme import build_stylesheet
from .theme_manager import ThemeManager
from .widgets.app_shell import MainWindow
from .widgets.gear_glyph import colored_svg_bytes


def _window_icon() -> QIcon:
    tokens = load_tokens()
    accent = tokens["color"]["palettes"]["dark"]["accentPrimary"]
    renderer = QSvgRenderer(colored_svg_bytes(accent))

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def main() -> int:
    app = QApplication(sys.argv)
    # Attach the theme manager to the QApplication so any widget can
    # reach it via QApplication.instance().theme without threading it
    # through constructors.
    theme = ThemeManager()
    app.theme = theme
    app.setStyleSheet(build_stylesheet(theme.palette_name))
    # Whenever the palette flips, rebuild the QSS from tokens. Widgets
    # with inline styles wire their own theme_changed handlers.
    theme.theme_changed.connect(lambda name: app.setStyleSheet(build_stylesheet(name)))
    app.setWindowIcon(_window_icon())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
