import json
from datetime import datetime

import numpy as np
import pytest
from nvh_contract.models import DcRecord, Direction, Model, OverallResult, TestRun

from analysis_engine.grading.master_builder import build_master_signature
from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from analysis_engine.pipeline import STAT_NAMES, analyze_dc_record, build_masters_from_trials, stats_to_dict
from analysis_engine.reports.consolidated import build_consolidated_report
from analysis_engine.reports.detailed import build_detailed_report
from analysis_engine.reports.serialization import to_jsonable
from analysis_engine.reports.summary import SummaryReportRow, build_summary_report
from analysis_engine.signal.stats import compute_stats

GEAR_R = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
SAMPLE_RATE_HZ = 5000.0
DURATION_S = 3.0
FULL_SCALE_BY_STAT = {name: 10.0 for name in STAT_NAMES}


def _healthy_signal(seed: int, rpm_start=1000.0, rpm_end=2500.0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SAMPLE_RATE_HZ * DURATION_S)) / SAMPLE_RATE_HZ
    rpm = rpm_start + (rpm_end - rpm_start) * (t / DURATION_S)
    omega = 2 * np.pi * rpm / 60.0
    theta = np.cumsum(omega) / SAMPLE_RATE_HZ
    signal = np.sin(GEAR_R.mesh_order * theta) + rng.normal(0, 0.02, size=t.shape)
    return signal, t, rpm


def _crash_faulted_signal(seed: int):
    signal, t, rpm = _healthy_signal(seed)
    rng = np.random.default_rng(seed + 1)
    window = (t >= 1.0) & (t <= 1.2)
    signal = signal.copy()
    signal[window] += rng.normal(0, 6.0, size=int(window.sum()))
    return signal, t, rpm


def _dummy_test_run(result: OverallResult = OverallResult.PENDING) -> TestRun:
    return TestRun(
        test_run_id="run-1",
        model_id="MODEL-A",
        serial_number="4112DK01781",
        started_at=datetime(2026, 1, 1),
        overall_result=result,
    )


def _dummy_dc_record() -> DcRecord:
    return DcRecord(
        dc_id="dc-1",
        test_run_id="run-1",
        gear_label="R",
        direction=Direction.RU,
        rpm_start=1000.0,
        rpm_end=2500.0,
        sample_rate_hz=SAMPLE_RATE_HZ,
        parquet_path="dc_R_RU.parquet",
    )


def _dummy_model() -> Model:
    return Model(
        model_id="MODEL-A",
        model_name="Nano 4 Speed",
        drive_teeth={"R": 12},
        idler_teeth_1={"R": 36},
        layshaft_teeth={"R": 32},
        ratios={"R": 3.753},
    )


def _build_masters():
    trial_stats = []
    for seed in range(10, 40):
        signal, _, _ = _healthy_signal(seed)
        trial_stats.append(compute_stats(signal))
    return build_masters_from_trials(trial_stats, FULL_SCALE_BY_STAT)


def test_consolidated_report_stamps_healthy_unit_pass():
    masters = _build_masters()
    signal, t, rpm = _healthy_signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)

    report = build_consolidated_report(_dummy_test_run(), _dummy_dc_record(), _dummy_model(), result)

    assert report.stamp == "PASS"
    assert report.model.model_id == "MODEL-A"


def test_consolidated_report_stamps_faulted_unit_fail():
    masters = _build_masters()
    signal, t, rpm = _crash_faulted_signal(1234)
    result = analyze_dc_record(
        signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters,
        crash_noise_band_hz=(500.0, 2000.0), crash_noise_threshold=0.5,
    )

    report = build_consolidated_report(_dummy_test_run(), _dummy_dc_record(), _dummy_model(), result)

    assert report.stamp == "FAIL"
    assert "CRASH_NOISE" in report.result.fail_reason_codes


def test_detailed_report_has_one_row_per_stat_linked_to_grading():
    masters = _build_masters()
    signal, t, rpm = _healthy_signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
    consolidated = build_consolidated_report(_dummy_test_run(), _dummy_dc_record(), _dummy_model(), result)

    detailed = build_detailed_report(consolidated, masters)

    assert len(detailed.numeric_table) == len(STAT_NAMES)
    stat_values = stats_to_dict(result.stats)
    for row in detailed.numeric_table:
        assert row.observed_value == pytest.approx(stat_values[row.stat_name])
        assert row.master is masters[row.stat_name]
        assert row.grading is result.grading.per_stat[row.stat_name]


def test_summary_report_reuses_spc_math_across_units():
    masters = _build_masters()
    rows = []
    for seed in range(5):
        signal, t, rpm = _healthy_signal(seed + 500)
        result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
        rows.append(SummaryReportRow(test_run=_dummy_test_run(), dc_record=_dummy_dc_record(), result=result))

    summary = build_summary_report(rows, stat_name="rms")

    assert summary.model_id == "MODEL-A"
    assert summary.gear_label == "R"
    assert len(summary.rows) == 5
    assert summary.xchart.center_line == pytest.approx(
        sum(stats_to_dict(r.result.stats)["rms"] for r in rows) / 5
    )


def test_summary_report_requires_at_least_one_row():
    with pytest.raises(ValueError):
        build_summary_report([], stat_name="rms")


def test_to_jsonable_round_trips_consolidated_report_through_json():
    masters = _build_masters()
    signal, t, rpm = _healthy_signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
    report = build_consolidated_report(_dummy_test_run(), _dummy_dc_record(), _dummy_model(), result)

    jsonable = to_jsonable(report)
    encoded = json.dumps(jsonable)  # must not raise (no leftover ndarray/Enum/dataclass)
    decoded = json.loads(encoded)

    assert decoded["stamp"] == "PASS"
    assert decoded["test_run"]["model_id"] == "MODEL-A"
    assert isinstance(decoded["result"]["order_spectrum"]["magnitude"], list)
