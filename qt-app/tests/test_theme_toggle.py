"""Tests for the runtime dark/light theme toggle: manager emits on
switch, header button flips label, connected screens see the change."""

from nvh_qt_app.theme_manager import PALETTE_DARK, PALETTE_LIGHT, ThemeManager
from nvh_qt_app.widgets.app_shell import MainWindow


class ThemeManagerTests:
    def test_starts_in_dark(self):
        m = ThemeManager()
        assert m.palette_name == PALETTE_DARK
        assert m.other() == PALETTE_LIGHT

    def test_toggle_flips_and_emits(self):
        m = ThemeManager()
        seen: list[str] = []
        m.theme_changed.connect(lambda name: seen.append(name))
        m.toggle()
        assert m.palette_name == PALETTE_LIGHT
        assert seen == [PALETTE_LIGHT]
        m.toggle()
        assert m.palette_name == PALETTE_DARK
        assert seen == [PALETTE_LIGHT, PALETTE_DARK]

    def test_human_label_reflects_switch_target(self):
        m = ThemeManager()
        assert m.human_label() == "Light"
        m.toggle()
        assert m.human_label() == "Dark"


class HeaderThemeToggleTests:
    def test_toggle_button_present_and_flips_app_theme(self, qapp):
        window = MainWindow()
        button = window._theme_button
        assert button is not None
        assert button.text() == "Light"
        button.click()
        assert qapp.theme.palette_name == PALETTE_LIGHT
        assert button.text() == "Dark"
