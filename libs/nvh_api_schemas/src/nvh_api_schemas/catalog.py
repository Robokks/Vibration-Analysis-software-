"""Wire schema for the Master Entry "Parameter catalog" screen: one row per
graded parameter for a given (model, program, gear, direction, channel),
bundling its master-signature stats, LIMIT/THRESHOLD config, and whether the
program's Table Config currently includes it. Built directly from DB rows
(MasterSignatureRow, LimitConfigRow, TableConfigParameterRow) -- independent
of analysis_engine.reports.*, unlike report.py's schemas, and not a plain
rollup either, unlike management.py's -- so it gets its own module."""

from __future__ import annotations

from pydantic import BaseModel, Field

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


class ChannelConfigOut(BaseModel):
    """One row per configured channel for a model, drives the
    Phase L auto-layout of Live Display plots (one plot group per
    channel). The `sensor_type` string is what the Qt client
    switches on: 'accel' (time + freq + order plots), 'mic' (time +
    freq octave), 'counter' (RPM readout only)."""

    channel_name: str
    sensor_type: str | None
    units: str
    sensitivity_mv_per_eu: float | None
    pregain_db: float | None
    weighting_filter: str | None
    is_reference_accel: bool


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


class CalibrationOut(BaseModel):
    """Sensor calibration state for one (model, channel) -- matches the
    real Vibr-O-Matic Analyzer's Calibration window field set."""

    model_id: str
    channel_name: str
    sensor_sensitivity_mv_per_eu: float
    engineering_units: str
    db_reference_eu: float
    custom_label: str
    weighting_filter: str
    pregain_db: float
    last_calibrated_at: str | None = None
    due_at: str | None = None


class CalibrationUpdate(BaseModel):
    """Body for the PATCH /models/{model_id}/calibrations/{channel_name}
    endpoint. All fields required -- the frontend sends the full state
    every save, matching the LabVIEW screen's single Save button."""

    sensor_sensitivity_mv_per_eu: float
    engineering_units: str
    db_reference_eu: float
    custom_label: str
    weighting_filter: str
    pregain_db: float
    last_calibrated_at: str | None = None
    due_at: str | None = None


# ---------------------------------------------------------------------------
# Write schemas for model / program / limit-config / table-config steps
# ---------------------------------------------------------------------------


class ModelCreate(BaseModel):
    """Body for POST /models. model_id is the user-defined identifier
    (matches the real MASTER SETUP screen's MODEL NAME field)."""

    model_id: str
    model_name: str
    drive_teeth: dict[str, int]
    idler_teeth_1: dict[str, int]
    idler_teeth_2: dict[str, int] = Field(default_factory=dict)
    layshaft_teeth: dict[str, int]
    drive_shaft_bearing_roll: dict[str, float] = Field(default_factory=dict)
    layshaft_bearing_roll: dict[str, float] = Field(default_factory=dict)
    fdr_teeth: dict[str, int] = Field(default_factory=dict)
    fd_sel: dict[str, str] = Field(default_factory=dict)
    ratios: dict[str, float]


class ModelUpdate(BaseModel):
    """Body for PUT /models/{model_id} -- full field replace (model_id is
    path-only). Matches the same field set as ModelCreate without model_id."""

    model_name: str
    drive_teeth: dict[str, int]
    idler_teeth_1: dict[str, int]
    idler_teeth_2: dict[str, int] = Field(default_factory=dict)
    layshaft_teeth: dict[str, int]
    drive_shaft_bearing_roll: dict[str, float] = Field(default_factory=dict)
    layshaft_bearing_roll: dict[str, float] = Field(default_factory=dict)
    fdr_teeth: dict[str, int] = Field(default_factory=dict)
    fd_sel: dict[str, str] = Field(default_factory=dict)
    ratios: dict[str, float]


class MasterProfileCreate(BaseModel):
    """Body for POST /models/{model_id}/programs."""

    program_name: str


class LimitConfigCreate(BaseModel):
    """Body for POST .../limit-configs. Upserts a single LimitConfigRow.
    Use the import-from-master action to bulk-seed from master signatures;
    use this endpoint to add or overwrite individual entries."""

    gear_label: str
    direction: str
    channel_name: str = "vib_a"
    stat_name: str
    order_number: float | None = None
    limit_low: float
    limit_high: float
    threshold_low: float = 0.0
    threshold_high: float = 0.0


class TableConfigStepOut(BaseModel):
    """One step row from the Table Config (gear+direction+order)."""

    model_id: str
    program_name: str
    gear_label: str
    direction: str
    channel_name: str
    step_order: int


class TableConfigStepUpsert(BaseModel):
    """Body for PUT .../table-config/steps -- add or update a step."""

    gear_label: str
    direction: str
    channel_name: str = "vib_a"
    step_order: int
