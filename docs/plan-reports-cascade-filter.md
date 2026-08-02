# Reports Screen: Cascade Filter + D-Report Layout

## Status

**Master Entry GUI (dynamic selectors + Create/Edit dialogs)** — COMPLETED (commit `766cf26`).
All 350 tests pass. Full plan is in `docs/plan-master-entry-gui.md`.

---

## Context

**Repo:** `robokks/vibration-analysis-software-`
**Branch:** `claude/nvh-software-python-28zib3`

The user's reference is a real LabVIEW D-report Excel file (TRANSAXLE NVH REPORT) with:
- Header: MODEL NAME, PART NUMBER, SERIAL NUMBER, REPEAT NUMBER, DATE OF TEST, START/END, TEST RESULT
- NVH DETAILS table: one row per TEST CONDITION (I-RU, I-STYD, I-RD, II-RU, ..., R-RD)
  with columns: SPEED(Rpm), CH1_M_RMS, CH1_M_PK, CH1_O_RMS, CH1_M_KURT, CH1_M_CREST,
  CH1_IN_H1(dB), CH1_IN_H2(dB), CH1_DIFF_H1(dB), CH1_DIFF_H2(dB), CH1_IN_S1.0, CH1_OUT_S1.0
- Three Excel tabs: Report, SPEED SERIES, TIME SERIES

**User's stated layout:** "left side cascade filter / top side general details / 
full graph with tabs then table also (like live display but table in another tab) / 
one more filter: gear selection and nvh id selection"

**Key domain facts:**
- A `TestRun` has multiple `dc_records`, each with `dc_id`, `gear_label`, `direction`
  (one dc_record per test condition, e.g. gear=I, direction=RU → label "I-RU")
- `nvh_id` (PLC enum 0–3) maps to direction: 0=RU, 1=STYD, 2=STYC, 3=RD
- "NVH ID selection" = choosing which dc_record (condition) to view in the graphs
- "Gear selection" = cascade filter that narrows the NVH ID combo to one gear's conditions
- Cascade filtering is fully client-side after one `fetch_test_runs()` + `fetch_summaries()` call

**Current state of `reports.py`:**
- Single flat `_run_combo` listing all runs as `serial_number — overall_result`
- Hardcoded `MODEL_ID`, `PROGRAM_NAME`, `GEAR_LABEL`, `DIRECTION`, `SUMMARY_STAT_NAME`
- No cascade, no left panel, no general details strip, no Gear/NVH ID filter

---

## Screen Layout

```
QHBoxLayout (top-level):
┌──────────────────┬──────────────────────────────────────────────────────┐
│ LEFT PANEL       │ RIGHT PANEL (QVBoxLayout)                            │
│ ~220px fixed     │                                                      │
│                  │  GENERAL DETAILS STRIP (QHBoxLayout)                 │
│ Test run         │  Model: [v]  Serial: [v]  Rpt: [v]  Date: [v]       │
│  Model   [combo] │  Start: [v]  End: [v]   [PASS/FAIL stamp]            │
│  Date    [combo] │                                                      │
│  Serial  [combo] │  QTabWidget ─────────────────────────────────────── │
│  Rpt No  [combo] │   Tab "Graphs"    → Order Spectrum + Order Tracking  │
│                  │   Tab "Detailed"  → per-stat table                   │
│ Condition        │   Tab "NVH Details" → per-condition NVH table        │
│  Gear    [combo] │   Tab "Summary"   → multi-serial X-chart             │
│  NVH ID  [combo] │                                                      │
│                  │                                                      │
│ Report context   │                                                      │
│  Program [combo] │                                                      │
│  Direction[combo]│                                                      │
│  [stretch]       │                                                      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

---

## File 1: `qt-app/src/nvh_qt_app/api_client.py`

Add one new method:
```python
def fetch_summaries(self, model_id: str, on_success: OnSuccess, on_error: OnError) -> None:
    self._get("/summaries", on_success, on_error, {"model_id": quote(model_id)})
