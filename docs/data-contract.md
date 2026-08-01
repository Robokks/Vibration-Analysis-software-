# NVH Data Contract (v1)

This document is the canonical spec for the boundary between the acquisition side
(today: a signal simulator; eventually: LabVIEW driving NI-DAQmx + PLC/OPC) and the
Python analysis side (`analysis-engine`, later `web-backend`). Anything that writes
test data — the simulator now, LabVIEW later — must conform to this contract.
Bump `CONTRACT_VERSION` on any breaking change.

## Storage split

- **Relational context** (what ran, on what unit, with what result) lives in a
  SQL database — SQLite for local dev/tests, Postgres in production. Models are
  defined once in `libs/nvh_contract` and shared by every consumer.
- **Raw signal / tach samples** live in Parquet files on disk, one file per DC
  record (a gear+direction run), referenced by path from the `dc_records` row.

## Directory layout for raw data

```
data/nvh/{plant_id}/{line_id}/{yyyy-mm-dd}/{test_run_id}/
    manifest.json                  # schema_version, model_id, calibration snapshot
    dc_{gear_label}_{direction}.parquet
```

### Parquet columns (per DC record)

| column | dtype | meaning |
|---|---|---|
| `sample_index` | int64 | 0-based sample counter |
| `time_s` | float64 | seconds since DC record start |
| `rpm` | float64 | instantaneous shaft speed, derived from the tach/encoder |
| `tach_pulse` | int8 | raw encoder pulse channel (0/1), source for `rpm` |
| `ch_<channel_name>` | float64 | one column per calibrated channel, e.g. `ch_vib_a`, `ch_mic` |

## Relational schema

