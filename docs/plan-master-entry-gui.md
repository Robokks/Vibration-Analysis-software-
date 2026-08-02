# Master Entry GUI: Dynamic Selectors + Create/Edit Dialogs

## Context

**Repo:** `robokks/vibration-analysis-software-`
**Branch:** `claude/nvh-software-python-28zib3`

The Qt Master Entry screen (`qt-app/src/nvh_qt_app/screens/master_entry.py`)
has hardcoded `MODEL_ID = "MODEL-A"`, `PROGRAM_NAME = "REVA"`,
`GEAR_LABEL = "R"`, `DIRECTION = "RU"` with a comment explicitly flagging
them for revisiting once a second model/program/gear exists. The
`ApiClient` (`qt-app/src/nvh_qt_app/api_client.py`) has only `_get()` and
`_patch()` transport methods — no `_post()`, `_put()`, or `_delete()`.
The gear table is entirely read-only (`NoEditTriggers`). No creation
dialogs exist anywhere in the app.

Backend write endpoints are already shipped (commit `d5e5de6` on the branch).
Available: models CRUD (`POST /models`, `PUT /models/{id}`, `DELETE /models/{id}`),
program create/delete (`POST/DELETE /models/{id}/programs/{name}`),
import-from-master (`POST .../import-from-master`), limit-config CRUD,
table-config step CRUD.

User's stated gaps: "no provision to create new master / and no provision
to add gears or edit gear / and teeth values".

---

## Part 1 — `qt-app/src/nvh_qt_app/api_client.py`

### Transport methods (follow the `_patch()` sendCustomRequest pattern exactly)

```python
def _post(self, path, body, on_success, on_error, params=None):
    query = f"?{urlencode(params)}" if params else ""
    request = QNetworkRequest(QUrl(f"{self._base_url}{path}{query}"))
    request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
    reply = self._manager.sendCustomRequest(request, b"POST", json.dumps(body).encode("utf-8"))
    self._track(reply, on_success, on_error)

def _put(self, path, body, on_success, on_error, params=None):
    # identical to _post but verb=b"PUT"

def _delete(self, path, on_success, on_error):
    request = QNetworkRequest(QUrl(f"{self._base_url}{path}"))
    reply = self._manager.sendCustomRequest(request, b"DELETE", QByteArray())
    self._track(reply, on_success, on_error)
```

Add `QByteArray` to the `PySide6.QtCore` import line (already has `QUrl`).

### New public endpoint methods

| Method | HTTP | Backend endpoint |
|---|---|---|
| `post_model(body: dict, on_success, on_error)` | POST | `/models` |
| `put_model(model_id: str, body: dict, on_success, on_error)` | PUT | `/models/{model_id}` |
| `post_program(model_id: str, program_name: str, on_success, on_error)` | POST | `/models/{model_id}/programs` |
| `delete_program(model_id: str, program_name: str, on_success, on_error)` | DELETE | `/models/{model_id}/programs/{program_name}` |
| `post_import_from_master(model_id, program_name, gear_label, direction, on_success, on_error, channel_name="vib_a")` | POST | `/models/{model_id}/programs/{program_name}/import-from-master?gear_label=...&direction=...&channel_name=...` |

---

## Part 2 — `qt-app/src/nvh_qt_app/screens/master_entry.py`

### Remove module-level hardcoded constants

Delete `MODEL_ID`, `PROGRAM_NAME`, `GEAR_LABEL`, `DIRECTION`, `CHANNEL_NAME`
module-level constants and the comment above them.
Add a module-level `_CHANNEL_NAME = "vib_a"` constant (single channel is still out of scope to make dynamic).

### New instance variables

```python
self._current_model: dict | None = None   # cached full GET /models/{id} response
self._model_id: str | None = None
self._program_name: str | None = None
self._gear_label: str | None = None
self._direction: str = "RU"
```

### New "Selectors" panel (insert first in layout, before gear table)

```python
def _build_selectors_panel(self) -> Panel:
```

Layout: 3 rows inside a `QFormLayout` or `QGridLayout`:
- Row 1: `"Model:"` + `_model_combo` (QComboBox) + `QPushButton("+")` → `_on_new_model()`
- Row 2: `"Program:"` + `_program_combo` (QComboBox) + `QPushButton("+")` → `_on_new_program()`
- Row 3: `"Direction:"` + `_direction_combo` (QComboBox, items: RU / STYD / STYC / RD) + `QPushButton("Import from master")` → `_on_import_from_master()`

