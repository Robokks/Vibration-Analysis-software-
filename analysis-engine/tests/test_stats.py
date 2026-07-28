import numpy as np
import pytest

from analysis_engine.signal.stats import compute_stats


def test_sine_wave_stats():
    fs = 10000
    t = np.arange(fs) / fs
    amplitude = 2.0
    x = amplitude * np.sin(2 * np.pi * 50 * t)

    result = compute_stats(x)

    assert result.rms == pytest.approx(amplitude / np.sqrt(2), rel=1e-3)
    assert result.peak == pytest.approx(amplitude, rel=1e-3)
    assert result.crest == pytest.approx(np.sqrt(2), rel=1e-2)
    assert result.mean == pytest.approx(0.0, abs=1e-6)


def test_gaussian_noise_kurtosis_near_normal():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=200000)
    result = compute_stats(x)
    assert result.kurtosis == pytest.approx(3.0, abs=0.1)
