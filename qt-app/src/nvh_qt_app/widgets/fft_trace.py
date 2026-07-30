"""Live magnitude-vs-frequency trace: computes an FFT of the current
buffer and paints it over the graticule -- same paint-on-graticule
convention SignalTraceWidget uses for the raw time-series. Only
recomputes when the buffer changes and the widget is visible, so the
frequency-domain tab doesn't pay for the FFT while it's hidden."""

from __future__ import annotations

from collections import deque
from typing import Iterable

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from nvh_design_tokens import load_tokens

from .graticule import GraticuleWidget

_TRACE_STROKE_WIDTH = 1.5


class FftTraceWidget(GraticuleWidget):
    """Real-valued FFT magnitude spectrum of the last N samples --
    autoscaled to the current peak. Sample rate is passed in from the
    LiveSignalChunk that drove the buffer so the x-axis represents real
    Hz values (though we don't paint tick labels yet -- see the graticule
    itself for a follow-up)."""

    def __init__(self, max_samples: int = 4000, parent=None) -> None:
        super().__init__(parent)
        self._max_samples = max_samples
        self._buffer: deque[float] = deque(maxlen=max_samples)
        self._sample_rate_hz: float = 5000.0  # simulator default; overwritten by chunks

        tokens = load_tokens()
        self._trace_color = QColor(tokens["color"]["palettes"]["dark"]["accentPrimary"])

    def append_samples(self, samples: Iterable[float], sample_rate_hz: float | None = None) -> None:
        added = False
        for value in samples:
            self._buffer.append(float(value))
            added = True
        if sample_rate_hz:
            self._sample_rate_hz = sample_rate_hz
        if added:
            self.update()

    def clear(self) -> None:
        if not self._buffer:
            return
        self._buffer.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)

        if len(self._buffer) < 32:
            return

        width = self.width()
        height = self.height()
        if width <= 1 or height <= 1:
            return

        arr = np.asarray(self._buffer, dtype=float)
        # Simple rectangular window is fine for a live-monitor magnitude
        # display -- we're showing shape, not measuring absolute levels.
        spectrum = np.abs(np.fft.rfft(arr))
        if spectrum.size < 2:
            return
        # Drop DC bin so the visible dynamic range isn't dominated by
        # any mean offset in the incoming signal.
        spectrum = spectrum[1:]
        peak = float(spectrum.max())
        if peak <= 0.0:
            return
        normalized = spectrum / peak

        bins = normalized.size
        # Reserve the same top/bottom margin as the raw trace so peaks
        # don't paint on the graticule border.
        top_margin = height * 0.08
        bottom_margin = height * 0.08
        drawable = height - top_margin - bottom_margin

        polygon = QPolygonF()
        for i, value in enumerate(normalized):
            x = (i / (bins - 1)) * (width - 1)
            y = (height - bottom_margin) - value * drawable
            polygon.append(QPointF(x, y))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._trace_color)
        pen.setWidthF(_TRACE_STROKE_WIDTH)
        painter.setPen(pen)
        painter.drawPolyline(polygon)
        painter.end()
