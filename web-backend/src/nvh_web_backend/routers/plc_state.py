"""GET /plc/state -- returns the last-known PLC state cached by LiveRelay
(Phase O Bug 4). The dashboard bridge's heartbeat loop hits this each
tick to build a real (not always -1) heartbeat blob."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/plc/state")
def get_plc_state(request: Request) -> dict:
    return request.app.state.live_relay.plc_state()
