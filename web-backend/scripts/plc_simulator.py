"""No-hardware alternative to `plc_client.py`. Publishes a scripted
sequence of `PlcStateUpdate` events on the shared ZMQ PUB port so the
producer + Qt live display can be exercised end-to-end without any
Siemens PLC hooked up.

The scripted sequence mirrors the three scenarios the old fake
producer used to loop (healthy / crash-noise / slippage): each is a
short RunUp cycle in gear R (gear_id=1, nvh_id=0), ending with a
final-log trigger, followed by an IDLE cool-down. Loops indefinitely.

Usage:
    python web-backend/scripts/plc_simulator.py --pub-url tcp://127.0.0.1:5555
"""

from __future__ import annotations

import argparse
import os
import time

import zmq

from nvh_api_schemas.realtime import PlcStateUpdate


# Each row: (nvh_cmd, gear_id, nvh_id, final_log_trigger, hold_seconds).
# Loop invariant: the final_log_trigger only rises for one tick per run
# so consumers see a clean rising edge (matches NvhStateMachine's
# rising-edge detection).
SCRIPTED_SEQUENCE: list[tuple[str, int, int, bool, float]] = [
    ("IDLE", -1, -1, False, 0.5),   # cool-down / initial
    ("START", 1, 0, False, 4.0),    # RunUp in R gear (nvh_id 0)
    ("START", 1, 1, False, 3.0),    # Steady-state drive
    ("START", 1, 3, False, 4.0),    # RunDown
    ("START", 1, 0, True, 0.2),     # final-log trigger rising edge
    ("STOP", 1, -1, False, 0.5),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="PLC simulator: scripted PlcStateUpdate over ZMQ PUB")
    parser.add_argument(
        "--pub-url",
        default=os.environ.get("NVH_PLC_PUB_URL", "tcp://127.0.0.1:5556"),
        help="ZMQ PUB socket bind URL for PLC events "
             "(default: tcp://127.0.0.1:5556 or $NVH_PLC_PUB_URL -- "
             "distinct from the signal producer's 5555 so both can PUB in parallel)",
    )
    parser.add_argument("--speed", type=float,
                        default=float(os.environ.get("NVH_PLC_SPEED", "1.0")),
                        help="Time multiplier for the scripted holds (default 1.0 or $NVH_PLC_SPEED)")
    parser.add_argument("--once", action="store_true",
                        help="Run the sequence once and exit (default: loop forever)")
    args = parser.parse_args()

    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.PUB)
    socket.bind(args.pub_url)
    print(f"plc_simulator: PUB bound to {args.pub_url}", flush=True)

    try:
        while True:
            for nvh_cmd, gear_id, nvh_id, trig, hold_s in SCRIPTED_SEQUENCE:
                event = PlcStateUpdate(
                    nvh_cmd=nvh_cmd, gear_id=gear_id, nvh_id=nvh_id,
                    final_log_trigger=trig,
                )
                socket.send_string(event.model_dump_json())
                print(
                    f"plc_simulator: cmd={nvh_cmd} gear_id={gear_id} "
                    f"nvh_id={nvh_id} final={trig}",
                    flush=True,
                )
                time.sleep(hold_s * args.speed)
            if args.once:
                break
    except KeyboardInterrupt:
        print("plc_simulator: shutting down", flush=True)
    finally:
        socket.close(linger=0)
        ctx.term()


if __name__ == "__main__":
    main()
