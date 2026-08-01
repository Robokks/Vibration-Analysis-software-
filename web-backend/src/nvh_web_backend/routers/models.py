from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from nvh_api_schemas.catalog import (
    CalibrationOut,
    CalibrationUpdate,
    ChannelConfigOut,
    LimitConfigCreate,
    LimitConfigLimitUpdate,
    LimitConfigThresholdUpdate,
    MasterProfileCreate,
    ModelCreate,
    ModelUpdate,
    ParameterCatalogRowOut,
    TableConfigParameterUpdate,
    TableConfigStepOut,
    TableConfigStepUpsert,
)
from nvh_contract.db import ChannelRow, DcRecordRow, MasterProfileRow, ModelRow, TableConfigStepRow, TestRunRow
from nvh_contract.models import MasterProfile, Model
from sqlalchemy.orm import Session

from nvh_web_backend.adapters import model_row_to_model
from nvh_web_backend.catalog_service import (
    create_master_profile,
    create_model,
    create_or_replace_limit_config,
    delete_limit_config_row,
    delete_master_profile,
    delete_model,
    delete_table_config_step,
    get_or_create_calibration,
    import_limit_configs_from_master_signatures,
    parameter_catalog_rows,
    set_table_config_parameter,
    update_calibration,
    update_limit_config_limit,
    update_limit_config_threshold,
    update_model,
    upsert_table_config_step,
)
from nvh_web_backend.db import get_session

router = APIRouter()


