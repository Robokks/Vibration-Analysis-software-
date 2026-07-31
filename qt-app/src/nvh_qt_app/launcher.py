"""Single-window launcher for the NVH stack.

Starts and monitors the four background services (live simulator, FastAPI
backend, Vite web frontend, Qt desktop client) plus offers one-click
access to the two one-shot commands (seed demo data, run analysis demo)
and a "Open Web UI" browser jump. Everything is a subprocess managed via
QProcess so we integrate with the Qt event loop -- no threads.

Entry point: `nvh-launcher` (see qt-app/pyproject.toml [project.scripts]).
"""

from __future__ import annotations

import shutil
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QProcessEnvironment
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nvh_design_tokens import load_tokens

from .theme import build_stylesheet
from .theme_manager import PALETTE_DARK, ThemeManager
from .widgets.gear_glyph import colored_svg_bytes

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_URL = "sqlite:///./data/nvh_demo/nvh_demo.db"
WEB_UI_URL = "http://localhost:5173"
DEFAULT_DAQ_DEVICE = "Dev1"
DEFAULT_DAQ_CHANNEL = "ai0"

_STATUS_IDLE = "idle"
_STATUS_STARTING = "starting"
_STATUS_RUNNING = "running"
_STATUS_CRASHED = "crashed"


@dataclass
class ServiceSpec:
    """Defines one managed background process."""

    key: str
    name: str
    description: str
    program: str
    args: list[str] = field(default_factory=list)
    cwd: Path = REPO_ROOT
    env: dict[str, str] = field(default_factory=dict)


def _build_service_specs() -> list[ServiceSpec]:
    npm = shutil.which("npm") or "npm"
    return [
        ServiceSpec(
            key="sim",
            name="Live Simulator (synthetic)",
            description="ZeroMQ PUB — synthetic gearbox signal on tcp://*:5555",
            program=sys.executable,
            args=[str(REPO_ROOT / "web-backend/scripts/live_simulator.py")],
        ),
        ServiceSpec(
            key="daq",
            name="NI-DAQmx Producer",
            description=(
                f"ZeroMQ PUB — NI-DAQmx {DEFAULT_DAQ_DEVICE}/{DEFAULT_DAQ_CHANNEL} "
                "(real hardware or a NI MAX simulated device)"
            ),
            program=sys.executable,
            args=[
                str(REPO_ROOT / "web-backend/scripts/live_daq.py"),
                "--device", DEFAULT_DAQ_DEVICE,
                "--channel", DEFAULT_DAQ_CHANNEL,
            ],
        ),
        ServiceSpec(
            key="backend",
            name="FastAPI Backend",
            description="REST + WebSocket API on :8000 (serves seeded SQLite)",
            program=sys.executable,
            args=["-m", "nvh_web_backend"],
            env={"NVH_DB_URL": DEFAULT_DB_URL},
        ),
        ServiceSpec(
            key="web",
            name="Web Frontend (Vite)",
            description=f"React dev server on {WEB_UI_URL}",
            program=npm,
            args=["run", "dev"],
            cwd=REPO_ROOT / "web-frontend",
        ),
        ServiceSpec(
            key="qt",
            name="Qt Desktop App",
            description="PySide6 client (Master Entry / Reports / Live Display)",
            program=sys.executable,
            args=["-m", "nvh_qt_app"],
        ),
    ]


