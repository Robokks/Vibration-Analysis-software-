# Development Progress Log

Running record of work done on this project, with timestamps, so progress is
visible in the repo itself rather than only in chat history. Newest entries
at the top. Updated at regular intervals as work continues.

---

## 2026-07-30 19:15 UTC — Qt: real Order Spectrum + Order Tracking sub-tabs

User shared two more photos of the real LabVIEW system's Frequency
Series sub-tabs (ORDER SPECTRUM + ORDER TRACKING). Reproduced both
in Qt, replacing the last two PlaceholderPanels on the Live Display's
Frequency-domain tab.

- **OrderSpectrumPlot** widget: two stacked plots matching the
  LabVIEW screen -- SPEED (rpm) vs TIME on top, magnitude vs ORDER
  on the bottom, plus a compact PEAKS table showing the top-5
  magnitude spikes.
- **OrderTrackingPlot** widget: MultiSeriesPlot with 5 named
  series (OVERALL + gear-mesh harmonics 12 / 24 / 36 / 48) plus an
  EXPECTED ORDER info panel on the right listing each labeled
  order.
- **Live wiring**: on every 4th signal_chunk, `_refresh_order_analysis`
  computes both from the raw signal + rpm buffers. Order spectrum
  uses `analysis_engine.signal.order_spectrum.compute_order_spectrum`
  (angle-domain resampled FFT, samples_per_rev=180); the per-order
  tracking magnitudes use
  `analysis_engine.signal.order_tracking.compute_order_tracking`
  (STFT with the target bin following order × rpm(t) / 60). OVERALL
  is a windowed-RMS envelope of the raw signal. Both are gated on
  a min 1024-sample buffer and a real rpm ramp (dtheta > 0).
- Added an rpm-buffer deque on LiveDisplayScreen that mirrors the
  raw-trace buffer sample-for-sample so the order-tracking math has
  an aligned rpm array to work with (pads by repeating the last
  known rpm when a chunk's rpm array is shorter than its values).
- Cleared alongside the other plots on a fresh RUNNING event.

Verified end-to-end against the running backend + simulator: Order
Spectrum shows the gear R's 12-tooth mesh at order 11.98 with 2x
at 24.04 and 3x at 36 (matches the seeded model exactly); Order
Tracking shows 5 stacked Y-axes with OVERALL/12/24/36/48 traces
plus the EXPECTED ORDER table populated.

Testing: 5 new widget tests
(`OrderSpectrumPlot.set_speed_and_spectrum`, `.set_peaks_populates_
table`, `.clear_wipes_state`; `OrderTrackingPlot.multiple_series_
data_pushes`, `.expected_orders_populates_table`). Full cross-
package suite: **246/246 passing.**

---

## 2026-07-30 18:30 UTC — Qt Calibration screen + real live spectrogram plots

After reading the real Vibr-O-Matic Analyzer user's manual (see
`vom_manual.txt` in scratchpad), tackled two of the missing pieces
the manual documents:

**Calibration screen** (matches section 7 of the manual):
- New `CalibrationRow` (per model × channel) with sensor_sensitivity_
  mv_per_eu / engineering_units / db_reference_eu / custom_label /
  weighting_filter / pregain_db + last_calibrated_at / due_at audit.
  Default values match the manual (1000 mV/EU, V, 1.0, EU, linear, 0 dB).
- New GET + PATCH `/models/{model_id}/calibrations/{channel_name}`
  endpoints on the models router; GET seeds defaults on first read
  so a fresh model works without a separate seed step.
- New `CalibrationOut` + `CalibrationUpdate` pydantic schemas.
- New `CalibrationScreen` (Qt) with the full manual field set:
  spinboxes for sensitivity/dB reference/pregain, combos for
  engineering units + weighting filter, a Save button that stamps
  last_calibrated_at (now) + due_at (12 months out). Added as the
  4th nav tab in the MainWindow.

