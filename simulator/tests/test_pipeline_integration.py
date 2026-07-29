"""End-to-end integration test: simulator generates known-good trial units and
one healthy + one faulty test unit; the analysis-engine pipeline must build a
master signature, pass the healthy unit, and fail the faulty unit for the
right reason. This is the core Phase 1 acceptance check — an evaluatable
result with no hardware and no web UI involved."""

import numpy as np

from analysis_engine.grading.parameters import default_full_scale_by_param
from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from analysis_engine.pipeline import analyze_dc_record, build_masters_from_trials, compute_trial_parameters
from nvh_simulator.faults import Fault
from nvh_simulator.generators import generate_dc_record

GEAR_R = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
SAMPLE_RATE_HZ = 5000
RPM_START, RPM_END = 1000, 2500
DURATION_S = 4.0
FULL_SCALE_BY_PARAM = default_full_scale_by_param()


def _trial_parameters(seed: int):
    rng = np.random.default_rng(seed)
    sig = generate_dc_record(GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng)
    return compute_trial_parameters(sig.channels["vib_a"], sig.time_s, sig.rpm, GEAR_R)


def test_healthy_unit_passes_against_master_built_from_trials():
    # a larger trial population gives the master's band_min/band_max a
    # realistic spread; too few trials makes the G-ladder unrealistically
    # tight around whatever phase/noise realization happened to occur.
    trial_parameters = [_trial_parameters(seed) for seed in range(10, 60)]
    masters = build_masters_from_trials(trial_parameters, FULL_SCALE_BY_PARAM)

    rng = np.random.default_rng(999)  # a fresh, healthy unit, unseen by the master
    healthy = generate_dc_record(GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng)

    result = analyze_dc_record(
        healthy.channels["vib_a"], healthy.time_s, healthy.rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters
    )

    assert result.passed is True
    assert result.fail_reason_codes == []


def test_crash_noise_fault_is_flagged():
    trial_parameters = [_trial_parameters(seed) for seed in range(10, 20)]
    masters = build_masters_from_trials(trial_parameters, FULL_SCALE_BY_PARAM)

    rng = np.random.default_rng(1234)
    fault = Fault(kind="crash_noise", start_s=2.0, end_s=2.3, amplitude=8.0)
    faulty = generate_dc_record(
        GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng, faults=[fault]
    )

    result = analyze_dc_record(
        faulty.channels["vib_a"],
        faulty.time_s,
        faulty.rpm,
        SAMPLE_RATE_HZ,
        "R",
        "RU",
        GEAR_R,
        masters,
        crash_noise_band_hz=(500.0, 2000.0),
        crash_noise_threshold=0.5,
    )

    assert result.passed is False
    assert "CRASH_NOISE" in result.fail_reason_codes


def test_slippage_fault_is_flagged():
    rng = np.random.default_rng(5555)
    fault = Fault(kind="slippage", start_s=1.0, end_s=3.0, drop_to=0.05)
    faulty = generate_dc_record(
        GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng, noise_std=0.005, faults=[fault]
    )

    result = analyze_dc_record(
        faulty.channels["vib_a"], faulty.time_s, faulty.rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters=None
    )

    assert "SLIPPAGE" in result.fail_reason_codes
