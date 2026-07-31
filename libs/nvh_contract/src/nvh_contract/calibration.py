"""Helpers for turning raw acquisition volts into engineering units,
using the same calibration constants the Calibration screen stores in
`CalibrationRow` (nvh_contract.db).

Kept small and dependency-free so both the acquisition producer
(web-backend/scripts/live_daq.py) and any post-analysis TDMS reader
can call it without pulling the whole nvh_web_backend stack.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def scale_v_to_eu(
    values_v: Sequence[float] | np.ndarray,
    sensor_sensitivity_mv_per_eu: float,
    pregain_db: float = 0.0,
) -> np.ndarray:
    """Convert an array of sample volts to engineering units.

    Two calibration constants are applied, matching the physical signal
    chain:

    - **sensor_sensitivity_mv_per_eu** -- how many mV the sensor outputs
      per one EU. E.g. a 100 mV/g accelerometer has 100.0 here (with
      engineering_units="g"). The scaling factor is 1000 / sensitivity.
    - **pregain_db** -- amplifier gain (in dB) applied before the ADC.
      To recover the source EU we divide by that gain, i.e. the factor
      is 10**(-pregain_db / 20).

    Returns a numpy float64 array of the same length. Identity scaling
    (1000 mV/EU sensitivity, 0 dB pregain) leaves the samples unchanged
    apart from the mV<->V unit factor.
    """
    values = np.asarray(values_v, dtype=np.float64)
    scale = 1000.0 / sensor_sensitivity_mv_per_eu
    if pregain_db != 0.0:
        scale = scale / (10.0 ** (pregain_db / 20.0))
    return values * scale
