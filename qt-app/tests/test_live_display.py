"""Widget-level tests for the rebuilt LiveDisplayScreen: toolbar,
tabs, (gear x direction) results grid, and 9-field bottom status bar.
Driven by FakeLiveClient + FakeApiClient so there's no live backend or
WebSocket."""

from nvh_qt_app.screens.live_display import LiveDisplayScreen
from nvh_qt_app.widgets.live_toolbar import _TOOLBAR_ACTIONS

from fakes import FakeApiClient, FakeLiveClient

_MODEL = {
    "model_id": "MODEL-A", "model_name": "Nano 4 Speed",
    "drive_teeth": {"R": 12, "I": 24}, "idler_teeth_1": {},
    "idler_teeth_2": {}, "layshaft_teeth": {},
    "drive_shaft_bearing_roll": {}, "layshaft_bearing_roll": {},
    "fdr_teeth": {}, "fd_sel": {},
    # Two gears so we get 4 rows (I_RU / I_RD / R_RU / R_RD after sort).
    "ratios": {"R": 3.753, "I": 2.5},
}

_TEST_RUN_DETAIL = {
    "test_run": {
        "test_run_id": "run-42", "model_id": "MODEL-A",
        "serial_number": "SN-9001", "operator_id": "alice",
        "shift_number": "A", "repeat_number": 3,
        "line_id": "LINE1", "station_id": "STATION-1",
        "started_at": "2026-07-30T09:00:00Z", "finished_at": None,
        "overall_result": "PENDING",
    },
    "dc_records": [],
}


def _make_screen():
    api = FakeApiClient({"fetch_model": _MODEL, "fetch_test_run": _TEST_RUN_DETAIL})
    live = FakeLiveClient()
    screen = LiveDisplayScreen(live_client=live, api_client=api)
    return screen, api, live


