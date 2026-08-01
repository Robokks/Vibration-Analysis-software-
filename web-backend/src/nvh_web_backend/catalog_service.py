"""Builds the dict[str, Value] shapes analysis_engine's grading functions
expect (masters, limit_configs) from DB rows, and the Master Entry
"Parameter catalog" screen's per-parameter list -- three related but
independent queries over the same three config tables."""

from __future__ import annotations

import json

from analysis_engine.grading.limit_config import LimitConfigValue
from analysis_engine.grading.master_builder import MasterSignatureStats
from analysis_engine.grading.parameters import PARAMETER_CATALOG
from analysis_engine.reports.table_config import TableConfig, TableConfigStep
from nvh_api_schemas.catalog import (
    LimitConfigCreate,
    ModelCreate,
    ModelUpdate,
    ParameterCatalogRowOut,
    TableConfigStepUpsert,
)
from nvh_api_schemas.report import MasterSignatureStatsOut
from nvh_contract.db import (
    CalibrationRow,
    LimitConfigRow,
    MasterProfileRow,
    MasterSignatureRow,
    ModelRow,
    TableConfigParameterRow,
    TableConfigStepRow,
)
from sqlalchemy.orm import Session


def masters_for(session: Session, model_id: str, gear_label: str, direction: str) -> dict[str, MasterSignatureStats]:
    """Not scoped by program_name -- MasterSignatureRow has no such column;
    a master signature is a property of (model, gear, direction, stat), same
    as it's always been since Phase A/B."""
    rows = (
        session.query(MasterSignatureRow)
        .filter_by(model_id=model_id, gear_label=gear_label, direction=direction)
        .all()
    )
    return {
        row.stat_name: MasterSignatureStats(
            mean_value=row.mean_value, band_min=row.band_min, band_max=row.band_max,
            full_scale=row.full_scale, trial_count=row.trial_count,
        )
        for row in rows
    }


def limit_configs_for(
    session: Session, model_id: str, program_name: str, gear_label: str, direction: str, channel_name: str = "vib_a"
) -> dict[str, LimitConfigValue]:
    """LimitConfigRow doesn't persist mean_value/full_scale (only
    limit_low/high + threshold_low/high) -- neither affects a
    check_value_with_threshold() pass/fail (only limit_low/high +
    threshold_low/high do), only the informational g_level's percentage
    representation, so falling back to a reasonable approximation when no
    master signature exists for a stat is safe. Prefer the real master's
    mean_value/full_scale when one exists (limit configs are normally
    imported *from* a master in the first place, per Phase C)."""
    masters = masters_for(session, model_id, gear_label, direction)
    rows = (
        session.query(LimitConfigRow)
        .filter_by(model_id=model_id, program_name=program_name, gear_label=gear_label,
                    direction=direction, channel_name=channel_name)
        .all()
    )
    values: dict[str, LimitConfigValue] = {}
    for row in rows:
        master = masters.get(row.stat_name)
        mean_value = master.mean_value if master else row.limit_low + (row.limit_high - row.limit_low) / 2
        full_scale = master.full_scale if master else max(abs(row.limit_high), abs(row.limit_low), 1.0)
        values[row.stat_name] = LimitConfigValue(
            mean_value=mean_value, limit_low=row.limit_low, limit_high=row.limit_high,
            full_scale=full_scale, threshold_low=row.threshold_low, threshold_high=row.threshold_high,
        )
    return values


def parameter_catalog_rows(
    session: Session, model_id: str, program_name: str, gear_label: str, direction: str, channel_name: str = "vib_a"
) -> list[ParameterCatalogRowOut]:
    """One row per parameter that has EITHER a master signature or a limit
    config -- a parameter with neither has nothing to show. Masters aren't
    program-scoped; limit configs and table-config inclusion are."""
    master_rows = {
        row.stat_name: row
        for row in session.query(MasterSignatureRow)
        .filter_by(model_id=model_id, gear_label=gear_label, direction=direction)
        .all()
    }
    limit_rows = {
        row.stat_name: row
        for row in session.query(LimitConfigRow)
        .filter_by(model_id=model_id, program_name=program_name, gear_label=gear_label,
                    direction=direction, channel_name=channel_name)
        .all()
    }
    included_names = {
        row.stat_name
        for row in session.query(TableConfigParameterRow)
        .filter_by(model_id=model_id, program_name=program_name, channel_name=channel_name)
        .all()
    }

    stat_names = sorted(set(master_rows) | set(limit_rows))
    rows: list[ParameterCatalogRowOut] = []
    for stat_name in stat_names:
        master_row = master_rows.get(stat_name)
        limit_row = limit_rows.get(stat_name)
        rows.append(
            ParameterCatalogRowOut(
                stat_name=stat_name,
                order_number=limit_row.order_number if limit_row else None,
                master=(
                    MasterSignatureStatsOut(
                        mean_value=master_row.mean_value, band_min=master_row.band_min,
                        band_max=master_row.band_max, full_scale=master_row.full_scale,
                        trial_count=master_row.trial_count,
                    )
                    if master_row else None
                ),
                limit_low=limit_row.limit_low if limit_row else None,
                limit_high=limit_row.limit_high if limit_row else None,
                threshold_low=limit_row.threshold_low if limit_row else None,
                threshold_high=limit_row.threshold_high if limit_row else None,
                included_in_table_config=stat_name in included_names,
            )
        )
    return rows


