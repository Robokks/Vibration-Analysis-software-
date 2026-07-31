"""POST /dashboard/context + GET /dashboard/context (Phase K).

Owns the single-row IngestContext used by the state machine + producer
to know which model/serial/operator the current run applies to."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from nvh_api_schemas.dashboard import IngestContextIn, IngestContextOut
from nvh_contract.db import IngestContextRow
from sqlalchemy.orm import Session

from nvh_web_backend.db import get_session

router = APIRouter()


def _row_to_out(row: IngestContextRow) -> IngestContextOut:
    return IngestContextOut(
        station_id=row.station_id,
        model_name=row.model_name,
        serial_no=row.serial_no,
        serial_rpt=row.serial_rpt,
        operator_name=row.operator_name,
        received_at=row.received_at,
    )


@router.post("/dashboard/context", response_model=IngestContextOut)
def upsert_context(body: IngestContextIn, session: Session = Depends(get_session)) -> IngestContextOut:
    now = datetime.now(timezone.utc).isoformat()
    row = session.get(IngestContextRow, body.station_id)
    if row is None:
        row = IngestContextRow(station_id=body.station_id, model_name=body.model_name,
                               serial_no=body.serial_no, serial_rpt=body.serial_rpt,
                               operator_name=body.operator_name, received_at=now)
        session.add(row)
    else:
        row.model_name = body.model_name
        row.serial_no = body.serial_no
        row.serial_rpt = body.serial_rpt
        row.operator_name = body.operator_name
        row.received_at = now
    session.commit()
    session.refresh(row)
    return _row_to_out(row)


@router.get("/dashboard/context/{station_id}", response_model=IngestContextOut)
def read_context(station_id: str, session: Session = Depends(get_session)) -> IngestContextOut:
    row = session.get(IngestContextRow, station_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no context for station {station_id!r}")
    return _row_to_out(row)
