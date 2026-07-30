"""Top toolbar for Live Display: nine icon+label buttons matching the
real system's operator navigation (Login / Calibration / System Config /
D Report / Summary Report / Master / Master Setup / Table Config /
Limit Config). Each button emits `action_triggered(name)` -- the screen
owning the toolbar decides what to route to (a sibling screen, a
placeholder status message, a modal setup dialog once one exists)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton

from ..icons import make_icon

# (action name, human label). Order matches the spec top-left to
# top-right; the human label wraps under the icon inside the button.
_TOOLBAR_ACTIONS: tuple[tuple[str, str], ...] = (
    ("login", "Login"),
    ("calibration", "Calibration"),
    ("system_config", "System"),
    ("d_report", "D Report"),
    ("summary_report", "Summary"),
    ("master", "Master"),
    ("master_setup", "Master Setup"),
    ("table_config", "Table Config"),
    ("limit_config", "Limit Config"),
)


class LiveToolbar(QFrame):
    """Icon+label toolbar row with an object name QSS can hook onto
    (``LiveToolbar``). Emits `action_triggered(str)` on any button click."""

    action_triggered = Signal(str)

    def __init__(self, icon_color: str, muted_color: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LiveToolbar")
        self._icon_color = icon_color
        self._muted_color = muted_color

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Keep a handle on each button by action name so tests + future
        # "highlight the active tool" wiring can find them without walking
        # the layout.
        self._buttons: dict[str, QToolButton] = {}
        for name, label in _TOOLBAR_ACTIONS:
            button = self._build_button(name, label)
            self._buttons[name] = button
            layout.addWidget(button)
        layout.addStretch(1)

    def _build_button(self, name: str, label: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(f"toolbar_{name}")
        button.setText(label)
        button.setIcon(make_icon(name, self._icon_color, size=28))
        button.setIconSize(QSize(28, 28))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setToolTip(label)
        # Fixed width keeps the toolbar visually aligned regardless of
        # per-label text length; height auto-sizes to icon + label.
        button.setFixedWidth(78)
        button.setStyleSheet(
            "QToolButton { "
            f"color: {self._muted_color}; "
            "padding: 6px 4px; border: none; "
            "font-family: 'IBM Plex Sans', sans-serif; font-size: 10px; }"
            "QToolButton:hover { "
            f"color: {self._icon_color}; "
            "background: rgba(79, 216, 224, 0.08); border-radius: 4px; }"
        )
        button.clicked.connect(lambda _checked=False, n=name: self.action_triggered.emit(n))
        return button

    def button(self, name: str) -> QToolButton:
        return self._buttons[name]
