"""Gear-slippage detection: a sustained dropout in the tracked mesh-order
magnitude relative to its expected (baseline) level, mirroring the reference
system's per-gear slip-force-tolerance check."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SlippageCheckResult:
    min_ratio: float
    dropout_fraction: float
    detected: bool


def detect_slippage(
    order_magnitude: np.ndarray,
    baseline_magnitude: float,
    drop_ratio_threshold: float = 0.5,
    min_dropout_fraction: float = 0.1,
) -> SlippageCheckResult:
    """`order_magnitude` is a tracked order's magnitude-vs-time trace (e.g.
    from `signal.order_tracking`). Flags slippage if at least
    `min_dropout_fraction` of samples fall below
    `drop_ratio_threshold * baseline_magnitude`."""
    if baseline_magnitude <= 0:
        raise ValueError("baseline_magnitude must be positive")

    ratios = order_magnitude / baseline_magnitude
    below_threshold = ratios < drop_ratio_threshold
    dropout_fraction = float(np.mean(below_threshold))
    min_ratio = float(np.min(ratios))

    return SlippageCheckResult(
        min_ratio=min_ratio,
        dropout_fraction=dropout_fraction,
        detected=dropout_fraction >= min_dropout_fraction,
    )
