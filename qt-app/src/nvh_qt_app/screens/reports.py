from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QTabWidget, QVBoxLayout, QWidget

from nvh_design_tokens import load_tokens

from ..widgets.gear_glyph import StampWidget
from ..widgets.labels import MonoLabel
from ..widgets.panel import Panel, TodoBanner

_REPORT_TABS = ["Consolidated", "Detailed", "Summary"]


def _build_tab_content(tab_name: str, pass_color: str, alarm_color: str) -> Panel:
    panel = Panel()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    stamps = QHBoxLayout()
    for result, color in (("PASS", pass_color), ("FAIL", alarm_color)):
        stamp = StampWidget(result=result, color=color)
        stamp.setFixedSize(140, 90)
        stamps.addWidget(stamp)
    stamps.addStretch(1)
    layout.addLayout(stamps)

    layout.addWidget(MonoLabel(f"{tab_name} report layout placeholder — no report data wired up yet."))
    layout.addStretch(1)
    return panel


class ReportsScreen(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        tokens = load_tokens()
        palette = tokens["color"]["palettes"]["dark"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            TodoBanner(
                "wire to analysis_engine.reports / nvh_api_schemas.report "
                "once Phase D (flat CODE-RESULT grading table) and Phase E "
                "(report/column configuration) land."
            )
        )

        tabs = QTabWidget()
        for tab_name in _REPORT_TABS:
            tabs.addTab(_build_tab_content(tab_name, palette["pass"], palette["alarm"]), tab_name)
        layout.addWidget(tabs)
