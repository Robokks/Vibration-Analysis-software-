"""Thin QFrame subclasses for theme.py's QSS type selectors — see labels.py."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout

from .labels import MonoLabel


class Panel(QFrame):
    pass


class HeaderBar(QFrame):
    pass


class TodoBanner(QFrame):
    """Flags a screen as scaffold-only, matching the web frontend's TodoBanner."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        label = MonoLabel(f"TODO: {text}")
        label.setWordWrap(True)
        layout.addWidget(label)
