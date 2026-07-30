from nvh_qt_app.screens.master_entry import (
    MasterEntryScreen,
    _ThresholdEditor,
    _COL_THRESHOLD_LOW,
    _COL_THRESHOLD_HIGH,
)

from fakes import FakeApiClient

_MODEL = {
    "model_id": "MODEL-A", "model_name": "Nano 4 Speed",
    "drive_teeth": {"R": 12}, "idler_teeth_1": {"R": 36}, "idler_teeth_2": {},
    "layshaft_teeth": {"R": 32}, "drive_shaft_bearing_roll": {}, "layshaft_bearing_roll": {},
    "fdr_teeth": {}, "fd_sel": {}, "ratios": {"R": 3.753},
}

_PARAMETERS = [
    {
        "stat_name": "RMS Avg", "order_number": None,
        "master": {"mean_value": 0.77, "band_min": 0.74, "band_max": 0.81, "full_scale": 10.0, "trial_count": 30},
        "limit_low": 0.74, "limit_high": 0.81, "threshold_low": 0.02, "threshold_high": 0.03,
        "included_in_table_config": True,
    },
    {
        "stat_name": "IN_H1(g)", "order_number": 12.0,
        "master": {"mean_value": 0.97, "band_min": 0.92, "band_max": 1.03, "full_scale": 20.0, "trial_count": 30},
        "limit_low": 0.92, "limit_high": 1.03, "threshold_low": 0.05, "threshold_high": 0.05,
        "included_in_table_config": True,
    },
]


class MasterEntryScreenTests:
    def test_gear_table_populates_from_model_response(self, qapp):
        fake = FakeApiClient({"fetch_model": _MODEL, "fetch_parameters": _PARAMETERS})
        screen = MasterEntryScreen(api_client=fake)

        assert screen._gear_table.rowCount() == 1
        assert screen._gear_table.item(0, 0).text() == "R"
        assert screen._gear_table.item(0, 4).text() == "3.753"

    def test_parameter_table_populates_from_api_response(self, qapp):
        fake = FakeApiClient({"fetch_model": _MODEL, "fetch_parameters": _PARAMETERS})
        screen = MasterEntryScreen(api_client=fake)

        assert screen._param_table.rowCount() == 2
        assert screen._param_table.item(0, 0).text() == "RMS Avg"
        assert screen._param_table.item(1, 1).text() == "12"
        assert "loaded" in screen._status.text()

    def test_threshold_columns_show_editors_with_initial_values(self, qapp):
        fake = FakeApiClient({"fetch_model": _MODEL, "fetch_parameters": _PARAMETERS})
        screen = MasterEntryScreen(api_client=fake)

        low_editor = screen._param_table.cellWidget(0, _COL_THRESHOLD_LOW)
        high_editor = screen._param_table.cellWidget(0, _COL_THRESHOLD_HIGH)
        assert isinstance(low_editor, _ThresholdEditor)
        assert isinstance(high_editor, _ThresholdEditor)
        assert low_editor.text() == "0.02"
        assert high_editor.text() == "0.03"

    def test_editing_threshold_dispatches_patch_and_updates_local_state(self, qapp):
        updated_row = {
            **_PARAMETERS[0],
            "threshold_low": 0.09, "threshold_high": 0.03,
        }
        fake = FakeApiClient({
            "fetch_model": _MODEL, "fetch_parameters": _PARAMETERS,
            "patch_threshold": updated_row,
        })
        screen = MasterEntryScreen(api_client=fake)

        low_editor = screen._param_table.cellWidget(0, _COL_THRESHOLD_LOW)
        low_editor.setText("0.09")
        low_editor.editingFinished.emit()

        assert len(fake.patch_threshold_calls) == 1
        call = fake.patch_threshold_calls[0]
        assert call["stat_name"] == "RMS Avg"
        assert call["threshold_low"] == 0.09
        # The other threshold gets carried through from the cached row
        # so the PATCH body is complete (endpoint requires both fields).
        assert call["threshold_high"] == 0.03
        assert screen._rows_by_stat["RMS Avg"]["threshold_low"] == 0.09
        assert "saved" in screen._status.text()

    def test_editing_threshold_restores_previous_value_on_backend_failure(self, qapp):
        fake = FakeApiClient(
            {"fetch_model": _MODEL, "fetch_parameters": _PARAMETERS},
            fail=frozenset({"patch_threshold"}),
        )
        screen = MasterEntryScreen(api_client=fake)

        low_editor = screen._param_table.cellWidget(0, _COL_THRESHOLD_LOW)
        low_editor.setText("0.09")
        low_editor.editingFinished.emit()

        assert low_editor.text() == "0.02"  # reverted to the pre-edit stored value
        assert "save failed" in screen._status.text()

    def test_shows_error_status_on_backend_failure(self, qapp):
        fake = FakeApiClient({}, fail=frozenset({"fetch_model", "fetch_parameters"}))
        screen = MasterEntryScreen(api_client=fake)

        assert "failed to reach backend" in screen._status.text()
