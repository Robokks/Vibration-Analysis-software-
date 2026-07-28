"""Gear mesh/shaft order computation from tooth counts and gear ratios.

Orders are computed algebraically, never measured — this mirrors the reference
system's "order matrix" behaviour.

Convention used here (documented explicitly since it is a design choice, not a
physical constant): the input/drive shaft is the reference and has order 1.
For any other shaft driven through a single mesh, its rotational order relative
to the drive shaft is `drive_shaft_teeth / other_shaft_teeth`. The **gear mesh
order** (tooth-contact event rate) for a meshing pair is invariant regardless of
which member of the pair you reference it from: `mesh_order = shaft_order *
teeth_on_that_shaft`, and for the drive shaft (order 1) that reduces to simply
`drive_shaft_teeth`.

Bearing defect orders are intentionally not computed here — they depend on
bearing geometry (ball count, pitch/ball diameter, contact angle), not gear
tooth counts, and are out of scope for this module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GearTeeth:
    drive_shaft: int
    idler_shaft: int = 0
    layshaft: int = 0


@dataclass(frozen=True)
class GearOrders:
    gear_label: str
    mesh_order: float
    idler_shaft_order: float | None
    layshaft_order: float | None
    output_shaft_order: float
    final_drive_mesh_order: float | None


def compute_gear_orders(
    gear_label: str,
    teeth: GearTeeth,
    gear_ratio: float,
    final_drive_teeth: int | None = None,
) -> GearOrders:
    if teeth.drive_shaft <= 0:
        raise ValueError(f"drive_shaft teeth must be positive for gear {gear_label!r}")
    if gear_ratio <= 0:
        raise ValueError(f"gear_ratio must be positive for gear {gear_label!r}")

    mesh_order = float(teeth.drive_shaft)

    idler_shaft_order = (
        teeth.drive_shaft / teeth.idler_shaft if teeth.idler_shaft else None
    )
    layshaft_order = (
        teeth.drive_shaft / teeth.layshaft if teeth.layshaft else None
    )

    output_shaft_order = 1.0 / gear_ratio

    final_drive_mesh_order = (
        output_shaft_order * final_drive_teeth if final_drive_teeth else None
    )

    return GearOrders(
        gear_label=gear_label,
        mesh_order=mesh_order,
        idler_shaft_order=idler_shaft_order,
        layshaft_order=layshaft_order,
        output_shaft_order=output_shaft_order,
        final_drive_mesh_order=final_drive_mesh_order,
    )


def compute_order_matrix(
    teeth_by_gear: dict[str, GearTeeth],
    ratio_by_gear: dict[str, float],
    final_drive_teeth: int | None = None,
) -> dict[str, GearOrders]:
    """Compute GearOrders for every gear present in both `teeth_by_gear` and
    `ratio_by_gear` (gears without a ratio, e.g. neutral, are skipped)."""
    matrix: dict[str, GearOrders] = {}
    for gear_label, teeth in teeth_by_gear.items():
        if gear_label not in ratio_by_gear:
            continue
        matrix[gear_label] = compute_gear_orders(
            gear_label, teeth, ratio_by_gear[gear_label], final_drive_teeth
        )
    return matrix
