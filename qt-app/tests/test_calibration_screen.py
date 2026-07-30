"""CalibrationScreen widget tests: form is filled from the fetch,
Save dispatches the PATCH with the current field values."""

from nvh_qt_app.screens.calibration import CalibrationScreen

from fakes import FakeApiClient

_CALIBRATION = {
    "model_id": "MODEL-A", "channel_name": "vib_a",
    "sensor_sensitivity_mv_per_eu": 100.0,
    "engineering_units": "g",
    "db_reference_eu": 1.0,
    "custom_label": "EU",
    "weighting_filter": "A",
    "pregain_db": 6.0,
    "last_calibrated_at": "2026-07-30T00:00:00Z",
    "due_at": "2027-07-30",
}


class CalibrationScreenTests:
    def test_form_populates_from_api_response(self, qapp):
        fake = FakeApiClient({"fetch_calibration": _CALIBRATION})
        screen = CalibrationScreen(api_client=fake)

        assert screen._sensitivity.value() == 100.0
        assert screen._engineering_units.currentText() == "g"
        assert screen._weighting_filter.currentText() == "A"
        assert screen._pregain.value() == 6.0
        assert "loaded" in screen._status.text()

    def test_save_dispatches_patch_with_form_values(self, qapp):
        fake = FakeApiClient({"fetch_calibration": _CALIBRATION})
        screen = CalibrationScreen(api_client=fake)

        # Tweak the pregain then save.
        screen._pregain.setValue(12.0)
        screen._save_button.click()

        assert len(fake.patch_calibration_calls) == 1
        call = fake.patch_calibration_calls[0]
        assert call["pregain_db"] == 12.0
        assert call["engineering_units"] == "g"
        assert call["last_calibrated_at"]  # non-empty ISO timestamp
        assert call["due_at"]  # YYYY-MM-DD

    def test_save_failure_re_enables_button_and_shows_error(self, qapp):
        fake = FakeApiClient(
            {"fetch_calibration": _CALIBRATION},
            fail=frozenset({"patch_calibration"}),
        )
        screen = CalibrationScreen(api_client=fake)
        screen._save_button.click()

        assert screen._save_button.isEnabled()
        assert "save failed" in screen._status.text()
