"""Injectable fault primitives for the simulator. Ground truth (which fault,
where in time) is always known here, unlike with real acquired data — this is
what makes the simulator useful for evaluating the analysis engine's fault
detectors and, later, the AI anomaly-detection layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

FaultKind = Literal["slippage", "crash_noise", "extra_order"]


@dataclass(frozen=True)
class Fault:
    kind: FaultKind
    start_s: float
    end_s: float
    amplitude: float = 0.5
    drop_to: float = 0.1
    order: float | None = None  # required for "extra_order"


def slippage_envelope(t: np.ndarray, start_s: float, end_s: float, drop_to: float) -> np.ndarray:
    """Multiplier in [drop_to, 1.0] that dips during [start_s, end_s] — models
    the mesh-order magnitude dropout of a slipping gear."""
    env = np.ones_like(t)
    env[(t >= start_s) & (t <= end_s)] = drop_to
    return env


def crash_noise_burst(t: np.ndarray, start_s: float, end_s: float, amplitude: float, rng: np.random.Generator) -> np.ndarray:
    """Broadband noise burst within a time window — models a gear-crash impact."""
    burst = np.zeros_like(t)
    mask = (t >= start_s) & (t <= end_s)
    burst[mask] = rng.normal(0.0, amplitude, size=int(mask.sum()))
    return burst


def extra_order_component(theta: np.ndarray, order: float, amplitude: float, rng: np.random.Generator) -> np.ndarray:
    """An extra sinusoidal order component not present in the healthy gear's
    order set — models an unexpected defect tone (e.g. a chipped tooth)."""
    phase0 = rng.uniform(0.0, 2 * np.pi)
    return amplitude * np.sin(order * theta + phase0)