```

---

## File 2: `qt-app/src/nvh_qt_app/screens/reports.py`

Full rewrite. The full prior plan in `docs/plan-reports-cascade-filter.md` covers the
cascade logic (Model→Date→Serial→Rpt) and Summary multi-serial selection. This plan
extends it with the layout changes, Gear/NVH ID filters, and general details strip.

### Remove module-level constants

Delete `MODEL_ID`, `PROGRAM_NAME`, `GEAR_LABEL`, `DIRECTION`, `SUMMARY_STAT_NAME`.

### New instance variables

```python
self._model_id: str | None = None
self._program_name: str | None = None
self._direction: str = "RU"
self._all_runs: list[dict] = []
self._all_summaries: list[dict] = []
self._current_dc_records: list[dict] = []  # dc_records of selected test run
```

### Left panel: `_build_filter_panel() -> Panel`

`QVBoxLayout` inside a fixed-width (`setFixedWidth(220)`) `Panel`:

```python
# Section 1: Test run cascade
SectionTitle("Test run")
_model_combo    (QComboBox)  ← populated from fetch_models()
_date_combo     (QComboBox)  ← "All" + unique YYYY-MM-DD from _all_runs
_serial_combo   (QComboBox)  ← unique serial_number for selected date
_rpt_combo      (QComboBox)  ← "Rpt N  (YYYY-MM-DD HH:MM:SS)" per run, userData=test_run_id

# Section 2: Condition selector (cascaded from loaded dc_records)
SectionTitle("Condition")
_gear_combo     (QComboBox)  ← "All" + sorted unique gear_label from _current_dc_records
_nvh_id_combo   (QComboBox)  ← "gear-direction" labels, e.g. "I-RU", filtered by gear

# Section 3: Report context
SectionTitle("Report context")
_program_combo  (QComboBox)  ← populated from fetch_programs()
_direction_combo (QComboBox) ← RU / STYD / STYC / RD  (for Summary report)
```

Signal wiring (all use `blockSignals(True/False)` during programmatic population):
- `_model_combo.currentIndexChanged` → `_on_model_changed()` → fetch programs, test_runs, summaries
- `_date_combo.currentIndexChanged` → `_on_date_changed()` → repopulate `_serial_combo`
- `_serial_combo.currentIndexChanged` → `_on_serial_changed()` → repopulate `_rpt_combo`
- `_rpt_combo.currentIndexChanged` → `_on_rpt_changed()` → fetch test run detail
- `_gear_combo.currentIndexChanged` → `_on_gear_changed()` → repopulate `_nvh_id_combo`, filter NVH Details table
- `_nvh_id_combo.currentIndexChanged` → `_on_nvh_id_changed()` → fetch consolidated/detailed for selected dc_id
- `_program_combo.currentIndexChanged` → store `_program_name`
- `_direction_combo.currentTextChanged` → store `_direction`, refresh Summary report if needed

### General details strip: `_build_details_strip() -> QWidget`

```python
row = QHBoxLayout()
self._det_model   = MonoLabel("—")  # prefixed "Model: "
self._det_serial  = MonoLabel("—")  # prefixed "Serial: "
self._det_rpt     = MonoLabel("—")  # prefixed "Rpt: "
self._det_date    = MonoLabel("—")  # prefixed "Date: "
self._det_start   = MonoLabel("—")  # prefixed "Start: "
self._det_end     = MonoLabel("—")  # prefixed "End: "
self._det_stamp   = StampWidget(...)  # PASS/FAIL stamp, small size
```

Updated in `_on_test_run_detail(detail)` and `_on_consolidated(payload)`.

### Cascade: NVH ID → dc_record

```python
def _on_test_run_detail(self, detail: dict) -> None:
    self._current_dc_records = detail.get("dc_records") or []
    # Update details strip from detail fields
    run = detail  # has serial_number, repeat_number, started_at, finished_at, overall_result
    self._det_serial.setText(f"Serial: {run.get('serial_number', '—')}")
    self._det_rpt.setText(f"Rpt: {run.get('repeat_number', '—')}")
    started = run.get('started_at', '')
    self._det_date.setText(f"Date: {started[:10]}")
    self._det_start.setText(f"Start: {started[11:19]}")
    self._det_end.setText(f"End: {(run.get('finished_at') or '')[:19][11:]}")
    # Repopulate gear combo
    self._repopulate_gear_combo()

