import numpy as np

from analysis_engine.signal.octave import compute_octave_bands


def test_octave_band_energy_peaks_near_tone_frequency():
    fs = 20000
    duration = 2.0
    t = np.arange(int(fs * duration)) / fs
    x = 1.0 * np.sin(2 * np.pi * 1000 * t)  # tone inside the 1000 Hz octave band

    result = compute_octave_bands(x, fs)

    peak_band_idx = int(np.argmax(result.rms))
    assert result.center_freq_hz[peak_band_idx] == 1000
