"""Wire schemas for the dashboard-app <-> NVH-app link (Phase K).

Two directions:
- Dashboard IN via NI DataSocket -> `dashboard_bridge.py` -> POST
  /dashboard/context on the FastAPI backend. `IngestContextIn` /
  `IngestContextOut` mirror the payload.
- NVH OUT: `dashboard_bridge.py` writes a `HeartbeatOut` blob back on
  a separate DataSocket URL at ~1 Hz.
"""

from __future__ import annotations

from pydantic import BaseModel


class IngestContextIn(BaseModel):
    """Body of POST /dashboard/context. Sent by the dashboard app via
    the DataSocket bridge."""

    station_id: str
    model_name: str
    serial_no: str
    serial_rpt: str = "1"
    operator_name: str | None = None


class IngestContextOut(BaseModel):
    station_id: str
    model_name: str
    serial_no: str
    serial_rpt: str
    operator_name: str | None
    received_at: str  # ISO-8601 UTC


class HeartbeatOut(BaseModel):
    """Payload NVH writes back to the dashboard's heartbeat DataSocket
    URL each interval (~1 s). Small on purpose so DataSocket's XML
    packing stays cheap."""

    status: str  # "OK" | "IDLE" | "ERROR"
    timestamp: str  # ISO-8601 UTC
    current_gear_id: int
    current_nvh_id: int