**Real live spectrogram / octave plots** (replacing 4 placeholders):
- Reused the analysis_engine's existing `signal.stft.compute_spectrogram`
  and `signal.octave.compute_octave_bands` -- both were already
  implemented, just not wired into the Qt Live Display.
- New `ColorMapPlot(GraticuleWidget)` -- 2D heatmap of |STFT| with
  frequency on Y (0-2.5k Hz) and time on X, painted via QImage with
  a viridis 6-stop LUT. Autoscaled to peak.
- New `WaterfallPlot(GraticuleWidget)` -- N stacked spectrum slices
  from the same matrix, painted with vertical offset + alpha fade
  toward older frames. Classic waterfall projection.
- New `OctaveBarsPlot(GraticuleWidget)` -- ISO 31.5/63/125/.../8k Hz
  band-energy bars, with band-center labels along the X-axis.
- Cascade uses the WaterfallPlot widget for this pass (same data,
  same projection -- extend later if we want a variant orientation).
- Live wiring: on every 4th signal_chunk, recompute STFT (nperseg
  256, noverlap 128) and octave bands from the raw-buffer contents,
  push into all four plots. Guarded on min 512 samples so the STFT
  has at least one full window.
- Order spectrum + Order tracking stay as PlaceholderPanels (they
  need angular resampling by tach, which is batch-computed today).

Testing: 3 new backend tests for the calibration endpoint
(seeds-defaults, persists-across-fresh-get, unknown-model 404); 3
new Qt tests for the Calibration screen (form populates, save
dispatches with form values, save failure re-enables); 5 new tests
for the spectrogram widgets (setters accept expected shapes,
clear resets). Updated the app-smoke test for 4 screens instead of
3. Full cross-package suite: **241/241 passing.**

---

## 2026-07-30 17:15 UTC — Qt Reports: plots on Consolidated + Summary tabs

Extended the multi-Y-axis plot pattern into the Reports screen:

- **Consolidated tab** — below the PASS/FAIL stamp + fault-detection
  text, two side-by-side plots wired to the report's actual arrays:
  `order_spectrum.magnitude` (dense FFT-like view on the left) and
  `order_tracking.magnitude` (amplitude vs. time on the right).
  Both use MultiSeriesPlot with a single series each.
- **Summary tab** — replaced the plain 2-column serial+value table
  with a proper SPC X-chart: MultiSeriesPlot showing the RMS Avg
  trend across trials, with three dashed horizontal reference lines
  at the SPC center_line (CL), UPPER control limit (UCL), and LOWER
  control limit (LCL) computed by the analysis engine. Autoscale is
  overridden with a manual range that includes both the values and
  the control limits, so the CL always sits inside the visible band.
- **MultiSeriesPlot extensions** used to make both work:
  - `set_series_data(name, values)` — replace a series' buffer with
    a fixed array (used for both order arrays + the X-chart values).
  - `set_reference_lines(name, [(y, label), ...])` — dashed
    horizontal marks in the plot area at those y-values on the
    series' scale, with right-aligned labels ("CL 0.92", "UCL 2.22",
    "LCL -0.38"). Muted alpha on the series color so they don't
    compete visually with the primary trace.
  - `_format_tick` improved to keep readable labels down to 1e-3
    magnitude and switch to scientific below that (the order
    spectrum used to render all ticks as "0.00" because raw FFT
    magnitudes hover in the 0.01-0.03 range).
- New tests: `test_set_series_data_replaces_the_buffer`,
  `test_set_reference_lines_stores_labels`. Rewrote the summary tab
  test to assert on the plot buffer + reference lines instead of the
  removed table. Added a consolidated-plot population test. Full
  cross-package suite: **230/230 passing.**

---

## 2026-07-30 16:30 UTC — Qt Computed sub-tab: multi-Y-axis plot with cursor + config menu

Replaced the numeric-readout `LiveStatsPanel` on the Computed sub-tab
with a real multi-Y-axis live plot matching the LabVIEW NVH TEST
SCREEN's COMPUTED view. Eight named series (SPEED / CREST / PEAK /
RMS / KURTOSIS / SKEWNESS / VARIANCE / MEAN), each with its own
Y-axis column stacked on the left, all sharing a common time axis
across the plot area.

