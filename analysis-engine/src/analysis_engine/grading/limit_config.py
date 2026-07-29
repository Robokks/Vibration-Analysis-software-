"""Two-stage LIMIT/THRESHOLD grading, matching the real system's
Limit Config.vi screen (STEP | CHANNEL | PARAMETER | ORDERS | LIMIT (LOW) |
THRESHOLD (LOW) | LIMIT (HIGH) | THRESHOLD (HIGH), with a "Save" and an
"Import From MASTER" action).

LIMIT is the auto-computed band from trial data (identical to
MasterSignatureStats.band_min/band_max -- "Import From MASTER" is exactly
`import_limit_config_from_masters` below). THRESHOLD is a manually-tunable
*margin* added outward from that band, not a replacement band and not a
substitute for the G-ladder: `effective_low = limit_low - threshold_low`,
`effective_high = limit_high + threshold_high`, and a value passes iff
`effective_low <= value <= effective_high`.

This module is purely additive alongside envelope_check.py's existing
master+G4-G6-window grading -- nothing here changes check_value()/
grade_dc_record()'s behavior; callers opt into this path explicitly by
supplying limit configs to analyze_dc_record()."""

from __future__ import annotations

from dataclasses import dataclass

from analysis_engine.grading.envelope_check import DcGradingSummary, EnvelopeCheckResult
from analysis_engine.grading.g_ladder import classify_g_level, compute_g_ladder
from analysis_engine.grading.master_builder import MasterSignatureStats


@dataclass(frozen=True)
class LimitConfigValue:
    mean_value: float
    limit_low: float
    limit_high: float
    full_scale: float
    threshold_low: float = 0.0
    threshold_high: float = 0.0


def import_limit_config_from_masters(
    masters: dict[str, MasterSignatureStats],
) -> dict[str, LimitConfigValue]:
    """The "Import From MASTER" button's backend: seeds limit_low/limit_high
    from the auto-computed band, threshold_low/threshold_high defaulted to
    0.0 pending manual tuning."""
    return {
        name: LimitConfigValue(
            mean_value=m.mean_value,
            limit_low=m.band_min,
            limit_high=m.band_max,
            full_scale=m.full_scale,
        )
        for name, m in masters.items()
    }


def check_value_with_threshold(
    entry: LimitConfigValue,
    value: float,
    low_g: int = 4,
    high_g: int = 6,
) -> EnvelopeCheckResult:
    """g_level is computed exactly like envelope_check.check_value() --
    informational only, from the LIMIT band. ok_flag comes from the
    THRESHOLD-widened range check instead of the G-ladder window; this is
    the only behavioral difference from check_value()."""
    ladder = compute_g_ladder(entry.mean_value, entry.limit_low, entry.limit_high, entry.full_scale)
    g_level = classify_g_level(ladder, value)
    effective_low = entry.limit_low - entry.threshold_low
    effective_high = entry.limit_high + entry.threshold_high
    ok = effective_low <= value <= effective_high
    return EnvelopeCheckResult(g_level=g_level, ok_flag=ok)


def grade_dc_record_with_limits(
    stat_values: dict[str, float],
    limit_configs: dict[str, LimitConfigValue],
    low_g: int = 4,
    high_g: int = 6,
) -> DcGradingSummary:
    """Mirrors grade_dc_record()'s exact skip-missing-config pattern: a stat
    present in `stat_values` but absent from `limit_configs` is omitted, not
    an error."""
    per_stat = {
        name: check_value_with_threshold(limit_configs[name], value, low_g, high_g)
        for name, value in stat_values.items()
        if name in limit_configs
    }
    passed = all(result.ok_flag for result in per_stat.values()) if per_stat else False
    return DcGradingSummary(per_stat=per_stat, passed=passed)
