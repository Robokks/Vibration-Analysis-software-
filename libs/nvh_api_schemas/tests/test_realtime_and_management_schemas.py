import pytest
from pydantic import ValidationError

from nvh_api_schemas import FailReasonRollup, LiveDcUpdate, LiveTestRunUpdate, PassRateRollup


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
