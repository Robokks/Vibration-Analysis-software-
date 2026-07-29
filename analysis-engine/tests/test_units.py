import pytest

from analysis_engine.signal.units import g_to_mps2, to_db_mps2


def test_g_to_mps2_uses_standard_gravity():
    assert g_to_mps2(1.0) == pytest.approx(9.80665)
    assert g_to_mps2(2.0) == pytest.approx(19.6133)


def test_to_db_mps2_reference_value_is_zero_db():
    assert to_db_mps2(1e-6) == pytest.approx(0.0, abs=1e-9)


def test_to_db_mps2_known_ratio():
    assert to_db_mps2(1e-3) == pytest.approx(60.0)


def test_to_db_mps2_zero_and_negative_inputs_stay_finite():
    zero_db = to_db_mps2(0.0)  # floored to the tiny epsilon -> large negative, not -inf
    negative_db = to_db_mps2(-1.0)  # abs(-1.0) == 1.0 -> same as to_db_mps2(1.0), well above reference

    import math

    assert math.isfinite(zero_db)
    assert math.isfinite(negative_db)
    assert zero_db < -100  # far below the reference, but finite
    assert negative_db == pytest.approx(to_db_mps2(1.0))
