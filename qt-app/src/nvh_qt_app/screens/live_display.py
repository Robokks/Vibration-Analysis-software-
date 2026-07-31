"""Realtime operator screen -- rebuilt to match the real system's
Live Display layout: top toolbar of nine operator-workflow icons over
nested plot tabs (Time series {raw, computed} / Frequency domain
{FFT, order spectrum, order tracking, color map, waterfall}), a bottom
parameter table for the current gear+direction, and a 9-field bottom
status bar.

Data sources are the same as the previous scaffold: LiveEvent frames off
the /live/ws WebSocket for streaming updates, plus REST fetches
(/test-runs/{id}, /models/.../parameters) for the fields the stream
doesn't carry (operator/shift/serial/repeat and the parameter catalog).
The subtabs the analysis engine only produces on completed DC records
(order spectrum / tracking / color map / waterfall) show a clearly-
labeled placeholder rather than pretending to compute nothing."""

from __future__ import annotations

from typing import Any

import numpy as np
from analysis_engine.signal.octave import STANDARD_OCTAVE_CENTERS_HZ, compute_octave_bands
from analysis_engine.signal.order_spectrum import compute_order_spectrum
from analysis_engine.signal.order_tracking import compute_order_tracking
from analysis_engine.signal.stft import compute_spectrogram
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from nvh_design_tokens import load_tokens

from ..api_client import ApiClient
from ..freq_domain_settings import FreqDomainSettings
from ..live_client import LiveClient
from ..widgets.fft_trace import FftTraceWidget
from ..widgets.freq_domain_settings_dialog import FreqDomainSettingsDialog
from ..widgets.gear_glyph import GearGlyphWidget
from ..widgets.labels import MonoLabel, SectionTitle
from ..widgets.live_status_bar import LiveStatusBar
from ..widgets.live_toolbar import LiveToolbar
from ..widgets.multi_series_plot import MultiSeriesPlot
from ..widgets.order_plots import OrderSpectrumPlot, OrderTrackingPlot
from ..widgets.panel import Panel
from ..widgets.placeholder_panel import PlaceholderPanel
from ..widgets.plot_legend import PlotLegend
from ..widgets.signal_trace import SignalTraceWidget
from ..widgets.spectrogram_plots import ColorMapPlot, OctaveBarsPlot, WaterfallPlot

# The seeded dataset has one model/program/gear/direction, so the
# parameter table's fetch key is fixed here -- same demo constants as
# MasterEntryScreen. Once the stream events carry a real (model_id,
# program_name, gear_label, direction) tuple we should switch this
# fetch to be event-driven per DC.
_MODEL_ID = "MODEL-A"
_PROGRAM_NAME = "REVA"
_GEAR_LABEL = "R"
_DIRECTION = "RU"
_CHANNEL_NAME = "vib_a"

_TRACE_MAX_SAMPLES = 4000
_DEFAULT_STATION = "STN-01"
_PLACEHOLDER = "—"

# Series shown on the Computed sub-tab's multi-Y-axis plot -- one row
# per LabVIEW-style stat plus SPEED (rpm) as the process context signal.
# Order matches the real screen's left-to-right axis column order.
_COMPUTED_SERIES = (
    "SPEED", "CREST", "PEAK", "RMS", "KURTOSIS", "SKEWNESS", "VARIANCE", "MEAN",
)

# Order-tracking series shown on the ORDER TRACKING sub-tab. OVERALL
# is the RMS amplitude of the raw signal per time window (aggregate),
# the numeric labels are gear-mesh harmonics of the drive-teeth count
# (Model-A's demo gear R has 12 teeth -- 12/24/36/48 = the 1x/2x/3x/4x
# gear-mesh order harmonics we track). Matches the LabVIEW screen's
# convention where each labeled trace is one order-of-interest.
_TRACKED_ORDER_SERIES: tuple[tuple[str, float | None], ...] = (
    ("OVERALL", None),
    ("12", 12.0),
    ("24", 24.0),
    ("36", 36.0),
    ("48", 48.0),
)

# LabVIEW PLC boundary: NVH_ID enum for direction (see docs/data-contract).
_DIRECTION_NVH_ID: dict[str, int] = {"RU": 0, "STYD": 1, "STYC": 2, "RD": 3}


