"""Live-stat readout for the "Computed" tab: RMS / peak / crest / mean /
sample count, re-computed on every trace update from the same rolling
buffer the raw signal draws from. Uses numpy for the reductions -- it's
already a project dep and the buffer never gets larger than a few
thousand samples so a per-frame recompute is comfortably fast."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget


class LiveStatsPanel(QWidget):
    """Displays RMS/peak/crest/mean/N over the current live buffer.
    Call ``update_from_buffer(samples)`` on every trace update -- an empty
    or too-short buffer paints em-dashes instead of NaN readings."""

    def __init__(self, muted_color: str, accent_color: str, parent=None) -> None:
        super().__init__(parent)
        self._muted = muted_color
        self._accent = accent_color

        layout = QGridLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setHorizontalSpacing(48)
        layout.setVerticalSpacing(12)

        self._labels: dict[str, QLabel] = {}
        rows = (
            ("RMS", "rms"), ("Peak", "peak"), ("Crest", "crest"),
            ("Mean", "mean"), ("Samples", "samples"),
        )
        for index, (title, key) in enumerate(rows):
            title_label = QLabel(title)
            title_label.setStyleSheet(
                "QLabel { color: " + self._muted + "; "
                "font-family: 'IBM Plex Sans', sans-serif; font-size: 12px; "
                "letter-spacing: 0.1em; text-transform: uppercase; }"
            )
            value_label = QLabel("—")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setStyleSheet(
                "QLabel { color: " + self._accent + "; "
                "font-family: 'IBM Plex Mono', monospace; font-size: 24px; }"
            )
            layout.addWidget(title_label, index, 0)
            layout.addWidget(value_label, index, 1)
            self._labels[key] = value_label
        layout.setColumnStretch(1, 1)

    def update_from_buffer(self, samples: Sequence[float]) -> None:
        if len(samples) < 8:
            for widget in self._labels.values():
                widget.setText("—")
            return
        arr = np.asarray(samples, dtype=float)
        rms = float(np.sqrt(np.mean(arr * arr)))
        peak = float(np.max(np.abs(arr)))
        crest = peak / rms if rms > 0 else float("nan")
        mean = float(np.mean(arr))
        self._labels["rms"].setText(f"{rms:.4g}")
        self._labels["peak"].setText(f"{peak:.4g}")
        self._labels["crest"].setText("—" if np.isnan(crest) else f"{crest:.3f}")
        self._labels["mean"].setText(f"{mean:.3g}")
        self._labels["samples"].setText(f"{len(samples)}")

    def clear(self) -> None:
        for widget in self._labels.values():
            widget.setText("—")
