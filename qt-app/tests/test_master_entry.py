from nvh_qt_app.screens.master_entry import (
    MasterEntryScreen,
    _InTableToggle,
    _NumericEditor,
    _COL_IN_TABLE,
    _COL_LIMIT_LOW,
    _COL_LIMIT_HIGH,
    _COL_THRESHOLD_LOW,
    _COL_THRESHOLD_HIGH,
)

from fakes import FakeApiClient

_MODELS = [{"model_id": "MODEL-A", "model_name": "Nano 4 Speed"}]

_MODEL = {
    "model_id": "MODEL-A", "model_name": "Nano 4 Speed",
    "drive_teeth": {"R": 12}, "idler_teeth_1": {"R": 36}, "idler_teeth_2": {},
    "layshaft_teeth": {"R": 32}, "drive_shaft_bearing_roll": {}, "layshaft_bearing_roll": {},
    "fdr_teeth": {}, "fd_sel": {}, "ratios": {"R": 3.753},
}

_PROGRAMS = [{"program_name": "P1"}]

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


def _fake(fail: frozenset[str] = frozenset()) -> FakeApiClient:
    """FakeApiClient primed with the full cascade responses -- fetch_models,
    fetch_model, fetch_programs, fetch_parameters -- so the screen boots
    through the model/program/gear selectors and lands on populated tables."""
    return FakeApiClient(
        {
            "fetch_models": _MODELS,
            "fetch_model": _MODEL,
            "fetch_programs": _PROGRAMS,
            "fetch_parameters": _PARAMETERS,
        },
        fail=fail,
    )


