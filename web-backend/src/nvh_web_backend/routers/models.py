from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from nvh_api_schemas.catalog import LimitConfigThresholdUpdate, ParameterCatalogRowOut
from nvh_contract.db import MasterProfileRow, ModelRow
from nvh_contract.models import MasterProfile, Model
from sqlalchemy.orm import Session

from nvh_web_backend.adapters import model_row_to_model
from nvh_web_backend.catalog_service import parameter_catalog_rows, update_limit_config_threshold
from nvh_web_backend.db import get_session

router = APIRouter()


def _load_model_row(session: Session, model_id: str) -> ModelRow:
    row = session.get(ModelRow, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no model {model_id!r}")
    return row


@router.get("/models")
def list_models(session: Session = Depends(get_session)) -> list[dict[str, str]]:
    rows = session.query(ModelRow).all()
    return [{"model_id": row.model_id, "model_name": row.model_name} for row in rows]


@router.get("/models/{model_id}")
def get_model(model_id: str, session: Session = Depends(get_session)) -> Model:
    return model_row_to_model(_load_model_row(session, model_id))


@router.get("/models/{model_id}/programs")
def list_programs(model_id: str, session: Session = Depends(get_session)) -> list[MasterProfile]:
    _load_model_row(session, model_id)  # 404 if the model itself doesn't exist
    rows = session.query(MasterProfileRow).filter_by(model_id=model_id).all()
    return [MasterProfile(model_id=row.model_id, program_name=row.program_name, created_at=row.created_at) for row in rows]


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
            detail=(
                f"no limit config for model={model_id!r} program={program_name!r} "
                f"gear={gear_label!r} direction={direction!r} channel={channel_name!r} stat={stat_name!r}"
            ),
        )

    # Return the same shape the list endpoint uses so the client can drop
    # the response straight into its row-by-stat_name lookup.
    rows = parameter_catalog_rows(session, model_id, program_name, gear_label, direction, channel_name)
    for row in rows:
        if row.stat_name == stat_name:
            return row
    # Impossible in practice (we just updated a row that exists), but keep
    # the exhaustive branch honest.
    raise HTTPException(status_code=500, detail=f"stat {stat_name!r} missing from refreshed catalog rows")
