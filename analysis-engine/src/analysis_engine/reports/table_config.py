"""Filters + reorders a Phase D CodeResultReport per an operator-configured
Table Config, matching the real Table Config.vi screen's two tabs: "GEAR &
NVH" (which gear+direction combos appear, and in what order) and "PARAMETER
CONFIG" (which parameters appear). Table Config is scoped per channel (the
screen's CHAN[NEL] dropdown), same as Phase C's limit_configs.

Pure post-processing on top of build_code_result_report() -- code_result.py
itself is not modified. Never adds a row for a (gear_direction, parameter)
pair build_code_result_report() didn't already produce: an ungraded
parameter never got a row in the first place (Phase D's existing "skip
stats with no master/config" pattern). See docs/data-contract.md's Phase E
section for the full column-semantics writeup."""

from __future__ import annotations

from dataclasses import dataclass, replace

from analysis_engine.grading.parameters import PARAMETER_CATALOG
from analysis_engine.reports.code_result import CodeResultReport

_PARAMETER_RANK: dict[str, int] = {name: index for index, name in enumerate(PARAMETER_CATALOG)}


@dataclass(frozen=True)
class TableConfigStep:
    gear_label: str
    direction: str
    step_order: int


@dataclass(frozen=True)
class TableConfig:
    channel_name: str
    steps: tuple[TableConfigStep, ...]
    included_parameters: frozenset[str]


def apply_table_config(report: CodeResultReport, table_config: TableConfig) -> CodeResultReport:
    """Raises if `report` contains rows for a different channel than
    `table_config` is scoped to -- a caller error (wrong report fed to wrong
    config), not a legitimate "nothing configured" case, which is instead
    represented by a row simply having no matching step/parameter entry."""
    if any(row.channel_name != table_config.channel_name for row in report.rows):
        raise ValueError(
            f"table config is scoped to channel {table_config.channel_name!r}, "
            "but the report contains rows for a different channel"
        )

    step_order_by_gear_direction = {
        f"{step.gear_label}_{step.direction}": step.step_order for step in table_config.steps
    }

    rows = [
        replace(row, step=step_order_by_gear_direction[row.gear_direction])
        for row in report.rows
        if row.gear_direction in step_order_by_gear_direction
        and row.parameter in table_config.included_parameters
    ]
    rows.sort(key=lambda row: (row.step, _PARAMETER_RANK[row.parameter]))
    return CodeResultReport(rows=rows)
