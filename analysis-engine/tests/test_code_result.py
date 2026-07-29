import numpy as np
import pytest

from analysis_engine.grading.limit_config import LimitConfigValue
from analysis_engine.grading.parameters import PARAMETER_CATALOG, default_full_scale_by_param
from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from analysis_engine.pipeline import analyze_dc_record, build_masters_from_trials, compute_trial_parameters
from analysis_engine.reports.code_result import build_code_result_report

GEAR_R = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
SAMPLE_RATE_HZ = 5000.0
DURATION_S = 3.0
FULL_SCALE_BY_PARAM = default_full_scale_by_param()


def _signal(seed, gear_orders=GEAR_R):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SAMPLE_RATE_HZ * DURATION_S)) / SAMPLE_RATE_HZ
    rpm = 1000 + (2500 - 1000) * (t / DURATION_S)
    theta = np.cumsum(2 * np.pi * rpm / 60.0) / SAMPLE_RATE_HZ
    signal = np.sin(gear_orders.mesh_order * theta) + rng.normal(0, 0.02, size=t.shape)
    return signal, t, rpm


def _masters(gear_orders=GEAR_R):
    trial_parameters = []
    for seed in range(10, 40):
        signal, t, rpm = _signal(seed, gear_orders)
        trial_parameters.append(compute_trial_parameters(signal, t, rpm, gear_orders))
    return build_masters_from_trials(trial_parameters, FULL_SCALE_BY_PARAM)


def test_one_result_via_masters_path_produces_one_row_per_graded_stat():
    masters = _masters()
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)

    report = build_code_result_report([result], {"R": GEAR_R})

    assert len(report.rows) == len(result.grading.per_stat)
    assert all(row.step == 1 for row in report.rows)
    assert all(row.gear_direction == "R_RU" for row in report.rows)
    assert all(row.channel_name == "vib_a" for row in report.rows)


def test_harmonic_row_has_orders_base_stat_row_does_not():
    masters = _masters()
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)

    report = build_code_result_report([result], {"R": GEAR_R})
    by_param = {row.parameter: row for row in report.rows}

    harmonic_name = "IN_H1(g)"
    if harmonic_name in by_param:
        expected_order = PARAMETER_CATALOG[harmonic_name].order_fn(GEAR_R)
        assert by_param[harmonic_name].orders == pytest.approx(expected_order)
        assert by_param[harmonic_name].unit == "g"

    base_name = "RMS Avg"
    if base_name in by_param:
        assert by_param[base_name].orders is None
        assert by_param[base_name].unit == "g"


def test_unit_label_reflects_unit_convert():
    masters = _masters()
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)

    report = build_code_result_report([result], {"R": GEAR_R})
    by_param = {row.parameter: row for row in report.rows}

    converted_name = "RMS Avg (m/s2)"
    if converted_name in by_param:
        assert by_param[converted_name].unit == "m/s2"

    db_name = "RMS Avg (dB m/s2)"
    if db_name in by_param:
        assert by_param[db_name].unit == "dB m/s2"


def test_step_increments_in_supplied_order_across_two_results():
    masters = _masters()
    signal_a, t_a, rpm_a = _signal(999)
    signal_b, t_b, rpm_b = _signal(1000)
    result_a = analyze_dc_record(signal_a, t_a, rpm_a, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)
    result_b = analyze_dc_record(signal_b, t_b, rpm_b, SAMPLE_RATE_HZ, "R", "RD", GEAR_R, masters)

    report = build_code_result_report([result_a, result_b], {"R": GEAR_R})

    steps = {row.gear_direction: row.step for row in report.rows}
    assert steps["R_RU"] == 1
    assert steps["R_RD"] == 2


def test_limit_configs_path_reports_effective_bounds():
    gear_orders = GEAR_R
    signal, t, rpm = _signal(999)
    result_no_grading = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", gear_orders, masters=None)
    rms_value = result_no_grading.parameters["RMS Avg"]

    limit_configs = {
        "RMS Avg": LimitConfigValue(
            mean_value=rms_value, limit_low=rms_value - 1.0, limit_high=rms_value + 1.0,
            full_scale=10.0, threshold_low=0.1, threshold_high=0.2,
        )
    }
    result = analyze_dc_record(
        signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", gear_orders, masters=None, limit_configs=limit_configs,
    )

    report = build_code_result_report([result], {"R": gear_orders})
    row = next(row for row in report.rows if row.parameter == "RMS Avg")

    assert row.low == pytest.approx(rms_value - 1.0 - 0.1)
    assert row.high == pytest.approx(rms_value + 1.0 + 0.2)
    assert row.ok_flag is True
    assert row.actual == pytest.approx(rms_value)


def test_ungraded_parameter_is_skipped():
    masters = _masters()
    signal, t, rpm = _signal(999)
    # Only "RMS Avg" has a master -- every other parameter is computed but ungraded.
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, {"RMS Avg": masters["RMS Avg"]})

    report = build_code_result_report([result], {"R": GEAR_R})

    assert len(report.rows) == 1
    assert report.rows[0].parameter == "RMS Avg"
    assert len(report.rows) < len(result.parameters)


def test_no_grading_at_all_produces_no_rows():
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters=None)
    assert result.grading is None

    report = build_code_result_report([result], {"R": GEAR_R})
    assert report.rows == []


def test_missing_gear_in_orders_map_degrades_to_none_instead_of_raising():
    masters = _masters()
    signal, t, rpm = _signal(999)
    result = analyze_dc_record(signal, t, rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters)

    report = build_code_result_report([result], {})

    assert len(report.rows) == len(result.grading.per_stat)
    assert all(row.orders is None for row in report.rows)
