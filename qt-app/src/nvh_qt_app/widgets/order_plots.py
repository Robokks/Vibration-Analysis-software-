"""Order-domain plot widgets matching the LabVIEW Vibr-O-Matic
Analyzer's ORDER SPECTRUM and ORDER TRACKING sub-tabs (see
docs/vom_manual.txt sections 13.1.3.2 - 13.1.3.3).

Both consume outputs from analysis_engine.signal.order_spectrum /
order_tracking; the widgets just present them.

OrderSpectrumPlot -- two stacked traces:
  top: SPEED (rpm) vs TIME (secs)
  bottom: magnitude vs ORDER, with a floating PEAKS list

OrderTrackingPlot -- one plot with N named traces (OVERALL + per-order
harmonic magnitudes vs time), plus a small "expected orders" info
panel. Reuses MultiSeriesPlot under the hood."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from nvh_design_tokens import load_tokens

from .multi_series_plot import MultiSeriesPlot


class OrderSpectrumPlot(QWidget):
    """Two stacked plots matching the LabVIEW ORDER SPECTRUM sub-tab.
    Top: SPEED vs TIME. Bottom: magnitude vs ORDER + peaks list on the
    right showing the top-N magnitude spikes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        palette = load_tokens()["color"]["palettes"]["dark"]
        self._muted = palette["secondaryText"]
        self._accent = palette["accentSecondary"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._speed_plot = MultiSeriesPlot(["SPEED"], max_samples=4000)
        self._speed_plot.setMinimumHeight(100)
        layout.addWidget(self._speed_plot, stretch=1)

        # Bottom: magnitude-vs-order plot + peaks list side by side.
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)

        self._spectrum_plot = MultiSeriesPlot(["Magnitude"], max_samples=4000)
        self._spectrum_plot.setMinimumHeight(140)
        bottom_layout.addWidget(self._spectrum_plot, stretch=3)

        self._peaks_table = QTableWidget(0, 2)
        self._peaks_table.setHorizontalHeaderLabels(["Order", "Mag"])
        self._peaks_table.verticalHeader().setVisible(False)
        self._peaks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._peaks_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._peaks_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self._peaks_table.setMaximumWidth(180)
        bottom_layout.addWidget(self._peaks_table)

        layout.addWidget(bottom, stretch=2)

    def set_speed_over_time(self, rpm: Sequence[float]) -> None:
        self._speed_plot.set_series_data("SPEED", list(rpm))

    def set_spectrum(self, magnitude: Sequence[float]) -> None:
        self._spectrum_plot.set_series_data("Magnitude", list(magnitude))

    def set_peaks(self, peaks: list[tuple[float, float]]) -> None:
        """peaks is a list of (order, magnitude) pairs -- typically the
        top-N by magnitude. Rendered as a compact 2-column table."""
        self._peaks_table.setRowCount(len(peaks))
        for r, (order, mag) in enumerate(peaks):
            self._peaks_table.setItem(r, 0, QTableWidgetItem(f"{order:.2f}"))
            self._peaks_table.setItem(r, 1, QTableWidgetItem(f"{mag:.3g}"))

    def clear(self) -> None:
        self._speed_plot.clear()
        self._spectrum_plot.clear()
        self._peaks_table.setRowCount(0)


class OrderTrackingPlot(QWidget):
    """One MultiSeriesPlot showing N traces of magnitude-vs-time --
    OVERALL + per-order harmonics -- matching the LabVIEW ORDER
    TRACKING sub-tab. `series_names` is fixed at construction; the
    caller pushes data via ``set_series_data(name, values)`` -- same
    API as MultiSeriesPlot underneath."""

    def __init__(self, series_names: Sequence[str], parent=None) -> None:
        super().__init__(parent)
        palette = load_tokens()["color"]["palettes"]["dark"]
        self._muted = palette["secondaryText"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self._plot = MultiSeriesPlot(list(series_names), max_samples=4000)
        self._plot.setMinimumHeight(240)
        layout.addWidget(self._plot, stretch=3)

        # Expected-orders info panel on the right, matching the LabVIEW
        # screen's "EXPECTED ORDER" table.
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)
        header = QLabel("EXPECTED ORDER")
        header.setStyleSheet(
            "QLabel { color: " + self._muted + "; "
            "font-family: 'IBM Plex Sans', sans-serif; font-size: 10px; "
            "letter-spacing: 0.12em; }"
        )
        info_layout.addWidget(header)
        self._expected_table = QTableWidget(0, 2)
        self._expected_table.setHorizontalHeaderLabels(["Name", "Order"])
        self._expected_table.verticalHeader().setVisible(False)
        self._expected_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._expected_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._expected_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self._expected_table.setMaximumWidth(180)
        info_layout.addWidget(self._expected_table)
        info_layout.addStretch(1)
        layout.addWidget(info)

    def set_series_data(self, name: str, values: Sequence[float]) -> None:
        self._plot.set_series_data(name, list(values))

    def set_expected_orders(self, entries: list[tuple[str, float]]) -> None:
        self._expected_table.setRowCount(len(entries))
        for r, (name, order) in enumerate(entries):
            self._expected_table.setItem(r, 0, QTableWidgetItem(name))
            self._expected_table.setItem(r, 1, QTableWidgetItem(f"{order:.2f}"))

    def clear(self) -> None:
        self._plot.clear()
