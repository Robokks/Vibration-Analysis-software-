"""In-process integration test: bring up a ZMQ PUB on a random port, point
the backend's SUB relay at it via create_app(NVH_LIVE_SUB_URL override),
push a synthetic LiveEvent, and confirm the /live/ws WebSocket delivers
it byte-for-byte. Uses fastapi.testclient's WebSocket support -- no real
uvicorn process needed."""

from __future__ import annotations

import json
import socket
import time

import pytest
import zmq
from fastapi.testclient import TestClient
from nvh_api_schemas import LiveSignalChunk, LiveTestRunUpdate

from nvh_web_backend.app import create_app


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_pub_and_client(monkeypatch, seeded_db):
    db_url, _ = seeded_db
    port = _pick_free_port()
    url = f"tcp://127.0.0.1:{port}"

    context = zmq.Context.instance()
    pub = context.socket(zmq.PUB)
    pub.bind(url)

    # Give the SUB side time to actually connect before the first publish,
    # otherwise PUB drops messages sent while there are no subscribers yet.
    monkeypatch.setenv("NVH_LIVE_SUB_URL", url)
    app = create_app(db_url=db_url)
    with TestClient(app) as client:
        time.sleep(0.15)
        yield pub, client

    pub.close(linger=0)


def test_websocket_forwards_live_test_run_event(live_pub_and_client):
    pub, client = live_pub_and_client
    event = LiveTestRunUpdate(test_run_id="run-1", station_id="STN-01", status="RUNNING")

    with client.websocket_connect("/live/ws") as ws:
        # Small pause after WS accept so the relay's fan-out reaches this queue.
        time.sleep(0.05)
        pub.send_string(event.model_dump_json())
        received = json.loads(ws.receive_text())

    assert received["type"] == "test_run"
    assert received["test_run_id"] == "run-1"
    assert received["status"] == "RUNNING"


def test_websocket_forwards_signal_chunk(live_pub_and_client):
    pub, client = live_pub_and_client
    chunk = LiveSignalChunk(
        test_run_id="run-1", dc_id="dc-1", station_id="STN-01",
        gear_label="R", direction="RU", channel_name="vib_a",
        sample_rate_hz=5000.0, chunk_index=0,
        time_s=[0.0, 0.0002], values=[0.1, -0.2], rpm=[1000.0, 1000.3],
    )

    with client.websocket_connect("/live/ws") as ws:
        time.sleep(0.05)
        pub.send_string(chunk.model_dump_json())
        received = json.loads(ws.receive_text())

    assert received["type"] == "signal_chunk"
    assert received["values"] == [0.1, -0.2]
    assert received["chunk_index"] == 0
