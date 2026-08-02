from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nvh_design_tokens import load_tokens

from ..api_client import ApiClient
from ..widgets.labels import Chip, MonoLabel, SectionTitle
from ..widgets.panel import Panel

# Single-channel is still out of scope, but we drop the other hardcoded
# constants (MODEL_ID, PROGRAM_NAME, GEAR_LABEL, DIRECTION) now that the
# UI has dynamic selectors + a create-new flow (see Master Entry GUI plan).
_CHANNEL_NAME = "vib_a"

_DIRECTION_CYCLE = ["RU", "STYD", "STYC", "RD"]

_PARAMETER_COLUMNS = [
    "Parameter", "Order", "Master mean", "Band min", "Band max",
    "Limit low", "Limit high", "Threshold low", "Threshold high", "In table",
]
_COL_STAT_NAME = 0
_COL_LIMIT_LOW = 5
_COL_LIMIT_HIGH = 6
_COL_THRESHOLD_LOW = 7
_COL_THRESHOLD_HIGH = 8
_COL_IN_TABLE = 9

# Column -> (field key, PATCH method name on ApiClient). Order matters --
# used both for rendering the editable cell widgets and for restoring one on
# a failed PATCH from _restore_editor().
_NUMERIC_EDIT_COLUMNS: tuple[tuple[int, str], ...] = (
    (_COL_LIMIT_LOW, "limit_low"),
    (_COL_LIMIT_HIGH, "limit_high"),
    (_COL_THRESHOLD_LOW, "threshold_low"),
    (_COL_THRESHOLD_HIGH, "threshold_high"),
)


