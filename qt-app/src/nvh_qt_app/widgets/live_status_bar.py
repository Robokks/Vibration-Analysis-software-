"""Bottom status bar for Live Display -- fixed set of nine operator-visible
fields: operator, shift, serial no, serial repeat, model, NVH start/stop,
gear id, nvh id (direction PLC id), test result.

Fields are labeled inline (``label:value``) and monospace so they line up
regardless of value width. The bar owns one QLabel per field; the screen
above updates them in place via ``set_field(name, value)`` -- no signals,
no per-field getters, just a flat setter API."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel

# Field names in visible order (left-to-right, top-to-bottom in the grid).
# The keys are also the setter-side identifiers ``set_field`` accepts, so
# tests can assert against a stable vocabulary.
_FIELDS: tuple[tuple[str, str], ...] = (
    ("operator", "Op"),
    ("shift", "Shift"),
    ("serial", "SN"),
    ("repeat", "Rep"),
    ("model", "Model"),
    ("status", "Status"),
    ("gear_id", "Gear"),
    ("nvh_id", "NVH"),
    ("result", "Result"),
)

_PLACEHOLDER = "—"


class LiveStatusBar(QFrame):
    """9-field bottom bar. All fields start at "—"; the owning screen
    fills them in as ``test_run``/``dc`` events arrive."""

    def __init__(self, muted_color: str, accent_color: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("LiveStatusBar")
        self._muted = muted_color
        self._accent = accent_color

        layout = QGridLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setHorizontalSpacing(24)
        layout.setVerticalSpacing(2)

        # Two rows of ~5 columns each so the bar stays compact horizontally
        # instead of scrolling on a 1400px capture.
        per_row = 5
        # Keep the last-set raw value per field so a theme change can
        # re-render the rich text with the fresh palette without losing
        # the value that was displayed.
        self._values: dict[str, str] = {name: _PLACEHOLDER for name, _ in _FIELDS}
        self._labels: dict[str, QLabel] = {}
        for index, (name, _human) in enumerate(_FIELDS):
            row = index // per_row
            col = index % per_row
            container = QLabel()
            container.setTextFormat(Qt.TextFormat.RichText)
            self._labels[name] = container
            layout.addWidget(container, row, col)
        self._apply_label_style()
        self._refresh_all()

        for c in range(per_row):
            layout.setColumnStretch(c, 1)

    def _apply_label_style(self) -> None:
        style = (
            "QLabel { font-family: 'IBM Plex Mono', monospace; font-size: 11px; "
            f"color: {self._muted}; }}"
        )
        for label in self._labels.values():
            label.setStyleSheet(style)

    def _format(self, human: str, value: str) -> str:
        return (
            f'<span style="color:{self._muted}">{human}:</span> '
            f'<span style="color:{self._accent}">{value}</span>'
        )

    def _refresh_all(self) -> None:
        humans = dict(_FIELDS)
        for name, value in self._values.items():
            self._labels[name].setText(self._format(humans[name], value))

    def set_field(self, name: str, value: str | int | None) -> None:
        if name not in self._labels:
            return
        text = _PLACEHOLDER if value is None or value == "" else str(value)
        self._values[name] = text
        human = dict(_FIELDS)[name]
        self._labels[name].setText(self._format(human, text))

    def reset(self) -> None:
        for name in self._labels:
            self.set_field(name, None)

    def apply_palette(self, muted_color: str, accent_color: str) -> None:
        self._muted = muted_color
        self._accent = accent_color
        self._apply_label_style()
        self._refresh_all()

    def field_text(self, name: str) -> str:
        """Test helper -- return the plain text currently shown in the
        named field (strips the label prefix and HTML tags)."""
        raw = self._labels[name].text()
        # Extract the last <span>...</span> value.
        end = raw.rfind("</span>")
        start = raw.rfind(">", 0, end) + 1
        return raw[start:end]
