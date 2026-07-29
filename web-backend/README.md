# web-backend

FastAPI service (`nvh_web_backend`) serving the demo SQLite DB (populated
by `scripts/seed_demo_data.py`) so the `web-frontend`/`qt-app` Report GUI
clients can show real data on their Master Entry and Reports screens.
**Live Display is out of scope** — it needs a continuous live stream and
nothing in this codebase produces one yet.

## Design

Every report endpoint reconstructs a live `analysis_engine.pipeline.
DcAnalysisResult` on each request — read the raw signal back out of its
Parquet file, rebuild `GearOrders`/masters/limit-configs from DB rows, and
re-run `analyze_dc_record()` — rather than reading anything back from the
persisted `grading_results`/`spc_points` snapshot tables. Those tables only
ever stored `g_level`/`ok_flag` per stat, never the full order-spectrum/
order-tracking/fault-detection data a report needs, so this is the same
"compose from live analysis output" convention every
`analysis_engine.reports.*` builder already follows, not a new pattern.

See `src/nvh_web_backend/`:
- `adapters.py` — ORM row → pydantic/dataclass conversions (nothing in
  `nvh_contract`/`analysis-engine` does this today; every existing consumer
  builds these objects in-memory rather than reading them back from a row).
- `catalog_service.py` — builds the `dict[str, Value]` shapes
  `analysis_engine`'s grading functions expect, plus the Master Entry
  parameter-catalog list.
- `report_service.py` — the reconstruction chain above, including
  `DcAnalysisResult.passed`'s manual injection before validating a payload
  (it's a computed `@property`, so `to_jsonable()` never emits it — the
  same fix `libs/nvh_api_schemas/tests/test_report_schema_contract.py`
  already established as "what the future backend's report_service does").
- `routers/` — one FastAPI router per resource (`health`, `models`,
  `test_runs`, `reports`).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../libs/nvh_contract -e ../libs/nvh_api_schemas \
  -e ../analysis-engine -e . pytest
```

## Seed a demo dataset

```bash
.venv/bin/python scripts/seed_demo_data.py --data-root ./data/nvh_demo --trials 30
```

## Run

```bash
NVH_DB_URL="sqlite:///./data/nvh_demo/nvh_demo.db" .venv/bin/nvh-web-backend
```

Defaults to `http://127.0.0.1:8000`. Env vars: `NVH_DB_URL`,
`NVH_WEB_HOST`, `NVH_WEB_PORT`, `NVH_WEB_CORS_ORIGINS` (comma-separated,
defaults to the Vite dev server's `http://localhost:5173`).

## Test

```bash
.venv/bin/python -m pytest tests -q
```

Tests seed a fresh tmp-path SQLite DB per test (reusing
`scripts/seed_demo_data.py` exactly like `tests/test_seed_demo_data.py`
already does) and exercise the real FastAPI app via `TestClient` — no
external process needed.