class MasterEntryScreen(QWidget):
    def __init__(self, parent=None, api_client: ApiClient | None = None) -> None:
        super().__init__(parent)
        self._api = api_client if api_client is not None else ApiClient()
        self._error_shown = False
        # stat_name -> latest ParameterCatalogRowOut dict, so a PATCH round
        # trip can restore the pre-edit cell value on failure and keep the
        # "other" column's number when only one column changes.
        self._rows_by_stat: dict[str, dict] = {}
        # Dynamic selectors + cached model (see the Master Entry GUI plan --
        # these replace the old MODEL_ID / PROGRAM_NAME / GEAR_LABEL / DIRECTION
        # module-level constants).
        self._current_model: dict | None = None
        self._model_id: str | None = None
        self._program_name: str | None = None
        self._gear_label: str | None = None
        self._direction: str = "RU"
        self._load_palette()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._status = MonoLabel("loading models…")
        layout.addWidget(self._status)

        layout.addWidget(self._build_selectors_panel())
        layout.addWidget(self._build_model_gear_panel())
        layout.addWidget(self._build_direction_panel())
        layout.addWidget(self._build_parameter_panel())
        layout.addStretch(1)

        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)

        # Boot: fetch the list of models, then cascade into the first one.
        self._api.fetch_models(self._on_models_loaded, self._on_error)

    # --- panels ------------------------------------------------------

    def _build_selectors_panel(self) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Selectors"))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Model row: combo + "+"
        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(220)
        self._model_combo.currentIndexChanged.connect(self._on_model_selector_changed)
        model_row.addWidget(self._model_combo, 1)
        self._new_model_btn = QPushButton("+")
        self._new_model_btn.setToolTip("Create a new model")
        self._new_model_btn.setFixedWidth(32)
        self._new_model_btn.clicked.connect(self._on_new_model)
        model_row.addWidget(self._new_model_btn)
        form.addRow("Model:", model_row)

        # Program row: combo + "+"
        program_row = QHBoxLayout()
        self._program_combo = QComboBox()
        self._program_combo.setMinimumWidth(220)
        self._program_combo.currentIndexChanged.connect(self._on_program_selector_changed)
        program_row.addWidget(self._program_combo, 1)
        self._new_program_btn = QPushButton("+")
        self._new_program_btn.setToolTip("Create a new program (master profile)")
        self._new_program_btn.setFixedWidth(32)
        self._new_program_btn.clicked.connect(self._on_new_program)
        program_row.addWidget(self._new_program_btn)
        form.addRow("Program:", program_row)

        # Direction row: combo + "Import from master" button
        direction_row = QHBoxLayout()
        self._direction_combo = QComboBox()
        for direction in _DIRECTION_CYCLE:
            self._direction_combo.addItem(direction)
        self._direction_combo.setCurrentText(self._direction)
        self._direction_combo.currentTextChanged.connect(self._on_direction_changed)
        direction_row.addWidget(self._direction_combo, 1)
        self._import_master_btn = QPushButton("Import from master")
        self._import_master_btn.setToolTip(
            "Seed LIMIT/THRESHOLD rows for this (gear, direction, channel) "
            "from the model's master signatures."
        )
        self._import_master_btn.clicked.connect(self._on_import_from_master)
        direction_row.addWidget(self._import_master_btn)
        form.addRow("Direction:", direction_row)

        panel_layout.addLayout(form)
        return panel

    def _build_model_gear_panel(self) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Model & gear teeth"))

        # Button row above the table -- add/edit gear.
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._add_gear_btn = QPushButton("Add gear")
        self._add_gear_btn.clicked.connect(self._on_add_gear)
        self._edit_gear_btn = QPushButton("Edit gear")
        self._edit_gear_btn.setEnabled(False)   # enabled only when a row is selected
        self._edit_gear_btn.clicked.connect(self._on_edit_gear)
        btn_row.addWidget(self._add_gear_btn)
        btn_row.addWidget(self._edit_gear_btn)
        panel_layout.addLayout(btn_row)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Gear", "Drive teeth", "Idler 1", "Layshaft", "Ratio"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # SingleSelection so the Edit gear button can enable/disable off it.
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.itemSelectionChanged.connect(self._on_gear_selection_changed)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        panel_layout.addWidget(table)
        self._gear_table = table
        return panel

    def _build_direction_panel(self) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Direction cycle"))
        row = QHBoxLayout()
        for index, direction in enumerate(_DIRECTION_CYCLE):
            row.addWidget(Chip(direction))
            if index < len(_DIRECTION_CYCLE) - 1:
                row.addWidget(MonoLabel("→"))
        row.addStretch(1)
        panel_layout.addLayout(row)
        return panel

    def _build_parameter_panel(self) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Master & limit parameters"))

        table = QTableWidget(0, len(_PARAMETER_COLUMNS))
        table.setHorizontalHeaderLabels(_PARAMETER_COLUMNS)
        table.verticalHeader().setVisible(False)
        # No cell-level edit triggers -- the LIMIT/THRESHOLD columns get real
        # QLineEdit cell widgets instead so we can validate, catch
        # editing-finished, and paint feedback without shipping our own
        # QStyledItemDelegate.
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(1, len(_PARAMETER_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        panel_layout.addWidget(table)
        self._param_table = table
        return panel

    # --- boot / cascade handlers -------------------------------------

    def _on_models_loaded(self, models: list[dict]) -> None:
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for entry in models:
            self._model_combo.addItem(entry["model_id"])
        self._model_combo.blockSignals(False)
        if self._model_combo.count() == 0:
            self._status.setText("no models yet -- click + next to Model to create one")
            return
        self._model_combo.setCurrentIndex(0)
        self._on_model_selector_changed()

    def _on_model_selector_changed(self) -> None:
        model_id = self._model_combo.currentText()
        if not model_id:
            return
        self._model_id = model_id
        # Reset gear + program state -- these are model-scoped.
        self._gear_label = None
        self._program_name = None
        self._rows_by_stat = {}
        self._param_table.setRowCount(0)
        self._status.setText(f"loading model {model_id}…")
        self._api.fetch_model(model_id, self._on_model, self._on_error)
        self._api.fetch_programs(model_id, self._on_programs_loaded, self._on_error)

    def _on_programs_loaded(self, programs: list[dict]) -> None:
        self._program_combo.blockSignals(True)
        self._program_combo.clear()
        for entry in programs:
            self._program_combo.addItem(entry["program_name"])
        self._program_combo.blockSignals(False)
        if self._program_combo.count() == 0:
            self._program_name = None
            self._param_table.setRowCount(0)
            if not self._error_shown:
                self._status.setText(
                    f"model {self._model_id}: no programs yet -- click + next to Program"
                )
            return
        self._program_combo.setCurrentIndex(0)
        self._on_program_selector_changed()

    def _on_program_selector_changed(self) -> None:
        program = self._program_combo.currentText()
        if not program:
            return
        self._program_name = program
        self._refresh_parameter_table()

    def _on_direction_changed(self, direction: str) -> None:
        self._direction = direction
        self._refresh_parameter_table()

    def _refresh_parameter_table(self) -> None:
        if not (self._model_id and self._program_name and self._gear_label):
            return
        self._api.fetch_parameters(
            self._model_id, self._program_name, self._gear_label, self._direction,
            self._on_parameters, self._on_error, channel_name=_CHANNEL_NAME,
        )

    # --- model + gear-table population -------------------------------

    def _on_model(self, model: dict) -> None:
        # Cache the full ModelOut so the gear-edit dialog can compose a
        # ModelUpdate body without a re-fetch.
        self._current_model = model
        gear_labels = sorted(model["ratios"].keys())
        table = self._gear_table
        table.setRowCount(len(gear_labels))
        for r, label in enumerate(gear_labels):
            values = [
                label,
                str(model["drive_teeth"].get(label, "—")),
                str(model["idler_teeth_1"].get(label, "—")),
                str(model["layshaft_teeth"].get(label, "—")),
                f"{model['ratios'][label]:.3f}",
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))
        # Default the parameter-query gear to the first available label
        # so the operator sees data without an extra click. Only auto-set
        # if we haven't picked one yet -- don't blow away an operator's
        # selection on a Model reload.
        if gear_labels and self._gear_label is None:
            self._gear_label = gear_labels[0]
            self._refresh_parameter_table()
        if not self._error_shown:
            self._status.setText(f"model {self._model_id} loaded")

    def _on_gear_selection_changed(self) -> None:
        self._edit_gear_btn.setEnabled(len(self._gear_table.selectedItems()) > 0)

    def _on_parameters(self, rows: list[dict]) -> None:
        table = self._param_table
        table.setRowCount(len(rows))
        self._rows_by_stat = {}
        for r, row in enumerate(rows):
            self._rows_by_stat[row["stat_name"]] = row
            master = row.get("master")
            values = [
                row["stat_name"],
                "" if row.get("order_number") is None else f"{row['order_number']:.4g}",
                "" if not master else f"{master['mean_value']:.4g}",
                "" if not master else f"{master['band_min']:.4g}",
                "" if not master else f"{master['band_max']:.4g}",
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))

            for col, key in _NUMERIC_EDIT_COLUMNS:
                stored = row.get(key)
                if stored is None:
                    table.setCellWidget(r, col, None)
                    table.setItem(r, col, QTableWidgetItem("—"))
                else:
                    editor = _NumericEditor(row["stat_name"], key, stored, self)
                    editor.value_committed.connect(self._on_numeric_committed)
                    table.setCellWidget(r, col, editor)

            button = _InTableToggle(
                row["stat_name"], bool(row.get("included_in_table_config")),
                self._pass_color, self._muted_color, self,
            )
            button.toggled_by_user.connect(self._on_in_table_toggled)
            table.setCellWidget(r, _COL_IN_TABLE, button)
        if not self._error_shown:
            self._status.setText(f"{len(rows)} parameters loaded")

    # --- PATCH dispatch (uses instance selectors, not the old constants)

    def _on_numeric_committed(self, stat_name: str, field: str, new_value: float) -> None:
        """Fires when the operator finishes typing in a LIMIT or THRESHOLD
        cell -- dispatches to the matching PATCH endpoint. Same shape as
        the sibling web-frontend's NumericCell commit path."""
        if self._model_id is None or self._program_name is None or self._gear_label is None:
            return
        row = self._rows_by_stat.get(stat_name)
        if row is None:
            return
        self._status.setText(f"saving {stat_name} {field}={new_value}…")

        def _on_success(updated: dict) -> None:
            self._rows_by_stat[stat_name] = updated
            table = self._param_table
            for r in range(table.rowCount()):
                item = table.item(r, _COL_STAT_NAME)
                if item is None or item.text() != stat_name:
                    continue
                for col, key in _NUMERIC_EDIT_COLUMNS:
                    widget = table.cellWidget(r, col)
                    if isinstance(widget, _NumericEditor):
                        widget.set_value(updated.get(key))
                in_table = table.cellWidget(r, _COL_IN_TABLE)
                if isinstance(in_table, _InTableToggle):
                    in_table.set_included(bool(updated.get("included_in_table_config")))
                break
            self._status.setText(f"{stat_name} {field} saved")

        def _on_failure(message: str) -> None:
            self._restore_editor(stat_name, field, row.get(field))
            self._status.setText(f"save failed for {stat_name} ({message})")

        if field in ("limit_low", "limit_high"):
            self._api.patch_limit(
                self._model_id, self._program_name, stat_name,
                self._gear_label, self._direction,
                new_value if field == "limit_low" else row.get("limit_low") or 0.0,
                new_value if field == "limit_high" else row.get("limit_high") or 0.0,
                _on_success, _on_failure, channel_name=_CHANNEL_NAME,
            )
        else:
            self._api.patch_threshold(
                self._model_id, self._program_name, stat_name,
                self._gear_label, self._direction,
                new_value if field == "threshold_low" else row.get("threshold_low") or 0.0,
                new_value if field == "threshold_high" else row.get("threshold_high") or 0.0,
                _on_success, _on_failure, channel_name=_CHANNEL_NAME,
            )

    def _on_in_table_toggled(self, stat_name: str, included: bool) -> None:
        """Fires when the operator clicks the 'In table' toggle -- posts to
        the Table Config parameter inclusion endpoint. The server response
        is the refreshed ParameterCatalogRowOut, which we mirror back into
        the local cache and the button's visual state."""
        if self._model_id is None or self._program_name is None or self._gear_label is None:
            return
        row = self._rows_by_stat.get(stat_name)
        previous = bool(row.get("included_in_table_config")) if row else not included
        self._status.setText(f"saving {stat_name} in-table={included}…")

        def _on_success(updated: dict) -> None:
            self._rows_by_stat[stat_name] = updated
            self._restore_in_table(stat_name, bool(updated.get("included_in_table_config")))
            self._status.setText(f"{stat_name} in-table saved")

        def _on_failure(message: str) -> None:
            self._restore_in_table(stat_name, previous)
            self._status.setText(f"save failed for {stat_name} ({message})")

        self._api.patch_table_config_parameter(
            self._model_id, self._program_name, stat_name,
            self._gear_label, self._direction,
            included, _on_success, _on_failure, channel_name=_CHANNEL_NAME,
        )

    def _restore_editor(self, stat_name: str, field: str, stored) -> None:
        table = self._param_table
        col = {name: col for col, name in _NUMERIC_EDIT_COLUMNS}[field]
        for r in range(table.rowCount()):
            item = table.item(r, _COL_STAT_NAME)
            if item is None or item.text() != stat_name:
                continue
            widget = table.cellWidget(r, col)
            if isinstance(widget, _NumericEditor):
                widget.set_value(stored)
            return

    def _restore_in_table(self, stat_name: str, included: bool) -> None:
        table = self._param_table
        for r in range(table.rowCount()):
            item = table.item(r, _COL_STAT_NAME)
            if item is None or item.text() != stat_name:
                continue
            widget = table.cellWidget(r, _COL_IN_TABLE)
            if isinstance(widget, _InTableToggle):
                widget.set_included(included)
            return

    def _on_error(self, message: str) -> None:
        self._error_shown = True
        self._status.setText(f"failed to reach backend: {message}")

    # --- create / edit dialog wiring ---------------------------------

    def _on_new_model(self) -> None:
        dlg = _NewModelDialog(self._api, self._on_model_created, self._status, self)
        dlg.open()

    def _on_new_program(self) -> None:
        if self._model_id is None:
            self._status.setText("select a model first before creating a program")
            return
        if self._gear_label is None:
            self._status.setText("model has no gears yet -- add a gear before a program")
            return
        dlg = _NewProgramDialog(
            self._model_id, self._gear_label, self._direction,
            self._api, self._on_program_created, self._status, self,
        )
        dlg.open()

    def _on_add_gear(self) -> None:
        if self._current_model is None or self._model_id is None:
            self._status.setText("wait for the model to load before adding a gear")
            return
        dlg = _GearDialog(
            "add", self._current_model, None, self._model_id,
            self._api, self._on_gear_saved, self._status, self,
        )
        dlg.open()

    def _on_edit_gear(self) -> None:
        if self._current_model is None or self._model_id is None:
            return
        row = self._gear_table.currentRow()
        if row < 0:
            return
        item = self._gear_table.item(row, 0)
        if item is None:
            return
        label = item.text()
        dlg = _GearDialog(
            "edit", self._current_model, label, self._model_id,
            self._api, self._on_gear_saved, self._status, self,
        )
        dlg.open()

    def _on_import_from_master(self) -> None:
        if not (self._model_id and self._program_name and self._gear_label):
            self._status.setText("need a model, program and gear before import")
            return
        self._status.setText(
            f"importing masters for {self._model_id}/{self._program_name} "
            f"({self._gear_label}/{self._direction})…"
        )
        self._api.post_import_from_master(
            self._model_id, self._program_name, self._gear_label, self._direction,
            self._on_import_finished, self._on_error, channel_name=_CHANNEL_NAME,
        )

    def _on_import_finished(self, _payload) -> None:
        self._status.setText("import from master done -- refreshing parameters")
        self._refresh_parameter_table()

    def _on_model_created(self, model: dict) -> None:
        """Re-fetch the models list and select the new one."""
        created_id = model.get("model_id") if isinstance(model, dict) else None
        self._status.setText(f"model {created_id} created")

        def _pick_created(models: list[dict]) -> None:
            self._model_combo.blockSignals(True)
            self._model_combo.clear()
            for entry in models:
                self._model_combo.addItem(entry["model_id"])
            self._model_combo.blockSignals(False)
            index = self._model_combo.findText(created_id) if created_id else -1
            if index >= 0:
                self._model_combo.setCurrentIndex(index)
            self._on_model_selector_changed()

        self._api.fetch_models(_pick_created, self._on_error)

    def _on_program_created(self, program: dict) -> None:
        """Re-fetch programs for the current model and select the new one."""
        created = program.get("program_name") if isinstance(program, dict) else None
        self._status.setText(f"program {created} created")
        if self._model_id is None:
            return

        def _pick_created(programs: list[dict]) -> None:
            self._program_combo.blockSignals(True)
            self._program_combo.clear()
            for entry in programs:
                self._program_combo.addItem(entry["program_name"])
            self._program_combo.blockSignals(False)
            index = self._program_combo.findText(created) if created else -1
            if index >= 0:
                self._program_combo.setCurrentIndex(index)
            self._on_program_selector_changed()

        self._api.fetch_programs(self._model_id, _pick_created, self._on_error)

    def _on_gear_saved(self, model: dict) -> None:
        # Reuse the existing model handler to repopulate the gear table.
        self._current_model = model
        self._on_model(model)

    # --- theme -------------------------------------------------------

    def _load_palette(self) -> None:
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        palette_name = theme.palette_name if theme is not None else "dark"
        palette = load_tokens()["color"]["palettes"][palette_name]
        self._pass_color = palette["pass"]
        self._alarm_color = palette["alarm"]
        self._muted_color = palette["secondaryText"]

    def _on_theme_changed(self, _palette_name: str) -> None:
        self._load_palette()
        # Refresh every In-table toggle button in the current parameter
        # table. Threshold/limit editors use type-selector QSS so the
        # app-level setStyleSheet() refresh already handled them.
        table = self._param_table
        for r in range(table.rowCount()):
            widget = table.cellWidget(r, _COL_IN_TABLE)
            if isinstance(widget, _InTableToggle):
                widget.apply_palette(self._pass_color, self._muted_color)