- New `MultiSeriesPlot(GraticuleWidget)` widget (~330 lines).
  Each series has a `SeriesConfig` dataclass with color, visible,
  autoscale, manual_min/max, line_width, antialiased, and a bounded
  deque buffer. `push_sample(name, value)` appends + repaints.
  `contextMenuEvent` builds a QMenu with:
  - `Plot Visible` submenu (one checkable action per series)
  - `Line Width` (1 / 1.5 / 2 / 3 px, applied to every series)
  - `Anti-Aliased` toggle
  - `X Scale` (disabled -- X is a rolling time buffer today)
  - `Y Scale` -> per-series submenu with Autoscale toggle + Set
    Range... (QInputDialog for min/max)
  - `Cursor Enabled` toggle
  Widget also handles mouseMoveEvent to update the cursor position
  and draws a dashed vertical line + pill labels showing each visible
  series' value at that X.
- New `PlotLegend(QFrame)` widget: right-side legend with one row
  per series (color chip + name + visibility QCheckBox). Toggling
  the checkbox hides/shows the series -- same effect as the plot's
  Plot Visible submenu, discoverable via a persistent UI element.
- On every `signal_chunk` event the LiveDisplayScreen now computes
  RMS/Peak/Crest/Mean/Variance/Skewness/Kurtosis via numpy plus
  Speed from the chunk's rpm array, and pushes each into the plot.
  Guards on chunks < 8 samples and std ~ 0.
- Removed the now-unused `LiveStatsPanel` module.
- Testing: 8 new tests in `test_multi_series_plot.py` covering
  buffer growth, unknown-series push, bounded deque behavior,
  visibility toggle, cursor enable/disable, autoscale range,
  manual range override, clear(). Existing
  `test_signal_chunk_updates_...` rewritten to verify the plot's
  series buffers instead of the removed stats labels. Full
  cross-package suite: **227/227 passing.**

---

## 2026-07-30 15:00 UTC — Qt dark/light theme toggle

Runtime dark/light theme switching in the Qt app. The design tokens
already carried two palettes (`dark` = the cyan-on-black operator
theme, `print` = a fully-specified light palette originally for PDF
report output, reused here as the "light" mode). What was missing was
a way to flip between them without restarting.

- New `ThemeManager(QObject)` (`nvh_qt_app.theme_manager`) attached
  to the QApplication as `.theme`. Exposes `palette_name`,
  `palette`, `toggle()`, and `theme_changed(str)` signal.
- New "Dark"/"Light" toggle button in the HeaderBar (top-right,
  bordered pill styled via QSS). Button label shows the palette a
  click will switch TO, matching the OS convention.
- App-level `setStyleSheet(build_stylesheet(new_name))` on every
  toggle so all type-selector QSS refreshes automatically.
