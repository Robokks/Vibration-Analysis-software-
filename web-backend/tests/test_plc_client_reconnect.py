"""Regression tests for Phase O Bug 8: plc_client must clean up its
ZMQ PUB socket even when the initial snap7 connect() fails, and must
survive transient db_read failures via reconnect."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
import zmq

REPO_ROOT = Path(__file__).resolve().parents[2]
PLC_CLIENT = REPO_ROOT / "web-backend" / "scripts" / "plc_client.py"


def _install_fake_snap7(connect_should_fail: bool = False) -> types.SimpleNamespace:
    """Register a fake `snap7` module in sys.modules before plc_client
    imports it. Return a namespace with the tracked call counts."""
    tracker = types.SimpleNamespace(
        connect_calls=0, disconnect_calls=0, db_read_calls=0, last_connected=False,
    )

    class _FakeClient:
        def connect(self, ip, rack, slot):
            tracker.connect_calls += 1
            if connect_should_fail:
                raise RuntimeError("simulated PLC unreachable")
            tracker.last_connected = True

        def disconnect(self):
            tracker.disconnect_calls += 1
            tracker.last_connected = False

        def db_read(self, db, start, length):
            tracker.db_read_calls += 1
            # Return valid bytes so _decode_db doesn't fail.
            import struct
            return bytes([0, 0]) + struct.pack(">h", -1) + bytes([0])

    fake_snap7 = types.SimpleNamespace(
        client=types.SimpleNamespace(Client=_FakeClient),
    )
    sys.modules["snap7"] = fake_snap7
    return tracker


def _load_plc_client():
    # Reload to pick up the fresh sys.modules["snap7"] injection.
    spec = importlib.util.spec_from_file_location("_plc_client_test", PLC_CLIENT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_plc_client_test"] = module
    spec.loader.exec_module(module)
    return module


class PlcClientReconnectTests:
    def test_failed_initial_connect_exits_but_does_not_leak_zmq_socket(self, monkeypatch):
        tracker = _install_fake_snap7(connect_should_fail=True)
        module = _load_plc_client()

        # Bind to an ephemeral port to avoid clashing with a real launcher.
        monkeypatch.setattr(sys, "argv", [
            "plc_client.py",
            "--plc-ip", "127.0.0.1",
            "--pub-url", "tcp://127.0.0.1:15602",
            "--poll-hz", "10",
        ])

        close_count = {"n": 0}
        real_close = zmq.Socket.close

        def _tracked_close(self, *a, **kw):
            close_count["n"] += 1
            return real_close(self, *a, **kw)

        monkeypatch.setattr(zmq.Socket, "close", _tracked_close)

        with pytest.raises(SystemExit) as excinfo:
            module.main()
        # Exit code 2 on failed initial connect (matches nidaqmx-missing
        # error path -- launcher shows red LED).
        assert excinfo.value.code == 2
        assert tracker.connect_calls == 1  # attempted once
        # The finally block must have closed the PUB socket.
        assert close_count["n"] >= 1

        # Clean up.
        del sys.modules["snap7"]
