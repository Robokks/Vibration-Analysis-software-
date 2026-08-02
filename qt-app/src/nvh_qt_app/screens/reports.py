from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QListWidget,
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
from ..widgets.multi_series_plot import MultiSeriesPlot
from ..widgets.panel import Panel

_DETAILED_COLUMNS = ["Stat", "Domain", "Observed", "Master mean", "G-level", "OK/NOK"]
_CODE_RESULT_COLUMNS = [
    "Step", "Gear/Direction", "Channel", "Parameter", "Orders",
    "Low", "Actual", "High", "Unit", "OK/NOK",
]
_STAT_FIELD = {"RMS Avg": "rms_avg", "Peak": "peak", "Order 1x Mag": "order_1x_mag"}


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

        # Instance state
        self._model_id: str | None = None
        self._program_name: str | None = None
        self._direction: str = "RU"
        self._all_runs: list[dict] = []
        self._all_summaries: list[dict] = []
        self._current_dc_records: list[dict] = []
        self._code_result_rows: list[dict] = []

        # Outer layout: left filter panel + right content
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_filter_panel())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        self._status = MonoLabel("loading…")
        right_layout.addWidget(self._status)

        right_layout.addWidget(self._build_details_strip())

        self._detailed_table = _make_table(_DETAILED_COLUMNS)
        self._nvh_details_table = _make_table(_CODE_RESULT_COLUMNS)
        (
            self._graphs_panel,
            self._order_spectrum_plot,
            self._order_tracking_plot,
            self._graphs_detail,
        ) = self._build_graphs_tab()
        self._summary_panel = self._build_summary_tab()

        self._tabs = QTabWidget()
        self._tabs.addTab(self._graphs_panel, "Graphs")
        self._tabs.addTab(self._wrap(self._detailed_table), "Detailed")
        self._tabs.addTab(self._wrap(self._nvh_details_table), "NVH Details")
        self._tabs.addTab(self._summary_panel, "Summary")
        right_layout.addWidget(self._tabs)

        outer.addWidget(right, stretch=1)

        self._api.fetch_models(self._on_models_loaded, self._on_error)

    # ------------------------------------------------------------------
    # Panel builders
    # ------------------------------------------------------------------

    def _build_filter_panel(self) -> QWidget:
        panel = Panel()
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(6)

        # --- Test run cascade ---
        layout.addWidget(SectionTitle("Test run"))

        layout.addWidget(MonoLabel("Model:"))
        self._model_combo = QComboBox()
        layout.addWidget(self._model_combo)

        layout.addWidget(MonoLabel("Date:"))
        self._date_combo = QComboBox()
        layout.addWidget(self._date_combo)

        layout.addWidget(MonoLabel("Serial No:"))
        self._serial_combo = QComboBox()
        layout.addWidget(self._serial_combo)

        layout.addWidget(MonoLabel("Rpt No:"))
        self._rpt_combo = QComboBox()
        layout.addWidget(self._rpt_combo)

        # --- Condition selector ---
        layout.addWidget(SectionTitle("Condition"))

        layout.addWidget(MonoLabel("Gear:"))
        self._gear_combo = QComboBox()
        layout.addWidget(self._gear_combo)

        layout.addWidget(MonoLabel("NVH ID:"))
        self._nvh_id_combo = QComboBox()
        layout.addWidget(self._nvh_id_combo)

        # --- Report context ---
        layout.addWidget(SectionTitle("Report context"))

        layout.addWidget(MonoLabel("Program:"))
        self._program_combo = QComboBox()
        layout.addWidget(self._program_combo)

        layout.addWidget(MonoLabel("Direction:"))
        self._direction_combo = QComboBox()
        for d in ("RU", "STYD", "STYC", "RD"):
            self._direction_combo.addItem(d)
        layout.addWidget(self._direction_combo)

        layout.addStretch(1)

        # Wire signals
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        self._date_combo.currentIndexChanged.connect(self._on_date_changed)
        self._serial_combo.currentIndexChanged.connect(self._on_serial_changed)
        self._rpt_combo.currentIndexChanged.connect(self._on_rpt_changed)
        self._gear_combo.currentIndexChanged.connect(self._on_gear_changed)
        self._nvh_id_combo.currentIndexChanged.connect(self._on_nvh_id_changed)
        self._program_combo.currentIndexChanged.connect(self._on_program_changed)
        self._direction_combo.currentTextChanged.connect(self._on_direction_changed)

        return panel

    def _build_details_strip(self) -> QWidget:
        strip = QWidget()
        row = QHBoxLayout(strip)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        self._det_model = MonoLabel("Model: —")
        self._det_serial = MonoLabel("Serial: —")
        self._det_rpt = MonoLabel("Rpt: —")
        self._det_date = MonoLabel("Date: —")
        self._det_start = MonoLabel("Start: —")
        self._det_end = MonoLabel("End: —")

        for lbl in (self._det_model, self._det_serial, self._det_rpt,
                    self._det_date, self._det_start, self._det_end):
            row.addWidget(lbl)

        row.addStretch(1)

        self._det_stamp: StampWidget | None = None
        self._det_stamp_placeholder = QWidget()
        self._det_stamp_placeholder.setFixedSize(100, 64)
        row.addWidget(self._det_stamp_placeholder)

        return strip

    def _build_graphs_tab(self):
        panel = Panel()
        layout = QVBoxLayout(panel)

        detail_label = MonoLabel("")
        layout.addWidget(detail_label)

        plots_row = QHBoxLayout()
        plots_row.setSpacing(12)

        spec_plot = MultiSeriesPlot(["Order magnitude"], max_samples=4096)
        spec_plot.setMinimumHeight(220)
        spec_panel = Panel()
        spec_layout = QVBoxLayout(spec_panel)
        spec_layout.addWidget(SectionTitle("Order spectrum"))
        spec_layout.addWidget(spec_plot)
        plots_row.addWidget(spec_panel, stretch=1)

        track_plot = MultiSeriesPlot(["Order tracking"], max_samples=4096)
        track_plot.setMinimumHeight(220)
        track_panel = Panel()
        track_layout = QVBoxLayout(track_panel)
        track_layout.addWidget(SectionTitle("Order tracking"))
        track_layout.addWidget(track_plot)
        plots_row.addWidget(track_panel, stretch=1)

        layout.addLayout(plots_row)
        layout.addStretch(1)
        return panel, spec_plot, track_plot, detail_label

    def _build_summary_tab(self) -> QWidget:
        panel = Panel()
        layout = QVBoxLayout(panel)

        stat_row = QHBoxLayout()
        stat_row.addWidget(MonoLabel("Stat:"))
        self._stat_name_combo = QComboBox()
        for name in ("RMS Avg", "Peak", "Order 1x Mag"):
            self._stat_name_combo.addItem(name)
        self._stat_name_combo.currentTextChanged.connect(self._on_stat_changed)
        stat_row.addWidget(self._stat_name_combo)
        stat_row.addStretch(1)
        layout.addLayout(stat_row)

        layout.addWidget(SectionTitle("Serial numbers"))

        self._serial_list = QListWidget()
        self._serial_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._serial_list.setFixedHeight(120)
        self._serial_list.itemSelectionChanged.connect(self._on_serial_selection_changed)
        layout.addWidget(self._serial_list)

        self._xchart_plot = MultiSeriesPlot([], max_samples=1024)
        self._xchart_plot.setMinimumHeight(300)
        layout.addWidget(self._xchart_plot)

        self._summary_meta = MonoLabel("(no data)")
        layout.addWidget(self._summary_meta)
        layout.addStretch(1)
        return panel

    @staticmethod
    def _wrap(table: QTableWidget) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(table)
        return panel

    # ------------------------------------------------------------------
    # Cascade: Model → Date → Serial → Rpt No
    # ------------------------------------------------------------------

    def _on_models_loaded(self, models: list[dict]) -> None:
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for m in models:
            mid = m.get("model_id", "")
            self._model_combo.addItem(mid, userData=mid)
        self._model_combo.blockSignals(False)
        if models:
            self._on_model_changed(0)

    def _on_model_changed(self, _index: int) -> None:
        model_id = self._model_combo.currentData()
        if not model_id:
            return
        self._model_id = model_id
        self._det_model.setText(f"Model: {model_id}")
        self._api.fetch_programs(model_id, self._on_programs_loaded, self._on_error)
        self._api.fetch_test_runs(model_id, self._on_runs_loaded, self._on_error)
        self._api.fetch_summaries(model_id, self._on_summaries_loaded, self._on_error)

    def _on_programs_loaded(self, programs: list[dict]) -> None:
        self._program_combo.blockSignals(True)
        self._program_combo.clear()
        for p in programs:
            name = p.get("program_name", "")
            self._program_combo.addItem(name)
        self._program_combo.blockSignals(False)
        if programs:
            self._program_name = self._program_combo.currentText()

    def _on_program_changed(self, _index: int) -> None:
        self._program_name = self._program_combo.currentText()

    def _on_direction_changed(self, direction: str) -> None:
        self._direction = direction

    def _on_runs_loaded(self, runs: list[dict]) -> None:
        self._all_runs = sorted(runs, key=lambda r: r.get("started_at", ""), reverse=True)
        if not self._error_shown:
            self._status.setText(f"{len(runs)} test run(s) loaded")
        self._repopulate_dates()

    def _repopulate_dates(self) -> None:
        dates = ["All"] + sorted(
            {r["started_at"][:10] for r in self._all_runs if r.get("started_at")},
            reverse=True,
        )
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
        return [r for r in self._all_runs if r.get("started_at", "").startswith(date)]

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
            ts = r.get("started_at", "")[:19]
            label = f"Rpt {r['repeat_number']}  ({ts})"
            self._rpt_combo.addItem(label, userData=r["test_run_id"])
        self._rpt_combo.blockSignals(False)
        if runs:
            self._on_rpt_changed(0)

    def _on_rpt_changed(self, index: int) -> None:
        test_run_id = self._rpt_combo.itemData(index)
        if not test_run_id:
            return
        self._api.fetch_test_run(test_run_id, self._on_test_run_detail, self._on_error)

    # ------------------------------------------------------------------
    # Cascade: test run detail → Gear → NVH ID
    # ------------------------------------------------------------------

    def _on_test_run_detail(self, detail: dict) -> None:
        self._current_dc_records = detail.get("dc_records") or []

        serial = detail.get("serial_number", "—")
        rpt = detail.get("repeat_number", "—")
        started = detail.get("started_at") or ""
        finished = detail.get("finished_at") or ""
        overall = detail.get("overall_result", "")

        self._det_serial.setText(f"Serial: {serial}")
        self._det_rpt.setText(f"Rpt: {rpt}")
        self._det_date.setText(f"Date: {started[:10]}")
        self._det_start.setText(f"Start: {started[11:19]}")
        self._det_end.setText(f"End: {finished[11:19]}")

        self._update_det_stamp(overall)
        self._repopulate_gear_combo()

    def _update_det_stamp(self, result: str) -> None:
        if self._det_stamp is not None:
            self._det_stamp.setParent(None)
        if not result or result.upper() == "PENDING":
            self._det_stamp = None
            return
        color = self._pass_color if result.upper() == "PASS" else self._alarm_color
        stamp = StampWidget(result=result.upper(), color=color)
        stamp.setFixedSize(100, 64)
        # Insert before stretch — the placeholder keeps the row height stable
        det_layout = self._det_stamp_placeholder.parent().layout()
        if det_layout:
            det_layout.replaceWidget(self._det_stamp_placeholder, stamp)
            self._det_stamp_placeholder.hide()
        self._det_stamp = stamp

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
        recs = (
            self._current_dc_records
            if not gear or gear == "All"
            else [r for r in self._current_dc_records if r["gear_label"] == gear]
        )
        self._nvh_id_combo.blockSignals(True)
        self._nvh_id_combo.clear()
        for r in recs:
            label = f"{r['gear_label']}-{r['direction']}"
            self._nvh_id_combo.addItem(label, userData=r["dc_id"])
        self._nvh_id_combo.blockSignals(False)
        if recs:
            self._on_nvh_id_changed(0)
        self._filter_nvh_details_table()

    def _on_nvh_id_changed(self, index: int) -> None:
        dc_id = self._nvh_id_combo.itemData(index)
        if not dc_id:
            return
        pn = self._program_name or ""
        self._api.fetch_consolidated_report(dc_id, self._on_consolidated, self._on_error, program_name=pn)
        self._api.fetch_detailed_report(dc_id, self._on_detailed, self._on_error, program_name=pn)
        self._api.fetch_code_result_report(dc_id, self._on_code_result, self._on_error, program_name=pn)

    # ------------------------------------------------------------------
    # Report data handlers
    # ------------------------------------------------------------------

    def _on_consolidated(self, payload: dict) -> None:
        result = payload.get("result") or {}
        crash = result.get("crash_noise") or {}
        slip = result.get("slippage") or {}
        lines = [
            f"gear {result.get('gear_label', '?')} / {result.get('direction', '?')}",
            f"crash noise: {'DETECTED' if crash.get('detected') else 'clear'} "
            f"(peak {crash.get('peak_band_rms', 0):.3g} / threshold {crash.get('threshold', 0):.3g})",
            f"slippage: {'DETECTED' if slip.get('detected') else 'clear'} "
            f"(min ratio {slip.get('min_ratio', 0):.3g})",
        ]
        if result.get("fail_reason_codes"):
            lines.append(f"fail reasons: {', '.join(result['fail_reason_codes'])}")
        self._graphs_detail.setText("\n".join(lines))

        order_spectrum = result.get("order_spectrum") or {}
        magnitude = order_spectrum.get("magnitude") or []
        self._order_spectrum_plot.set_series_data("Order magnitude", magnitude)

        order_tracking = result.get("order_tracking") or {}
        tracking_magnitude = order_tracking.get("magnitude") or []
        self._order_tracking_plot.set_series_data("Order tracking", tracking_magnitude)

    def _on_detailed(self, payload: dict) -> None:
        rows = payload.get("numeric_table") or []
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

    def _on_code_result(self, payload: dict) -> None:
        self._code_result_rows = payload.get("rows") or []
        self._filter_nvh_details_table()

    def _filter_nvh_details_table(self) -> None:
        gear = self._gear_combo.currentText()
        rows = (
            self._code_result_rows
            if not gear or gear == "All"
            else [r for r in self._code_result_rows if r["gear_direction"].startswith(gear + "-")]
        )
        table = self._nvh_details_table
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

    # ------------------------------------------------------------------
    # Summary tab: multi-serial X-chart
    # ------------------------------------------------------------------

    def _on_summaries_loaded(self, rows: list[dict]) -> None:
        self._all_summaries = rows
        serials = sorted({r["serial_no"] for r in rows})
        self._serial_list.blockSignals(True)
        self._serial_list.clear()
        for s in serials:
            self._serial_list.addItem(s)
        self._serial_list.selectAll()
        self._serial_list.blockSignals(False)
        self._on_serial_selection_changed()

    def _on_serial_selection_changed(self) -> None:
        selected = [item.text() for item in self._serial_list.selectedItems()]
        field = _STAT_FIELD.get(self._stat_name_combo.currentText(), "rms_avg")
        for serial in list(self._xchart_plot.series_names()):
            if serial not in selected:
                self._xchart_plot.remove_series(serial)
        for serial in selected:
            self._xchart_plot.add_series(serial)
            vals = [
                r[field] for r in self._all_summaries
                if r["serial_no"] == serial and r.get(field) is not None
            ]
            self._xchart_plot.set_series_data(serial, vals)
        self._summary_meta.setText(
            f"{len(selected)} serial(s) selected / {len(self._all_summaries)} rows total"
        )

    def _on_stat_changed(self, _name: str) -> None:
        self._on_serial_selection_changed()

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    def _on_error(self, message: str) -> None:
        self._error_shown = True
        self._status.setText(f"error: {message}")
