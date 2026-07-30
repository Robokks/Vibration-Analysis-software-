"""Widget tests for MultiSeriesPlot: buffer growth, series visibility,
cursor enable/disable, autoscale/manual range."""

from nvh_qt_app.widgets.multi_series_plot import MultiSeriesPlot


class MultiSeriesPlotTests:
    def test_push_sample_grows_the_series_buffer(self, qapp):
        plot = MultiSeriesPlot(["RMS", "PEAK"], max_samples=100)
        plot.push_sample("RMS", 1.0)
        plot.push_sample("RMS", 2.0)
        plot.push_sample("PEAK", 5.0)
        assert list(plot.series_config("RMS").buffer) == [1.0, 2.0]
        assert list(plot.series_config("PEAK").buffer) == [5.0]

    def test_push_sample_ignores_unknown_series(self, qapp):
        plot = MultiSeriesPlot(["RMS"], max_samples=100)
        plot.push_sample("NOPE", 999.0)  # no exception
        assert len(plot.series_config("RMS").buffer) == 0

    def test_buffer_is_bounded_by_max_samples(self, qapp):
        plot = MultiSeriesPlot(["X"], max_samples=5)
        for i in range(20):
            plot.push_sample("X", float(i))
        buffer = plot.series_config("X").buffer
        assert len(buffer) == 5
        assert list(buffer) == [15.0, 16.0, 17.0, 18.0, 19.0]

    def test_set_visible_flips_the_series_config(self, qapp):
        plot = MultiSeriesPlot(["A", "B"], max_samples=10)
        assert plot.series_config("A").visible is True
        plot.set_visible("A", False)
        assert plot.series_config("A").visible is False
        plot.set_visible("A", True)
        assert plot.series_config("A").visible is True

    def test_cursor_enable_disable(self, qapp):
        plot = MultiSeriesPlot(["A"], max_samples=10)
        assert plot._cursor_enabled is False
        plot.set_cursor_enabled(True)
        assert plot._cursor_enabled is True
        plot.set_cursor_enabled(False)
        assert plot._cursor_enabled is False
        assert plot._cursor_x is None

    def test_autoscale_range_covers_the_buffer(self, qapp):
        plot = MultiSeriesPlot(["A"], max_samples=100)
        for v in (1.0, 5.0, 3.0, 4.0):
            plot.push_sample("A", v)
        lo, hi = plot.series_config("A").range()
        # 8% headroom above/below.
        assert lo < 1.0 and hi > 5.0

    def test_manual_range_used_when_autoscale_off(self, qapp):
        plot = MultiSeriesPlot(["A"], max_samples=100)
        plot.push_sample("A", 1.0)
        plot.push_sample("A", 5.0)
        cfg = plot.series_config("A")
        cfg.autoscale = False
        cfg.manual_min = -10.0
        cfg.manual_max = 20.0
        lo, hi = cfg.range()
        assert lo == -10.0
        assert hi == 20.0

    def test_clear_empties_every_series(self, qapp):
        plot = MultiSeriesPlot(["A", "B"], max_samples=10)
        plot.push_sample("A", 1.0)
        plot.push_sample("B", 2.0)
        plot.clear()
        assert len(plot.series_config("A").buffer) == 0
        assert len(plot.series_config("B").buffer) == 0
