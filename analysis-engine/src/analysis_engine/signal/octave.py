"""Octave-band analysis: band-pass energy at standard octave center
frequencies, useful for steady-state (non order-tracking) noise comparison."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt

STANDARD_OCTAVE_CENTERS_HZ = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000)


@dataclass(frozen=True)
class OctaveBandResult:
    center_freq_hz: tuple[float, ...]
    rms: tuple[float, ...]


def compute_octave_bands(
    signal: np.ndarray,
    sample_rate_hz: float,
    centers_hz: tuple[float, ...] = STANDARD_OCTAVE_CENTERS_HZ,
) -> OctaveBandResult:
    nyquist = sample_rate_hz / 2.0
    rms_values = []
    valid_centers = []
    for center in centers_hz:
        low = center / np.sqrt(2)
        high = center * np.sqrt(2)
        if high >= nyquist:
            continue
        sos = butter(4, [low, high], btype="bandpass", fs=sample_rate_hz, output="sos")
        filtered = sosfiltfilt(sos, signal)
        rms_values.append(float(np.sqrt(np.mean(filtered**2))))
        valid_centers.append(center)
    return OctaveBandResult(center_freq_hz=tuple(valid_centers), rms=tuple(rms_values))
