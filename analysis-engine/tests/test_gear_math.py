import pytest

from analysis_engine.ordermatrix.gear_math import (
    GearTeeth,
    compute_gear_orders,
    compute_order_matrix,
)


def test_mesh_order_equals_drive_shaft_teeth():
    orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
    assert orders.mesh_order == 12.0


def test_idler_and_layshaft_orders_are_teeth_ratios():
    orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
    assert orders.idler_shaft_1_order == pytest.approx(12 / 36)
    assert orders.layshaft_order == pytest.approx(12 / 32)


def test_missing_idler_shaft_gives_none():
    orders = compute_gear_orders("IV", GearTeeth(drive_shaft=38, idler_shaft_1=0, layshaft=41), gear_ratio=1.0)
    assert orders.idler_shaft_1_order is None
    assert orders.layshaft_order == pytest.approx(38 / 41)


def test_two_idler_shafts_give_independent_orders():
    orders = compute_gear_orders(
        "R", GearTeeth(drive_shaft=12, idler_shaft_1=36, idler_shaft_2=18, layshaft=32), gear_ratio=3.753
    )
    assert orders.idler_shaft_1_order == pytest.approx(12 / 36)
    assert orders.idler_shaft_2_order == pytest.approx(12 / 18)


def test_missing_idler_shaft_2_gives_none():
    orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
    assert orders.idler_shaft_2_order is None


def test_bearing_roll_orders_pass_through_unchanged():
    orders = compute_gear_orders(
        "R",
        GearTeeth(drive_shaft=12, layshaft=32, drive_shaft_bearing_roll=5.43, layshaft_bearing_roll=7.91),
        gear_ratio=3.753,
    )
    assert orders.drive_shaft_bearing_roll_order == 5.43
    assert orders.layshaft_bearing_roll_order == 7.91


def test_bearing_roll_orders_default_to_none():
    orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, layshaft=32), gear_ratio=3.753)
    assert orders.drive_shaft_bearing_roll_order is None
    assert orders.layshaft_bearing_roll_order is None


def test_output_shaft_order_is_inverse_of_ratio():
    orders = compute_gear_orders("IV", GearTeeth(drive_shaft=38, layshaft=41), gear_ratio=1.0)
    assert orders.output_shaft_order == pytest.approx(1.0)

    orders_r = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)
    assert orders_r.output_shaft_order == pytest.approx(1 / 3.753)


def test_final_drive_mesh_order_resolves_fd_sel_against_fdr_teeth():
    orders = compute_gear_orders(
        "IV",
        GearTeeth(drive_shaft=38, layshaft=41, fd_sel="FDR1"),
        gear_ratio=1.0,
        fdr_teeth={"FDR1": 27, "FDR2": 30},
    )
    assert orders.final_drive_mesh_order == pytest.approx(1.0 * 27)


def test_final_drive_mesh_order_is_none_without_fd_sel():
    orders = compute_gear_orders(
        "IV", GearTeeth(drive_shaft=38, layshaft=41), gear_ratio=1.0, fdr_teeth={"FDR1": 27}
    )
    assert orders.final_drive_mesh_order is None


def test_final_drive_mesh_order_is_none_when_fd_sel_not_in_fdr_teeth():
    orders = compute_gear_orders(
        "IV",
        GearTeeth(drive_shaft=38, layshaft=41, fd_sel="FDR9"),
        gear_ratio=1.0,
        fdr_teeth={"FDR1": 27, "FDR2": 30},
    )
    assert orders.final_drive_mesh_order is None


def test_final_drive_mesh_order_is_none_without_fdr_teeth():
    orders = compute_gear_orders("IV", GearTeeth(drive_shaft=38, layshaft=41, fd_sel="FDR1"), gear_ratio=1.0)
    assert orders.final_drive_mesh_order is None


def test_zero_drive_shaft_teeth_raises():
    with pytest.raises(ValueError):
        compute_gear_orders("N", GearTeeth(drive_shaft=0), gear_ratio=1.0)


def test_compute_order_matrix_skips_gears_without_ratio():
    teeth_by_gear = {
        "N": GearTeeth(drive_shaft=1),
        "R": GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32),
    }
    ratio_by_gear = {"R": 3.753}  # no ratio for N (neutral)

    matrix = compute_order_matrix(teeth_by_gear, ratio_by_gear)

    assert set(matrix.keys()) == {"R"}
    assert matrix["R"].mesh_order == 12.0


def test_compute_order_matrix_forwards_fdr_teeth_per_gear():
    teeth_by_gear = {
        "IV": GearTeeth(drive_shaft=38, layshaft=41, fd_sel="FDR1"),
        "V": GearTeeth(drive_shaft=43, layshaft=25, fd_sel="FDR2"),
    }
    ratio_by_gear = {"IV": 1.0, "V": 0.818}

    matrix = compute_order_matrix(teeth_by_gear, ratio_by_gear, fdr_teeth={"FDR1": 27, "FDR2": 30})

    assert matrix["IV"].final_drive_mesh_order == pytest.approx(1.0 * 27)
    assert matrix["V"].final_drive_mesh_order == pytest.approx((1 / 0.818) * 30)
