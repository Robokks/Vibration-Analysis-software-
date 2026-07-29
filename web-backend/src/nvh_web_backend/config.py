"""Environment-driven defaults, mirroring scripts/seed_demo_data.py's own
--db-url default so `nvh-web-backend` run with no configuration against a
freshly-seeded default demo dataset just works the same way `nvh-sim`/the
seed script do with their own defaults."""

from __future__ import annotations

import os

DEFAULT_DB_URL = "sqlite:///./data/nvh_demo/nvh_demo.db"


def db_url() -> str:
    return os.environ.get("NVH_DB_URL", DEFAULT_DB_URL)


def host() -> str:
    return os.environ.get("NVH_WEB_HOST", "127.0.0.1")


def port() -> int:
    return int(os.environ.get("NVH_WEB_PORT", "8000"))


def cors_origins() -> list[str]:
    # The Vite dev server's default port -- the only client this backend
    # needs to allow cross-origin from today (qt-app isn't a browser, so
    # CORS doesn't apply to it).
    raw = os.environ.get("NVH_WEB_CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
