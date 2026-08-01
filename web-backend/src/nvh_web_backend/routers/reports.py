from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from nvh_api_schemas import CodeResultReportOut, ConsolidatedReportOut, DetailedReportOut, SummaryReportOut
from sqlalchemy.orm import Session

from nvh_web_backend.db import get_session
from nvh_web_backend.report_service import (
    build_code_result_payload,
    build_consolidated_payload,
    build_detailed_payload,
    build_summary_payload,
)

router = APIRouter()


@router.get("/dc-records/{dc_id}/reports/consolidated")
def get_consolidated_report(
    dc_id: str, program_name: str | None = Query(None), session: Session = Depends(get_session)
) -> ConsolidatedReportOut:
    return build_consolidated_payload(session, dc_id, program_name)


@router.get("/dc-records/{dc_id}/reports/detailed")
def get_detailed_report(
    dc_id: str, program_name: str | None = Query(None), session: Session = Depends(get_session)
) -> DetailedReportOut:
    return build_detailed_payload(session, dc_id, program_name)


@router.get("/dc-records/{dc_id}/reports/code-result")
def get_code_result_report(
    dc_id: str, program_name: str | None = Query(None), session: Session = Depends(get_session)
) -> CodeResultReportOut:
    return build_code_result_payload(session, dc_id, program_name)


@router.get("/models/{model_id}/summary")
def get_summary_report(
    model_id: str,
    gear_label: str = Query(...),
    direction: str = Query(...),
    stat_name: str = Query(...),
    program_name: str | None = Query(None),
    channel_name: str = Query("vib_a"),
    session: Session = Depends(get_session),
) -> SummaryReportOut:
    return build_summary_payload(session, model_id, gear_label, direction, stat_name, program_name, channel_name)
