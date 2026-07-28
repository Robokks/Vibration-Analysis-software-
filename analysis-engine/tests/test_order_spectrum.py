import numpy as np
import pytest

from analysis_engine.signal.order_spectrum import compute_order_spectrum, peak_magnitude_near_order


def test_order_spectrum_peak_at_known_order_constant_rpm():
    fs = 5000
    duration = 4.0
    rpm_const = 1800.0
    order = 12.0
    amplitude = 1.5

    t = np.arange(int(fs * duration)) / fs
    rpm = np.full_like(t, rpm_const)
    freq_hz = order * rpm_const / 60.0
    x = amplitude * np.sin(2 * np.pi * freq_hz * t)

    result = compute_order_spectrum(x, t, rpm, samples_per_rev=360)

    peak_idx = np.argmax(result.magnitude)
    assert abs(result.order[peak_idx] - order) < 0.5
    assert peak_magnitude_near_order(result, order) == pytest.approx(amplitude, rel=0.1)


def test_order_spectrum_tracks_order_through_rpm_ramp():
    fs = 5000
    duration = 4.0
    order = 12.0
    amplitude = 1.0

    t = np.arange(int(fs * duration)) / fs
    rpm = 1000 + (2000 - 1000) * (t / duration)  # linear ramp
    omega = 2 * np.pi * rpm / 60.0
    theta = np.cumsum(omega) / fs  # crude integral, fine for a smoke test
    x = amplitude * np.sin(order * theta)

    result = compute_order_spectrum(x, t, rpm, samples_per_rev=360)
    peak_idx = np.argmax(result.magnitude)
    assert abs(result.order[peak_idx] - order) < 1.0
