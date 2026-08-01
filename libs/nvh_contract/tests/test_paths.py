from datetime import datetime, timezone
from pathlib import Path

from nvh_contract.paths import raw_tdms_path, state_file_path


class RawTdmsPathTests:
    def _when(self):
        return datetime(2026, 7, 31, 14, 30, tzinfo=timezone.utc)

    def test_nested_layout_matches_requirement(self):
        p = raw_tdms_path(
            base_dir="/data/raw",
            model_id="MODEL-A",
            serial_no="SN-42",
            serial_rpt=2,
            trial_no=7,
            gear_id=1,
            nvh_id=0,
            when=self._when(),
        )
        assert p == Path("/data/raw/2026/07/31/Trial7/MODEL-A/SN-42_2/SN-42_1_0.tdms")

    def test_string_serial_rpt_works(self):
        p = raw_tdms_path(
            base_dir="./data/raw",
            model_id="M",
            serial_no="A",
            serial_rpt="R2",
            trial_no=1,
            gear_id=0,
            nvh_id=1,
            when=self._when(),
        )
        assert "A_R2" in p.parts

    def test_filename_encodes_gear_and_nvh(self):
        p = raw_tdms_path(
            base_dir="/x", model_id="m", serial_no="s", serial_rpt=1,
            trial_no=1, gear_id=6, nvh_id=3, when=self._when(),
        )
        assert p.name == "s_6_3.tdms"


class StateFilePathTests:
    def test_returns_expected_file(self):
        assert state_file_path("/data/raw") == Path("/data/raw/state.json")
