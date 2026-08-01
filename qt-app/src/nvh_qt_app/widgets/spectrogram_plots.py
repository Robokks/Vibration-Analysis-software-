"""Three frequency-domain plot widgets sharing the same STFT input:

- ColorMapPlot -- 2D heatmap of |STFT| with frequency on Y and time on X.
- WaterfallPlot -- the same matrix rendered as N stacked spectrum
  slices with vertical offset + alpha fade (each slice is one point in
  time; the classic "waterfall over time" view).
- OctaveBarsPlot -- vertical bar chart of energy per octave band
  center frequency (ISO series). Takes bars directly rather than STFT.

All three subclass GraticuleWidget and repaint on theme_changed via
the widget's inherited palette subscription. No external plotting
library -- QPainter + QImage."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPolygonF,
)
from PySide6.QtWidgets import QApplication

from nvh_design_tokens import load_tokens

from .graticule import GraticuleWidget

# Viridis-inspired 6-stop LUT: purple-black -> teal -> yellow.
# Stored as (r, g, b) 0-255 tuples; the painter interpolates between
# stops to fill 256 quantized colors at render time.
_VIRIDIS_STOPS = (
    (68, 1, 84),
    (72, 40, 120),
    (62, 74, 137),
    (49, 104, 142),
    (33, 145, 140),
    (94, 201, 98),
    (253, 231, 37),
)


def _build_lut(stops: tuple[tuple[int, int, int], ...] = _VIRIDIS_STOPS) -> np.ndarray:
    """Return a (256, 4) RGBA lookup table by piecewise-linear interp
    across the stops. Used to translate a normalized magnitude in
    [0, 1] to a QRgb for QImage.setPixel."""
    n_stops = len(stops)
    arr = np.zeros((256, 4), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        idx = t * (n_stops - 1)
        lo = int(idx)
        hi = min(lo + 1, n_stops - 1)
        frac = idx - lo
        r = int(stops[lo][0] * (1 - frac) + stops[hi][0] * frac)
        g = int(stops[lo][1] * (1 - frac) + stops[hi][1] * frac)
        b = int(stops[lo][2] * (1 - frac) + stops[hi][2] * frac)
        arr[i] = (r, g, b, 255)
    return arr


_VIRIDIS_LUT = _build_lut()


def _muted_color() -> str:
    app = QApplication.instance()
    theme = getattr(app, "theme", None) if app is not None else None
    palette_name = theme.palette_name if theme is not None else "dark"
    return load_tokens()["color"]["palettes"][palette_name]["secondaryText"]


def _label_font() -> QFont:
    font = QFont()
    font.setFamily("IBM Plex Mono")
    font.setPointSizeF(8.5)
    return font


# ---- ColorMap -----------------------------------------------------


class ColorMapPlot(GraticuleWidget):
    """|STFT| heatmap. Set data via ``set_spectrogram(magnitude, times, freqs)``
    where magnitude is a (F, T) matrix, times is a T-length array of
    seconds, freqs is an F-length array of Hz."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._magnitude: np.ndarray | None = None
        self._times: np.ndarray | None = None
        self._freqs: np.ndarray | None = None

    def set_spectrogram(
        self, magnitude: np.ndarray, times: np.ndarray, freqs: np.ndarray,
    ) -> None:
        self._magnitude = np.asarray(magnitude, dtype=float)
        self._times = np.asarray(times, dtype=float)
        self._freqs = np.asarray(freqs, dtype=float)
        self.update()

    def clear(self) -> None:
        self._magnitude = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._magnitude is None or self._magnitude.size == 0:
            return
        width, height = self.width(), self.height()
        if width <= 40 or height <= 40:
            return

        # Reserve 44px on the left for a frequency Y-axis and 22px at
        # the bottom for the time X-axis.
        axis_left = 44
        axis_bottom = 22
        plot_w = width - axis_left - 8
        plot_h = height - axis_bottom - 8
        if plot_w <= 4 or plot_h <= 4:
            return

        # Autoscale to peak.
        mag = self._magnitude
        peak = float(mag.max()) if mag.size else 1.0
        if peak <= 0.0:
            peak = 1.0
        normalized = np.clip(mag / peak, 0.0, 1.0)

        # Build an RGBA image at (freq, time) resolution then scale to
        # the plot area via QPainter's smooth scaling.
        n_freq, n_time = normalized.shape
        img = QImage(n_time, n_freq, QImage.Format.Format_RGBA8888)
        indices = (normalized * 255).astype(np.uint8)
        # Flip vertically -- QImage y=0 is top, we want low freq at bottom.
        indices = np.flipud(indices)
        rgba = _VIRIDIS_LUT[indices]
        # Copy the numpy buffer into QImage. `bits()` returns a memoryview
        # sized to width*height*4 bytes.
        ptr = img.bits()
        ptr[:] = rgba.tobytes()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(
            QRectF(axis_left, 8, plot_w, plot_h),
            img, QRectF(0, 0, n_time, n_freq),
        )

        # Axis labels.
        axis_color = QColor(_muted_color())
        painter.setPen(QPen(axis_color))
        painter.setFont(_label_font())
        fm = QFontMetrics(_label_font())

        # Y (frequency): 5 ticks from freqs.min() to freqs.max().
        if self._freqs is not None and len(self._freqs) >= 2:
            f_lo, f_hi = float(self._freqs.min()), float(self._freqs.max())
            for i in range(5):
                t = i / 4
                y = 8 + (1 - t) * plot_h
                value = f_lo + t * (f_hi - f_lo)
                text = _format_hz(value)
                painter.drawText(4, int(y) + 4, text)
        # X (time): 5 ticks from times.min() to times.max().
        if self._times is not None and len(self._times) >= 2:
            t_lo, t_hi = float(self._times.min()), float(self._times.max())
            for i in range(5):
                frac = i / 4
                x = axis_left + frac * plot_w
                value = t_lo + frac * (t_hi - t_lo)
                text = f"{value:.2f}s"
                tw = fm.horizontalAdvance(text)
                painter.drawText(int(x) - tw // 2, height - 6, text)
        painter.end()


def _format_hz(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return f"{value:.0f}"


# ---- Waterfall ----------------------------------------------------


class WaterfallPlot(GraticuleWidget):
    """N stacked spectrum slices painted with vertical offset and alpha
    fade toward the oldest. Takes the same STFT matrix ColorMapPlot
    consumes; each column of the matrix becomes one slice."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._magnitude: np.ndarray | None = None
        self._freqs: np.ndarray | None = None

    def set_spectrogram(
        self, magnitude: np.ndarray, times: np.ndarray, freqs: np.ndarray,
    ) -> None:
        _ = times  # accepted for API symmetry; not needed in this projection
        self._magnitude = np.asarray(magnitude, dtype=float)
        self._freqs = np.asarray(freqs, dtype=float)
        self.update()

    def clear(self) -> None:
        self._magnitude = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._magnitude is None or self._magnitude.size == 0:
            return
        width, height = self.width(), self.height()
        if width <= 40 or height <= 40:
            return

        mag = self._magnitude
        peak = float(mag.max()) if mag.size else 1.0
        if peak <= 0.0:
            peak = 1.0
        normalized = mag / peak

        n_freq, n_time = normalized.shape
        # Subsample time frames so we don't paint 100+ overlapping polylines.
        max_frames = 20
        stride = max(1, n_time // max_frames)
        frame_indices = list(range(0, n_time, stride))

        left = 8
        right = width - 8
        top = 8
        bottom = height - 8
        plot_w = right - left
        plot_h = bottom - top
        # Each slice occupies half the plot height; consecutive slices
        # are offset by (plot_h * 0.5) / n_frames from front to back.
        slice_h = plot_h * 0.5
        offset_total = plot_h * 0.5
        n_frames = len(frame_indices)

        palette = load_tokens()["color"]["palettes"]
        accent = QColor(palette["dark"]["accentSecondary"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for i, frame_idx in enumerate(reversed(frame_indices)):
            spectrum = normalized[:, frame_idx]
            # Front slice = i=0 (fully opaque), back slice fades.
            depth = i / max(1, n_frames - 1)
            alpha = int(255 * (1.0 - 0.75 * depth))
            color = QColor(accent)
            color.setAlpha(alpha)
            pen = QPen(color, 1.2)
            painter.setPen(pen)

            y_offset = depth * offset_total
            base_y = top + y_offset + slice_h
            polygon = QPolygonF()
            for j, value in enumerate(spectrum):
                x = left + (j / max(1, n_freq - 1)) * plot_w
                y = base_y - float(value) * slice_h
                polygon.append(QPointF(x, y))
            painter.drawPolyline(polygon)

        painter.end()


# ---- Octave bars --------------------------------------------------


class OctaveBarsPlot(GraticuleWidget):
    """Vertical bars, one per octave-band center frequency. Set data
    via ``set_bands(centers_hz, rms)`` where the two arrays align."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._centers: list[float] = []
        self._rms: list[float] = []

    def set_bands(self, centers_hz, rms) -> None:
        self._centers = list(map(float, centers_hz))
        self._rms = list(map(float, rms))
        self.update()

    def clear(self) -> None:
        self._centers = []
        self._rms = []
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._centers or not self._rms:
            return
        width, height = self.width(), self.height()
        if width <= 40 or height <= 40:
            return

        axis_left = 48
        axis_bottom = 22
        plot_w = width - axis_left - 8
        plot_h = height - axis_bottom - 8
        if plot_w <= 4 or plot_h <= 4:
            return

        peak = max(self._rms) if self._rms else 1.0
        if peak <= 0.0:
            peak = 1.0

        palette = load_tokens()["color"]["palettes"]["dark"]
        bar_color = QColor(palette["accentPrimary"])
        axis_color = QColor(_muted_color())

        painter = QPainter(self)
        painter.setFont(_label_font())
        fm = QFontMetrics(_label_font())

        n = len(self._centers)
        gap = 4
        bar_w = max(4, (plot_w - gap * (n + 1)) / n)

        # Bars.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bar_color))
        for i, (center, value) in enumerate(zip(self._centers, self._rms)):
            x = axis_left + gap + i * (bar_w + gap)
            h = (value / peak) * plot_h
            y = 8 + plot_h - h
            painter.drawRect(QRectF(x, y, bar_w, h))

        # X-axis center-frequency labels.
        painter.setPen(QPen(axis_color))
        for i, center in enumerate(self._centers):
            x = axis_left + gap + i * (bar_w + gap) + bar_w / 2
            text = _format_hz(center)
            tw = fm.horizontalAdvance(text)
            painter.drawText(int(x - tw / 2), height - 6, text)

        # Y-axis: 5 ticks from 0 to peak.
        for i in range(5):
            t = i / 4
            y = 8 + (1 - t) * plot_h
            value = t * peak
            text = f"{value:.3g}"
            tw = fm.horizontalAdvance(text)
            painter.drawText(axis_left - tw - 4, int(y) + fm.ascent() // 2 - 1, text)

        painter.end()
