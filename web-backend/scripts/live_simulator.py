"""Live-Display producer: publishes LiveEvent payloads on a ZeroMQ PUB
socket for the FastAPI backend to relay into `/live/ws`. Runs in one
of two modes:

- **Auto mode** (default -- no `--plc-url`): loops a canned sequence of
  three scenarios (healthy / crash-noise / slippage), matching the old
  behaviour. Useful for the pre-Phase-F demo.

- **PLC-driven mode** (`--plc-url tcp://127.0.0.1:5556`): subscribes to a
  PLC PUB socket that publishes `PlcStateUpdate` events (see
  `plc_simulator.py` / `plc_client.py`). Feeds them through an
  `NvhStateMachine`; only emits signal chunks + TDMS while
  `log_active`; opens/closes test-run + DC records on RUN_STARTED /
  RUN_STOPPED / FINAL_LOG_REQUESTED transitions.

Usage:
    python web-backend/scripts/live_simulator.py --pub-url tcp://127.0.0.1:5555
    python web-backend/scripts/live_simulator.py --plc-url tcp://127.0.0.1:5556
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import zmq

from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
import json as _json
import urllib.request as _urlreq

from nvh_api_schemas.realtime import (
    LiveDcUpdate,
    LiveSignalChunk,
    LiveTestRunUpdate,
    PlcStateUpdate,
)
from nvh_contract.calibration import scale_v_to_eu
from nvh_contract.paths import raw_tdms_path
from nvh_contract.state import NvhStateMachine, Transition
from nvh_simulator.faults import Fault
from nvh_simulator.generators import generate_dc_record


def _open_tdms_writer(path: str):
    """Return an nptdms.TdmsWriter for the resolved path, or None if the
    optional nptdms package isn't installed (prints one clear line and
    keeps the sim running -- TDMS is a nice-to-have, not a hard dep)."""
    try:
        from nptdms import TdmsWriter  # noqa: WPS433 (deferred import by design)
    except ImportError:
        print(
            "live_simulator: --tdms-path requested but `nptdms` isn't installed. "
            "Install with `pip install -r requirements-daq.txt` and re-run. "
            "Continuing without TDMS logging.",
            file=sys.stderr, flush=True,
        )
        return None
    resolved = path.replace("{ts}", time.strftime("%Y%m%d_%H%M%S", time.gmtime()))
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    writer = TdmsWriter(resolved)
    writer.open()
    print(f"live_simulator: TDMS logging -> {resolved}", flush=True)
    return writer


def _write_tdms_chunk(writer, values, rpm, sample_rate_hz: float, channel_name: str) -> None:
    from nptdms import ChannelObject, RootObject, GroupObject  # noqa: WPS433

    props = {"wf_start_offset": 0.0, "wf_increment": 1.0 / sample_rate_hz, "unit_string": "V"}
    writer.write_segment([
        RootObject(properties={"producer": "live_simulator"}),
        GroupObject("acquisition"),
        ChannelObject("acquisition", channel_name, np.asarray(values, dtype=np.float64), properties=props),
        ChannelObject("acquisition", "rpm", np.asarray(rpm, dtype=np.float64), properties={"unit_string": "RPM"}),
    ])


# Kept in sync with web-backend/scripts/seed_demo_data.py.
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


# -----------------------------------------------------------------------
# Auto-mode (legacy) implementation -- unchanged behaviour when --plc-url
# isn't set.
# -----------------------------------------------------------------------


def _emit_scenario(socket: zmq.Socket, label: str, fault: Fault | None, stamp: str, fail_reason_codes: list[str], tdms_writer=None) -> None:
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
        if tdms_writer is not None:
            _write_tdms_chunk(tdms_writer, values[start:end], rpm[start:end], SAMPLE_RATE_HZ, CHANNEL_NAME)
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


def _run_auto_mode(socket: zmq.Socket, tdms_writer) -> None:
    while True:
        for label, fault, stamp, codes in SCENARIOS:
            _emit_scenario(socket, label, fault, stamp, codes, tdms_writer=tdms_writer)
            time.sleep(IDLE_BETWEEN_RUNS_S)


# -----------------------------------------------------------------------
# PLC-driven mode -- new in Phase F. State machine gates every chunk.
# -----------------------------------------------------------------------


def _synth_chunk(gear_label: str, chunk_index: int, sample_rate_hz: float, rng) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Produces a 100 ms slice of a synthetic gear-mesh signal keyed on
    `chunk_index`. This is per-chunk-fresh (not sliced from a longer
    pre-generated waveform) so a state-machine-driven producer never
    has to worry about run boundaries."""
    t0 = chunk_index * CHUNK_SAMPLES / sample_rate_hz
    time_s = t0 + np.arange(CHUNK_SAMPLES) / sample_rate_hz
    # Fixed sim RPM in PLC-driven mode; real ramps come from the DAQ
    # producer's counter task once Phase G lands.
    rpm_current = 1500.0
    freq_1x = rpm_current / 60.0
    values = 0.5 * np.sin(2 * np.pi * freq_1x * time_s) + 0.05 * rng.standard_normal(CHUNK_SAMPLES)
    rpm = np.full(CHUNK_SAMPLES, rpm_current, dtype=np.float64)
    return time_s, values, rpm


