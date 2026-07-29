"""Unit conversions for accelerometer-native ('g') magnitudes: g -> m/s^2
(standard-gravity factor) and m/s^2 -> dB re 1 um/s^2 (ISO 1683's acceleration
reference). The dB reference is a documented, overridable assumption -- the
client has not confirmed which reference they use; ISO 1683's 1e-6 m/s^2 is
the standard convention and is used here as the default."""

from __future__ import annotations

import math

STANDARD_GRAVITY_MPS2 = 9.80665

# ISO 1683 acceleration level reference. Documented assumption -- not
# confirmed by the client; override via the `reference_mps2` parameter if a
# different convention is specified later.
DB_REFERENCE_MPS2 = 1e-6

# Floor applied before log10 so a genuinely zero/near-zero magnitude (e.g. a
# perfectly silent window, or an order-spectrum bin with no measurable peak)
# produces a large-but-finite negative dB value instead of -inf/NaN, which
# would otherwise break downstream G-ladder math (band_min/band_max/mean
# arithmetic on -inf).
_DB_FLOOR_MPS2 = 1e-12


def g_to_mps2(value_g: float) -> float:
    """Converts an accelerometer-native magnitude in g to m/s^2."""
    return value_g * STANDARD_GRAVITY_MPS2


def to_db_mps2(value_mps2: float, reference_mps2: float = DB_REFERENCE_MPS2) -> float:
    """dB = 20*log10(|value_mps2| / reference_mps2), floored to avoid log(0).
    `abs()` is defensive: every caller in this codebase only ever feeds this
    RMS/peak/spectral-peak magnitudes, which are already non-negative."""
    magnitude = max(abs(value_mps2), _DB_FLOOR_MPS2)
    return 20.0 * math.log10(magnitude / reference_mps2)
