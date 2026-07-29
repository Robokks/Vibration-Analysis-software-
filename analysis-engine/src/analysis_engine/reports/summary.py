"""Summary report: multi-unit comparison + SPC for one (model, gear,
direction, stat), matching the reference system's Summary screen. Reuses the
existing SPC math directly — no new statistics are introduced here."""

from __future__ import annotations

from dataclasses import dataclass

from nvh_contract.models import DcRecord, TestRun

from analysis_engine.pipeline import DcAnalysisResult, stats_to_dict
from analysis_engine.spc.histogram import HistogramResult, compute_histogram
from analysis_engine.spc.xchart import XChartResult, compute_xchart


@dataclass(frozen=True)
class SummaryReportRow:
    test_run: TestRun
    dc_record: DcRecord
    result: DcAnalysisResult


@dataclass(frozen=True)
class SummaryReport:
    model_id: str
    gear_label: str
    direction: str
    stat_name: str
    rows: list[SummaryReportRow]
    xchart: XChartResult
    histogram: HistogramResult


def build_summary_report(
    rows: list[SummaryReportRow], stat_name: str, n_bins: int = 10
) -> SummaryReport:
    if not rows:
        raise ValueError("need at least one row to build a summary report")

    values = [stats_to_dict(row.result.stats)[stat_name] for row in rows]

    return SummaryReport(
        model_id=rows[0].test_run.model_id,
        gear_label=rows[0].dc_record.gear_label,
        direction=rows[0].dc_record.direction,
        stat_name=stat_name,
        rows=rows,
        xchart=compute_xchart(values),
        histogram=compute_histogram(values, n_bins),
    )
