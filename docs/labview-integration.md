# LabVIEW integration: acquisition producer contract

This document describes the wire contract the LabVIEW acquisition
application implements to plug into the Python NVH stack. The Python
`live_daq.py` / `live_simulator.py` producers in this repo are
reference implementations of the same contract; a LabVIEW app can
replace either (or both) without any downstream changes.

## Transport

Two ZeroMQ PUB sockets on the acquisition machine. Downstream (the
FastAPI backend, Qt live client, web client) all subscribe via the
backend's `/live/ws` WebSocket relay, which is fed by internal ZMQ
SUBs on both ports.

| Purpose | Default bind URL | Env override |
|---|---|---|
| Signal + test-run + DC events | `tcp://127.0.0.1:5555` | `$NVH_LIVE_PUB_URL` |
| PLC state events | `tcp://127.0.0.1:5556` | `$NVH_PLC_PUB_URL` |

Every message is a JSON object serialised as a UTF-8 string (ZMQ
`send_string`). All events carry a `type` discriminator on the
top-level object -- the same tagged-union convention `pydantic`
discrimination uses in `libs/nvh_api_schemas/src/nvh_api_schemas/realtime.py`.

## Event schemas

All schemas live in `libs/nvh_api_schemas/src/nvh_api_schemas/realtime.py`
as pydantic `BaseModel`s. The JSON shape is exactly `model_dump_json()`
of each type. Field names below match the Python attribute names
verbatim.

### `LiveTestRunUpdate`

Marks a run's lifecycle (open on RUN_STARTED, close on RUN_STOPPED).
The LabVIEW app is expected to emit exactly one RUNNING and one
COMPLETED per PLC-triggered run cycle.

```json
{
  "type": "test_run",
  "test_run_id": "cd6f...uuid",
  "station_id": "STATION-1",
  "status": "RUNNING",
  "overall_result": null
}
```

Fields:
- `type: "test_run"`
- `test_run_id: string` (uuid recommended; must be stable across the same run)
- `station_id: string`
- `status: "RUNNING" | "COMPLETED"`
- `overall_result: "PASS" | "FAIL" | null` (null on RUNNING; the
  stamp on COMPLETED)

### `LiveSignalChunk`

100 ms slice of the current DC record. Emitted at wall-clock pace
while `log_active` (PLC nvh_cmd == START and nvh_id != -1).

```json
{
  "type": "signal_chunk",
  "test_run_id": "cd6f...uuid",
  "dc_id": "8f92...uuid",
  "station_id": "STATION-1",
  "gear_label": "R",
  "direction": "RU",
  "channel_name": "vib_a",
  "sample_rate_hz": 5000.0,
  "chunk_index": 42,
  "time_s": [0.0, 0.0002, ...],
  "values": [0.11, -0.09, ...],
  "rpm": [1503.0, 1503.1, ...],
  "channels": {"vib_a": [0.11, -0.09, ...], "mic": [0.02, 0.03, ...]}
}
```

Fields:
- `type: "signal_chunk"`
- `test_run_id`, `dc_id`, `station_id`
- `gear_label: string` (matches gear_ids.py: N/R/I/II/III/IV/V)
- `direction: "RU" | "STYD" | "STYC" | "RD"` (see nvh_id mapping below)
- `channel_name: string` -- the primary channel name (== the first
  key in `channels`)
- `sample_rate_hz: float`
- `chunk_index: int` (monotonic per run; consumers reassemble the
  ordering by this, not by delivery order)
- `time_s: list[float]`, `values: list[float]`, `rpm: list[float]`
  -- three arrays of the same length. `values` is the primary
  channel, in engineering units *after* calibration has been applied
  producer-side (see `nvh_contract.calibration.scale_v_to_eu`).
- `channels: dict[str, list[float]]` -- multi-channel map, always
  contains the primary channel; may contain additional channels
  (e.g. `mic`) if the acquisition config includes them.

### `LiveDcUpdate`

One per DC record on FINAL_LOG_REQUESTED. Downstream uses the
`stamp` to color the (gear x direction) grid in Live Display; the
same event triggers the summary-DB POST from the producer.

