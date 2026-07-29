"""The Phase B 49-parameter catalog: windowed base statistics (bare units and
two derived unit families), plus order-spectrum harmonic peak lookups (three
unit families each, no windowing). One ParameterSpec shape expresses all
three: `kind` distinguishes "windowed" (draws from WindowedStatsResult) vs
"harmonic" (draws from peak_magnitude_near_order); `unit_convert` expresses
the bare/m-s2/dB-m-s2 unit-family axis that both kinds share.

Parameter names are the literal strings read off the client's real Master
Entry "Parameters" screen and are persisted verbatim as `stat_name` in
nvh_contract's master_signatures/grading_results/spc_points tables (all
unconstrained TEXT -- no migration needed). Two real, and easily missed,
formatting quirks are preserved deliberately because these names round-trip
through a database:
  - base-stat names use lowercase "max" but capitalized "Avg" (e.g.
    "Mean max" / "Mean Avg") -- inconsistent, but that's what the real
    screen shows.
  - the RMS/PK unit-family suffix has a leading space ("RMS max (m/s2)")
    while the harmonic unit suffix does not ("IN_H1(g)").
"IN_H2(g)" (and its m/s2/dB variants) is a best-effort read of a partially
obscured screenshot cell -- flagged for a final visual confirmation against
the real screen before this catalog is treated as gospel, per the Phase B
plan's own caveat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from analysis_engine.ordermatrix.gear_math import GearOrders
from analysis_engine.signal.order_spectrum import OrderSpectrumResult, peak_magnitude_near_order
from analysis_engine.signal.units import g_to_mps2, to_db_mps2
from analysis_engine.signal.windowed_stats import DEFAULT_N_WINDOWS, WindowedStatsResult, compute_windowed_stats

UnitConvert = Literal["none", "g_to_mps2", "g_to_db_mps2"]


@dataclass(frozen=True)
class ParameterSpec:
    name: str  # exact catalog key, e.g. "RMS max (m/s2)" or "IN_H1(g)"
    kind: Literal["windowed", "harmonic"]
    unit_convert: UnitConvert = "none"
    default_full_scale: float = 10.0

    # windowed-only (kind == "windowed"); ignored for "harmonic"
    stat_field: str | None = None  # SignalStats field name, e.g. "rms", "peak"
    reduction: Literal["max", "avg"] | None = None

    # harmonic-only (kind == "harmonic"); ignored for "windowed"
    order_fn: Callable[[GearOrders], float | None] | None = None
    tolerance: float = 0.5


def _order_of(attr: str, multiplier: float = 1.0) -> Callable[[GearOrders], float | None]:
    def fn(gear_orders: GearOrders) -> float | None:
        base = getattr(gear_orders, attr)
        return None if base is None else base * multiplier

    return fn


def _constant_order(value: float) -> Callable[[GearOrders], float | None]:
    def fn(gear_orders: GearOrders) -> float | None:  # noqa: ARG001
        return value

    return fn


def _unit_variants(base_full_scale_g: float) -> dict[UnitConvert, float]:
    """Derives default_full_scale for the m/s2 and dB(m/s2) variants from the
    bare-units (g) default, using the same conversion the runtime values go
    through, so the full-scale and the value stay in the same unit space."""
    mps2 = g_to_mps2(base_full_scale_g)
    return {"none": base_full_scale_g, "g_to_mps2": mps2, "g_to_db_mps2": to_db_mps2(mps2)}


# (display label, SignalStats field name, bare-unit default full_scale)
_BASE_STATS: tuple[tuple[str, str, float], ...] = (
    ("Mean", "mean", 10.0),
    ("Variance", "variance", 10.0),
    ("Skewness", "skewness", 10.0),
    ("Kurtosis", "kurtosis", 30.0),
    ("RMS", "rms", 10.0),
    ("PK", "peak", 20.0),  # NB: display label is "PK", SignalStats field is "peak"
    ("Crest", "crest", 5.0),
)
_UNIT_FAMILY_LABELS = ("RMS", "PK")  # only these two also get m/s2 + dB m/s2 variants

# (display label, order_fn, bare-unit(g) default full_scale)
_HARMONICS: tuple[tuple[str, Callable[[GearOrders], float | None], float], ...] = (
    ("IN_H1", _order_of("mesh_order", 1.0), 20.0),
    ("IN_H2", _order_of("mesh_order", 2.0), 20.0),
    ("IN_H3", _order_of("mesh_order", 3.0), 20.0),
    ("CM_H1", _order_of("final_drive_mesh_order", 1.0), 20.0),
    ("CM_H2", _order_of("final_drive_mesh_order", 2.0), 20.0),
    ("CM_H3", _order_of("final_drive_mesh_order", 3.0), 20.0),
    ("IN_S1.0", _constant_order(1.0), 20.0),
    ("OUT_S1.0", _order_of("layshaft_order", 1.0), 20.0),
    # OUTPUT_S1.0 is approximated by the pre-final-drive output_shaft_order --
    # a known simplification in this codebase's gear model, not a real gap.
    ("OUTPUT_S1.0", _order_of("output_shaft_order", 1.0), 20.0),
)

_REDUCTION_LABEL: dict[str, str] = {"max": "max", "avg": "Avg"}  # base-stat names: lowercase "max", capitalized "Avg"
_HARMONIC_UNIT_SUFFIX: dict[UnitConvert, str] = {"none": "g", "g_to_mps2": "m/s2", "g_to_db_mps2": "dB m/s2"}


def _build_catalog() -> dict[str, ParameterSpec]:
    catalog: dict[str, ParameterSpec] = {}

    for label, stat_field, base_full_scale in _BASE_STATS:
        for reduction in ("max", "avg"):
            name = f"{label} {_REDUCTION_LABEL[reduction]}"
            catalog[name] = ParameterSpec(
                name=name,
                kind="windowed",
                unit_convert="none",
                default_full_scale=base_full_scale,
                stat_field=stat_field,
                reduction=reduction,
            )
        if label in _UNIT_FAMILY_LABELS:
            variants = _unit_variants(base_full_scale)
            for unit_convert, unit_label in (("g_to_mps2", "m/s2"), ("g_to_db_mps2", "dB m/s2")):
                for reduction in ("max", "avg"):
                    name = f"{label} {_REDUCTION_LABEL[reduction]} ({unit_label})"
                    catalog[name] = ParameterSpec(
                        name=name,
                        kind="windowed",
                        unit_convert=unit_convert,
                        default_full_scale=variants[unit_convert],
                        stat_field=stat_field,
                        reduction=reduction,
                    )

    for label, order_fn, base_full_scale in _HARMONICS:
        variants = _unit_variants(base_full_scale)
        for unit_convert in ("none", "g_to_mps2", "g_to_db_mps2"):
            name = f"{label}({_HARMONIC_UNIT_SUFFIX[unit_convert]})"
            catalog[name] = ParameterSpec(
                name=name,
                kind="harmonic",
                unit_convert=unit_convert,
                default_full_scale=variants[unit_convert],
                order_fn=order_fn,
            )

    return catalog


PARAMETER_CATALOG: dict[str, ParameterSpec] = _build_catalog()
# 14 base + 8 unit-family + 27 harmonic = 49. `Speed`/`Time` context columns
# are NOT part of this catalog -- they are the existing rpm/time_s arrays,
# passed through for display, never graded.
assert len(PARAMETER_CATALOG) == 49


def _apply_unit_convert(value_g: float, unit_convert: UnitConvert) -> float:
    if unit_convert == "none":
        return value_g
    value_mps2 = g_to_mps2(value_g)
    if unit_convert == "g_to_mps2":
        return value_mps2
    return to_db_mps2(value_mps2)  # "g_to_db_mps2"


def _compute_one(
    spec: ParameterSpec,
    windowed: WindowedStatsResult,
    order_spec: OrderSpectrumResult,
    gear_orders: GearOrders,
) -> float | None:
    if spec.kind == "windowed":
        source = windowed.max if spec.reduction == "max" else windowed.avg
        base_value = source[spec.stat_field]
    else:  # "harmonic"
        target_order = spec.order_fn(gear_orders)
        if target_order is None:
            return None
        base_value = peak_magnitude_near_order(order_spec, target_order, tolerance=spec.tolerance)
    return _apply_unit_convert(base_value, spec.unit_convert)


def compute_parameter_catalog(
    signal,
    order_spec: OrderSpectrumResult,
    gear_orders: GearOrders,
    n_windows: int = DEFAULT_N_WINDOWS,
) -> dict[str, float]:
    """Computes every parameter in PARAMETER_CATALOG for one DC record.
    Harmonic parameters whose underlying GearOrders field is None (e.g.
    final_drive_mesh_order or layshaft_order not configured for this gear)
    are silently omitted from the returned dict, matching grade_dc_record's
    existing "skip stats with no master" pattern."""
    windowed = compute_windowed_stats(signal, n_windows=n_windows)
    values: dict[str, float] = {}
    for name, spec in PARAMETER_CATALOG.items():
        value = _compute_one(spec, windowed, order_spec, gear_orders)
        if value is not None:
            values[name] = value
    return values


def default_full_scale_by_param() -> dict[str, float]:
    return {name: spec.default_full_scale for name, spec in PARAMETER_CATALOG.items()}