def _open_rollover_writer(base_dir: str | None, trial_no: int, gear_id: int, nvh_id: int, model_id: str, serial_no: str, serial_rpt: int):
    """Open a per-(gear_id, nvh_id) TDMS file under `base_dir` using the
    nested layout, or None if base_dir isn't configured OR the
    (gear_id, nvh_id) says "don't log" (either sentinel < 0)."""
    if not base_dir:
        return None
    if gear_id < 0 or nvh_id < 0:
        return None
    try:
        from nptdms import TdmsWriter  # noqa: WPS433
    except ImportError:
        print(
            "live_simulator: TDMS rollover requested but `nptdms` isn't installed. "
            "Install with `pip install -r requirements-daq.txt` to enable per-transition logging.",
            file=sys.stderr, flush=True,
        )
        return None
    path = raw_tdms_path(
        base_dir=base_dir, model_id=model_id, serial_no=serial_no,
        serial_rpt=serial_rpt, trial_no=trial_no,
        gear_id=gear_id, nvh_id=nvh_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = TdmsWriter(str(path))
    writer.open()
    print(f"live_simulator: TDMS rollover -> {path}", flush=True)
    return writer


def _post_summary(backend_url: str, body: dict) -> None:
    """Fire-and-forget POST to /summaries. Best-effort -- a summary
    persistence failure must not kill the producer (the live stream is
    the real deliverable). Prints one line on error and moves on."""
    try:
        payload = _json.dumps(body).encode("utf-8")
        req = _urlreq.Request(
            f"{backend_url.rstrip('/')}/summaries",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _urlreq.urlopen(req, timeout=1.5) as resp:
            resp.read()
    except Exception as exc:
        print(f"live_simulator: summary POST failed: {exc}", file=sys.stderr, flush=True)


def _run_plc_driven_mode(
    socket: zmq.Socket,
    plc_url: str,
    tdms_writer,
    *,
    sensor_sensitivity_mv_per_eu: float = 1000.0,
    pregain_db: float = 0.0,
    rollover_base_dir: str | None = None,
    model_id: str = MODEL_ID,
    serial_no: str = "SN-DEMO",
    serial_rpt: int = 1,
    backend_url: str | None = None,
) -> None:
    ctx = zmq.Context.instance()
    plc_sub = ctx.socket(zmq.SUB)
    plc_sub.connect(plc_url)
    plc_sub.setsockopt_string(zmq.SUBSCRIBE, "")
    poller = zmq.Poller()
    poller.register(plc_sub, zmq.POLLIN)

    print(f"live_simulator: SUB {plc_url} for PLC state; chunks gated on log_active", flush=True)

    sm = NvhStateMachine()
    rng = np.random.default_rng()
    active_test_run_id: str | None = None
    active_dc_id: str | None = None
    chunk_index = 0
    next_chunk_at = time.monotonic()

    # Per-(gear_id, nvh_id) rollover writer -- opens on transition,
    # closes when a new one takes over. `tdms_writer` (the legacy
    # single-file --tdms-path writer) still receives every chunk when
    # rollover_base_dir is None.
    rollover_writer = None
    rollover_key: tuple[int, int] | None = None

    def _switch_rollover_writer(gear_id: int, nvh_id: int) -> None:
        nonlocal rollover_writer, rollover_key
        if rollover_writer is not None:
            rollover_writer.close()
            rollover_writer = None
        rollover_key = (gear_id, nvh_id)
        rollover_writer = _open_rollover_writer(
            rollover_base_dir, sm.trial_no, gear_id, nvh_id,
            model_id, serial_no, serial_rpt,
        )

    while True:
        # Non-blocking-ish poll: wait until it's time for the next chunk,
        # but also wake early on incoming PLC events.
        now = time.monotonic()
        wait_ms = max(0, int((next_chunk_at - now) * 1000))
        events = dict(poller.poll(timeout=wait_ms))

        if plc_sub in events:
            payload = plc_sub.recv_string()
            update = PlcStateUpdate.model_validate_json(payload)
            transitions = sm.apply(update)
            for t in transitions:
                if t == Transition.RUN_STARTED:
                    active_test_run_id = str(uuid.uuid4())
                    active_dc_id = str(uuid.uuid4())
                    chunk_index = 0
                    _send(socket, LiveTestRunUpdate(
                        test_run_id=active_test_run_id, station_id=STATION_ID, status="RUNNING",
                    ))
                    _switch_rollover_writer(sm.gear_id, sm.nvh_id)
                    print(f"live_simulator: RUN_STARTED test_run_id={active_test_run_id[:8]} trial={sm.trial_no}", flush=True)
                elif t in (Transition.GEAR_CHANGED, Transition.NVH_ID_CHANGED):
                    _switch_rollover_writer(sm.gear_id, sm.nvh_id)
                elif t == Transition.FINAL_LOG_REQUESTED:
                    if active_dc_id and sm.gear_label and sm.direction:
                        _send(socket, LiveDcUpdate(
                            dc_id=active_dc_id,
                            test_run_id=active_test_run_id or active_dc_id,
                            station_id=STATION_ID,
                            gear_label=sm.gear_label,
                            direction=sm.direction,
                            stamp="PASS",  # producer doesn't grade; downstream does
                            fail_reason_codes=[],
                        ))
                        print(f"live_simulator: FINAL_LOG_REQUESTED dc_id={active_dc_id[:8]}", flush=True)
                        if backend_url:
                            _post_summary(backend_url, {
                                "test_run_id": active_test_run_id or active_dc_id,
                                "dc_id": active_dc_id,
                                "model_id": model_id,
                                "serial_no": serial_no,
                                "serial_rpt": serial_rpt,
                                "gear_id": sm.gear_id,
                                "nvh_id": sm.nvh_id,
                                "stamp": "PASS",
                                "fail_reason_codes": [],
                            })
                elif t == Transition.RUN_STOPPED:
                    if active_test_run_id:
                        _send(socket, LiveTestRunUpdate(
                            test_run_id=active_test_run_id, station_id=STATION_ID,
                            status="COMPLETED", overall_result="PASS",
                        ))
                        print(f"live_simulator: RUN_STOPPED test_run_id={active_test_run_id[:8]}", flush=True)
                    active_test_run_id = None
                    active_dc_id = None
                    if rollover_writer is not None:
                        rollover_writer.close()
                        rollover_writer = None
                        rollover_key = None

        # Time-slice: emit a chunk if we're actively logging.
        if time.monotonic() >= next_chunk_at:
            if sm.log_active and active_test_run_id and active_dc_id and sm.gear_label and sm.direction:
                time_s, values_v, rpm = _synth_chunk(sm.gear_label, chunk_index, SAMPLE_RATE_HZ, rng)
                # Calibration scaling raw V -> EU. Identity by default.
                values_eu = scale_v_to_eu(values_v, sensor_sensitivity_mv_per_eu, pregain_db)
                values_list = values_eu.tolist()
                _send(socket, LiveSignalChunk(
                    test_run_id=active_test_run_id,
                    dc_id=active_dc_id,
                    station_id=STATION_ID,
                    gear_label=sm.gear_label,
                    direction=sm.direction,
                    channel_name=CHANNEL_NAME,
                    sample_rate_hz=SAMPLE_RATE_HZ,
                    chunk_index=chunk_index,
                    time_s=time_s.tolist(),
                    values=values_list,
                    rpm=rpm.tolist(),
                    channels={CHANNEL_NAME: values_list},
                ))
                if tdms_writer is not None:
                    _write_tdms_chunk(tdms_writer, values_eu, rpm, SAMPLE_RATE_HZ, CHANNEL_NAME)
                if rollover_writer is not None:
                    _write_tdms_chunk(rollover_writer, values_eu, rpm, SAMPLE_RATE_HZ, CHANNEL_NAME)
                chunk_index += 1
            next_chunk_at += CHUNK_PERIOD_S


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish live NVH events over a ZMQ PUB socket")
    parser.add_argument(
        "--pub-url",
        default=os.environ.get("NVH_LIVE_PUB_URL", "tcp://127.0.0.1:5555"),
        help="ZMQ PUB socket bind URL (default: tcp://127.0.0.1:5555 or $NVH_LIVE_PUB_URL)",
    )
    parser.add_argument(
        "--plc-url",
        default=os.environ.get("NVH_PLC_PUB_URL", ""),
        help="ZMQ SUB URL of the PLC event producer. If set, the producer "
             "runs in PLC-driven mode and gates chunk emission on the "
             "state machine. If unset, runs the legacy scenarios loop.",
    )
    parser.add_argument(
        "--tdms-path",
        default=os.environ.get("NVH_LIVE_TDMS_PATH", ""),
        help="Optional TDMS output path (see requirements-daq.txt).",
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=float(os.environ.get("NVH_LIVE_SENSITIVITY_MV_PER_EU", "1000.0")),
        help="Sensor sensitivity in mV per engineering unit "
             "(default 1000.0 = identity V->EU scaling; "
             "100.0 for a typical 100 mV/g accelerometer).",
    )
    parser.add_argument(
        "--pregain-db",
        type=float,
        default=float(os.environ.get("NVH_LIVE_PREGAIN_DB", "0.0")),
        help="Pre-amp gain applied before the ADC in dB (default 0 dB).",
    )
    parser.add_argument(
        "--raw-dir",
        default=os.environ.get("NVH_RAW_DIR", ""),
        help="If set, PLC-driven mode opens a new TDMS file per "
             "(gear_id, nvh_id) transition under this base directory "
             "(nested as YYYY/MM/DD/TrialN/model/serial_rpt/). "
             "Setting this is independent of --tdms-path; they can coexist.",
    )
    parser.add_argument("--model-id", default=os.environ.get("NVH_MODEL_ID", "MODEL-A"),
                        help="Model id used in the raw-dir path (default MODEL-A).")
    parser.add_argument("--serial-no", default=os.environ.get("NVH_SERIAL_NO", "SN-DEMO"),
                        help="Serial number used in the raw-dir path (default SN-DEMO).")
    parser.add_argument("--serial-rpt", type=int,
                        default=int(os.environ.get("NVH_SERIAL_RPT", "1")),
                        help="Serial repeat counter used in the raw-dir path (default 1).")
    parser.add_argument("--backend-url",
                        default=os.environ.get("NVH_BACKEND_URL", ""),
                        help="If set, POST a summary row here on every "
                             "FINAL_LOG_REQUESTED transition (Phase J). "
                             "E.g. http://localhost:8000")
    args = parser.parse_args()

    context = zmq.Context.instance()
    socket = context.socket(zmq.PUB)
    socket.bind(args.pub_url)
    print(f"live_simulator: PUB bound to {args.pub_url}", flush=True)

    tdms_writer = _open_tdms_writer(args.tdms_path) if args.tdms_path else None

    try:
        if args.plc_url:
            _run_plc_driven_mode(
                socket, args.plc_url, tdms_writer,
                sensor_sensitivity_mv_per_eu=args.sensitivity,
                pregain_db=args.pregain_db,
                rollover_base_dir=args.raw_dir or None,
                model_id=args.model_id,
                serial_no=args.serial_no,
                serial_rpt=args.serial_rpt,
                backend_url=args.backend_url or None,
            )
        else:
            _run_auto_mode(socket, tdms_writer)
    except KeyboardInterrupt:
        print("live_simulator: shutting down", flush=True)
    finally:
        if tdms_writer is not None:
            tdms_writer.close()
        socket.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
