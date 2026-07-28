import pytest

from analysis_engine.ordermatrix.gear_math import (
    GearTeeth,
    compute_gear_orders,
    compute_order_matrix,
)


def test_mesh_order_equals_drive_shaft_teeth():
    orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft=36, layshaft=32), gear_ratio=3.753)
    assert orders.mesh_order == 12.0


def test_idler_and_layshaft_orders_are_teeth_ratios():
    orders = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft=36, layshaft=32), gear_ratio=3.753)
    assert orders.idler_shaft_order == pytest.approx(12 / 36)
    assert orders.layshaft_order == pytest.approx(12 / 32)


def test_missing_idler_shaft_gives_none():
    orders = compute_gear_orders("IV", GearTeeth(drive_shaft=38, idler_shaft=0, layshaft=41), gear_ratio=1.0)
    assert orders.idler_shaft_order is None
    assert orders.layshaft_order == pytest.approx(38 / 41)


def test_output_shaft_order_is_inverse_of_ratio():
    orders = compute_gear_orders("IV", GearTeeth(drive_shaft=38, layshaft=41), gear_ratio=1.0)
    assert orders.output_shaft_order == pytest.approx(1.0)

    orders_r = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft=36, layshaft=32), gear_ratio=3.753)
    assert orders_r.output_shaft_order == pytest.approx(1 / 3.753)


def test_final_drive_mesh_order_uses_output_shaft_order():
    orders = compute_gear_orders(
        "IV", GearTeeth(drive_shaft=38, layshaft=41), gear_ratio=1.0, final_drive_teeth=27
    )
    assert orders.final_drive_mesh_order == pytest.approx(1.0 * 27)


def test_final_drive_mesh_order_is_none_without_teeth():
    orders = compute_gear_orders("IV", GearTeeth(drive_shaft=38, layshaft=41), gear_ratio=1.0)
    assert orders.final_drive_mesh_order is None


def test_zero_drive_shaft_teeth_raises():
    with pytest.raises(ValueError):
        compute_gear_orders("N", GearTeeth(drive_shaft=0), gear_ratio=1.0)


def test_compute_order_matrix_skips_gears_without_ratio():
    teeth_by_gear = {
        "N": GearTeeth(drive_shaft=1),
        "R": GearTeeth(drive_shaft=12, idler_shaft=36, layshaft=32),
    }
    ratio_by_gear = {"R": 3.753}  # no ratio for N (neutral)

    matrix = compute_order_matrix(teeth_by_gear, ratio_by_gear)

    assert set(matrix.keys()) == {"R"}
    assert matrix["R"].mesh_order == 12.0
