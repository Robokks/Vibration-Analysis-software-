"""Shared fixtures for the FastAPI backend tests: a seeded demo DB (reusing
scripts/seed_demo_data.py exactly like test_seed_demo_data.py's own `seeded`
fixture does) and a TestClient pointed at it via create_app(db_url=...)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from seed_demo_data import seed  # noqa: E402

from nvh_web_backend.app import create_app  # noqa: E402


@pytest.fixture
def seeded_db(tmp_path):
    data_root = tmp_path / "data"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    summary = seed(data_root, db_url, n_trials=15, seed_value=0)
    return db_url, summary


@pytest.fixture
def client(seeded_db):
    db_url, _ = seeded_db
    return TestClient(create_app(db_url=db_url))