```sql
CREATE TABLE models (
    model_id            TEXT PRIMARY KEY,
    model_name          TEXT NOT NULL,
    drive_teeth_json     TEXT NOT NULL,   -- {"N": 1, "R": 12, "I": 12, ...}
    idler_teeth_1_json   TEXT NOT NULL,   -- Master Entry screen's "IDLER SHAFT1 TEETH"
    idler_teeth_2_json   TEXT NOT NULL DEFAULT '{}',  -- "IDLER SHAFT2 TEETH"
    layshaft_teeth_json  TEXT NOT NULL,
    drive_shaft_bearing_roll_json TEXT NOT NULL DEFAULT '{}',  -- "DRIVE SHAFT BEARING ROLL" (order, direct entry)
    layshaft_bearing_roll_json    TEXT NOT NULL DEFAULT '{}',  -- "LAY SHAFT BEARING ROLL" (order, direct entry)
    fdr_teeth_json       TEXT NOT NULL DEFAULT '{}',  -- available final-drive variants, e.g. {"FDR1": 27, "FDR2": 30}
    fd_sel_json          TEXT NOT NULL DEFAULT '{}',  -- per-gear FDR selection, e.g. {"R": "FDR1"} ("FD SEL" column)
    ratios_json          TEXT NOT NULL    -- {"R": 3.753, "I": 4.105, ...}
);

CREATE TABLE test_runs (
    test_run_id      TEXT PRIMARY KEY,
    model_id         TEXT NOT NULL REFERENCES models(model_id),
    serial_number    TEXT NOT NULL,
    operator_id      TEXT,
    shift_number     TEXT,
    repeat_number    INTEGER NOT NULL DEFAULT 1,
    line_id          TEXT,
    station_id       TEXT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    overall_result   TEXT CHECK (overall_result IN ('PASS','FAIL','PENDING')) NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE dc_records (
    dc_id            TEXT PRIMARY KEY,
    test_run_id      TEXT NOT NULL REFERENCES test_runs(test_run_id),
    gear_label       TEXT NOT NULL,          -- e.g. 'R', 'I', 'II'
    -- direction cycle per gear: RU -> STYD -> STYC -> RD (PLC nvh_id 0/1/2/3;
    -- nvh_id -1 "no log" is a transport sentinel, never persisted here).
    -- Reverse (R) conventionally only logs RU/STYD/RD (no STYC) -- a
    -- data/config convention, not enforced by this CHECK (or by the
    -- SQLAlchemy ORM, which has no CheckConstraint on this column today).
    direction        TEXT CHECK (direction IN ('RU','STYD','STYC','RD')) NOT NULL,
    rpm_start        REAL NOT NULL,
    rpm_end          REAL NOT NULL,
    sample_rate_hz   REAL NOT NULL,
    parquet_path     TEXT NOT NULL,
    result           TEXT CHECK (result IN ('PASS','FAIL','PENDING')) NOT NULL DEFAULT 'PENDING',
    fail_reason_codes TEXT                  -- comma-separated, e.g. 'RMS_NOK,CRASH_NOISE'
);

CREATE TABLE channels (
    channel_id       TEXT PRIMARY KEY,
    dc_id            TEXT NOT NULL REFERENCES dc_records(dc_id),
    channel_name     TEXT NOT NULL,          -- e.g. 'vib_a', 'mic'
    sensor_type      TEXT,                   -- 'accelerometer' | 'microphone'
    units            TEXT NOT NULL,          -- 'g' | 'Pa' | 'V'
    sensitivity_mv_per_eu REAL,
    pregain_db       REAL DEFAULT 0,
    weighting_filter TEXT DEFAULT 'linear'
);

CREATE TABLE master_signatures (
    master_id        TEXT PRIMARY KEY,
    model_id         TEXT NOT NULL REFERENCES models(model_id),
    gear_label       TEXT NOT NULL,
    direction        TEXT NOT NULL,
    stat_name        TEXT NOT NULL,          -- see analysis_engine.grading.parameters.PARAMETER_CATALOG (49 possible names)
    domain           TEXT CHECK (domain IN ('time','speed')) NOT NULL,
    mean_value       REAL NOT NULL,
    band_min         REAL NOT NULL,
    band_max         REAL NOT NULL,
    full_scale       REAL NOT NULL,
    trial_count      INTEGER NOT NULL,
    created_at       TEXT NOT NULL
);

CREATE TABLE grading_results (
    dc_id            TEXT NOT NULL REFERENCES dc_records(dc_id),
    stat_name        TEXT NOT NULL,
    domain           TEXT NOT NULL,
    g_level          INTEGER NOT NULL,       -- 1..10
    ok_flag          INTEGER NOT NULL,       -- 0/1
    PRIMARY KEY (dc_id, stat_name, domain)
);

CREATE TABLE spc_points (
    serial_number    TEXT NOT NULL,
    model_id         TEXT NOT NULL,
    gear_label       TEXT NOT NULL,
    direction        TEXT NOT NULL,
    stat_name        TEXT NOT NULL,
    value            REAL NOT NULL,
    recorded_at      TEXT NOT NULL
);

-- Phase C: named master profiles (the real system's "NVH-PROGRAM", e.g. "REVA")
CREATE TABLE master_profiles (
    model_id         TEXT NOT NULL REFERENCES models(model_id),
    program_name     TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    PRIMARY KEY (model_id, program_name)
);

-- Phase C: two-stage LIMIT (auto, imported from master_signatures) / THRESHOLD
-- (manually tuned margin) config, matching the real Limit Config.vi screen's
-- STEP | CHANNEL | PARAMETER | ORDERS | LIMIT (LOW/HIGH) | THRESHOLD (LOW/HIGH).
CREATE TABLE limit_configs (
    model_id         TEXT NOT NULL REFERENCES models(model_id),
    program_name     TEXT NOT NULL,
    gear_label       TEXT NOT NULL,          -- STEP = gear_label + direction
    direction        TEXT NOT NULL,
    channel_name     TEXT NOT NULL,          -- CHANNEL; defaults to "vib_a" -- see multi-channel note below
    stat_name        TEXT NOT NULL,          -- PARAMETER; see analysis_engine.grading.parameters.PARAMETER_CATALOG
    order_number     REAL,                   -- ORDERS; the resolved harmonic order, NULL for non-harmonic params
    limit_low        REAL NOT NULL,
    limit_high       REAL NOT NULL,
    threshold_low    REAL NOT NULL DEFAULT 0.0,
    threshold_high   REAL NOT NULL DEFAULT 0.0,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (model_id, program_name, gear_label, direction, channel_name, stat_name)
);

-- Phase E: Table Config, matching the real Table Config.vi screen's two
-- tabs ("GEAR & NVH" -- which gear+direction combos show and in what
-- order; "PARAMETER CONFIG" -- which parameters show). Row presence in
-- either table = included; absence = excluded (no separate boolean flag,
-- matching limit_configs' own idiom).
CREATE TABLE table_config_steps (
    model_id         TEXT NOT NULL REFERENCES models(model_id),
    program_name     TEXT NOT NULL,
    gear_label       TEXT NOT NULL,          -- "GEAR & NVH" tab's row identity: gear_label + direction
    direction        TEXT NOT NULL,
    channel_name     TEXT NOT NULL,          -- CHAN[NEL] dropdown
    step_order       INTEGER NOT NULL,       -- S.NO; the resolved STEP (see Phase D's CodeResultRow.step)
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (model_id, program_name, gear_label, direction, channel_name)
);

CREATE TABLE table_config_parameters (
    model_id         TEXT NOT NULL REFERENCES models(model_id),
    program_name     TEXT NOT NULL,
    channel_name     TEXT NOT NULL,
    stat_name        TEXT NOT NULL,          -- PARAMETER_CATALOG key, or "Speed"/"Time" -- see Phase E notes below
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (model_id, program_name, channel_name, stat_name)
);
```

