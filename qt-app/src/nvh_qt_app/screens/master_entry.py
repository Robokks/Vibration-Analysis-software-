from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
)

from nvh_design_tokens import load_tokens

from ..api_client import ApiClient
from ..widgets.labels import Chip, MonoLabel, SectionTitle
from ..widgets.panel import Panel

# The seeded demo dataset (web-backend/scripts/seed_demo_data.py) has
# exactly one model/program/gear/direction -- hardcoded here rather than
# building selectors, since there's nothing else to select between yet.
# Revisit once a second model/program/gear exists. Same constants as the
# sibling web-frontend screen.
MODEL_ID = "MODEL-A"
PROGRAM_NAME = "REVA"
GEAR_LABEL = "R"
DIRECTION = "RU"
CHANNEL_NAME = "vib_a"

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
        self._load_palette()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._status = MonoLabel(f"loading model {MODEL_ID}…")
        layout.addWidget(self._status)

        layout.addWidget(self._build_model_gear_panel())
        layout.addWidget(self._build_direction_panel())
        layout.addWidget(self._build_parameter_panel())
        layout.addStretch(1)

        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)

        self._api.fetch_model(MODEL_ID, self._on_model, self._on_error)
        self._api.fetch_parameters(
            MODEL_ID, PROGRAM_NAME, GEAR_LABEL, DIRECTION, self._on_parameters, self._on_error,
            channel_name=CHANNEL_NAME,
        )

    def _build_model_gear_panel(self) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Model & gear teeth"))

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Gear", "Drive teeth", "Idler 1", "Layshaft", "Ratio"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
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

    def _on_model(self, model: dict) -> None:
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
        if not self._error_shown:
            self._status.setText(f"model {MODEL_ID} loaded")

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

    def _on_numeric_committed(self, stat_name: str, field: str, new_value: float) -> None:
        """Fires when the operator finishes typing in a LIMIT or THRESHOLD
        cell -- dispatches to the matching PATCH endpoint. Same shape as
        the sibling web-frontend's NumericCell commit path."""
        row = self._rows_by_stat.get(stat_name)
        if row is None:
            return
        self._status.setText(f"saving {stat_name} {field}={new_value}…")

        def _on_success(updated: dict) -> None:
            self._rows_by_stat[stat_name] = updated
            # Repaint every editable cell in the row -- the server may have
            # normalized a value we sent, and a PATCH to (e.g.) limit_low
            # can leave threshold_* alone but the response is always the
            # full row.
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
                MODEL_ID, PROGRAM_NAME, stat_name, GEAR_LABEL, DIRECTION,
                new_value if field == "limit_low" else row.get("limit_low") or 0.0,
                new_value if field == "limit_high" else row.get("limit_high") or 0.0,
                _on_success, _on_failure, channel_name=CHANNEL_NAME,
            )
        else:
            self._api.patch_threshold(
                MODEL_ID, PROGRAM_NAME, stat_name, GEAR_LABEL, DIRECTION,
                new_value if field == "threshold_low" else row.get("threshold_low") or 0.0,
                new_value if field == "threshold_high" else row.get("threshold_high") or 0.0,
                _on_success, _on_failure, channel_name=CHANNEL_NAME,
            )

    def _on_in_table_toggled(self, stat_name: str, included: bool) -> None:
        """Fires when the operator clicks the 'In table' toggle -- posts to
        the Table Config parameter inclusion endpoint. The server response
        is the refreshed ParameterCatalogRowOut, which we mirror back into
        the local cache and the button's visual state."""
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
            MODEL_ID, PROGRAM_NAME, stat_name, GEAR_LABEL, DIRECTION,
            included, _on_success, _on_failure, channel_name=CHANNEL_NAME,
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
