"""Realtime operator screen -- consumes ``LiveEvent`` frames off the
``/live/ws`` WebSocket (see ``nvh_api_schemas.realtime``) and updates the
status header, signal trace, and DC-record card grid in place.

The event stream is a three-kind tagged union: ``test_run`` (test start/end),
``dc`` (per-gear/direction stamp), and ``signal_chunk`` (a slice of the raw
time-series streamed at wall-clock pace, ~10 chunks/second). This screen
plays the sibling web-frontend role in Qt -- same data source, same visual
grammar (graticule background, mono/value labels, PASS/FAIL stamp
colouring)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nvh_design_tokens import load_tokens

from ..live_client import LiveClient
from ..widgets.gear_glyph import GearGlyphWidget
from ..widgets.labels import AlarmLabel, MonoLabel, PassLabel, SectionTitle, ValueLabel
from ..widgets.panel import Panel
from ..widgets.signal_trace import SignalTraceWidget

_PLACEHOLDER = "—"  # em-dash, matches the web-frontend scaffold value
_DEFAULT_STATION = "STN-01"
_TRACE_MAX_SAMPLES = 4000

_CARD_ORDER = ("Test run", "Gear", "Direction", "Stamp")


class LiveDisplayScreen(QWidget):
    """Operator-facing live view. Wired to a ``LiveClient`` in the
    constructor so tests can inject a fake and the app can pass a
    pre-configured URL; when ``live_client`` is ``None`` a default one is
    constructed and started on show."""

    def __init__(self, parent=None, live_client: LiveClient | None = None) -> None:
        super().__init__(parent)
        tokens = load_tokens()
        accent_secondary = tokens["color"]["palettes"]["dark"]["accentSecondary"]

        # --- state --------------------------------------------------
        self._station_id = _DEFAULT_STATION
        self._test_run_id: str | None = None
        self._test_run_status: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- status row --------------------------------------------
        status_row = QHBoxLayout()
        indicator = GearGlyphWidget(color=accent_secondary, spinning=True)
        indicator.setFixedSize(40, 30)
        status_row.addWidget(indicator)
        self._status_label = MonoLabel("connecting…")
        status_row.addWidget(self._status_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        # --- trace --------------------------------------------------
        self._trace = SignalTraceWidget(max_samples=_TRACE_MAX_SAMPLES)
        self._trace.setMinimumHeight(280)
        layout.addWidget(self._trace, stretch=1)

        # --- card grid ---------------------------------------------
        cards = QGridLayout()
        cards.setSpacing(12)
        # Keep a handle on each card's inner layout so we can swap the
        # stamp value widget between ValueLabel / PassLabel / AlarmLabel
        # (they're distinct types so QSS can style them, not swappable
        # via ``setProperty``) and update the other cards' text in place.
        self._card_layouts: dict[str, QVBoxLayout] = {}
        self._card_values: dict[str, QLabel] = {}
        for col, label in enumerate(_CARD_ORDER):
            panel, panel_layout, value_widget = self._build_card(label, _PLACEHOLDER)
            self._card_layouts[label] = panel_layout
            self._card_values[label] = value_widget
            cards.addWidget(panel, 0, col)
        layout.addLayout(cards)

        # --- wire the client ---------------------------------------
        self._client = live_client if live_client is not None else LiveClient()
        # Bind callbacks after construction so both the default (built
        # here) and an injected (test-supplied) client fire this screen's
        # handlers -- LiveClient exposes ``on_event``/``on_status`` as
        # public rebindable attributes for exactly this reason.
        self._client.on_event = self._on_event
        self._client.on_status = self._on_status
        self._client.start()

    # --- card construction ------------------------------------------

    @staticmethod
    def _build_card(label: str, value: str) -> tuple[Panel, QVBoxLayout, QLabel]:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        title = SectionTitle(label)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        panel_layout.addWidget(title)
        value_widget = ValueLabel(value)
        panel_layout.addWidget(value_widget)
        return panel, panel_layout, value_widget

    def _set_card_text(self, label: str, text: str) -> None:
        widget = self._card_values[label]
        widget.setText(text)

    def _set_stamp(self, stamp: str) -> None:
        """Swap the Stamp card's value widget for the correct label
        subclass so the theme's PassLabel/AlarmLabel QSS rules apply.
        PENDING (or any unknown/empty value) uses the neutral
        ValueLabel."""
        panel_layout = self._card_layouts["Stamp"]
        old = self._card_values["Stamp"]
        if stamp == "PASS":
            new: QLabel = PassLabel(stamp)
        elif stamp == "FAIL":
            new = AlarmLabel(stamp)
        else:
            new = ValueLabel(stamp or "PENDING")
        # Replace at the same layout position (index 1: title is at 0).
        panel_layout.replaceWidget(old, new)
        old.deleteLater()
        self._card_values["Stamp"] = new

    # --- WebSocket callbacks ----------------------------------------

    def _on_status(self, state: str, error: str | None) -> None:
        if state == "connecting":
            self._status_label.setText("connecting…")
            return
        if state == "open":
            self._status_label.setText(self._compose_status())
            return
        if state == "closed":
            # Preserve any error string in the label so operators see
            # *why* the socket dropped ("Connection refused",
            # "Host not found", ...) rather than a bare "connection lost".
            suffix = f": {error}" if error else ""
            self._status_label.setText(
                f"station {self._station_id} — connection lost{suffix}"
            )

    def _on_event(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("type")
        if event_type == "test_run":
            self._handle_test_run(payload)
        elif event_type == "dc":
            self._handle_dc(payload)
        elif event_type == "signal_chunk":
            self._handle_signal_chunk(payload)
        # Unknown types: silently ignore -- forwards compatible with
        # future kinds added to the LiveEvent union.

    def _handle_test_run(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        self._test_run_id = payload.get("test_run_id")
        self._test_run_status = payload.get("status")
        self._set_card_text("Test run", self._test_run_id or _PLACEHOLDER)

        if self._test_run_status == "RUNNING":
            # Fresh acquisition -- reset the per-DC card values and the
            # trace so the previous run's tail doesn't linger on screen.
            self._set_card_text("Gear", _PLACEHOLDER)
            self._set_card_text("Direction", _PLACEHOLDER)
            self._set_stamp("PENDING")
            self._trace.clear()

        self._status_label.setText(self._compose_status())

    def _handle_dc(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        gear = payload.get("gear_label") or _PLACEHOLDER
        direction = payload.get("direction") or _PLACEHOLDER
        stamp = payload.get("stamp") or "PENDING"
        self._set_card_text("Gear", gear)
        self._set_card_text("Direction", direction)
        self._set_stamp(stamp)
        # A dc event doesn't change the running/completed status of the
        # test run itself -- the status header only reflects test_run
        # transitions.

    def _handle_signal_chunk(self, payload: dict[str, Any]) -> None:
        self._station_id = payload.get("station_id") or self._station_id
        values = payload.get("values") or []
        if values:
            self._trace.append_samples(values)

    # --- status-string composer -------------------------------------

    def _compose_status(self) -> str:
        station = self._station_id
        if self._test_run_id is None:
            return f"station {station} — awaiting test run"
        if self._test_run_status == "RUNNING":
            return f"station {station} — {self._test_run_id} running…"
        if self._test_run_status == "COMPLETED":
            return f"station {station} — {self._test_run_id} completed"
        return f"station {station} — {self._test_run_id}"

    # --- lifecycle --------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Stop the reconnect timer + socket cleanly so the widget can be
        # torn down (in tests, or on app quit) without leaking a
        # background reconnection loop.
        self._client.stop()
        super().closeEvent(event)
