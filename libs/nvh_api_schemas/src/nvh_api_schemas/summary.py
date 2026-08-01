"""Wire schema for the persisted summary-data pipeline (Phase J).

When the PLC's `final_log_trigger` transition fires, the producer POSTs
a `SummaryDataCreate` to `/summaries` on the FastAPI backend, which
persists a row in the SummaryDataRow table. Reports UI can list these
back via `SummaryDataOut` -- distinct from the on-demand
`SummaryReportOut` at `nvh_api_schemas.report`, which is a
reconstruction from the raw Parquet + config rows and has different
purpose (fine-grained analysis view) and lifecycle.
"""

from __future__ import annotations

from pydantic import BaseModel


class SummaryDataCreate(BaseModel):
    """Body of POST /summaries. All numeric fields optional -- the
    producer sends whatever it has computed at trigger time."""

    test_run_id: str
    dc_id: str
    model_id: str
    serial_no: str
    serial_rpt: str  # string to match IngestContextIn -- accepts "R2" etc.
    gear_id: int
    nvh_id: int
    rms_avg: float | None = None
    peak: float | None = None
    order_1x_mag: float | None = None
    stamp: str = "PASS"
    fail_reason_codes: list[str] = []


class SummaryDataOut(BaseModel):
    """One persisted row. `summary_id` is the row PK. `created_at` is
    an ISO-8601 UTC timestamp."""

    summary_id: str
    test_run_id: str
    dc_id: str
    model_id: str
    serial_no: str
    serial_rpt: str  # string to match IngestContextIn -- accepts "R2" etc.
    gear_id: int
    nvh_id: int
    rms_avg: float | None
    peak: float | None
    order_1x_mag: float | None
    stamp: str
    fail_reason_codes: list[str]
    created_at: str
