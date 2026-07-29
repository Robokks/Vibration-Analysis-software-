"""Windowed statistics: segments a signal into a fixed number of contiguous
time-windows, runs the existing `compute_stats()` primitive per window, and
reduces across windows to a per-field worst-case ("max") and mean-across-
windows ("avg"). This is a configurable *approximation* of the client's real
per-revolution windowing convention, which is not yet specified -- see
docs/data-contract.md's Phase B section. `n_windows` is a plain fixed count
of contiguous time-slices, not a per-revolution segmentation; revisit if/when
the real LabVIEW windowing scheme is confirmed.

"max" is the literal maximum across windows (not max-of-abs). For fields that
can be negative (mean, skewness), this is a simplifying assumption -- it may
under-represent the most extreme *magnitude* excursion if it happens to be
negative. Flagged for revisit alongside the windowing scheme itself."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analysis_engine.signal.stats import STAT_NAMES, compute_stats

DEFAULT_N_WINDOWS = 10

# A window with too few samples produces degenerate (NaN/inf) skewness and
# kurtosis (scipy divides by a near-zero standard deviation). Guards against
# silently propagating NaN into grading.
_MIN_SAMPLES_PER_WINDOW = 8


@dataclass(frozen=True)
class WindowedStatsResult:
    max: dict[str, float]  # SignalStats field name -> worst-case value across windows
    avg: dict[str, float]  # SignalStats field name -> mean value across windows
    n_windows: int


def compute_windowed_stats(signal: np.ndarray, n_windows: int = DEFAULT_N_WINDOWS) -> WindowedStatsResult:
    signal = np.asarray(signal, dtype=float)

    if n_windows < 1:
        raise ValueError(f"n_windows must be >= 1, got {n_windows}")
    if len(signal) // n_windows < _MIN_SAMPLES_PER_WINDOW:
        raise ValueError(
            f"n_windows={n_windows} is too fine for a signal of length {len(signal)} "
            f"(would leave < {_MIN_SAMPLES_PER_WINDOW} samples per window)"
        )

    chunks = np.array_split(signal, n_windows)
    per_window = [compute_stats(chunk) for chunk in chunks]

    max_values = {name: max(getattr(s, name) for s in per_window) for name in STAT_NAMES}
    avg_values = {name: float(np.mean([getattr(s, name) for s in per_window])) for name in STAT_NAMES}

    return WindowedStatsResult(max=max_values, avg=avg_values, n_windows=n_windows)
