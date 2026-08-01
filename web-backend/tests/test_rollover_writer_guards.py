"""Regression tests for `_open_rollover_writer`'s gear/nvh id guards
(Phase O Bug 3d)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_SIM = REPO_ROOT / "web-backend" / "scripts" / "live_simulator.py"


@pytest.fixture(scope="module")
def live_sim_module():
    spec = importlib.util.spec_from_file_location("_live_sim_for_tests", LIVE_SIM)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_live_sim_for_tests"] = module
    spec.loader.exec_module(module)
    return module


class RolloverWriterGuardTests:
    """`_open_rollover_writer` must return None (no file opened) for
    any invalid gear_id or nvh_id -- not just negative sentinels but
    unknown positive values like 5 or 99. Prior to Phase O Bug 3d,
    a rogue PLC packet with nvh_id=5 produced a real file at
    `SN-XXX_1_5.tdms`, encoding an invalid id into the filename."""

    def test_negative_sentinel_returns_none(self, live_sim_module, tmp_path):
        assert live_sim_module._open_rollover_writer(
            str(tmp_path), trial_no=1, gear_id=-1, nvh_id=0,
            model_id="M", serial_no="S", serial_rpt=1,
        ) is None
        assert live_sim_module._open_rollover_writer(
            str(tmp_path), trial_no=1, gear_id=1, nvh_id=-1,
            model_id="M", serial_no="S", serial_rpt=1,
        ) is None

    def test_unknown_nvh_id_returns_none(self, live_sim_module, tmp_path):
        # Bug 3d: rogue nvh_id=5 used to open `SN-M_1_5.tdms`.
        writer = live_sim_module._open_rollover_writer(
            str(tmp_path), trial_no=1, gear_id=1, nvh_id=5,
            model_id="M", serial_no="S", serial_rpt=1,
        )
        assert writer is None
        # And no directory tree was created for the invalid id.
        assert not list(tmp_path.rglob("*.tdms"))

    def test_unknown_gear_id_returns_none(self, live_sim_module, tmp_path):
        writer = live_sim_module._open_rollover_writer(
            str(tmp_path), trial_no=1, gear_id=99, nvh_id=0,
            model_id="M", serial_no="S", serial_rpt=1,
        )
        assert writer is None
        assert not list(tmp_path.rglob("*.tdms"))

    def test_valid_ids_open_writer(self, live_sim_module, tmp_path):
        # Positive test -- confirm the guard didn't reject valid inputs.
        try:
            from nptdms import TdmsWriter  # noqa: F401
        except ImportError:
            pytest.skip("nptdms not installed")
        writer = live_sim_module._open_rollover_writer(
            str(tmp_path), trial_no=1, gear_id=1, nvh_id=0,
            model_id="M", serial_no="S", serial_rpt=1,
        )
        assert writer is not None
        writer.close()
        assert list(tmp_path.rglob("S_1_0.tdms"))
