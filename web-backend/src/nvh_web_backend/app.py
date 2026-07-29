from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from nvh_contract.db import init_db, make_engine, make_session_factory

from nvh_web_backend import config
from nvh_web_backend.routers import health, models, reports, test_runs


def create_app(db_url: str | None = None) -> FastAPI:
    """`db_url` override exists so tests can point the app at a freshly
    seeded tmp_path SQLite DB without touching environment variables --
    the same TestClient(create_app(db_url=...)) pattern
    web-backend/tests/test_seed_demo_data.py's fixture already reuses."""
    app = FastAPI(title="NVH Report GUI backend")

    engine = make_engine(db_url or config.db_url())
    init_db(engine)  # no-op safety net against an empty DB -- the real demo DB is always pre-seeded
    app.state.session_factory = make_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins(),
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(test_runs.router)
    app.include_router(reports.router)

    return app
