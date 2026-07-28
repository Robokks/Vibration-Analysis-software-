# NVH End-of-Line Test System — Python + Web + AI Rebuild

A from-scratch rebuild of an end-of-line (EOL) gearbox/transmission NVH test and
grading system, evolving an existing LabVIEW-based tool into **LabVIEW +
Python + Web UI + AI**. See [`docs/data-contract.md`](docs/data-contract.md)
for the canonical data contract and the full architecture plan for context and
phased roadmap.

## Status: Phase 1 (MVP analysis engine + simulator)

Phase 1 is complete: a signal simulator + the core analysis engine (order
matrix, spectral/order analysis, master-signature grading, fault detection,
SPC), fully demonstrable via CLI with **no hardware and no web UI**. Later
phases (web backend/frontend, AI layer, real LabVIEW integration) are not yet
built — see the roadmap in the architecture plan.

## Packages

| Package | Purpose |
|---|---|
| `libs/nvh_contract` | Shared pydantic + SQLAlchemy models for the data contract between acquisition (simulator today, LabVIEW later) and analysis |
| `analysis-engine` | Order-matrix computation, spectral/order analysis, grading, fault detection, SPC |
| `simulator` | Synthetic gearbox NVH signal generator conforming to the data contract, with injectable faults for testing |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e libs/nvh_contract -e analysis-engine -e simulator pytest
```

## Run the end-to-end demo

```bash
.venv/bin/nvh-sim --trials 30 --out report.json
```

This builds a master signature from 30 simulated known-good units for gear R,
then runs a healthy unit, a crash-noise-faulted unit, and a slippage-faulted
unit through the full analysis pipeline, printing PASS/FAIL for each.

## Run the tests

```bash
.venv/bin/python -m pytest analysis-engine/tests simulator/tests libs/nvh_contract/tests -q
```