- Widgets with inline styles gained `apply_palette(...)` methods and
  the screens cascade to their children on `theme_changed`:
  `LiveToolbar` (rebuilds icons at the new stroke color +
  per-button QSS), `LiveStatusBar` (rich-text rebuild),
  `LiveStatsPanel`, `PlaceholderPanel`, `_InTableToggle`.
  `LiveDisplayScreen` also repaints the FFT trace pen color and
  re-applies pass/alarm hex to any already-stamped Result cells
  (cached per-row so the flip doesn't lose them).
- `GraticuleWidget` reads its background from the current palette
  (used to hardcode `dark.background`) and subscribes to
  `theme_changed` so plots repaint on flip.
- Testing: 4 new tests (`test_theme_toggle.py`) cover manager
  start/toggle/label + HeaderBar's toggle button flipping the app
  theme. Full cross-package suite: **219/219 passing.**

---

## 2026-07-30 14:20 UTC — Qt Live Display: bottom table -> (gear x direction) results grid

User shared a photo of the real LabVIEW NVH TEST SCREEN.vi to clarify
what the bottom table should look like: rows are per-(gear, direction)
combos (R_RU / R_RD / I_RU / I_RD / ... / IV_RD in the real screen),
columns are Gear ID + Result (colored PASS/FAIL fill) + one column per
graded parameter (RMS max / PK max / Kurtosis max / IN_H1(dB m/s2) /
IN_H1(g)). Result cell is green on PASS, red on FAIL, empty until the
DC completes -- the color IS the value, matching the LabVIEW screen.

Replaced the previous "Live parameter catalog" table with this
`Live results grid`:

- Rows are seeded from `_DEFAULT_GEAR_LABELS` (R/I/II/III/IV/V) on
  first paint, then reseeded from the real model's gear labels once
  the `fetch_model` reply lands (excluding neutral N since it doesn't
  have a graded step). Two rows per gear (RU / RD) matching the real
  screen's convention.
- `_paint_result_cell(gear, direction, stamp)` fills the Result cell
  green (`pass` token) on PASS, red (`alarm` token) on FAIL. The
  matching (gear, direction) row is found in O(1) via a
  `_row_index[(gear, direction)] -> row` lookup built at seed time.
- Parameter columns stay empty for now -- the live event stream
  carries `stamp` and `fail_reason_codes` but not per-parameter
  values, so those cells will fill in once the DC-complete event
  starts carrying the full grading result (or once the analysis
  engine streams per-parameter values mid-run). This mirrors the
  real system's mid-run state where Result is known but detailed
  columns aren't yet.
- Two new tests: seeds one row per (gear, direction) pair from the
  fetched model; dc-event paints the matching Result cell with the
  pass token color. Full qt-app suite: **27/27 passing.**

---

## 2026-07-30 13:45 UTC — Qt Live Display rebuild: toolbar + nested tabs + status bar

Rebuilt the qt-app Live Display screen to match the real system's
operator layout, replacing the single trace + 4-card scaffold. The new
screen has four visual bands stacked vertically:

- **Top toolbar** — nine SVG-icon buttons matching the real operator
  workflow (Login / Calibration / System / D Report / Summary /
  Master / Master Setup / Table Config / Limit Config). Icons are
  inline SVGs drawn from a new `nvh_qt_app.icons` module, colored via
  the design tokens' `accentSecondary`; hover state is a subtle
  tinted rounded corner. Each button emits `action_triggered(name)`
  so future routing (e.g. Master button → nav to Master Entry) can be
  wired without touching the toolbar.
- **Plot tabs** — a `QTabWidget` with two top-level tabs (Time series /
  Frequency domain) and nested subtabs inside each:
  - Time series → **Raw signal** (existing `SignalTraceWidget`) +
    **Computed** (new `LiveStatsPanel` — RMS/peak/crest/mean/N
    recomputed on every chunk via numpy).
  - Frequency domain → **FFT** (new `FftTraceWidget` — `np.fft.rfft`
    of the current buffer, magnitude autoscaled, painted over the
    same graticule; the demo data's gear-mesh harmonics are clearly
    visible at 1×, 2×, 3× the fundamental) + four **placeholder**
    subtabs (Order spectrum / Order tracking / Color map / Waterfall)
    that label themselves as batch-computed-not-streamed today rather
    than pretending to compute an empty result.
- **Live parameter catalog table** — fetches
  `/models/MODEL-A/programs/REVA/parameters` once on load, shows
  stat_name + order + LIMIT band + table-config membership.
- **Bottom status bar** — 9 fields in a 2-row grid: Op / Shift / SN /
  Rep / Model / Status / Gear / NVH / Result. Backfilled from
  `/test-runs/{id}` on every `test_run` event; direction is mapped to
  the PLC `nvh_id` (0=RU, 1=STYD, 2=STYC, 3=RD).
- New widgets: `LiveToolbar`, `LiveStatusBar`, `LiveStatsPanel`,
  `FftTraceWidget`, `PlaceholderPanel`.
- Testing: new `FakeLiveClient` in the test fakes (public
  `emit_event`/`emit_status` for synchronous driving), 8 new
  `test_live_display.py` tests covering toolbar wiring, tab structure,
  parameter fetch, test_run/dc/signal_chunk event handling, and the
  RUNNING-clears-previous-traces reset behavior. Full qt-app suite:
  **26/26 passing**.

---

## 2026-07-30 11:20 UTC — LIMIT band edit + Table Config parameter toggle

Second round of write endpoints, extending the threshold-tuning pattern:
the operator can now override the LIMIT band directly (real Limit
Config.vi "operator override" flow) and can add/remove a parameter from
the program's Table Config with one click (Phase E's per-parameter
inclusion checkbox).

