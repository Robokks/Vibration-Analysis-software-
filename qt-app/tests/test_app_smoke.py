"""Boots the app shell headlessly (requires QT_QPA_PLATFORM=offscreen, which
conftest.py sets automatically) and checks navigation switches screens
without crashing. Not a visual regression test — just "does it come up."
"""

from nvh_qt_app.screens.live_display import LiveDisplayScreen
from nvh_qt_app.screens.master_entry import MasterEntryScreen
from nvh_qt_app.screens.reports import ReportsScreen
from nvh_qt_app.theme import build_stylesheet
from nvh_qt_app.widgets.app_shell import MainWindow


class BuildStylesheetTests:
    def test_returns_nonempty_qss_for_both_palettes(self):
        assert "background-color: #12161C" in build_stylesheet("dark")
        assert "background-color: #FFFFFF" in build_stylesheet("print")


class MainWindowTests:
    def test_starts_on_live_display_and_holds_three_screens(self, qapp):
        window = MainWindow()
        assert window._stack.count() == 3
        assert window._stack.currentIndex() == 0
        assert isinstance(window._stack.widget(0), LiveDisplayScreen)
        assert isinstance(window._stack.widget(1), MasterEntryScreen)
        assert isinstance(window._stack.widget(2), ReportsScreen)

    def test_nav_buttons_switch_the_visible_screen(self, qapp):
        window = MainWindow()
        window._show_screen(2)
        assert window._stack.currentIndex() == 2
        window._show_screen(1)
        assert window._stack.currentIndex() == 1
