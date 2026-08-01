"""Thin WebSocket client for the realtime ``/live/ws`` stream, built on
``PySide6.QtWebSockets.QWebSocket`` so incoming frames land on the Qt event
loop without a background thread. Mirrors the callback-not-signal style of
``api_client.py``: callers pass plain ``on_event``/``on_status`` callables
rather than binding to Qt signals, keeping screen code readable and free of
QObject-wiring boilerplate.

Every text frame is decoded as JSON and forwarded to ``on_event`` as a plain
dict -- the discriminator/schema lives in
``nvh_api_schemas.realtime.LiveEvent`` and belongs to the screen that
consumes it, not this transport. Auto-reconnects on close/error with a
2-second backoff timer (single-shot QTimer, not ``time.sleep``, so the UI
never blocks)."""

from __future__ import annotations

import json
from typing import Callable

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtWebSockets import QWebSocket

DEFAULT_WS_URL = "ws://127.0.0.1:8000/live/ws"
_RECONNECT_MS = 2000

OnEvent = Callable[[dict], None]
OnStatus = Callable[[str, "str | None"], None]


def _noop_event(_payload: dict) -> None:
    pass


def _noop_status(_state: str, _error: "str | None") -> None:
    pass


class LiveClient(QObject):
    """Auto-reconnecting WebSocket subscriber for ``/live/ws``.

    ``on_event(payload_dict)`` fires once per successfully decoded text
    frame. ``on_status(state, error)`` fires on connect/close/error
    transitions where ``state`` is one of ``"connecting"``, ``"open"``,
    ``"closed"`` and ``error`` is a human-readable string (or ``None`` on
    clean transitions)."""

    def __init__(
        self,
        ws_url: str = DEFAULT_WS_URL,
        on_event: OnEvent = _noop_event,
        on_status: OnStatus = _noop_status,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = QUrl(ws_url)
        # Public attributes so a caller that injected a pre-built client
        # (e.g. a screen that owns the callbacks) can rebind them after
        # construction without reaching into private state.
        self.on_event = on_event
        self.on_status = on_status

        self._socket = QWebSocket()
        self._socket.connected.connect(self._handle_connected)
        self._socket.disconnected.connect(self._handle_disconnected)
        self._socket.errorOccurred.connect(self._handle_error)
        self._socket.textMessageReceived.connect(self._handle_message)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._open_socket)

        self._running = False

    # --- public API ---------------------------------------------------

    def start(self) -> None:
        """Begin the connect loop. Safe to call more than once (a
        second call while already running is a no-op)."""
        if self._running:
            return
        self._running = True
        self._open_socket()

    def stop(self) -> None:
        """Close the socket and cancel any pending reconnect. After
        ``stop()`` no further callbacks fire until ``start()`` is called
        again."""
        self._running = False
        self._reconnect_timer.stop()
        # ``close()`` fires ``disconnected`` even when the socket never
        # opened -- guard the handler against scheduling a reconnect
        # after an intentional stop by checking ``self._running``.
        self._socket.close()

    # --- internals ----------------------------------------------------

    def _open_socket(self) -> None:
        if not self._running:
            return
        self.on_status("connecting", None)
        self._socket.open(self._url)

    def _schedule_reconnect(self) -> None:
        if not self._running:
            return
        if self._reconnect_timer.isActive():
            return
        self._reconnect_timer.start(_RECONNECT_MS)

    def _handle_connected(self) -> None:
        self.on_status("open", None)

    def _handle_disconnected(self) -> None:
        self.on_status("closed", None)
        self._schedule_reconnect()

    def _handle_error(self, _error) -> None:
        # ``errorOccurred`` fires alongside ``disconnected`` for most
        # failure modes; surface the error text here so callers see
        # *why* the socket dropped, and let ``_handle_disconnected``
        # own the reconnect scheduling.
        self.on_status("closed", self._socket.errorString())

    def _handle_message(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            self.on_status("closed", f"invalid JSON from backend: {exc}")
            return
        self.on_event(payload)
