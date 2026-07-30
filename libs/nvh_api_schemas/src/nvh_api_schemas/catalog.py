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


class LimitConfigLimitUpdate(BaseModel):
    """Body for the PATCH /models/{...}/limit-configs/{stat_name}/limit
    endpoint -- the operator override side of Limit Config.vi. The LIMIT
    band is normally auto-imported from the master signature, but the real
    system lets an operator overwrite it (e.g. to loosen a limit that's
    tripping too often); this endpoint persists just LIMIT_LOW/HIGH,
    leaving THRESHOLD_LOW/HIGH untouched."""

    limit_low: float
    limit_high: float


class TableConfigParameterUpdate(BaseModel):
    """Body for the PATCH /models/{...}/table-config/parameters/{stat_name}
    endpoint -- toggles whether the parameter appears in the program's
    Table Config (Phase E). `included=true` inserts a
    TableConfigParameterRow if none exists; `included=false` deletes it.
    Idempotent by design."""

    included: bool
