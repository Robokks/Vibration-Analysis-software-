"""SPC X-chart: 3-sigma control limits over a sequence of per-unit stat
values, as used in the reference system's Statistical Data module."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class XChartResult:
    center_line: float
    ucl: float
    lcl: float
    values: np.ndarray
    out_of_control_indices: list[int]


def compute_xchart(values: list[float] | np.ndarray, sigma_multiplier: float = 3.0) -> XChartResult:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        raise ValueError("need at least 2 values to compute control limits")
    center_line = float(np.mean(values))
    sigma = float(np.std(values, ddof=1))
    ucl = center_line + sigma_multiplier * sigma
    lcl = center_line - sigma_multiplier * sigma
    out_of_control = [i for i, v in enumerate(values) if v > ucl or v < lcl]
    return XChartResult(center_line=center_line, ucl=ucl, lcl=lcl, values=values, out_of_control_indices=out_of_control)
