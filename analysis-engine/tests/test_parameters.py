import numpy as np
import pytest

from analysis_engine.grading.parameters import PARAMETER_CATALOG, compute_parameter_catalog, default_full_scale_by_param
from analysis_engine.ordermatrix.gear_math import GearOrders
from analysis_engine.signal.order_spectrum import compute_order_spectrum
from analysis_engine.signal.units import g_to_mps2, to_db_mps2

# The 49 literal names read off the client's real Master Entry "Parameters"
# screen -- this is the single most important assertion in this file. See
# grading/parameters.py's module docstring for the two formatting quirks
# (lowercase "max"/capitalized "Avg"; harmonic suffixes have no leading
# space, unit-family suffixes on RMS/PK do) that are deliberately preserved.
EXPECTED_NAMES = {
    "Mean max", "Mean Avg", "Variance max", "Variance Avg",
    "Skewness max", "Skewness Avg", "Kurtosis max", "Kurtosis Avg",
    "RMS max", "RMS Avg", "PK max", "PK Avg", "Crest max", "Crest Avg",
    "RMS max (m/s2)", "RMS Avg (m/s2)", "RMS max (dB m/s2)", "RMS Avg (dB m/s2)",
    "PK max (m/s2)", "PK Avg (m/s2)", "PK max (dB m/s2)", "PK Avg (dB m/s2)",
    "IN_H1(g)", "IN_H2(g)", "IN_H3(g)",
    "CM_H1(g)", "CM_H2(g)", "CM_H3(g)",
    "IN_S1.0(g)", "OUT_S1.0(g)", "OUTPUT_S1.0(g)",
    "IN_H1(m/s2)", "IN_H2(m/s2)", "IN_H3(m/s2)",
    "CM_H1(m/s2)", "CM_H2(m/s2)", "CM_H3(m/s2)",
    "IN_S1.0(m/s2)", "OUT_S1.0(m/s2)", "OUTPUT_S1.0(m/s2)",
    "IN_H1(dB m/s2)", "IN_H2(dB m/s2)", "IN_H3(dB m/s2)",
    "CM_H1(dB m/s2)", "CM_H2(dB m/s2)", "CM_H3(dB m/s2)",
    "IN_S1.0(dB m/s2)", "OUT_S1.0(dB m/s2)", "OUTPUT_S1.0(dB m/s2)",
}


def test_catalog_has_exactly_the_49_real_names():
    assert set(PARAMETER_CATALOG) == EXPECTED_NAMES
    assert len(PARAMETER_CATALOG) == 49


def _constant_rpm_signal(target_orders_and_amplitudes, rpm=3000.0, duration_s=2.0, sample_rate_hz=20000.0):
    n = int(sample_rate_hz * duration_s)
    t = np.arange(n) / sample_rate_hz
    omega = 2 * np.pi * rpm / 60.0
    theta = np.cumsum(np.full(n, omega)) / sample_rate_hz
    signal = np.zeros(n)
    for order, amplitude in target_orders_and_amplitudes:
        signal += amplitude * np.sin(order * theta)
    rng = np.random.default_rng(0)
    signal += rng.normal(0, 0.01, size=n)
    return signal, t, np.full(n, rpm)


# Well-separated target orders (gaps >= 1, tolerance is 0.5) so each
# parameter's order-spectrum lookup window contains exactly one injected tone.
_MESH_ORDER = 10.0
_LAYSHAFT_ORDER = 2.0
_OUTPUT_SHAFT_ORDER = 8.0
_FINAL_DRIVE_MESH_ORDER = 48.0

_GEAR_ORDERS_FULL = GearOrders(
    gear_label="R",
    mesh_order=_MESH_ORDER,
    idler_shaft_1_order=None,
    idler_shaft_2_order=None,
    layshaft_order=_LAYSHAFT_ORDER,
    output_shaft_order=_OUTPUT_SHAFT_ORDER,
    final_drive_mesh_order=_FINAL_DRIVE_MESH_ORDER,
)