- **Schemas** (`nvh_api_schemas.catalog`): `LimitConfigLimitUpdate`
  (mirrors `LimitConfigThresholdUpdate`) and `TableConfigParameterUpdate`
  (`{included: bool}`). Still no `REPORT_SCHEMA_VERSION` bump — same
  boundary-scope reasoning.
- **Backend**:
  - `catalog_service.update_limit_config_limit()` — writes just
    LIMIT_LOW/HIGH on the matching row (symmetric with the threshold
    service; THRESHOLD stays untouched).
  - `catalog_service.set_table_config_parameter()` — idempotently
    inserts/deletes a `TableConfigParameterRow`. Rejects a stat name
    that isn't in `PARAMETER_CATALOG` (analysis engine's authoritative
    list), so the toggle can't smuggle a phantom parameter into the
    Table Config.
  - Two new PATCH routes returning the refreshed
    `ParameterCatalogRowOut`, with shared `_missing_limit_config_detail`
    + `_refreshed_row` helpers so the three edit endpoints stay in
    lockstep.
  - 7 new tests: LIMIT updates only limit columns, LIMIT 404, LIMIT 422;
    table-config toggle off/on, idempotent no-op, 404 for unknown stat,
    422 for missing body field.
- **web-frontend**: `MasterEntry.tsx`'s `ThresholdCell` generalized into
  `NumericCell` that dispatches to `patchThreshold` vs `patchLimit`
  based on which of the four field names it holds. New `InTableCell`
  renders a token-driven pass-green / muted button that toggles the
  Table Config membership. Parameter table now has **four** editable
  numeric columns and a clickable inclusion toggle.
- **qt-app**: `_ThresholdEditor` -> `_NumericEditor` with the same
  `value_committed` signal now serving all four numeric columns.
  New `_InTableToggle(QToolButton)` (checkable, token-driven pass/muted
  color) replaces the static "yes"/"no" text cell. `ApiClient` gets
  `patch_limit` + `patch_table_config_parameter`; `FakeApiClient` grows
  matching call-logs and configurable responses.
- **Testing**: 4 new qt-app tests (LIMIT dispatch, in-table dispatch,
  revert on failure for both). Full cross-package suite: **206/206
  passing** (was 196; 10 new — 7 backend + 3 net-new qt-app).

---

## 2026-07-30 09:15 UTC — Threshold tuning: PATCH endpoint + inline editing in both clients

First **write endpoint** in the backend (everything before this was
read-only). Wires up the real system's *Limit Config.vi "Save"* button in
both clients: the operator types a tuned THRESHOLD margin into the
Master Entry parameter table and the backend persists just those two
columns (`THRESHOLD_LOW`/`THRESHOLD_HIGH`) on the matching
`LimitConfigRow` — leaves the LIMIT band and everything else untouched.

- **Schema**: new `nvh_api_schemas.catalog.LimitConfigThresholdUpdate`
  (two `float` fields). No `REPORT_SCHEMA_VERSION` bump — its docstring
  scopes that version to the analysis-engine→report-shape boundary,
  which this isn't part of.