```json
{
  "type": "dc",
  "dc_id": "8f92...uuid",
  "test_run_id": "cd6f...uuid",
  "station_id": "STATION-1",
  "gear_label": "R",
  "direction": "RU",
  "stamp": "PASS",
  "fail_reason_codes": []
}
```

### `PlcStateUpdate` (PLC PUB port only)

Snapshot of the PLC data-block state. The LabVIEW acquisition app
usually consumes these rather than emitting them; the separate
`plc_client.py` / `plc_simulator.py` producers own that side.

```json
{
  "type": "plc_state",
  "nvh_cmd": "START",
  "gear_id": 1,
  "nvh_id": 0,
  "final_log_trigger": false
}
```

Fields:
- `type: "plc_state"`
- `nvh_cmd: "START" | "STOP" | "IDLE"`
- `gear_id: int` -- see mapping below
- `nvh_id: int` -- see mapping below
- `final_log_trigger: bool` -- rising-edge triggers the summary
  persistence pipeline

## Enumeration mappings

Codified in `libs/nvh_contract/src/nvh_contract/gear_ids.py` and
`libs/nvh_contract/src/nvh_contract/state.py`.

| gear_id | gear_label |
|---|---|
| 0 | N |
| 1 | R |
| 2 | I |
| 3 | II |
| 4 | III |
| 5 | IV |
| 6 | V |

| nvh_id | direction |
|---|---|
| -1 | (no log -- transport sentinel) |
| 0 | RU (Run-Up) |
| 1 | STYD (Steady drive) |
| 2 | STYC (Steady coast) |
| 3 | RD (Run-Down) |

## State machine (what downstream expects)

`NvhStateMachine` in `libs/nvh_contract/src/nvh_contract/state.py`
consumes the PLC events and emits `Transition` events which the
producer + Qt client dispatch on:

- **RUN_STARTED** -- nvh_cmd flipped IDLE/STOP -> START (bumps
  trial_no). LabVIEW app emits `LiveTestRunUpdate(RUNNING)` here.
- **GEAR_CHANGED** / **NVH_ID_CHANGED** -- transitions while
  `log_active`. Producer rolls TDMS files (new file per (gear_id,
  nvh_id) pair).
- **FINAL_LOG_REQUESTED** -- rising edge on `final_log_trigger`.
  Producer emits `LiveDcUpdate` + POSTs a summary row.
- **RUN_STOPPED** -- nvh_cmd flipped START -> STOP/IDLE. Producer
  closes TDMS + emits `LiveTestRunUpdate(COMPLETED)`.

`log_active` = `nvh_cmd == START AND nvh_id != -1`. Signal chunks
should only flow while this holds.

## Raw-data folder layout (write-side, LabVIEW's job)

If the LabVIEW app also does its own TDMS logging (mirroring the
Python `live_daq.py --raw-dir` behaviour), the expected layout is
computed by `libs/nvh_contract/src/nvh_contract/paths.py::raw_tdms_path`:

```
<base>/YYYY/MM/DD/Trial{N}/{model_id}/{serial}_{rpt}/{serial}_{gear_id}_{nvh_id}.tdms
```

- `base` is `data/raw/` relative to the repo root by convention.
- One file per (gear_id, nvh_id) segment; close + open on transition.
- `nvh_id == -1` -> no file open, no writes.

## Reference implementation

`web-backend/scripts/live_simulator.py --plc-url tcp://127.0.0.1:5556 --raw-dir ./data/raw`
is a full Python implementation of the acquisition side. Reading its
`_run_plc_driven_mode` function is the fastest way to see the full
lifecycle (PLC SUB -> state machine -> chunk emit -> TDMS rollover ->
summary POST).

## Version history

| Contract change | Commit | Notes |
|---|---|---|
| Initial LiveEvent trio | 2026-Q3 | LiveTestRunUpdate / LiveSignalChunk / LiveDcUpdate |
| PlcStateUpdate + multi-channel `channels` map | Phase F/G | additive; existing consumers still work |