class _NumericEditor(QLineEdit):
    """Inline QLineEdit for a single editable LIMIT or THRESHOLD cell --
    commits on editingFinished (Enter or focus-out), validates as a plain
    double, keeps its own "last committed value" so an Escape or a failed
    PATCH can revert without a re-fetch. The screen dispatches to the
    matching PATCH endpoint based on the `field` name."""

    value_committed = Signal(str, str, float)

    def __init__(self, stat_name: str, field: str, initial: float, parent=None) -> None:
        super().__init__(parent)
        self._stat_name = stat_name
        self._field = field
        self._committed = float(initial)
        self.setValidator(QDoubleValidator(self))
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.set_value(initial)
        self.editingFinished.connect(self._on_editing_finished)

    def set_value(self, value) -> None:
        if value is None:
            self._committed = 0.0
            self.setText("")
            return
        self._committed = float(value)
        # Match the display precision used by the display-only columns so
        # the visual language of the row stays uniform (0.4g -> 4 sig figs).
        self.setText(f"{self._committed:.4g}")

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.set_value(self._committed)
            self.clearFocus()
            return
        super().keyPressEvent(event)

    def _on_editing_finished(self) -> None:
        text = self.text().strip()
        try:
            parsed = float(text) if text else 0.0
        except ValueError:
            self.set_value(self._committed)
            return
        if parsed == self._committed:
            return
        self._committed = parsed
        self.value_committed.emit(self._stat_name, self._field, parsed)


