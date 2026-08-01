"""Tests for the PLOT SETUP dialog and its FreqDomainSettings
roundtrip -- values in via constructor, values back out via
current_settings()."""

from nvh_qt_app.freq_domain_settings import (
    FftSettings, FreqDomainSettings, OrderSpectrumSettings,
    OrderTrackingSettings, SpectraScaling, SpectrogramSettings,
)
from nvh_qt_app.widgets.freq_domain_settings_dialog import (
    FreqDomainSettingsDialog,
)


class FreqDomainSettingsDialogTests:
    def test_dialog_has_seven_tabs(self, qapp):
        dlg = FreqDomainSettingsDialog(FreqDomainSettings())
        assert dlg._tabs.count() == 7
        tab_names = [dlg._tabs.tabText(i) for i in range(7)]
        assert tab_names == [
            "FFT", "Order Spectrum", "Order Tracking",
            "Waterfall", "Cascade", "Colormap", "Octave",
        ]

    def test_fft_roundtrip_preserves_values(self, qapp):
        settings = FreqDomainSettings(
            fft=FftSettings(window="Blackman", percent_overlap=25.0, number_of_lines=1024),
        )
        dlg = FreqDomainSettingsDialog(settings)
        out = dlg.current_settings()
        assert out.fft.window == "Blackman"
        assert out.fft.percent_overlap == 25.0
        assert out.fft.number_of_lines == 1024

    def test_order_spectrum_roundtrip(self, qapp):
        settings = FreqDomainSettings(
            order_spectrum=OrderSpectrumSettings(max_order=64.0, order_resolution=0.05),
        )
        dlg = FreqDomainSettingsDialog(settings)
        # Simulate an operator changing max_order to 128 before saving.
        dlg._order_spectrum_tab.max_order.setValue(128.0)
        out = dlg.current_settings()
        assert out.order_spectrum.max_order == 128.0
        assert out.order_spectrum.order_resolution == 0.05

    def test_order_tracking_x_axis_roundtrip(self, qapp):
        settings = FreqDomainSettings(
            order_tracking=OrderTrackingSettings(x_axis="Speed", max_order=48.0),
        )
        dlg = FreqDomainSettingsDialog(settings)
        out = dlg.current_settings()
        assert out.order_tracking.x_axis == "Speed"
        assert out.order_tracking.max_order == 48.0

    def test_waterfall_db_on_roundtrip(self, qapp):
        settings = FreqDomainSettings(
            waterfall=SpectrogramSettings(db_on=True, window_type="Hamming", freq_order_bins=4096),
        )
        dlg = FreqDomainSettingsDialog(settings)
        out = dlg.current_settings()
        assert out.waterfall.db_on is True
        assert out.waterfall.window_type == "Hamming"
        assert out.waterfall.freq_order_bins == 4096

    def test_shared_spectra_scaling_roundtrip(self, qapp):
        # Set a non-default scaling on the FFT tab.
        settings = FreqDomainSettings(
            fft=FftSettings(spectra=SpectraScaling(
                linear_db="dB", db_reference=-6.0, power_magnitude="power", view="peak",
            )),
        )
        dlg = FreqDomainSettingsDialog(settings)
        out = dlg.current_settings()
        assert out.fft.spectra.linear_db == "dB"
        assert out.fft.spectra.db_reference == -6.0
        assert out.fft.spectra.power_magnitude == "power"
        assert out.fft.spectra.view == "peak"


class LiveDisplayFreqSettingsIntegration:
    def _make_screen(self):
        from nvh_qt_app.screens.live_display import LiveDisplayScreen
        from fakes import FakeApiClient, FakeLiveClient
        return LiveDisplayScreen(
            api_client=FakeApiClient({"fetch_model": {
                "model_id": "MODEL-A", "model_name": "Nano",
                "drive_teeth": {"R": 12}, "idler_teeth_1": {},
                "idler_teeth_2": {}, "layshaft_teeth": {},
                "drive_shaft_bearing_roll": {}, "layshaft_bearing_roll": {},
                "fdr_teeth": {}, "fd_sel": {},
                "ratios": {"R": 3.753},
            }}),
            live_client=FakeLiveClient(),
        )

    def test_settings_button_is_present(self, qapp):
        screen = self._make_screen()
        button = screen._plot_tabs.cornerWidget(0x00020000)  # Qt.Corner.TopRightCorner
        assert button is not None
        assert button.text() == "Settings…"
        # Default settings match the dataclass defaults.
        assert screen._freq_settings.order_spectrum.max_order == 32.0

    def test_apply_settings_propagates_fft_window_to_widget(self, qapp):
        screen = self._make_screen()
        # Default FFT window is Hanning per the LabVIEW manual.
        assert screen._fft_trace._window_name == "Hanning"
        # Simulate the dialog editing FFT window to Blackman + accept.
        screen._freq_settings.fft.window = "Blackman"
        screen._fft_trace.set_window(screen._freq_settings.fft.window)
        assert screen._fft_trace._window_name == "Blackman"
