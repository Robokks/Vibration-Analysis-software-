from datetime import datetime

import pytest
from pydantic import ValidationError

from nvh_contract import (
    CONTRACT_VERSION,
    DcRecord,
    Direction,
    LimitConfigEntry,
    MasterProfile,
    Model,
    OverallResult,
    TableConfigParameterEntry,
    TableConfigStepEntry,
)


def test_contract_version_is_set():
    assert CONTRACT_VERSION == "1.0"


def test_model_teeth_roundtrip():
    model = Model(
        model_id="MODEL-A",
        model_name="Nano 4 Speed",
        drive_teeth={"N": 1, "R": 12},
        idler_teeth_1={"R": 36},
        layshaft_teeth={"N": 0, "R": 32},
        ratios={"R": 3.753},
    )
    assert model.ratios["R"] == 3.753


def test_model_new_optional_fields_default_to_empty_dict():
    model = Model(
        model_id="MODEL-A",
        model_name="Nano 4 Speed",
        drive_teeth={"R": 12},
        idler_teeth_1={"R": 36},
        layshaft_teeth={"R": 32},
        ratios={"R": 3.753},
    )
    assert model.idler_teeth_2 == {}
    assert model.drive_shaft_bearing_roll == {}
    assert model.layshaft_bearing_roll == {}
    assert model.fdr_teeth == {}
    assert model.fd_sel == {}


def test_model_new_optional_fields_roundtrip_when_supplied():
    model = Model(
        model_id="MODEL-A",
        model_name="Nano 4 Speed",
        drive_teeth={"R": 12},
        idler_teeth_1={"R": 36},
        idler_teeth_2={"R": 18},
        layshaft_teeth={"R": 32},
        drive_shaft_bearing_roll={"R": 5.43},
        layshaft_bearing_roll={"R": 7.91},
        fdr_teeth={"FDR1": 27, "FDR2": 30},
        fd_sel={"R": "FDR1"},
        ratios={"R": 3.753},
    )
    assert model.idler_teeth_2["R"] == 18
    assert model.drive_shaft_bearing_roll["R"] == 5.43
    assert model.layshaft_bearing_roll["R"] == 7.91
    assert model.fdr_teeth["FDR1"] == 27
    assert model.fd_sel["R"] == "FDR1"


def test_dc_record_defaults_to_pending():
    dc = DcRecord(
        dc_id="dc-1",
        test_run_id="run-1",
        gear_label="R",
        direction=Direction.RU,
        rpm_start=1000.0,
        rpm_end=2500.0,
        sample_rate_hz=5000.0,
        parquet_path="dc_R_RU.parquet",
    )
    assert dc.result == OverallResult.PENDING
    assert dc.fail_reason_codes == []


def test_direction_round_trips_all_four_values_through_json():
    for direction in Direction:
        dc = DcRecord(
            dc_id="dc-1",
            test_run_id="run-1",
            gear_label="I",
            direction=direction,
            rpm_start=1000.0,
            rpm_end=2500.0,
            sample_rate_hz=5000.0,
            parquet_path="dc.parquet",
        )
        restored = DcRecord.model_validate_json(dc.model_dump_json())
        assert restored.direction == direction


def test_master_profile_roundtrip_through_json():
    profile = MasterProfile(model_id="MODEL-A", program_name="REVA", created_at=datetime(2026, 1, 1))
    restored = MasterProfile.model_validate_json(profile.model_dump_json())
    assert restored.program_name == "REVA"
    assert restored.model_id == "MODEL-A"


def test_limit_config_entry_order_number_defaults_to_none():
    entry = LimitConfigEntry(
        model_id="MODEL-A", program_name="REVA", gear_label="R", direction=Direction.RU,
        stat_name="RMS Avg", limit_low=0.9, limit_high=1.1, updated_at=datetime(2026, 1, 1),
    )
    assert entry.order_number is None
    assert entry.channel_name == "vib_a"
    assert entry.threshold_low == 0.0
    assert entry.threshold_high == 0.0


def test_limit_config_entry_roundtrip_when_fully_supplied():
    entry = LimitConfigEntry(
        model_id="MODEL-A", program_name="REVA", gear_label="R", direction=Direction.RU,
        channel_name="mic", stat_name="IN_H1(g)", order_number=12.0,
        limit_low=0.9, limit_high=1.1, threshold_low=0.05, threshold_high=0.1,
        updated_at=datetime(2026, 1, 1),
    )
    restored = LimitConfigEntry.model_validate_json(entry.model_dump_json())
    assert restored.channel_name == "mic"
    assert restored.order_number == 12.0
    assert restored.threshold_low == 0.05
    assert restored.threshold_high == 0.1


def test_reverse_with_styc_is_representable_but_not_enforced():
    # "R conventionally has no STYC" is a data/config convention (Phase B/E),
    # not a constraint on this contract layer -- this must still validate.
    dc = DcRecord(
        dc_id="dc-1",
        test_run_id="run-1",
        gear_label="R",
        direction=Direction.STYC,
        rpm_start=1000.0,
        rpm_end=2500.0,
        sample_rate_hz=5000.0,
        parquet_path="dc.parquet",
    )
    assert dc.direction == Direction.STYC


def test_table_config_step_entry_roundtrip():
    entry = TableConfigStepEntry(
        model_id="MODEL-A", program_name="REVA", gear_label="R", direction=Direction.RU,
        channel_name="vib_a", step_order=1, updated_at=datetime(2026, 1, 1),
    )
    restored = TableConfigStepEntry.model_validate_json(entry.model_dump_json())
    assert restored.gear_label == "R"
    assert restored.direction == Direction.RU
    assert restored.step_order == 1


def test_table_config_step_entry_step_order_must_be_at_least_one():
    with pytest.raises(ValidationError):
        TableConfigStepEntry(
            model_id="MODEL-A", program_name="REVA", gear_label="R", direction=Direction.RU,
            step_order=0, updated_at=datetime(2026, 1, 1),
        )


def test_table_config_parameter_entry_roundtrip():
    entry = TableConfigParameterEntry(
        model_id="MODEL-A", program_name="REVA", channel_name="vib_a",
        stat_name="RMS Avg", updated_at=datetime(2026, 1, 1),
    )
    restored = TableConfigParameterEntry.model_validate_json(entry.model_dump_json())
    assert restored.stat_name == "RMS Avg"
    assert restored.channel_name == "vib_a"


def test_table_config_parameter_entry_accepts_non_graded_context_columns():
    # "Speed"/"Time" are not PARAMETER_CATALOG keys but the real screen's
    # checklist includes them -- stat_name is a bare str here (see the
    # class docstring), so this must validate.
    entry = TableConfigParameterEntry(
        model_id="MODEL-A", program_name="REVA", stat_name="Speed", updated_at=datetime(2026, 1, 1),
    )
    assert entry.stat_name == "Speed"
