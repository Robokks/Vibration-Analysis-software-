"""Frequency-Series PLOT SETUP dialog -- one QTabWidget across 7
sub-tab pages (FFT / Order Spectrum / Order Tracking / Waterfall /
Cascade / Colormap / Octave), each with the form fields the real
LabVIEW screen shows. Roundtrips through the FreqDomainSettings
dataclass tree: constructor pulls values in, ``current_settings()``
reads them back out.

The dialog is layout-only -- LiveDisplayScreen owns the settings
object and decides which fields actually affect the plots (max order
is wired today; the rest is UI scaffold ready for follow-up wiring)."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..freq_domain_settings import (
    AVERAGING_MODES, AveragingParams, FftSettings, FreqDomainSettings,
    LINEAR_DB, LINEAR_MODES, OctaveSettings, OrderSpectrumSettings,
    OrderTrackingSettings, PEAK_SEARCH, POWER_MAGNITUDE, SpectraScaling,
    SpectrogramSettings, VIEW_MODES, WEIGHTING_MODES, WINDOW_TYPES,
)


# ---------- small helpers -----------------------------------------


def _double_spin(value: float, minimum: float = -1e9, maximum: float = 1e9,
                 decimals: int = 4, suffix: str = "") -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setRange(minimum, maximum)
    sb.setDecimals(decimals)
    sb.setValue(value)
    if suffix:
        sb.setSuffix(suffix)
    return sb


def _int_spin(value: int, minimum: int = 0, maximum: int = 100000) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(minimum, maximum)
    sb.setValue(value)
    return sb


def _combo(current: str, options) -> QComboBox:
    cb = QComboBox()
    cb.addItems(list(options))
    idx = cb.findText(current)
    if idx >= 0:
        cb.setCurrentIndex(idx)
    return cb


def _averaging_group(params: AveragingParams) -> tuple[QGroupBox, dict[str, QWidget]]:
    box = QGroupBox("AVERAGING PARAMETERS")
    form = QFormLayout(box)
    fields = {
        "averaging_mode": _combo(params.averaging_mode, AVERAGING_MODES),
        "weighting_mode": _combo(params.weighting_mode, WEIGHTING_MODES),
        "num_averages": _int_spin(params.num_averages, 1, 1000),
        "linear_mode": _combo(params.linear_mode, LINEAR_MODES),
    }
    form.addRow("Averaging Mode", fields["averaging_mode"])
    form.addRow("Weighting Mode", fields["weighting_mode"])
    form.addRow("Number of Averages", fields["num_averages"])
    form.addRow("Linear Mode", fields["linear_mode"])
    return box, fields


def _spectra_group(scaling: SpectraScaling, title: str = "SPECTRA") -> tuple[QGroupBox, dict[str, QWidget]]:
    box = QGroupBox(title)
    form = QFormLayout(box)
    fields = {
        "linear_db": _combo(scaling.linear_db, LINEAR_DB),
        "db_reference": _double_spin(scaling.db_reference, -1e6, 1e6),
        "power_magnitude": _combo(scaling.power_magnitude, POWER_MAGNITUDE),
        "view": _combo(scaling.view, VIEW_MODES),
    }
    form.addRow("Linear/dB", fields["linear_db"])
    form.addRow("dB reference", fields["db_reference"])
    form.addRow("Power/Magnitude", fields["power_magnitude"])
    form.addRow("View", fields["view"])
    return box, fields


def _read_averaging(fields: dict[str, QWidget]) -> AveragingParams:
    return AveragingParams(
        averaging_mode=fields["averaging_mode"].currentText(),
        weighting_mode=fields["weighting_mode"].currentText(),
        num_averages=fields["num_averages"].value(),
        linear_mode=fields["linear_mode"].currentText(),
    )


def _read_spectra(fields: dict[str, QWidget]) -> SpectraScaling:
    return SpectraScaling(
        linear_db=fields["linear_db"].currentText(),
        db_reference=fields["db_reference"].value(),
        power_magnitude=fields["power_magnitude"].currentText(),
        view=fields["view"].currentText(),
    )


# ---------- per-tab builders --------------------------------------


class _FftTab(QWidget):
    def __init__(self, s: FftSettings, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        peak_box = QGroupBox("PEAK SEARCH SETTINGS")
        peak_form = QFormLayout(peak_box)
        self.peak_search = _combo(s.peak_search, PEAK_SEARCH)
        self.peak_threshold = _double_spin(s.peak_threshold)
        peak_form.addRow("Single/Multi", self.peak_search)
        peak_form.addRow("Threshold", self.peak_threshold)
        layout.addWidget(peak_box)

        zoom_box = QGroupBox("ZOOM SETTINGS")
        zoom_form = QFormLayout(zoom_box)
        self.start_freq = _double_spin(s.start_frequency_hz, 0.0, 1e9, suffix=" Hz")
        self.stop_freq = _double_spin(s.stop_frequency_hz, 0.0, 1e9, suffix=" Hz")
        self.window = _combo(s.window, WINDOW_TYPES)
        self.overlap = _double_spin(s.percent_overlap, 0.0, 99.0, decimals=1, suffix=" %")
        self.lines = _int_spin(s.number_of_lines, 0, 65536)
        zoom_form.addRow("Start Frequency", self.start_freq)
        zoom_form.addRow("Stop Frequency", self.stop_freq)
        zoom_form.addRow("Window", self.window)
        zoom_form.addRow("% Overlap", self.overlap)
        zoom_form.addRow("Number of Lines", self.lines)
        layout.addWidget(zoom_box)

        avg_box, self.avg_fields = _averaging_group(s.averaging)
        layout.addWidget(avg_box)
        spectra_box, self.spectra_fields = _spectra_group(s.spectra)
        layout.addWidget(spectra_box)
        layout.addStretch(1)

    def read(self) -> FftSettings:
        return FftSettings(
            peak_search=self.peak_search.currentText(),
            peak_threshold=self.peak_threshold.value(),
            start_frequency_hz=self.start_freq.value(),
            stop_frequency_hz=self.stop_freq.value(),
            window=self.window.currentText(),
            percent_overlap=self.overlap.value(),
            number_of_lines=self.lines.value(),
            averaging=_read_averaging(self.avg_fields),
            spectra=_read_spectra(self.spectra_fields),
        )


class _OrderSpectrumTab(QWidget):
    def __init__(self, s: OrderSpectrumSettings, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        core = QGroupBox("Core")
        core_form = QFormLayout(core)
        self.max_order = _double_spin(s.max_order, 0.1, 1e5, decimals=2)
        self.order_resolution = _double_spin(s.order_resolution, 0.001, 100.0, decimals=3)
        self.window = _combo(s.window, WINDOW_TYPES)
        core_form.addRow("MAX ORDER", self.max_order)
        core_form.addRow("ORDER RESOLUTION", self.order_resolution)
        core_form.addRow("Window", self.window)
        layout.addWidget(core)

        peak = QGroupBox("PEAK SEARCH SETTINGS")
        peak_form = QFormLayout(peak)
        self.peak_search = _combo(s.peak_search, PEAK_SEARCH)
        self.peak_threshold = _double_spin(s.peak_threshold)
        peak_form.addRow("Single/Multi", self.peak_search)
        peak_form.addRow("Threshold", self.peak_threshold)
        layout.addWidget(peak)

        env = QGroupBox("ENVELOPE SETTINGS")
        env_form = QFormLayout(env)
        self.db_on = QCheckBox("dB On(T)")
        self.db_on.setChecked(s.envelope_db_on)
        env_form.addRow(self.db_on)
        self.band_center = _double_spin(s.band_center, 0.0, 1e6)
        self.band_unit = _combo(s.band_unit, ("Hz", "Order"))
        self.band_span = _double_spin(s.band_span_order, 0.0, 1000.0)
        env_form.addRow("Band center", self.band_center)
        env_form.addRow("Band unit", self.band_unit)
        env_form.addRow("Band span [Order]", self.band_span)
        layout.addWidget(env)

        avg_box, self.avg_fields = _averaging_group(s.averaging)
        layout.addWidget(avg_box)
        spectra_box, self.spectra_fields = _spectra_group(s.spectra)
        layout.addWidget(spectra_box)
        layout.addStretch(1)

    def read(self) -> OrderSpectrumSettings:
        return OrderSpectrumSettings(
            max_order=self.max_order.value(),
            order_resolution=self.order_resolution.value(),
            window=self.window.currentText(),
            peak_search=self.peak_search.currentText(),
            peak_threshold=self.peak_threshold.value(),
            envelope_db_on=self.db_on.isChecked(),
            band_center=self.band_center.value(),
            band_unit=self.band_unit.currentText(),
            band_span_order=self.band_span.value(),
            averaging=_read_averaging(self.avg_fields),
            spectra=_read_spectra(self.spectra_fields),
        )


class _OrderTrackingTab(QWidget):
    def __init__(self, s: OrderTrackingSettings, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        core = QGroupBox("Core")
        core_form = QFormLayout(core)
        self.x_axis = _combo(s.x_axis, ("Time", "Speed"))
        self.max_order = _double_spin(s.max_order, 0.1, 1e5, decimals=2)
        self.bw_order = _double_spin(s.bw_order, 0.1, 1e5, decimals=2)
        core_form.addRow("X AXIS", self.x_axis)
        core_form.addRow("MAX ORDER", self.max_order)
        core_form.addRow("BW ORDER", self.bw_order)
        layout.addWidget(core)

        time_box = QGroupBox("TIME SEGMENT [s]")
        time_form = QFormLayout(time_box)
        self.time_start = _double_spin(s.time_start_s, 0.0, 1e6)
        self.time_end = _double_spin(s.time_end_s, 0.0, 1e6)
        self.time_step = _double_spin(s.time_step_s, 0.001, 1e6, decimals=3)
        time_form.addRow("start [s]", self.time_start)
        time_form.addRow("end [s]", self.time_end)
        time_form.addRow("step size [s]", self.time_step)
        layout.addWidget(time_box)

        speed_box = QGroupBox("SPEED SEGMENT [rpm]")
        speed_form = QFormLayout(speed_box)
        self.speed_start = _double_spin(s.speed_start_rpm, 0.0, 1e6)
        self.speed_end = _double_spin(s.speed_end_rpm, 0.0, 1e6)
        self.speed_step = _double_spin(s.speed_step_rpm, 0.1, 1e6)
        speed_form.addRow("start [rpm]", self.speed_start)
        speed_form.addRow("end [rpm]", self.speed_end)
        speed_form.addRow("step size [rpm]", self.speed_step)
        layout.addWidget(speed_box)

        scaling_box, self.scaling_fields = _spectra_group(s.scaling, title="SCALING")
        layout.addWidget(scaling_box)
        layout.addStretch(1)

    def read(self) -> OrderTrackingSettings:
        return OrderTrackingSettings(
            x_axis=self.x_axis.currentText(),
            max_order=self.max_order.value(),
            bw_order=self.bw_order.value(),
            time_start_s=self.time_start.value(),
            time_end_s=self.time_end.value(),
            time_step_s=self.time_step.value(),
            speed_start_rpm=self.speed_start.value(),
            speed_end_rpm=self.speed_end.value(),
            speed_step_rpm=self.speed_step.value(),
            scaling=_read_spectra(self.scaling_fields),
        )


class _SpectrogramTab(QWidget):
    """Shared tab body for WATERFALL / CASCADE / COLORMAP -- identical
    field set. `label` is just for the tab header."""

    def __init__(self, s: SpectrogramSettings, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        core = QGroupBox("Core")
        core_form = QFormLayout(core)
        self.plot_type = _combo(s.plot_type, ("Frequency-Time", "Order-Time", "Frequency-Speed"))
        self.max_order = _double_spin(s.max_order, 0.1, 1e5, decimals=2)
        self.db_on = QCheckBox("dB ON")
        self.db_on.setChecked(s.db_on)
        core_form.addRow("PLOT TYPE", self.plot_type)
        core_form.addRow("MAX ORDER", self.max_order)
        core_form.addRow(self.db_on)
        layout.addWidget(core)

        spectra = QGroupBox("SPECTRA SETTINGS")
        spectra_form = QFormLayout(spectra)
        self.window_type = _combo(s.window_type, WINDOW_TYPES)
        self.bins = _int_spin(s.freq_order_bins, 64, 65536)
        spectra_form.addRow("Window Type", self.window_type)
        spectra_form.addRow("Freq\\Order Bins", self.bins)
        layout.addWidget(spectra)

        time_box = QGroupBox("TIME SEGMENT [s]")
        time_form = QFormLayout(time_box)
        self.time_mode = _combo(s.time_segment_mode, ("SEGMENT PERIOD", "SEGMENT COUNT"))
        self.time_start = _double_spin(s.time_start_s, 0.0, 1e6)
        self.time_end = _double_spin(s.time_end_s, 0.0, 1e6)
        self.time_step = _double_spin(s.time_step_s, 0.001, 1e6, decimals=3)
        time_form.addRow("Mode", self.time_mode)
        time_form.addRow("start [s]", self.time_start)
        time_form.addRow("end [s]", self.time_end)
        time_form.addRow("step size [s]", self.time_step)
        layout.addWidget(time_box)

        speed_box = QGroupBox("SPEED SEGMENT [rpm]")
        speed_form = QFormLayout(speed_box)
        self.speed_start = _double_spin(s.speed_start_rpm, 0.0, 1e6)
        self.speed_end = _double_spin(s.speed_end_rpm, 0.0, 1e6)
        self.speed_step = _double_spin(s.speed_step_rpm, 0.1, 1e6)
        speed_form.addRow("start [rpm]", self.speed_start)
        speed_form.addRow("end [rpm]", self.speed_end)
        speed_form.addRow("step size [rpm]", self.speed_step)
        layout.addWidget(speed_box)

        scaling_box, self.scaling_fields = _spectra_group(s.scaling, title="SCALING")
        layout.addWidget(scaling_box)
        layout.addStretch(1)

    def read(self) -> SpectrogramSettings:
        return SpectrogramSettings(
            plot_type=self.plot_type.currentText(),
            max_order=self.max_order.value(),
            db_on=self.db_on.isChecked(),
            window_type=self.window_type.currentText(),
            freq_order_bins=self.bins.value(),
            time_segment_mode=self.time_mode.currentText(),
            time_start_s=self.time_start.value(),
            time_end_s=self.time_end.value(),
            time_step_s=self.time_step.value(),
            speed_start_rpm=self.speed_start.value(),
            speed_end_rpm=self.speed_end.value(),
            speed_step_rpm=self.speed_step.value(),
            scaling=_read_spectra(self.scaling_fields),
        )


class _OctaveTab(QWidget):
    def __init__(self, s: OctaveSettings, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        avg_box, self.avg_fields = _averaging_group(s.averaging)
        layout.addWidget(avg_box)
        spectra_box, self.spectra_fields = _spectra_group(s.spectra)
        layout.addWidget(spectra_box)
        layout.addStretch(1)

    def read(self) -> OctaveSettings:
        return OctaveSettings(
            averaging=_read_averaging(self.avg_fields),
            spectra=_read_spectra(self.spectra_fields),
        )


# ---------- main dialog -------------------------------------------


class FreqDomainSettingsDialog(QDialog):
    """PLOT SETUP dialog -- one QTabWidget with 7 pages. Roundtrips
    through the FreqDomainSettings dataclass tree; the caller owns
    persistence."""

    def __init__(self, settings: FreqDomainSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PLOT SETUP")
        self.setMinimumSize(520, 640)

        layout = QVBoxLayout(self)
        title = QLabel("PLOT SETUP")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "QLabel { font-family: 'Space Grotesk', sans-serif; font-size: 14px; "
            "letter-spacing: 0.12em; }"
        )
        layout.addWidget(title)

        self._tabs = QTabWidget()
        self._fft_tab = _FftTab(settings.fft)
        self._order_spectrum_tab = _OrderSpectrumTab(settings.order_spectrum)
        self._order_tracking_tab = _OrderTrackingTab(settings.order_tracking)
        self._waterfall_tab = _SpectrogramTab(settings.waterfall)
        self._cascade_tab = _SpectrogramTab(settings.cascade)
        self._colormap_tab = _SpectrogramTab(settings.colormap)
        self._octave_tab = _OctaveTab(settings.octave)

        # Order matches the LabVIEW dialog's tab arrangement.
        self._tabs.addTab(self._fft_tab, "FFT")
        self._tabs.addTab(self._order_spectrum_tab, "Order Spectrum")
        self._tabs.addTab(self._order_tracking_tab, "Order Tracking")
        self._tabs.addTab(self._waterfall_tab, "Waterfall")
        self._tabs.addTab(self._cascade_tab, "Cascade")
        self._tabs.addTab(self._colormap_tab, "Colormap")
        self._tabs.addTab(self._octave_tab, "Octave")
        layout.addWidget(self._tabs, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def current_settings(self) -> FreqDomainSettings:
        return FreqDomainSettings(
            fft=self._fft_tab.read(),
            order_spectrum=self._order_spectrum_tab.read(),
            order_tracking=self._order_tracking_tab.read(),
            waterfall=self._waterfall_tab.read(),
            cascade=self._cascade_tab.read(),
            colormap=self._colormap_tab.read(),
            octave=self._octave_tab.read(),
        )
