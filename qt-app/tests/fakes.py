"""Fake ApiClient + LiveClient for widget-level tests -- both call the
same callbacks the real transports do, but synchronously with canned
payloads, no real network/event-loop dependency. Avoids coupling
qt-app's test suite to web-backend existing/being importable, and
avoids needing a live backend in CI."""

from __future__ import annotations

from typing import Any


class FakeApiClient:
    def __init__(self, responses: dict[str, Any] | None = None, fail: frozenset[str] = frozenset()) -> None:
        self._responses = responses or {}
        self._fail = fail
        # Test-visible logs of every PATCH the code under test issued --
        # lets tests assert URL/body without a live server.
        self.patch_threshold_calls: list[dict[str, Any]] = []
        self.patch_limit_calls: list[dict[str, Any]] = []
        self.patch_table_config_calls: list[dict[str, Any]] = []
        self.patch_calibration_calls: list[dict[str, Any]] = []

    def _respond(self, key: str, on_success, on_error) -> None:
        if key in self._fail:
            on_error(f"stubbed failure for {key}")
        else:
            on_success(self._responses[key])

    def fetch_health(self, on_success, on_error) -> None:
        self._respond("fetch_health", on_success, on_error)

    def fetch_models(self, on_success, on_error) -> None:
        self._respond("fetch_models", on_success, on_error)

    def fetch_model(self, model_id, on_success, on_error) -> None:
        self._respond("fetch_model", on_success, on_error)

    def fetch_programs(self, model_id, on_success, on_error) -> None:
        self._respond("fetch_programs", on_success, on_error)

    def fetch_parameters(self, model_id, program_name, gear_label, direction, on_success, on_error, channel_name="vib_a") -> None:
        self._respond("fetch_parameters", on_success, on_error)

    def fetch_test_runs(self, model_id, on_success, on_error) -> None:
        self._respond("fetch_test_runs", on_success, on_error)

    def fetch_test_run(self, test_run_id, on_success, on_error) -> None:
        self._respond("fetch_test_run", on_success, on_error)

    def fetch_consolidated_report(self, dc_id, on_success, on_error, program_name=None) -> None:
        self._respond("fetch_consolidated_report", on_success, on_error)

    def fetch_detailed_report(self, dc_id, on_success, on_error, program_name=None) -> None:
        self._respond("fetch_detailed_report", on_success, on_error)

    def fetch_code_result_report(self, dc_id, on_success, on_error, program_name=None) -> None:
        self._respond("fetch_code_result_report", on_success, on_error)

    def fetch_summary_report(
        self, model_id, gear_label, direction, stat_name, on_success, on_error, program_name=None, channel_name="vib_a"
    ) -> None:
        self._respond("fetch_summary_report", on_success, on_error)

    def patch_threshold(
        self, model_id, program_name, stat_name, gear_label, direction,
        threshold_low, threshold_high, on_success, on_error, channel_name="vib_a",
    ) -> None:
        self.patch_threshold_calls.append({
            "model_id": model_id, "program_name": program_name, "stat_name": stat_name,
            "gear_label": gear_label, "direction": direction, "channel_name": channel_name,
            "threshold_low": threshold_low, "threshold_high": threshold_high,
        })
        if "patch_threshold" in self._fail:
            on_error(f"stubbed failure for patch_threshold")
            return
        response = self._responses.get("patch_threshold")
        if response is None:
            response = {
                "stat_name": stat_name, "order_number": None, "master": None,
                "limit_low": None, "limit_high": None,
                "threshold_low": threshold_low, "threshold_high": threshold_high,
                "included_in_table_config": False,
            }
        on_success(response)

    def patch_limit(
        self, model_id, program_name, stat_name, gear_label, direction,
        limit_low, limit_high, on_success, on_error, channel_name="vib_a",
    ) -> None:
        self.patch_limit_calls.append({
            "model_id": model_id, "program_name": program_name, "stat_name": stat_name,
            "gear_label": gear_label, "direction": direction, "channel_name": channel_name,
            "limit_low": limit_low, "limit_high": limit_high,
        })
        if "patch_limit" in self._fail:
            on_error(f"stubbed failure for patch_limit")
            return
        response = self._responses.get("patch_limit")
        if response is None:
            response = {
                "stat_name": stat_name, "order_number": None, "master": None,
                "limit_low": limit_low, "limit_high": limit_high,
                "threshold_low": None, "threshold_high": None,
                "included_in_table_config": False,
            }
        on_success(response)

    def fetch_calibration(self, model_id, channel_name, on_success, on_error) -> None:
        self._respond("fetch_calibration", on_success, on_error)

    def patch_calibration(self, model_id, channel_name, payload, on_success, on_error) -> None:
        self.patch_calibration_calls.append({
            "model_id": model_id, "channel_name": channel_name, **payload,
        })
        if "patch_calibration" in self._fail:
            on_error("stubbed failure for patch_calibration")
            return
        response = self._responses.get("patch_calibration")
        if response is None:
            response = {"model_id": model_id, "channel_name": channel_name, **payload}
        on_success(response)

    def patch_table_config_parameter(
        self, model_id, program_name, stat_name, gear_label, direction,
        included, on_success, on_error, channel_name="vib_a",
    ) -> None:
        self.patch_table_config_calls.append({
            "model_id": model_id, "program_name": program_name, "stat_name": stat_name,
            "gear_label": gear_label, "direction": direction, "channel_name": channel_name,
            "included": included,
        })
        if "patch_table_config_parameter" in self._fail:
            on_error(f"stubbed failure for patch_table_config_parameter")
            return
        response = self._responses.get("patch_table_config_parameter")
        if response is None:
            response = {
                "stat_name": stat_name, "order_number": None, "master": None,
                "limit_low": None, "limit_high": None,
                "threshold_low": None, "threshold_high": None,
                "included_in_table_config": included,
            }
        on_success(response)


class FakeLiveClient:
    """Stand-in for nvh_qt_app.live_client.LiveClient. Doesn't actually
    open a socket -- start()/stop() just flip a flag, and callers push
    canned payloads directly via emit_event()/emit_status(). Callback
    binding matches the real client's public-attribute style."""

    def __init__(self) -> None:
        self.on_event = lambda _payload: None
        self.on_status = lambda _state, _error: None
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def emit_event(self, payload: dict[str, Any]) -> None:
        self.on_event(payload)

    def emit_status(self, state: str, error: str | None = None) -> None:
        self.on_status(state, error)
