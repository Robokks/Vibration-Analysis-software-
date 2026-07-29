"""Contract tests: real analysis-engine report objects, serialized via
to_jsonable(), must validate against the nvh_api_schemas classes the backend
will declare as response_model and the Qt client will parse against. This is
the concrete guard against the two drifting apart."""

from datetime import datetime

import numpy as np
from nvh_contract.models import DcRecord, Direction, Model, TestRun

from analysis_engine.grading.master_builder import build_master_signature
from analysis_engine.grading.parameters import default_full_scale_by_param
from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from analysis_engine.pipeline import analyze_dc_record, build_masters_from_trials, compute_trial_parameters
from analysis_engine.reports.consolidated import build_consolidated_report
from analysis_engine.reports.detailed import build_detailed_report
from analysis_engine.reports.serialization import to_jsonable
from analysis_engine.reports.summary import SummaryReportRow, build_summary_report
from nvh_api_schemas import ConsolidatedReportOut, DetailedReportOut, SummaryReportOut

GEAR_R = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
SAMPLE_RATE_HZ = 5000.0
DURATION_S = 3.0
FULL_SCALE_BY_PARAM = default_full_scale_by_param()


def _signal(seed):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SAMPLE_RATE_HZ * DURATION_S)) / SAMPLE_RATE_HZ
    rpm = 1000 + (2500 - 1000) * (t / DURATION_S)
    theta = np.cumsum(2 * np.pi * rpm / 60.0) / SAMPLE_RATE_HZ
    signal = np.sin(GEAR_R.mesh_order * theta) + rng.normal(0, 0.02, size=t.shape)
    return signal, t, rpm


def _masters():
    trial_parameters = []
    for seed in range(10, 40):
        signal, t, rpm = _signal(seed)
        trial_parameters.append(compute_trial_parameters(signal, t, rpm, GEAR_R))
    return build_masters_from_trials(trial_parameters, FULL_SCALE_BY_PARAM)


def _test_run():
    return TestRun(test_run_id="run-1", model_id="MODEL-A", serial_number="SN-1", started_at=datetime(2026, 1, 1))


def _dc_record():
    return DcRecord(
        dc_id="dc-1", test_run_id="run-1", gear_label="R", direction=Direction.RU,
        rpm_start=1000.0, rpm_end=2500.0, sample_rate_hz=SAMPLE_RATE_HZ, parquet_path="x.parquet",
    )


def _model():
    return Model(model_id="MODEL-A", model_name="Nano 4 Speed", drive_teeth={"R": 12},
                 idler_teeth_1={"R": 36}, layshaft_teeth={"R": 32}, ratios={"R": 3.753})


def _as_api_dict(result) -> dict:
    """Mirrors what the (future) backend's report_service does: serialize via
    to_jsonable, then add the `passed` property explicitly since it's computed,
    not a dataclass field, so to_jsonable() doesn't emit it on its own."""
    payload = to_jsonable(result)
    payload["passed"] = result.passed
    return payload


def test_consolidated_report_matches_schema():
    masters = _masters()
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
    report = build_consolidated_report(_test_run(), _dc_record(), _model(), result)

    payload = to_jsonable(report)
    payload["result"]["passed"] = result.passed

    validated = ConsolidatedReportOut.model_validate(payload)
    assert validated.stamp == "PASS"
    assert validated.model.model_id == "MODEL-A"
    assert validated.result.order_spectrum.order  # non-empty list


def test_detailed_report_matches_schema():
    masters = _masters()
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
    consolidated = build_consolidated_report(_test_run(), _dc_record(), _model(), result)
    detailed = build_detailed_report(consolidated, masters)

    payload = to_jsonable(detailed)
    payload["consolidated"]["result"]["passed"] = result.passed

    validated = DetailedReportOut.model_validate(payload)
    assert len(validated.numeric_table) == len(result.parameters)
    assert all(row.master is not None for row in validated.numeric_table)


def test_summary_report_matches_schema():
    masters = _masters()
    rows = []
    for seed in range(5):
        signal, t, rpm = _signal(seed + 500)
        result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
        rows.append(SummaryReportRow(test_run=_test_run(), dc_record=_dc_record(), result=result))
    summary = build_summary_report(rows, stat_name="RMS Avg")

    payload = to_jsonable(summary)
    for row_payload, row in zip(payload["rows"], rows):
        row_payload["result"]["passed"] = row.result.passed

    validated = SummaryReportOut.model_validate(payload)
    assert validated.stat_name == "RMS Avg"
    assert len(validated.rows) == 5