class _InTableToggle(QToolButton):
    """Clickable 'In table' toggle -- one QToolButton per row, checkable,
    labeled 'yes'/'no'. Uses the theme's `pass` (dark green) accent when
    included, muted otherwise. Emits toggled_by_user only on real user
    clicks (not on programmatic set_included calls) so the screen can
    dispatch a PATCH without racing itself."""

    toggled_by_user = Signal(str, bool)

    def __init__(
        self, stat_name: str, initial: bool,
        pass_color: str, muted_color: str, parent=None,
    ) -> None:
        super().__init__(parent)
        self._stat_name = stat_name
        self._pass_color = pass_color
        self._muted_color = muted_color
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_included(initial)
        self.clicked.connect(self._on_clicked)

    def set_included(self, included: bool) -> None:
        # Block signals so set_included() called from a PATCH response
        # doesn't recursively re-fire toggled_by_user.
        self.blockSignals(True)
        self.setChecked(included)
        self._paint()
        self.blockSignals(False)

    def _paint(self) -> None:
        included = self.isChecked()
        self.setText("yes" if included else "no")
        color = self._pass_color if included else self._muted_color
        self.setStyleSheet(
            "QToolButton { "
            f"color: {color}; "
            "border: none; padding: 4px 12px; font-family: 'IBM Plex Mono', monospace; "
            "font-size: 11px; }"
        )

    def apply_palette(self, pass_color: str, muted_color: str) -> None:
        self._pass_color = pass_color
        self._muted_color = muted_color
        self._paint()

    def _on_clicked(self) -> None:
        self._paint()
        self.toggled_by_user.emit(self._stat_name, self.isChecked())


