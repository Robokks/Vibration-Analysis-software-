"""A fake ApiClient for widget-level tests -- calls on_success/on_error
synchronously with canned payloads, no real network/event-loop dependency.
Avoids coupling qt-app's test suite to web-backend existing/being
importable, and avoids needing a live backend in CI."""

from __future__ import annotations

from typing import Any


class FakeApiClient:
    def __init__(self, responses: dict[str, Any] | None = None, fail: frozenset[str] = frozenset()) -> None:
        self._responses = responses or {}
        self._fail = fail

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
