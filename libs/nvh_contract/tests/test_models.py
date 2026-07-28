from nvh_contract import CONTRACT_VERSION, DcRecord, Direction, Model, OverallResult


def test_contract_version_is_set():
    assert CONTRACT_VERSION == "1.0"


def test_model_teeth_roundtrip():
    model = Model(
        model_id="MODEL-A",
        model_name="Nano 4 Speed",
        drive_teeth={"N": 1, "R": 12},
        idler_teeth={"R": 36},
        layshaft_teeth={"N": 0, "R": 32},
        ratios={"R": 3.753},
    )
    assert model.ratios["R"] == 3.753


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