class LiveDisplayScreenTests:
    def test_toolbar_has_all_nine_action_buttons(self, qapp):
        screen, _api, _live = _make_screen()
        for name, _label in _TOOLBAR_ACTIONS:
            assert screen._toolbar.button(name) is not None

    def test_toolbar_click_shows_action_in_status_label(self, qapp):
        screen, _api, _live = _make_screen()
        screen._toolbar.button("master").click()
        assert "master" in screen._status_label.text()

    def test_plot_tabs_have_both_time_series_and_frequency_domain(self, qapp):
        screen, _api, _live = _make_screen()
        assert screen._plot_tabs.count() == 2
        assert screen._plot_tabs.tabText(0) == "Time series"
        assert screen._plot_tabs.tabText(1) == "Frequency domain"

    def test_results_grid_seeds_one_row_per_gear_direction_pair(self, qapp):
        screen, _api, _live = _make_screen()
        # Model has R + I -> sorted: I, R -> 4 rows (I_RU, I_RD, R_RU, R_RD).
        assert screen._results_table.rowCount() == 4
        gear_ids = [screen._results_table.item(r, 0).text() for r in range(4)]
        assert gear_ids == ["I_RU", "I_RD", "R_RU", "R_RD"]

    def test_dc_event_colors_the_matching_result_cell(self, qapp):
        screen, _api, live = _make_screen()
        live.emit_event({
            "type": "dc", "dc_id": "d1", "test_run_id": "run-42",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "stamp": "PASS", "fail_reason_codes": [],
        })
        r_ru_row = next(
            r for r in range(screen._results_table.rowCount())
            if screen._results_table.item(r, 0).text() == "R_RU"
        )
        cell = screen._results_table.item(r_ru_row, 1)
        assert cell.background().color().name().lower() == screen._pass.lower()

    def test_test_run_event_fetches_detail_and_fills_status_bar(self, qapp):
        screen, _api, live = _make_screen()
        live.emit_event({
            "type": "test_run", "test_run_id": "run-42",
            "station_id": "STATION-1", "status": "RUNNING",
            "overall_result": None,
        })
        # Status bar should now carry the fields the fetch_test_run
        # response filled in.
        assert screen._status_bar.field_text("operator") == "alice"
        assert screen._status_bar.field_text("shift") == "A"
        assert screen._status_bar.field_text("serial") == "SN-9001"
        assert screen._status_bar.field_text("repeat") == "3"
        assert screen._status_bar.field_text("status") == "RUNNING"

    def test_dc_event_updates_gear_nvh_id_result(self, qapp):
        screen, _api, live = _make_screen()
        live.emit_event({
            "type": "dc", "dc_id": "d1", "test_run_id": "run-42",
            "station_id": "STATION-1", "gear_label": "R", "direction": "STYC",
            "stamp": "PASS", "fail_reason_codes": [],
        })
        assert screen._status_bar.field_text("gear_id") == "R"
        assert screen._status_bar.field_text("nvh_id") == "2"  # STYC -> 2
        assert screen._status_bar.field_text("result") == "PASS"

    def test_signal_chunk_updates_raw_fft_and_computed_plot(self, qapp):
        screen, _api, live = _make_screen()
        # Long enough to exercise the stat computation (needs >=8) and
        # the FftTraceWidget (>=32).
        values = [0.5 * ((-1) ** i) for i in range(64)]
        live.emit_event({
            "type": "signal_chunk", "test_run_id": "run-42", "dc_id": "d1",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "channel_name": "vib_a", "sample_rate_hz": 5000.0,
            "chunk_index": 0, "time_s": list(range(64)),
            "values": values, "rpm": [1000.0] * 64,
        })
        assert len(screen._raw_trace._buffer) == 64
        assert len(screen._fft_trace._buffer) == 64
        # Each of the 8 computed series should have one sample after
        # one chunk.
        for name in ("SPEED", "CREST", "PEAK", "RMS", "KURTOSIS", "SKEWNESS", "VARIANCE", "MEAN"):
            assert len(screen._computed_plot.series_config(name).buffer) == 1
        # RMS of ±0.5 sample is 0.5; peak is 0.5; crest ~= 1.
        assert abs(screen._computed_plot.series_config("RMS").buffer[0] - 0.5) < 1e-6
        assert abs(screen._computed_plot.series_config("PEAK").buffer[0] - 0.5) < 1e-6
        assert abs(screen._computed_plot.series_config("SPEED").buffer[0] - 1000.0) < 1e-6

    def test_signal_chunk_populates_live_rms_and_peak_cells(self, qapp):
        screen, _api, live = _make_screen()
        values = [0.5 * ((-1) ** i) for i in range(64)]  # RMS = 0.5, peak = 0.5
        live.emit_event({
            "type": "signal_chunk", "test_run_id": "r", "dc_id": "d",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "channel_name": "vib_a", "sample_rate_hz": 5000.0,
            "chunk_index": 0, "time_s": list(range(64)),
            "values": values, "rpm": [1000.0] * 64,
        })
        # The (R, RU) row should now show 0.500 in the RMS max column.
        row = screen._row_index[("R", "RU")]
        assert screen._results_table.item(row, 2).text() == "0.500"
        # Second chunk with smaller values should NOT lower the running max.
        smaller = [0.1] * 64
        live.emit_event({
            "type": "signal_chunk", "test_run_id": "r", "dc_id": "d",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "channel_name": "vib_a", "sample_rate_hz": 5000.0,
            "chunk_index": 1, "time_s": list(range(64)),
            "values": smaller, "rpm": [1000.0] * 64,
        })
        assert screen._results_table.item(row, 2).text() == "0.500"

    def test_row_stats_reset_on_new_dc(self, qapp):
        # Phase O Bug 2: _row_stats used to latch to lifetime max because
        # nothing ever cleared it. After a dc event closes one run, the
        # next run must start from zero, not inherit the previous run's
        # running peak.
        screen, _api, live = _make_screen()
        row = screen._row_index[("R", "RU")]

        # Run 1: high peaks -> 0.5 RMS max shown.
        live.emit_event({
            "type": "signal_chunk", "test_run_id": "r1", "dc_id": "d1",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "channel_name": "vib_a", "sample_rate_hz": 5000.0,
            "chunk_index": 0, "time_s": list(range(64)),
            "values": [0.5 * ((-1) ** i) for i in range(64)], "rpm": [1000.0] * 64,
        })
        assert screen._results_table.item(row, 2).text() == "0.500"

        # DC arrives (PASS) -- closes the run and must reset the stats.
        live.emit_event({
            "type": "dc", "dc_id": "d1", "test_run_id": "r1",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "stamp": "PASS", "fail_reason_codes": [],
        })

        # Run 2: much lower peaks. The cell must show the new run's RMS
        # (0.100), NOT the previous run's max (0.500).
        live.emit_event({
            "type": "signal_chunk", "test_run_id": "r2", "dc_id": "d2",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "channel_name": "vib_a", "sample_rate_hz": 5000.0,
            "chunk_index": 0, "time_s": list(range(64)),
            "values": [0.1] * 64, "rpm": [1000.0] * 64,
        })
        assert screen._results_table.item(row, 2).text() == "0.100"

    def test_running_test_run_clears_previous_traces(self, qapp):
        screen, _api, live = _make_screen()
        live.emit_event({
            "type": "signal_chunk", "test_run_id": "r0", "dc_id": "d0",
            "station_id": "STATION-1", "gear_label": "R", "direction": "RU",
            "channel_name": "vib_a", "sample_rate_hz": 5000.0,
            "chunk_index": 0, "time_s": [0], "values": [0.1] * 50, "rpm": [1000.0] * 50,
        })
        assert len(screen._raw_trace._buffer) == 50
        live.emit_event({
            "type": "test_run", "test_run_id": "r1",
            "station_id": "STATION-1", "status": "RUNNING",
            "overall_result": None,
        })
        assert len(screen._raw_trace._buffer) == 0
        assert len(screen._fft_trace._buffer) == 0