class ProcessRow(QFrame):
    """One managed service: LED + name/desc + Start/Stop + log tail."""

    def __init__(self, spec: ServiceSpec, palette: dict[str, str]) -> None:
        super().__init__()
        self.spec = spec
        self._palette = palette
        self._status = _STATUS_IDLE
        self._proc: QProcess | None = None

        self.setObjectName("ProcessRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)

        self.led = QLabel()
        self.led.setFixedSize(14, 14)
        header.addWidget(self.led)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        self.name_lbl = QLabel(spec.name)
        name_font = QFont()
        name_font.setBold(True)
        self.name_lbl.setFont(name_font)
        self.desc_lbl = QLabel(spec.description)
        self.desc_lbl.setStyleSheet(f"color: {palette['secondaryText']};")
        text_col.addWidget(self.name_lbl)
        text_col.addWidget(self.desc_lbl)
        header.addLayout(text_col, stretch=1)

        self.status_lbl = QLabel("idle")
        self.status_lbl.setMinimumWidth(70)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.status_lbl)

        self.action_btn = QPushButton("Start")
        self.action_btn.setMinimumWidth(80)
        self.action_btn.clicked.connect(self._toggle)
        header.addWidget(self.action_btn)

        outer.addLayout(header)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setFixedHeight(110)
        log_font = QFont("Menlo, Consolas, monospace")
        log_font.setPointSize(9)
        self.log.setFont(log_font)
        outer.addWidget(self.log)

        self._paint_led()

    def apply_palette(self, palette: dict[str, str]) -> None:
        self._palette = palette
        self.desc_lbl.setStyleSheet(f"color: {palette['secondaryText']};")
        self._paint_led()
        self._paint_status()

    def _toggle(self) -> None:
        if self._status in (_STATUS_RUNNING, _STATUS_STARTING):
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            return

        self._append_log(f"$ {self.spec.program} {' '.join(self.spec.args)}")
        self._append_log(f"  cwd={self.spec.cwd}")

        proc = QProcess(self)
        proc.setWorkingDirectory(str(self.spec.cwd))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        env = QProcessEnvironment.systemEnvironment()
        for k, v in self.spec.env.items():
            env.insert(k, v)
        proc.setProcessEnvironment(env)

        proc.readyReadStandardOutput.connect(self._on_output)
        proc.started.connect(self._on_started)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        proc.start(self.spec.program, self.spec.args)
        self._proc = proc
        self._set_status(_STATUS_STARTING)

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.state() == QProcess.ProcessState.NotRunning:
            self._proc = None
            self._set_status(_STATUS_IDLE)
            return
        self._append_log("--- terminate requested ---")
        self._proc.terminate()
        if not self._proc.waitForFinished(3000):
            self._append_log("--- kill (SIGKILL) ---")
            self._proc.kill()

    def _on_started(self) -> None:
        self._set_status(_STATUS_RUNNING)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._append_log(f"--- exited: code {exit_code} ---")
        if exit_code == 0 or self._status == _STATUS_STARTING:
            self._set_status(_STATUS_IDLE)
        else:
            self._set_status(_STATUS_CRASHED)
        self._proc = None

    def _on_error(self, err: QProcess.ProcessError) -> None:
        self._append_log(f"--- QProcess error: {err.name} ---")
        if err == QProcess.ProcessError.FailedToStart:
            self._set_status(_STATUS_CRASHED)

    def _on_output(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        if data:
            for line in data.splitlines():
                if line:
                    self._append_log(line)

    def _append_log(self, line: str) -> None:
        self.log.appendPlainText(line)

    def _set_status(self, status: str) -> None:
        self._status = status
        self._paint_led()
        self._paint_status()
        if status in (_STATUS_RUNNING, _STATUS_STARTING):
            self.action_btn.setText("Stop")
        else:
            self.action_btn.setText("Start")

    def _paint_led(self) -> None:
        color = {
            _STATUS_IDLE: self._palette["secondaryText"],
            _STATUS_STARTING: self._palette["accentPrimary"],
            _STATUS_RUNNING: self._palette["pass"],
            _STATUS_CRASHED: self._palette["alarm"],
        }[self._status]
        self.led.setStyleSheet(
            f"background-color: {color}; border-radius: 7px;"
        )

    def _paint_status(self) -> None:
        color = {
            _STATUS_IDLE: self._palette["secondaryText"],
            _STATUS_STARTING: self._palette["accentPrimary"],
            _STATUS_RUNNING: self._palette["pass"],
            _STATUS_CRASHED: self._palette["alarm"],
        }[self._status]
        self.status_lbl.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.status_lbl.setText(self._status)


class OneShotBar(QFrame):
    """Top row of one-click actions: seed data, analysis demo, open web UI."""

    def __init__(self, main_log: QPlainTextEdit) -> None:
        super().__init__()
        self._main_log = main_log
        self._active: QProcess | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self.seed_btn = QPushButton("Seed Demo Data")
        self.seed_btn.setToolTip(
            "One-shot: writes ./data/nvh_demo/ Parquet + SQLite (~30 trials)."
        )
        self.seed_btn.clicked.connect(self._seed)
        outer.addWidget(self.seed_btn)

        self.sim_btn = QPushButton("Run Analysis Demo")
        self.sim_btn.setToolTip(
            "One-shot: nvh-sim --trials 30 --out report.json (CLI PASS/FAIL demo)."
        )
        self.sim_btn.clicked.connect(self._analysis)
        outer.addWidget(self.sim_btn)

        self.web_btn = QPushButton("Open Web UI")
        self.web_btn.setToolTip(f"Opens {WEB_UI_URL} in your default browser.")
        self.web_btn.clicked.connect(lambda: webbrowser.open(WEB_UI_URL))
        outer.addWidget(self.web_btn)

        outer.addStretch(1)

    def _seed(self) -> None:
        self._run_oneshot(
            "Seed Demo Data",
            sys.executable,
            [
                str(REPO_ROOT / "web-backend/scripts/seed_demo_data.py"),
                "--data-root",
                "./data/nvh_demo",
                "--trials",
                "30",
            ],
        )

    def _analysis(self) -> None:
        self._run_oneshot(
            "Analysis Demo",
            sys.executable,
            ["-m", "nvh_simulator.cli", "--trials", "30", "--out", "report.json"],
        )

    def _run_oneshot(self, label: str, program: str, args: list[str]) -> None:
        if self._active is not None and self._active.state() != QProcess.ProcessState.NotRunning:
            self._log(f"[{label}] skipped -- another one-shot is still running")
            return

        self._log(f"[{label}] $ {program} {' '.join(args)}")
        proc = QProcess(self)
        proc.setWorkingDirectory(str(REPO_ROOT))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(
            lambda p=proc, l=label: self._on_output(p, l)
        )
        proc.finished.connect(lambda code, _st, l=label: self._log(f"[{l}] exited: code {code}"))
        proc.start(program, args)
        self._active = proc
        self._set_enabled(False)
        proc.finished.connect(lambda *_: self._set_enabled(True))

    def _on_output(self, proc: QProcess, label: str) -> None:
        text = bytes(proc.readAllStandardOutput()).decode(errors="replace")
        for line in text.splitlines():
            if line:
                self._log(f"[{label}] {line}")

    def _set_enabled(self, enabled: bool) -> None:
        self.seed_btn.setEnabled(enabled)
        self.sim_btn.setEnabled(enabled)

    def _log(self, line: str) -> None:
        self._main_log.appendPlainText(line)


class LauncherWindow(QMainWindow):
    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self._theme = theme

        self.setWindowTitle("NVH Launcher")
        self.setMinimumSize(920, 900)
        self.setWindowIcon(_window_icon())

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        title = QLabel("NVH Test System")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        subtitle = QLabel(
            f"Root: {REPO_ROOT}  ·  Backend DB: {DEFAULT_DB_URL}"
        )
        subtitle.setStyleSheet(f"color: {self._current_palette()['secondaryText']};")
        self._subtitle = subtitle
        outer.addWidget(subtitle)

        self.oneshot_log = QPlainTextEdit()
        self.oneshot_log.setReadOnly(True)
        self.oneshot_log.setMaximumBlockCount(500)
        self.oneshot_log.setFixedHeight(90)
        log_font = QFont("Menlo, Consolas, monospace")
        log_font.setPointSize(9)
        self.oneshot_log.setFont(log_font)

        self.oneshot_bar = OneShotBar(self.oneshot_log)
        outer.addWidget(self.oneshot_bar)
        outer.addWidget(self.oneshot_log)

        self._rows: list[ProcessRow] = []
        palette = self._current_palette()
        for spec in _build_service_specs():
            row = ProcessRow(spec, palette)
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self._rows.append(row)
            outer.addWidget(row)

        outer.addStretch(1)

        theme.theme_changed.connect(self._on_theme_changed)

    def _current_palette(self) -> dict[str, str]:
        return load_tokens()["color"]["palettes"][self._theme.palette_name]

    def _on_theme_changed(self, _palette_name: str) -> None:
        palette = self._current_palette()
        self._subtitle.setStyleSheet(f"color: {palette['secondaryText']};")
        for row in self._rows:
            row.apply_palette(palette)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        running = [r for r in self._rows if r._status == _STATUS_RUNNING]
        if running:
            names = ", ".join(r.spec.name for r in running)
            answer = QMessageBox.question(
                self,
                "Stop running services?",
                f"Still running: {names}.\n\nStop them and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for row in running:
                row.stop()
        super().closeEvent(event)


def _window_icon() -> QIcon:
    tokens = load_tokens()
    accent = tokens["color"]["palettes"]["dark"]["accentPrimary"]
    renderer = QSvgRenderer(colored_svg_bytes(accent))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    theme = ThemeManager(initial=PALETTE_DARK)
    app.setStyleSheet(build_stylesheet(theme.palette_name))
    theme.theme_changed.connect(lambda name: app.setStyleSheet(build_stylesheet(name)))
    app.theme = theme  # type: ignore[attr-defined]

    window = LauncherWindow(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
