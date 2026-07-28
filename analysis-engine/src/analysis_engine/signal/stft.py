"""Short-time FFT surface (time x frequency x magnitude), the shared data
behind both the "waterfall" and "cascade" views — both render the same
time/frequency/magnitude surface, just with different visual presentation, so
one computation feeds both."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import stft


@dataclass(frozen=True)
class SpectrogramResult:
    time_s: np.ndarray
    freq: np.ndarray
    magnitude: np.ndarray  # shape (len(freq), len(time_s))


def compute_spectrogram(
    signal: np.ndarray,
    sample_rate_hz: float,
    nperseg: int = 1024,
    noverlap: int | None = None,
) -> SpectrogramResult:
    noverlap = noverlap if noverlap is not None else nperseg // 2
    freq, t_stft, zxx = stft(signal, fs=sample_rate_hz, nperseg=nperseg, noverlap=noverlap)
    return SpectrogramResult(time_s=t_stft, freq=freq, magnitude=np.abs(zxx))
