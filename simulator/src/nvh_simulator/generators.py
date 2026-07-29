"""Synthesizes gearbox NVH signals for a single DC record (one gear + direction
run-up/run-down). Signals are built as sums of gear-mesh order components riding
on an instantaneous shaft speed ramp, plus broadband noise and optional injected
faults, so the analysis engine can be developed and tested with known ground
truth before any real hardware exists."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from analysis_engine.ordermatrix.gear_math import GearOrders
from nvh_simulator.faults import (
    Fault,
    crash_noise_burst,
    extra_order_component,
    slippage_envelope,
)


@dataclass
class DcSignal:
    time_s: np.ndarray
    rpm: np.ndarray
    tach_pulse: np.ndarray
    channels: dict[str, np.ndarray]
    injected_fault_kinds: list[str] = field(default_factory=list)


def shaft_angle_and_speed(
    rpm_start: float, rpm_end: float, duration_s: float, sample_rate_hz: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Linear RPM ramp over `duration_s`; shaft angle is the closed-form
    integral of instantaneous angular speed, so order components stay
    phase-consistent through the ramp (angle-domain resampling later needs
    this to be correct, not just "sin(2*pi*f*t)" with a changing f)."""
    n = max(1, int(round(duration_s * sample_rate_hz)))
    t = np.arange(n) / sample_rate_hz
    rpm = rpm_start + (rpm_end - rpm_start) * (t / duration_s)
    theta = (2 * np.pi / 60.0) * (rpm_start * t + (rpm_end - rpm_start) * t**2 / (2 * duration_s))
    return t, rpm, theta


def tach_pulse_train(theta: np.ndarray, pulses_per_rev: int) -> np.ndarray:
    """Square-wave encoder pulse channel, frequency-modulated by the shaft
    angle (so it naturally speeds up/slows down with rpm)."""
    phase = (pulses_per_rev * theta) % (2 * np.pi)
    return (phase < np.pi).astype(np.int8)


def default_orders_for_gear(gear_orders: GearOrders, base_amplitude: float = 1.0) -> dict[float, float]:
    """A physically-motivated default order content for a healthy gear: the
    mesh order and its first two harmonics (dominant gear-whine tones), plus
    the layshaft and final-drive orders at lower amplitude."""
    orders: dict[float, float] = {}
    for harmonic, amp_scale in ((1, 1.0), (2, 0.4), (3, 0.15)):
        orders[gear_orders.mesh_order * harmonic] = base_amplitude * amp_scale
    if gear_orders.layshaft_order:
        orders[gear_orders.layshaft_order] = base_amplitude * 0.1
    if gear_orders.final_drive_mesh_order:
        orders[gear_orders.final_drive_mesh_order] = base_amplitude * 0.3
    return orders


def synthesize_channel(
    theta: np.ndarray,
    t: np.ndarray,
    orders: dict[float, float],
    noise_std: float,
    rng: np.random.Generator,
    order_envelopes: dict[float, callable] | None = None,
    amplitude_jitter_std: float = 0.03,
) -> np.ndarray:
    """`amplitude_jitter_std` draws one multiplicative jitter factor per
    order per call (not per sample) -- a stand-in for real unit-to-unit
    variance (mounting, meshing quality, bearing wear) that a real
    accelerometer would show between nominally-identical healthy units.
    Without it, gear-mesh order amplitudes are perfectly deterministic
    (only phase varies), which makes any order-spectrum-peak-based grading
    (e.g. the IN_H*/CM_H* harmonic parameters) build a razor-thin G-ladder
    band from trial data and then fail healthy units on FFT-bin noise
    alone."""
    signal = np.zeros_like(theta)
    order_envelopes = order_envelopes or {}
    for order, amplitude in orders.items():
        phase0 = rng.uniform(0.0, 2 * np.pi)
        jitter = rng.normal(1.0, amplitude_jitter_std) if amplitude_jitter_std else 1.0
        envelope = order_envelopes.get(order)
        amp = amplitude * jitter * envelope(t) if envelope is not None else amplitude * jitter
        signal += amp * np.sin(order * theta + phase0)
    signal += rng.normal(0.0, noise_std, size=theta.shape)
    return signal


def generate_dc_record(
    gear_orders: GearOrders,
    rpm_start: float,
    rpm_end: float,
    duration_s: float,
    sample_rate_hz: float,
    pulses_per_rev: int = 60,
    channel_names: tuple[str, ...] = ("vib_a", "mic"),
    noise_std: float = 0.02,
    rng: np.random.Generator | None = None,
    faults: list[Fault] | None = None,
) -> DcSignal:
    rng = rng if rng is not None else np.random.default_rng()
    t, rpm, theta = shaft_angle_and_speed(rpm_start, rpm_end, duration_s, sample_rate_hz)
    tach_pulse = tach_pulse_train(theta, pulses_per_rev)
    orders = default_orders_for_gear(gear_orders)

    order_envelopes: dict[float, callable] = {}
    extra_signal = np.zeros_like(t)
    injected_fault_kinds: list[str] = []

    for fault in faults or []:
        if fault.kind == "slippage":
            order_envelopes[gear_orders.mesh_order] = (
                lambda tt, f=fault: slippage_envelope(tt, f.start_s, f.end_s, f.drop_to)
            )
            injected_fault_kinds.append("slippage")
        elif fault.kind == "crash_noise":
            extra_signal = extra_signal + crash_noise_burst(t, fault.start_s, fault.end_s, fault.amplitude, rng)
            injected_fault_kinds.append("crash_noise")
        elif fault.kind == "extra_order":
            if fault.order is None:
                raise ValueError("extra_order fault requires `order` to be set")
            extra_signal = extra_signal + extra_order_component(theta, fault.order, fault.amplitude, rng)
            injected_fault_kinds.append("extra_order")

    channels = {
        name: synthesize_channel(theta, t, orders, noise_std, rng, order_envelopes) + extra_signal
        for name in channel_names
    }

    return DcSignal(
        time_s=t,
        rpm=rpm,
        tach_pulse=tach_pulse,
        channels=channels,
        injected_fault_kinds=injected_fault_kinds,
    )
