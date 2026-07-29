# Development Progress Log

Running record of work done on this project, with timestamps, so progress is
visible in the repo itself rather than only in chat history. Newest entries
at the top. Updated at regular intervals as work continues.

---

## 2026-07-29 16:19 UTC — Phase E: Table Config (which STEP/PARAMETER rows show, and in what order)

Resolved via real client screenshots of the LabVIEW `Table Config.vi`
screen (previously only a one-line placeholder description in this log),
which turned out to be one window with two tabs, both scoped per
`(model_id, program_name, channel_name)` like `limit_configs`:

- **"GEAR & NVH" tab** (a client-side mislabeled `PARAMETER NAMES` column
  that actually lists gear+direction combos, e.g. `R_RU, R_STYD, R_RD,
  I_RU, I_STYD, I_STYC, ...` — Reverse correctly has no `STYC` row,
  matching the already-documented convention) → new
  `table_config_steps` table / `TableConfigStepEntry`: which
  gear+direction steps are included, and their `step_order`.
- **"PARAMETER CONFIG" tab** (a genuine checkbox list of the 49 catalog
  parameters plus `Speed`/`Time`) → new `table_config_parameters` table /
  `TableConfigParameterEntry`: which parameters are included. New
  `analysis_engine.grading.parameters.NON_GRADED_CONTEXT_COLUMNS =
  ("Speed", "Time")` constant to represent the latter two.
- Row presence = included, absence = excluded in both — no separate
  boolean flag, matching `limit_configs`' own idiom.
- New `analysis_engine.reports.table_config.apply_table_config()`: a pure
  post-processing filter over Phase D's `build_code_result_report()`
  output (`code_result.py` itself untouched) — drops rows for
  unconfigured steps/parameters, overwrites each surviving row's `step`
  with the *configured* `step_order` (replacing Phase D's caller-list-order
  placeholder now that a real ordering exists), and sorts by
  `(step_order, PARAMETER_CATALOG insertion rank)` — explicitly **not**
  alphabetically, a real bug a Plan sub-agent caught in the draft design
  before implementation.
- `seed_demo_data.py` now persists a demo Table Config (the one
  gear+direction+channel the demo exercises, `step_order=1`, every
  currently-graded parameter included) via `session.merge()` — required,
  not stylistic: `test_seed_is_rerunnable_without_error` already reruns
  `seed()` against the same DB, and `session.add()` would have reproduced
  the exact historical `LimitConfigRow` idempotency bug Phase C already
  fixed once. Verified the rerun manually in addition to the test.
