"""Management-rollup payloads — plain SQL aggregates over test_runs/dc_records,
no analysis-engine involvement."""

from __future__ import annotations

from pydantic import BaseModel


class PassRateRollup(BaseModel):
    group_key: str  # e.g. a date, shift, or line label, per the requested group_by
    total: int
    passed: int
    pass_rate: float


class FailReasonRollup(BaseModel):
    reason_code: str
    count: int
