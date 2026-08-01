"""Oscilloscope-style trace overlay: a ``GraticuleWidget`` that also keeps a
rolling buffer of the last N samples and paints them as a polyline on top of
its own grid. Callers push samples in with ``append_samples`` as
``LiveSignalChunk`` frames arrive, and the widget takes care of trimming to
the window size, auto-scaling the y-range, and repainting -- no external
plotting library involved (PySide6's ``QPainter.drawPolyline`` is enough for
one live trace, and matches the graticule's stroke conventions)."""

from __future__ import annotations

from collections import deque
from typing import Iterable

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from nvh_design_tokens import load_tokens

from .graticule import GraticuleWidget

_TRACE_STROKE_WIDTH = 1.5
# Small floor so an all-zero buffer doesn't divide by zero when auto-scaling
# and the trace collapses to a flat line at mid-height instead of vanishing.
_MIN_Y_SCALE = 1e-9


class SignalTraceWidget(GraticuleWidget):
    """``GraticuleWidget`` subclass that maintains a rolling buffer of
    samples and overpaints a polyline trace on top of the graticule grid.

    Auto-scales the y-axis to ``max(abs(buffer))`` on every repaint --
    for a live vibration signal the amplitude envelope drifts slowly
    enough that per-frame rescaling looks stable, and it means the trace
    never clips regardless of channel/gear."""

    def __init__(self, max_samples: int = 4000, parent=None) -> None:
        super().__init__(parent)
        self._max_samples = max_samples
        self._buffer: deque[float] = deque(maxlen=max_samples)

        tokens = load_tokens()
        self._trace_color = QColor(tokens["color"]["palettes"]["dark"]["accentSecondary"])

    def append_samples(self, samples: Iterable[float]) -> None:
        """Append samples to the rolling buffer (keeps the last
        ``max_samples``) and schedule a repaint. Safe to call with an
        empty iterable."""
        added = False
        for value in samples:
            self._buffer.append(float(value))
            added = True
        if added:
            self.update()

    def clear(self) -> None:
        """Drop all buffered samples and repaint an empty trace (grid
        only). Called on new-test-run transitions so a fresh acquisition
        doesn't start mid-scroll with the previous run's tail."""
        if not self._buffer:
            return
        self._buffer.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Draw the graticule background first so the trace sits on top
        # of the grid rather than under it. ``GraticuleWidget.paintEvent``
        # opens and closes its own QPainter -- Qt supports repeated
        # painters against the same widget within a single paintEvent as
        # long as each one is properly ended.
        super().paintEvent(event)

        if not self._buffer:
            return

        width = self.width()
        height = self.height()
        if width <= 1 or height <= 1:
            return

        buffer_len = len(self._buffer)
        # Anchor the trace so a partially filled buffer draws from the
        # left edge and grows to the right rather than always stretching
        # to fill the full width.
        window = max(buffer_len, 2)
        y_scale = max((abs(v) for v in self._buffer), default=0.0)
        if y_scale < _MIN_Y_SCALE:
            y_scale = _MIN_Y_SCALE

        mid_y = height / 2.0
        # Reserve a small margin so the extreme peaks don't paint on the
        # very top/bottom pixel row where they visually merge with the
        # graticule border.
        amplitude = mid_y * 0.9

        polygon = QPolygonF()
        for i, value in enumerate(self._buffer):
            x = (i / (window - 1)) * (width - 1)
            y = mid_y - (value / y_scale) * amplitude
            polygon.append(QPointF(x, y))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._trace_color)
        pen.setWidthF(_TRACE_STROKE_WIDTH)
        painter.setPen(pen)
        painter.drawPolyline(polygon)
        painter.end()
