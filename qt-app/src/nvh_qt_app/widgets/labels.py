"""Thin QLabel subclasses that exist purely so theme.py's QSS can target them
by type selector (e.g. ``SectionTitle { ... }``) instead of juggling
``#objectName`` or dynamic-property selectors."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class AppTitle(QLabel):
    pass


class AppSubtitle(QLabel):
    pass


class SectionTitle(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text.upper(), parent)


class MonoLabel(QLabel):
    pass


class ValueLabel(QLabel):
    pass


class PassLabel(QLabel):
    pass


class AlarmLabel(QLabel):
    pass


class Chip(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
