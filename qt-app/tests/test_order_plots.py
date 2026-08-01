"""Widget-level smoke tests for OrderSpectrumPlot + OrderTrackingPlot
-- setters accept the expected shapes and repainting doesn't crash."""

from nvh_qt_app.widgets.order_plots import OrderSpectrumPlot, OrderTrackingPlot


class OrderSpectrumPlotTests:
    def test_set_speed_and_spectrum(self, qapp):
        plot = OrderSpectrumPlot()
        plot.set_speed_over_time([1000.0, 1500.0, 2000.0, 2500.0])
        plot.set_spectrum([0.1, 0.5, 0.2, 0.7, 0.1])
        assert list(plot._speed_plot.series_config("SPEED").buffer) == [1000.0, 1500.0, 2000.0, 2500.0]
        assert len(plot._spectrum_plot.series_config("Magnitude").buffer) == 5

    def test_set_peaks_populates_table(self, qapp):
        plot = OrderSpectrumPlot()
        plot.set_peaks([(12.0, 0.5), (24.0, 0.3), (36.0, 0.1)])
        assert plot._peaks_table.rowCount() == 3
        assert plot._peaks_table.item(0, 0).text() == "12.00"

    def test_clear_wipes_state(self, qapp):
        plot = OrderSpectrumPlot()
        plot.set_speed_over_time([1000.0, 2000.0])
        plot.set_spectrum([0.1, 0.2])
        plot.set_peaks([(1.0, 0.5)])
        plot.clear()
        assert len(plot._speed_plot.series_config("SPEED").buffer) == 0
        assert plot._peaks_table.rowCount() == 0


class OrderTrackingPlotTests:
    def test_multiple_series_data_pushes(self, qapp):
        plot = OrderTrackingPlot(["OVERALL", "12", "24"])
        plot.set_series_data("OVERALL", [1.0, 2.0, 3.0])
        plot.set_series_data("12", [0.1, 0.2, 0.3])
        plot.set_series_data("24", [0.05, 0.10, 0.15])
        assert list(plot._plot.series_config("OVERALL").buffer) == [1.0, 2.0, 3.0]
        assert list(plot._plot.series_config("12").buffer) == [0.1, 0.2, 0.3]

    def test_expected_orders_populates_table(self, qapp):
        plot = OrderTrackingPlot(["OVERALL", "12"])
        plot.set_expected_orders([("12", 12.0), ("24", 24.0)])
        assert plot._expected_table.rowCount() == 2
        assert plot._expected_table.item(0, 0).text() == "12"
        assert plot._expected_table.item(1, 1).text() == "24.00"
