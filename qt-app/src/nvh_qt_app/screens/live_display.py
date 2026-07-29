from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from nvh_design_tokens import load_tokens

from ..widgets.gear_glyph import GearGlyphWidget
from ..widgets.graticule import GraticuleWidget
from ..widgets.labels import MonoLabel, SectionTitle, ValueLabel
from ..widgets.panel import Panel, TodoBanner

_PLACEHOLDER_DC = {
    "Test run": "—",
    "Gear": "—",
    "Direction": "—",
    "Stamp": "PENDING",
}


class LiveDisplayScreen(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        tokens = load_tokens()
        accent_secondary = tokens["color"]["palettes"]["dark"]["accentSecondary"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            TodoBanner(
                "wire to the realtime API once it exists "
                "(nvh_api_schemas.realtime.LiveDcUpdate over WebSocket) — "
                "Phase C-E land the master-profile/limit config this screen will grade against."
            )
        )

        status_row = QHBoxLayout()
        indicator = GearGlyphWidget(color=accent_secondary, spinning=True)
        indicator.setFixedSize(40, 30)
        status_row.addWidget(indicator)
        status_row.addWidget(MonoLabel("station STN-01 — awaiting test run"))
        status_row.addStretch(1)
        layout.addLayout(status_row)

        graticule = GraticuleWidget()
        graticule.setMinimumHeight(280)
        layout.addWidget(graticule, stretch=1)

        cards = QGridLayout()
        cards.setSpacing(12)
        for col, (label, value) in enumerate(_PLACEHOLDER_DC.items()):
            cards.addWidget(self._build_card(label, value), 0, col)
        layout.addLayout(cards)

    @staticmethod
    def _build_card(label: str, value: str) -> Panel:
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        title = SectionTitle(label)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        panel_layout.addWidget(title)
        panel_layout.addWidget(ValueLabel(value))
        return panel
