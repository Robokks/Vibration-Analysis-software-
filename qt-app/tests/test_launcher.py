from nvh_qt_app.launcher import (
    LauncherWindow,
    OneShotBar,
    ProcessRow,
    _build_service_specs,
    _STATUS_CRASHED,
    _STATUS_IDLE,
    _STATUS_RUNNING,
)
from nvh_qt_app.theme_manager import PALETTE_DARK, PALETTE_LIGHT, ThemeManager
from nvh_design_tokens import load_tokens


class LauncherWindowTests:
    def test_all_services_rendered(self, qapp):
        theme = ThemeManager(initial=PALETTE_DARK)
        window = LauncherWindow(theme)

        assert len(window._rows) == 5
        service_keys = [row.spec.key for row in window._rows]
        assert service_keys == ["sim", "daq", "backend", "web", "qt"]

        window.close()

    def test_daq_row_targets_live_daq_script(self, qapp):
        theme = ThemeManager(initial=PALETTE_DARK)
        window = LauncherWindow(theme)

        daq_row = next(r for r in window._rows if r.spec.key == "daq")
        assert daq_row.spec.args[0].endswith("live_daq.py")
        assert "--device" in daq_row.spec.args
        assert "--channel" in daq_row.spec.args

        window.close()

    def test_theme_flip_repaints_rows(self, qapp):
        theme = ThemeManager(initial=PALETTE_DARK)
        window = LauncherWindow(theme)
        dark = load_tokens()["color"]["palettes"][PALETTE_DARK]
        light = load_tokens()["color"]["palettes"][PALETTE_LIGHT]
        assert dark["secondaryText"] != light["secondaryText"]

        for row in window._rows:
            assert row._palette["secondaryText"] == dark["secondaryText"]

        theme.set_palette(PALETTE_LIGHT)

        for row in window._rows:
            assert row._palette["secondaryText"] == light["secondaryText"]

        window.close()


class ProcessRowTests:
    def test_status_transitions_repaint_led_and_button(self, qapp):
        spec = _build_service_specs()[0]
        palette = load_tokens()["color"]["palettes"][PALETTE_DARK]
        row = ProcessRow(spec, palette)

        assert row._status == _STATUS_IDLE
        assert row.action_btn.text() == "Start"

        row._set_status(_STATUS_RUNNING)
        assert row.action_btn.text() == "Stop"
        assert palette["pass"].lower() in row.led.styleSheet().lower()

        row._set_status(_STATUS_CRASHED)
        assert row.action_btn.text() == "Start"
        assert palette["alarm"].lower() in row.led.styleSheet().lower()


class OneShotBarTests:
    def test_buttons_present_and_enabled(self, qapp):
        from PySide6.QtWidgets import QPlainTextEdit

        log = QPlainTextEdit()
        bar = OneShotBar(log)
        assert bar.seed_btn.isEnabled()
        assert bar.sim_btn.isEnabled()
        assert bar.web_btn.isEnabled()

    def test_disable_during_oneshot(self, qapp):
        from PySide6.QtWidgets import QPlainTextEdit

        log = QPlainTextEdit()
        bar = OneShotBar(log)
        bar._set_enabled(False)
        assert not bar.seed_btn.isEnabled()
        assert not bar.sim_btn.isEnabled()
        # Web-UI button stays enabled -- it just opens a browser.
        assert bar.web_btn.isEnabled()