Signal wiring (block signals during programmatic population to avoid cascade):
- `_model_combo.currentIndexChanged` → `_on_model_selector_changed()`
- `_program_combo.currentIndexChanged` → `_on_program_selector_changed()`
- `_direction_combo.currentTextChanged` → `_on_direction_changed()`

### Modified "Model & gear teeth" panel

Keep the 5-column gear table columns unchanged (Gear | Drive teeth | Idler 1 | Layshaft | Ratio).
Add a button row **above** the table:

```python
btn_row = QHBoxLayout()
btn_row.addStretch(1)
self._add_gear_btn = QPushButton("Add gear")
self._edit_gear_btn = QPushButton("Edit gear")
self._edit_gear_btn.setEnabled(False)   # enabled only when a row is selected
btn_row.addWidget(self._add_gear_btn)
btn_row.addWidget(self._edit_gear_btn)
```

Change `setSelectionMode` from `NoSelection` to `SingleSelection`.
Connect `gear_table.itemSelectionChanged` to:
```python
self._edit_gear_btn.setEnabled(len(self._gear_table.selectedItems()) > 0)
```
Connect buttons: `_add_gear_btn.clicked` → `_on_add_gear()`, `_edit_gear_btn.clicked` → `_on_edit_gear()`.

### Direction cycle panel

Keep **unchanged** — it is informational only (shows the 4-step test sequence).
The active direction for the parameter table is now driven by `_direction_combo`.

### Initialization flow (replace the direct calls in `__init__`)

Replace:
```python
self._api.fetch_model(MODEL_ID, self._on_model, self._on_error)
self._api.fetch_parameters(MODEL_ID, PROGRAM_NAME, GEAR_LABEL, DIRECTION, ...)
```
With:
```python
self._api.fetch_models(self._on_models_loaded, self._on_error)
```

`_on_models_loaded(models: list[dict])`:
- Populate `_model_combo` with `model["model_id"]` for each entry (block signals while doing so).
- After population, set index to 0, then call `_on_model_selector_changed()` manually.

`_on_model_selector_changed()`:
- Extract `self._model_id` from `_model_combo.currentText()`.
- Call `fetch_model(self._model_id, self._on_model, self._on_error)`.
- Call `fetch_programs(self._model_id, self._on_programs_loaded, self._on_error)`.
- Clear parameter table.

`_on_programs_loaded(programs: list[dict])`:
- Populate `_program_combo` with `p["program_name"]` for each entry (block signals).
- Set index to 0, call `_on_program_selector_changed()` manually.

`_on_program_selector_changed()`:
- Extract `self._program_name`.
- If `self._model_id` and `self._program_name` and `self._gear_label`, call `fetch_parameters(...)`.

`_on_direction_changed(direction: str)`:
- Set `self._direction = direction`.
- Refresh parameter table if all three keys are set.

`_on_model(model: dict)` (existing handler, add two lines):
- Existing: populate gear table from `model["ratios"]`.
- Add: `self._current_model = model`.
- Add: if `self._gear_label is None`, set `self._gear_label = sorted(model["ratios"])[0]`.

### New dialogs (inner classes at bottom of `master_entry.py`)

**`_NewModelDialog(QDialog)`**

```python
class _NewModelDialog(QDialog):
    def __init__(self, api: ApiClient, on_created, status_label, parent=None): ...
```

Fields:
- `model_id` — QLineEdit (required)
- `model_name` — QLineEdit (required)

OK button triggers:
```python
api.post_model(
    {"model_id": model_id_text, "model_name": model_name_text,
     "drive_teeth": {}, "idler_teeth_1": {}, "layshaft_teeth": {}, "ratios": {}},
    on_success=lambda result: (self.accept(), on_created(result)),
    on_error=lambda msg: status_label.setText(f"create model failed: {msg}"),
)
```
On 409 (conflict) the error callback fires; don't close the dialog — the status label shows the message.

**`_NewProgramDialog(QDialog)`**

