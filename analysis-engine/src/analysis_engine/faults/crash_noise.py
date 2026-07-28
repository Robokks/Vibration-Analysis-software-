"""Crash-noise detection: band-limited RMS within a configured frequency
window, tracked over a sliding time window and compared against a gate-force
threshold — mirrors the reference system's per-gear crash-noise check
(start/end frequency + gate force). A sliding window (rather than one RMS over
the whole run) is what lets a brief impact be detected regardless of how long
the overall DC record is."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt


@dataclass(frozen=True)
class CrashNoiseCheckResult:
    peak_band_rms: float
    threshold: float
    detected: bool


def detect_crash_noise(
    signal: np.ndarray,
    sample_rate_hz: float,
    start_freq_hz: float,
    end_freq_hz: float,
    gate_force_threshold: float,
    window_s: float = 0.05,
) -> CrashNoiseCheckResult:
    nyquist = sample_rate_hz / 2.0
    high = min(end_freq_hz, nyquist * 0.999)
    sos = butter(4, [start_freq_hz, high], btype="bandpass", fs=sample_rate_hz, output="sos")
    filtered = sosfiltfilt(sos, signal)

    window_n = max(1, int(round(window_s * sample_rate_hz)))
    n_windows = max(1, len(filtered) // window_n)
    trimmed = filtered[: n_windows * window_n].reshape(n_windows, window_n)
    window_rms = np.sqrt(np.mean(trimmed**2, axis=1))
    peak_band_rms = float(np.max(window_rms))

    return CrashNoiseCheckResult(
        peak_band_rms=peak_band_rms,
        threshold=gate_force_threshold,
        detected=peak_band_rms > gate_force_threshold,
    )
