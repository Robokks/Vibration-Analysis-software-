import numpy as np
import pytest

from analysis_engine.faults.crash_noise import detect_crash_noise
from analysis_engine.faults.slippage import detect_slippage


def test_crash_noise_detected_when_band_energy_exceeds_threshold():
    fs = 5000
    t = np.arange(fs * 2) / fs
    rng = np.random.default_rng(0)
    signal = rng.normal(0, 0.01, size=t.shape)  # quiet baseline
    signal[fs : fs + 200] += rng.normal(0, 3.0, size=200)  # crash burst in band

    result = detect_crash_noise(signal, fs, start_freq_hz=100, end_freq_hz=1000, gate_force_threshold=0.1)
    assert result.detected is True
    assert result.peak_band_rms > result.threshold


def test_crash_noise_not_detected_for_quiet_signal():
    fs = 5000
    t = np.arange(fs * 2) / fs
    rng = np.random.default_rng(1)
    signal = rng.normal(0, 0.01, size=t.shape)

    result = detect_crash_noise(signal, fs, start_freq_hz=100, end_freq_hz=1000, gate_force_threshold=0.1)
    assert result.detected is False


def test_slippage_detected_on_sustained_dropout():
    magnitude = np.concatenate([np.full(50, 2.0), np.full(50, 0.2), np.full(50, 2.0)])
    result = detect_slippage(magnitude, baseline_magnitude=2.0, drop_ratio_threshold=0.5, min_dropout_fraction=0.1)
    assert result.detected is True
    assert result.dropout_fraction == pytest.approx(50 / 150, rel=0.05)


def test_slippage_not_detected_for_stable_magnitude():
    magnitude = np.full(100, 2.0)
    result = detect_slippage(magnitude, baseline_magnitude=2.0)
    assert result.detected is False
    assert result.dropout_fraction == 0.0


def test_slippage_rejects_nonpositive_baseline():
    with pytest.raises(ValueError):
        detect_slippage(np.array([1.0]), baseline_magnitude=0.0)
