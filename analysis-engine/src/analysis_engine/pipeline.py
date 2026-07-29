"""Orchestrates the per-DC-record analysis: parameter catalog (windowed
stats + unit families + harmonic order lookups) -> order spectrum/tracking ->
crash-noise/slippage checks -> grading against a master signature (if
available). This is the single entry point the CLI demo (and, later, the web
backend) calls per DC record."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from analysis_engine.faults.crash_noise import CrashNoiseCheckResult, detect_crash_noise
from analysis_engine.faults.slippage import SlippageCheckResult, detect_slippage
from analysis_engine.grading.envelope_check import DcGradingSummary, grade_dc_record
from analysis_engine.grading.limit_config import LimitConfigValue, grade_dc_record_with_limits
from analysis_engine.grading.master_builder import MasterSignatureStats, build_master_signature
from analysis_engine.grading.parameters import compute_parameter_catalog
from analysis_engine.ordermatrix.gear_math import GearOrders
from analysis_engine.signal.order_spectrum import OrderSpectrumResult, compute_order_spectrum
from analysis_engine.signal.order_tracking import OrderTrackingResult, compute_order_tracking
from analysis_engine.signal.windowed_stats import DEFAULT_N_WINDOWS


@dataclass(frozen=True)
class DcAnalysisResult:
    gear_label: str
    direction: str
    parameters: dict[str, float]
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
    n_windows: int = DEFAULT_N_WINDOWS,
    limit_configs: dict[str, LimitConfigValue] | None = None,
) -> DcAnalysisResult:
    order_spec = compute_order_spectrum(signal, time_s, rpm, samples_per_rev=360)
    tracking = compute_order_tracking(signal, time_s, rpm, sample_rate_hz, gear_orders.mesh_order)
    parameters = compute_parameter_catalog(signal, order_spec, gear_orders, n_windows=n_windows)

    crash = detect_crash_noise(
        signal, sample_rate_hz, crash_noise_band_hz[0], crash_noise_band_hz[1], crash_noise_threshold
    )

    baseline_magnitude = float(np.median(tracking.magnitude)) or 1e-9
    slip = detect_slippage(tracking.magnitude, baseline_magnitude, slippage_drop_ratio, slippage_min_fraction)

    if limit_configs:
        grading = grade_dc_record_with_limits(parameters, limit_configs)
    elif masters:
        grading = grade_dc_record(parameters, masters)
    else:
        grading = None

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
        parameters=parameters,
        order_spectrum=order_spec,
        order_tracking=tracking,
        crash_noise=crash,
        slippage=slip,
        grading=grading,
        fail_reason_codes=fail_reasons,
    )


def compute_trial_parameters(
    signal: np.ndarray,
    time_s: np.ndarray,
    rpm: np.ndarray,
    gear_orders: GearOrders,
    n_windows: int = DEFAULT_N_WINDOWS,
) -> dict[str, float]:
    """Convenience wrapper for callers that only need one trial's parameter
    catalog (master-building loops in seed_demo_data.py, the CLI demo, and
    tests) without the rest of analyze_dc_record's output. Keeps the
    compute_order_spectrum(..., samples_per_rev=360) convention in one place."""
    order_spec = compute_order_spectrum(signal, time_s, rpm, samples_per_rev=360)
    return compute_parameter_catalog(signal, order_spec, gear_orders, n_windows=n_windows)


def build_masters_from_trials(
    trial_parameters: list[dict[str, float]], full_scale_by_param: dict[str, float]
) -> dict[str, MasterSignatureStats]:
    """Builds one MasterSignatureStats per parameter name observed across
    trials. A parameter present in zero trials for this gear (e.g. a harmonic
    whose underlying GearOrders field was None, so compute_parameter_catalog
    omitted it) is skipped entirely -- mirroring grade_dc_record's existing
    pattern of silently ignoring parameters with no master."""
    param_names: set[str] = set()
    for trial in trial_parameters:
        param_names.update(trial.keys())

    masters: dict[str, MasterSignatureStats] = {}
    for name in param_names:
        values = [t[name] for t in trial_parameters if name in t]
        if len(values) < 2:
            continue
        masters[name] = build_master_signature(values, full_scale_by_param.get(name, 10.0))
    return masters
