"""Order tracking: magnitude of a specific order, tracked over time, as the
shaft speed changes during a run-up/run-down. Implemented via STFT with the
target frequency bin following `order * rpm(t) / 60` at each time frame —
this is the standard way to track an order through a speed ramp without
needing angle-domain resampling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import stft


@dataclass(frozen=True)
class OrderTrackingResult:
    time_s: np.ndarray
    magnitude: np.ndarray


def compute_order_tracking(
    signal: np.ndarray,
    time_s: np.ndarray,
    rpm: np.ndarray,
    sample_rate_hz: float,
    order: float,
    nperseg: int = 1024,
    noverlap: int | None = None,
) -> OrderTrackingResult:
    noverlap = noverlap if noverlap is not None else nperseg // 2
    freq, t_stft, zxx = stft(signal, fs=sample_rate_hz, nperseg=nperseg, noverlap=noverlap)
    # scipy's stft already normalizes by the window sum internally; a factor of 2
    # (single-sided spectrum convention) recovers the sinusoid amplitude, matching
    # the same convention used in fft.py.
    magnitude_stft = np.abs(zxx) * 2.0

    rpm_at_frames = np.interp(t_stft, time_s, rpm)
    target_freq_hz = order * rpm_at_frames / 60.0

    magnitude = np.array(
        [np.interp(target_freq_hz[i], freq, magnitude_stft[:, i]) for i in range(len(t_stft))]
    )
    return OrderTrackingResult(time_s=t_stft, magnitude=magnitude)
