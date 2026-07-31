"""Live-Display producer backed by NI-DAQmx (real hardware or a
NI MAX simulated device). Publishes the same three schemas over the
same ZMQ PUB URL as ``live_simulator.py``, so the FastAPI relay + GUI
clients don't know or care which producer is running.

Prerequisites
-------------
1. Install the NI-DAQmx driver from ni.com (Windows only for the
   simulated-device workflow; Linux support exists but the simulated
   device path lives in NI MAX which is Windows).
2. In NI MAX, right-click "Devices and Interfaces" -> "Create New..."
   -> "Simulated NI-DAQmx Device or Modular Instrument", pick something
   like an NI 9234 (dynamic-signal-acquisition, 4-ch, IEPE) and give it
   a name (default "cDAQ1Mod1" or "Dev1").
3. `pip install -r requirements-daq.txt` in the repo-root venv.

Usage
-----
    python web-backend/scripts/live_daq.py --device Dev1 --channel ai0

Every 4 seconds it starts a synthetic "test run" (LiveTestRunUpdate),
streams the acquired samples in 100 ms LiveSignalChunk messages with a
synthesised RPM ramp (1000 -> 2500 RPM linear over the run -- an
NI MAX simulated device has no tacho, so this keeps downstream order-
tracking code fed with valid RPMs), then emits a LiveDcUpdate with a
placeholder PASS stamp. Real analysis/grading is a follow-up.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

import numpy as np
import zmq

from nvh_api_schemas.realtime import LiveDcUpdate, LiveSignalChunk, LiveTestRunUpdate

# Keep these in lockstep with live_simulator.py -- same virtual station,
# same channel labels, so a downstream client can flip between producers
# without any re-config.
MODEL_ID = "MODEL-A"
GEAR_LABEL = "R"
DIRECTION = "RU"
STATION_ID = "STATION-1"
CHANNEL_NAME = "vib_a"
RPM_START, RPM_END = 1000.0, 2500.0
DURATION_S = 4.0
IDLE_BETWEEN_RUNS_S = 1.0


def _send(socket: zmq.Socket, event) -> None:
    socket.send_string(event.model_dump_json())


def _import_nidaqmx():
    try:
        import nidaqmx
        from nidaqmx.constants import AcquisitionType

        return nidaqmx, AcquisitionType
    except ImportError as exc:
        print(
            "live_daq: the `nidaqmx` package isn't installed.\n"
            "         Install with:  pip install -r requirements-daq.txt\n"
            "         (requires the NI-DAQmx driver from ni.com; on Windows,\n"
            "         create a simulated device in NI MAX first.)",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


def _emit_run(
    socket: zmq.Socket,
    task,
    sample_rate_hz: float,
    chunk_samples: int,
    n_chunks: int,
) -> None:
    test_run_id = str(uuid.uuid4())
    dc_id = str(uuid.uuid4())

    _send(socket, LiveTestRunUpdate(test_run_id=test_run_id, station_id=STATION_ID, status="RUNNING"))

    total_samples = n_chunks * chunk_samples
    rpm_ramp = np.linspace(RPM_START, RPM_END, total_samples, dtype=np.float64)

    for chunk_index in range(n_chunks):
        raw = task.read(number_of_samples_per_channel=chunk_samples)
        # task.read returns a Python list for a single channel or a nested
        # list for multi-channel. We only read one channel, so raw is a
        # flat list of floats.
        values = np.asarray(raw, dtype=np.float64)
        t0 = chunk_index * chunk_samples / sample_rate_hz
        time_s = (t0 + np.arange(chunk_samples) / sample_rate_hz).tolist()
        rpm_slice = rpm_ramp[chunk_index * chunk_samples : (chunk_index + 1) * chunk_samples].tolist()

        _send(socket, LiveSignalChunk(
            test_run_id=test_run_id,
            dc_id=dc_id,
            station_id=STATION_ID,
            gear_label=GEAR_LABEL,
            direction=DIRECTION,
            channel_name=CHANNEL_NAME,
            sample_rate_hz=sample_rate_hz,
            chunk_index=chunk_index,
            time_s=time_s,
            values=values.tolist(),
            rpm=rpm_slice,
        ))

    _send(socket, LiveDcUpdate(
        dc_id=dc_id,
        test_run_id=test_run_id,
        station_id=STATION_ID,
        gear_label=GEAR_LABEL,
        direction=DIRECTION,
        stamp="PASS",
        fail_reason_codes=[],
    ))
    _send(socket, LiveTestRunUpdate(
        test_run_id=test_run_id, station_id=STATION_ID, status="COMPLETED", overall_result="PASS",
    ))
    print(f"live_daq: run {test_run_id[:8]}... completed", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish NI-DAQmx samples over ZMQ (drop-in for live_simulator.py)")
    parser.add_argument("--device", default=os.environ.get("NVH_DAQ_DEVICE", "Dev1"),
                        help="NI-DAQmx device name (default: Dev1 or $NVH_DAQ_DEVICE)")
    parser.add_argument("--channel", default=os.environ.get("NVH_DAQ_CHANNEL", "ai0"),
                        help="Analog-input channel (default: ai0 or $NVH_DAQ_CHANNEL)")
    parser.add_argument("--sample-rate", type=float,
                        default=float(os.environ.get("NVH_DAQ_SAMPLE_RATE", "5000")),
                        help="Sample rate in Hz (default: 5000)")
    parser.add_argument("--min-volt", type=float, default=-10.0)
    parser.add_argument("--max-volt", type=float, default=10.0)
    parser.add_argument(
        "--pub-url",
        default=os.environ.get("NVH_LIVE_PUB_URL", "tcp://127.0.0.1:5555"),
        help="ZMQ PUB socket bind URL (default: tcp://127.0.0.1:5555 or $NVH_LIVE_PUB_URL)",
    )
    args = parser.parse_args()

    nidaqmx, AcquisitionType = _import_nidaqmx()

    chunk_samples = int(args.sample_rate * 0.1)
    n_chunks = int(round(DURATION_S / 0.1))

    context = zmq.Context.instance()
    socket = context.socket(zmq.PUB)
    socket.bind(args.pub_url)
    print(f"live_daq: PUB bound to {args.pub_url}", flush=True)

    physical = f"{args.device}/{args.channel}"

    try:
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(
                physical, min_val=args.min_volt, max_val=args.max_volt,
            )
            task.timing.cfg_samp_clk_timing(
                rate=args.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=chunk_samples * 4,
            )
            task.start()
            print(
                f"live_daq: acquiring from {physical} @ {args.sample_rate:.0f} Hz "
                f"({chunk_samples} samples/chunk, {n_chunks} chunks/run)",
                flush=True,
            )

            while True:
                _emit_run(socket, task, args.sample_rate, chunk_samples, n_chunks)
                time.sleep(IDLE_BETWEEN_RUNS_S)
    except KeyboardInterrupt:
        print("live_daq: shutting down", flush=True)
    finally:
        socket.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