## Grading formula (G1–G10 ladder)

Given a master signature's `band_min`/`band_max`/`full_scale`:

```
delta_percent = (band_max - band_min) / 2 / full_scale * 100   # the "G5%" step
delta_value   = delta_percent / 100 * full_scale = (band_max - band_min) / 2
G_n           = mean_value + (n - 5) * delta_value                for n in 1..10
```

(`full_scale` cancels out of the round trip — it only matters for the percent
representation, e.g. for display; the value-space ladder step is simply half
the master band width.)

An observed stat value is classified into the nearest `G_n`; `ok_flag` is 1 when the
value falls within the configured pass window around G5 (grade bands widen as `n`
moves away from 5 in either direction), 0 otherwise.

## Phase B: NVH Parameter Catalog

The real Master Entry "Parameters" screen configures **49 graded parameters**
per DC record, plus 2 non-graded context columns (`Speed`, `Time` — the
existing `rpm`/`time_s` arrays, display-only, never fed into
grading/masters/SPC). All 49 names live in
`analysis_engine.grading.parameters.PARAMETER_CATALOG` — that module is the
single source of truth; nothing else hardcodes a parameter name.

### The 3 parameter families

| Family | Count | Name pattern | Source |
|---|---|---|---|
| Base | 14 | `{Mean,Variance,Skewness,Kurtosis,RMS,PK,Crest} {max,avg}` (note: lowercase "max", capitalized "Avg") | windowed `SignalStats`, bare/native units |
| Unit-family | 8 | `{RMS,PK} {max,avg} ({m/s2}\|{dB m/s2})` — RMS/PK only | same windowed values, unit-converted |
| Harmonic | 27 | `{IN_H1,IN_H2,IN_H3,CM_H1,CM_H2,CM_H3,IN_S1.0,OUT_S1.0,OUTPUT_S1.0}({g}\|{m/s2}\|{dB m/s2})` — no leading space before the suffix | order-spectrum peak lookup, unit-converted |

### Unit conversions (documented, overridable assumptions)

- `STANDARD_GRAVITY_MPS2 = 9.80665` (g -> m/s^2, exact standard-gravity constant).
- `DB_REFERENCE_MPS2 = 1e-6` (ISO 1683 acceleration-level reference; the
  client has not confirmed which reference they use — override if a
  different convention is specified later). `dB = 20*log10(|value_mps2| /
  reference)`, floored before the log to keep near-zero inputs finite.

