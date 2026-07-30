"""Legend panel for a MultiSeriesPlot: one row per series showing a
colored chip + name + visibility checkbox. Checking/unchecking hides
the series (same effect as the plot's own Plot Visible submenu -- the
legend is just a more discoverable path to the same toggle)."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)


class _ColorChip(QFrame):
    def __init__(self, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(14, 14)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setPen(QPen(self._color, 2))
        painter.drawLine(1, self.height() // 2, self.width() - 1, self.height() // 2)
        painter.end()


class PlotLegend(QFrame):
    """Vertical stack of `chip | name | checkbox` rows. The plot passes
    its series dict in and hands the legend a set-visible callback so
    a checkbox flip flows straight through to the plot."""

    def __init__(
        self,
        series_names: list[str],
        color_lookup: dict[str, QColor],
        set_visible: Callable[[str, bool], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PlotLegend")
        self._set_visible = set_visible
        self._checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        for name in series_names:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(_ColorChip(color_lookup[name], self))
            label = QLabel(name)
            label.setStyleSheet(
                "QLabel { font-family: 'IBM Plex Mono', monospace; font-size: 11px; }"
            )
            row.addWidget(label, stretch=1)
            check = QCheckBox()
            check.setChecked(True)
            check.stateChanged.connect(self._make_toggle(name))
            row.addWidget(check)
            self._checks[name] = check
            layout.addLayout(row)
        layout.addStretch(1)

    def _make_toggle(self, name: str) -> Callable[[int], None]:
        def _toggled(state: int) -> None:
            self._set_visible(name, state == Qt.CheckState.Checked.value)
        return _toggled
