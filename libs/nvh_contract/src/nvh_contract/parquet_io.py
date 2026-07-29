"""Read/write helpers for the per-DC-record Parquet files defined in
docs/data-contract.md. This is the one place that format is implemented, so
any producer (the simulator today, LabVIEW later) and any consumer (the
analysis engine, the web backend) go through the same code."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


def write_dc_parquet(
    path: str | Path,
    time_s: np.ndarray,
    rpm: np.ndarray,
    tach_pulse: np.ndarray,
    channels: dict[str, np.ndarray],
) -> None:
    n = len(time_s)
    columns: dict[str, np.ndarray] = {
        "sample_index": np.arange(n, dtype=np.int64),
        "time_s": np.asarray(time_s, dtype=np.float64),
        "rpm": np.asarray(rpm, dtype=np.float64),
        "tach_pulse": np.asarray(tach_pulse, dtype=np.int8),
    }
    for channel_name, values in channels.items():
        columns[f"ch_{channel_name}"] = np.asarray(values, dtype=np.float64)

    table = pa.table(columns)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(out_path))


def read_dc_parquet(path: str | Path) -> dict[str, np.ndarray]:
    table = pq.read_table(str(path))
    return {name: table.column(name).to_numpy() for name in table.column_names}


def channel_names_in(columns: dict[str, np.ndarray]) -> list[str]:
    """Extracts calibrated channel names (e.g. 'vib_a') from a dict returned
    by `read_dc_parquet`, i.e. every `ch_<name>` column."""
    return [name[len("ch_") :] for name in columns if name.startswith("ch_")]
