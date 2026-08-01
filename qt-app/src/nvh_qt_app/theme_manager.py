"""Runtime theme switching. Owns the current palette name and emits
`theme_changed(palette_name)` when it flips. Widgets with inline styles
(colors set via setStyleSheet at construction, not via type-selector
QSS) can subscribe to keep in sync when the operator toggles the theme.

Two palettes are supported today, both defined in the design-tokens
package: ``dark`` (the default operator theme, cyan-on-black
oscilloscope aesthetic) and ``print`` (originally intended for
paper/PDF report output -- reused here as the "light" mode since it's
already a fully specified light-background palette)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from nvh_design_tokens import load_tokens

# The palette names in tokens.json are "dark" / "print"; keep those in
# storage/wire form so we don't fork the token file, but expose a
# human-facing "light"/"dark" toggle label to the UI.
PALETTE_DARK = "dark"
PALETTE_LIGHT = "print"

_HUMAN_LABEL = {PALETTE_DARK: "Dark", PALETTE_LIGHT: "Light"}


class ThemeManager(QObject):
    """One instance per QApplication -- created in ``app.main()`` and
    attached as ``QApplication.instance().theme`` so any widget can reach
    it without a constructor chain."""

    theme_changed = Signal(str)

    def __init__(self, initial: str = PALETTE_DARK, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._palette_name = initial

    @property
    def palette_name(self) -> str:
        return self._palette_name

    @property
    def palette(self) -> dict:
        return load_tokens()["color"]["palettes"][self._palette_name]

    def other(self) -> str:
        return PALETTE_LIGHT if self._palette_name == PALETTE_DARK else PALETTE_DARK

    def human_label(self) -> str:
        """Text for the toggle button -- shows the palette the click will
        SWITCH TO (matches the "click to go to X" convention every OS's
        dark-mode toggle uses)."""
        return _HUMAN_LABEL[self.other()]

    def set_palette(self, name: str) -> None:
        if name not in (PALETTE_DARK, PALETTE_LIGHT):
            raise ValueError(f"unknown palette {name!r}")
        if name == self._palette_name:
            return
        self._palette_name = name
        self.theme_changed.emit(name)

    def toggle(self) -> None:
        self.set_palette(self.other())
