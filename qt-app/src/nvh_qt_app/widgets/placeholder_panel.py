"""Clearly-labeled placeholder for the frequency-domain subtabs that
aren't computed live yet (order spectrum / order tracking / color map /
waterfall -- all are batch-computed in the analysis engine from a
completed DC record today, not from streaming chunks). Keeps the tab
present in the UI so operators see the whole intended surface, while
making it plain that the panel is deliberately empty rather than broken."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPanel(QWidget):
    def __init__(self, title: str, detail: str, muted_color: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            "QLabel { color: " + muted_color + "; "
            "font-family: 'IBM Plex Sans', sans-serif; font-size: 16px; "
            "letter-spacing: 0.12em; text-transform: uppercase; }"
        )
        detail_label = QLabel(detail)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet(
            "QLabel { color: " + muted_color + "; "
            "font-family: 'IBM Plex Mono', monospace; font-size: 12px; }"
        )

        layout.addStretch(1)
        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        layout.addStretch(1)
