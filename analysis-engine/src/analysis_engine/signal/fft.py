"""Windowed FFT over a uniformly-sampled signal, amplitude-corrected for the
window function."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal.windows import get_window


@dataclass(frozen=True)
class SpectrumResult:
    freq: np.ndarray
    magnitude: np.ndarray


def compute_fft(x: np.ndarray, sample_rate_hz: float, window: str = "hann") -> SpectrumResult:
    x = np.asarray(x, dtype=float)
    n = len(x)
    win = get_window(window, n)
    windowed = x * win
    spectrum = np.fft.rfft(windowed)
    freq = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
    # amplitude correction: 2/sum(window) recovers the true sinusoid amplitude
    magnitude = np.abs(spectrum) * (2.0 / np.sum(win))
    magnitude[0] /= 2.0  # DC bin shouldn't be doubled
    return SpectrumResult(freq=freq, magnitude=magnitude)
