import numpy as np
import pytest

from nvh_contract.calibration import scale_v_to_eu


class ScaleVToEuTests:
    def test_identity_scaling_leaves_samples_unchanged(self):
        # 1000 mV/EU + 0 dB = factor of 1.0 (V and EU are the same
        # numerical scale after the mV<->V cancellation).
        arr = scale_v_to_eu([0.1, -0.2, 0.3], sensor_sensitivity_mv_per_eu=1000.0)
        np.testing.assert_allclose(arr, [0.1, -0.2, 0.3])

    def test_100_mv_per_g_accelerometer_gives_10x_gain(self):
        # 100 mV/g sensitivity -> factor 1000/100 = 10 EU per V.
        arr = scale_v_to_eu([0.1, 0.2], sensor_sensitivity_mv_per_eu=100.0)
        np.testing.assert_allclose(arr, [1.0, 2.0])

    def test_positive_pregain_reduces_output(self):
        # +20 dB pregain = 10x amp gain -> divide by 10 to recover source.
        arr = scale_v_to_eu([1.0], sensor_sensitivity_mv_per_eu=1000.0, pregain_db=20.0)
        np.testing.assert_allclose(arr, [0.1])

    def test_returns_numpy_float64(self):
        arr = scale_v_to_eu([1, 2, 3], sensor_sensitivity_mv_per_eu=1000.0)
        assert arr.dtype == np.float64
