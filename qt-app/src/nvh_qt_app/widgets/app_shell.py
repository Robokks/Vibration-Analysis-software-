"""The main window: header bar (gear-glyph mark + title + nav) over a
stacked widget holding the three screens — the Qt-side equivalent of the web
frontend's ``AppShell`` component."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..screens.live_display import LiveDisplayScreen
from ..screens.master_entry import MasterEntryScreen
from ..screens.reports import ReportsScreen
from ..theme import build_stylesheet
from ..theme_manager import ThemeManager
from .gear_glyph import GearGlyphWidget
from .labels import AppSubtitle, AppTitle
from .nav_button import NavButton
from .panel import HeaderBar

_SCREENS = [
    ("Live Display", LiveDisplayScreen),
    ("Master Entry", MasterEntryScreen),
    ("Reports", ReportsScreen),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NVH EOL Test System")
        self.resize(1280, 800)

        # Attach a theme manager to the QApplication if app.main() didn't
        # (tests instantiate MainWindow directly without going through
        # app.main), so any widget can reach QApplication.instance().theme.
        app = QApplication.instance()
        if not hasattr(app, "theme"):
            app.theme = ThemeManager()
            app.setStyleSheet(build_stylesheet(app.theme.palette_name))
            app.theme.theme_changed.connect(
                lambda name: app.setStyleSheet(build_stylesheet(name))
            )
        self._theme = app.theme

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())

        self._stack = QStackedWidget()
        for _, screen_cls in _SCREENS:
            self._stack.addWidget(screen_cls())
        root_layout.addWidget(self._stack, stretch=1)

        self.setCentralWidget(central)

    def _build_header(self) -> HeaderBar:
        header = HeaderBar()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 12, 24, 12)

        mark = GearGlyphWidget()
        mark.setFixedSize(32, 24)
        layout.addWidget(mark)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(AppTitle("NVH EOL Test System"))
        title_box.addWidget(AppSubtitle("Report GUI — scaffold build"))
        layout.addLayout(title_box)

        layout.addStretch(1)

        nav_group = QButtonGroup(header)
        nav_group.setExclusive(True)
        for index, (label, _) in enumerate(_SCREENS):
            button = NavButton(label)
            nav_group.addButton(button, index)
            layout.addWidget(button)
            if index == 0:
                button.setChecked(True)
        nav_group.idClicked.connect(self._show_screen)
        self._nav_group = nav_group

        # Theme toggle button -- label reflects the palette a click will
        # switch TO (matches OS convention). Distinct object name so the
        # QSS can target it explicitly if we want to and so tests can
        # find it without knowing the layout index.
        self._theme_button = QPushButton(self._theme.human_label())
        self._theme_button.setObjectName("ThemeToggle")
        self._theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._theme_button.clicked.connect(self._theme.toggle)
        self._theme.theme_changed.connect(
            lambda _name: self._theme_button.setText(self._theme.human_label())
        )
        layout.addWidget(self._theme_button)

        return header

    def _show_screen(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
