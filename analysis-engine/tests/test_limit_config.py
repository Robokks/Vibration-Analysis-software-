import pytest

from analysis_engine.grading.g_ladder import classify_g_level, compute_g_ladder
from analysis_engine.grading.limit_config import (
    check_value_with_threshold,
    grade_dc_record_with_limits,
    import_limit_config_from_masters,
)
from analysis_engine.grading.master_builder import build_master_signature
from analysis_engine.pipeline import analyze_dc_record
from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
import numpy as np


def test_import_limit_config_from_masters_maps_band_to_limit():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    configs = import_limit_config_from_masters({"rms": master})

    entry = configs["rms"]
    assert entry.mean_value == pytest.approx(master.mean_value)
    assert entry.limit_low == pytest.approx(master.band_min)
    assert entry.limit_high == pytest.approx(master.band_max)
    assert entry.full_scale == pytest.approx(master.full_scale)
    assert entry.threshold_low == 0.0
    assert entry.threshold_high == 0.0


def test_check_value_with_threshold_boundary_inclusive_at_limit():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    entry = import_limit_config_from_masters({"rms": master})["rms"]

    result = check_value_with_threshold(entry, entry.limit_low)
    assert result.ok_flag is True
    assert result.low == pytest.approx(entry.limit_low - entry.threshold_low)
    assert result.high == pytest.approx(entry.limit_high + entry.threshold_high)


def test_check_value_with_threshold_fails_just_below_limit_when_threshold_zero():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    entry = import_limit_config_from_masters({"rms": master})["rms"]

    just_below = entry.limit_low - 0.01
    result = check_value_with_threshold(entry, just_below)
    assert result.ok_flag is False


def test_threshold_margin_widens_the_effective_pass_range():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    entry = import_limit_config_from_masters({"rms": master})["rms"]
    just_below = entry.limit_low - 0.01

    assert check_value_with_threshold(entry, just_below).ok_flag is False

    widened = type(entry)(
        mean_value=entry.mean_value, limit_low=entry.limit_low, limit_high=entry.limit_high,
        full_scale=entry.full_scale, threshold_low=0.05, threshold_high=0.0,
    )
    assert check_value_with_threshold(widened, just_below).ok_flag is True


def test_g_level_is_unaffected_by_threshold_margin():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    entry = import_limit_config_from_masters({"rms": master})["rms"]
    ladder = compute_g_ladder(entry.mean_value, entry.limit_low, entry.limit_high, entry.full_scale)
    probe_value = ladder.g_level_value(8)
    expected_g_level = classify_g_level(ladder, probe_value)

    widened = type(entry)(
        mean_value=entry.mean_value, limit_low=entry.limit_low, limit_high=entry.limit_high,
        full_scale=entry.full_scale, threshold_low=5.0, threshold_high=5.0,
    )
    result = check_value_with_threshold(widened, probe_value)
    assert result.g_level == expected_g_level
    # still within the (very wide) threshold-widened range despite a high g_level
    assert result.ok_flag is True


def test_grade_dc_record_with_limits_skips_stats_with_no_config():
    master_rms = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    configs = import_limit_config_from_masters({"rms": master_rms})

    summary = grade_dc_record_with_limits({"rms": master_rms.mean_value, "unconfigured_stat": 42.0}, configs)

    assert "unconfigured_stat" not in summary.per_stat
    assert "rms" in summary.per_stat
    assert summary.passed is True


def test_grade_dc_record_with_limits_fails_with_empty_per_stat():
    summary = grade_dc_record_with_limits({"rms": 1.0}, limit_configs={})
    assert summary.per_stat == {}
    assert summary.passed is False


def test_analyze_dc_record_with_limit_configs_grades_via_threshold_path():
    gear_orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
    sample_rate_hz = 5000.0
    duration_s = 3.0
    t = np.arange(int(sample_rate_hz * duration_s)) / sample_rate_hz
    rpm = 1000.0 + (2500.0 - 1000.0) * (t / duration_s)
    theta = np.cumsum(2 * np.pi * rpm / 60.0) / sample_rate_hz
    rng = np.random.default_rng(0)
    signal = np.sin(gear_orders.mesh_order * theta) + rng.normal(0, 0.02, size=t.shape)

    result_no_config = analyze_dc_record(signal, t, rpm, sample_rate_hz, "R", "RU", gear_orders, masters=None)
    assert result_no_config.grading is None  # no masters, no limit_configs -> no grading at all

    rms_value = result_no_config.parameters["RMS Avg"]
    # a deliberately narrow, clearly-failing limit config for one parameter
    from analysis_engine.grading.limit_config import LimitConfigValue

    limit_configs = {"RMS Avg": LimitConfigValue(
        mean_value=rms_value, limit_low=rms_value + 10.0, limit_high=rms_value + 20.0, full_scale=10.0,
    )}
    result = analyze_dc_record(
        signal, t, rpm, sample_rate_hz, "R", "RU", gear_orders, masters=None, limit_configs=limit_configs,
    )
    assert result.grading is not None
    assert result.grading.passed is False
    assert "ENVELOPE_NOK" in result.fail_reason_codes
