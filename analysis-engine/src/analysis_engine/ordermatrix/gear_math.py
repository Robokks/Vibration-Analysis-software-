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

Bearing roll orders are not *computed* here — they depend on bearing geometry
(ball count, pitch/ball diameter, contact angle) looked up from a datasheet,
which is out of scope for this module. They *are* carried through from
`GearTeeth` to `GearOrders` unchanged, exactly like any other order value,
once someone has entered them (e.g. on a master-entry screen): the entered
value is already a dimensionless order number, not a teeth count needing
conversion, so no ratio is computed for it here.

Final-drive selection: a model may have multiple final-drive (FDR) teeth
variants available; `GearTeeth.fd_sel` names which variant a given gear uses,
resolved against an `fdr_teeth` lookup passed to `compute_gear_orders`/
`compute_order_matrix`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GearTeeth:
    drive_shaft: int
    idler_shaft_1: int = 0
    idler_shaft_2: int = 0
    layshaft: int = 0
    drive_shaft_bearing_roll: float | None = None
    layshaft_bearing_roll: float | None = None
    fd_sel: str | None = None  # which entry of `fdr_teeth` this gear uses, e.g. "FDR1"


@dataclass(frozen=True)
class GearOrders:
    gear_label: str
    mesh_order: float
    idler_shaft_1_order: float | None
    idler_shaft_2_order: float | None
    layshaft_order: float | None
    output_shaft_order: float
    final_drive_mesh_order: float | None
    drive_shaft_bearing_roll_order: float | None = None
    layshaft_bearing_roll_order: float | None = None


def compute_gear_orders(
    gear_label: str,
    teeth: GearTeeth,
    gear_ratio: float,
    fdr_teeth: dict[str, int] | None = None,
) -> GearOrders:
    if teeth.drive_shaft <= 0:
        raise ValueError(f"drive_shaft teeth must be positive for gear {gear_label!r}")
    if gear_ratio <= 0:
        raise ValueError(f"gear_ratio must be positive for gear {gear_label!r}")

    mesh_order = float(teeth.drive_shaft)

    idler_shaft_1_order = (
        teeth.drive_shaft / teeth.idler_shaft_1 if teeth.idler_shaft_1 else None
    )
    idler_shaft_2_order = (
        teeth.drive_shaft / teeth.idler_shaft_2 if teeth.idler_shaft_2 else None
    )
    layshaft_order = (
        teeth.drive_shaft / teeth.layshaft if teeth.layshaft else None
    )

    output_shaft_order = 1.0 / gear_ratio

    final_drive_teeth = (
        fdr_teeth.get(teeth.fd_sel) if fdr_teeth and teeth.fd_sel else None
    )
    final_drive_mesh_order = (
        output_shaft_order * final_drive_teeth if final_drive_teeth else None
    )

    return GearOrders(
        gear_label=gear_label,
        mesh_order=mesh_order,
        idler_shaft_1_order=idler_shaft_1_order,
        idler_shaft_2_order=idler_shaft_2_order,
        layshaft_order=layshaft_order,
        output_shaft_order=output_shaft_order,
        final_drive_mesh_order=final_drive_mesh_order,
        drive_shaft_bearing_roll_order=teeth.drive_shaft_bearing_roll,
        layshaft_bearing_roll_order=teeth.layshaft_bearing_roll,
    )


def compute_order_matrix(
    teeth_by_gear: dict[str, GearTeeth],
    ratio_by_gear: dict[str, float],
    fdr_teeth: dict[str, int] | None = None,
) -> dict[str, GearOrders]:
    """Compute GearOrders for every gear present in both `teeth_by_gear` and
    `ratio_by_gear` (gears without a ratio, e.g. neutral, are skipped)."""
    matrix: dict[str, GearOrders] = {}
    for gear_label, teeth in teeth_by_gear.items():
        if gear_label not in ratio_by_gear:
            continue
        matrix[gear_label] = compute_gear_orders(
            gear_label, teeth, ratio_by_gear[gear_label], fdr_teeth
        )
    return matrix