def table_config_for(session: Session, model_id: str, program_name: str, channel_name: str = "vib_a") -> TableConfig:
    step_rows = (
        session.query(TableConfigStepRow)
        .filter_by(model_id=model_id, program_name=program_name, channel_name=channel_name)
        .all()
    )
    parameter_rows = (
        session.query(TableConfigParameterRow)
        .filter_by(model_id=model_id, program_name=program_name, channel_name=channel_name)
        .all()
    )
    return TableConfig(
        channel_name=channel_name,
        steps=tuple(
            TableConfigStep(gear_label=row.gear_label, direction=row.direction, step_order=row.step_order)
            for row in step_rows
        ),
        included_parameters=frozenset(row.stat_name for row in parameter_rows),
    )


def update_limit_config_threshold(
    session: Session,
    model_id: str,
    program_name: str,
    gear_label: str,
    direction: str,
    channel_name: str,
    stat_name: str,
    threshold_low: float,
    threshold_high: float,
    updated_at: str,
) -> LimitConfigRow | None:
    """Updates just the THRESHOLD_LOW/HIGH columns of the matching
    LimitConfigRow, leaving the LIMIT band (imported from the master) and
    every other column untouched -- matches the real system's Limit
    Config.vi "Save" button after an operator tunes the margin. Returns
    None (not a KeyError/HTTPException) if the row doesn't exist so the
    router can raise its own 404 with a descriptive message."""
    row = session.get(
        LimitConfigRow,
        (model_id, program_name, gear_label, direction, channel_name, stat_name),
    )
    if row is None:
        return None
    row.threshold_low = threshold_low
    row.threshold_high = threshold_high
    row.updated_at = updated_at
    session.commit()
    return row


def update_limit_config_limit(
    session: Session,
    model_id: str,
    program_name: str,
    gear_label: str,
    direction: str,
    channel_name: str,
    stat_name: str,
    limit_low: float,
    limit_high: float,
    updated_at: str,
) -> LimitConfigRow | None:
    """Operator-override side of Limit Config.vi -- updates just the LIMIT
    band, leaving THRESHOLD_LOW/HIGH and everything else alone. Symmetric
    with update_limit_config_threshold(); returns None on unknown row so
    the router raises its own 404."""
    row = session.get(
        LimitConfigRow,
        (model_id, program_name, gear_label, direction, channel_name, stat_name),
    )
    if row is None:
        return None
    row.limit_low = limit_low
    row.limit_high = limit_high
    row.updated_at = updated_at
    session.commit()
    return row


def get_or_create_calibration(
    session: Session, model_id: str, channel_name: str, updated_at: str,
) -> CalibrationRow:
    """Fetch the (model, channel) calibration row, creating one with
    the manual's default values if none exists yet. Lets the frontend
    GET the endpoint on a fresh model without a separate seed step."""
    row = session.get(CalibrationRow, (model_id, channel_name))
    if row is not None:
        return row
    row = CalibrationRow(
        model_id=model_id,
        channel_name=channel_name,
        sensor_sensitivity_mv_per_eu=1000.0,
        engineering_units="V",
        db_reference_eu=1.0,
        custom_label="EU",
        weighting_filter="linear",
        pregain_db=0.0,
        last_calibrated_at=None,
        due_at=None,
        updated_at=updated_at,
    )
    session.add(row)
    session.commit()
    return row