def _load_model_row(session: Session, model_id: str) -> ModelRow:
    row = session.get(ModelRow, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no model {model_id!r}")
    return row


def _load_program_row(session: Session, model_id: str, program_name: str) -> MasterProfileRow:
    row = session.get(MasterProfileRow, (model_id, program_name))
    if row is None:
        raise HTTPException(status_code=404, detail=f"no program {program_name!r} for model {model_id!r}")
    return row


@router.get("/models")
def list_models(session: Session = Depends(get_session)) -> list[dict[str, str]]:
    rows = session.query(ModelRow).all()
    return [{"model_id": row.model_id, "model_name": row.model_name} for row in rows]


@router.post("/models", status_code=201)
def create_model_endpoint(
    body: ModelCreate = Body(...),
    session: Session = Depends(get_session),
) -> Model:
    row = create_model(session, body)
    if row is None:
        raise HTTPException(status_code=409, detail=f"model {body.model_id!r} already exists")
    return model_row_to_model(row)


@router.get("/models/{model_id}")
def get_model(model_id: str, session: Session = Depends(get_session)) -> Model:
    return model_row_to_model(_load_model_row(session, model_id))


@router.put("/models/{model_id}")
def update_model_endpoint(
    model_id: str,
    body: ModelUpdate = Body(...),
    session: Session = Depends(get_session),
) -> Model:
    row = _load_model_row(session, model_id)
    return model_row_to_model(update_model(session, row, body))


@router.delete("/models/{model_id}", status_code=204)
def delete_model_endpoint(
    model_id: str,
    session: Session = Depends(get_session),
) -> Response:
    row = _load_model_row(session, model_id)
    delete_model(session, row)
    return Response(status_code=204)


@router.get("/models/{model_id}/programs")
def list_programs(model_id: str, session: Session = Depends(get_session)) -> list[MasterProfile]:
    _load_model_row(session, model_id)  # 404 if the model itself doesn't exist
    rows = session.query(MasterProfileRow).filter_by(model_id=model_id).all()
    return [MasterProfile(model_id=row.model_id, program_name=row.program_name, created_at=row.created_at) for row in rows]


@router.post("/models/{model_id}/programs", status_code=201)
def create_program(
    model_id: str,
    body: MasterProfileCreate = Body(...),
    session: Session = Depends(get_session),
) -> MasterProfile:
    _load_model_row(session, model_id)
    row = create_master_profile(session, model_id, body.program_name, datetime.now(timezone.utc).isoformat())
    if row is None:
        raise HTTPException(status_code=409, detail=f"program {body.program_name!r} already exists for model {model_id!r}")
    return MasterProfile(model_id=row.model_id, program_name=row.program_name, created_at=row.created_at)


@router.delete("/models/{model_id}/programs/{program_name}", status_code=204)
def delete_program(
    model_id: str,
    program_name: str,
    session: Session = Depends(get_session),
) -> Response:
    _load_model_row(session, model_id)
    row = session.get(MasterProfileRow, (model_id, program_name))
    if row is None:
        raise HTTPException(status_code=404, detail=f"program {program_name!r} not found for model {model_id!r}")
    delete_master_profile(session, row)
    return Response(status_code=204)


@router.get("/models/{model_id}/programs/{program_name}/parameters")
def list_parameters(
    model_id: str,
    program_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    session: Session = Depends(get_session),
) -> list[ParameterCatalogRowOut]:
    _load_model_row(session, model_id)
    return parameter_catalog_rows(session, model_id, program_name, gear_label, direction, channel_name)


@router.patch("/models/{model_id}/programs/{program_name}/limit-configs/{stat_name}/threshold")
def update_threshold(
    model_id: str,
    program_name: str,
    stat_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    body: LimitConfigThresholdUpdate = Body(...),
    session: Session = Depends(get_session),
) -> ParameterCatalogRowOut:
    """The real system's Limit Config.vi "Save" button after an operator
    tunes THRESHOLD_LOW/HIGH -- writes just those two columns on the
    matching LimitConfigRow, leaves the LIMIT band untouched, and returns
    the row's refreshed ParameterCatalogRowOut so the client can update in
    place without a separate GET."""
    _load_model_row(session, model_id)
    updated = update_limit_config_threshold(
        session, model_id, program_name, gear_label, direction, channel_name, stat_name,
        threshold_low=body.threshold_low, threshold_high=body.threshold_high,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=_missing_limit_config_detail(model_id, program_name, gear_label, direction, channel_name, stat_name),
        )
    return _refreshed_row(session, model_id, program_name, gear_label, direction, channel_name, stat_name)


@router.patch("/models/{model_id}/programs/{program_name}/limit-configs/{stat_name}/limit")
def update_limit(
    model_id: str,
    program_name: str,
    stat_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    body: LimitConfigLimitUpdate = Body(...),
    session: Session = Depends(get_session),
) -> ParameterCatalogRowOut:
    """Operator LIMIT override -- symmetric with the threshold PATCH above.
    Writes LIMIT_LOW/HIGH only; THRESHOLD stays as-is."""
    _load_model_row(session, model_id)
    updated = update_limit_config_limit(
        session, model_id, program_name, gear_label, direction, channel_name, stat_name,
        limit_low=body.limit_low, limit_high=body.limit_high,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=_missing_limit_config_detail(model_id, program_name, gear_label, direction, channel_name, stat_name),
        )
    return _refreshed_row(session, model_id, program_name, gear_label, direction, channel_name, stat_name)


@router.post("/models/{model_id}/programs/{program_name}/import-from-master", status_code=200)
def import_from_master(
    model_id: str,
    program_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    session: Session = Depends(get_session),
) -> list[ParameterCatalogRowOut]:
    """The "Import From MASTER" button backend: seeds or refreshes
    LimitConfigRows for all stats with a master signature for this
    (model, gear, direction), setting LIMIT_LOW/HIGH from band_min/band_max
    while preserving any existing THRESHOLD values. Returns the refreshed
    parameter catalog rows so the client can update its table in place."""
    _load_model_row(session, model_id)
    _load_program_row(session, model_id, program_name)
    import_limit_configs_from_master_signatures(
        session, model_id, program_name, gear_label, direction, channel_name,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return parameter_catalog_rows(session, model_id, program_name, gear_label, direction, channel_name)


@router.post("/models/{model_id}/programs/{program_name}/limit-configs", status_code=201)
def create_limit_config(
    model_id: str,
    program_name: str,
    body: LimitConfigCreate = Body(...),
    session: Session = Depends(get_session),
) -> ParameterCatalogRowOut:
    """Creates or fully replaces a single LimitConfigRow. Use the
    import-from-master action to bulk-seed from master signatures; use this
    endpoint to add or overwrite individual entries."""
    _load_model_row(session, model_id)
    _load_program_row(session, model_id, program_name)
    create_or_replace_limit_config(
        session, model_id, program_name, body,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return _refreshed_row(session, model_id, program_name, body.gear_label, body.direction, body.channel_name, body.stat_name)


@router.delete("/models/{model_id}/programs/{program_name}/limit-configs/{stat_name}", status_code=204)
def delete_limit_config(
    model_id: str,
    program_name: str,
    stat_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    session: Session = Depends(get_session),
) -> Response:
    _load_model_row(session, model_id)
    deleted = delete_limit_config_row(session, model_id, program_name, gear_label, direction, channel_name, stat_name)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=_missing_limit_config_detail(model_id, program_name, gear_label, direction, channel_name, stat_name),
        )
    return Response(status_code=204)


@router.patch("/models/{model_id}/programs/{program_name}/table-config/parameters/{stat_name}")
def update_table_config_parameter(
    model_id: str,
    program_name: str,
    stat_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    body: TableConfigParameterUpdate = Body(...),
    session: Session = Depends(get_session),
) -> ParameterCatalogRowOut:
    """Toggles whether the parameter appears in the program's Table Config
    (Phase E). Idempotent -- adding an already-included row (or removing
    an already-excluded one) is a no-op. gear_label/direction are query
    parameters only because the returned ParameterCatalogRowOut needs
    them to look up the row's master/limit-config data; the Table Config
    itself is program-scoped, not gear-scoped."""
    _load_model_row(session, model_id)
    ok = set_table_config_parameter(
        session, model_id, program_name, channel_name, stat_name,
        included=body.included, updated_at=datetime.now(timezone.utc).isoformat(),
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"unknown stat_name {stat_name!r}")
    return _refreshed_row(session, model_id, program_name, gear_label, direction, channel_name, stat_name)


@router.get("/models/{model_id}/programs/{program_name}/table-config/steps")
def list_table_config_steps(
    model_id: str,
    program_name: str,
    channel_name: str = Query("vib_a"),
    session: Session = Depends(get_session),
) -> list[TableConfigStepOut]:
    _load_model_row(session, model_id)
    rows = (
        session.query(TableConfigStepRow)
        .filter_by(model_id=model_id, program_name=program_name, channel_name=channel_name)
        .order_by(TableConfigStepRow.step_order)
        .all()
    )
    return [
        TableConfigStepOut(
            model_id=r.model_id, program_name=r.program_name,
            gear_label=r.gear_label, direction=r.direction,
            channel_name=r.channel_name, step_order=r.step_order,
        )
        for r in rows
    ]


@router.put("/models/{model_id}/programs/{program_name}/table-config/steps", status_code=200)
def upsert_table_config_step_endpoint(
    model_id: str,
    program_name: str,
    body: TableConfigStepUpsert = Body(...),
    session: Session = Depends(get_session),
) -> TableConfigStepOut:
    """Adds or updates a step entry (gear+direction+channel → step_order).
    Idempotent: re-submitting the same tuple with the same step_order is a
    no-op. Useful for re-ordering existing steps too."""
    _load_model_row(session, model_id)
    _load_program_row(session, model_id, program_name)
    row = upsert_table_config_step(session, model_id, program_name, body, datetime.now(timezone.utc).isoformat())
    return TableConfigStepOut(
        model_id=row.model_id, program_name=row.program_name,
        gear_label=row.gear_label, direction=row.direction,
        channel_name=row.channel_name, step_order=row.step_order,
    )


@router.delete("/models/{model_id}/programs/{program_name}/table-config/steps", status_code=204)
def delete_table_config_step_endpoint(
    model_id: str,
    program_name: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    channel_name: str = Query("vib_a"),
    session: Session = Depends(get_session),
) -> Response:
    _load_model_row(session, model_id)
    deleted = delete_table_config_step(session, model_id, program_name, gear_label, direction, channel_name)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"no table config step for model={model_id!r} program={program_name!r} "
                   f"gear={gear_label!r} direction={direction!r} channel={channel_name!r}",
        )
    return Response(status_code=204)


@router.get("/models/{model_id}/channels", response_model=list[ChannelConfigOut])
def list_model_channels(model_id: str, session: Session = Depends(get_session)) -> list[ChannelConfigOut]:
    """Distinct channels configured for the model, deduped across
    that model's dc_records. Drives the Phase L auto-layout on the
    Live Display: one plot group per channel."""
    _load_model_row(session, model_id)
    # Distinct on channel_name across all channels linked (via
    # dc_records -> test_runs) to this model. SQLite doesn't do
    # DISTINCT ON, so do the dedupe in Python -- volumes are tiny.
    rows = (
        session.query(ChannelRow)
        .join(DcRecordRow, ChannelRow.dc_id == DcRecordRow.dc_id)
        .join(TestRunRow, DcRecordRow.test_run_id == TestRunRow.test_run_id)
        .filter(TestRunRow.model_id == model_id)
        .all()
    )
    seen: set[str] = set()
    out: list[ChannelConfigOut] = []
    for r in rows:
        if r.channel_name in seen:
            continue
        seen.add(r.channel_name)
        out.append(ChannelConfigOut(
            channel_name=r.channel_name,
            sensor_type=r.sensor_type,
            units=r.units,
            sensitivity_mv_per_eu=r.sensitivity_mv_per_eu,
            pregain_db=r.pregain_db,
            weighting_filter=r.weighting_filter,
            is_reference_accel=bool(r.is_reference_accel),
        ))
    return out


@router.get("/models/{model_id}/calibrations/{channel_name}")
def get_calibration(
    model_id: str,
    channel_name: str,
    session: Session = Depends(get_session),
) -> CalibrationOut:
    """Returns the (model, channel) calibration state, seeding the row
    with the LabVIEW manual's default values (1000 mV/EU, V, 1.0 dB
    ref, linear, 0 dB pregain) on first read so a fresh model doesn't
    need a separate calibration-seed step."""
    _load_model_row(session, model_id)
    row = get_or_create_calibration(
        session, model_id, channel_name, updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return CalibrationOut(
        model_id=row.model_id, channel_name=row.channel_name,
        sensor_sensitivity_mv_per_eu=row.sensor_sensitivity_mv_per_eu,
        engineering_units=row.engineering_units,
        db_reference_eu=row.db_reference_eu,
        custom_label=row.custom_label,
        weighting_filter=row.weighting_filter,
        pregain_db=row.pregain_db,
        last_calibrated_at=row.last_calibrated_at,
        due_at=row.due_at,
    )


@router.patch("/models/{model_id}/calibrations/{channel_name}")
def patch_calibration(
    model_id: str,
    channel_name: str,
    body: CalibrationUpdate = Body(...),
    session: Session = Depends(get_session),
) -> CalibrationOut:
    """Persist the operator's calibration form -- writes every field on
    a Save. Matches the LabVIEW screen's single-Save behavior."""
    _load_model_row(session, model_id)
    row = update_calibration(
        session, model_id, channel_name,
        updated_at=datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    )
    return CalibrationOut(
        model_id=row.model_id, channel_name=row.channel_name,
        sensor_sensitivity_mv_per_eu=row.sensor_sensitivity_mv_per_eu,
        engineering_units=row.engineering_units,
        db_reference_eu=row.db_reference_eu,
        custom_label=row.custom_label,
        weighting_filter=row.weighting_filter,
        pregain_db=row.pregain_db,
        last_calibrated_at=row.last_calibrated_at,
        due_at=row.due_at,
    )


def _missing_limit_config_detail(
    model_id: str, program_name: str, gear_label: str, direction: str, channel_name: str, stat_name: str,
) -> str:
    return (
        f"no limit config for model={model_id!r} program={program_name!r} "
        f"gear={gear_label!r} direction={direction!r} channel={channel_name!r} stat={stat_name!r}"
    )


def _refreshed_row(
    session: Session, model_id: str, program_name: str, gear_label: str, direction: str,
    channel_name: str, stat_name: str,
) -> ParameterCatalogRowOut:
    """Look up and return the refreshed ParameterCatalogRowOut so the
    client can drop the response straight into its row-by-stat_name lookup
    -- shared by all three PATCH endpoints."""
    rows = parameter_catalog_rows(session, model_id, program_name, gear_label, direction, channel_name)
    for row in rows:
        if row.stat_name == stat_name:
            return row
    raise HTTPException(status_code=500, detail=f"stat {stat_name!r} missing from refreshed catalog rows")
