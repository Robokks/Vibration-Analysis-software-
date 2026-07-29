"""Live-Display producer: continuously simulates test runs and publishes
LiveEvent payloads on a ZeroMQ PUB socket for the FastAPI backend to relay
into `/live/ws`. This is the "acquisition" stand-in used until the LabVIEW
producer exists — same schema shapes (`nvh_api_schemas.realtime`), same
transport, so the backend relay is developed against a stable interface.

Usage:
    python web-backend/scripts/live_simulator.py --pub-url tcp://127.0.0.1:5555
"""

from __future__ import annotations

import argparse
import os
import time
import uuid

import numpy as np
import zmq

from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from nvh_api_schemas.realtime import LiveDcUpdate, LiveSignalChunk, LiveTestRunUpdate
from nvh_simulator.faults import Fault
from nvh_simulator.generators import generate_dc_record

# Kept in sync with web-backend/scripts/seed_demo_data.py — the persisted demo
# dataset and the live stream describe the same virtual station, so any
# receiver treating the stream as ground truth stays consistent with the DB.
MODEL_ID = "MODEL-A"
GEAR_LABEL = "R"
DIRECTION = "RU"
SAMPLE_RATE_HZ = 5000.0
RPM_START, RPM_END = 1000.0, 2500.0
DURATION_S = 4.0
STATION_ID = "STATION-1"
CHANNEL_NAME = "vib_a"
GEAR_R = compute_gear_orders(GEAR_LABEL, GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)

CHUNK_SAMPLES = int(SAMPLE_RATE_HZ * 0.1)  # 100ms per chunk
CHUNK_PERIOD_S = 0.1
IDLE_BETWEEN_RUNS_S = 1.0

SCENARIOS: list[tuple[str, Fault | None, str, list[str]]] = [
    ("healthy-unit", None, "PASS", []),
    ("crash-noise-unit", Fault(kind="crash_noise", start_s=2.0, end_s=2.3, amplitude=8.0), "FAIL", ["CRASH_NOISE"]),
    ("slippage-unit", Fault(kind="slippage", start_s=1.0, end_s=3.0, drop_to=0.05), "FAIL", ["SLIPPAGE"]),
]


def _send(socket: zmq.Socket, event) -> None:
    socket.send_string(event.model_dump_json())


def _emit_scenario(socket: zmq.Socket, label: str, fault: Fault | None, stamp: str, fail_reason_codes: list[str]) -> None:
    test_run_id = str(uuid.uuid4())
    dc_id = str(uuid.uuid4())
    rng = np.random.default_rng()

    signal = generate_dc_record(
        GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ,
        rng=rng, faults=[fault] if fault else None,
    )
    values = signal.channels[CHANNEL_NAME]
    time_s = signal.time_s
    rpm = signal.rpm
    n_chunks = (len(values) + CHUNK_SAMPLES - 1) // CHUNK_SAMPLES

    print(f"[{label}] test_run_id={test_run_id} publishing {n_chunks} chunks...", flush=True)

    _send(socket, LiveTestRunUpdate(
        test_run_id=test_run_id, station_id=STATION_ID, status="RUNNING",
    ))

    for chunk_index in range(n_chunks):
        start = chunk_index * CHUNK_SAMPLES
        end = start + CHUNK_SAMPLES
        _send(socket, LiveSignalChunk(
            test_run_id=test_run_id,
            dc_id=dc_id,
            station_id=STATION_ID,
            gear_label=GEAR_LABEL,
            direction=DIRECTION,
            channel_name=CHANNEL_NAME,
            sample_rate_hz=SAMPLE_RATE_HZ,
            chunk_index=chunk_index,
            time_s=time_s[start:end].tolist(),
            values=values[start:end].tolist(),
            rpm=rpm[start:end].tolist(),
        ))
        time.sleep(CHUNK_PERIOD_S)

    _send(socket, LiveDcUpdate(
        dc_id=dc_id,
        test_run_id=test_run_id,
        station_id=STATION_ID,
        gear_label=GEAR_LABEL,
        direction=DIRECTION,
        stamp=stamp,
        fail_reason_codes=fail_reason_codes,
    ))
    _send(socket, LiveTestRunUpdate(
        test_run_id=test_run_id, station_id=STATION_ID, status="COMPLETED", overall_result=stamp,
    ))

    print(f"[{label}] -> {stamp}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish live NVH events over a ZMQ PUB socket")
    parser.add_argument(
        "--pub-url",
        default=os.environ.get("NVH_LIVE_PUB_URL", "tcp://127.0.0.1:5555"),
        help="ZMQ PUB socket bind URL (default: tcp://127.0.0.1:5555 or $NVH_LIVE_PUB_URL)",
    )
    args = parser.parse_args()

    context = zmq.Context.instance()
    socket = context.socket(zmq.PUB)
    socket.bind(args.pub_url)
    print(f"live_simulator: PUB bound to {args.pub_url}", flush=True)

    try:
        while True:
            for label, fault, stamp, codes in SCENARIOS:
                _emit_scenario(socket, label, fault, stamp, codes)
                time.sleep(IDLE_BETWEEN_RUNS_S)
    except KeyboardInterrupt:
        print("live_simulator: shutting down", flush=True)
    finally:
        socket.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
