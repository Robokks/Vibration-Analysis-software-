"""Time/speed-domain statistics used throughout grading and SPC: mean,
variance, skewness, kurtosis, RMS, peak, and crest factor."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as scipy_stats


@dataclass(frozen=True)
class SignalStats:
    mean: float
    variance: float
    skewness: float
    kurtosis: float
    rms: float
    peak: float
    crest: float


def compute_stats(x: np.ndarray) -> SignalStats:
    x = np.asarray(x, dtype=float)
    mean = float(np.mean(x))
    variance = float(np.var(x))
    rms = float(np.sqrt(np.mean(x**2)))
    peak = float(np.max(np.abs(x)))
    crest = float(peak / rms) if rms > 0 else 0.0
    skewness = float(scipy_stats.skew(x))
    kurtosis = float(scipy_stats.kurtosis(x, fisher=False))  # Pearson (normal ~= 3), matches legacy convention
    return SignalStats(
        mean=mean,
        variance=variance,
        skewness=skewness,
        kurtosis=kurtosis,
        rms=rms,
        peak=peak,
        crest=crest,
    )
