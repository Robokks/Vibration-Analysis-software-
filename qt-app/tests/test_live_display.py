"""Widget-level tests for the rebuilt LiveDisplayScreen: toolbar,
tabs, parameter table, and 9-field bottom status bar. Driven by
FakeLiveClient + FakeApiClient so there's no live backend or WebSocket."""

from nvh_qt_app.screens.live_display import LiveDisplayScreen
from nvh_qt_app.widgets.live_toolbar import _TOOLBAR_ACTIONS

from fakes import FakeApiClient, FakeLiveClient

_PARAMETERS = [
    {
        "stat_name": "RMS Avg", "order_number": None,
        "master": None,
        "limit_low": 0.74, "limit_high": 0.81,
        "threshold_low": 0.0, "threshold_high": 0.0,
        "included_in_table_config": True,
    },
    {
        "stat_name": "IN_H1(g)", "order_number": 12.0,
        "master": None,
        "limit_low": 0.92, "limit_high": 1.03,
        "threshold_low": 0.0, "threshold_high": 0.0,
        "included_in_table_config": False,
    },
]

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
    api = FakeApiClient({"fetch_parameters": _PARAMETERS, "fetch_test_run": _TEST_RUN_DETAIL})
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

    def test_parameter_table_populates_from_api(self, qapp):
        screen, _api, _live = _make_screen()
        assert screen._param_table.rowCount() == len(_PARAMETERS)
        assert screen._param_table.item(0, 0).text() == "RMS Avg"

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

    def test_signal_chunk_updates_raw_and_fft_traces_and_stats(self, qapp):
        screen, _api, live = _make_screen()
        # Long enough to exercise the LiveStatsPanel (needs >=8 samples)
        # and the FftTraceWidget (needs >=32 samples).
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
        # Stats panel should have swapped its em-dashes for real numbers.
        assert screen._stats_panel._labels["rms"].text() != "—"
        assert screen._stats_panel._labels["peak"].text() != "—"

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