# ---------------------------------------------------------------------------
# Create / edit dialogs
#
# All three dialogs follow the same async pattern: the OK button fires the
# API call, and only accepts (closes) the dialog inside the success
# callback. Failures leave the dialog open with the error surfaced on the
# parent screen's status label -- matches the "no blocking QDialog.exec()"
# rule in the Master Entry GUI plan.
# ---------------------------------------------------------------------------


class _NewModelDialog(QDialog):
    """Dialog: create a new empty model shell.

    The model starts with empty dicts for all gear-teeth fields; the
    operator populates gears via 'Add gear' afterwards. This matches the
    real LabVIEW MASTER SETUP screen's flow (save a model shell, then
    add gears one at a time)."""

    def __init__(self, api: ApiClient, on_created, status_label, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._on_created = on_created
        self._status_label = status_label
        self.setWindowTitle("New model")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._model_id_edit = QLineEdit()
        self._model_id_edit.setPlaceholderText("e.g. MODEL-A")
        self._model_name_edit = QLineEdit()
        self._model_name_edit.setPlaceholderText("Human-facing name")
        form.addRow("Model ID:", self._model_id_edit)
        form.addRow("Model name:", self._model_name_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._buttons = buttons

    def _on_ok(self) -> None:
        model_id = self._model_id_edit.text().strip()
        model_name = self._model_name_edit.text().strip()
        if not model_id or not model_name:
            self._status_label.setText("model_id and model_name are required")
            return
        # Disable Ok while the request is in flight so a double-click
        # can't fire two POSTs.
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        def _on_success(result) -> None:
            self.accept()
            self._on_created(result)

        def _on_error(message: str) -> None:
            self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            self._status_label.setText(f"create model failed: {message}")

        body = {
            "model_id": model_id,
            "model_name": model_name,
            "drive_teeth": {},
            "idler_teeth_1": {},
            "layshaft_teeth": {},
            "ratios": {},
        }
        self._api.post_model(body, _on_success, _on_error)


class _NewProgramDialog(QDialog):
    """Dialog: create a new program (master profile) under the current
    model, optionally seeding LIMIT rows from the master signatures."""

    def __init__(
        self, model_id: str, gear_label: str, direction: str,
        api: ApiClient, on_created, status_label, parent=None,
    ) -> None:
        super().__init__(parent)
        self._model_id = model_id
        self._gear_label = gear_label
        self._direction = direction
        self._api = api
        self._on_created = on_created
        self._status_label = status_label
        self.setWindowTitle("New program")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._program_name_edit = QLineEdit()
        self._program_name_edit.setPlaceholderText("e.g. REVA")
        form.addRow("Program name:", self._program_name_edit)
        layout.addLayout(form)

        self._import_check = QCheckBox("Import limits from master immediately")
        self._import_check.setChecked(True)
        layout.addWidget(self._import_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._buttons = buttons

    def _on_ok(self) -> None:
        program_name = self._program_name_edit.text().strip()
        if not program_name:
            self._status_label.setText("program_name is required")
            return
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        wants_import = self._import_check.isChecked()

        def _on_import_success(_rows) -> None:
            self.accept()
            self._on_created({"program_name": program_name})

        def _on_import_error(message: str) -> None:
            # The program itself was created; report the import error
            # but still accept -- the operator can retry the import from
            # the "Import from master" button.
            self.accept()
            self._on_created({"program_name": program_name})
            self._status_label.setText(f"program created, import failed: {message}")

        def _on_program_success(result) -> None:
            if wants_import:
                self._api.post_import_from_master(
                    self._model_id, program_name,
                    self._gear_label, self._direction,
                    _on_import_success, _on_import_error,
                    channel_name=_CHANNEL_NAME,
                )
            else:
                self.accept()
                self._on_created(result)

        def _on_program_error(message: str) -> None:
            self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            self._status_label.setText(f"create program failed: {message}")

        self._api.post_program(self._model_id, program_name, _on_program_success, _on_program_error)


class _GearDialog(QDialog):
    """Dialog: add or edit one gear on the currently selected model.

    Sends a full ModelUpdate PUT -- copies the cached model dict, mutates
    the four gear-scoped keys, and pushes the whole body back. The plan
    warns explicitly: never send a partial ModelUpdate body."""

    def __init__(
        self, mode: str, current_model: dict, gear_label: str | None,
        model_id: str, api: ApiClient, on_saved, status_label, parent=None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._current_model = current_model
        self._model_id = model_id
        self._api = api
        self._on_saved = on_saved
        self._status_label = status_label
        self._original_label = gear_label

        self.setWindowTitle("Edit gear" if mode == "edit" else "Add gear")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._gear_label_edit = QLineEdit()
        self._gear_label_edit.setPlaceholderText("e.g. R, I, II, III")
        if mode == "edit":
            self._gear_label_edit.setText(gear_label or "")
            self._gear_label_edit.setReadOnly(True)
        form.addRow("Gear label:", self._gear_label_edit)

        self._drive_edit = QLineEdit()
        self._drive_edit.setValidator(QIntValidator(1, 1_000, self))
        form.addRow("Drive teeth:", self._drive_edit)

        self._idler_edit = QLineEdit()
        self._idler_edit.setValidator(QIntValidator(1, 1_000, self))
        form.addRow("Idler 1 teeth:", self._idler_edit)

        self._layshaft_edit = QLineEdit()
        self._layshaft_edit.setValidator(QIntValidator(1, 1_000, self))
        form.addRow("Layshaft teeth:", self._layshaft_edit)

        self._ratio_edit = QLineEdit()
        self._ratio_edit.setValidator(QDoubleValidator(0.0, 1_000.0, 4, self))
        form.addRow("Ratio:", self._ratio_edit)

        # Pre-fill on edit.
        if mode == "edit" and gear_label is not None:
            drive = current_model.get("drive_teeth", {}).get(gear_label)
            idler = current_model.get("idler_teeth_1", {}).get(gear_label)
            layshaft = current_model.get("layshaft_teeth", {}).get(gear_label)
            ratio = current_model.get("ratios", {}).get(gear_label)
            if drive is not None:
                self._drive_edit.setText(str(drive))
            if idler is not None:
                self._idler_edit.setText(str(idler))
            if layshaft is not None:
                self._layshaft_edit.setText(str(layshaft))
            if ratio is not None:
                self._ratio_edit.setText(f"{ratio:.4g}")

        layout.addLayout(form)

        # Reserved for surface-level validation feedback inside the dialog.
        self._dialog_message = QLabel("")
        self._dialog_message.setStyleSheet("color: #c94a4a;")
        layout.addWidget(self._dialog_message)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._buttons = buttons

    def _on_ok(self) -> None:
        label = (self._original_label if self._mode == "edit"
                 else self._gear_label_edit.text().strip())
        if not label:
            self._dialog_message.setText("gear label is required")
            return
        try:
            drive = int(self._drive_edit.text())
            idler = int(self._idler_edit.text())
            layshaft = int(self._layshaft_edit.text())
            ratio = float(self._ratio_edit.text())
        except ValueError:
            self._dialog_message.setText("all four numeric fields are required")
            return

        # Build a *full* ModelUpdate body -- copy every field from the
        # cached model, then override the four gear-scoped dicts. The
        # backend rejects partial bodies.
        base = self._current_model
        body = {
            "model_name": base["model_name"],
            "drive_teeth": dict(base.get("drive_teeth", {})),
            "idler_teeth_1": dict(base.get("idler_teeth_1", {})),
            "idler_teeth_2": dict(base.get("idler_teeth_2", {})),
            "layshaft_teeth": dict(base.get("layshaft_teeth", {})),
            "drive_shaft_bearing_roll": dict(base.get("drive_shaft_bearing_roll", {})),
            "layshaft_bearing_roll": dict(base.get("layshaft_bearing_roll", {})),
            "fdr_teeth": dict(base.get("fdr_teeth", {})),
            "fd_sel": dict(base.get("fd_sel", {})),
            "ratios": dict(base.get("ratios", {})),
        }
        body["drive_teeth"][label] = drive
        body["idler_teeth_1"][label] = idler
        body["layshaft_teeth"][label] = layshaft
        body["ratios"][label] = ratio

        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        def _on_success(updated_model) -> None:
            self.accept()
            self._on_saved(updated_model)

        def _on_error(message: str) -> None:
            self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            self._dialog_message.setText(f"save failed: {message}")
            self._status_label.setText(f"save gear failed: {message}")

        self._api.put_model(self._model_id, body, _on_success, _on_error)
