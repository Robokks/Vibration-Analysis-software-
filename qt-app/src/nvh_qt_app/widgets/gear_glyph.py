"""The app's one signature element (per docs/design-tokens.md): a
meshing-gear-tooth glyph used as the live-test indicator, the PASS/FAIL stamp
outline, and a print watermark.

The source SVG (``design-tokens/.../assets/gear-glyph.svg``) leaves fill/
stroke as ``currentColor`` so "each renderer... applies its own palette from
tokens.json at draw time" (the asset's own doc comment). Qt's SVG renderer
has no notion of CSS ``currentColor``, so this module substitutes the actual
token color into the SVG text before handing it to QSvgRenderer — the Qt
side of that same contract.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from nvh_design_tokens import gear_glyph_path, load_tokens

_VIEWBOX_WIDTH = 132.0
_VIEWBOX_HEIGHT = 100.0
_GEAR_LEFT_CENTER = QPointF(42.0, 50.0)
_GEAR_RIGHT_CENTER = QPointF(98.0, 50.0)
_SPIN_INTERVAL_MS = 33
_GEAR_LEFT_DEGREES_PER_TICK = 360.0 / (6000.0 / _SPIN_INTERVAL_MS)
_GEAR_RIGHT_DEGREES_PER_TICK = -360.0 / (4500.0 / _SPIN_INTERVAL_MS)


def colored_svg_bytes(color: str) -> bytes:
    svg_text = gear_glyph_path().read_text(encoding="utf-8")
    return svg_text.replace("currentColor", color).encode("utf-8")


class GearGlyphWidget(QWidget):
    """Renders the gear-glyph asset. Pass ``spinning=True`` for the
    live-test indicator use (rotates #gear-left/#gear-right in opposite
    directions, per the asset's own doc comment)."""

    def __init__(self, color: str | None = None, spinning: bool = False, parent=None) -> None:
        super().__init__(parent)
        if color is None:
            tokens = load_tokens()
            color = tokens["color"]["palettes"]["dark"]["accentPrimary"]

        self._renderer = QSvgRenderer(colored_svg_bytes(color))
        self._spinning = spinning
        self._left_angle = 0.0
        self._right_angle = 0.0

        # QSvgRenderer.render(painter, elementId, rect) maps *that element's
        # own* bounding box onto `rect`, so passing the full glyph rect for
        # each gear independently would stretch each one to fill the whole
        # icon. Cache each element's bounds in the document's own coordinate
        # space up front and re-derive a correctly-scaled destination rect
        # for it at paint time instead (see _element_dest_rect).
        if spinning:
            self._left_bounds = self._renderer.boundsOnElement("gear-left")
            self._right_bounds = self._renderer.boundsOnElement("gear-right")

        self._timer: QTimer | None = None
        if spinning:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(_SPIN_INTERVAL_MS)

    def _tick(self) -> None:
        self._left_angle = (self._left_angle + _GEAR_LEFT_DEGREES_PER_TICK) % 360.0
        self._right_angle = (self._right_angle + _GEAR_RIGHT_DEGREES_PER_TICK) % 360.0
        self.update()

    def _glyph_rect(self) -> QRectF:
        """Largest centered rect matching the SVG's aspect ratio."""
        target_ratio = _VIEWBOX_WIDTH / _VIEWBOX_HEIGHT
        w, h = self.width(), self.height()
        if w / max(h, 1) > target_ratio:
            draw_h = h
            draw_w = h * target_ratio
        else:
            draw_w = w
            draw_h = w / target_ratio
        x = (w - draw_w) / 2
        y = (h - draw_h) / 2
        return QRectF(x, y, draw_w, draw_h)

    def _paint_glyph(self, painter: QPainter) -> None:
        rect = self._glyph_rect()
        if not self._spinning:
            self._renderer.render(painter, rect)
            return

        scale_x = rect.width() / _VIEWBOX_WIDTH
        scale_y = rect.height() / _VIEWBOX_HEIGHT

        def to_widget_rect(doc_bounds: QRectF) -> QRectF:
            return QRectF(
                rect.x() + doc_bounds.x() * scale_x,
                rect.y() + doc_bounds.y() * scale_y,
                doc_bounds.width() * scale_x,
                doc_bounds.height() * scale_y,
            )

        def render_element(element_id: str, doc_bounds: QRectF, center: QPointF, angle: float) -> None:
            painter.save()
            origin = QPointF(rect.x() + center.x() * scale_x, rect.y() + center.y() * scale_y)
            painter.translate(origin)
            painter.rotate(angle)
            painter.translate(-origin)
            self._renderer.render(painter, element_id, to_widget_rect(doc_bounds))
            painter.restore()

        render_element("gear-left", self._left_bounds, _GEAR_LEFT_CENTER, self._left_angle)
        render_element("gear-right", self._right_bounds, _GEAR_RIGHT_CENTER, self._right_angle)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_glyph(painter)
        painter.end()


class StampWidget(GearGlyphWidget):
    """The gear-glyph outline as a PASS/FAIL stamp, per docs/design-tokens.md
    ("the outline the PASS/FAIL stamp is cut into")."""

    def __init__(self, result: str, color: str, parent=None) -> None:
        super().__init__(color=color, spinning=False, parent=parent)
        self._result = result
        self._text_color = QColor(color)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(0.5)
        self._paint_glyph(painter)
        painter.setOpacity(1.0)

        font = QFont()
        font.setBold(True)
        font.setPointSize(16)
        painter.setFont(font)
        painter.setPen(self._text_color)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._result)
        painter.end()
