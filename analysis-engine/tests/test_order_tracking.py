import numpy as np
import pytest

from analysis_engine.signal.order_tracking import compute_order_tracking


def test_order_tracking_constant_amplitude_at_constant_rpm():
    fs = 5000
    duration = 4.0
    rpm_const = 1800.0
    order = 12.0
    amplitude = 2.0

    t = np.arange(int(fs * duration)) / fs
    rpm = np.full_like(t, rpm_const)
    freq_hz = order * rpm_const / 60.0
    x = amplitude * np.sin(2 * np.pi * freq_hz * t)

    result = compute_order_tracking(x, t, rpm, fs, order, nperseg=1024)

    # ignore edge frames where STFT windowing distorts amplitude
    interior = result.magnitude[2:-2]
    assert np.mean(interior) == pytest.approx(amplitude, rel=0.15)
    assert np.std(interior) < 0.3