```python
class _NewProgramDialog(QDialog):
    def __init__(self, model_id, gear_label, direction, api, on_created, status_label, parent=None): ...
```

Fields:
- `program_name` — QLineEdit (required)
- `QCheckBox("Import limits from master immediately")` — default checked

OK button:
1. Call `api.post_program(model_id, program_name_text, on_success, on_error)`.
2. `on_success(result)`: if checkbox checked, call
   `api.post_import_from_master(model_id, program_name_text, gear_label, direction, on_imported, on_error)`.
3. `on_imported(rows)`: accept dialog, call `on_created(result)`.
4. If checkbox unchecked: accept immediately after program created.

**`_GearDialog(QDialog)`**

```python
class _GearDialog(QDialog):
    def __init__(self, mode: str, current_model: dict, gear_label: str | None,
                 model_id: str, api: ApiClient, on_saved, status_label, parent=None): ...
```

Fields:
- `gear_label` — QLineEdit (read-only when `mode="edit"`, editable when `mode="add"`)
- `drive_teeth` — QLineEdit with `QIntValidator`
- `idler_teeth_1` — QLineEdit with `QIntValidator`
- `layshaft_teeth` — QLineEdit with `QIntValidator`
- `ratio` — QLineEdit with `QDoubleValidator`

When `mode="edit"`: pre-fill all fields from `current_model` dicts for `gear_label`.

OK button:
1. Copy `current_model` to `updated` dict.
2. Set `updated["drive_teeth"][label] = int(drive_teeth_text)` etc.
3. Set `updated["ratios"][label] = float(ratio_text)`.
4. Build full `ModelUpdate`-shaped body (all fields from `updated`):
   `api.put_model(model_id, updated_body, on_success, on_error)`.
5. `on_success(model)`: accept dialog, call `on_saved(model)`.

`_on_add_gear()` in `MasterEntryScreen`:
```python
dlg = _GearDialog("add", self._current_model, None, self._model_id,
                  self._api, self._on_gear_saved, self._status, self)
dlg.open()
```

`_on_edit_gear()` in `MasterEntryScreen`:
```python
row = self._gear_table.currentRow()
label = self._gear_table.item(row, 0).text()
dlg = _GearDialog("edit", self._current_model, label, self._model_id,
                  self._api, self._on_gear_saved, self._status, self)
dlg.open()
```

`_on_gear_saved(model: dict)` in `MasterEntryScreen`:
```python
self._current_model = model
self._on_model(model)   # reuse existing handler to repopulate gear table
```

### Patch call updates in `_on_numeric_committed` and `_on_in_table_toggled`

Replace every bare `MODEL_ID`, `PROGRAM_NAME`, `GEAR_LABEL`, `DIRECTION`, `CHANNEL_NAME`
with `self._model_id`, `self._program_name`, `self._gear_label`, `self._direction`, `_CHANNEL_NAME`.

Add guards at the top of each handler:
```python
if self._model_id is None or self._program_name is None or self._gear_label is None:
    return
```

---

## Verification

```bash
# Install updated packages
.venv/bin/pip install -e qt-app -e libs/nvh_api_schemas

# All existing tests must still pass (no test changes required for this plan)
.venv/bin/python -m pytest web-backend/tests libs/nvh_contract/tests analysis-engine/tests -q

# Seed demo data and start backend
.venv/bin/python web-backend/scripts/seed_demo_data.py
.venv/bin/python -m uvicorn nvh_web_backend.app:app --reload &

# Launch Qt app (manual visual verification)
.venv/bin/python -m nvh_qt_app
```

Manual checklist:
- [ ] Model combo populates with existing models on startup
- [ ] "+" next to Model creates a new model (appears in combo, auto-selected)
- [ ] Program combo populates for selected model; switches when model changes
- [ ] "+" next to Program creates a new program; if "Import from master" checked, parameter table populates with limit configs
- [ ] Direction combo switches parameter table between directions
- [ ] "Add gear" opens dialog, new gear row appears in gear table and gear label appears in parameter-query context after save
- [ ] "Edit gear" (enabled when a gear row is selected) opens pre-filled dialog, updated values visible after save
- [ ] Limit/threshold edits and "In table" toggles still work with dynamic selectors (no regressions from old hardcoded path)
