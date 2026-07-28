import numpy as np
import pytest

from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from nvh_simulator.faults import Fault
from nvh_simulator.generators import (
    default_orders_for_gear,
    generate_dc_record,
    shaft_angle_and_speed,
    tach_pulse_train,
)

GEAR_R = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft=36, layshaft=32), gear_ratio=3.753)


def test_rpm_ramps_linearly():
    t, rpm, _ = shaft_angle_and_speed(rpm_start=1000, rpm_end=2500, duration_s=5.0, sample_rate_hz=1000)
    assert rpm[0] == pytest.approx(1000, abs=1)
    assert rpm[-1] == pytest.approx(2500, abs=5)
    # monotonically increasing for a run-up
    assert np.all(np.diff(rpm) >= 0)


def test_tach_pulse_frequency_matches_expected_pulse_count():
    duration_s = 2.0
    rpm_const = 1200.0  # 20 rev/s
    pulses_per_rev = 60
    t, rpm, theta = shaft_angle_and_speed(rpm_const, rpm_const, duration_s, sample_rate_hz=20000)
    pulses = tach_pulse_train(theta, pulses_per_rev)
    # number of rising edges ~= revolutions * pulses_per_rev
    rising_edges = np.sum(np.diff(pulses.astype(int)) == 1)
    expected_revolutions = (rpm_const / 60.0) * duration_s
    assert rising_edges == pytest.approx(expected_revolutions * pulses_per_rev, rel=0.02)


def test_generate_dc_record_is_deterministic_with_same_seed():
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)

    sig1 = generate_dc_record(GEAR_R, 1000, 2500, 2.0, 5000, rng=rng1)
    sig2 = generate_dc_record(GEAR_R, 1000, 2500, 2.0, 5000, rng=rng2)

    np.testing.assert_array_equal(sig1.channels["vib_a"], sig2.channels["vib_a"])
    np.testing.assert_array_equal(sig1.rpm, sig2.rpm)


def test_different_seeds_give_different_signals():
    sig1 = generate_dc_record(GEAR_R, 1000, 2500, 2.0, 5000, rng=np.random.default_rng(1))
    sig2 = generate_dc_record(GEAR_R, 1000, 2500, 2.0, 5000, rng=np.random.default_rng(2))
    assert not np.array_equal(sig1.channels["vib_a"], sig2.channels["vib_a"])


def test_default_orders_include_mesh_harmonics_and_final_drive():
    orders = default_orders_for_gear(GEAR_R)
    assert GEAR_R.mesh_order in orders
    assert GEAR_R.mesh_order * 2 in orders
    assert GEAR_R.layshaft_order in orders


def test_crash_noise_fault_increases_windowed_variance():
    rng_base = np.random.default_rng(7)
    baseline = generate_dc_record(GEAR_R, 1000, 2500, 4.0, 5000, rng=rng_base, noise_std=0.01)

    rng_fault = np.random.default_rng(7)
    fault = Fault(kind="crash_noise", start_s=1.5, end_s=2.0, amplitude=5.0)
    faulted = generate_dc_record(GEAR_R, 1000, 2500, 4.0, 5000, rng=rng_fault, noise_std=0.01, faults=[fault])

    window = (baseline.time_s >= 1.5) & (baseline.time_s <= 2.0)
    outside = ~window

    baseline_window_var = np.var(baseline.channels["vib_a"][window])
    faulted_window_var = np.var(faulted.channels["vib_a"][window])
    faulted_outside_var = np.var(faulted.channels["vib_a"][outside])

    assert faulted_window_var > baseline_window_var * 5
    # outside the fault window, faulted signal should look like baseline-ish variance
    assert faulted_outside_var < faulted_window_var
    assert "crash_noise" in faulted.injected_fault_kinds


def test_slippage_fault_reduces_mesh_order_amplitude_in_window():
    rng = np.random.default_rng(3)
    fault = Fault(kind="slippage", start_s=1.0, end_s=2.0, drop_to=0.05)
    sig = generate_dc_record(GEAR_R, 1000, 1000, 3.0, 5000, rng=rng, noise_std=0.001, faults=[fault])

    _, _, theta = shaft_angle_and_speed(1000, 1000, 3.0, 5000)
    # correlate signal against the mesh-order carrier to estimate its local amplitude
    carrier = np.sin(GEAR_R.mesh_order * theta)
    window = (sig.time_s >= 1.0) & (sig.time_s <= 2.0)
    outside = sig.time_s < 0.9

    corr_in_window = np.abs(np.mean(sig.channels["vib_a"][window] * carrier[window]))
    corr_outside = np.abs(np.mean(sig.channels["vib_a"][outside] * carrier[outside]))

    assert corr_in_window < corr_outside
    assert "slippage" in sig.injected_fault_kinds
