"""The G1-G10 tolerance ladder, as specified in docs/data-contract.md.

The reference manual describes the step as "G5 grade percentage ... = (band_max
- band_min)/2, as a percentage of full_scale" — i.e. the step exists in two
equivalent representations:

    delta_percent = (band_max - band_min) / 2 / full_scale * 100   # "G5%"
    delta_value   = delta_percent / 100 * full_scale                # back to value units
                  = (band_max - band_min) / 2

`full_scale` cancels out of the round trip, so the value-space ladder is
simply centered on `mean_value` with a step of half the master band width;
`full_scale` only matters if a percentage representation is needed (e.g. for
display), so it's kept on `GLadder` for that purpose but doesn't affect
`g_level_value`.

    G_n = mean_value + (n - 5) * delta_value    for n in 1..10

A value is classified into whichever G_n it's nearest to.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GLadder:
    mean_value: float
    delta_value: float
    delta_percent: float

    def g_level_value(self, n: int) -> float:
        if not 1 <= n <= 10:
            raise ValueError(f"g_level must be in 1..10, got {n}")
        return self.mean_value + (n - 5) * self.delta_value


def compute_g_ladder(mean_value: float, band_min: float, band_max: float, full_scale: float) -> GLadder:
    delta_value = (band_max - band_min) / 2
    delta_percent = (delta_value / full_scale * 100) if full_scale else 0.0
    return GLadder(mean_value=mean_value, delta_value=delta_value, delta_percent=delta_percent)


def classify_g_level(ladder: GLadder, value: float) -> int:
    levels = range(1, 11)
    distances = [abs(value - ladder.g_level_value(n)) for n in levels]
    return list(levels)[int(np.argmin(distances))]
