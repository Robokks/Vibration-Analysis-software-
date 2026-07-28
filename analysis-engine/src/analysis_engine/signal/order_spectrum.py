"""Order spectrum: FFT of a signal after angle-domain resampling, so bins are
directly in "orders" (cycles per shaft revolution) rather than Hz."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal.windows import get_window

from analysis_engine.signal.resampling import compute_shaft_angle, resample_to_angle_domain


@dataclass(frozen=True)
class OrderSpectrumResult:
    order: np.ndarray
    magnitude: np.ndarray


def compute_order_spectrum(
    signal: np.ndarray,
    time_s: np.ndarray,
    rpm: np.ndarray,
    samples_per_rev: int = 360,
    window: str = "hann",
) -> OrderSpectrumResult:
    theta = compute_shaft_angle(time_s, rpm)
    _, signal_uniform = resample_to_angle_domain(signal, theta, samples_per_rev)

    n = len(signal_uniform)
    win = get_window(window, n)
    windowed = signal_uniform * win
    spectrum = np.fft.rfft(windowed)
    # sample spacing is 1/samples_per_rev revolutions -> rfftfreq gives orders directly
    order = np.fft.rfftfreq(n, d=1.0 / samples_per_rev)
    magnitude = np.abs(spectrum) * (2.0 / np.sum(win))
    magnitude[0] /= 2.0
    return OrderSpectrumResult(order=order, magnitude=magnitude)


def peak_magnitude_near_order(result: OrderSpectrumResult, target_order: float, tolerance: float = 0.5) -> float:
    mask = np.abs(result.order - target_order) <= tolerance
    if not np.any(mask):
        return 0.0
    return float(np.max(result.magnitude[mask]))
