"""Consolidated report: the per-unit grade/pass-fail overview, matching the
reference system's Consolidated Report screen. Time/speed/frequency-series
tabs in the UI map directly onto fields already present on `DcAnalysisResult`
— no new series types are introduced here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from nvh_contract.models import DcRecord, Model, TestRun

from analysis_engine.pipeline import DcAnalysisResult

Stamp = Literal["PASS", "FAIL"]


@dataclass(frozen=True)
class ConsolidatedReport:
    test_run: TestRun
    dc_record: DcRecord
    model: Model
    result: DcAnalysisResult
    stamp: Stamp


def build_consolidated_report(
    test_run: TestRun, dc_record: DcRecord, model: Model, result: DcAnalysisResult
) -> ConsolidatedReport:
    return ConsolidatedReport(
        test_run=test_run,
        dc_record=dc_record,
        model=model,
        result=result,
        stamp="PASS" if result.passed else "FAIL",
    )
