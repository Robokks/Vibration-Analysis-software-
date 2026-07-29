import pytest

from analysis_engine.grading.parameters import PARAMETER_CATALOG
from analysis_engine.reports.code_result import CodeResultReport, CodeResultRow
from analysis_engine.reports.table_config import TableConfig, TableConfigStep, apply_table_config


def _row(gear_direction, parameter, step=99, channel_name="vib_a"):
    return CodeResultRow(
        step=step, gear_direction=gear_direction, channel_name=channel_name, parameter=parameter,
        orders=None, low=0.9, high=1.1, actual=1.0, unit="g", ok_flag=True,
    )


def test_filters_out_unconfigured_steps_and_parameters():
    report = CodeResultReport(
        rows=[
            _row("R_RU", "RMS Avg"),
            _row("R_STYD", "RMS Avg"),  # not in the configured steps
            _row("R_RU", "PK Avg"),  # not in the configured parameters
        ]
    )
    table_config = TableConfig(
        channel_name="vib_a",
        steps=(TableConfigStep(gear_label="R", direction="RU", step_order=1),),
        included_parameters=frozenset({"RMS Avg"}),
    )

    filtered = apply_table_config(report, table_config)

    assert len(filtered.rows) == 1
    assert filtered.rows[0].gear_direction == "R_RU"
    assert filtered.rows[0].parameter == "RMS Avg"


def test_step_is_overwritten_from_configured_step_order_not_caller_order():
    report = CodeResultReport(rows=[_row("I_RU", "RMS Avg", step=42)])
    table_config = TableConfig(
        channel_name="vib_a",
        steps=(TableConfigStep(gear_label="I", direction="RU", step_order=7),),
        included_parameters=frozenset({"RMS Avg"}),
    )

    filtered = apply_table_config(report, table_config)

    assert filtered.rows[0].step == 7


def test_sort_order_follows_parameter_catalog_insertion_rank_not_alphabetical():
    # In PARAMETER_CATALOG's insertion order, "RMS Avg" comes before "Crest
    # Avg" (RMS is the 5th of 7 base labels, Crest the 7th) -- but
    # alphabetically "Crest Avg" < "RMS Avg". A naive alphabetical sort
    # would put Crest Avg first; the real ordering must not.
    names = list(PARAMETER_CATALOG)
    assert names.index("RMS Avg") < names.index("Crest Avg")

    report = CodeResultReport(
        rows=[_row("R_RU", "Crest Avg"), _row("R_RU", "RMS Avg")]
    )
    table_config = TableConfig(
        channel_name="vib_a",
        steps=(TableConfigStep(gear_label="R", direction="RU", step_order=1),),
        included_parameters=frozenset({"Crest Avg", "RMS Avg"}),
    )

    filtered = apply_table_config(report, table_config)

    assert [row.parameter for row in filtered.rows] == ["RMS Avg", "Crest Avg"]


def test_sorts_by_step_then_parameter_rank_across_multiple_steps():
    report = CodeResultReport(
        rows=[
            _row("I_RU", "PK Avg"),
            _row("R_RU", "RMS Avg"),
            _row("I_RU", "RMS Avg"),
        ]
    )
    table_config = TableConfig(
        channel_name="vib_a",
        steps=(
            TableConfigStep(gear_label="R", direction="RU", step_order=2),
            TableConfigStep(gear_label="I", direction="RU", step_order=1),
        ),
        included_parameters=frozenset({"RMS Avg", "PK Avg"}),
    )

    filtered = apply_table_config(report, table_config)

    assert [(row.step, row.gear_direction, row.parameter) for row in filtered.rows] == [
        (1, "I_RU", "RMS Avg"),
        (1, "I_RU", "PK Avg"),
        (2, "R_RU", "RMS Avg"),
    ]


def test_never_invents_a_row_for_a_pair_build_code_result_report_did_not_produce():
    # An ungraded parameter never gets a row from build_code_result_report()
    # in the first place -- apply_table_config can only narrow, never expand.
    report = CodeResultReport(rows=[_row("R_RU", "RMS Avg")])
    table_config = TableConfig(
        channel_name="vib_a",
        steps=(TableConfigStep(gear_label="R", direction="RU", step_order=1),),
        included_parameters=frozenset({"RMS Avg", "PK Avg", "Crest Avg"}),  # PK/Crest have no row to keep
    )

    filtered = apply_table_config(report, table_config)

    assert len(filtered.rows) == 1
    assert filtered.rows[0].parameter == "RMS Avg"


def test_channel_mismatch_raises():
    report = CodeResultReport(rows=[_row("R_RU", "RMS Avg", channel_name="mic")])
    table_config = TableConfig(
        channel_name="vib_a",
        steps=(TableConfigStep(gear_label="R", direction="RU", step_order=1),),
        included_parameters=frozenset({"RMS Avg"}),
    )

    with pytest.raises(ValueError):
        apply_table_config(report, table_config)


def test_empty_config_produces_no_rows():
    report = CodeResultReport(rows=[_row("R_RU", "RMS Avg")])
    table_config = TableConfig(channel_name="vib_a", steps=(), included_parameters=frozenset())

    filtered = apply_table_config(report, table_config)

    assert filtered.rows == []
