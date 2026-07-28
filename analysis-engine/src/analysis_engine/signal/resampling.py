"""Angle-domain resampling: converts a time-sampled signal into the shaft-angle
domain using the tach-derived instantaneous speed, so a subsequent FFT yields an
order spectrum instead of a frequency spectrum. This is what lets order
analysis handle a changing RPM (run-up/run-down) that a plain FFT cannot."""

from __future__ import annotations

import numpy as np
from scipy.integrate import cumulative_trapezoid


def compute_shaft_angle(time_s: np.ndarray, rpm: np.ndarray) -> np.ndarray:
    """theta(t) = integral of 2*pi*rpm(t)/60 dt, in radians."""
    omega = 2 * np.pi * rpm / 60.0
    theta = cumulative_trapezoid(omega, time_s, initial=0.0)
    return theta


def resample_to_angle_domain(
    signal: np.ndarray, theta: np.ndarray, samples_per_rev: int = 360
) -> tuple[np.ndarray, np.ndarray]:
    """Resamples `signal` (given at the original time-domain instants whose
    shaft angle is `theta`) onto a uniform shaft-angle grid.

    Returns (theta_uniform, signal_resampled). `theta_uniform` spacing is
    `2*pi/samples_per_rev` radians, i.e. `1/samples_per_rev` revolutions —
    this uniform revolution spacing is what makes
    `numpy.fft.rfftfreq(n, d=1/samples_per_rev)` yield order numbers directly.
    """
    n_revs = theta[-1] / (2 * np.pi)
    n_samples = max(2, int(np.floor(n_revs * samples_per_rev)))
    theta_uniform = np.arange(n_samples) * (2 * np.pi / samples_per_rev)
    signal_resampled = np.interp(theta_uniform, theta, signal)
    return theta_uniform, signal_resampled
