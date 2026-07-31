# NVH End-of-Line Test System — Python + Web + AI Rebuild

A from-scratch rebuild of an end-of-line (EOL) gearbox/transmission NVH test and
grading system, evolving an existing LabVIEW-based tool into **LabVIEW +
Python + Web UI + Qt UI + AI**. See [`docs/data-contract.md`](docs/data-contract.md)
for the canonical data contract and [`docs/design-tokens.md`](docs/design-tokens.md)
for the shared visual design system.

## Status

- **Phase 1 (MVP analysis engine + simulator): done.** Signal simulator + core
  analysis engine (order matrix, spectral/order analysis, master-signature
  grading, fault detection, SPC), demonstrable via CLI with no hardware and no
  web UI.
- **Report GUI, M0 (Foundations): done.** Shared design tokens, the
  report-assembly layer, shared API wire schemas, and a demo-data seed script
  that persists Parquet files + DB rows per the data contract — the first
  thing in the repo to actually write that data.
- **GUI scaffolding: done.** `web-frontend/` (Vite+React+TS+Tailwind) and
  `qt-app/` (PySide6) app shells, sharing one visual language derived from
  `design-tokens`.
- **M1: done.** `web-backend/` — a FastAPI service serving the demo
  SQLite DB (reconstructing full analysis results on the fly from the raw
  Parquet signal + DB config rows, never from persisted grading snapshots).
  All three GUI screens wired end-to-end in both clients: **Master Entry**,
  **Reports** (Consolidated/Detailed/Summary/Code-Result tabs), and
  **Live Display** — the last via a ZeroMQ PUB→SUB→WebSocket pipeline
  (`web-backend/scripts/live_simulator.py` produces continuous signal
  chunks + status events over ZMQ, the FastAPI backend relays to a
  `/live/ws` WebSocket, both clients render a rolling signal trace and
  live PASS/FAIL stamp). The ZMQ producer is designed so LabVIEW can
  drop-in replace it later without touching anything downstream.
- **Not yet built**: write/edit endpoints (backend is read-only today —
  creating models/master profiles/limit configs from the GUI is a later
  slice), the AI layer, and real LabVIEW hardware integration.

## Packages

| Package | Purpose |
|---|---|
| `libs/nvh_contract` | Shared pydantic + SQLAlchemy data contract (models, DB schema, Parquet read/write) between acquisition (simulator today, LabVIEW later) and analysis |
| `libs/nvh_api_schemas` | Shared pydantic wire schemas for the (future) web backend and Qt client — one source of truth for the API contract |
| `design-tokens` | Canonical design tokens (color, type, layout, signature gear-glyph asset) shared by the web and Qt clients |
| `analysis-engine` | Order-matrix computation, spectral/order analysis, grading, fault detection, SPC, and report assembly (Consolidated/Detailed/Summary) |
| `simulator` | Synthetic gearbox NVH signal generator conforming to the data contract, with injectable faults for testing |
| `web-backend/scripts/seed_demo_data.py` | Seeds a demo dataset (Parquet + DB rows) that `web-backend`'s FastAPI app serves |
| `web-backend` (`nvh_web_backend`) | FastAPI backend serving the demo SQLite DB — reconstructs live analysis results from Parquet + DB config rows on every request, never from persisted grading snapshots (see its own README) |
| `web-frontend` | Vite+React+TS+Tailwind Report GUI web client — Master Entry/Reports wired to `web-backend`, Live Display still a placeholder (see its own README) |
| `qt-app` | PySide6 Report GUI desktop client — same screens, same backend, same design tokens (see its own README) |

## Setup

**Python 3.10 or newer.** All seven local packages declare
`requires-python = ">=3.10"`; 3.10.8 (the PyCharm bundled version many
Windows installs land on) is fine, and 3.11/3.12 are what CI runs.

