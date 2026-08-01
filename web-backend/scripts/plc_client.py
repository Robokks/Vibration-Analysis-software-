"""Real Siemens S7 PLC reader. Polls one data block, publishes
`PlcStateUpdate` events on the shared ZMQ PUB port for the producer +
state machine to consume.

Prerequisites
-------------
1. Install the snap7 library: on Windows the `python-snap7` wheel bundles
   the DLL; on Linux install `libsnap7` system-wide (or place the .so on
   LD_LIBRARY_PATH).
2. `pip install -r requirements-plc.txt` in the repo-root venv.
3. The PLC exposes a DB laid out as (byte offsets configurable via
   flags):
       byte 0: nvh_cmd  (0=IDLE, 1=START, 2=STOP)
       byte 1: gear_id  (0..6)
       int  2: nvh_id   (INT16, big-endian; -1 sentinel = 0xFFFF)
       byte 4: final_log_trigger (0/1)

Usage:
    python web-backend/scripts/plc_client.py --plc-ip 192.168.0.1 --db-number 100
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time

import zmq

from nvh_api_schemas.realtime import PlcStateUpdate


_NVH_CMD_LOOKUP = {0: "IDLE", 1: "START", 2: "STOP"}


def _import_snap7():
    try:
        import snap7
    except ImportError as exc:
        print(
            "plc_client: the `python-snap7` package isn't installed.\n"
            "            Install with:  pip install -r requirements-plc.txt\n"
            "            (also requires the snap7 shared library from ni.com's\n"
            "            competitor snap7 project -- see the README).",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    return snap7


def _decode_db(buf: bytes) -> PlcStateUpdate:
    cmd_byte = buf[0]
    gear_id = buf[1]
    nvh_id_raw, = struct.unpack(">h", buf[2:4])  # signed INT16 big-endian
    trig = bool(buf[4])
    return PlcStateUpdate(
        nvh_cmd=_NVH_CMD_LOOKUP.get(cmd_byte, "IDLE"),
        gear_id=gear_id,
        nvh_id=nvh_id_raw,
        final_log_trigger=trig,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Siemens S7 -> ZMQ PLC bridge")
    parser.add_argument("--plc-ip", default=os.environ.get("NVH_PLC_IP", "192.168.0.1"))
    parser.add_argument("--rack", type=int, default=int(os.environ.get("NVH_PLC_RACK", "0")))
    parser.add_argument("--slot", type=int, default=int(os.environ.get("NVH_PLC_SLOT", "1")))
    parser.add_argument("--db-number", type=int, default=int(os.environ.get("NVH_PLC_DB", "100")))
    parser.add_argument("--start-byte", type=int, default=0)
    parser.add_argument("--length", type=int, default=5, help="Bytes to read (default 5)")
    parser.add_argument("--poll-hz", type=float, default=10.0)
    parser.add_argument(
        "--pub-url",
        default=os.environ.get("NVH_PLC_PUB_URL", "tcp://127.0.0.1:5556"),
        help="ZMQ PUB socket bind URL for PLC events (default: tcp://127.0.0.1:5556)",
    )
    args = parser.parse_args()

    snap7 = _import_snap7()

    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.PUB)
    socket.bind(args.pub_url)
    print(f"plc_client: PUB bound to {args.pub_url}", flush=True)

    # Phase O Bug 8: put connect() inside try so a failed initial connect
    # still runs the finally block (which closes the PUB socket + ctx),
    # not just db_read/loop exceptions. Also treat db_read errors as
    # reconnect signals rather than fatal -- transient PLC dropouts are
    # normal in an industrial network and shouldn't kill the producer.
    client = snap7.client.Client()
    period_s = 1.0 / max(0.1, args.poll_hz)
    last_json: str | None = None

    def _connect() -> bool:
        try:
            client.connect(args.plc_ip, args.rack, args.slot)
            print(
                f"plc_client: connected to {args.plc_ip}:{args.rack}/{args.slot}, "
                f"polling DB{args.db_number} @ {args.poll_hz:.1f} Hz",
                flush=True,
            )
            return True
        except Exception as exc:  # snap7 raises snap7.exceptions.Snap7Exception
            print(f"plc_client: connect failed: {exc}", file=sys.stderr, flush=True)
            return False

    try:
        # Initial connect. If it fails, don't spin -- exit cleanly with
        # exit code 2 so the launcher's row shows a crashed status and
        # the operator sees what happened.
        if not _connect():
            raise SystemExit(2)
        while True:
            try:
                buf = bytes(client.db_read(args.db_number, args.start_byte, args.length))
            except Exception as exc:  # noqa: BLE001
                print(f"plc_client: db_read failed ({exc}); attempting reconnect", file=sys.stderr, flush=True)
                try:
                    client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(1.0)
                if not _connect():
                    time.sleep(2.0)  # back off and retry on next iteration
                continue
            event = _decode_db(buf)
            payload = event.model_dump_json()
            # Only publish on change -- reduces WebSocket traffic and
            # matches how NvhStateMachine treats unchanged updates as
            # no-ops anyway.
            if payload != last_json:
                socket.send_string(payload)
                last_json = payload
                print(
                    f"plc_client: cmd={event.nvh_cmd} gear_id={event.gear_id} "
                    f"nvh_id={event.nvh_id} final={event.final_log_trigger}",
                    flush=True,
                )
            time.sleep(period_s)
    except KeyboardInterrupt:
        print("plc_client: shutting down", flush=True)
    finally:
        # Best-effort cleanup; each step guarded so one failure doesn't
        # skip the rest.
        try:
            client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        try:
            socket.close(linger=0)
        except Exception:  # noqa: BLE001
            pass
        try:
            ctx.term()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
