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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from nvh_design_tokens import load_tokens

from ..api_client import ApiClient
from ..live_client import LiveClient
from ..widgets.fft_trace import FftTraceWidget
from ..widgets.gear_glyph import GearGlyphWidget
from ..widgets.labels import MonoLabel, SectionTitle
from ..widgets.live_stats import LiveStatsPanel
from ..widgets.live_status_bar import LiveStatusBar
from ..widgets.live_toolbar import LiveToolbar
from ..widgets.panel import Panel
from ..widgets.placeholder_panel import PlaceholderPanel
from ..widgets.signal_trace import SignalTraceWidget

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

# LabVIEW PLC boundary: NVH_ID enum for direction (see docs/data-contract).
_DIRECTION_NVH_ID: dict[str, int] = {"RU": 0, "STYD": 1, "STYC": 2, "RD": 3}

_PARAMETER_TABLE_COLUMNS = ("Parameter", "Order", "Limit low", "Limit high", "In table")


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
        palette = load_tokens()["color"]["palettes"]["dark"]
        self._accent_primary = palette["accentPrimary"]
        self._accent_secondary = palette["accentSecondary"]
        self._muted = palette["secondaryText"]
        self._pass = palette["pass"]
        self._alarm = palette["alarm"]

        # --- state --------------------------------------------------
        self._station_id = _DEFAULT_STATION
        self._test_run_id: str | None = None
        self._test_run_status: str | None = None

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
        layout.addWidget(self._plot_tabs, stretch=1)

        # --- bottom parameter table ---------------------------------
        table_panel = Panel()
        table_panel_layout = QVBoxLayout(table_panel)
        table_panel_layout.setContentsMargins(16, 12, 16, 12)
        table_panel_layout.addWidget(SectionTitle("Live parameter catalog"))
        self._param_table = self._build_parameter_table()
        table_panel_layout.addWidget(self._param_table)
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
        self._api.fetch_parameters(
            _MODEL_ID, _PROGRAM_NAME, _GEAR_LABEL, _DIRECTION,
            self._on_parameters, self._on_api_error,
            channel_name=_CHANNEL_NAME,
        )

        self._client = live_client if live_client is not None else LiveClient()
        self._client.on_event = self._on_event
        self._client.on_status = self._on_status
        self._client.start()

    # --- tab builders -----------------------------------------------

    def _build_time_series_tab(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        # Raw signal
        self._raw_trace = SignalTraceWidget(max_samples=_TRACE_MAX_SAMPLES)
        self._raw_trace.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._raw_trace), "Raw signal")
        # Computed
        self._stats_panel = LiveStatsPanel(
            muted_color=self._muted, accent_color=self._accent_secondary,
        )
        tabs.addTab(self._stats_panel, "Computed")
        return tabs

    def _build_frequency_domain_tab(self) -> QWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        # FFT (live)
        self._fft_trace = FftTraceWidget(max_samples=_TRACE_MAX_SAMPLES)
        self._fft_trace.setMinimumHeight(240)
        tabs.addTab(self._wrap_padded(self._fft_trace), "FFT")
        # Placeholders -- see PlaceholderPanel's own docstring for why.
        for label, detail in (
            ("Order spectrum",
             "Batch-computed from a completed DC record. Add live order tracking to the analysis engine to wire this up."),
            ("Order tracking",
             "Batch-computed from a completed DC record. Needs live tach-based rpm/order tracking."),
            ("Color map",
             "Batch STFT over the DC record. Not streamed today."),
            ("Waterfall",
             "3D magnitude vs. frequency vs. time. Batch-computed from the DC record."),
        ):
            tabs.addTab(
                PlaceholderPanel(label, detail, muted_color=self._muted),
                label,
            )
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

    def _build_parameter_table(self) -> QTableWidget:
        table = QTableWidget(0, len(_PARAMETER_TABLE_COLUMNS))
        table.setHorizontalHeaderLabels(list(_PARAMETER_TABLE_COLUMNS))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setMaximumHeight(180)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(1, len(_PARAMETER_TABLE_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        return table

    # --- toolbar action handling ------------------------------------

    def _on_toolbar_action(self, action: str) -> None:
        """Toolbar buttons don't own routing -- they just emit a name.
        For now surface the action in the top status label so the click
        is observable; MainWindow can subscribe to route to sibling
        screens in a follow-up (see PROGRESS.md)."""
        readable = action.replace("_", " ")
        self._status_label.setText(f"station {self._station_id} — {readable} requested")

    # --- REST callbacks ---------------------------------------------

    def _on_parameters(self, rows: list[dict]) -> None:
        table = self._param_table
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row.get("stat_name", ""),
                "" if row.get("order_number") is None else f"{row['order_number']:.4g}",
                "" if row.get("limit_low") is None else f"{row['limit_low']:.4g}",
                "" if row.get("limit_high") is None else f"{row['limit_high']:.4g}",
                "yes" if row.get("included_in_table_config") else "no",
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))

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
            # Fresh acquisition -- clear the traces and stat panel.
            self._raw_trace.clear()
            self._fft_trace.clear()
            self._stats_panel.clear()
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

    def _handle_signal_chunk(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        values = payload.get("values") or []
        sample_rate_hz = payload.get("sample_rate_hz")
        if not values:
            return
        self._raw_trace.append_samples(values)
        self._fft_trace.append_samples(values, sample_rate_hz=sample_rate_hz)
        # LiveStatsPanel reads from the raw trace's public buffer to
        # avoid keeping a duplicate rolling window in RAM.
        self._stats_panel.update_from_buffer(list(self._raw_trace._buffer))

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
