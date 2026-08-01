"""Reconstructs a live analysis_engine.pipeline.DcAnalysisResult on every
request (never read back from persisted grading_results/spc_points rows --
those are historical snapshots per docs/data-contract.md's Phase D "Not
persisted yet" note, missing order_spectrum/order_tracking/crash_noise/
slippage entirely), then feeds it through the existing report builders and
serializes via to_jsonable(). Every payload gets DcAnalysisResult.passed
injected manually before validation, since it's a computed @property that
to_jsonable() never emits -- the exact pattern
libs/nvh_api_schemas/tests/test_report_schema_contract.py already
establishes as "what the future backend's report_service does"."""

from __future__ import annotations

from typing import Any

from analysis_engine.pipeline import DcAnalysisResult, analyze_dc_record
from analysis_engine.reports.code_result import build_code_result_report
from analysis_engine.reports.consolidated import build_consolidated_report
from analysis_engine.reports.detailed import build_detailed_report
from analysis_engine.reports.serialization import to_jsonable
from analysis_engine.reports.summary import SummaryReportRow, build_summary_report
from analysis_engine.reports.table_config import apply_table_config
from fastapi import HTTPException
from nvh_api_schemas import CodeResultReportOut, ConsolidatedReportOut, DetailedReportOut, SummaryReportOut
from nvh_contract.db import DcRecordRow, ModelRow, TestRunRow
from nvh_contract.parquet_io import read_dc_parquet
from sqlalchemy.orm import Session

from nvh_web_backend.adapters import (
    dc_record_row_to_dc_record,
    gear_orders_for,
    model_row_to_model,
    test_run_row_to_test_run,
)
from nvh_web_backend.catalog_service import limit_configs_for, masters_for, table_config_for


def _load_dc_record_row(session: Session, dc_id: str) -> DcRecordRow:
    row = session.get(DcRecordRow, dc_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no dc_record {dc_id!r}")
    return row


def _reconstruct_result(session: Session, dc_row: DcRecordRow, program_name: str | None) -> DcAnalysisResult:
    test_run_row = session.get(TestRunRow, dc_row.test_run_id)
    model_row = session.get(ModelRow, test_run_row.model_id)
    model = model_row_to_model(model_row)
    gear_orders = gear_orders_for(model, dc_row.gear_label)

    columns = read_dc_parquet(dc_row.parquet_path)
    channel_names = [name[len("ch_") :] for name in columns if name.startswith("ch_")]
    if not channel_names:
        raise HTTPException(status_code=500, detail=f"parquet file for dc_record {dc_row.dc_id!r} has no channel columns")
    channel_name = channel_names[0]
    signal = columns[f"ch_{channel_name}"]

    masters = masters_for(session, model.model_id, dc_row.gear_label, dc_row.direction)
    limit_configs = (
        limit_configs_for(session, model.model_id, program_name, dc_row.gear_label, dc_row.direction, channel_name)
        if program_name
        else None
    )

    return analyze_dc_record(
        signal, columns["time_s"], columns["rpm"], dc_row.sample_rate_hz,
        dc_row.gear_label, dc_row.direction, gear_orders,
        masters=masters, limit_configs=limit_configs,
    )


def build_consolidated_payload(session: Session, dc_id: str, program_name: str | None) -> ConsolidatedReportOut:
    dc_row = _load_dc_record_row(session, dc_id)
    test_run_row = session.get(TestRunRow, dc_row.test_run_id)
    model_row = session.get(ModelRow, test_run_row.model_id)

    result = _reconstruct_result(session, dc_row, program_name)
    report = build_consolidated_report(
        test_run_row_to_test_run(test_run_row), dc_record_row_to_dc_record(dc_row),
        model_row_to_model(model_row), result,
    )

    payload: dict[str, Any] = to_jsonable(report)
    payload["result"]["passed"] = result.passed
    return ConsolidatedReportOut.model_validate(payload)


def build_detailed_payload(session: Session, dc_id: str, program_name: str | None) -> DetailedReportOut:
    dc_row = _load_dc_record_row(session, dc_id)
    test_run_row = session.get(TestRunRow, dc_row.test_run_id)
    model_row = session.get(ModelRow, test_run_row.model_id)

    result = _reconstruct_result(session, dc_row, program_name)
    consolidated = build_consolidated_report(
        test_run_row_to_test_run(test_run_row), dc_record_row_to_dc_record(dc_row),
        model_row_to_model(model_row), result,
    )
    masters = masters_for(session, model_row.model_id, dc_row.gear_label, dc_row.direction)
    detailed = build_detailed_report(consolidated, masters)

    payload = to_jsonable(detailed)
    payload["consolidated"]["result"]["passed"] = result.passed
    return DetailedReportOut.model_validate(payload)


def build_code_result_payload(session: Session, dc_id: str, program_name: str | None) -> CodeResultReportOut:
    dc_row = _load_dc_record_row(session, dc_id)
    test_run_row = session.get(TestRunRow, dc_row.test_run_id)
    model_row = session.get(ModelRow, test_run_row.model_id)
    model = model_row_to_model(model_row)

    result = _reconstruct_result(session, dc_row, program_name)
    columns = read_dc_parquet(dc_row.parquet_path)
    channel_name = next(name[len("ch_") :] for name in columns if name.startswith("ch_"))

    report = build_code_result_report(
        [result], {dc_row.gear_label: gear_orders_for(model, dc_row.gear_label)}, channel_name=channel_name
    )
    if program_name:
        table_config = table_config_for(session, model.model_id, program_name, channel_name)
        report = apply_table_config(report, table_config)

    payload = to_jsonable(report)
    return CodeResultReportOut.model_validate(payload)


def build_summary_payload(
    session: Session, model_id: str, gear_label: str, direction: str, stat_name: str, program_name: str | None,
    channel_name: str = "vib_a",
) -> SummaryReportOut:
    model_row = session.get(ModelRow, model_id)
    if model_row is None:
        raise HTTPException(status_code=404, detail=f"no model {model_id!r}")

    dc_rows = (
        session.query(DcRecordRow)
        .join(TestRunRow, DcRecordRow.test_run_id == TestRunRow.test_run_id)
        .filter(TestRunRow.model_id == model_id, DcRecordRow.gear_label == gear_label, DcRecordRow.direction == direction)
        .all()
    )
    if not dc_rows:
        raise HTTPException(status_code=404, detail=f"no dc_records for model={model_id!r} gear={gear_label!r} direction={direction!r}")

    rows = []
    for dc_row in dc_rows:
        test_run_row = session.get(TestRunRow, dc_row.test_run_id)
        result = _reconstruct_result(session, dc_row, program_name)
        rows.append(
            SummaryReportRow(
                test_run=test_run_row_to_test_run(test_run_row),
                dc_record=dc_record_row_to_dc_record(dc_row),
                result=result,
            )
        )

    summary = build_summary_report(rows, stat_name=stat_name)

    payload = to_jsonable(summary)
    for row_payload, row in zip(payload["rows"], rows):
        row_payload["result"]["passed"] = row.result.passed
    return SummaryReportOut.model_validate(payload)
