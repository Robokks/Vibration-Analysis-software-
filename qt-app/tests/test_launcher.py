from nvh_qt_app.launcher import (
    LauncherWindow,
    OneShotBar,
    ProcessRow,
    ProducerRow,
    SOURCE_DAQ,
    SOURCE_SIM,
    _build_service_specs,
    _producer_specs,
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

        # Row 0 is the shared Live Producer, then the three fixed services.
        assert len(window._rows) == 4
        assert isinstance(window._rows[0], ProducerRow)
        assert [r.spec.key for r in window._rows[1:]] == ["backend", "web", "qt"]

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


class ProducerRowTests:
    def _make(self, qapp, initial=SOURCE_SIM):
        palette = load_tokens()["color"]["palettes"][PALETTE_DARK]
        return ProducerRow(palette, initial=initial)

    def test_defaults_to_simulation(self, qapp):
        row = self._make(qapp)
        assert row.selected_source() == SOURCE_SIM
        assert row.sim_btn.isChecked()
        assert not row.daq_btn.isChecked()
        assert row.spec.key == SOURCE_SIM
        assert "live_simulator.py" in row.spec.args[0]

    def test_click_daq_switches_spec(self, qapp):
        row = self._make(qapp)
        row.daq_btn.setChecked(True)
        row._select(SOURCE_DAQ)
        assert row.selected_source() == SOURCE_DAQ
        assert row.spec.key == SOURCE_DAQ
        assert "live_daq.py" in row.spec.args[0]
        assert "--device" in row.spec.args
        assert "--channel" in row.spec.args

    def test_pills_disabled_while_running(self, qapp):
        row = self._make(qapp)
        assert row.sim_btn.isEnabled()
        assert row.daq_btn.isEnabled()
        row._set_status(_STATUS_RUNNING)
        assert not row.sim_btn.isEnabled()
        assert not row.daq_btn.isEnabled()
        row._set_status(_STATUS_IDLE)
        assert row.sim_btn.isEnabled()
        assert row.daq_btn.isEnabled()

    def test_select_is_a_no_op_while_running(self, qapp):
        row = self._make(qapp)
        row._set_status(_STATUS_RUNNING)
        row._select(SOURCE_DAQ)  # ignored -- can't switch mid-run
        assert row.selected_source() == SOURCE_SIM


class ProducerSpecTests:
    def test_both_producers_defined(self):
        specs = _producer_specs()
        assert set(specs.keys()) == {SOURCE_SIM, SOURCE_DAQ}
        assert "live_simulator.py" in specs[SOURCE_SIM].args[0]
        assert "live_daq.py" in specs[SOURCE_DAQ].args[0]


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
