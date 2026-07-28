"""Orchestrates the per-DC-record analysis: stats -> order spectrum/tracking ->
crash-noise/slippage checks -> grading against a master signature (if
available). This is the single entry point the CLI demo (and, later, the web
backend) calls per DC record."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from analysis_engine.faults.crash_noise import CrashNoiseCheckResult, detect_crash_noise
from analysis_engine.faults.slippage import SlippageCheckResult, detect_slippage
from analysis_engine.grading.envelope_check import DcGradingSummary, grade_dc_record
from analysis_engine.grading.master_builder import MasterSignatureStats, build_master_signature
from analysis_engine.ordermatrix.gear_math import GearOrders
from analysis_engine.signal.order_spectrum import OrderSpectrumResult, compute_order_spectrum
from analysis_engine.signal.order_tracking import OrderTrackingResult, compute_order_tracking
from analysis_engine.signal.stats import SignalStats, compute_stats

STAT_NAMES = ("mean", "variance", "skewness", "kurtosis", "rms", "peak", "crest")


def _stats_to_dict(stats: SignalStats) -> dict[str, float]:
    return {name: getattr(stats, name) for name in STAT_NAMES}


@dataclass(frozen=True)
class DcAnalysisResult:
    gear_label: str
    direction: str
    stats: SignalStats
    order_spectrum: OrderSpectrumResult
    order_tracking: OrderTrackingResult
    crash_noise: CrashNoiseCheckResult
    slippage: SlippageCheckResult
    grading: DcGradingSummary | None = None
    fail_reason_codes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.fail_reason_codes and (self.grading is None or self.grading.passed)


def analyze_dc_record(
    signal: np.ndarray,
    time_s: np.ndarray,
    rpm: np.ndarray,
    sample_rate_hz: float,
    gear_label: str,
    direction: str,
    gear_orders: GearOrders,
    masters: dict[str, MasterSignatureStats] | None = None,
    crash_noise_band_hz: tuple[float, float] = (500.0, 3000.0),
    crash_noise_threshold: float = 0.5,
    slippage_drop_ratio: float = 0.5,
    slippage_min_fraction: float = 0.1,
) -> DcAnalysisResult:
    stats = compute_stats(signal)
    order_spec = compute_order_spectrum(signal, time_s, rpm, samples_per_rev=360)
    tracking = compute_order_tracking(signal, time_s, rpm, sample_rate_hz, gear_orders.mesh_order)

    crash = detect_crash_noise(
        signal, sample_rate_hz, crash_noise_band_hz[0], crash_noise_band_hz[1], crash_noise_threshold
    )

    baseline_magnitude = float(np.median(tracking.magnitude)) or 1e-9
    slip = detect_slippage(tracking.magnitude, baseline_magnitude, slippage_drop_ratio, slippage_min_fraction)

    grading = grade_dc_record(_stats_to_dict(stats), masters) if masters else None

    fail_reasons = []
    if crash.detected:
        fail_reasons.append("CRASH_NOISE")
    if slip.detected:
        fail_reasons.append("SLIPPAGE")
    if grading is not None and not grading.passed:
        fail_reasons.append("ENVELOPE_NOK")

    return DcAnalysisResult(
        gear_label=gear_label,
        direction=direction,
        stats=stats,
        order_spectrum=order_spec,
        order_tracking=tracking,
        crash_noise=crash,
        slippage=slip,
        grading=grading,
        fail_reason_codes=fail_reasons,
    )


def build_masters_from_trials(
    trial_stats: list[SignalStats], full_scale_by_stat: dict[str, float]
) -> dict[str, MasterSignatureStats]:
    """Builds one MasterSignatureStats per stat name from a list of known-good
    trial units' stats for the same (gear, direction)."""
    masters = {}
    for stat_name in STAT_NAMES:
        values = [getattr(s, stat_name) for s in trial_stats]
        masters[stat_name] = build_master_signature(values, full_scale_by_stat[stat_name])
    return masters
