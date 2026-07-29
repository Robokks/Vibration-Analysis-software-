from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nvh_design_tokens import load_tokens

from ..api_client import ApiClient
from ..widgets.gear_glyph import StampWidget
from ..widgets.labels import MonoLabel, SectionTitle
from ..widgets.panel import Panel

# Same demo-dataset scoping story as MasterEntryScreen -- one model/program/
# gear/direction exists today.
MODEL_ID = "MODEL-A"
PROGRAM_NAME = "REVA"
GEAR_LABEL = "R"
DIRECTION = "RU"
SUMMARY_STAT_NAME = "RMS Avg"

_DETAILED_COLUMNS = ["Stat", "Domain", "Observed", "Master mean", "G-level", "OK/NOK"]
_SUMMARY_COLUMNS = ["Serial number", "Value"]
_CODE_RESULT_COLUMNS = [
    "Step", "Gear/Direction", "Channel", "Parameter", "Orders", "Low", "Actual", "High", "Unit", "OK/NOK",
]


def _make_table(columns: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    for col in range(1, len(columns)):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
    return table


class ReportsScreen(QWidget):
    def __init__(self, parent=None, api_client: ApiClient | None = None) -> None:
        super().__init__(parent)
        self._api = api_client if api_client is not None else ApiClient()
        self._error_shown = False

        tokens = load_tokens()
        palette = tokens["color"]["palettes"]["dark"]
        self._pass_color = palette["pass"]
        self._alarm_color = palette["alarm"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._status = MonoLabel("loading test runs…")
        layout.addWidget(self._status)

        run_panel = Panel()
        run_layout = QVBoxLayout(run_panel)
        run_layout.addWidget(SectionTitle("Test run"))
        self._run_combo = QComboBox()
        self._run_combo.currentIndexChanged.connect(self._on_test_run_selected)
        run_layout.addWidget(self._run_combo)
        layout.addWidget(run_panel)

        self._tabs = QTabWidget()
        self._consolidated_stamp: StampWidget | None = None
        self._consolidated_panel, self._consolidated_stamps_row, self._consolidated_detail = self._build_consolidated_tab()
        self._detailed_table = _make_table(_DETAILED_COLUMNS)
        self._summary_table = _make_table(_SUMMARY_COLUMNS)
        self._code_result_table = _make_table(_CODE_RESULT_COLUMNS)

        self._tabs.addTab(self._consolidated_panel, "Consolidated")
        self._tabs.addTab(self._wrap(self._detailed_table), "Detailed")
        self._tabs.addTab(self._wrap(self._summary_table), "Summary")
        self._tabs.addTab(self._wrap(self._code_result_table), "Code-Result")
        layout.addWidget(self._tabs)

        self._api.fetch_test_runs(MODEL_ID, self._on_test_runs, self._on_error)

    @staticmethod
    def _wrap(table: QTableWidget) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(table)
        return panel

    def _build_consolidated_tab(self) -> tuple[Panel, QHBoxLayout, MonoLabel]:
        panel = Panel()
        layout = QVBoxLayout(panel)
        stamps_row = QHBoxLayout()
        layout.addLayout(stamps_row)
        detail_label = MonoLabel("")
        layout.addWidget(detail_label)
        layout.addStretch(1)
        return panel, stamps_row, detail_label

    def _on_test_runs(self, runs: list[dict]) -> None:
        self._run_combo.blockSignals(True)
        self._run_combo.clear()
        for run in runs:
            self._run_combo.addItem(f"{run['serial_number']} — {run['overall_result']}", userData=run["test_run_id"])
        self._run_combo.blockSignals(False)
        if not self._error_shown:
            self._status.setText(f"{len(runs)} test runs loaded")
        if runs:
            self._on_test_run_selected(0)

    def _on_test_run_selected(self, index: int) -> None:
        if index < 0:
            return
        test_run_id = self._run_combo.itemData(index)
        if test_run_id is None:
            return
        self._api.fetch_test_run(test_run_id, self._on_test_run_detail, self._on_error)

    def _on_test_run_detail(self, detail: dict) -> None:
        dc_records = detail.get("dc_records") or []
        if not dc_records:
            return
        dc_id = dc_records[0]["dc_id"]
        self._api.fetch_consolidated_report(dc_id, self._on_consolidated, self._on_error, program_name=PROGRAM_NAME)
        self._api.fetch_detailed_report(dc_id, self._on_detailed, self._on_error, program_name=PROGRAM_NAME)
        self._api.fetch_code_result_report(dc_id, self._on_code_result, self._on_error, program_name=PROGRAM_NAME)
        self._api.fetch_summary_report(
            MODEL_ID, GEAR_LABEL, DIRECTION, SUMMARY_STAT_NAME, self._on_summary, self._on_error,
            program_name=PROGRAM_NAME,
        )

    def _on_consolidated(self, payload: dict) -> None:
        stamp = payload["stamp"]
        color = self._pass_color if stamp == "PASS" else self._alarm_color
        if self._consolidated_stamp is not None:
            self._consolidated_stamp.setParent(None)
        new_stamp = StampWidget(result=stamp, color=color)
        new_stamp.setFixedSize(140, 90)
        self._consolidated_stamps_row.insertWidget(0, new_stamp)
        self._consolidated_stamp = new_stamp

        result = payload["result"]
        crash = result["crash_noise"]
        slip = result["slippage"]
        lines = [
            f"gear {result['gear_label']} / {result['direction']}",
            f"crash noise: {'DETECTED' if crash['detected'] else 'clear'} "
            f"(peak {crash['peak_band_rms']:.3g} / threshold {crash['threshold']:.3g})",
            f"slippage: {'DETECTED' if slip['detected'] else 'clear'} (min ratio {slip['min_ratio']:.3g})",
        ]
        if result["fail_reason_codes"]:
            lines.append(f"fail reasons: {', '.join(result['fail_reason_codes'])}")
        self._consolidated_detail.setText("\n".join(lines))

    def _on_detailed(self, payload: dict) -> None:
        rows = payload["numeric_table"]
        table = self._detailed_table
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            master = row.get("master")
            grading = row.get("grading")
            values = [
                row["stat_name"],
                row["domain"],
                f"{row['observed_value']:.4g}",
                "" if not master else f"{master['mean_value']:.4g}",
                "" if not grading else str(grading["g_level"]),
                "" if not grading else ("OK" if grading["ok_flag"] else "NOK"),
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))

    def _on_summary(self, payload: dict) -> None:
        rows = payload["rows"]
        values = payload["xchart"]["values"]
        table = self._summary_table
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(row["test_run"]["serial_number"]))
            value = values[r] if r < len(values) else None
            table.setItem(r, 1, QTableWidgetItem("" if value is None else f"{value:.4g}"))

    def _on_code_result(self, payload: dict) -> None:
        rows = payload["rows"]
        table = self._code_result_table
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                str(row["step"]),
                row["gear_direction"],
                row["channel_name"],
                row["parameter"],
                "" if row["orders"] is None else f"{row['orders']:.4g}",
                f"{row['low']:.4g}",
                f"{row['actual']:.4g}",
                f"{row['high']:.4g}",
                row["unit"],
                "OK" if row["ok_flag"] else "NOK",
            ]
            for c, text in enumerate(values):
                table.setItem(r, c, QTableWidgetItem(text))

    def _on_error(self, message: str) -> None:
        self._error_shown = True
        self._status.setText(f"failed to reach backend: {message}")