def test_harmonic_parameters_pick_up_correct_order_amplitudes():
    tones = [
        (_MESH_ORDER * 1, 3.0),   # IN_H1
        (_MESH_ORDER * 2, 2.0),   # IN_H2
        (_MESH_ORDER * 3, 1.0),   # IN_H3
        (_FINAL_DRIVE_MESH_ORDER * 1, 4.0),  # CM_H1
        (1.0, 0.5),               # IN_S1.0 (constant reference order)
        (_LAYSHAFT_ORDER, 1.5),   # OUT_S1.0
        (_OUTPUT_SHAFT_ORDER, 2.5),  # OUTPUT_S1.0
    ]
    signal, t, rpm = _constant_rpm_signal(tones)
    order_spec = compute_order_spectrum(signal, t, rpm, samples_per_rev=360)

    result = compute_parameter_catalog(signal, order_spec, _GEAR_ORDERS_FULL, n_windows=1)

    assert result["IN_H1(g)"] == pytest.approx(3.0, rel=0.2)
    assert result["IN_H2(g)"] == pytest.approx(2.0, rel=0.2)
    assert result["IN_H3(g)"] == pytest.approx(1.0, rel=0.2)
    assert result["CM_H1(g)"] == pytest.approx(4.0, rel=0.2)
    assert result["IN_S1.0(g)"] == pytest.approx(0.5, rel=0.3)
    assert result["OUT_S1.0(g)"] == pytest.approx(1.5, rel=0.2)
    assert result["OUTPUT_S1.0(g)"] == pytest.approx(2.5, rel=0.2)


def test_rms_pk_unit_family_variants_match_conversion_helpers():
    signal, t, rpm = _constant_rpm_signal([(_MESH_ORDER, 2.0)])
    order_spec = compute_order_spectrum(signal, t, rpm, samples_per_rev=360)

    result = compute_parameter_catalog(signal, order_spec, _GEAR_ORDERS_FULL, n_windows=4)

    assert result["RMS max (m/s2)"] == pytest.approx(g_to_mps2(result["RMS max"]))
    assert result["RMS max (dB m/s2)"] == pytest.approx(to_db_mps2(g_to_mps2(result["RMS max"])))
    assert result["PK Avg (m/s2)"] == pytest.approx(g_to_mps2(result["PK Avg"]))
    assert result["PK Avg (dB m/s2)"] == pytest.approx(to_db_mps2(g_to_mps2(result["PK Avg"])))


def test_none_final_drive_mesh_order_drops_exactly_cm_h_names():
    signal, t, rpm = _constant_rpm_signal([(_MESH_ORDER, 1.0)])
    order_spec = compute_order_spectrum(signal, t, rpm, samples_per_rev=360)
    gear_orders = GearOrders(
        gear_label="R", mesh_order=_MESH_ORDER, idler_shaft_1_order=None, idler_shaft_2_order=None,
        layshaft_order=_LAYSHAFT_ORDER, output_shaft_order=_OUTPUT_SHAFT_ORDER, final_drive_mesh_order=None,
    )

    result = compute_parameter_catalog(signal, order_spec, gear_orders, n_windows=4)

    missing = EXPECTED_NAMES - set(result)
    assert missing == {f"CM_H{n}({unit})" for n in (1, 2, 3) for unit in ("g", "m/s2", "dB m/s2")}
    assert len(result) == 40


def test_none_layshaft_order_drops_exactly_out_s1_names():
    signal, t, rpm = _constant_rpm_signal([(_MESH_ORDER, 1.0)])
    order_spec = compute_order_spectrum(signal, t, rpm, samples_per_rev=360)
    gear_orders = GearOrders(
        gear_label="R", mesh_order=_MESH_ORDER, idler_shaft_1_order=None, idler_shaft_2_order=None,
        layshaft_order=None, output_shaft_order=_OUTPUT_SHAFT_ORDER, final_drive_mesh_order=_FINAL_DRIVE_MESH_ORDER,
    )

    result = compute_parameter_catalog(signal, order_spec, gear_orders, n_windows=4)

    missing = EXPECTED_NAMES - set(result)
    assert missing == {f"OUT_S1.0({unit})" for unit in ("g", "m/s2", "dB m/s2")}
    assert len(result) == 46


def test_both_final_drive_and_layshaft_none_drops_both_groups():
    signal, t, rpm = _constant_rpm_signal([(_MESH_ORDER, 1.0)])
    order_spec = compute_order_spectrum(signal, t, rpm, samples_per_rev=360)
    gear_orders = GearOrders(
        gear_label="R", mesh_order=_MESH_ORDER, idler_shaft_1_order=None, idler_shaft_2_order=None,
        layshaft_order=None, output_shaft_order=_OUTPUT_SHAFT_ORDER, final_drive_mesh_order=None,
    )

    result = compute_parameter_catalog(signal, order_spec, gear_orders, n_windows=4)

    assert len(result) == 37


def test_default_full_scale_by_param_covers_the_full_catalog():
    defaults = default_full_scale_by_param()
    assert set(defaults) == EXPECTED_NAMES
    assert all(value > 0 for value in defaults.values())
