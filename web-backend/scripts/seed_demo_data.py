"""Seeds a demo dataset that actually persists per docs/data-contract.md:
Parquet files on disk plus nvh_contract DB rows (models, test_runs,
dc_records, master_signatures, grading_results, spc_points).

Nothing in the repo writes this data today — the simulator only produces
in-memory signals — so this script is the first thing that ever closes the
loop end-to-end. It's the data the web backend (built in a later milestone)
will serve, and can be re-run at any time to reset the demo dataset.

Usage:
    python web-backend/scripts/seed_demo_data.py --data-root ./data/nvh_demo --trials 30
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from analysis_engine.pipeline import STAT_NAMES, analyze_dc_record, build_masters_from_trials, stats_to_dict
from analysis_engine.signal.stats import compute_stats
from nvh_contract import CONTRACT_VERSION
from nvh_contract.db import (
    DcRecordRow,
    GradingResultRow,
    MasterSignatureRow,
    ModelRow,
    SpcPointRow,
    TestRunRow,
    init_db,
    make_engine,
    make_session_factory,
)
from nvh_contract.parquet_io import write_dc_parquet
from nvh_simulator.faults import Fault
from nvh_simulator.generators import generate_dc_record

MODEL_ID = "MODEL-A"
GEAR_LABEL = "R"
DIRECTION = "RU"
SAMPLE_RATE_HZ = 5000.0
RPM_START, RPM_END = 1000.0, 2500.0
DURATION_S = 4.0
PLANT_ID, LINE_ID, STATION_ID = "PLANT1", "LINE1", "STATION-1"
CHANNEL_NAME = "vib_a"
FULL_SCALE_BY_STAT = {
    "mean": 10.0, "variance": 10.0, "skewness": 10.0, "kurtosis": 30.0, "rms": 10.0, "peak": 20.0, "crest": 5.0,
}

GEAR_R = compute_gear_orders(GEAR_LABEL, GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_dc_record_files(data_root: Path, test_run_id: str, signal, model_id: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = data_root / PLANT_ID / LINE_ID / day / test_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = run_dir / f"dc_{GEAR_LABEL}_{DIRECTION}.parquet"
    write_dc_parquet(
        parquet_path, signal.time_s, signal.rpm, signal.tach_pulse, {CHANNEL_NAME: signal.channels[CHANNEL_NAME]}
    )

    manifest = {"schema_version": CONTRACT_VERSION, "model_id": model_id}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return str(parquet_path)


def seed(data_root: Path, db_url: str, n_trials: int, seed_value: int) -> dict:
    engine = make_engine(db_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    rng = np.random.default_rng(seed_value)

    with session_factory() as session:
        session.merge(
            ModelRow(
                model_id=MODEL_ID,
                model_name="Nano 4 Speed",
                drive_teeth_json=json.dumps({GEAR_LABEL: 12}),
                idler_teeth_1_json=json.dumps({GEAR_LABEL: 36}),
                layshaft_teeth_json=json.dumps({GEAR_LABEL: 32}),
                ratios_json=json.dumps({GEAR_LABEL: 3.753}),
            )
        )
        session.commit()

        trial_stats = []
        for _ in range(n_trials):
            trial_signal = generate_dc_record(GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng)
            trial_stats.append(compute_stats(trial_signal.channels[CHANNEL_NAME]))
        masters = build_masters_from_trials(trial_stats, FULL_SCALE_BY_STAT)

        created_at = _now_iso()
        for stat_name, master in masters.items():
            session.add(
                MasterSignatureRow(
                    master_id=str(uuid.uuid4()),
                    model_id=MODEL_ID,
                    gear_label=GEAR_LABEL,
                    direction=DIRECTION,
                    stat_name=stat_name,
                    domain="time",
                    mean_value=master.mean_value,
                    band_min=master.band_min,
                    band_max=master.band_max,
                    full_scale=master.full_scale,
                    trial_count=master.trial_count,
                    created_at=created_at,
                )
            )
        session.commit()

        scenarios = [
            ("healthy-unit", None),
            ("crash-noise-unit", Fault(kind="crash_noise", start_s=2.0, end_s=2.3, amplitude=8.0)),
            ("slippage-unit", Fault(kind="slippage", start_s=1.0, end_s=3.0, drop_to=0.05)),
        ]

        seeded_runs = []
        for label, fault in scenarios:
            test_run_id = str(uuid.uuid4())
            dc_id = str(uuid.uuid4())
            serial_number = f"DEMO-{label.upper()}"

            session.add(
                TestRunRow(
                    test_run_id=test_run_id, model_id=MODEL_ID, serial_number=serial_number,
                    operator_id="demo", shift_number="A", repeat_number=1,
                    line_id=LINE_ID, station_id=STATION_ID, started_at=_now_iso(), overall_result="PENDING",
                )
            )

            signal = generate_dc_record(
                GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng,
                faults=[fault] if fault else None,
            )
            parquet_path = _write_dc_record_files(data_root, test_run_id, signal, MODEL_ID)

            session.add(
                DcRecordRow(
                    dc_id=dc_id, test_run_id=test_run_id, gear_label=GEAR_LABEL, direction=DIRECTION,
                    rpm_start=RPM_START, rpm_end=RPM_END, sample_rate_hz=SAMPLE_RATE_HZ,
                    parquet_path=parquet_path, result="PENDING", fail_reason_codes="",
                )
            )
            session.commit()

            result = analyze_dc_record(
                signal.channels[CHANNEL_NAME], signal.time_s, signal.rpm, SAMPLE_RATE_HZ,
                GEAR_LABEL, DIRECTION, GEAR_R, masters,
                crash_noise_band_hz=(500.0, 2000.0), crash_noise_threshold=0.5,
            )

            dc_row = session.get(DcRecordRow, dc_id)
            dc_row.result = "PASS" if result.passed else "FAIL"
            dc_row.fail_reason_codes = ",".join(result.fail_reason_codes)

            test_run_row = session.get(TestRunRow, test_run_id)
            test_run_row.overall_result = dc_row.result
            test_run_row.finished_at = _now_iso()

            if result.grading is not None:
                for stat_name, check in result.grading.per_stat.items():
                    session.add(
                        GradingResultRow(
                            dc_id=dc_id, stat_name=stat_name, domain="time",
                            g_level=check.g_level, ok_flag=check.ok_flag,
                        )
                    )

            recorded_at = _now_iso()
            for stat_name, value in stats_to_dict(result.stats).items():
                session.add(
                    SpcPointRow(
                        serial_number=serial_number, model_id=MODEL_ID, gear_label=GEAR_LABEL,
                        direction=DIRECTION, stat_name=stat_name, value=value, recorded_at=recorded_at,
                    )
                )

            session.commit()
            seeded_runs.append({"label": label, "test_run_id": test_run_id, "dc_id": dc_id, "result": dc_row.result})

        return {"model_id": MODEL_ID, "n_trials": n_trials, "runs": seeded_runs}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a demo NVH dataset (Parquet + DB rows)")
    parser.add_argument("--data-root", type=str, default="./data/nvh_demo")
    parser.add_argument("--db-url", type=str, default=None, help="defaults to sqlite:///<data-root>/nvh_demo.db")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    data_root = Path(args.data_root)
    data_root.mkdir(parents=True, exist_ok=True)
    db_url = args.db_url or f"sqlite:///{(data_root / 'nvh_demo.db').resolve()}"

    summary = seed(data_root, db_url, args.trials, args.seed)

    print(f"Seeded model {summary['model_id']} with {summary['n_trials']} master-building trials.")
    for run in summary["runs"]:
        print(f"  [{run['label']}] test_run_id={run['test_run_id']} dc_id={run['dc_id']} -> {run['result']}")
    print(f"\nData root: {data_root.resolve()}")
    print(f"DB URL:    {db_url}")


if __name__ == "__main__":
    main()
