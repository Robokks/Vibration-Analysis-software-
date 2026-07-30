from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

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
_COL_THRESHOLD_LOW = 7
_COL_THRESHOLD_HIGH = 8


class MasterEntryScreen(QWidget):
    def __init__(self, parent=None, api_client: ApiClient | None = None) -> None:
        super().__init__(parent)
        self._api = api_client if api_client is not None else ApiClient()
        self._error_shown = False
        # stat_name -> latest ParameterCatalogRowOut dict, so a PATCH round
        # trip can restore the pre-edit cell value on failure and keep the
        # "other" threshold's number when only one column changes.
        self._rows_by_stat: dict[str, dict] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._status = MonoLabel(f"loading model {MODEL_ID}…")
        layout.addWidget(self._status)

        layout.addWidget(self._build_model_gear_panel())
        layout.addWidget(self._build_direction_panel())
        layout.addWidget(self._build_parameter_panel())
        layout.addStretch(1)

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
        # No cell-level edit triggers -- the threshold columns get real
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
                "" if row.get("limit_low") is None else f"{row['limit_low']:.4g}",
                "" if row.get("limit_high") is None else f"{row['limit_high']:.4g}",
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))
            # Threshold columns get editable widgets when the row actually
            # carries thresholds (LimitConfigRow exists); otherwise a plain
            # em-dash placeholder like the display-only columns above.
            for col, key in ((_COL_THRESHOLD_LOW, "threshold_low"),
                              (_COL_THRESHOLD_HIGH, "threshold_high")):
                stored = row.get(key)
                if stored is None:
                    table.setItem(r, col, QTableWidgetItem("—"))
                else:
                    editor = _ThresholdEditor(row["stat_name"], key, stored, self)
                    editor.threshold_committed.connect(self._on_threshold_committed)
                    table.setCellWidget(r, col, editor)
            # "In table" column shifts to the tail after the two new columns.
            table.setItem(
                r, len(_PARAMETER_COLUMNS) - 1,
                QTableWidgetItem("yes" if row.get("included_in_table_config") else "no"),
            )
        if not self._error_shown:
            self._status.setText(f"{len(rows)} parameters loaded")

    def _on_threshold_committed(self, stat_name: str, field: str, new_value: float) -> None:
        """Fires when the operator finishes typing in a threshold cell --
        matches the real Limit Config.vi "Save" button. Sends the PATCH,
        updates the local cache on success, restores the editor on failure."""
        row = self._rows_by_stat.get(stat_name)
        if row is None:
            return
        threshold_low = new_value if field == "threshold_low" else row.get("threshold_low") or 0.0
        threshold_high = new_value if field == "threshold_high" else row.get("threshold_high") or 0.0
        self._status.setText(f"saving {stat_name} {field}={new_value}…")

        def _on_success(updated: dict) -> None:
            self._rows_by_stat[stat_name] = updated
            # Repaint just the two threshold editors from the server's
            # response, in case the backend rounded/normalized either value.
            table = self._param_table
            for r in range(table.rowCount()):
                item = table.item(r, _COL_STAT_NAME)
                if item is None or item.text() != stat_name:
                    continue
                for col, key in ((_COL_THRESHOLD_LOW, "threshold_low"),
                                  (_COL_THRESHOLD_HIGH, "threshold_high")):
                    widget = table.cellWidget(r, col)
                    if isinstance(widget, _ThresholdEditor):
                        widget.set_value(updated.get(key))
                break
            self._status.setText(f"{stat_name} thresholds saved")

        def _on_failure(message: str) -> None:
            self._restore_editor(stat_name, field, row.get(field))
            self._status.setText(f"save failed for {stat_name} ({message})")

        self._api.patch_threshold(
            MODEL_ID, PROGRAM_NAME, stat_name, GEAR_LABEL, DIRECTION,
            threshold_low, threshold_high, _on_success, _on_failure,
            channel_name=CHANNEL_NAME,
        )

    def _restore_editor(self, stat_name: str, field: str, stored) -> None:
        table = self._param_table
        col = _COL_THRESHOLD_LOW if field == "threshold_low" else _COL_THRESHOLD_HIGH
        for r in range(table.rowCount()):
            item = table.item(r, _COL_STAT_NAME)
            if item is None or item.text() != stat_name:
                continue
            widget = table.cellWidget(r, col)
            if isinstance(widget, _ThresholdEditor):
                widget.set_value(stored)
            return

    def _on_error(self, message: str) -> None:
        self._error_shown = True
        self._status.setText(f"failed to reach backend: {message}")


class _ThresholdEditor(QLineEdit):
    """Inline QLineEdit for a single threshold cell -- commits on
    editingFinished (Enter or focus-out), validates as a plain double,
    keeps its own "last committed value" so an Escape or a failed PATCH can
    revert without a re-fetch."""

    threshold_committed = Signal(str, str, float)

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
        # Optimistically show the new value; the screen will call set_value()
        # again from the PATCH response (or revert on failure).
        self._committed = parsed
        self.threshold_committed.emit(self._stat_name, self._field, parsed)