- **Backend**:
  - `catalog_service.update_limit_config_threshold()` — writes just the
    two threshold columns + `updated_at`, returns the refreshed
    `LimitConfigRow` (or `None` for an unknown row).
  - `PATCH /models/{model_id}/programs/{program_name}/limit-configs/{stat_name}/threshold`
    endpoint on `models.router` — returns the refreshed
    `ParameterCatalogRowOut` for the row so clients can drop the
    response straight into their in-place lookup.
  - CORS `allow_methods` widened from `["GET"]` to `["GET", "PATCH"]`.
  - 5 new tests in `test_models_router.py`: threshold-only column
    update, persistence across a fresh GET, 404 for unknown stat name,
    404 for unknown model, 422 for a missing body field.
- **web-frontend**: `api.patchThreshold(...)` (via a new `patchJson`
  helper). `MasterEntry.tsx` gains two editable `<input>` columns
  (`threshold_low`/`threshold_high`); on blur/Enter the value is
  parsed, PATCHed, and the returned `ParameterCatalogRowOut` swapped in
  so the visible cell matches DB state (server may round/normalize).
  Escape reverts; a save failure shows an alarm-red border and restores
  the last-committed value.
- **qt-app**: `ApiClient.patch_threshold(...)` (built on
  `QNetworkAccessManager.sendCustomRequest("PATCH", …)`, cross-version-
  safe since PySide's older `.patch()` sugar isn't consistent).
  `MasterEntryScreen` gains two new columns backed by
  `_ThresholdEditor(QLineEdit)` cell widgets — `QDoubleValidator`,
  `editingFinished` triggers the PATCH, Escape reverts, save failure
  restores the pre-edit value from the local cache.
  `FakeApiClient` grows a `patch_threshold_calls` log + configurable
  response so widget-level tests can assert the PATCH body without a
  live backend.
- **Tests**: 5 new qt-app tests round out the 6 total on
  `MasterEntryScreen` (editor presence, PATCH round-trip with local
  state update, revert-on-failure). Full cross-package suite:
  **196/196 passing.**

---

## 2026-07-29 18:30 UTC — M1: Live Display streaming via ZeroMQ → WebSocket

Second (and final for this milestone's Report GUI scope) M1 slice: wired
Live Display in both GUI clients to a continuous live signal stream,
using ZeroMQ per the user's explicit choice — designed so LabVIEW can
drop-in replace the simulator side later without touching anything
downstream.

- **Architecture**: producer (`web-backend/scripts/live_simulator.py`)
  → ZMQ PUB (`tcp://127.0.0.1:5555`) → backend ZMQ SUB async task →
  in-process fan-out to WebSocket clients → `/live/ws` → GUIs. Browsers
  can't speak ZMQ, so the WebSocket relay is the necessary bridge; Qt
  goes through the same WebSocket for consistency (one contract, both
  clients).
- **Message shapes** (`nvh_api_schemas.realtime`): three `type`-tagged
  events — `LiveTestRunUpdate` (RUNNING/COMPLETED), `LiveDcUpdate`
  (per-DC PASS/FAIL stamp), `LiveSignalChunk` (500-sample slices of the
  current channel's time-series + rpm, streamed ~10 chunks/sec at wall
  clock). One `LiveEvent` union across all three.
- **Simulator**: cycles indefinitely through the 3 demo scenarios
  (healthy → PASS, crash-noise → FAIL, slippage → FAIL) — builds a full
  DC record via the existing `generate_dc_record()` and chunks it out
  over wall-clock time with a fresh `np.random.default_rng()` per cycle
  so each cycle's noise is different (matches "real acquisition" better
  than the deterministic-seed batch simulator does).
- **Backend relay** (`nvh_web_backend.live_relay.LiveRelay`): one
  `zmq.asyncio.Context` + `zmq.SUB` socket, one background task fans
  received strings out to per-WebSocket `asyncio.Queue`s (maxsize 200;
  slow clients get their oldest message dropped rather than blocking the
  fan-out). Lifespan-managed via FastAPI's `lifespan=` context manager
  (started/stopped alongside the app). WebSocket endpoint is a thin
  loop-and-forward.
