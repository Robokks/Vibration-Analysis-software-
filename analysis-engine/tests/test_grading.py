import pytest

from analysis_engine.grading.envelope_check import check_value, grade_dc_record
from analysis_engine.grading.g_ladder import classify_g_level, compute_g_ladder
from analysis_engine.grading.master_builder import build_master_signature


def test_master_signature_from_trials():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    assert master.mean_value == pytest.approx(1.05)
    assert master.band_min == pytest.approx(0.9)
    assert master.band_max == pytest.approx(1.2)
    assert master.trial_count == 4


def test_master_signature_requires_at_least_two_trials():
    with pytest.raises(ValueError):
        build_master_signature([1.0], full_scale=10.0)


def test_g_ladder_matches_documented_formula():
    # band_min=0.9, band_max=1.2, full_scale=10 -> delta_value = (1.2-0.9)/2 = 0.15
    # delta_percent = 0.15 / 10 * 100 = 1.5%
    ladder = compute_g_ladder(mean_value=1.05, band_min=0.9, band_max=1.2, full_scale=10.0)
    assert ladder.delta_value == pytest.approx(0.15)
    assert ladder.delta_percent == pytest.approx(1.5)
    assert ladder.g_level_value(5) == pytest.approx(1.05)
    assert ladder.g_level_value(6) == pytest.approx(1.05 + 0.15)
    assert ladder.g_level_value(4) == pytest.approx(1.05 - 0.15)


def test_classify_g_level_picks_nearest_band():
    ladder = compute_g_ladder(mean_value=1.05, band_min=0.9, band_max=1.2, full_scale=10.0)
    assert classify_g_level(ladder, 1.05) == 5
    assert classify_g_level(ladder, ladder.g_level_value(8)) == 8
    assert classify_g_level(ladder, ladder.g_level_value(1)) == 1
    assert classify_g_level(ladder, ladder.g_level_value(10)) == 10


def test_check_value_ok_within_default_g4_g6_window():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    result_ok = check_value(master, master.mean_value)
    assert result_ok.g_level == 5
    assert result_ok.ok_flag is True


def test_check_value_nok_outside_window():
    master = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    ladder = compute_g_ladder(master.mean_value, master.band_min, master.band_max, master.full_scale)
    far_value = ladder.g_level_value(9)
    result = check_value(master, far_value)
    assert result.g_level == 9
    assert result.ok_flag is False


def test_grade_dc_record_passes_only_if_all_stats_ok():
    master_rms = build_master_signature([1.0, 1.2, 0.9, 1.1], full_scale=10.0)
    master_kurt = build_master_signature([3.0, 3.2, 2.9, 3.1], full_scale=30.0)
    masters = {"rms": master_rms, "kurtosis": master_kurt}

    good = grade_dc_record({"rms": master_rms.mean_value, "kurtosis": master_kurt.mean_value}, masters)
    assert good.passed is True

    ladder_kurt = compute_g_ladder(master_kurt.mean_value, master_kurt.band_min, master_kurt.band_max, master_kurt.full_scale)
    bad = grade_dc_record(
        {"rms": master_rms.mean_value, "kurtosis": ladder_kurt.g_level_value(9)}, masters
    )
    assert bad.passed is False
    assert bad.per_stat["kurtosis"].ok_flag is False