def _repopulate_gear_combo(self) -> None:
    gears = ["All"] + sorted({r["gear_label"] for r in self._current_dc_records})
    self._gear_combo.blockSignals(True)
    self._gear_combo.clear()
    for g in gears:
        self._gear_combo.addItem(g)
    self._gear_combo.blockSignals(False)
    self._on_gear_changed(0)

def _on_gear_changed(self, _index: int) -> None:
    gear = self._gear_combo.currentText()
    recs = self._current_dc_records if gear == "All" else [
        r for r in self._current_dc_records if r["gear_label"] == gear
    ]
    self._nvh_id_combo.blockSignals(True)
    self._nvh_id_combo.clear()
    for r in recs:
        label = f"{r['gear_label']}-{r['direction']}"
        self._nvh_id_combo.addItem(label, userData=r["dc_id"])
    self._nvh_id_combo.blockSignals(False)
    if recs:
        self._on_nvh_id_changed(0)
    # Also filter NVH Details table if data is loaded
    self._filter_nvh_details_table()

def _on_nvh_id_changed(self, index: int) -> None:
    dc_id = self._nvh_id_combo.itemData(index)
    if not dc_id:
        return
    pn = self._program_name or ""
    self._api.fetch_consolidated_report(dc_id, self._on_consolidated, self._on_error, program_name=pn)
    self._api.fetch_detailed_report(dc_id, self._on_detailed, self._on_error, program_name=pn)
    self._api.fetch_code_result_report(dc_id, self._on_code_result, self._on_error, program_name=pn)
```

Note: `fetch_summary_report` is called with model_id + gear_label + direction from
`_direction_combo` (for the SPC X-chart), NOT triggered by NVH ID changes.

### NVH Details table gear filter

After `_on_code_result` populates `_nvh_details_table`, store the raw rows:
```python
self._code_result_rows = rows   # full list
self._filter_nvh_details_table()

def _filter_nvh_details_table(self) -> None:
    gear = self._gear_combo.currentText()
    rows = self._code_result_rows if gear == "All" else [
        r for r in self._code_result_rows
        if r["gear_direction"].startswith(gear + "-")
    ]
    # repopulate _nvh_details_table from rows (same as current _on_code_result logic)
```

### Tab layout (right panel)

```python
self._tabs = QTabWidget()

# Tab 1: Graphs (order spectrum + order tracking side-by-side, as in current Consolidated tab)
graphs_panel = _build_graphs_tab()   # returns (panel, spec_plot, track_plot)
self._tabs.addTab(graphs_panel, "Graphs")

# Tab 2: Detailed (existing _detailed_table)
self._tabs.addTab(self._wrap(self._detailed_table), "Detailed")

# Tab 3: NVH Details (existing code-result table, renamed)
self._tabs.addTab(self._wrap(self._nvh_details_table), "NVH Details")

# Tab 4: Summary (multi-serial X-chart with serial list + stat combo)
self._tabs.addTab(self._summary_panel, "Summary")
```

The "Graphs" tab keeps the existing Consolidated panel content (order spectrum plot,
order tracking plot, PASS/FAIL stamp, detail label) but removes the top-level stamp —
that moves to the general details strip.

### Summary tab (multi-serial selection)

Same as `docs/plan-reports-cascade-filter.md`:
- `QListWidget(selectionMode=MultiSelection)` for serial numbers
- `QComboBox` for stat name: `["RMS Avg", "Peak", "Order 1x Mag"]`
- `MultiSeriesPlot` for X-chart
- `_STAT_FIELD = {"RMS Avg": "rms_avg", "Peak": "peak", "Order 1x Mag": "order_1x_mag"}`
- `_on_summaries_loaded`: populate list, `selectAll()`
- `_on_serial_selection_changed`: `set_series_data(serial, vals)` per selected serial

### `MultiSeriesPlot` additions (if missing)

In `qt-app/src/nvh_qt_app/widgets/multi_series_plot.py`, add if not present:
```python
def series_names(self) -> list[str]:
    return list(self._series.keys())

