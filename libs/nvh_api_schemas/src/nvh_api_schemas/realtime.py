"""Realtime event payloads for the operator's Live Display screen.

The transport layout: a producer (today: `web-backend/scripts/live_simulator.py`;
later: LabVIEW) publishes these payloads over ZeroMQ PUB, the FastAPI
backend's `/live/ws` WebSocket relays them to connected browsers, and Qt
clients subscribe to the same WebSocket for a consistent shape across
both GUIs. Every message is a `LiveEvent` -- a `type`-tagged union so a
single WebSocket carries every event kind in one stream, matching the
existing `analysis_engine.reports` convention of one API surface per
concern rather than a socket-per-event-kind."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


class LiveTestRunUpdate(BaseModel):
    type: Literal["test_run"] = "test_run"
    test_run_id: str
    station_id: str
    status: Literal["RUNNING", "COMPLETED"]
    overall_result: str | None = None


class LiveDcUpdate(BaseModel):
    type: Literal["dc"] = "dc"
    dc_id: str
    test_run_id: str
    station_id: str
    gear_label: str
    direction: str
    stamp: Literal["PASS", "FAIL"]
    fail_reason_codes: list[str] = []


class LiveSignalChunk(BaseModel):
    """A slice of the current DC record's raw time-series, streamed at
    wall-clock pace so the operator's plot updates as acquisition runs
    (rather than only jumping once the whole DC record finishes). Every
    chunk carries the sample_rate_hz + chunk_index so a receiver can
    reassemble the ordering without relying on delivery order (ZeroMQ PUB
    doesn't guarantee it under load, though our demo won't stress that)."""

    type: Literal["signal_chunk"] = "signal_chunk"
    test_run_id: str
    dc_id: str
    station_id: str
    gear_label: str
    direction: str
    channel_name: str
    sample_rate_hz: float
    chunk_index: int
    time_s: list[float]
    values: list[float]
    rpm: list[float]


LiveEvent = Union[LiveTestRunUpdate, LiveDcUpdate, LiveSignalChunk]


class LiveEventEnvelope(BaseModel):
    """Small wrapper so `model_validate({"event": {...}})` can dispatch on
    the inner `type` field. Callers usually serialize the inner event
    directly rather than this envelope -- it exists mainly to give the
    tagged-union discrimination a name for `pydantic.TypeAdapter`."""

    event: LiveEvent = Field(discriminator="type")
