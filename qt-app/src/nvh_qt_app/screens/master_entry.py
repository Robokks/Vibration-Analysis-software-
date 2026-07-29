from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..widgets.labels import Chip, MonoLabel, SectionTitle
from ..widgets.panel import Panel, TodoBanner

_DIRECTION_CYCLE = ["RU", "STYD", "STYC", "RD"]
_GEAR_LABELS = ["N", "R", "I", "II", "III", "IV", "V"]

_PARAMETER_FAMILIES = [
    ("Base", "14", "{Mean,Variance,Skewness,Kurtosis,RMS,PK,Crest} x {max,avg}"),
    ("Unit-family", "8", "{RMS,PK} x {max,avg} x {(m/s2),(dB m/s2)}"),
    ("Harmonic", "27", "{IN_H1-3,CM_H1-3,IN_S1.0,OUT_S1.0,OUTPUT_S1.0} x {(g),(m/s2),(dB m/s2)}"),
]


class MasterEntryScreen(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            TodoBanner(
                "wire to the model/master-signature API once Phase C (named "
                "NVH-PROGRAM profiles + LIMIT/THRESHOLD config) lands — this "
                "screen only lays out the shape today."
            )
        )

        layout.addWidget(self._build_model_gear_panel())
        layout.addWidget(self._build_direction_panel())
        layout.addWidget(self._build_parameter_panel())
        layout.addStretch(1)

    @staticmethod
    def _build_model_gear_panel() -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Model & gear"))
        chip_row = QHBoxLayout()
        for label in _GEAR_LABELS:
            chip_row.addWidget(Chip(label))
        chip_row.addStretch(1)
        panel_layout.addLayout(chip_row)
        return panel

    @staticmethod
    def _build_direction_panel() -> Panel:
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

    @staticmethod
    def _build_parameter_panel() -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(SectionTitle("Parameter catalog (49 graded parameters)"))

        table = QTableWidget(len(_PARAMETER_FAMILIES), 3)
        table.setHorizontalHeaderLabels(["Family", "Count", "Pattern"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for row, (family, count, pattern) in enumerate(_PARAMETER_FAMILIES):
            table.setItem(row, 0, QTableWidgetItem(family))
            table.setItem(row, 1, QTableWidgetItem(count))
            table.setItem(row, 2, QTableWidgetItem(pattern))

        panel_layout.addWidget(table)
        return panel