From a fresh venv, install third-party deps first, then the seven local
packages in editable mode. This is a two-step install by design:
older `pip` releases on Windows (notably 23.2.x, as shipped by many
PyCharm bundles) reject `-e ./path` inside a requirements file with
"is not a valid editable requirement", so we keep the editable installs
out of `requirements.txt` and run them as a separate command.

```bash
python3 -m venv .venv
. .venv/bin/activate                                        # Windows: .venv\Scripts\activate

pip install -r requirements.txt                             # third-party deps
pip install -r requirements-dev.txt                         # + pytest

pip install -e libs/nvh_contract -e libs/nvh_api_schemas -e design-tokens \
  -e analysis-engine -e simulator -e web-backend -e qt-app  # local packages
```

Or run the one-shot bootstrap script that does both pip steps for you:

```bash
scripts/install_local.sh          # Linux / macOS
scripts\install_local.bat         # Windows
```

### PyCharm interpreter (Windows gotcha)

PyCharm sees a `pyproject.toml` in every subfolder (`qt-app/`,
`web-backend/`, `analysis-engine/`, …) and, if you let it, will offer
to create a *per-subfolder venv* like `qt-app\.venv\`. Those sub-venvs
do NOT contain the seven editable packages, so `Run 'app.py'` on a file
under `qt-app/src/nvh_qt_app/` will crash with:

```
ModuleNotFoundError: No module named 'nvh_design_tokens'
```

The root `pyproject.toml` declares a `[project]` section so PyCharm
recognises the *repository root* as the single Python project, which
mostly prevents the trap on fresh clones. If your project already has
stray sub-venvs, clean them up with the helper script and re-point the
interpreter:

```bash
scripts\fix_pycharm.bat        # Windows
scripts/fix_pycharm.sh         # Linux / macOS
```

Then in PyCharm:

1. **File → Settings → Project: Vibration-Analysis-software- → Python Interpreter**
2. Gear icon → **Add Interpreter → Add Local Interpreter… → Existing**
3. Browse to
   `...\Vibration-Analysis-software-\.venv\Scripts\python.exe`
   (the root `.venv`, not `qt-app\.venv` or `web-backend\.venv`)
4. OK.

`scripts\install_local.bat` also refuses to run if the active venv
isn't the repository-root one, so you can't silently install packages
into the wrong sub-venv.

> **Activate the venv first.** The commands below assume your venv is
> active — the prompt shows `(.venv)` or `(venv)`. Activate with
> `. .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate`
> (Windows PowerShell). Once active, `python`, `pip`, and the console
> scripts (`nvh-launcher`, `nvh-sim`, `nvh-web-backend`, `nvh-qt-app`) all resolve on
> `PATH` — you do NOT prefix them with `.venv/bin/` on Linux or
> `.venv\Scripts\` on Windows. Do not paste `.venv/bin/nvh-sim` into
> PowerShell — that's a Linux path and Windows will report
> `CommandNotFoundException`.

## Single-window launcher (recommended)

```bash
nvh-launcher
```

A small PySide6 window that manages every subprocess for you: one-click
`Seed Demo Data`, `Run Analysis Demo`, and `Open Web UI` up top, then
four managed services (Live Simulator, FastAPI Backend, Web Frontend,
Qt Desktop App) each with a status LED, Start/Stop toggle, and live log
tail. Closes cleanly — offers to stop anything still running.

The rest of the sections below list the same commands the launcher
invokes, for when you want to run them by hand instead.

## Run the end-to-end analysis demo

```bash
nvh-sim --trials 30 --out report.json
```

Builds a master signature from 30 simulated known-good units for gear R, then
runs a healthy unit, a crash-noise-faulted unit, and a slippage-faulted unit
through the full analysis pipeline, printing PASS/FAIL for each.

## Seed a persisted demo dataset

```bash
python web-backend/scripts/seed_demo_data.py --data-root ./data/nvh_demo --trials 30
```

Writes Parquet files under `./data/nvh_demo/` and a SQLite DB
(`nvh_demo.db`) with one healthy and two faulted test runs — the dataset
`web-backend` serves to the web/Qt clients.

## Run the backend + live simulator + a GUI client

```bash
# terminal 1 -- the live-stream producer (ZeroMQ PUB); optional for
# Master Entry / Reports, required to see Live Display do anything
python web-backend/scripts/live_simulator.py