- **web-frontend Live Display**: WebSocket via `useLiveEvents` hook
  (2s bounded reconnect), rolling 4000-sample buffer rendered as inline
  SVG `<polyline>` inside the graticule box, auto-scaled per frame; PASS
  in green, FAIL in red, PENDING in white; fail-reason-codes surface
  below the card grid when present. No charting library.
- **qt-app Live Display**: `QWebSocket` wrapped in `LiveClient` (same
  callback-based shape as the REST `ApiClient`), new
  `SignalTraceWidget(GraticuleWidget)` that overpaints a `QPolygonF`
  polyline on top of the existing graticule paint; Stamp card swaps its
  child widget between `ValueLabel`/`PassLabel`/`AlarmLabel` so the
  existing theme QSS rules apply. No new PySide6 dependency
  (`QtWebSockets` lives inside the already-declared `PySide6` meta-
  package).
- **Real bug fix caught during live smoke test**: uvicorn refused the
  WebSocket upgrade with a `WARNING: Unsupported upgrade request` — the
  raw `uvicorn` install doesn't include the actual WebSocket protocol
  libraries. Fixed by bumping the dep from `uvicorn>=0.29` to
  `uvicorn[standard]>=0.29`.
- **Testing**: schema-side tagged-union tests
  (`libs/nvh_api_schemas/tests/test_realtime_and_management_schemas.py`
  now covers each `type` discriminator + `TypeAdapter[LiveEvent]`
  dispatch); backend-side in-process integration test
  (`web-backend/tests/test_live_relay.py` binds a real ZMQ PUB on a
  random free port, points `create_app()`'s SUB at it, publishes real
  `LiveTestRunUpdate`/`LiveSignalChunk` events, and asserts they arrive
  byte-for-byte over `TestClient.websocket_connect("/live/ws")`) —
  covers the full ZMQ → SUB → fan-out → WebSocket pipeline in one test
  without needing an external process.
- **Verified beyond the tests**: ran the real simulator + real backend
  + real Vite dev server, drove Live Display in headless Chromium and
  Qt via `QT_QPA_PLATFORM=offscreen`, and captured screenshots of both
  clients mid-stream — web caught a full healthy → PASS transition
  (green stamp, real seeded gear-mesh waveform in the trace), Qt caught
  a crash-noise-unit mid-stream showing the crash burst spikes clearly
  visible in the trace under the graticule.
- **Parallel-agents workflow**: spawned four background agents (live
  simulator, backend relay, web-frontend wiring, qt-app wiring) against
  a fixed schema contract I wrote first, then reconciled + integrated
  their outputs myself and did the end-to-end verification.
- **Result:** 188/188 tests passing (4 new: 2 for the tagged-union
  schema, 2 for the backend WebSocket relay); web-frontend typechecks
  cleanly; qt-app imports cleanly; live pipeline verified end-to-end
  with real ZMQ + WebSocket + both GUI clients rendering real streaming
  data.

## 2026-07-29 17:06 UTC — M1 slice: FastAPI backend + wire Master Entry/Reports in both GUI clients

First work against M1 now that Phases A–E are complete. Scope (confirmed
with the user, including deferring live-stream work): build the FastAPI
backend the GUI scaffolds' `TODO:` banners were waiting on, and wire
**Master Entry** and **Reports** to it in both `web-frontend` and
`qt-app`. **Live Display stays a placeholder** — it needs a continuous
live stream and nothing in this codebase produces one yet.

- New `web-backend` package (`nvh_web_backend`, first `pyproject.toml`
  under `web-backend/` — previously just `scripts/`+`tests/`). Every
  report endpoint reconstructs a live `DcAnalysisResult` per request (raw
  Parquet signal + DB config rows → `analyze_dc_record()`), never reading
  back from the persisted `grading_results`/`spc_points` snapshot tables
  (those never carried enough data to reconstruct a full result — the
  same "compose from live analysis output" convention every
  `analysis_engine.reports.*` builder already follows).
- New `nvh_api_schemas.catalog.ParameterCatalogRowOut` — a DB-catalog
  schema (not an analysis-engine report shape, not a plain rollup) backing
  Master Entry's per-parameter master/limit/table-config view.
