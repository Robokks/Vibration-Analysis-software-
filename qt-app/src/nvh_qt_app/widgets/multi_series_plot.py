"""Multi-Y-axis live plot -- one plot area, N named series, each with
its own stacked Y-axis column on the left. Matches the real LabVIEW
NVH TEST SCREEN.vi's Computed sub-tab where SPEED / CREST / PEAK / RMS
/ KURTOSIS / SKEWNESS / VARIANCE / MEAN each have their own scale
range and share a common time axis on the right.

Draws its own graticule + axes + traces via QPainter (no external
plotting library). Cursor + right-click config menu match the LabVIEW
plot's ``Plot Visible / Color / Line Width / Anti-Aliased / X Scale /
Y Scale / Cursor`` conventions.

Series data is pushed one sample at a time via ``push_sample(name,
value)``. Buffers are bounded so old samples fall off the left as new
ones arrive on the right."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QAction, QActionGroup, QBrush, QColor, QFont, QFontMetrics, QMouseEvent,
    QPainter, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QMenu, QWidget,
)

from nvh_design_tokens import load_tokens

from .graticule import GraticuleWidget

_AXIS_COLUMN_WIDTH_PX = 60
_TICK_COUNT = 8

# Palette used for the default trace colors when the caller doesn't
# specify one -- covers up to 8 series matching the real system's stat
# set. Deliberately picked for visual separation on both dark and
# light backgrounds.
_DEFAULT_TRACE_COLORS = (
    "#4FD8E0",  # cyan (accent-secondary)
    "#FFB627",  # amber (accent-primary)
    "#E764C5",  # magenta
    "#3ECF8E",  # green (pass token)
    "#FF4136",  # red (alarm token)
    "#9B7BFB",  # violet
    "#5B8DEF",  # blue
    "#F2C94C",  # yellow
)


@dataclass
class SeriesConfig:
    """One trace's rendering + scaling state. Everything except the
    color has a runtime-editable equivalent via the context menu."""

    name: str
    color: QColor
    visible: bool = True
    autoscale: bool = True
    manual_min: float = 0.0
    manual_max: float = 1.0
    line_width: float = 1.5
    antialiased: bool = True
    buffer: deque[float] = field(default_factory=lambda: deque(maxlen=2000))

    def range(self) -> tuple[float, float]:
        """Effective y-range for this series -- either the buffer's
        min/max (with a small floor to avoid /0 on a flat signal) or
        the manually-set bounds."""
        if not self.autoscale and self.manual_max > self.manual_min:
            return self.manual_min, self.manual_max
        if not self.buffer:
            return 0.0, 1.0
        lo = min(self.buffer)
        hi = max(self.buffer)
        if hi - lo < 1e-9:
            return lo - 0.5, hi + 0.5
        # Small headroom top/bottom so peaks don't paint on the graticule border.
        span = hi - lo
        return lo - span * 0.08, hi + span * 0.08


class MultiSeriesPlot(GraticuleWidget):
    """N-series plot with per-series Y-axes stacked on the left, cursor
    overlay, and right-click config menu. Emits nothing -- the owning
    screen holds the data source and just pushes samples in."""

    def __init__(
        self,
        series_names: list[str],
        max_samples: int = 500,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)  # required so mouseMoveEvent fires without a button press
        self._series: dict[str, SeriesConfig] = {}
        for index, name in enumerate(series_names):
            hex_color = _DEFAULT_TRACE_COLORS[index % len(_DEFAULT_TRACE_COLORS)]
            cfg = SeriesConfig(name=name, color=QColor(hex_color))
            cfg.buffer = deque(maxlen=max_samples)
            self._series[name] = cfg
        self._max_samples = max_samples
        self._cursor_enabled: bool = False
        self._cursor_x: int | None = None

        tokens = load_tokens()
        layout = tokens["layout"]
        self._axis_stroke = layout["graticuleStrokeWidth"]

    # --- data-push API ----------------------------------------------

    def push_sample(self, name: str, value: float) -> None:
        cfg = self._series.get(name)
        if cfg is None:
            return
        cfg.buffer.append(float(value))
        self.update()

    def clear(self) -> None:
        for cfg in self._series.values():
            cfg.buffer.clear()
        self.update()

    # --- series config queries used by the legend/tests --------------

    def series_names(self) -> list[str]:
        return list(self._series.keys())

    def series_config(self, name: str) -> SeriesConfig:
        return self._series[name]

    def set_visible(self, name: str, visible: bool) -> None:
        if name in self._series:
            self._series[name].visible = visible
            self.update()

    def set_cursor_enabled(self, enabled: bool) -> None:
        self._cursor_enabled = enabled
        if not enabled:
            self._cursor_x = None
        self.update()

    # --- painting ----------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)  # draws graticule + background
        width = self.width()
        height = self.height()
        if width <= 20 or height <= 20:
            return

        # Reserve the left N * axis_column_width for stacked Y-axes.
        visible = [cfg for cfg in self._series.values() if cfg.visible]
        axis_area_width = _AXIS_COLUMN_WIDTH_PX * len(visible)
        plot_left = axis_area_width
        plot_right = width - 12
        plot_top = 12
        plot_bottom = height - 12
        plot_w = max(1, plot_right - plot_left)
        plot_h = max(1, plot_bottom - plot_top)

        painter = QPainter(self)
        # Axes are drawn against the whole widget; keep the base pen
        # tuned to the current palette's muted text color so tick
        # numbers stay readable on both themes.
        palette = self._resolve_palette()
        axis_color = QColor(palette["secondaryText"])
        painter.setFont(self._label_font())

        # Draw stacked Y-axis columns.
        for index, cfg in enumerate(visible):
            col_left = index * _AXIS_COLUMN_WIDTH_PX
            self._draw_axis_column(painter, cfg, col_left, plot_top, plot_bottom, axis_color)

        # Draw each visible trace, mapped from its own y-range to the
        # shared plot area on the right.
        for cfg in visible:
            self._draw_trace(painter, cfg, plot_left, plot_right, plot_top, plot_bottom)

        # Cursor overlay: vertical line + per-series value pill labels.
        if self._cursor_enabled and self._cursor_x is not None:
            self._draw_cursor(
                painter, visible,
                plot_left, plot_right, plot_top, plot_bottom, axis_color,
            )

        painter.end()

    def _resolve_palette(self) -> dict[str, str]:
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        palette_name = theme.palette_name if theme is not None else "dark"
        return load_tokens()["color"]["palettes"][palette_name]

    def _label_font(self) -> QFont:
        font = QFont()
        font.setFamily("IBM Plex Mono")
        font.setPointSizeF(8.5)
        return font

    def _draw_axis_column(
        self,
        painter: QPainter,
        cfg: SeriesConfig,
        col_left: int,
        plot_top: int,
        plot_bottom: int,
        axis_color: QColor,
    ) -> None:
        col_right = col_left + _AXIS_COLUMN_WIDTH_PX
        lo, hi = cfg.range()
        # Vertical axis line + tick marks + tick labels.
        pen = QPen(axis_color)
        pen.setWidthF(self._axis_stroke)
        painter.setPen(pen)
        painter.drawLine(col_right - 1, plot_top, col_right - 1, plot_bottom)

        fm = QFontMetrics(self._label_font())
        for i in range(_TICK_COUNT + 1):
            t = i / _TICK_COUNT
            y = plot_bottom - t * (plot_bottom - plot_top)
            value = lo + t * (hi - lo)
            painter.drawLine(col_right - 4, int(y), col_right - 1, int(y))
            text = self._format_tick(value)
            text_width = fm.horizontalAdvance(text)
            painter.drawText(col_right - 7 - text_width, int(y) + fm.ascent() // 2 - 1, text)

        # Rotated series-name label to the left of the axis column,
        # matching the LabVIEW screen's convention (SPEED / CREST / ...).
        painter.save()
        painter.setPen(QPen(cfg.color))
        label_font = QFont(self._label_font())
        label_font.setPointSizeF(9.5)
        label_font.setBold(True)
        painter.setFont(label_font)
        painter.translate(col_left + 12, (plot_top + plot_bottom) / 2)
        painter.rotate(-90)
        painter.drawText(0, 0, cfg.name)
        painter.restore()

    @staticmethod
    def _format_tick(value: float) -> str:
        if abs(value) >= 1000:
            return f"{value:.0f}"
        if abs(value) >= 10:
            return f"{value:.1f}"
        return f"{value:.2f}"

    def _draw_trace(
        self,
        painter: QPainter,
        cfg: SeriesConfig,
        plot_left: int, plot_right: int,
        plot_top: int, plot_bottom: int,
    ) -> None:
        if len(cfg.buffer) < 2:
            return
        lo, hi = cfg.range()
        span = hi - lo if hi > lo else 1.0
        pen = QPen(cfg.color)
        pen.setWidthF(cfg.line_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, cfg.antialiased)

        n = len(cfg.buffer)
        window = max(n, 2)
        polygon = QPolygonF()
        for i, value in enumerate(cfg.buffer):
            x = plot_left + (i / (window - 1)) * (plot_right - plot_left)
            y = plot_bottom - ((value - lo) / span) * (plot_bottom - plot_top)
            polygon.append(QPointF(x, y))
        painter.drawPolyline(polygon)

    def _draw_cursor(
        self,
        painter: QPainter,
        visible: list[SeriesConfig],
        plot_left: int, plot_right: int,
        plot_top: int, plot_bottom: int,
        axis_color: QColor,
    ) -> None:
        x = int(self._cursor_x)
        x = max(plot_left, min(plot_right, x))
        pen = QPen(axis_color, 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(x, plot_top, x, plot_bottom)

        # Map cursor x back to a fractional index into each buffer to
        # pull the value at that point.
        fraction = (x - plot_left) / max(1, plot_right - plot_left)
        palette = self._resolve_palette()
        panel_hex = palette["panel"]
        text_hex = palette["secondaryText"]
        painter.setFont(self._label_font())
        fm = QFontMetrics(self._label_font())
        pill_y = plot_top + 8
        for cfg in visible:
            if not cfg.buffer:
                continue
            n = len(cfg.buffer)
            idx = min(n - 1, max(0, int(fraction * (n - 1))))
            value = list(cfg.buffer)[idx]
            text = f"{cfg.name}: {self._format_tick(value)}"
            text_w = fm.horizontalAdvance(text)
            rect = QRectF(x + 8, pill_y, text_w + 16, fm.height() + 6)
            painter.setBrush(QBrush(QColor(panel_hex)))
            painter.setPen(QPen(cfg.color, 1))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QPen(QColor(text_hex)))
            painter.drawText(
                int(rect.left()) + 8,
                int(rect.top()) + fm.ascent() + 3,
                text,
            )
            pill_y += fm.height() + 10

    # --- mouse + context menu ---------------------------------------

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._cursor_enabled:
            self._cursor_x = int(event.position().x())
            self.update()
        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)

        # Plot Visible submenu -- one checkable action per series.
        vis_menu = menu.addMenu("Plot Visible")
        for cfg in self._series.values():
            act = QAction(cfg.name, vis_menu)
            act.setCheckable(True)
            act.setChecked(cfg.visible)
            act.toggled.connect(self._make_visibility_toggle(cfg.name))
            vis_menu.addAction(act)

        # Line width submenu -- affects every series uniformly (matches
        # LabVIEW's per-plot menu semantics; per-series widths can be an
        # extension later).
        lw_menu = menu.addMenu("Line Width")
        group = QActionGroup(lw_menu)
        for width in (1.0, 1.5, 2.0, 3.0):
            act = QAction(f"{width}", lw_menu)
            act.setCheckable(True)
            group.addAction(act)
            act.triggered.connect(self._make_line_width_setter(width))
            lw_menu.addAction(act)

        aa = QAction("Anti-Aliased", menu)
        aa.setCheckable(True)
        # If every series has AA on, show it checked; ignore mixed state.
        aa.setChecked(all(cfg.antialiased for cfg in self._series.values()))
        aa.toggled.connect(self._toggle_antialiased)
        menu.addAction(aa)

        menu.addSeparator()

        # X Scale / Y Scale submenus -- Autoscale toggle + Set Range.
        x_menu = menu.addMenu("X Scale")
        x_menu.setEnabled(False)  # X is a rolling time buffer today; no manual range yet.
        y_menu = menu.addMenu("Y Scale")
        for cfg in self._series.values():
            sub = y_menu.addMenu(cfg.name)
            auto = QAction("Autoscale", sub)
            auto.setCheckable(True)
            auto.setChecked(cfg.autoscale)
            auto.toggled.connect(self._make_autoscale_toggle(cfg.name))
            sub.addAction(auto)
            set_range = QAction("Set Range…", sub)
            set_range.triggered.connect(self._make_range_setter(cfg.name))
            sub.addAction(set_range)

        menu.addSeparator()

        cursor = QAction("Cursor Enabled", menu)
        cursor.setCheckable(True)
        cursor.setChecked(self._cursor_enabled)
        cursor.toggled.connect(self.set_cursor_enabled)
        menu.addAction(cursor)

        menu.exec(event.globalPos())

    def _make_visibility_toggle(self, name: str) -> Callable[[bool], None]:
        def _toggle(checked: bool) -> None:
            self.set_visible(name, checked)
        return _toggle

    def _make_line_width_setter(self, width: float) -> Callable[[], None]:
        def _apply() -> None:
            for cfg in self._series.values():
                cfg.line_width = width
            self.update()
        return _apply

    def _toggle_antialiased(self, checked: bool) -> None:
        for cfg in self._series.values():
            cfg.antialiased = checked
        self.update()

    def _make_autoscale_toggle(self, name: str) -> Callable[[bool], None]:
        def _toggle(checked: bool) -> None:
            self._series[name].autoscale = checked
            self.update()
        return _toggle

    def _make_range_setter(self, name: str) -> Callable[[], None]:
        def _prompt() -> None:
            cfg = self._series[name]
            lo, ok_lo = QInputDialog.getDouble(
                self, f"{name} Y range", "Minimum:",
                value=cfg.manual_min, decimals=4,
            )
            if not ok_lo:
                return
            hi, ok_hi = QInputDialog.getDouble(
                self, f"{name} Y range", "Maximum:",
                value=cfg.manual_max, decimals=4,
            )
            if not ok_hi or hi <= lo:
                return
            cfg.manual_min = lo
            cfg.manual_max = hi
            cfg.autoscale = False
            self.update()
        return _prompt
