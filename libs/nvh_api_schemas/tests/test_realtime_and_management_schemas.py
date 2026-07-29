import json

import pytest
from pydantic import TypeAdapter, ValidationError

from nvh_api_schemas import (
    FailReasonRollup,
    LiveDcUpdate,
    LiveEvent,
    LiveSignalChunk,
    LiveTestRunUpdate,
    PassRateRollup,
)


def test_live_test_run_update_accepts_valid_status():
    update = LiveTestRunUpdate(test_run_id="run-1", station_id="ST-1", status="RUNNING")
    assert update.overall_result is None


def test_live_test_run_update_rejects_invalid_status():
    with pytest.raises(ValidationError):
        LiveTestRunUpdate(test_run_id="run-1", station_id="ST-1", status="BOGUS")


def test_live_dc_update_defaults_empty_fail_reasons():
    update = LiveDcUpdate(
        dc_id="dc-1", test_run_id="run-1", station_id="ST-1", gear_label="R", direction="RU", stamp="PASS"
    )
    assert update.fail_reason_codes == []


def test_pass_rate_rollup_roundtrip():
    rollup = PassRateRollup(group_key="2026-07-29", total=10, passed=8, pass_rate=0.8)
    assert rollup.model_dump()["pass_rate"] == 0.8


def test_fail_reason_rollup_roundtrip():
    rollup = FailReasonRollup(reason_code="CRASH_NOISE", count=3)
    assert rollup.count == 3


def test_live_events_serialize_with_type_discriminator():
    # Every LiveEvent kind serializes with a `type` field so the WebSocket
    # consumer (browser or Qt) can dispatch on it without needing an
    # envelope wrapper -- the same shape the sibling frontend clients
    # rely on verbatim.
    run = LiveTestRunUpdate(test_run_id="r", station_id="s", status="RUNNING")
    dc = LiveDcUpdate(dc_id="d", test_run_id="r", station_id="s", gear_label="R", direction="RU", stamp="FAIL")
    chunk = LiveSignalChunk(
        test_run_id="r", dc_id="d", station_id="s", gear_label="R", direction="RU",
        channel_name="vib_a", sample_rate_hz=5000.0, chunk_index=3,
        time_s=[0.0, 1.0], values=[0.1, -0.1], rpm=[1000.0, 1005.0],
    )
    assert json.loads(run.model_dump_json())["type"] == "test_run"
    assert json.loads(dc.model_dump_json())["type"] == "dc"
    assert json.loads(chunk.model_dump_json())["type"] == "signal_chunk"


def test_live_event_tagged_union_dispatches_by_type():
    adapter = TypeAdapter(LiveEvent)

    run_payload = LiveTestRunUpdate(test_run_id="r", station_id="s", status="RUNNING").model_dump_json()
    assert isinstance(adapter.validate_json(run_payload), LiveTestRunUpdate)

    chunk_payload = LiveSignalChunk(
        test_run_id="r", dc_id="d", station_id="s", gear_label="R", direction="RU",
        channel_name="vib_a", sample_rate_hz=5000.0, chunk_index=0,
        time_s=[], values=[], rpm=[],
    ).model_dump_json()
    assert isinstance(adapter.validate_json(chunk_payload), LiveSignalChunk)