class MasterEntryScreenTests:
    def test_gear_table_populates_from_model_response(self, qapp):
        fake = _fake()
        screen = MasterEntryScreen(api_client=fake)

        assert screen._gear_table.rowCount() == 1
        assert screen._gear_table.item(0, 0).text() == "R"
        assert screen._gear_table.item(0, 4).text() == "3.753"

    def test_parameter_table_populates_from_api_response(self, qapp):
        fake = _fake()
        screen = MasterEntryScreen(api_client=fake)

        assert screen._param_table.rowCount() == 2
        assert screen._param_table.item(0, 0).text() == "RMS Avg"
        assert screen._param_table.item(1, 1).text() == "12"
        assert "loaded" in screen._status.text()

    def test_all_four_numeric_columns_are_editable(self, qapp):
        fake = _fake()
        screen = MasterEntryScreen(api_client=fake)

        for col in (_COL_LIMIT_LOW, _COL_LIMIT_HIGH, _COL_THRESHOLD_LOW, _COL_THRESHOLD_HIGH):
            editor = screen._param_table.cellWidget(0, col)
            assert isinstance(editor, _NumericEditor)
        assert screen._param_table.cellWidget(0, _COL_LIMIT_LOW).text() == "0.74"
        assert screen._param_table.cellWidget(0, _COL_THRESHOLD_LOW).text() == "0.02"

    def test_editing_threshold_dispatches_patch_threshold(self, qapp):
        fake = _fake()
        screen = MasterEntryScreen(api_client=fake)

        editor = screen._param_table.cellWidget(0, _COL_THRESHOLD_LOW)
        editor.setText("0.09")
        editor.editingFinished.emit()

        assert len(fake.patch_threshold_calls) == 1
        assert fake.patch_limit_calls == []
        call = fake.patch_threshold_calls[0]
        assert call["stat_name"] == "RMS Avg"
        assert call["threshold_low"] == 0.09
        assert call["threshold_high"] == 0.03  # carried through from cached row
        assert screen._rows_by_stat["RMS Avg"]["threshold_low"] == 0.09

    def test_editing_limit_dispatches_patch_limit(self, qapp):
        fake = _fake()
        screen = MasterEntryScreen(api_client=fake)

        editor = screen._param_table.cellWidget(0, _COL_LIMIT_HIGH)
        editor.setText("0.95")
        editor.editingFinished.emit()

        assert len(fake.patch_limit_calls) == 1
        assert fake.patch_threshold_calls == []
        call = fake.patch_limit_calls[0]
        assert call["stat_name"] == "RMS Avg"
        assert call["limit_high"] == 0.95
        assert call["limit_low"] == 0.74  # carried through from cached row
        assert screen._rows_by_stat["RMS Avg"]["limit_high"] == 0.95

    def test_editing_numeric_reverts_on_backend_failure(self, qapp):
        fake = _fake(fail=frozenset({"patch_limit"}))
        screen = MasterEntryScreen(api_client=fake)

        editor = screen._param_table.cellWidget(0, _COL_LIMIT_HIGH)
        editor.setText("0.95")
        editor.editingFinished.emit()

        assert editor.text() == "0.81"  # reverted to the pre-edit stored value
        assert "save failed" in screen._status.text()

    def test_in_table_toggle_dispatches_patch(self, qapp):
        fake = _fake()
        screen = MasterEntryScreen(api_client=fake)

        button = screen._param_table.cellWidget(0, _COL_IN_TABLE)
        assert isinstance(button, _InTableToggle)
        assert button.text() == "yes"

        # Simulate a real user click: toggle checked state, then fire clicked.
        button.setChecked(False)
        button.clicked.emit()

        assert len(fake.patch_table_config_calls) == 1
        call = fake.patch_table_config_calls[0]
        assert call["stat_name"] == "RMS Avg"
        assert call["included"] is False
        assert screen._rows_by_stat["RMS Avg"]["included_in_table_config"] is False
        assert button.text() == "no"

    def test_in_table_toggle_reverts_on_backend_failure(self, qapp):
        fake = _fake(fail=frozenset({"patch_table_config_parameter"}))
        screen = MasterEntryScreen(api_client=fake)

        button = screen._param_table.cellWidget(0, _COL_IN_TABLE)
        button.setChecked(False)
        button.clicked.emit()

        assert button.text() == "yes"  # reverted from the failed toggle
        assert "save failed" in screen._status.text()

    def test_shows_error_status_on_backend_failure(self, qapp):
        # Failing the very first cascade call surfaces the error banner --
        # every downstream call is short-circuited by _on_error setting
        # the status text.
        fake = FakeApiClient({}, fail=frozenset({"fetch_models"}))
        screen = MasterEntryScreen(api_client=fake)

        assert "failed to reach backend" in screen._status.text()

    def test_add_gear_button_posts_full_model_update(self, qapp):
        """The Add gear dialog must send a *full* ModelUpdate body (all 10
        fields), mutating only the four gear-scoped dicts. The plan calls
        this out explicitly."""
        from nvh_qt_app.screens.master_entry import _GearDialog

        put_calls: list[dict] = []

        class RecordingApi(FakeApiClient):
            def put_model(inner_self, model_id, body, on_success, on_error):
                put_calls.append({"model_id": model_id, "body": body})
                # Echo an updated model back so _on_gear_saved re-renders.
                on_success({**_MODEL, "ratios": {**_MODEL["ratios"], "II": 2.1}})

        fake = RecordingApi(
            {
                "fetch_models": _MODELS,
                "fetch_model": _MODEL,
                "fetch_programs": _PROGRAMS,
                "fetch_parameters": _PARAMETERS,
            }
        )
        screen = MasterEntryScreen(api_client=fake)

        dlg = _GearDialog(
            "add", screen._current_model, None, screen._model_id,
            fake, screen._on_gear_saved, screen._status, screen,
        )
        dlg._gear_label_edit.setText("II")
        dlg._drive_edit.setText("14")
        dlg._idler_edit.setText("42")
        dlg._layshaft_edit.setText("30")
        dlg._ratio_edit.setText("2.1")
        dlg._on_ok()

        assert len(put_calls) == 1
        body = put_calls[0]["body"]
        # Every ModelUpdate field must be present -- backend rejects partial.
        for key in (
            "model_name", "drive_teeth", "idler_teeth_1", "idler_teeth_2",
            "layshaft_teeth", "drive_shaft_bearing_roll",
            "layshaft_bearing_roll", "fdr_teeth", "fd_sel", "ratios",
        ):
            assert key in body, f"missing {key} from ModelUpdate body"
        # New gear was merged in without dropping the existing one.
        assert body["drive_teeth"]["II"] == 14
        assert body["drive_teeth"]["R"] == 12
        assert body["ratios"]["II"] == 2.1