# terminal 2 -- the FastAPI backend (serves the DB + relays the ZMQ
# stream to /live/ws)
#   Linux / macOS:
NVH_DB_URL="sqlite:///./data/nvh_demo/nvh_demo.db" nvh-web-backend
#   Windows PowerShell (env var is a separate statement):
$env:NVH_DB_URL = "sqlite:///./data/nvh_demo/nvh_demo.db"; nvh-web-backend
```

Then, in another terminal: `cd web-frontend && npm run dev` (Vite dev
server, `http://localhost:5173`), or `nvh-qt-app` (desktop). Both
clients' Master Entry and Reports screens will show the seeded demo data.

## NI-DAQmx source (real or NI MAX simulated device)

`live_simulator.py` is fine for offline demos, but if you have NI-DAQmx
installed — including the NI MAX "simulated device" workflow that ships
with the driver — you can swap it for `live_daq.py` without touching
anything downstream. Both publish the same three ZMQ schemas
(`LiveTestRunUpdate`, `LiveSignalChunk`, `LiveDcUpdate`) on the same
PUB URL, so the FastAPI relay and both GUI clients don't know or care
which one is running.

Setup:

1. Install the NI-DAQmx driver from ni.com. Open **NI MAX → Devices and
   Interfaces**, right-click → **Create New… → Simulated NI-DAQmx Device
   or Modular Instrument**. Pick an analog-input device (an NI 9234 is
   a good default — 4-channel dynamic-signal-acquisition), give it a
   name like `Dev1`, and save.
2. Install the Python bindings into the repo-root venv:

   ```bash
   pip install -r requirements-daq.txt
   ```

3. Start acquisition:

   ```bash
   python web-backend/scripts/live_daq.py --device Dev1 --channel ai0
   ```

   `nvh-launcher` also has a dedicated **Live Producer** row with a
   Simulation / NI-DAQmx pill toggle — pick a source, tick **Log to
   TDMS** if you want the raw samples on disk, set the DMA buffer
   size, and click Start. Only one producer can hold `tcp://*:5555`
   at a time, so stop whichever you're not using.

### Buffer + TDMS logging

Both producers accept `--tdms-path` and (DAQ only) `--buffer-seconds`:

- **`--buffer-seconds`** on `live_daq.py` sets the NI-DAQmx DMA buffer
  in seconds (`samps_per_chan = sample_rate * buffer_seconds`). The
  driver holds this window in memory so a slow ZMQ read can't drop
  samples. Default 1.0 s. Larger values trade RAM for tolerance to
  downstream stalls.
- **`--tdms-path`** enables raw-sample logging alongside the ZMQ
  stream. `{ts}` in the path is substituted with a UTC timestamp so
  parallel launches never collide (e.g. `./data/tdms/daq_{ts}.tdms`).
  On `live_daq.py` this uses NI-DAQmx's own `LOG_AND_READ` logging
  (best latency, driver-managed). On `live_simulator.py` it uses
  `nptdms` (pure Python, requires `pip install -r requirements-daq.txt`
  — missing that package prints one line and keeps streaming without
  the TDMS side, since it's a nice-to-have not a hard dep).

The launcher's Live Producer row exposes both as inline controls, so
you don't have to hand-edit the launch command.

## Run the tests

```bash
python -m pytest analysis-engine/tests simulator/tests libs/nvh_contract/tests \
  libs/nvh_api_schemas/tests design-tokens/tests web-backend/tests qt-app/tests -q
```