### Windowing approximation

"max"/"avg" for the base/unit-family parameters require **windowed
statistics**: the signal is split into `n_windows` contiguous time-slices
(default 10, see `analysis_engine.signal.windowed_stats.
DEFAULT_N_WINDOWS`), each stat is computed per window via the existing
`compute_stats()`, and reduced to the worst-case window ("max", literal
max — not max-of-abs) and the mean across windows ("avg"). This is a
configurable **stand-in for an unconfirmed real per-revolution windowing
scheme** — revisit if/when the client's actual convention is specified.

### Harmonic order mapping

Each harmonic parameter is a single `peak_magnitude_near_order()` lookup
against the whole-run order spectrum (no windowing), at an order resolved
from `GearOrders`:

| Parameter | Order | Notes |
|---|---|---|
| `IN_H1`/`IN_H2`/`IN_H3` | 1x/2x/3x of `mesh_order` | |
| `CM_H1`/`CM_H2`/`CM_H3` | 1x/2x/3x of `final_drive_mesh_order` | CM = DIFF (differential/final-drive harmonics). Absent for a gear with no `fd_sel`/`fdr_teeth` configured (`final_drive_mesh_order is None`) — graceful degradation, matches `grade_dc_record`'s existing "skip stats with no master" pattern. |
| `IN_S1.0` | constant order 1.0 | The drive shaft's own reference order (`gear_math.py`'s "drive shaft has order 1" convention). |
| `OUT_S1.0` | `layshaft_order` | Layshaft/countershaft order. Absent when `layshaft` teeth = 0. |
| `OUTPUT_S1.0` | `output_shaft_order` | Accepted approximation for "the final output shaft" even though this is technically pre-final-drive in this codebase's gear model — a documented simplification, not a gap to fix now; the true post-final-drive shaft order would need a new ring-gear-teeth field this contract doesn't have. |

All 49 parameters are tagged `domain="time"` (matching the existing
`Domain` enum's default) rather than adding a third value for
order-domain harmonics — avoids a `CHECK` constraint migration; also a
documented simplification.

## Report/API contract versioning

Two independent version numbers govern two independent boundaries — do not
conflate them:

- `nvh_contract.CONTRACT_VERSION` (below) governs the **Parquet/DB manifest
  boundary**. Phase B needed **zero migration** here — every `stat_name`
  column is an unconstrained `TEXT`/`String`, so it transparently carries
  49 possible values instead of 7.
- `nvh_api_schemas.REPORT_SCHEMA_VERSION = "2.1"` governs the separate
  **analysis-engine -> nvh_api_schemas report-shape boundary**. This bumped
  to `2.0` because `DcAnalysisResultOut.stats: SignalStatsOut` (7 hardcoded
  fields) was replaced by `DcAnalysisResultOut.parameters: dict[str,
  float]` (a breaking shape change) — but that change has nothing to do
  with the Parquet/DB contract, so it does not bump `CONTRACT_VERSION`.

  This constant has no runtime enforcement anywhere in the codebase — it's
  a documentation-only signal for consumers. Phase D's bump (`2.0` ->
  `2.1`) is the first change since the `2.0` bump to touch this boundary
  (Phase C's changes were DB-only) and is purely additive (new required
  `low`/`high` fields on `EnvelopeCheckOut`, one new `CodeResultReportOut`/
  `CodeResultRowOut` pair, no removals) — establishing, for the first time,
  an explicit convention: **integer bump** (`X.0`) when a field is
  removed/renamed/replaced (a genuine breaking change for any consumer),
  **decimal bump** (`X.Y`) when fields/schemas are purely added.

## Phase C: Master Profiles & Two-Stage Limits

