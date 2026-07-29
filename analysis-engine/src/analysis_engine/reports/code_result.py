"""Flat CODE-RESULT-style grading output table, matching the real system's
exported per-unit grading-result sheet: one row per (gear+direction, channel,
parameter), confirmed from a real client screenshot with columns
STEP | GEAR_DIRECTION | CHANNEL | PARAMETER | ORDERS | LOW | ACTUAL | HIGH |
UNIT | OK/NOK. Built directly from in-memory DcAnalysisResult objects, the
same way consolidated.py/detailed.py/summary.py are -- purely additive, no
changes to DcAnalysisResult or pipeline.py. See docs/data-contract.md's
Phase D section for the full column-semantics writeup."""

from __future__ import annotations

from dataclasses import dataclass

from analysis_engine.grading.parameters import PARAMETER_CATALOG, unit_label_for
from analysis_engine.ordermatrix.gear_math import GearOrders
from analysis_engine.pipeline import DcAnalysisResult


@dataclass(frozen=True)
class CodeResultRow:
    step: int
    gear_direction: str
    channel_name: str
    parameter: str
    orders: float | None
    low: float
    high: float
    actual: float
    unit: str
    ok_flag: bool


@dataclass(frozen=True)
class CodeResultReport:
    rows: list[CodeResultRow]


def build_code_result_report(
    results: list[DcAnalysisResult],
    gear_orders_by_gear: dict[str, GearOrders],
    channel_name: str = "vib_a",
) -> CodeResultReport:
    """`gear_orders_by_gear` is keyed by gear_label only (not gear+direction)
    -- GearOrders is purely a property of the gear's teeth/ratio, shared
    across all 4 directions. A result whose gear_label is missing from the
    map degrades to orders=None for its harmonic rows rather than raising,
    matching this codebase's dominant graceful-degradation style. Only
    parameters present in a result's `grading.per_stat` get rows -- an
    ungraded parameter has no meaningful LOW/HIGH/OK-NOK to show, matching
    grade_dc_record's/grade_dc_record_with_limits's "skip stats with no
    master/config" pattern. `step` is a 1-based ordinal over `results` in
    the order supplied."""
    rows: list[CodeResultRow] = []
    for step, result in enumerate(results, start=1):
        if result.grading is None:
            continue
        gear_orders = gear_orders_by_gear.get(result.gear_label)
        gear_direction = f"{result.gear_label}_{result.direction}"
        for stat_name, check in result.grading.per_stat.items():
            spec = PARAMETER_CATALOG[stat_name]
            orders = spec.order_fn(gear_orders) if spec.kind == "harmonic" and gear_orders is not None else None
            rows.append(
                CodeResultRow(
                    step=step,
                    gear_direction=gear_direction,
                    channel_name=channel_name,
                    parameter=stat_name,
                    orders=orders,
                    low=check.low,
                    high=check.high,
                    actual=result.parameters[stat_name],
                    unit=unit_label_for(spec),
                    ok_flag=check.ok_flag,
                )
            )
    return CodeResultReport(rows=rows)
