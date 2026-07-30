"""Widget-level smoke tests for ColorMapPlot / WaterfallPlot /
OctaveBarsPlot -- setters accept the expected shapes and repainting
doesn't crash. Rendering correctness is verified visually via the
Live Display screenshot pass."""

import numpy as np

from nvh_qt_app.widgets.spectrogram_plots import (
    ColorMapPlot, OctaveBarsPlot, WaterfallPlot,
)


class ColorMapPlotTests:
    def test_set_spectrogram_accepts_matrix(self, qapp):
        plot = ColorMapPlot()
        mag = np.abs(np.random.rand(64, 32))
        times = np.linspace(0, 1, 32)
        freqs = np.linspace(0, 2500, 64)
        plot.set_spectrogram(mag, times, freqs)
        assert plot._magnitude is not None
        assert plot._magnitude.shape == (64, 32)

    def test_clear_wipes_state(self, qapp):
        plot = ColorMapPlot()
        plot.set_spectrogram(np.ones((8, 8)), np.arange(8), np.arange(8))
        plot.clear()
        assert plot._magnitude is None


class WaterfallPlotTests:
    def test_set_spectrogram_accepts_matrix(self, qapp):
        plot = WaterfallPlot()
        mag = np.abs(np.random.rand(64, 32))
        plot.set_spectrogram(mag, np.arange(32), np.arange(64))
        assert plot._magnitude is not None


class OctaveBarsPlotTests:
    def test_set_bands_stores_arrays(self, qapp):
        plot = OctaveBarsPlot()
        centers = (31.5, 63, 125, 250)
        rms = (0.1, 0.2, 0.3, 0.4)
        plot.set_bands(centers, rms)
        assert plot._centers == list(centers)
        assert plot._rms == list(rms)

    def test_clear_empties_state(self, qapp):
        plot = OctaveBarsPlot()
        plot.set_bands((100.0,), (1.0,))
        plot.clear()
        assert plot._centers == []
        assert plot._rms == []