- Endpoints: `/models`, `/models/{id}`, `/models/{id}/programs`,
  `/models/{id}/programs/{program}/parameters`, `/test-runs`,
  `/test-runs/{id}`, `/dc-records/{id}/reports/{consolidated,detailed,
  code-result}`, `/models/{id}/summary` — all read-only, `program_name`
  optional throughout (omitted → grade via masters/G-ladder; supplied →
  grade via that program's LIMIT/THRESHOLD, and code-result additionally
  gets `apply_table_config()`'d).
- `web-frontend`: new `src/lib/api.ts` (typed client) + `useApi.ts` (one
  shared fetch-state hook, no query library — a handful of one-shot GETs
  against a tiny fixed demo dataset doesn't justify one yet) + `Panel`/
  `AsyncSection`/`DemoDataNote` components. `MasterEntry.tsx`/`Reports.tsx`
  rewired to real data; `Reports.tsx` gained a **4th tab** (Code-Result,
  alongside the existing Consolidated/Detailed/Summary — not a
  replacement, see the planning note below).
- `qt-app`: new `api_client.py` built on `QNetworkAccessManager` (PySide6's
  own async networking, zero new dependency — not httpx+QThread, which
  would add a second concurrency model for no benefit at this app's
  scale). `MasterEntryScreen`/`ReportsScreen` rewired the same way, with
  an injectable `api_client` constructor parameter + a `FakeApiClient` test
  double so widget tests don't need a live backend or network access.
- **Planning correction, worth recording:** the API contract I initially
  handed to two parallel planning sub-agents (backend design, web-frontend
  wiring, qt-app wiring) omitted a `/summary` endpoint, so both frontend
  agents independently proposed *replacing* the scaffold's existing
  "Summary" tab with "Code-Result." The backend agent, reading the actual
  code, found `nvh_api_schemas.SummaryReportOut` already exists and is
  buildable — Summary was real, already-built functionality, not a
  placeholder to discard. Fixed by adding Code-Result as a 4th tab in both
  clients instead of replacing anything.
- Planned via three parallel Plan sub-agents (backend design, web-frontend
  wiring, qt-app wiring) against that (corrected) fixed contract. The
  backend agent also caught a real gotcha: `DcAnalysisResult.passed` is a
  computed `@property`, so `to_jsonable()` never emits it — every report
  payload needs it injected manually before validation (the exact pattern
  `test_report_schema_contract.py` already established).
- Verified end-to-end beyond the automated test suites: ran the real
  `uvicorn` server against a freshly seeded demo DB, `curl`'d every
  endpoint directly, then drove both real GUI clients (Vite dev server;
  headless-offscreen Qt with a real running event loop) against that same
  live backend and screenshotted all 4 Reports tabs plus Master Entry in
  both clients to confirm real data actually renders, not just that
  requests succeed.
- **Result:** 184/184 Python tests passing (backend: 34 new; qt-app: 12,
  9 new) + web-frontend typecheck/build clean. Fixed one incidental test
  basename collision (`qt-app/tests/test_reports.py` vs. the pre-existing
  unrelated `analysis-engine/tests/test_reports.py`, colliding under a
  joint pytest invocation with no per-package `__init__.py`) by renaming
  to `test_reports_screen.py`.

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
- **A–E complete.**
- **M1 (done):** FastAPI backend (`web-backend`/`nvh_web_backend`) + all
  three GUI screens wired in both `web-frontend` and `qt-app`
  (Master Entry, Reports, Live Display — the last via a ZeroMQ →
  WebSocket relay so LabVIEW can drop-in replace the simulator later).
- **Remaining beyond M1:** write/edit endpoints (today's backend is
  read-only — creating/editing models, master profiles, limit configs,
  Table Configs from the GUI is a later slice); the AI layer; real
  LabVIEW hardware integration (the ZMQ side of the wire is already
  agnostic to the producer — LabVIEW just needs to publish the same
  JSON shapes on the same socket).
