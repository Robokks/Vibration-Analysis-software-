# Reports Screen: Cascade Filter + Summary Multi-Serial Selection

## Context

**Repo:** `robokks/vibration-analysis-software-`
**Branch:** `claude/nvh-software-python-28zib3`

**Current state** (`qt-app/src/nvh_qt_app/screens/reports.py`):
- Single flat combo box listing all test runs as `serial_number — overall_result`
- Hardcoded `MODEL_ID = "MODEL-A"`, `PROGRAM_NAME = "REVA"`, `GEAR_LABEL = "R"`,
  `DIRECTION = "RU"`, `SUMMARY_STAT_NAME = "RMS Avg"`
- No date filter, no cascade, no way to navigate by date → serial → repeat
- Summary tab: single X-chart for one stat, no multi-serial selection

**User's stated gaps:**
1. **Report screen**: cascade filter — Model → Date → Serial No → Serial Rpt No → display
2. **Summary tab**: same cascade filter option + multiple serial number selection for graphs

**Backend facts (no backend changes needed except one API client method):**
- `GET /test-runs?model_id=X` already filters by model
- `GET /models` already returns model list
- `GET /models/{id}/programs` already returns programs
- `GET /summaries?model_id=X` already returns SummaryDataRow list with `serial_no`, `rms_avg`,
  `peak`, `order_1x_mag`, `stamp` fields — usable directly for multi-serial graph
- `TestRunRow` has `model_id`, `serial_number`, `repeat_number`, `started_at` — all
  available in the `TestRun` pydantic model returned by the existing list endpoint
- All cascade filtering can be done **client-side** after a single `fetch_test_runs()` call

---

## Changes Required

### File 1: `qt-app/src/nvh_qt_app/api_client.py`

Add one new method (no other changes):

```python
def fetch_summaries(self, model_id: str, on_success: OnSuccess, on_error: OnError) -> None:
    self._get("/summaries", on_success, on_error, {"model_id": quote(model_id)})
```

---

### File 2: `qt-app/src/nvh_qt_app/screens/reports.py`

Full rewrite. Key structural changes:

#### Remove module-level constants

Delete `MODEL_ID`, `PROGRAM_NAME`, `GEAR_LABEL`, `DIRECTION`, `SUMMARY_STAT_NAME`.
Replace with instance variables.

#### New instance variables

```python
self._model_id: str | None = None
self._program_name: str | None = None
self._gear_label: str | None = None
self._direction: str = "RU"
self._all_runs: list[dict] = []   # full list for model, client-side filtered
self._all_summaries: list[dict] = []  # for multi-serial summary plot
```

#### New top "Selectors" panel

Replace the current single "Test run" panel with a filter panel containing:

**Row 1** (report context):
- `"Model:"` + `_model_combo` (QComboBox) — populated from `fetch_models()`
- `"Program:"` + `_program_combo` (QComboBox) — populated from `fetch_programs()`
- `"Gear:"` + `_gear_combo` (QComboBox, from model's gear list)
- `"Direction:"` + `_direction_combo` (QComboBox: RU / STYD / STYC / RD)

**Row 2** (cascade filter):
- `"Date:"` + `_date_combo` (QComboBox, items: "All" + unique YYYY-MM-DD extracted from `_all_runs`)
- `"Serial No:"` + `_serial_combo` (QComboBox, filtered by date)
- `"Serial Rpt No:"` + `_rpt_combo` (QComboBox, filtered by serial)

Cascade signal wiring (each blocks signals while populating):
- `_model_combo.currentIndexChanged` → `_on_model_changed()` →
  fetch programs, fetch test_runs, fetch summaries, repopulate `_date_combo`
- `_date_combo.currentIndexChanged` → `_on_date_changed()` →
  filter `_all_runs` by date, repopulate `_serial_combo` with unique serial numbers
- `_serial_combo.currentIndexChanged` → `_on_serial_changed()` →
  filter by serial, repopulate `_rpt_combo` with unique repeat numbers
- `_rpt_combo.currentIndexChanged` → `_on_rpt_changed()` →
  find the matching test_run_id, call `_load_reports_for_run(test_run_id)`

#### Cascade logic (pure client-side, no extra API calls)

```python
def _on_model_changed(self) -> None:
    self._model_id = self._model_combo.currentData()   # store model_id as userData
    if not self._model_id:
        return
    self._api.fetch_programs(self._model_id, self._on_programs, self._on_error)
    self._api.fetch_test_runs(self._model_id, self._on_runs_loaded, self._on_error)
    self._api.fetch_summaries(self._model_id, self._on_summaries_loaded, self._on_error)

def _on_runs_loaded(self, runs: list[dict]) -> None:
    self._all_runs = sorted(runs, key=lambda r: r["started_at"], reverse=True)
    self._repopulate_dates()

def _repopulate_dates(self) -> None:
    dates = ["All"] + sorted(
        {r["started_at"][:10] for r in self._all_runs}, reverse=True
    )
    # blockSignals, clear, addItems, unblockSignals
    self._date_combo.blockSignals(True)
    self._date_combo.clear()
    for d in dates:
        self._date_combo.addItem(d)
    self._date_combo.blockSignals(False)
    self._on_date_changed(0)

def _filtered_runs_by_date(self) -> list[dict]:
    date = self._date_combo.currentText()
    if date == "All":
        return self._all_runs
    return [r for r in self._all_runs if r["started_at"].startswith(date)]

def _on_date_changed(self, _index: int) -> None:
    runs = self._filtered_runs_by_date()
    serials = sorted({r["serial_number"] for r in runs})
    self._serial_combo.blockSignals(True)
    self._serial_combo.clear()
    for s in serials:
        self._serial_combo.addItem(s)
    self._serial_combo.blockSignals(False)
    self._on_serial_changed(0)

def _on_serial_changed(self, _index: int) -> None:
    serial = self._serial_combo.currentText()
    runs = [r for r in self._filtered_runs_by_date() if r["serial_number"] == serial]
    self._rpt_combo.blockSignals(True)
    self._rpt_combo.clear()
    for r in runs:
        label = f"Rpt {r['repeat_number']}  ({r['started_at'][:19]})"
        self._rpt_combo.addItem(label, userData=r["test_run_id"])
    self._rpt_combo.blockSignals(False)
    if runs:
        self._on_rpt_changed(0)

def _on_rpt_changed(self, index: int) -> None:
    test_run_id = self._rpt_combo.itemData(index)
    if not test_run_id:
        return
    self._api.fetch_test_run(test_run_id, self._on_test_run_detail, self._on_error)
```

#### `_on_test_run_detail` update

The existing `_on_test_run_detail` calls report endpoints with hardcoded constants.
Replace with instance variables:

```python
def _on_test_run_detail(self, detail: dict) -> None:
    dc_records = detail.get("dc_records") or []
    if not dc_records:
        return
    dc_id = dc_records[0]["dc_id"]
    pn = self._program_name or ""
    self._api.fetch_consolidated_report(dc_id, self._on_consolidated, self._on_error, program_name=pn)
    self._api.fetch_detailed_report(dc_id, self._on_detailed, self._on_error, program_name=pn)
    self._api.fetch_code_result_report(dc_id, self._on_code_result, self._on_error, program_name=pn)
    self._api.fetch_summary_report(
        self._model_id, self._gear_label or "R", self._direction,
        self._stat_name_combo.currentText(),
        self._on_summary, self._on_error, program_name=pn,
    )
```

#### Summary tab rebuild: multi-serial selection

Replace `_build_summary_tab()` with:

```python
def _build_summary_tab(self):
    panel = Panel()
    layout = QVBoxLayout(panel)

    # Stat name selector
    stat_row = QHBoxLayout()
    stat_row.addWidget(MonoLabel("Stat:"))
    self._stat_name_combo = QComboBox()
    for name in ["RMS Avg", "Peak", "Order 1x Mag"]:
        self._stat_name_combo.addItem(name)
    self._stat_name_combo.currentTextChanged.connect(self._on_stat_changed)
    stat_row.addWidget(self._stat_name_combo)
    stat_row.addStretch(1)
    layout.addLayout(stat_row)

    layout.addWidget(SectionTitle("Serial numbers"))

    # Multi-select serial list
    self._serial_list = QListWidget()
    self._serial_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    self._serial_list.setFixedHeight(120)
    layout.addWidget(self._serial_list)

    # Plot
    self._xchart_plot = MultiSeriesPlot([], max_samples=1024)
    self._xchart_plot.setMinimumHeight(300)
    layout.addWidget(self._xchart_plot)

    self._summary_meta = MonoLabel("(no data)")
    layout.addWidget(self._summary_meta)
    layout.addStretch(1)
    return panel
```

When `_all_summaries` is loaded (`_on_summaries_loaded`):
1. Extract unique serial numbers.
2. Populate `_serial_list` (one item per serial, all selected by default).

When selection changes (`_serial_list.itemSelectionChanged` → `_on_serial_selection_changed`):
1. Get selected serials from `_serial_list`.
2. For each selected serial, filter `_all_summaries` for that serial.
3. Get stat values from the field matching `_stat_name_combo.currentText()`
   (map: `"RMS Avg"` → `"rms_avg"`, `"Peak"` → `"peak"`, `"Order 1x Mag"` → `"order_1x_mag"`).
4. Call `_xchart_plot.set_series_data(serial, values)` for each.
5. Update `_summary_meta` with count info.

```python
def _on_summaries_loaded(self, rows: list[dict]) -> None:
    self._all_summaries = rows
    serials = sorted({r["serial_no"] for r in rows})
    self._serial_list.blockSignals(True)
    self._serial_list.clear()
    for s in serials:
        self._serial_list.addItem(s)
    self._serial_list.selectAll()   # all selected by default
    self._serial_list.blockSignals(False)
    self._on_serial_selection_changed()

_STAT_FIELD = {"RMS Avg": "rms_avg", "Peak": "peak", "Order 1x Mag": "order_1x_mag"}

def _on_serial_selection_changed(self) -> None:
    selected = [item.text() for item in self._serial_list.selectedItems()]
    field = _STAT_FIELD.get(self._stat_name_combo.currentText(), "rms_avg")
    # Remove old series not in selection
    for serial in list(self._xchart_plot.series_names()):
        if serial not in selected:
            self._xchart_plot.remove_series(serial)
    # Add/update series for selected
    for serial in selected:
        vals = [r[field] for r in self._all_summaries
                if r["serial_no"] == serial and r[field] is not None]
        self._xchart_plot.set_series_data(serial, vals)
    self._summary_meta.setText(f"{len(selected)} serial(s) selected / {len(self._all_summaries)} rows total")

def _on_stat_changed(self, _name: str) -> None:
    self._on_serial_selection_changed()
```

**Note on `MultiSeriesPlot.series_names()` and `remove_series()`:**
Check if these methods exist on `MultiSeriesPlot`
(`qt-app/src/nvh_qt_app/widgets/multi_series_plot.py`). If they don't, add them:

```python
def series_names(self) -> list[str]:
    return list(self._series.keys())

def remove_series(self, name: str) -> None:
    self._series.pop(name, None)
```

---

## Initialization flow

```python
def __init__(self, parent=None, api_client=None):
    super().__init__(parent)
    self._api = api_client or ApiClient()
    # ... build UI ...
    self._api.fetch_models(self._on_models_loaded, self._on_error)
```

`_on_models_loaded(models)`:
- Store model list. Populate `_model_combo` with `model_id` as text and also as `userData`.
- Set index 0 → triggers `_on_model_changed()`.

`_on_programs(programs)`:
- Populate `_program_combo`. Set index 0.

`_on_model_changed()` (as above): fetches programs + test_runs + summaries.

---

## Verification

```bash
.venv/bin/pip install -e qt-app
.venv/bin/python -m pytest web-backend/tests libs/nvh_contract/tests -q
# seed data and start backend
.venv/bin/python web-backend/scripts/seed_demo_data.py
.venv/bin/python -m uvicorn nvh_web_backend.app:app --reload &
.venv/bin/python -m nvh_qt_app
```

Manual checklist:
- [ ] Model combo populates on startup
- [ ] Date combo shows unique dates from loaded test runs; "All" shows every run
- [ ] Selecting a date narrows Serial No combo to serials tested on that date
- [ ] Selecting a serial narrows Serial Rpt No combo to that serial's repeats (with timestamp)
- [ ] Selecting a repeat loads Consolidated / Detailed / Code-Result / Summary tabs
- [ ] Program / Gear / Direction combos all work and drive report fetches
- [ ] Summary tab: serial list shows all unique serials, all pre-selected
- [ ] Deselecting serials removes their line from the X-chart
- [ ] Stat dropdown (RMS Avg / Peak / Order 1x Mag) switches the plotted field
- [ ] Multiple serials selected shows multiple lines in the plot
