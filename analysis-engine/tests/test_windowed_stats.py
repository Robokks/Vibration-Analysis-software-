import numpy as np
import pytest

from analysis_engine.signal.stats import STAT_NAMES, compute_stats
from analysis_engine.signal.windowed_stats import compute_windowed_stats


def test_single_window_reproduces_plain_compute_stats():
    rng = np.random.default_rng(0)
    signal = rng.normal(0, 1, size=2000)

    plain = compute_stats(signal)
    windowed = compute_windowed_stats(signal, n_windows=1)

    for name in STAT_NAMES:
        assert windowed.max[name] == pytest.approx(getattr(plain, name))
        assert windowed.avg[name] == pytest.approx(getattr(plain, name))
    assert windowed.n_windows == 1


def test_burst_confined_to_one_window_is_caught_by_max_but_diluted_in_avg():
    rng = np.random.default_rng(1)
    n_windows = 5
    window_len = 1000
    signal = rng.normal(0, 0.01, size=window_len * n_windows)
    # inject a high-amplitude burst confined to window index 3
    burst_start = window_len * 3
    signal[burst_start : burst_start + window_len] += rng.normal(0, 5.0, size=window_len)

    result = compute_windowed_stats(signal, n_windows=n_windows)

    assert result.max["rms"] > result.avg["rms"] * 2


def test_n_windows_less_than_one_raises():
    with pytest.raises(ValueError):
        compute_windowed_stats(np.zeros(100), n_windows=0)


def test_n_windows_too_fine_for_signal_length_raises():
    with pytest.raises(ValueError):
        compute_windowed_stats(np.zeros(10), n_windows=5)


def test_n_windows_is_echoed_on_result():
    signal = np.random.default_rng(2).normal(size=1000)
    result = compute_windowed_stats(signal, n_windows=4)
    assert result.n_windows == 4
