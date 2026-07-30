"""Wire schema for the Master Entry "Parameter catalog" screen: one row per
graded parameter for a given (model, program, gear, direction, channel),
bundling its master-signature stats, LIMIT/THRESHOLD config, and whether the
program's Table Config currently includes it. Built directly from DB rows
(MasterSignatureRow, LimitConfigRow, TableConfigParameterRow) -- independent
of analysis_engine.reports.*, unlike report.py's schemas, and not a plain
rollup either, unlike management.py's -- so it gets its own module."""

from __future__ import annotations

from pydantic import BaseModel

from nvh_api_schemas.report import MasterSignatureStatsOut


class ParameterCatalogRowOut(BaseModel):
    stat_name: str
    order_number: float | None = None
    master: MasterSignatureStatsOut | None = None
    limit_low: float | None = None
    limit_high: float | None = None
    threshold_low: float | None = None
    threshold_high: float | None = None
    included_in_table_config: bool


class LimitConfigThresholdUpdate(BaseModel):
    """Body for the PATCH /models/{...}/limit-configs/{stat_name}/threshold
    endpoint -- matches the real system's Limit Config.vi "Save" button
    persisting an operator-tuned THRESHOLD margin (see Phase C notes in
    docs/data-contract.md for what THRESHOLD_LOW/HIGH mean physically)."""

    threshold_low: float
    threshold_high: float