- Explicitly no `nvh_api_schemas` changes (confirmed Phase C set this
  precedent for its own new persisted tables — zero wire schemas either;
  `CodeResultReportOut` already covers the filtered report's shape
  unchanged) and no `code_result.py` changes (Phase E composes with Phase
  D's output rather than modifying it).
- Documented, not silently absorbed: `Speed`/`Time` are modeled in the
  parameter config for 1:1 fidelity with the real screen's checklist, but
  are currently inert — no report builder in this codebase produces a
  Speed/Time row to filter yet.
- Planned via a Plan sub-agent validating the design against real
  client screenshots and the actual code (same workflow as prior phases)
  — besides the alphabetical-sort bug, it corrected the test-file
  convention (no new `nvh_contract` test files — `test_models.py`/
  `test_db.py` are cross-cutting, single files per package, not
  per-model), confirmed the `nvh_api_schemas`/`seed_demo_data.py` scoping
  decisions above by reading the actual Phase C diff rather than assuming
  precedent, and added a defensive channel-mismatch check to
  `apply_table_config()`.
- **Result:** 146/146 tests passing across every package (14 new: 4 in
  `test_models.py`, 3 in `test_db.py`, 7 in the new
  `test_table_config.py`, plus extended assertions in
  `test_seed_populates_all_contract_tables`); CLI demo and
  `seed_demo_data.py` re-verified end-to-end, including a manual
  double-run confirming idempotency.

## 2026-07-29 15:39 UTC — Phase D: Flat CODE-RESULT grading output table

Built the flat, per-row grading output table matching the real system's
exported grading-result sheet, confirmed from a client screenshot: `STEP |
GEAR_DIRECTION | CHANNEL | PARAMETER | ORDERS | LOW | ACTUAL | HIGH | UNIT |
OK/NOK`, one row per (gear+direction, channel, parameter) per test unit:

- Closed the gap flagged going into this phase: `EnvelopeCheckResult`
  (shared by both the master/G-ladder path and Phase C's LIMIT/THRESHOLD
  path) gained `low`/`high` resolved-bound fields — `envelope_check.
  check_value()` populates them from the G4/G6-window's `GLadder.
  g_level_value()`, `limit_config.check_value_with_threshold()` threads
  through the `effective_low`/`effective_high` it was already computing
  but discarding. Purely additive: only 2 construction sites repo-wide,
  zero direct constructions in tests.
- New `analysis_engine.reports.code_result`: `CodeResultRow`/
  `CodeResultReport`/`build_code_result_report()`, following the exact
  `consolidated.py`/`detailed.py`/`summary.py` pattern (built from live
  `DcAnalysisResult` objects, never DB rows). Takes a
  `gear_orders_by_gear: dict[str, GearOrders]` map (keyed by gear_label,
  since the order matrix has no direction dependence) rather than widening
  `DcAnalysisResult` itself, keeping every existing report/schema
  untouched — confirmed zero consumers of those types exist yet anywhere
  in `web-backend/`/`qt-app/`/`web-frontend/`.
- Exposed `parameters.UNIT_LABEL_BY_CONVERT`/`unit_label_for()` (was a
  private harmonic-only helper) as the UNIT column's source for all 49
  parameters — documented explicitly that `"g"` is a placeholder, not a
  precise label, for `Variance`/`Skewness`/`Kurtosis`/`Crest` (8 of 49
  parameters are dimensionless or g² and don't have a real "g" unit).
- `nvh_api_schemas`: `EnvelopeCheckOut` gained `low`/`high`; new
  `CodeResultRowOut`/`CodeResultReportOut`. `REPORT_SCHEMA_VERSION` bumped
  `2.0` -> `2.1`, establishing (this constant has zero runtime consumers,
  it's documentation-only) an explicit convention going forward: integer
  bump for breaking/removed fields, decimal bump for purely-additive ones.
- Planned via a Plan sub-agent validating the design against the real
  code (same workflow as Phase A/B) — it caught the base-parameter unit
  label count being off (10 non-unit-family base entries, not 12, and the
  physical-unit imprecision affecting 8/49 params specifically, not just
  "some"), confirmed `REPORT_SCHEMA_VERSION` has no runtime enforcement
  anywhere (strengthening the case for treating this bump as establishing
  a new convention rather than just following one), and confirmed
  `reports/types.py` is dead code not to be used as a pattern reference.
- New `docs/data-contract.md` "Phase D" section: STEP-vs-GEAR_DIRECTION
  disambiguation against Phase C's existing informal "STEP" comment,
  LOW/HIGH resolution per grading path, ORDERS/UNIT derivation, and a
  documented forward gap (`grading_results` DB table doesn't persist
  `low`/`high` yet — fine today since no report type in this codebase is
  built from DB rows, will matter once a future milestone serves
  *historical* CODE-RESULT reports from stored data).
- Deliberately out of scope, with reasoning recorded in the plan: no
  `seed_demo_data.py` demo-emission wiring (no real consumer yet to
  justify it, and Phase C's own precedent didn't add one either despite
  adding a whole new grading path); no `grading_results` DB schema change
  (see forward-gap note above); no `DcAnalysisResult`/`pipeline.py`
  changes (kept purely additive to the new report module only).
- **Result:** 132/132 tests passing across every package (analysis-engine,
  simulator, `nvh_contract`, `nvh_api_schemas`, design-tokens, web-backend);
  CLI demo and `seed_demo_data.py` re-verified end-to-end, unaffected.

## 2026-07-29 15:11 UTC — Phase C: Named master profiles + two-stage LIMIT/THRESHOLD config
**Commit:** `da80efd`

*(This entry was written retroactively — Phase C landed in a separate
session that didn't update this log at the time; recorded now for
continuity before Phase D builds on top of it.)*

Added named master profiles (the real system's "NVH-PROGRAM", e.g.
"REVA") and a two-stage LIMIT (auto-computed from masters, via "Import
From MASTER")/THRESHOLD (manually-tunable margin) limit-configuration
path, matching the real system's `Limit Config.vi` screen:

- `nvh_contract`: new `MasterProfile`/`LimitConfigEntry` pydantic models +
  `MasterProfileRow`/`LimitConfigRow` ORM tables (`master_profiles`,
  `limit_configs`).
- New `analysis_engine.grading.limit_config`: `import_limit_config_from_
  masters()` (the "Import From MASTER" button's backend — seeds
  `limit_low`/`limit_high` from the auto-computed master band,
  `threshold_low`/`threshold_high` defaulted to `0.0`), plus
  `check_value_with_threshold()`/`grade_dc_record_with_limits()` — a
  genuinely new, parallel pass/fail path (`effective_low/high = limit
  -+ threshold`) that does not replace or modify the existing
  master+G4-G6-window path.
- `pipeline.analyze_dc_record()` gained an optional `limit_configs`
  parameter; every existing call site (masters + G4-G6 window) behaves
  identically — purely additive.
- `seed_demo_data.py` now persists a "REVA" profile importing the master
  band (though the 3 demo scenarios still grade via the plain masters
  path, not `limit_configs`), and fixed a real idempotency bug along the
  way (`LimitConfigRow` used `session.add()` instead of `merge()`,
  breaking re-runs against the same DB).

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

- **Phase C** (done, `da80efd`): named master profiles (`NVH-PROGRAM`) +
  two-stage LIMIT (auto-computed) / THRESHOLD (manually tuned) limit
  configuration.
- **Phase D** (done): flat CODE-RESULT-style grading output table,
  matching the real system's report shape.
- **Phase E** (done): Table Config — which gear+direction/parameter rows
  show in a report, and in what order.
- **A–E complete.** Next: **M1** — FastAPI backend + web/Qt Report GUI,
  built against the now-reconciled domain shapes. (A GUI *scaffold* — app
  shell + placeholder screens, no live data wiring — already exists in
  `web-frontend/`/`qt-app/`, built ahead of M1 to have the visual shell
  ready; see their own READMEs.)
