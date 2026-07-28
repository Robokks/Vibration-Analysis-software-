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
    idler_teeth_json     TEXT NOT NULL,
    layshaft_teeth_json  TEXT NOT NULL,
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
    direction        TEXT CHECK (direction IN ('RU','RD')) NOT NULL,
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
    stat_name        TEXT NOT NULL,          -- 'mean'|'variance'|'skewness'|'kurtosis'|'rms'|'peak'|'crest'
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

## Versioning

- `CONTRACT_VERSION = "1.0"` (see `nvh_contract.CONTRACT_VERSION`).
- Any producer (simulator today, LabVIEW later) must stamp this version in
  `manifest.json` and any consumer must reject a mismatched major version.