def _to_db(magnitude: np.ndarray) -> np.ndarray:
    """20 * log10(|magnitude|) with a small floor to avoid log(0).
    Used when the operator flips the dB ON toggle in PLOT SETUP."""
    floor = np.maximum(magnitude, 1e-12)
    return 20.0 * np.log10(floor)

# Results-grid layout: rows are (gear, direction) pairs, columns are one
# graded-parameter each. Matches the real system's NVH TEST SCREEN.vi
# table (see docs -- Gear ID / Result / RMS max / PK max / Kurtosis /
# IN_H1(dB m/s2) / IN_H1(g)). Result cell paints pass-green / alarm-red
# once the DC completes; parameter cells stay em-dash until the live
# stream starts carrying per-parameter values.
_RESULT_TABLE_COLUMNS = (
    "Gear ID", "Result",
    "RMS max (m/s2)", "PK max (dB m/s2)", "Kurtosis max",
    "IN_H1(dB m/s2)", "IN_H1(g)",
)
_RESULT_TABLE_DIRECTIONS = ("RU", "RD")
# Fallback gear list if the model fetch hasn't completed yet -- matches
# the real gearbox's non-neutral gears so the table isn't empty during
# the first paint.
_DEFAULT_GEAR_LABELS = ("R", "I", "II", "III", "IV", "V")


