"""WebSocket event payloads pushed to the operator view."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LiveTestRunUpdate(BaseModel):
    test_run_id: str
    station_id: str
    status: Literal["RUNNING", "COMPLETED"]
    overall_result: str | None = None


class LiveDcUpdate(BaseModel):
    dc_id: str
    test_run_id: str
    station_id: str
    gear_label: str
    direction: str
    stamp: Literal["PASS", "FAIL"]
    fail_reason_codes: list[str] = []
