"""Detailed report: a Consolidated report plus a numeric table tab (grades and
raw stat values), matching the reference system's Detailed Report screen."""

from __future__ import annotations

from dataclasses import dataclass

from analysis_engine.grading.envelope_check import EnvelopeCheckResult
from analysis_engine.grading.master_builder import MasterSignatureStats
from analysis_engine.pipeline import stats_to_dict
from analysis_engine.reports.consolidated import ConsolidatedReport


@dataclass(frozen=True)
class NumericTableRow:
    stat_name: str
    domain: str  # 'time' | 'speed'
    observed_value: float
    master: MasterSignatureStats | None
    grading: EnvelopeCheckResult | None


@dataclass(frozen=True)
class DetailedReport:
    consolidated: ConsolidatedReport
    numeric_table: list[NumericTableRow]


def build_detailed_report(
    consolidated: ConsolidatedReport,
    masters: dict[str, MasterSignatureStats] | None = None,
    domain: str = "time",
) -> DetailedReport:
    masters = masters or {}
    stat_values = stats_to_dict(consolidated.result.stats)
    per_stat_grading = (
        consolidated.result.grading.per_stat if consolidated.result.grading is not None else {}
    )

    rows = [
        NumericTableRow(
            stat_name=stat_name,
            domain=domain,
            observed_value=value,
            master=masters.get(stat_name),
            grading=per_stat_grading.get(stat_name),
        )
        for stat_name, value in stat_values.items()
    ]

    return DetailedReport(consolidated=consolidated, numeric_table=rows)
