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
- `nvh_api_schemas.REPORT_SCHEMA_VERSION = "2.0"` governs the separate
  **analysis-engine -> nvh_api_schemas report-shape boundary**. This bumped
  because `DcAnalysisResultOut.stats: SignalStatsOut` (7 hardcoded fields)
  was replaced by `DcAnalysisResultOut.parameters: dict[str, float]` (a
  breaking shape change) — but that change has nothing to do with the
  Parquet/DB contract, so it does not bump `CONTRACT_VERSION`.

## Versioning

- `CONTRACT_VERSION = "1.0"` (see `nvh_contract.CONTRACT_VERSION`).
- Any producer (simulator today, LabVIEW later) must stamp this version in
  `manifest.json` and any consumer must reject a mismatched major version.
