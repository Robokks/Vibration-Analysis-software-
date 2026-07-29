from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

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
    "Parameter", "Order", "Master mean", "Band min", "Band max", "Limit low", "Limit high", "In table",
]


class MasterEntryScreen(QWidget):
    def __init__(self, parent=None, api_client: ApiClient | None = None) -> None:
        super().__init__(parent)
        self._api = api_client if api_client is not None else ApiClient()
        self._error_shown = False

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
        for r, row in enumerate(rows):
            master = row.get("master")
            values = [
                row["stat_name"],
                "" if row.get("order_number") is None else f"{row['order_number']:.4g}",
                "" if not master else f"{master['mean_value']:.4g}",
                "" if not master else f"{master['band_min']:.4g}",
                "" if not master else f"{master['band_max']:.4g}",
                "" if row.get("limit_low") is None else f"{row['limit_low']:.4g}",
                "" if row.get("limit_high") is None else f"{row['limit_high']:.4g}",
                "yes" if row.get("included_in_table_config") else "no",
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))
        if not self._error_shown:
            self._status.setText(f"{len(rows)} parameters loaded")

    def _on_error(self, message: str) -> None:
        self._error_shown = True
        self._status.setText(f"failed to reach backend: {message}")
