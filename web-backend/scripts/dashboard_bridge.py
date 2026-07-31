"""Bridge the dashboard app <-> NVH app via NI DataSocket (Phase K).

Two data flows on two DataSocket URLs:

- IN  (dstp://.../nvh/context): the dashboard writes an XML struct
  containing model_name / serial_no / serial_rpt / operator_name. This
  script polls the URL, and on every value change forwards the payload
  as POST /dashboard/context to the FastAPI backend.
- OUT (dstp://.../nvh/heartbeat): once per second this script writes
  a HeartbeatOut XML struct back with status + timestamp + current
  gear_id + nvh_id (pulled from GET /dashboard/context and the last
  known PLC state via GET on the same backend).

DataSocket is an ActiveX COM object with no pure-Python binding, so we
use pywin32 + `win32com.client.Dispatch("CWDataSocket.Data")`. Windows-
only in practice. Everything except the two Dispatch calls is
protocol-agnostic, so tests inject a fake `_DataSocketClient` via the
`--client-factory` hook (exercised in test_dashboard_bridge.py).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Protocol


class _DataSocketClient(Protocol):
    def read_context(self) -> dict[str, Any] | None: ...
    def write_heartbeat(self, blob: dict[str, Any]) -> None: ...


def _real_com_client(context_url: str, heartbeat_url: str) -> _DataSocketClient:
    """Concrete DataSocket client using pywin32. Deferred import so
    Linux CI / non-Windows machines can still import the module."""
    try:
        import win32com.client  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover -- import path
        print(
            "dashboard_bridge: pywin32 not installed. Install with "
            "`pip install -r requirements-dashboard.txt` on Windows.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    class _Impl:
        def __init__(self) -> None:
            self._in = win32com.client.Dispatch("CWDataSocket.Data")
            self._in.ConnectTo(context_url, 1)  # 1 = connect for read
            self._out = win32com.client.Dispatch("CWDataSocket.Data")
            self._out.ConnectTo(heartbeat_url, 2)  # 2 = connect for write

        def read_context(self) -> dict[str, Any] | None:
            value = self._in.Value
            if not value:
                return None
            # Phase O Bug 6: JSON on the wire, not k=v pairs. The
            # previous parser (`str(value).split(",")` then split on `=`)
            # broke on operator names or serials containing commas and
            # silently returned None on any parse error, blocking all
            # context propagation. If a real dashboard emits XML we can
            # add a branch here, but JSON is the only well-defined
            # format for now.
            try:
                parsed = json.loads(str(value))
            except (ValueError, TypeError) as exc:
                print(
                    f"dashboard_bridge: DataSocket read_context JSON decode failed: {exc}",
                    file=sys.stderr, flush=True,
                )
                return None
            if not isinstance(parsed, dict):
                print(
                    f"dashboard_bridge: DataSocket payload was {type(parsed).__name__}, expected dict",
                    file=sys.stderr, flush=True,
                )
                return None
            return parsed

        def write_heartbeat(self, blob: dict[str, Any]) -> None:
            self._out.Value = json.dumps(blob)

    return _Impl()


def _post_context(backend_url: str, body: dict[str, Any]) -> None:
    try:
        req = urllib.request.Request(
            f"{backend_url.rstrip('/')}/dashboard/context",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"dashboard_bridge: context POST failed: {exc}", file=sys.stderr, flush=True)


def _fetch_plc_state(backend_url: str) -> dict[str, Any]:
    """Phase O Bug 4: real gear_id / nvh_id come from the backend's
    LiveRelay cache, not from the dashboard-IN payload (which never
    contained them). On any error, fall back to the -1 sentinels --
    heartbeat is best-effort, don't kill the loop."""
    try:
        with urllib.request.urlopen(
            f"{backend_url.rstrip('/')}/plc/state", timeout=1.5
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {"gear_id": -1, "nvh_id": -1}


def run_bridge(
    backend_url: str,
    station_id: str,
    poll_hz: float,
    heartbeat_hz: float,
    client_factory: Callable[[], _DataSocketClient],
    *,
    max_iterations: int | None = None,
) -> None:
    """Main loop. `max_iterations` lets tests bound how long we run."""
    client = client_factory()
    poll_period = 1.0 / max(0.1, poll_hz)
    hb_period = 1.0 / max(0.1, heartbeat_hz)
    last_context: dict[str, Any] | None = None
    next_hb_at = time.monotonic()
    iter_count = 0
    print(f"dashboard_bridge: bridging to {backend_url} (station {station_id!r})", flush=True)

    while True:
        context = client.read_context()
        if context and context != last_context:
            body = {
                "station_id": station_id,
                "model_name": context.get("model_name", "UNKNOWN"),
                "serial_no": context.get("serial_no", ""),
                "serial_rpt": context.get("serial_rpt", "1"),
                "operator_name": context.get("operator_name") or None,
            }
            _post_context(backend_url, body)
            last_context = context

        now = time.monotonic()
        if now >= next_hb_at:
            plc_state = _fetch_plc_state(backend_url)
            client.write_heartbeat({
                "status": "OK",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_gear_id": plc_state.get("gear_id", -1),
                "current_nvh_id": plc_state.get("nvh_id", -1),
            })
            next_hb_at = now + hb_period

        iter_count += 1
        if max_iterations is not None and iter_count >= max_iterations:
            return
        time.sleep(poll_period)


def main() -> None:
    parser = argparse.ArgumentParser(description="NI DataSocket <-> NVH backend bridge")
    parser.add_argument("--backend-url", default=os.environ.get("NVH_BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--station-id", default=os.environ.get("NVH_STATION_ID", "STATION-1"))
    parser.add_argument("--context-url", default=os.environ.get("NVH_DS_CONTEXT_URL", "dstp://localhost/nvh/context"))
    parser.add_argument("--heartbeat-url", default=os.environ.get("NVH_DS_HEARTBEAT_URL", "dstp://localhost/nvh/heartbeat"))
    parser.add_argument("--poll-hz", type=float, default=2.0)
    parser.add_argument("--heartbeat-hz", type=float, default=1.0)
    args = parser.parse_args()

    def _factory() -> _DataSocketClient:
        return _real_com_client(args.context_url, args.heartbeat_url)

    try:
        run_bridge(args.backend_url, args.station_id, args.poll_hz, args.heartbeat_hz, _factory)
    except KeyboardInterrupt:
        print("dashboard_bridge: shutting down", flush=True)


if __name__ == "__main__":
    main()
