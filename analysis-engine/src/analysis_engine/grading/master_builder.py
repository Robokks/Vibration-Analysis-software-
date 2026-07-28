"""Builds a master signature (golden reference) for one (model, gear,
direction, stat, domain) combination by averaging trial runs from known-good
units, mirroring the reference system's auto-record-N-trials workflow."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MasterSignatureStats:
    mean_value: float
    band_min: float
    band_max: float
    full_scale: float
    trial_count: int


def build_master_signature(trial_values: list[float], full_scale: float) -> MasterSignatureStats:
    if len(trial_values) < 2:
        raise ValueError("need at least 2 trial values to build a master signature")
    values = np.asarray(trial_values, dtype=float)
    return MasterSignatureStats(
        mean_value=float(np.mean(values)),
        band_min=float(np.min(values)),
        band_max=float(np.max(values)),
        full_scale=full_scale,
        trial_count=len(trial_values),
    )