def update_calibration(
    session: Session,
    model_id: str,
    channel_name: str,
    updated_at: str,
    **fields,
) -> CalibrationRow:
    """PATCH-shaped writer: full row replace for the six form fields +
    the two audit timestamps. Creates the row if it doesn't exist yet
    (matches the LabVIEW screen's Save button which always persists)."""
    row = get_or_create_calibration(session, model_id, channel_name, updated_at)
    for key, value in fields.items():
        if hasattr(row, key):
            setattr(row, key, value)
    row.updated_at = updated_at
    session.commit()
    return row


def set_table_config_parameter(
    session: Session,
    model_id: str,
    program_name: str,
    channel_name: str,
    stat_name: str,
    included: bool,
    updated_at: str,
) -> bool:
    """Adds or removes a TableConfigParameterRow -- the Phase E "which
    parameters go in the Table Config" toggle. Idempotent: turning an
    already-included parameter on again (or an already-excluded one off)
    is a no-op. Rejects stat names that aren't in the analysis engine's
    PARAMETER_CATALOG so we can't insert a Table Config row for a
    parameter that doesn't exist in the grading framework. Returns True
    on success, False for an unknown stat_name."""
    if stat_name not in PARAMETER_CATALOG:
        return False

    existing = session.get(TableConfigParameterRow, (model_id, program_name, channel_name, stat_name))
    if included and existing is None:
        session.add(
            TableConfigParameterRow(
                model_id=model_id,
                program_name=program_name,
                channel_name=channel_name,
                stat_name=stat_name,
                updated_at=updated_at,
            )
        )
    elif not included and existing is not None:
        session.delete(existing)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------


def _model_row_kwargs(body: ModelCreate | ModelUpdate, model_id: str | None = None) -> dict:
    base: dict = {
        "model_name": body.model_name,
        "drive_teeth_json": json.dumps(body.drive_teeth),
        "idler_teeth_1_json": json.dumps(body.idler_teeth_1),
        "idler_teeth_2_json": json.dumps(body.idler_teeth_2),
        "layshaft_teeth_json": json.dumps(body.layshaft_teeth),
        "drive_shaft_bearing_roll_json": json.dumps(body.drive_shaft_bearing_roll),
        "layshaft_bearing_roll_json": json.dumps(body.layshaft_bearing_roll),
        "fdr_teeth_json": json.dumps(body.fdr_teeth),
        "fd_sel_json": json.dumps(body.fd_sel),
        "ratios_json": json.dumps(body.ratios),
    }
    if model_id is not None:
        base["model_id"] = model_id
    return base


def create_model(session: Session, body: ModelCreate) -> ModelRow:
    """Creates a new ModelRow. Returns None if model_id already exists."""
    if session.get(ModelRow, body.model_id) is not None:
        return None
    row = ModelRow(**_model_row_kwargs(body, model_id=body.model_id))
    session.add(row)
    session.commit()
    return row


def update_model(session: Session, row: ModelRow, body: ModelUpdate) -> ModelRow:
    """Full-field replace of a ModelRow (model_id is unchanged)."""
    for key, value in _model_row_kwargs(body).items():
        setattr(row, key, value)
    session.commit()
    return row


def delete_model(session: Session, row: ModelRow) -> None:
    """Deletes a ModelRow and all directly dependent rows (cascades manually
    since SQLite doesn't enforce FK cascades by default)."""
    session.delete(row)
    session.commit()


# ---------------------------------------------------------------------------
# Master profile CRUD
# ---------------------------------------------------------------------------


def create_master_profile(session: Session, model_id: str, program_name: str, created_at: str) -> MasterProfileRow | None:
    """Creates a MasterProfileRow. Returns None if the (model_id,
    program_name) pair already exists."""
    if session.get(MasterProfileRow, (model_id, program_name)) is not None:
        return None
    row = MasterProfileRow(model_id=model_id, program_name=program_name, created_at=created_at)
    session.add(row)
    session.commit()
    return row


def delete_master_profile(session: Session, row: MasterProfileRow) -> None:
    """Deletes a MasterProfileRow (and its limit configs / table config rows)."""
    session.query(LimitConfigRow).filter_by(
        model_id=row.model_id, program_name=row.program_name,
    ).delete()
    session.query(TableConfigStepRow).filter_by(
        model_id=row.model_id, program_name=row.program_name,
    ).delete()
    session.query(TableConfigParameterRow).filter_by(
        model_id=row.model_id, program_name=row.program_name,
    ).delete()
    session.delete(row)
    session.commit()


