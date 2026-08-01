from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from nvh_contract.db import DcRecordRow, TestRunRow
from nvh_contract.models import DcRecord, TestRun
from pydantic import BaseModel
from sqlalchemy.orm import Session

from nvh_web_backend.adapters import dc_record_row_to_dc_record, test_run_row_to_test_run
from nvh_web_backend.db import get_session

router = APIRouter()


class TestRunDetail(BaseModel):
    test_run: TestRun
    dc_records: list[DcRecord]


@router.get("/test-runs")
def list_test_runs(
    model_id: str | None = Query(None), session: Session = Depends(get_session)
) -> list[TestRun]:
    query = session.query(TestRunRow)
    if model_id is not None:
        query = query.filter_by(model_id=model_id)
    return [test_run_row_to_test_run(row) for row in query.all()]


@router.get("/test-runs/{test_run_id}")
def get_test_run(test_run_id: str, session: Session = Depends(get_session)) -> TestRunDetail:
    test_run_row = session.get(TestRunRow, test_run_id)
    if test_run_row is None:
        raise HTTPException(status_code=404, detail=f"no test_run {test_run_id!r}")
    dc_rows = session.query(DcRecordRow).filter_by(test_run_id=test_run_id).all()
    return TestRunDetail(
        test_run=test_run_row_to_test_run(test_run_row),
        dc_records=[dc_record_row_to_dc_record(row) for row in dc_rows],
    )
