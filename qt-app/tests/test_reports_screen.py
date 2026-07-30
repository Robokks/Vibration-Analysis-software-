from nvh_qt_app.screens.reports import ReportsScreen

from fakes import FakeApiClient

_TEST_RUNS = [
    {"test_run_id": "run-1", "model_id": "MODEL-A", "serial_number": "DEMO-HEALTHY-UNIT", "overall_result": "PASS"},
]

_TEST_RUN_DETAIL = {
    "test_run": _TEST_RUNS[0],
    "dc_records": [{"dc_id": "dc-1", "gear_label": "R", "direction": "RU", "result": "PASS", "fail_reason_codes": []}],
}

_CONSOLIDATED = {
    "stamp": "PASS",
    "result": {
        "gear_label": "R", "direction": "RU",
        "crash_noise": {"peak_band_rms": 0.47, "threshold": 0.5, "detected": False},
        "slippage": {"min_ratio": 0.0002, "dropout_fraction": 0.0, "detected": False},
        "order_spectrum": {"order": [0, 1, 2, 3, 4], "magnitude": [0.1, 0.5, 0.3, 0.2, 0.1]},
        "order_tracking": {"time_s": [0, 0.1, 0.2, 0.3], "magnitude": [0.4, 0.5, 0.6, 0.7]},
        "fail_reason_codes": [], "passed": True,
    },
}

_DETAILED = {
    "numeric_table": [
        {
            "stat_name": "RMS Avg", "domain": "time", "observed_value": 0.803,
            "master": {"mean_value": 0.77, "band_min": 0.74, "band_max": 0.81, "full_scale": 10.0, "trial_count": 30},
            "grading": {"g_level": 6, "ok_flag": True, "low": 0.74, "high": 0.81},
        },
    ]
}

_SUMMARY = {
    "stat_name": "RMS Avg", "gear_label": "R", "direction": "RU",
    "rows": [{"test_run": _TEST_RUNS[0]}],
    "xchart": {"center_line": 0.91, "ucl": 2.18, "lcl": -0.36, "values": [0.80], "out_of_control_indices": []},
    "histogram": {"bin_edges": [], "counts": [], "normal_pdf_x": [], "normal_pdf_y": []},
}

_CODE_RESULT = {
    "rows": [
        {
            "step": 1, "gear_direction": "R_RU", "channel_name": "vib_a", "parameter": "RMS Avg",
            "orders": None, "low": 0.74, "actual": 0.80, "high": 0.81, "unit": "g", "ok_flag": True,
        },
    ]
}

_RESPONSES = {
    "fetch_test_runs": _TEST_RUNS,
    "fetch_test_run": _TEST_RUN_DETAIL,
    "fetch_consolidated_report": _CONSOLIDATED,
    "fetch_detailed_report": _DETAILED,
    "fetch_summary_report": _SUMMARY,
    "fetch_code_result_report": _CODE_RESULT,
}


class ReportsScreenTests:
    def test_test_run_combo_populates_and_auto_selects_first_run(self, qapp):
        fake = FakeApiClient(_RESPONSES)
        screen = ReportsScreen(api_client=fake)

        assert screen._run_combo.count() == 1
        assert "DEMO-HEALTHY-UNIT" in screen._run_combo.currentText()

    def test_consolidated_tab_shows_real_stamp_and_detail(self, qapp):
        fake = FakeApiClient(_RESPONSES)
        screen = ReportsScreen(api_client=fake)

        assert screen._consolidated_stamp is not None
        assert "gear R / RU" in screen._consolidated_detail.text()

    def test_detailed_tab_populates_table(self, qapp):
        fake = FakeApiClient(_RESPONSES)
        screen = ReportsScreen(api_client=fake)

        assert screen._detailed_table.rowCount() == 1
        assert screen._detailed_table.item(0, 0).text() == "RMS Avg"

    def test_code_result_tab_populates_table(self, qapp):
        fake = FakeApiClient(_RESPONSES)
        screen = ReportsScreen(api_client=fake)

        assert screen._code_result_table.rowCount() == 1
        assert screen._code_result_table.item(0, 1).text() == "R_RU"
        assert screen._code_result_table.item(0, 9).text() == "OK"

    def test_consolidated_tab_populates_order_plots(self, qapp):
        fake = FakeApiClient(_RESPONSES)
        screen = ReportsScreen(api_client=fake)

        spec = screen._order_spectrum_plot.series_config("Order magnitude")
        track = screen._order_tracking_plot.series_config("Order tracking")
        assert list(spec.buffer) == [0.1, 0.5, 0.3, 0.2, 0.1]
        assert list(track.buffer) == [0.4, 0.5, 0.6, 0.7]

    def test_summary_tab_populates_xchart_and_reference_lines(self, qapp):
        fake = FakeApiClient(_RESPONSES)
        screen = ReportsScreen(api_client=fake)

        cfg = screen._xchart_plot.series_config("RMS Avg")
        assert list(cfg.buffer) == [0.80]
        # Reference lines carry CL / UCL / LCL in that order.
        lines = dict((label, y) for y, label in cfg.reference_lines)
        assert lines["CL"] == 0.91
        assert lines["UCL"] == 2.18
        assert lines["LCL"] == -0.36
        assert "CL 0.91" in screen._summary_meta.text() or "0.91" in screen._summary_meta.text()

    def test_shows_error_status_on_backend_failure(self, qapp):
        fake = FakeApiClient({}, fail=frozenset({"fetch_test_runs"}))
        screen = ReportsScreen(api_client=fake)

        assert "failed to reach backend" in screen._status.text()
