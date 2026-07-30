"""Calibration screen -- matches the Vibr-O-Matic Analyzer manual's
Calibration window (section 7). Per-channel form: sensor sensitivity
[mV/EU], engineering units, dB reference [EU], custom label, weighting
filter, pregain [dB], plus a Summary showing the last-calibrated date
and the next-due date.

Backed by GET / PATCH /models/{model_id}/calibrations/{channel_name}
-- the endpoint seeds the LabVIEW-manual defaults on first read, so
this screen works against a freshly-created model without an
explicit seed step."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from nvh_design_tokens import load_tokens

from ..api_client import ApiClient
from ..widgets.labels import MonoLabel, SectionTitle
from ..widgets.panel import Panel

# Same demo-scoping story: one model, one channel today.
MODEL_ID = "MODEL-A"
CHANNEL_NAME = "vib_a"

_ENGINEERING_UNITS = ("V", "g", "m/s^2", "in/s^2", "Pa", "custom")
_WEIGHTING_FILTERS = ("linear", "A", "B", "C", "D")


class CalibrationScreen(QWidget):
    def __init__(self, parent=None, api_client: ApiClient | None = None) -> None:
        super().__init__(parent)
        self._api = api_client if api_client is not None else ApiClient()

        palette = load_tokens()["color"]["palettes"]["dark"]
        self._muted = palette["secondaryText"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._status = MonoLabel(f"loading calibration for {CHANNEL_NAME}…")
        layout.addWidget(self._status)

        # --- Channel info form -------------------------------------
        form_panel = Panel()
        form_layout = QVBoxLayout(form_panel)
        form_layout.addWidget(SectionTitle("Channel info"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)

        self._sensitivity = QDoubleSpinBox()
        self._sensitivity.setRange(0.0001, 1e6)
        self._sensitivity.setDecimals(4)
        self._sensitivity.setSuffix(" mV/EU")
        form.addRow("Sensor sensitivity", self._sensitivity)

        self._engineering_units = QComboBox()
        self._engineering_units.addItems(_ENGINEERING_UNITS)
        form.addRow("Engineering units", self._engineering_units)

        self._db_reference = QDoubleSpinBox()
        self._db_reference.setRange(1e-9, 1e6)
        self._db_reference.setDecimals(6)
        form.addRow("dB reference [EU]", self._db_reference)

        self._custom_label = QLineEdit()
        self._custom_label.setPlaceholderText("EU")
        form.addRow("Custom label", self._custom_label)

        self._weighting_filter = QComboBox()
        self._weighting_filter.addItems(_WEIGHTING_FILTERS)
        form.addRow("Weighting filter", self._weighting_filter)

        self._pregain = QDoubleSpinBox()
        self._pregain.setRange(-60.0, 60.0)
        self._pregain.setDecimals(2)
        self._pregain.setSuffix(" dB")
        form.addRow("Pregain", self._pregain)

        form_layout.addLayout(form)

        # Save button + status.
        save_row = QHBoxLayout()
        self._save_button = QPushButton("Save calibration")
        self._save_button.setObjectName("CalibrationSave")
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.clicked.connect(self._on_save_clicked)
        save_row.addWidget(self._save_button)
        save_row.addStretch(1)
        form_layout.addLayout(save_row)
        layout.addWidget(form_panel)

        # --- Summary section ---------------------------------------
        summary_panel = Panel()
        summary_layout = QVBoxLayout(summary_panel)
        summary_layout.addWidget(SectionTitle("Summary"))
        self._last_label = MonoLabel("Last calibration date/time: —")
        self._due_label = MonoLabel("Due date: —")
        summary_layout.addWidget(self._last_label)
        summary_layout.addWidget(self._due_label)
        layout.addWidget(summary_panel)

        layout.addStretch(1)

        self._api.fetch_calibration(MODEL_ID, CHANNEL_NAME, self._on_calibration, self._on_error)

    # --- REST callbacks ------------------------------------------------

    def _on_calibration(self, payload: dict[str, Any]) -> None:
        self._apply_payload(payload)
        self._status.setText(f"calibration loaded for channel {CHANNEL_NAME}")

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        self._sensitivity.setValue(float(payload.get("sensor_sensitivity_mv_per_eu", 1000.0)))
        units = payload.get("engineering_units", "V")
        idx = self._engineering_units.findText(units)
        if idx >= 0:
            self._engineering_units.setCurrentIndex(idx)
        self._db_reference.setValue(float(payload.get("db_reference_eu", 1.0)))
        self._custom_label.setText(payload.get("custom_label") or "")
        weighting = payload.get("weighting_filter", "linear")
        idx = self._weighting_filter.findText(weighting)
        if idx >= 0:
            self._weighting_filter.setCurrentIndex(idx)
        self._pregain.setValue(float(payload.get("pregain_db", 0.0)))
        self._last_label.setText(
            f"Last calibration date/time: {payload.get('last_calibrated_at') or '—'}"
        )
        self._due_label.setText(f"Due date: {payload.get('due_at') or '—'}")

    def _on_save_clicked(self) -> None:
        payload = {
            "sensor_sensitivity_mv_per_eu": self._sensitivity.value(),
            "engineering_units": self._engineering_units.currentText(),
            "db_reference_eu": self._db_reference.value(),
            "custom_label": self._custom_label.text() or "EU",
            "weighting_filter": self._weighting_filter.currentText(),
            "pregain_db": self._pregain.value(),
            # Save = calibration event -- stamp both last_calibrated_at
            # (now) and due_at (12 months from now, matching the manual's
            # implicit "annual recalibration" convention).
            "last_calibrated_at": datetime.now(timezone.utc).isoformat(),
            "due_at": _one_year_from_now(),
        }
        self._save_button.setEnabled(False)
        self._status.setText(f"saving calibration for {CHANNEL_NAME}…")
        self._api.patch_calibration(
            MODEL_ID, CHANNEL_NAME, payload, self._on_saved, self._on_save_error,
        )

    def _on_saved(self, payload: dict[str, Any]) -> None:
        self._apply_payload(payload)
        self._status.setText(f"calibration saved for {CHANNEL_NAME}")
        self._save_button.setEnabled(True)

    def _on_save_error(self, message: str) -> None:
        self._status.setText(f"save failed: {message}")
        self._save_button.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self._status.setText(f"failed to reach backend: {message}")


def _one_year_from_now() -> str:
    now = datetime.now(timezone.utc)
    # Naive "same month/day, next year" -- Feb 29 rolls to Feb 28 next
    # year on non-leap years, which is fine for a due-date approximation.
    try:
        due = now.replace(year=now.year + 1)
    except ValueError:
        due = now.replace(year=now.year + 1, day=28)
    return due.strftime("%Y-%m-%d")
