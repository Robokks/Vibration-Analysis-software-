"""Histogram + normal-curve overlay, as used in the reference system's
Statistical Data module."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as scipy_stats


@dataclass(frozen=True)
class HistogramResult:
    bin_edges: np.ndarray
    counts: np.ndarray
    normal_pdf_x: np.ndarray
    normal_pdf_y: np.ndarray


def compute_histogram(values: list[float] | np.ndarray, n_bins: int = 10) -> HistogramResult:
    values = np.asarray(values, dtype=float)
    counts, edges = np.histogram(values, bins=n_bins)
    mean = float(np.mean(values))
    std = float(np.std(values))
    x = np.linspace(edges[0], edges[-1], 200)
    y = scipy_stats.norm.pdf(x, mean, std if std > 0 else 1e-9)
    return HistogramResult(bin_edges=edges, counts=counts, normal_pdf_x=x, normal_pdf_y=y)
