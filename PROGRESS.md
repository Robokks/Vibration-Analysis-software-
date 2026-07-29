# Development Progress Log

Running record of work done on this project, with timestamps, so progress is
visible in the repo itself rather than only in chat history. Newest entries
at the top. Updated at regular intervals as work continues.

---

## 2026-07-29 14:24 UTC — Phase B: Named 49-parameter grading framework
**Commit:** `5603a1d`

Replaced the generic 7-stat grading pipeline (`mean/variance/skewness/
kurtosis/rms/peak/crest`) with the real Master Entry screen's 49 named
parameters, confirmed directly from a client screenshot:

- **14 base** parameters: `{Mean, Variance, Skewness, Kurtosis, RMS, PK,
  Crest} x {max, avg}` — new windowed-statistics machinery
  (`signal/windowed_stats.py`) segments each DC record into sub-windows and
  reduces to worst-case ("max") and mean-across-windows ("avg").
- **8 unit-family** parameters: RMS/PK only, each also in `(m/s2)` and
  `(dB m/s2)` — new `signal/units.py` (g→m/s² conversion, dB transform).
- **27 harmonic** parameters: `IN_H1-3`, `CM_H1-3` (= DIFF), `IN_S1.0`,
  `OUT_S1.0`, `OUTPUT_S1.0`, each in `(g)`/`(m/s2)`/`(dB m/s2)` — revived the
  previously-unused `peak_magnitude_near_order()` order-spectrum lookup,
  mapped to `GearOrders` fields from Phase A.
- New `grading/parameters.py`: `PARAMETER_CATALOG` (single source of truth
  for all 49 names) + `compute_parameter_catalog()` orchestration.
- `DcAnalysisResult.stats: SignalStats` (7 fixed fields) →
  `.parameters: dict[str, float]` (49 possible keys); same reshape in the
  `nvh_api_schemas` report contract (`SignalStatsOut` deleted, new
  `REPORT_SCHEMA_VERSION = "2.0"` for that boundary — kept independent of
  `nvh_contract.CONTRACT_VERSION`, which needed zero migration since
  `stat_name` columns were always unconstrained text).
- Ripple-through across 15 files (seed script, CLI demo, all affected
  tests) + 3 new test files (units, windowing, parameter catalog).
- Fixed a real bug surfaced along the way: the simulator's gear-mesh
  harmonic amplitudes were fully deterministic, producing a razor-thin
  G-ladder band that false-failed the demo's healthy unit once harmonics
  were graded — added small per-trial amplitude jitter to
  `nvh_simulator/generators.py` to fix it.
- **Result:** 108/108 tests passing across all packages; CLI demo verified
  end-to-end.

## 2026-07-29 11:16 UTC — Phase A: Core domain model reconciliation
**Commit:** `2e9bfca`

Reconciled the domain model against the real client LabVIEW system
(reverse-engineered from screenshots/docs of the actual "Vibro-O-Matic
Analyzer" EOL test system):

- `Direction` enum extended from 2 values (`RU`, `RD`) to the real 4-value
  cycle: `RU` (run-up) → `STYD` (steady-drive) → `STYC` (steady-coast) →
  `RD` (run-down), matching PLC `nvh_id` 0/1/2/3 (`-1` "no log" is a
  transport sentinel, never persisted).
- New `nvh_contract/gear_ids.py`: PLC-boundary `gear_id` (0-7 int) ↔
  `gear_label` lookup (`0=N, 1=R, 2=I, 3=II, 4=III, 5=IV, 6=V`).
- `GearTeeth`/`GearOrders` (order matrix) extended: second idler shaft
  (`idler_shaft_1`/`idler_shaft_2`), bearing-roll order pass-through
  (`drive_shaft_bearing_roll`, `layshaft_bearing_roll`), and final-drive
  selection (`fdr_teeth` variants + per-gear `fd_sel`).
- `Model`/`ModelRow` mirrored with the same new fields (new columns
  default to `{}` so existing model definitions don't need updating).
- Full ripple-through rename sweep (`idler_shaft` → `idler_shaft_1`) across
  every call site; **91/91 tests passing.**

## 2026-07-29 05:54 UTC — Report GUI M0: design tokens, report assembly, API schemas, demo data
**Commit:** `3b0ed6e`

- `design-tokens` package: shared visual language (colors, type roles,
  gear-glyph SVG asset) for the future web + Qt UIs.
- `analysis_engine.reports`: `ConsolidatedReport`/`DetailedReport`/
  `SummaryReport` builders on top of the Phase 1 pipeline output, plus a
  generic `to_jsonable()` serializer.
- `libs/nvh_api_schemas`: pydantic wire schemas mirroring the report layer,
  contract-tested against real analysis-engine output so the API and the
  Qt/web clients can't silently drift apart.
- `web-backend/scripts/seed_demo_data.py`: first end-to-end persistence
  pipeline (Parquet + SQLite rows) — closes the gap between the simulator's
  in-memory signals and the data contract's on-disk/DB shapes.
- **74/74 tests passing.**

## 2026-07-28 17:20 UTC — Phase 1: NVH data contract, analysis engine, and simulator (MVP)
**Commit:** `02af3fe`

Initial build-out, driven entirely by a signal simulator (no hardware
available):

- `libs/nvh_contract`: the single source-of-truth data contract (pydantic
  models + SQLAlchemy ORM + Parquet I/O), documented in
  `docs/data-contract.md`.
- `nvh_simulator`: synthesizes gearbox NVH signals (gear-mesh order content
  on a speed ramp, plus injectable faults) with known ground truth, so the
  analysis side can be built and tested before any real hardware exists.
- `analysis_engine`: order-matrix math (teeth counts → order numbers),
  signal statistics, FFT/order-spectrum/order-tracking, G1–G10 envelope
  grading, crash-noise/slippage fault detection, SPC (X-chart/histogram).
- End-to-end CLI demo tying it all together: build a master signature from
  known-good trials, then PASS/FAIL a healthy and a faulted unit with no
  hardware and no web UI involved.

---

## What's next

Per the approved reconciliation plan (Phases A–E, reconciling the domain
model against the real LabVIEW system before building the web/Qt Report
GUI in M1):

- **Phase C** (not started): named master profiles (`NVH-PROGRAM`) +
  two-stage LIMIT (auto-computed) / THRESHOLD (manually tuned) limit
  configuration.
- **Phase D** (not started): flat CODE-RESULT-style grading output table,
  matching the real system's report shape.
- **Phase E** (not started): table/report configuration model (which
  columns/parameters show where).
- **M1** (after A–E): FastAPI backend + web/Qt Report GUI, built against
  the now-reconciled domain shapes.
