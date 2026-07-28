import numpy as np
import pytest

from analysis_engine.signal.fft import compute_fft


def test_fft_peak_at_known_frequency():
    fs = 5000
    duration = 2.0
    t = np.arange(int(fs * duration)) / fs
    amplitude = 3.0
    freq0 = 200.0
    x = amplitude * np.sin(2 * np.pi * freq0 * t)

    result = compute_fft(x, fs)

    peak_idx = np.argmax(result.magnitude)
    freq_resolution = fs / len(x)
    assert abs(result.freq[peak_idx] - freq0) <= freq_resolution
    assert result.magnitude[peak_idx] == pytest.approx(amplitude, rel=0.05)
