"""Oscilloscope-graticule grid background, matching the web frontend's
``.graticule-bg`` (see ``web-frontend/src/index.css``): a major division grid
at full opacity layered with a finer minor grid at reduced opacity, both
derived from ``design-tokens``' ``layout`` tokens rather than hardcoded.

Subscribes to the app-level ThemeManager so a dark/light flip repaints
the graticule against the fresh background."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from nvh_design_tokens import load_tokens

_MAJOR_SPACING_PX = 60
_MINOR_SPACING_PX = 12


class GraticuleWidget(QWidget):
    """A plot-area background: draw this widget behind live/plot content."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        tokens = load_tokens()
        layout = tokens["layout"]
        self._line_color = QColor(layout["graticuleColor"])
        self._stroke_width = layout["graticuleStrokeWidth"]
        self._minor_alpha = layout["graticuleMinorAlpha"]
        self._background = QColor(self._current_background())

        # Repaint on palette flips.
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)

    @staticmethod
    def _current_background() -> str:
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        palette_name = theme.palette_name if theme is not None else "dark"
        return load_tokens()["color"]["palettes"][palette_name]["background"]

    def _on_theme_changed(self, _palette_name: str) -> None:
        self._background = QColor(self._current_background())
        self.update()

    def _draw_grid(self, painter: QPainter, spacing: int, color: QColor) -> None:
        pen = QPen(color)
        pen.setWidthF(self._stroke_width)
        painter.setPen(pen)
        width, height = self.width(), self.height()
        x = 0
        while x <= width:
            painter.drawLine(x, 0, x, height)
            x += spacing
        y = 0
        while y <= height:
            painter.drawLine(0, y, width, y)
            y += spacing

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background)

        major_color = QColor(self._line_color)
        self._draw_grid(painter, _MAJOR_SPACING_PX, major_color)

        minor_color = QColor(self._line_color)
        minor_color.setAlphaF(self._minor_alpha)
        self._draw_grid(painter, _MINOR_SPACING_PX, minor_color)

        painter.end()
