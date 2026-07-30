"""Settings dataclasses for the Frequency-Series PLOT SETUP dialog --
matches the field set of the real Vibr-O-Matic Analyzer's plot-setup
window (see docs/vom_manual.txt sections 13.1.3.8 / 13.2.3.8, plus the
7 reference photos the user shared).

One dataclass per sub-tab (FFT / Order Spectrum / Order Tracking /
Waterfall / Cascade / Colormap / Octave). Defaults come straight from
the LabVIEW screens (Hanning window, MAX ORDER 32, 10 averages, etc)
so a fresh session opens looking familiar to an operator moving over
from the real system."""

from __future__ import annotations

from dataclasses import dataclass, field


# --- shared submodels ------------------------------------------------

AVERAGING_MODES = ("No averaging", "Vector averaging", "RMS averaging", "Peak hold")
WEIGHTING_MODES = ("Exponential", "Linear")
LINEAR_MODES = ("One shot", "Continuous")
LINEAR_DB = ("no change", "linear", "dB")
POWER_MAGNITUDE = ("magnitude", "power")
VIEW_MODES = ("rms", "peak", "peak-to-peak")
WINDOW_TYPES = ("Hanning", "Hamming", "Blackman", "Flat top", "Rectangular", "Gaussian")
PEAK_SEARCH = ("Single Max Peak", "Multi Peak")


@dataclass
class AveragingParams:
    """Shared 'AVERAGING PARAMETERS' block from the LabVIEW screens."""
    averaging_mode: str = "No averaging"
    weighting_mode: str = "Exponential"
    num_averages: int = 10
    linear_mode: str = "One shot"


@dataclass
class SpectraScaling:
    """Shared 'SPECTRA' / 'SCALING' block."""
    linear_db: str = "no change"  # no change | linear | dB
    db_reference: float = 0.0
    power_magnitude: str = "magnitude"
    view: str = "rms"


# --- per-sub-tab settings --------------------------------------------


@dataclass
class FftSettings:
    """FFT sub-tab. Peak search + zoom (start/stop freq, window, %
    overlap, number of lines) + averaging + spectra."""
    peak_search: str = "Single Max Peak"
    peak_threshold: float = -74.7399
    start_frequency_hz: float = 0.0
    stop_frequency_hz: float = 0.0
    window: str = "Hanning"
    percent_overlap: float = 0.0
    number_of_lines: int = 0
    averaging: AveragingParams = field(default_factory=AveragingParams)
    spectra: SpectraScaling = field(default_factory=SpectraScaling)


@dataclass
class OrderSpectrumSettings:
    """ORDER SPECTRUM sub-tab. Max order + resolution + window, plus
    peak search, envelope band, averaging, spectra."""
    max_order: float = 32.0
    order_resolution: float = 0.1
    window: str = "Hanning"
    peak_search: str = "Single Max Peak"
    peak_threshold: float = -74.7399
    envelope_db_on: bool = False
    band_center: float = 6000.0
    band_unit: str = "Hz"
    band_span_order: float = 20.0
    averaging: AveragingParams = field(default_factory=AveragingParams)
    spectra: SpectraScaling = field(default_factory=SpectraScaling)


@dataclass
class OrderTrackingSettings:
    """ORDER TRACKING sub-tab. X axis (Time/Speed) + max order + BW
    order + Time/Speed segment ranges + scaling."""
    x_axis: str = "Time"  # Time | Speed
    max_order: float = 32.0
    bw_order: float = 32.0
    time_start_s: float = 0.0
    time_end_s: float = 10.0
    time_step_s: float = 0.5
    speed_start_rpm: float = 0.0
    speed_end_rpm: float = 5000.0
    speed_step_rpm: float = 10.0
    scaling: SpectraScaling = field(default_factory=lambda: SpectraScaling(linear_db="linear"))


@dataclass
class SpectrogramSettings:
    """Shared shape for WATERFALL / CASCADE / COLORMAP -- all three
    have the same field set in the LabVIEW dialog (plot type / max
    order / dB ON / window / bins / time-segment / speed-segment /
    scaling), just three different projections of the same STFT."""
    plot_type: str = "Frequency-Time"
    max_order: float = 32.0
    db_on: bool = False
    window_type: str = "Gaussian"
    freq_order_bins: int = 2048
    time_segment_mode: str = "SEGMENT PERIOD"
    time_start_s: float = 0.0
    time_end_s: float = 10.0
    time_step_s: float = 0.5
    speed_start_rpm: float = 0.0
    speed_end_rpm: float = 5000.0
    speed_step_rpm: float = 10.0
    scaling: SpectraScaling = field(default_factory=lambda: SpectraScaling(linear_db="linear"))


@dataclass
class OctaveSettings:
    """OCTAVE sub-tab. Same shape as the other steady-state analyses
    -- averaging + scaling drive the display."""
    averaging: AveragingParams = field(default_factory=AveragingParams)
    spectra: SpectraScaling = field(default_factory=SpectraScaling)


# --- root container --------------------------------------------------


@dataclass
class FreqDomainSettings:
    """One-per-screen settings container. Owned by LiveDisplayScreen
    (in-memory only for this pass -- future work persists to the
    backend keyed by (model_id, channel_name))."""
    fft: FftSettings = field(default_factory=FftSettings)
    order_spectrum: OrderSpectrumSettings = field(default_factory=OrderSpectrumSettings)
    order_tracking: OrderTrackingSettings = field(default_factory=OrderTrackingSettings)
    waterfall: SpectrogramSettings = field(default_factory=SpectrogramSettings)
    cascade: SpectrogramSettings = field(default_factory=SpectrogramSettings)
    colormap: SpectrogramSettings = field(default_factory=SpectrogramSettings)
    octave: OctaveSettings = field(default_factory=OctaveSettings)
