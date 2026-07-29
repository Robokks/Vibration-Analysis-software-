"""Converts nvh_contract ORM rows into the plain pydantic/dataclass shapes
the rest of the stack (nvh_contract.models, analysis_engine.ordermatrix)
expects. Nothing in nvh_contract or analysis-engine does this conversion
today -- every existing consumer (seed_demo_data.py, the CLI demo, tests)
builds these objects directly in-memory rather than reading them back out
of a DB row, so this is the first code to bridge that gap."""

from __future__ import annotations

import json

from analysis_engine.ordermatrix.gear_math import GearOrders, GearTeeth, compute_gear_orders
from fastapi import HTTPException
from nvh_contract.db import DcRecordRow, ModelRow, TestRunRow
from nvh_contract.models import DcRecord, Model, TestRun


def model_row_to_model(row: ModelRow) -> Model:
    return Model(
        model_id=row.model_id,
        model_name=row.model_name,
        drive_teeth=json.loads(row.drive_teeth_json),
        idler_teeth_1=json.loads(row.idler_teeth_1_json),
        idler_teeth_2=json.loads(row.idler_teeth_2_json),
        layshaft_teeth=json.loads(row.layshaft_teeth_json),
        drive_shaft_bearing_roll=json.loads(row.drive_shaft_bearing_roll_json),
        layshaft_bearing_roll=json.loads(row.layshaft_bearing_roll_json),
        fdr_teeth=json.loads(row.fdr_teeth_json),
        fd_sel=json.loads(row.fd_sel_json),
        ratios=json.loads(row.ratios_json),
    )


def test_run_row_to_test_run(row: TestRunRow) -> TestRun:
    return TestRun(
        test_run_id=row.test_run_id,
        model_id=row.model_id,
        serial_number=row.serial_number,
        operator_id=row.operator_id,
        shift_number=row.shift_number,
        repeat_number=row.repeat_number,
        line_id=row.line_id,
        station_id=row.station_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        overall_result=row.overall_result,
    )


def dc_record_row_to_dc_record(row: DcRecordRow) -> DcRecord:
    codes = [code for code in (row.fail_reason_codes or "").split(",") if code]
    return DcRecord(
        dc_id=row.dc_id,
        test_run_id=row.test_run_id,
        gear_label=row.gear_label,
        direction=row.direction,
        rpm_start=row.rpm_start,
        rpm_end=row.rpm_end,
        sample_rate_hz=row.sample_rate_hz,
        parquet_path=row.parquet_path,
        result=row.result,
        fail_reason_codes=codes,
    )


def gear_teeth_for(model: Model, gear_label: str) -> GearTeeth:
    if gear_label not in model.drive_teeth:
        raise HTTPException(status_code=404, detail=f"gear {gear_label!r} is not configured for model {model.model_id!r}")
    return GearTeeth(
        drive_shaft=model.drive_teeth[gear_label],
        idler_shaft_1=model.idler_teeth_1.get(gear_label, 0),
        idler_shaft_2=model.idler_teeth_2.get(gear_label, 0),
        layshaft=model.layshaft_teeth.get(gear_label, 0),
        drive_shaft_bearing_roll=model.drive_shaft_bearing_roll.get(gear_label),
        layshaft_bearing_roll=model.layshaft_bearing_roll.get(gear_label),
        fd_sel=model.fd_sel.get(gear_label),
    )


def gear_orders_for(model: Model, gear_label: str) -> GearOrders:
    if gear_label not in model.ratios:
        raise HTTPException(status_code=404, detail=f"gear {gear_label!r} has no configured ratio for model {model.model_id!r}")
    teeth = gear_teeth_for(model, gear_label)
    fdr_teeth = model.fdr_teeth or None
    return compute_gear_orders(gear_label, teeth, model.ratios[gear_label], fdr_teeth)
