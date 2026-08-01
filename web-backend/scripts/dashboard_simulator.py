"""No-hardware alternative to `dashboard_bridge.py`. Loops a scripted
sequence of dashboard-side identifiers (model / serial / serial_rpt /
operator_name) and POSTs each one straight to the FastAPI backend's
`/dashboard/context` endpoint.

Skips the NI DataSocket layer entirely -- the whole point of having a
simulator peer is not needing DataSocket. Useful for demoing the
Phase K persistence path end-to-end on Linux or on a Windows dev
machine without a real dashboard application running.

Usage:
    python web-backend/scripts/dashboard_simulator.py \\
        --backend-url http://localhost:8000 --station-id STATION-1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request


# (model_name, serial_no, serial_rpt, operator_name). Kept small on
# purpose -- the point is to demonstrate the "context changes" the
# backend responds to, not to stress-test.
SCRIPTED_SEQUENCE: list[tuple[str, str, str, str | None]] = [
    ("MODEL-A", "SN-42", "1", "Alex"),
    ("MODEL-A", "SN-42", "2", "Alex"),
    ("MODEL-B", "SN-99", "1", "Bob"),
]


def _post_context(backend_url: str, station_id: str, entry: tuple[str, str, str, str | None]) -> None:
    """Fire-and-forget POST to /dashboard/context. Mirrors _post_summary
    in live_simulator.py -- prints one line on error and moves on so
    the simulator loop can't be killed by a temporarily-down backend."""
    model_name, serial_no, serial_rpt, operator_name = entry
    body = json.dumps({
        "station_id": station_id,
        "model_name": model_name,
        "serial_no": serial_no,
        "serial_rpt": serial_rpt,
        "operator_name": operator_name,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{backend_url.rstrip('/')}/dashboard/context",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            resp.read()
        print(
            f"dashboard_simulator: POST -> {model_name} {serial_no}/{serial_rpt} "
            f"operator={operator_name!r}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"dashboard_simulator: POST failed: {exc}", file=sys.stderr, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scripted dashboard-context POSTs, no DataSocket needed")
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("NVH_BACKEND_URL", "http://localhost:8000"),
        help="FastAPI backend base URL (default: http://localhost:8000 or $NVH_BACKEND_URL)",
    )
    parser.add_argument(
        "--station-id",
        default=os.environ.get("NVH_STATION_ID", "STATION-1"),
        help="station_id sent with every POST (default STATION-1 or $NVH_STATION_ID)",
    )
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds between context updates (default 2.0)")
    parser.add_argument("--once", action="store_true",
                        help="Run the sequence once and exit (default: loop forever)")
    args = parser.parse_args()

    print(f"dashboard_simulator: posting to {args.backend_url} (station {args.station_id!r})", flush=True)

    try:
        while True:
            for entry in SCRIPTED_SEQUENCE:
                _post_context(args.backend_url, args.station_id, entry)
                time.sleep(args.interval)
            if args.once:
                break
    except KeyboardInterrupt:
        print("dashboard_simulator: shutting down", flush=True)


if __name__ == "__main__":
    main()