Source of truth: the real system's `Limit Config.vi` screen (`STEP |
CHANNEL | PARAMETER | ORDERS | LIMIT (LOW) | THRESHOLD (LOW) | LIMIT (HIGH)
| THRESHOLD (HIGH)`, with "Save" and "Import From MASTER" actions) and its
`MASTER SETUP` screen (`MODEL NAME` + `NVH-PROGRAM` dropdowns, e.g.
"e2o-48V" + "REVA").

**Scoping.** Master signatures (`master_signatures`, Phase A/B, unchanged)
stay a single auto-computed band per model — building masters from trial
data is exactly as it was before this phase. A named profile
(`master_profiles.program_name`, the "NVH-PROGRAM") covers *all*
gears/directions for a model; the `limit_configs` table's
`gear_label`+`direction` (STEP) and `channel_name`/`stat_name`
(CHANNEL/PARAMETER) disambiguate rows within one profile. Multiple
programs for the same model each independently "Import From MASTER" the
same band (`import_limit_config_from_masters()` in
`analysis_engine.grading.limit_config`), then diverge only in their
manually-tuned `threshold_low`/`threshold_high` margins.

**LIMIT/THRESHOLD formula.** `LIMIT_LOW`/`LIMIT_HIGH` are a straight copy
of the master's `band_min`/`band_max` (the "Import From MASTER" step).
`THRESHOLD_LOW`/`THRESHOLD_HIGH` are manually-tunable margins, defaulted to
`0.0` on import. A value passes iff:
```
effective_low  = limit_low  - threshold_low
effective_high = limit_high + threshold_high
ok = effective_low <= value <= effective_high
```
This is a genuinely new, parallel pass/fail path
(`check_value_with_threshold()`/`grade_dc_record_with_limits()` in
`analysis_engine.grading.limit_config`) — it does not replace or modify
`envelope_check.check_value()`/`grade_dc_record()`'s existing G4-G6-window
behavior, which stays exactly as it was in Phase A/B. The G1-G10 ladder
(`g_level`) is still computed from the LIMIT band for informational/
diagnostic display; it is not the pass/fail source once a limit config is
supplied to `pipeline.analyze_dc_record(..., limit_configs=...)`.

**Multi-channel simplification (documented).** `channel_name` exists on
`limit_configs` to match the real screen, but the analysis pipeline
(`analyze_dc_record`) only ever grades one channel per call — there is no
multi-channel orchestration anywhere yet. It defaults to `"vib_a"`
everywhere for now; real multi-channel grading is a separate, later
concern.

A real exported grading-result sheet (a flat per-unit report, the target
shape for Phase D, not built yet) confirms this formula in practice: a row
like `IN_H1 | order=13 | LOW=26 | ACTUAL=35.369 | HIGH=35 -> NOK` shows
`LOW`/`HIGH` as already-combined effective bounds, exactly as derived
above, compared directly against the observed value.

## Phase D: Flat CODE-RESULT Grading Output

Source of truth: a real exported grading-result sheet (client screenshot),
columns `STEP | GEAR_DIRECTION | CHANNEL | PARAMETER | ORDERS | LOW |
ACTUAL | HIGH | UNIT | OK/NOK` — one row per (gear+direction, channel,
parameter) per test unit, e.g. `1 | I_STYC | vib_a | IN_H1(g) | 13 | 26 |
35.369 | 35 | g | NOK`. Built by `analysis_engine.reports.code_result.
build_code_result_report()` directly from a `list[DcAnalysisResult]`,
following the same "compose from live pipeline output, don't widen it"
pattern as Consolidated/Detailed/Summary.

**STEP vs GEAR_DIRECTION naming note.** The Phase C `limit_configs` schema
comment above (`gear_label -- STEP = gear_label + direction`) uses "STEP"
as shorthand for the natural-key identity `(gear_label, direction)`. Here,
STEP and GEAR_DIRECTION are two separate rendered columns: STEP is a
1-based sequential ordinal over the order gear+direction combinations were
run (`enumerate(results, start=1)`, matching the order the caller supplies
`results` in — there is no separate "test sequence" concept modeled
anywhere else in this codebase yet), while GEAR_DIRECTION is the human
string label `f"{gear_label}_{direction}"` (e.g. "I_STYC" / "R_RU"). Both
still identify the same underlying (gear_label, direction) pair — this is
not a contradiction of the Phase C comment, just two different renderings
of the same identity that a future reader could otherwise conflate.

**LOW/HIGH resolution.** `EnvelopeCheckResult` now carries the resolved
bounds directly (`low`/`high`), populated from whichever grading path
produced it:
- master+G-ladder path (`envelope_check.check_value`): `low =
  ladder.g_level_value(low_g)`, `high = ladder.g_level_value(high_g)` — the
  G4/G6-window bounds in value-space.
- LIMIT/THRESHOLD path (`limit_config.check_value_with_threshold`): `low =
  limit_low - threshold_low`, `high = limit_high + threshold_high` — the
  already-combined effective bounds. This matches the confirmed example row
  from the Phase C section above: `IN_H1 | order=13 | LOW=26 |
  ACTUAL=35.369 | HIGH=35 -> NOK`.

Only parameters present in a result's `grading.per_stat` get a row — a
parameter with no master/limit-config has no meaningful LOW/HIGH/OK-NOK to
show, matching `grade_dc_record`'s/`grade_dc_record_with_limits`'s existing
"skip stats with no master/config" pattern.

**ORDERS.** `PARAMETER_CATALOG[parameter].order_fn(gear_orders)` for
harmonic parameters, `None` for windowed base/unit-family parameters —
identical to the ORDERS resolution `seed_demo_data.py` already performs for
`LimitConfigRow.order_number`. `gear_orders` is looked up per row from a
`gear_orders_by_gear: dict[str, GearOrders]` map supplied by the caller,
keyed by `gear_label` only (`GearOrders`/`compute_gear_orders()` take no
direction argument at all — the order matrix is a property of the gear's
teeth/ratio, shared across all 4 directions). A gear missing from the map
degrades to `orders=None` for its rows rather than raising, matching this
codebase's dominant graceful-degradation style.

**UNIT.** Derived from `ParameterSpec.unit_convert` via
`analysis_engine.grading.parameters.unit_label_for()` /
`UNIT_LABEL_BY_CONVERT` (`"none" -> "g"`, `"g_to_mps2" -> "m/s2"`,
`"g_to_db_mps2" -> "dB m/s2"`) for all 49 parameters, not just harmonics.

**Documented assumption: unit label precision.** `"g"` is the physically
correct unit for `Mean`/`RMS`/`PK` (max+avg, 6 of 49 parameters) and for
all 9 whole-run harmonic-peak-magnitude parameters with
`unit_convert="none"` — 15/49 total, all literal acceleration-in-g values.
It is *not* physically precise for `Variance` (technically g², 2
parameters) or for `Skewness`/`Kurtosis`/`Crest` (dimensionless shape/ratio
statistics, no physical unit at all — 6 parameters) — 8/49 total.
`unit_convert` doesn't currently distinguish these cases; `"g"` is used as
a placeholder rather than introducing a new unit axis, matching this
codebase's existing practice of documenting rather than silently absorbing
such simplifications (cf. the dB-reference-constant and
windowing-approximation notes in the Phase B section above).

**Channel scoping.** `channel_name` defaults to `"vib_a"` for every row,
matching the existing single-channel-per-call simplification already
documented above — `analyze_dc_record` doesn't carry channel identity on
`DcAnalysisResult` yet, so `build_code_result_report` takes it as a
caller-supplied constant, not a per-result field.

**Not persisted yet (documented gap).** `nvh_contract.db.GradingResultRow`
stores only `g_level`/`ok_flag` per stat, not `low`/`high`. Like the other
report builders, `build_code_result_report` is built from live
`DcAnalysisResult` objects, not DB rows, so this is not a blocker today —
flagged here so a later milestone serving *historical* CODE-RESULT reports
from stored data knows to add `low`/`high` columns to `grading_results`
first.

## Phase E: Table Config

Source of truth: the real system's `Table Config.vi` screen, one window
with two tabs, both scoped per `(model_id, program_name, channel_name)`
like `limit_configs`:

- **"GEAR & NVH" tab**: a listbox headed `S.NO | PARAMETER NAMES` — despite
  the header, this column lists gear+direction combos (`R_RU, R_STYD,
  R_RD, I_RU, I_STYD, I_STYC, I_RD, II_RU, ...`), not catalog parameters;
  a client-side mislabel, not a modeling decision on this project's part.
  Reverse (`R`) only has 3 rows (no `STYC`), already consistent with this
  contract's existing convention (see `Direction`'s docstring and the
  `dc_records.direction` comment above). `S.NO` is the operator-assigned
  step position — `table_config_steps.step_order`.
- **"PARAMETER CONFIG" tab** (same window): a checkbox listbox, genuinely
  listing parameter names — `PARAMETER_CATALOG` keys plus
  `analysis_engine.grading.parameters.NON_GRADED_CONTEXT_COLUMNS =
  ("Speed", "Time")` (the existing non-graded `rpm`/`time_s` context
  columns). No ordering concept here, unlike the steps tab — just
  inclusion. `table_config_parameters`.

**Row presence = included; absence = excluded**, in both tables — no
separate boolean flag, matching this contract's existing dominant idiom
(`limit_configs`, `grade_dc_record`'s per-stat skip, etc.).

**`apply_table_config()`** (`analysis_engine.reports.table_config`) is a
pure post-processing filter over Phase D's `build_code_result_report()`
output — `code_result.py` itself is unmodified. It (1) drops any row whose
`(gear_direction, channel_name)` has no configured step, (2) drops any row
whose `parameter` isn't in the configured parameter set, (3) overwrites
each surviving row's `step` with the *configured* `step_order`, and (4)
sorts by `(step_order, PARAMETER_CATALOG insertion rank)` — **not
alphabetically**; nothing in the real screen supports re-alphabetizing,
and `PARAMETER_CATALOG`'s own insertion order (base stats, then
unit-family, then harmonics) is the only ordering this contract has ever
established. To be precise about what changes and what doesn't: Phase D's
`step` was always documented as real caller-supplied run-order semantics
(the order `results` were passed to `build_code_result_report()`), not a
placeholder awaiting this screen — Phase E supplies the missing
*authoritative*, operator-configured ordering that was simply absent
before, via `apply_table_config()`, rather than replacing a stand-in.

Like Phase D, `apply_table_config()` can only narrow/reorder what was
already produced — a parameter selected in `table_config_parameters` but
never graded (no master/limit-config) still gets no row, since
`build_code_result_report()` never emitted one for it.

**Documented gap: `Speed`/`Time` are currently inert.** They're modeled in
`table_config_parameters`/`NON_GRADED_CONTEXT_COLUMNS` for 1:1 schema
fidelity with the real screen's checklist, but no report builder in this
codebase (`Consolidated`/`Detailed`/`Summary`/`CodeResult`) ever produces a
Speed/Time row — `compute_parameter_catalog()` never touches `rpm`/
`time_s`. Selecting them in a Table Config has no filtering effect today;
revisit if/when a future report type surfaces per-parameter Speed/Time
rows.

**No `nvh_api_schemas` changes.** Confirmed Phase C added zero wire
schemas for its own new persisted tables (`master_profiles`/
`limit_configs`); Phase E follows the identical precedent for
`table_config_steps`/`table_config_parameters`. `CodeResultReportOut`
already covers `apply_table_config()`'s output unchanged, since it's still
exactly a `CodeResultReport`, just filtered/reordered.

## Versioning

- `CONTRACT_VERSION = "1.0"` (see `nvh_contract.CONTRACT_VERSION`).
- Any producer (simulator today, LabVIEW later) must stamp this version in
  `manifest.json` and any consumer must reject a mismatched major version.
