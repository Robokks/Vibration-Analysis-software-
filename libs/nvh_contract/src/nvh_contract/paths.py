"""Filesystem layout helpers for the raw-data logging tree.

The industrial requirement: raw TDMS files live under a
`YYYY/MM/DD/TrialN/model/serial_rpt/` nested tree, keyed on the run's
(gear_id, nvh_id) pair so post-analysis tools can locate exactly one
file per state-transition without scanning.

This module owns the path derivation so producers, launcher-side
tests, and post-analysis readers all agree on the shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def raw_tdms_path(
    base_dir: str | Path,
    model_id: str,
    serial_no: str,
    serial_rpt: str | int,
    trial_no: int,
    gear_id: int,
    nvh_id: int,
    *,
    when: datetime | None = None,
) -> Path:
    """Return the absolute Path where a TDMS file for one
    (gear_id, nvh_id) segment should be written.

    Layout::

        <base_dir>/YYYY/MM/DD/Trial{N}/{model_id}/{serial}_{rpt}/{serial}_{gear_id}_{nvh_id}.tdms

    - `when` (default: `datetime.now(timezone.utc)`) sources the
      YYYY/MM/DD prefix; injectable so tests can pin timestamps.
    - `serial_rpt` may be an int (typical repeat count) or a string
      (in case operator entry uses a suffix like "R2").
    - The parent directory is *not* created here -- the producer does
      `parent.mkdir(parents=True, exist_ok=True)` before opening the
      TdmsWriter so a filesystem error surfaces at write time, not
      at path-construction time.
    """
    when = when or datetime.now(timezone.utc)
    y, m, d = when.strftime("%Y"), when.strftime("%m"), when.strftime("%d")
    filename = f"{serial_no}_{gear_id}_{nvh_id}.tdms"
    return (
        Path(base_dir)
        / y / m / d
        / f"Trial{trial_no}"
        / str(model_id)
        / f"{serial_no}_{serial_rpt}"
        / filename
    )


def state_file_path(base_dir: str | Path) -> Path:
    """Where the persistent trial counter lives (see
    `NvhStateMachine.trial_no`). Kept alongside the raw tree at
    `<base_dir>/state.json` so a re-launch continues counting from
    where the last run left off."""
    return Path(base_dir) / "state.json"