def remove_series(self, name: str) -> None:
    self._series.pop(name, None)
```

### Initialization

```python
def __init__(self, parent=None, api_client=None):
    super().__init__(parent)
    self._api = api_client or ApiClient()
    # build left panel, details strip, tabs
    # outer QHBoxLayout: left panel + right QVBoxLayout(details + tabs)
    self._api.fetch_models(self._on_models_loaded, self._on_error)
```

`_on_models_loaded`: populate `_model_combo`, set index=0 → triggers `_on_model_changed()`.

---

## Cascade flow summary

```
fetch_models() → _model_combo
  _on_model_changed() → fetch_programs + fetch_test_runs + fetch_summaries
    _on_runs_loaded() → _all_runs → _date_combo
      _on_date_changed() → _serial_combo
        _on_serial_changed() → _rpt_combo
          _on_rpt_changed() → fetch_test_run(test_run_id)
            _on_test_run_detail() → update details strip, _gear_combo
              _on_gear_changed() → _nvh_id_combo
                _on_nvh_id_changed() → fetch consolidated + detailed + code_result reports
    _on_summaries_loaded() → _serial_list (Summary tab)
```

---

## Verification

```bash
.venv/bin/pip install -e qt-app
.venv/bin/python -m pytest web-backend/tests libs/nvh_contract/tests -q
.venv/bin/python web-backend/scripts/seed_demo_data.py
.venv/bin/python -m uvicorn nvh_web_backend.app:app --reload &
.venv/bin/python -m nvh_qt_app
```

Manual checklist:
- [ ] Left panel shows: Model / Date / Serial / Rpt No / Gear / NVH ID / Program / Direction
- [ ] Model combo populates on startup
- [ ] Date combo shows unique dates; "All" shows all runs
- [ ] Selecting date narrows Serial combo; selecting serial narrows Rpt combo
- [ ] Selecting Rpt No loads run → details strip shows Model, Serial, Rpt, Date, Start, End
- [ ] Gear combo shows "All" + unique gear labels from that test run's dc_records
- [ ] Selecting a gear narrows NVH ID combo to that gear's conditions (e.g. "I-RU", "I-STYD")
- [ ] Selecting NVH ID loads Graphs tab (order spectrum + tracking plots)
- [ ] Graphs tab shows order spectrum and order tracking for selected condition
- [ ] NVH Details tab shows per-condition table; gear filter narrows rows
- [ ] PASS/FAIL result appears in details strip after consolidated report loads
- [ ] Summary tab serial list shows all serials, all pre-selected, X-chart populated
- [ ] Multi-serial selection / deselection updates X-chart lines
- [ ] Stat dropdown (RMS Avg / Peak / Order 1x Mag) switches the plotted field

---

# Phase C (Next): Named Master Profiles + Two-Stage LIMIT/THRESHOLD Config

Backend-only phase. Spec unchanged from previous plan. Key points:

- New `MasterProfile` and `LimitConfigEntry` pydantic models in `nvh_contract/models.py`
- New `MasterProfileRow` and `LimitConfigRow` ORM rows in `nvh_contract/db.py`
- New `analysis-engine/src/analysis_engine/grading/limit_config.py` with
  `import_limit_config_from_masters`, `check_value_with_threshold`,
  `grade_dc_record_with_limits`
- `analyze_dc_record()` in `pipeline.py` gains optional `limit_configs` param
- `seed_demo_data.py` persists one `MasterProfileRow` (program_name="REVA") and
  `LimitConfigRow` entries seeded from `import_limit_config_from_masters(masters)`
- Formula: `effective_high = limit_high + threshold_high`,
  `effective_low = limit_low - threshold_low`
- All existing tests pass unchanged (purely additive)

Verification:
```bash
.venv/bin/pip install -e libs/nvh_contract -e analysis-engine -e simulator -e libs/nvh_api_schemas
.venv/bin/python -m pytest analysis-engine/tests simulator/tests libs/nvh_contract/tests \
  libs/nvh_api_schemas/tests design-tokens/tests web-backend/tests -q
```