# ---------------------------------------------------------------------------
# Limit config create / import / delete
# ---------------------------------------------------------------------------


def import_limit_configs_from_master_signatures(
    session: Session,
    model_id: str,
    program_name: str,
    gear_label: str,
    direction: str,
    channel_name: str,
    updated_at: str,
) -> int:
    """The "Import From MASTER" button backend: seeds / refreshes
    LimitConfigRows for all stats that have a MasterSignatureRow for this
    (model, gear, direction), seeding limit_low/high from band_min/band_max
    and leaving any existing threshold values intact. Returns the row count
    upserted."""
    master_rows = (
        session.query(MasterSignatureRow)
        .filter_by(model_id=model_id, gear_label=gear_label, direction=direction)
        .all()
    )
    for mr in master_rows:
        pk = (model_id, program_name, gear_label, direction, channel_name, mr.stat_name)
        existing = session.get(LimitConfigRow, pk)
        if existing is not None:
            existing.limit_low = mr.band_min
            existing.limit_high = mr.band_max
            existing.updated_at = updated_at
        else:
            spec = PARAMETER_CATALOG.get(mr.stat_name)
            session.add(LimitConfigRow(
                model_id=model_id,
                program_name=program_name,
                gear_label=gear_label,
                direction=direction,
                channel_name=channel_name,
                stat_name=mr.stat_name,
                order_number=None,  # can't resolve per-gear order here without GearOrders; informational only
                limit_low=mr.band_min,
                limit_high=mr.band_max,
                threshold_low=0.0,
                threshold_high=0.0,
                updated_at=updated_at,
            ))
    session.commit()
    return len(master_rows)


def create_or_replace_limit_config(
    session: Session,
    model_id: str,
    program_name: str,
    body: LimitConfigCreate,
    updated_at: str,
) -> LimitConfigRow:
    """Upserts a single LimitConfigRow (create or full-field replace)."""
    pk = (model_id, program_name, body.gear_label, body.direction, body.channel_name, body.stat_name)
    row = session.get(LimitConfigRow, pk)
    if row is None:
        row = LimitConfigRow(
            model_id=model_id,
            program_name=program_name,
            gear_label=body.gear_label,
            direction=body.direction,
            channel_name=body.channel_name,
            stat_name=body.stat_name,
            order_number=body.order_number,
            limit_low=body.limit_low,
            limit_high=body.limit_high,
            threshold_low=body.threshold_low,
            threshold_high=body.threshold_high,
            updated_at=updated_at,
        )
        session.add(row)
    else:
        row.order_number = body.order_number
        row.limit_low = body.limit_low
        row.limit_high = body.limit_high
        row.threshold_low = body.threshold_low
        row.threshold_high = body.threshold_high
        row.updated_at = updated_at
    session.commit()
    return row


def delete_limit_config_row(
    session: Session,
    model_id: str,
    program_name: str,
    gear_label: str,
    direction: str,
    channel_name: str,
    stat_name: str,
) -> bool:
    """Deletes a LimitConfigRow. Returns True if deleted, False if not found."""
    row = session.get(LimitConfigRow, (model_id, program_name, gear_label, direction, channel_name, stat_name))
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Table config step upsert / delete
# ---------------------------------------------------------------------------


def upsert_table_config_step(
    session: Session,
    model_id: str,
    program_name: str,
    body: TableConfigStepUpsert,
    updated_at: str,
) -> TableConfigStepRow:
    """Adds or updates a TableConfigStepRow (upsert by 5-column PK)."""
    pk = (model_id, program_name, body.gear_label, body.direction, body.channel_name)
    row = session.get(TableConfigStepRow, pk)
    if row is None:
        row = TableConfigStepRow(
            model_id=model_id,
            program_name=program_name,
            gear_label=body.gear_label,
            direction=body.direction,
            channel_name=body.channel_name,
            step_order=body.step_order,
            updated_at=updated_at,
        )
        session.add(row)
    else:
        row.step_order = body.step_order
        row.updated_at = updated_at
    session.commit()
    return row


def delete_table_config_step(
    session: Session,
    model_id: str,
    program_name: str,
    gear_label: str,
    direction: str,
    channel_name: str,
) -> bool:
    """Deletes a TableConfigStepRow. Returns True if deleted, False if not found."""
    row = session.get(TableConfigStepRow, (model_id, program_name, gear_label, direction, channel_name))
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True
