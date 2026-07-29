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
  `design-tokens`. Every screen is a placeholder marked `TODO:` — **no live
  data wiring yet**; that follows once Phase C–E and the FastAPI backend
  land.
- **Not yet built**: the FastAPI backend (M1), wiring the web frontend (M2)
  and Qt desktop app (M3) to real data, the AI layer, and real LabVIEW
  hardware integration.

## Packages

| Package | Purpose |
|---|---|
| `libs/nvh_contract` | Shared pydantic + SQLAlchemy data contract (models, DB schema, Parquet read/write) between acquisition (simulator today, LabVIEW later) and analysis |
| `libs/nvh_api_schemas` | Shared pydantic wire schemas for the (future) web backend and Qt client — one source of truth for the API contract |
| `design-tokens` | Canonical design tokens (color, type, layout, signature gear-glyph asset) shared by the web and Qt clients |
| `analysis-engine` | Order-matrix computation, spectral/order analysis, grading, fault detection, SPC, and report assembly (Consolidated/Detailed/Summary) |
| `simulator` | Synthetic gearbox NVH signal generator conforming to the data contract, with injectable faults for testing |
| `web-backend/scripts/seed_demo_data.py` | Seeds a demo dataset (Parquet + DB rows) — precedes the FastAPI app itself, which is a later milestone |
| `web-frontend` | Vite+React+TS+Tailwind Report GUI web client — app shell + Live Display/Master Entry/Reports screens, GUI scaffolding only (see its own README) |
| `qt-app` | PySide6 Report GUI desktop client — same screens, same design tokens, GUI scaffolding only (see its own README) |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e libs/nvh_contract -e libs/nvh_api_schemas -e design-tokens \
  -e analysis-engine -e simulator pytest
```

## Run the end-to-end analysis demo

```bash
.venv/bin/nvh-sim --trials 30 --out report.json
```

Builds a master signature from 30 simulated known-good units for gear R, then
runs a healthy unit, a crash-noise-faulted unit, and a slippage-faulted unit
through the full analysis pipeline, printing PASS/FAIL for each.

## Seed a persisted demo dataset

```bash
.venv/bin/python web-backend/scripts/seed_demo_data.py --data-root ./data/nvh_demo --trials 30
```

Writes Parquet files under `./data/nvh_demo/` and a SQLite DB
(`nvh_demo.db`) with one healthy and two faulted test runs — the dataset a
future backend/frontend/Qt app would read from.

## Run the tests

```bash
.venv/bin/python -m pytest analysis-engine/tests simulator/tests libs/nvh_contract/tests \
  libs/nvh_api_schemas/tests design-tokens/tests web-backend/tests -q
```
