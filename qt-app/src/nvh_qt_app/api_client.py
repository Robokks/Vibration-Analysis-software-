"""Thin async HTTP client over the nvh-web-backend FastAPI service, built on
QNetworkAccessManager (PySide6's own async-native networking, already
shipped inside the PySide6 dependency -- no httpx/QThread needed) so
requests never block the UI event loop. Mirrors the exact API contract
wired into the sibling web-frontend client verbatim -- field names here are
load-bearing, not renamed.

Every fetch_* method takes plain on_success/on_error callables rather than
exposing QNetworkReply directly -- callers don't need Qt networking
boilerplate, and each screen only fires a handful of known requests at
fixed lifecycle points, so a closure callback keeps call sites to one line
without needing a bespoke QObject-derived signal class per request."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote, urlencode

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

OnSuccess = Callable[[Any], None]
OnError = Callable[[str], None]


class ApiClient:
    """One QNetworkAccessManager per client instance -- meant to be reused
    across requests, not recreated per call (it holds the connection
    cache)."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")
        self._manager = QNetworkAccessManager()
        # Keep references to in-flight replies so they aren't garbage
        # collected before `finished` fires.
        self._in_flight: set[QNetworkReply] = set()

    def _get(self, path: str, on_success: OnSuccess, on_error: OnError, params: dict[str, str] | None = None) -> None:
        query = f"?{urlencode(params)}" if params else ""
        request = QNetworkRequest(QUrl(f"{self._base_url}{path}{query}"))
        reply = self._manager.get(request)
        self._track(reply, on_success, on_error)

    def _patch(
        self,
        path: str,
        body: dict[str, Any],
        on_success: OnSuccess,
        on_error: OnError,
        params: dict[str, str] | None = None,
    ) -> None:
        query = f"?{urlencode(params)}" if params else ""
        request = QNetworkRequest(QUrl(f"{self._base_url}{path}{query}"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        # QNAM has no dedicated .patch() on older PySide builds -- sendCustomRequest
        # is the documented cross-version escape hatch.
        reply = self._manager.sendCustomRequest(request, b"PATCH", json.dumps(body).encode("utf-8"))
        self._track(reply, on_success, on_error)

    def _track(self, reply: QNetworkReply, on_success: OnSuccess, on_error: OnError) -> None:
        self._in_flight.add(reply)

        def _handle() -> None:
            self._in_flight.discard(reply)
            reply.deleteLater()
            if reply.error() != QNetworkReply.NetworkError.NoError:
                on_error(reply.errorString())
                return
            try:
                payload = json.loads(bytes(reply.readAll().data()))
            except json.JSONDecodeError as exc:
                on_error(f"invalid JSON from backend: {exc}")
                return
            on_success(payload)

        reply.finished.connect(_handle)

    # --- endpoints, one method per contract line ---------------------

    def fetch_health(self, on_success: OnSuccess, on_error: OnError) -> None:
        self._get("/health", on_success, on_error)

    def fetch_models(self, on_success: OnSuccess, on_error: OnError) -> None:
        self._get("/models", on_success, on_error)

    def fetch_model(self, model_id: str, on_success: OnSuccess, on_error: OnError) -> None:
        self._get(f"/models/{quote(model_id)}", on_success, on_error)

    def fetch_programs(self, model_id: str, on_success: OnSuccess, on_error: OnError) -> None:
        self._get(f"/models/{quote(model_id)}/programs", on_success, on_error)

    def fetch_parameters(
        self,
        model_id: str,
        program_name: str,
        gear_label: str,
        direction: str,
        on_success: OnSuccess,
        on_error: OnError,
        channel_name: str = "vib_a",
    ) -> None:
        path = f"/models/{quote(model_id)}/programs/{quote(program_name)}/parameters"
        self._get(path, on_success, on_error, {"gear_label": gear_label, "direction": direction, "channel_name": channel_name})

    def fetch_test_runs(self, model_id: str, on_success: OnSuccess, on_error: OnError) -> None:
        self._get("/test-runs", on_success, on_error, {"model_id": model_id})

    def fetch_test_run(self, test_run_id: str, on_success: OnSuccess, on_error: OnError) -> None:
        self._get(f"/test-runs/{quote(test_run_id)}", on_success, on_error)

    def fetch_consolidated_report(
        self, dc_id: str, on_success: OnSuccess, on_error: OnError, program_name: str | None = None
    ) -> None:
        params = {"program_name": program_name} if program_name else None
        self._get(f"/dc-records/{quote(dc_id)}/reports/consolidated", on_success, on_error, params)

    def fetch_detailed_report(
        self, dc_id: str, on_success: OnSuccess, on_error: OnError, program_name: str | None = None
    ) -> None:
        params = {"program_name": program_name} if program_name else None
        self._get(f"/dc-records/{quote(dc_id)}/reports/detailed", on_success, on_error, params)

    def fetch_code_result_report(
        self, dc_id: str, on_success: OnSuccess, on_error: OnError, program_name: str | None = None
    ) -> None:
        params = {"program_name": program_name} if program_name else None
        self._get(f"/dc-records/{quote(dc_id)}/reports/code-result", on_success, on_error, params)

    def fetch_summary_report(
        self,
        model_id: str,
        gear_label: str,
        direction: str,
        stat_name: str,
        on_success: OnSuccess,
        on_error: OnError,
        program_name: str | None = None,
        channel_name: str = "vib_a",
    ) -> None:
        params = {"gear_label": gear_label, "direction": direction, "stat_name": stat_name, "channel_name": channel_name}
        if program_name:
            params["program_name"] = program_name
        self._get(f"/models/{quote(model_id)}/summary", on_success, on_error, params)

    def patch_threshold(
        self,
        model_id: str,
        program_name: str,
        stat_name: str,
        gear_label: str,
        direction: str,
        threshold_low: float,
        threshold_high: float,
        on_success: OnSuccess,
        on_error: OnError,
        channel_name: str = "vib_a",
    ) -> None:
        path = (
            f"/models/{quote(model_id)}/programs/{quote(program_name)}"
            f"/limit-configs/{quote(stat_name)}/threshold"
        )
        params = {"gear_label": gear_label, "direction": direction, "channel_name": channel_name}
        body = {"threshold_low": threshold_low, "threshold_high": threshold_high}
        self._patch(path, body, on_success, on_error, params)

    def patch_limit(
        self,
        model_id: str,
        program_name: str,
        stat_name: str,
        gear_label: str,
        direction: str,
        limit_low: float,
        limit_high: float,
        on_success: OnSuccess,
        on_error: OnError,
        channel_name: str = "vib_a",
    ) -> None:
        path = (
            f"/models/{quote(model_id)}/programs/{quote(program_name)}"
            f"/limit-configs/{quote(stat_name)}/limit"
        )
        params = {"gear_label": gear_label, "direction": direction, "channel_name": channel_name}
        body = {"limit_low": limit_low, "limit_high": limit_high}
        self._patch(path, body, on_success, on_error, params)

    def patch_table_config_parameter(
        self,
        model_id: str,
        program_name: str,
        stat_name: str,
        gear_label: str,
        direction: str,
        included: bool,
        on_success: OnSuccess,
        on_error: OnError,
        channel_name: str = "vib_a",
    ) -> None:
        path = (
            f"/models/{quote(model_id)}/programs/{quote(program_name)}"
            f"/table-config/parameters/{quote(stat_name)}"
        )
        params = {"gear_label": gear_label, "direction": direction, "channel_name": channel_name}
        body = {"included": included}
        self._patch(path, body, on_success, on_error, params)