class LiveDisplayScreen(QWidget):
    """Operator-facing live view with the full toolbar/tabs/table/status
    bar layout. `live_client` and `api_client` can both be injected for
    tests -- the default constructor wires real clients pointed at the
    same backend the rest of the app uses."""

    def __init__(
        self, parent=None,
        live_client: LiveClient | None = None,
        api_client: ApiClient | None = None,
    ) -> None:
        super().__init__(parent)
        # Read colors from the current global theme -- when the user
        # flips dark/light via the header toggle the ThemeManager emits
        # theme_changed and this screen cascades apply_palette() to every
        # child widget that has inline styles.
        self._load_palette()

        # --- state --------------------------------------------------
        self._station_id = _DEFAULT_STATION
        self._test_run_id: str | None = None
        self._test_run_status: str | None = None
        # (gear_label, direction) -> row index in the results table, so a
        # dc event can find the right row in O(1) without walking cells.
        self._row_index: dict[tuple[str, str], int] = {}
        # (gear_label, direction) -> stamp last painted, so a palette
        # flip can re-color Result cells with the fresh pass/alarm hex.
        self._row_stamp: dict[tuple[str, str], str] = {}
        # (gear_label, direction) -> running (rms_max, peak_max) live
        # values, updated per signal_chunk. Cleared when a new dc for
        # that pair arrives (a fresh run starts).
        self._row_stats: dict[tuple[str, str], tuple[float, float]] = {}
        # Rolling rpm buffer that mirrors the raw-trace sample buffer,
        # kept in lockstep so order tracking has an aligned rpm value
        # for each sample. Bounded at _TRACE_MAX_SAMPLES.
        from collections import deque
        self._rpm_buffer: deque[float] = deque(maxlen=_TRACE_MAX_SAMPLES)
        self._sample_rate_hz: float = 5000.0
        # Frequency-domain plot settings (in-memory only for now --
        # persistence is future work). Exposed via the PLOT SETUP
        # dialog reachable from the frequency-domain tab.
        self._freq_settings = FreqDomainSettings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- toolbar ------------------------------------------------
        self._toolbar = LiveToolbar(icon_color=self._accent_secondary, muted_color=self._muted)
        self._toolbar.action_triggered.connect(self._on_toolbar_action)
        layout.addWidget(self._toolbar)

        # --- status line (small, above the plot tabs) ---------------
        status_row = QHBoxLayout()
        status_row.setContentsMargins(24, 6, 24, 6)
        indicator = GearGlyphWidget(color=self._accent_secondary, spinning=True)
        indicator.setFixedSize(28, 20)
        status_row.addWidget(indicator)
        self._status_label = MonoLabel("connecting…")
        status_row.addWidget(self._status_label)
        status_row.addStretch(1)
        status_row_widget = QWidget()
        status_row_widget.setLayout(status_row)
        layout.addWidget(status_row_widget)

        # --- plot tabs ----------------------------------------------
        self._plot_tabs = QTabWidget()
        self._plot_tabs.addTab(self._build_time_series_tab(), "Time series")
        self._plot_tabs.addTab(self._build_frequency_domain_tab(), "Frequency domain")
        # A "Settings…" corner widget on the frequency-domain tab
        # opens the multi-tab PLOT SETUP dialog. Anchored via
        # setCornerWidget so it sits at the top-right of the tab bar
        # regardless of which tab is active.
        settings_btn = QPushButton("Settings…")
        settings_btn.setObjectName("FreqSettingsButton")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setFlat(True)
        settings_btn.clicked.connect(self._open_freq_domain_settings)
        self._plot_tabs.setCornerWidget(settings_btn, Qt.Corner.TopRightCorner)
        layout.addWidget(self._plot_tabs, stretch=1)

        # --- bottom results table -----------------------------------
        # Rebuilt to match the real NVH TEST SCREEN.vi table: one row per
        # (gear_label, direction) step, columns for the row-scoped
        # grading parameters, Result cell colored green/red as DC events
        # arrive. See _populate_results_rows() for the row-set derivation.
        table_panel = Panel()
        table_panel_layout = QVBoxLayout(table_panel)
        table_panel_layout.setContentsMargins(16, 12, 16, 12)
        table_panel_layout.addWidget(SectionTitle("Live results grid"))
        self._results_table = self._build_results_table()
        self._populate_results_rows(_DEFAULT_GEAR_LABELS)
        table_panel_layout.addWidget(self._results_table)
        layout.addWidget(table_panel)

        # --- bottom status bar --------------------------------------
        self._status_bar = LiveStatusBar(
            muted_color=self._muted, accent_color=self._accent_secondary,
        )
        self._status_bar.set_field("model", _MODEL_ID)
        self._status_bar.set_field("gear_id", _GEAR_LABEL)
        self._status_bar.set_field("nvh_id", _DIRECTION_NVH_ID.get(_DIRECTION, _PLACEHOLDER))
        layout.addWidget(self._status_bar)

        # --- API + live-stream clients -----------------------------
        self._api = api_client if api_client is not None else ApiClient()
        # Fetch the model so we can seed the results grid with the real
        # gearbox's gear labels rather than the hardcoded default.
        self._api.fetch_model(_MODEL_ID, self._on_model, self._on_api_error)

        self._client = live_client if live_client is not None else LiveClient()
        self._client.on_event = self._on_event
        self._client.on_status = self._on_status
        self._client.start()

        # Subscribe to global palette flips so this screen (and its
        # inline-styled children) can refresh alongside the app-level
        # setStyleSheet. Guarded because tests build MainWindow which
        # auto-attaches a theme; standalone screen tests get the same
        # via app_shell's fallback attach path.
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)

    # --- tab builders -----------------------------------------------

    def _build_time_series_tab(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        # Raw signal
        self._raw_trace = SignalTraceWidget(max_samples=_TRACE_MAX_SAMPLES)
        self._raw_trace.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._raw_trace), "Raw signal")
        # Computed -- multi-Y-axis plot, one series per LabVIEW-style
        # stat, with a legend on the right for per-series visibility.
        self._computed_plot = MultiSeriesPlot(list(_COMPUTED_SERIES), max_samples=500)
        self._computed_plot.setMinimumHeight(240)
        colors = {name: self._computed_plot.series_config(name).color for name in _COMPUTED_SERIES}
        self._computed_legend = PlotLegend(
            list(_COMPUTED_SERIES), colors, self._computed_plot.set_visible,
        )
        computed_container = QWidget()
        computed_layout = QHBoxLayout(computed_container)
        computed_layout.setContentsMargins(12, 12, 12, 12)
        computed_layout.setSpacing(8)
        computed_layout.addWidget(self._computed_plot, stretch=1)
        computed_layout.addWidget(self._computed_legend)
        tabs.addTab(computed_container, "Computed")
        return tabs

    def _build_frequency_domain_tab(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        # FFT (live)
        self._fft_trace = FftTraceWidget(max_samples=_TRACE_MAX_SAMPLES)
        self._fft_trace.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._fft_trace), "FFT")

        # Color map + Waterfall + Cascade share one STFT computation --
        # rendered as three different projections of the same matrix.
        self._colormap_plot = ColorMapPlot()
        self._colormap_plot.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._colormap_plot), "Color map")

        self._waterfall_plot = WaterfallPlot()
        self._waterfall_plot.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._waterfall_plot), "Waterfall")

        # Cascade is the same STFT projected the same way as waterfall,
        # historically drawn with a different orientation. Reuse the
        # widget for the demo -- extend later if we want a variant.
        self._cascade_plot = WaterfallPlot()
        self._cascade_plot.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._cascade_plot), "Cascade")

        # Octave: 1/3-octave center-frequency band-energy bars.
        self._octave_plot = OctaveBarsPlot()
        self._octave_plot.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._octave_plot), "Octave")

        # Order spectrum: SPEED-vs-time on top + magnitude-vs-order on
        # bottom, with a peaks list. Computed by angle-domain resampling
        # so bins are directly in orders (cycles per shaft revolution).
        self._order_spectrum_plot = OrderSpectrumPlot()
        self._order_spectrum_plot.setMinimumHeight(320)
        tabs.addTab(self._wrap_padded(self._order_spectrum_plot), "Order spectrum")

        # Order tracking: N traces vs time (OVERALL + gear-mesh harmonics).
        self._order_tracking_plot = OrderTrackingPlot(
            [name for name, _ in _TRACKED_ORDER_SERIES]
        )
        self._order_tracking_plot.setMinimumHeight(240)
        self._order_tracking_plot.set_expected_orders([
            (name, order) for name, order in _TRACKED_ORDER_SERIES if order is not None
        ])
        tabs.addTab(self._wrap_padded(self._order_tracking_plot), "Order tracking")

        # Nothing is a placeholder any more -- keep the list so the
        # theme-refresh path in _on_theme_changed still iterates over
        # an empty tuple without special-casing.
        self._placeholder_panels: list[PlaceholderPanel] = []
        return tabs

    @staticmethod
    def _wrap_padded(widget: QWidget) -> QWidget:
        # Give the trace widgets a small internal margin so they don't
        # butt up against the tab bar / bottom table.
        container = QWidget()
        wrap = QVBoxLayout(container)
        wrap.setContentsMargins(12, 12, 12, 12)
        wrap.addWidget(widget)
        return container

    def _build_results_table(self) -> QTableWidget:
        table = QTableWidget(0, len(_RESULT_TABLE_COLUMNS))
        table.setHorizontalHeaderLabels(list(_RESULT_TABLE_COLUMNS))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setMaximumHeight(220)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(2, len(_RESULT_TABLE_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        return table

    def _populate_results_rows(self, gear_labels: tuple[str, ...] | list[str]) -> None:
        """Seed the results grid with one row per (gear, direction) pair
        drawn from the model's gear labels. Row order matches the real
        LabVIEW screen (all gears asc, RU before RD)."""
        table = self._results_table
        # Match the LabVIEW screen's convention: skip neutral (N) since
        # neutral doesn't have a graded acquisition step, and emit RU
        # before RD within each gear group.
        gears = [g for g in gear_labels if g != "N"]
        rows: list[tuple[str, str]] = [
            (gear, direction) for gear in gears for direction in _RESULT_TABLE_DIRECTIONS
        ]
        table.setRowCount(len(rows))
        self._row_index.clear()
        self._row_stamp.clear()
        for r, (gear, direction) in enumerate(rows):
            self._row_index[(gear, direction)] = r
            gear_id_item = QTableWidgetItem(f"{gear}_{direction}")
            gear_id_item.setForeground(QBrush(QColor(self._accent_secondary)))
            table.setItem(r, 0, gear_id_item)
            # All other cells start empty -- Result colors in on a dc
            # event, parameter cells fill in once the stream carries
            # per-parameter values.
            for c in range(1, len(_RESULT_TABLE_COLUMNS)):
                table.setItem(r, c, QTableWidgetItem(""))

    # --- toolbar action handling ------------------------------------

    def _on_toolbar_action(self, action: str) -> None:
        """Toolbar buttons don't own routing -- they just emit a name.
        For now surface the action in the top status label so the click
        is observable; MainWindow can subscribe to route to sibling
        screens in a follow-up (see PROGRESS.md)."""
        readable = action.replace("_", " ")
        self._status_label.setText(f"station {self._station_id} — {readable} requested")

    # --- REST callbacks ---------------------------------------------

    def _on_model(self, model: dict) -> None:
        """Reseed the results grid from the real gearbox's gear labels
        (sorted). Runs once after the initial fetch_model completes."""
        gears = tuple(sorted(model.get("ratios", {}).keys()))
        if gears:
            self._populate_results_rows(gears)

    def _on_test_run_detail(self, payload: dict[str, Any]) -> None:
        test_run = payload.get("test_run") or {}
        self._status_bar.set_field("operator", test_run.get("operator_id"))
        self._status_bar.set_field("shift", test_run.get("shift_number"))
        self._status_bar.set_field("serial", test_run.get("serial_number"))
        self._status_bar.set_field("repeat", test_run.get("repeat_number"))
        self._status_bar.set_field("model", test_run.get("model_id") or _MODEL_ID)
        self._status_bar.set_field("result", test_run.get("overall_result"))

    def _on_api_error(self, _message: str) -> None:
        # REST failures don't kill Live Display -- the WebSocket stream
        # still drives the trace. Silently absorb them; the status label
        # already reflects the primary connection state, and simulator-
        # driven test_run IDs 404 by design (they're ephemeral, never
        # persisted). Real REST outages will still surface in the
        # parameter table staying empty.
        pass

    # --- WebSocket callbacks ----------------------------------------

    def _on_status(self, state: str, error: str | None) -> None:
        if state == "connecting":
            self._status_label.setText("connecting…")
            return
        if state == "open":
            self._status_label.setText(self._compose_status())
            return
        if state == "closed":
            suffix = f": {error}" if error else ""
            self._status_label.setText(
                f"station {self._station_id} — connection lost{suffix}"
            )
            self._status_bar.set_field("status", "DISCONNECTED")

    def _on_event(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("type")
        if event_type == "test_run":
            self._handle_test_run(payload)
        elif event_type == "dc":
            self._handle_dc(payload)
        elif event_type == "signal_chunk":
            self._handle_signal_chunk(payload)

    def _handle_test_run(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        self._test_run_id = payload.get("test_run_id")
        self._test_run_status = payload.get("status")
        self._status_bar.set_field("status", self._test_run_status)

        if self._test_run_status == "RUNNING":
            # Fresh acquisition -- clear every plot buffer.
            self._raw_trace.clear()
            self._fft_trace.clear()
            self._computed_plot.clear()
            self._colormap_plot.clear()
            self._waterfall_plot.clear()
            self._cascade_plot.clear()
            self._octave_plot.clear()
            self._order_spectrum_plot.clear()
            self._order_tracking_plot.clear()
            self._rpm_buffer.clear()
            self._status_bar.set_field("result", "PENDING")

        # Backfill operator/shift/serial/repeat from the test-run summary.
        if self._test_run_id:
            self._api.fetch_test_run(
                self._test_run_id, self._on_test_run_detail, self._on_api_error,
            )
        self._status_label.setText(self._compose_status())

    def _handle_dc(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        gear = payload.get("gear_label") or _PLACEHOLDER
        direction = payload.get("direction") or _PLACEHOLDER
        stamp = payload.get("stamp") or "PENDING"
        self._status_bar.set_field("gear_id", gear)
        self._status_bar.set_field("nvh_id", _DIRECTION_NVH_ID.get(direction, _PLACEHOLDER))
        self._status_bar.set_field("result", stamp)
        # Also color the matching row in the results grid. Unknown
        # (gear, direction) pairs (e.g. STYD/STYC that this table doesn't
        # show) are silently ignored -- the status bar still updated.
        self._paint_result_cell(gear, direction, stamp)

    def _paint_result_cell(self, gear: str, direction: str, stamp: str) -> None:
        row = self._row_index.get((gear, direction))
        if row is None:
            return
        item = self._results_table.item(row, 1)
        if item is None:
            item = QTableWidgetItem("")
            self._results_table.setItem(row, 1, item)
        self._row_stamp[(gear, direction)] = stamp
        color_hex = self._pass if stamp == "PASS" else self._alarm if stamp == "FAIL" else None
        if color_hex is None:
            item.setBackground(QBrush())
            item.setText(stamp)
            return
        item.setBackground(QBrush(QColor(color_hex)))
        # Empty text -- the color IS the value, matching the real
        # LabVIEW screen's convention (green fill == PASS).
        item.setText("")

    def _handle_signal_chunk(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        # Multi-channel: prefer the `channels` dict if present (Phase G+),
        # falling back to the legacy top-level `values` for
        # wire-compatibility with older producers.
        channels = payload.get("channels") or {}
        primary_channel = payload.get("channel_name") or "vib_a"
        if channels and primary_channel in channels:
            values = channels[primary_channel]
        else:
            values = payload.get("values") or []
        rpm = payload.get("rpm") or []
        sample_rate_hz = payload.get("sample_rate_hz")
        if not values:
            return
        self._raw_trace.append_samples(values)
        self._fft_trace.append_samples(values, sample_rate_hz=sample_rate_hz)
        # Keep the rpm buffer in lockstep with the raw sample buffer.
        # Order spectrum + order tracking need a matched rpm array; if
        # a chunk carries fewer rpm samples than values (or none) pad
        # by repeating the last known rpm so the arrays stay aligned.
        if sample_rate_hz:
            self._sample_rate_hz = float(sample_rate_hz)
        rpm_iter = iter(rpm)
        last_rpm = self._rpm_buffer[-1] if self._rpm_buffer else 0.0
        for _ in values:
            try:
                last_rpm = float(next(rpm_iter))
            except StopIteration:
                pass  # fall back to last_rpm
            self._rpm_buffer.append(last_rpm)
        self._push_computed_from_chunk(values, rpm)
        # Compute STFT + octave bands from the full raw buffer every 4
        # chunks -- roughly one refresh per 400ms wall-clock at the
        # simulator's 10 chunks/sec pace. Anything faster is wasted
        # since the user can't perceive it.
        self._chunk_counter = getattr(self, "_chunk_counter", 0) + 1
        if self._chunk_counter % 4 == 0:
            self._refresh_spectrogram(sample_rate_hz)
            self._refresh_order_analysis()

        # Update the live RMS-max / PK-max cells in the results grid
        # for the (gear_label, direction) this chunk belongs to.
        gear = payload.get("gear_label")
        direction = payload.get("direction")
        if gear and direction and values:
            self._update_row_live_stats(gear, direction, values)

    def _update_row_live_stats(self, gear: str, direction: str, values: list[float]) -> None:
        arr = np.asarray(values, dtype=np.float64)
        rms = float(np.sqrt(np.mean(arr * arr))) if arr.size else 0.0
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        prev_rms, prev_peak = self._row_stats.get((gear, direction), (0.0, 0.0))
        rms_max = max(prev_rms, rms)
        peak_max = max(prev_peak, peak)
        self._row_stats[(gear, direction)] = (rms_max, peak_max)

        r = self._row_index.get((gear, direction))
        if r is None:
            return
        # Columns: 0=gear id, 1=result, 2=RMS max, 3=PK max, ...
        rms_item = self._results_table.item(r, 2) or QTableWidgetItem("")
        rms_item.setText(f"{rms_max:.3f}")
        self._results_table.setItem(r, 2, rms_item)
        # PK max is in dB m/s^2 per column header; approximate as 20*log10.
        peak_db = 20.0 * np.log10(max(peak_max, 1e-12))
        peak_item = self._results_table.item(r, 3) or QTableWidgetItem("")
        peak_item.setText(f"{peak_db:.2f}")
        self._results_table.setItem(r, 3, peak_item)

    def _refresh_spectrogram(self, sample_rate_hz: float | None) -> None:
        """Compute STFT + octave bands from the current raw-signal buffer
        and push into the frequency-domain widgets. Guarded on a minimum
        buffer size so the STFT has at least one full window per call.
        nperseg / dB conversion driven by the operator's PLOT SETUP
        settings (colormap tab -- waterfall/cascade share the projection
        so they read from the same computed matrix)."""
        buffer = list(self._raw_trace._buffer)
        if len(buffer) < 512:
            return
        sr = sample_rate_hz or 5000.0
        arr = np.asarray(buffer, dtype=float)
        # Bins from the settings dialog. Cap at buffer size so scipy
        # doesn't reject nperseg > input length; halve for noverlap
        # (50% overlap is the STFT convention the analysis engine
        # uses by default).
        cfg = self._freq_settings.colormap
        nperseg = min(max(64, cfg.freq_order_bins // 8), len(buffer))
        try:
            spec = compute_spectrogram(arr, sample_rate_hz=sr, nperseg=nperseg, noverlap=nperseg // 2)
        except Exception:
            return
        mag = spec.magnitude
        # dB conversion, opt-in per view -- 20 * log10(|X|) with a floor
        # to avoid log(0). Waterfall / Cascade / Colormap each have
        # their own dB toggle in the PLOT SETUP dialog.
        cm_mag = _to_db(mag) if self._freq_settings.colormap.db_on else mag
        wf_mag = _to_db(mag) if self._freq_settings.waterfall.db_on else mag
        cs_mag = _to_db(mag) if self._freq_settings.cascade.db_on else mag
        self._colormap_plot.set_spectrogram(cm_mag, spec.time_s, spec.freq)
        self._waterfall_plot.set_spectrogram(wf_mag, spec.time_s, spec.freq)
        self._cascade_plot.set_spectrogram(cs_mag, spec.time_s, spec.freq)
        try:
            bands = compute_octave_bands(arr, sample_rate_hz=sr, centers_hz=STANDARD_OCTAVE_CENTERS_HZ)
            self._octave_plot.set_bands(bands.center_freq_hz, bands.rms)
        except Exception:
            pass

    def _open_freq_domain_settings(self) -> None:
        """Show the PLOT SETUP dialog. On accept, replace the in-memory
        settings, propagate the window/dB/bins choices down to the
        plot widgets, and force a fresh spectrogram + order-analysis
        pass so the new settings take effect right away."""
        dialog = FreqDomainSettingsDialog(self._freq_settings, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._freq_settings = dialog.current_settings()
            # Push the FFT window choice down so the live FFT trace
            # reflects the operator's selection.
            self._fft_trace.set_window(self._freq_settings.fft.window)
            self._refresh_spectrogram(self._sample_rate_hz)
            self._refresh_order_analysis()

    def _refresh_order_analysis(self) -> None:
        """Compute order spectrum + per-order tracking from the current
        raw signal + rpm buffers, push into the two order-domain
        widgets. Skipped on a too-short buffer (need >= 1024 samples
        for a meaningful order spectrum) or when rpm never actually
        changes (angular resampling divides by dtheta which requires
        a real ramp)."""
        n = min(len(self._raw_trace._buffer), len(self._rpm_buffer))
        if n < 1024:
            return
        signal = np.asarray(list(self._raw_trace._buffer)[-n:], dtype=float)
        rpm = np.asarray(list(self._rpm_buffer)[-n:], dtype=float)
        if rpm.max() - rpm.min() < 1.0:  # constant rpm -- no angular resample
            return
        sr = self._sample_rate_hz
        time_s = np.arange(n) / sr

        # -- Order spectrum --
        # samples_per_rev = 1 / order_resolution rounded to the nearest
        # power-of-2-ish integer -- the LabVIEW screen exposes
        # ORDER RESOLUTION directly, so let the operator's value drive
        # this via the settings dialog.
        cfg = self._freq_settings.order_spectrum
        samples_per_rev = max(32, int(round(1.0 / max(cfg.order_resolution, 0.001))))
        try:
            os_result = compute_order_spectrum(signal, time_s, rpm, samples_per_rev=samples_per_rev)
        except Exception:
            return
        # Trim leading DC bin + clamp to the operator-configured MAX
        # ORDER (matches the LabVIEW screen's MAX ORDER field).
        max_order = cfg.max_order
        keep = (os_result.order > 0.5) & (os_result.order <= max_order)
        mag_view = os_result.magnitude[keep]
        order_view = os_result.order[keep]
        self._order_spectrum_plot.set_speed_over_time(rpm[::max(1, n // 500)].tolist())
        self._order_spectrum_plot.set_spectrum(mag_view.tolist())
        # Top-5 peaks by magnitude.
        if mag_view.size > 0:
            top_idx = np.argsort(mag_view)[-5:][::-1]
            peaks = [(float(order_view[i]), float(mag_view[i])) for i in top_idx]
            self._order_spectrum_plot.set_peaks(peaks)

        # -- Order tracking (per-order magnitude vs time) --
        for name, order in _TRACKED_ORDER_SERIES:
            if order is None:
                # OVERALL = windowed RMS envelope of the raw signal.
                window = max(1, n // 100)
                envelope = [
                    float(np.sqrt(np.mean(signal[i:i + window] ** 2)))
                    for i in range(0, n, window)
                ]
                self._order_tracking_plot.set_series_data(name, envelope)
                continue
            try:
                ot_result = compute_order_tracking(
                    signal, time_s, rpm, sample_rate_hz=sr, order=order, nperseg=256,
                )
            except Exception:
                continue
            self._order_tracking_plot.set_series_data(name, ot_result.magnitude.tolist())

    def _push_computed_from_chunk(self, values: list[float], rpm: list[float]) -> None:
        """Compute one sample per stat from this chunk and append to
        the multi-series plot. Guards against a chunk too small to
        yield meaningful stats (min 8 samples)."""
        if len(values) < 8:
            return
        arr = np.asarray(values, dtype=float)
        mean = float(arr.mean())
        centered = arr - mean
        variance = float(np.mean(centered * centered))
        std = variance ** 0.5
        rms = float(np.sqrt(np.mean(arr * arr)))
        peak = float(np.max(np.abs(arr)))
        crest = peak / rms if rms > 0 else 0.0
        # Skewness and kurtosis (Fisher's excess): guard for std==0.
        if std > 1e-9:
            skew = float(np.mean((centered / std) ** 3))
            kurt = float(np.mean((centered / std) ** 4) - 3.0)
        else:
            skew = 0.0
            kurt = 0.0
        speed = float(np.mean(np.asarray(rpm, dtype=float))) if rpm else 0.0

        push = self._computed_plot.push_sample
        push("SPEED", speed)
        push("CREST", crest)
        push("PEAK", peak)
        push("RMS", rms)
        push("KURTOSIS", kurt)
        push("SKEWNESS", skew)
        push("VARIANCE", variance)
        push("MEAN", mean)

    # --- theme -------------------------------------------------------

    def _load_palette(self) -> None:
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        palette_name = theme.palette_name if theme is not None else "dark"
        palette = load_tokens()["color"]["palettes"][palette_name]
        self._accent_primary = palette["accentPrimary"]
        self._accent_secondary = palette["accentSecondary"]
        self._muted = palette["secondaryText"]
        self._pass = palette["pass"]
        self._alarm = palette["alarm"]

    def _on_theme_changed(self, _palette_name: str) -> None:
        """Rebuild every inline-styled child's colors from the fresh
        palette. The app-level QSS refresh already handled everything
        that goes through type-selector styles."""
        self._load_palette()
        self._toolbar.apply_palette(icon_color=self._accent_secondary, muted_color=self._muted)
        self._status_bar.apply_palette(muted_color=self._muted, accent_color=self._accent_secondary)
        # Multi-series plot rereads its palette on the next paint via
        # GraticuleWidget's own theme_changed subscription -- no extra
        # apply_palette hop needed.
        self._computed_plot.update()
        for panel in self._placeholder_panels:
            panel.apply_palette(muted_color=self._muted)
        # Repaint the FFT trace in the new accent color.
        self._fft_trace._trace_color = QColor(self._accent_primary)
        self._fft_trace.update()
        # Repaint any already-shown Result cells in the fresh pass/alarm hex.
        self._repaint_result_cells()
        # Refresh the Gear ID column color.
        for row in range(self._results_table.rowCount()):
            item = self._results_table.item(row, 0)
            if item is not None:
                item.setForeground(QBrush(QColor(self._accent_secondary)))

    def _repaint_result_cells(self) -> None:
        """After a palette flip, re-apply each cached stamp with the
        fresh pass/alarm hex. Rows with no stamp cache stay empty."""
        for (gear, direction), stamp in self._row_stamp.items():
            self._paint_result_cell(gear, direction, stamp)

    # --- helpers -----------------------------------------------------

    def _compose_status(self) -> str:
        station = self._station_id
        if self._test_run_id is None:
            return f"station {station} — awaiting test run"
        if self._test_run_status == "RUNNING":
            return f"station {station} — {self._test_run_id} running…"
        if self._test_run_status == "COMPLETED":
            return f"station {station} — {self._test_run_id} completed"
        return f"station {station} — {self._test_run_id}"

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._client.stop()
        super().closeEvent(event)
