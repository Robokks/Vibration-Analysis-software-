from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from nvh_api_schemas.catalog import ParameterCatalogRowOut
from nvh_contract.db import MasterProfileRow, ModelRow
from nvh_contract.models import MasterProfile, Model
from sqlalchemy.orm import Session

from nvh_web_backend.adapters import model_row_to_model
from nvh_web_backend.catalog_service import parameter_catalog_rows
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
