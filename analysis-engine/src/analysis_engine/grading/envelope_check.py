"""OK/NOK check for a single stat value against its master signature's G-ladder,
and the DC/unit-level PASS/FAIL rollup."""

from __future__ import annotations

from dataclasses import dataclass

from analysis_engine.grading.g_ladder import classify_g_level, compute_g_ladder
from analysis_engine.grading.master_builder import MasterSignatureStats


@dataclass(frozen=True)
class EnvelopeCheckResult:
    g_level: int
    ok_flag: bool
    low: float
    high: float


def check_value(
    master: MasterSignatureStats,
    value: float,
    low_g: int = 4,
    high_g: int = 6,
) -> EnvelopeCheckResult:
    ladder = compute_g_ladder(master.mean_value, master.band_min, master.band_max, master.full_scale)
    g_level = classify_g_level(ladder, value)
    ok = low_g <= g_level <= high_g
    return EnvelopeCheckResult(
        g_level=g_level, ok_flag=ok, low=ladder.g_level_value(low_g), high=ladder.g_level_value(high_g)
    )


@dataclass(frozen=True)
class DcGradingSummary:
    per_stat: dict[str, EnvelopeCheckResult]
    passed: bool


def grade_dc_record(stat_values: dict[str, float], masters: dict[str, MasterSignatureStats], low_g: int = 4, high_g: int = 6) -> DcGradingSummary:
    """`stat_values` and `masters` are keyed by the same stat name (e.g. 'rms',
    'kurtosis'). A DC record passes only if every graded stat is OK."""
    per_stat = {
        stat_name: check_value(masters[stat_name], value, low_g, high_g)
        for stat_name, value in stat_values.items()
        if stat_name in masters
    }
    passed = all(result.ok_flag for result in per_stat.values()) if per_stat else False
    return DcGradingSummary(per_stat=per_stat, passed=passed)
