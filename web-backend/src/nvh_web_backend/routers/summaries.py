"""POST /summaries + GET /summaries for the Phase J persistence path.

Producer POSTs one row per PLC final-log-trigger. Reports UI can list
them back. Distinct from the on-demand reconstruction path in
`report_service._reconstruct_result` -- see docstrings on
`nvh_api_schemas.summary`."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from nvh_api_schemas.summary import SummaryDataCreate, SummaryDataOut
from nvh_contract.db import SummaryDataRow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nvh_web_backend.db import get_session

router = APIRouter()


def _row_to_out(row: SummaryDataRow) -> SummaryDataOut:
    return SummaryDataOut(
        summary_id=row.summary_id,
        test_run_id=row.test_run_id,
        dc_id=row.dc_id,
        model_id=row.model_id,
        serial_no=row.serial_no,
        serial_rpt=row.serial_rpt,
        gear_id=row.gear_id,
        nvh_id=row.nvh_id,
        rms_avg=row.rms_avg,
        peak=row.peak,
        order_1x_mag=row.order_1x_mag,
        stamp=row.stamp,
        fail_reason_codes=json.loads(row.fail_reason_codes_json or "[]"),
        created_at=row.created_at,
    )


@router.post("/summaries", response_model=SummaryDataOut)
def create_summary(body: SummaryDataCreate, session: Session = Depends(get_session)) -> SummaryDataOut:
    row = SummaryDataRow(
        summary_id=str(uuid.uuid4()),
        test_run_id=body.test_run_id,
        dc_id=body.dc_id,
        model_id=body.model_id,
        serial_no=body.serial_no,
        serial_rpt=body.serial_rpt,
        gear_id=body.gear_id,
        nvh_id=body.nvh_id,
        rms_avg=body.rms_avg,
        peak=body.peak,
        order_1x_mag=body.order_1x_mag,
        stamp=body.stamp,
        fail_reason_codes_json=json.dumps(body.fail_reason_codes),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        # Phase O Bug 9: producer's fire-and-forget POST can retry on a
        # transient backend blip. UNIQUE (test_run_id, dc_id, gear_id,
        # nvh_id) on SummaryDataRow makes the second POST a no-op:
        # roll back the doomed insert, look up the existing row, and
        # return it. The producer's contract is idempotent.
        session.rollback()
        existing = (
            session.query(SummaryDataRow)
            .filter_by(
                test_run_id=body.test_run_id,
                dc_id=body.dc_id,
                gear_id=body.gear_id,
                nvh_id=body.nvh_id,
            )
            .one()
        )
        return _row_to_out(existing)
    session.refresh(row)
    return _row_to_out(row)


@router.get("/summaries", response_model=list[SummaryDataOut])
def list_summaries(
    model_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[SummaryDataOut]:
    stmt = session.query(SummaryDataRow).order_by(SummaryDataRow.created_at.desc())
    if model_id is not None:
        stmt = stmt.filter(SummaryDataRow.model_id == model_id)
    return [_row_to_out(r) for r in stmt.all()]
