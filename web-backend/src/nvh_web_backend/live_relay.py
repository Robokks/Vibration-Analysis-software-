"""ZeroMQ SUB -> in-process async fan-out for the `/live/ws` WebSocket.

A single background task pulls string payloads off the ZMQ SUB socket and
pushes each one to every subscribed asyncio.Queue. Each connected
WebSocket owns one queue, so a slow client only backs up its own queue,
never the shared receive loop -- if a queue fills up we drop the oldest
message rather than blocking the fan-out. Payloads are forwarded as-is;
schema validation is the sender's and receiver's job (see
`nvh_api_schemas.realtime`).

Phase O Bug 4 addition: the receive loop also sniffs `type=plc_state`
messages and remembers the latest one in `plc_state_cache`, so the
dashboard bridge's heartbeat loop can fetch it via `GET /plc/state`
instead of trying to read gear/nvh keys off the dashboard's own
context payload (which never contains them)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)

_QUEUE_MAXSIZE = 200


class LiveRelay:
    def __init__(self, sub_url: str) -> None:
        self._sub_url = sub_url
        self._context: zmq.asyncio.Context | None = None
        self._socket: zmq.asyncio.Socket | None = None
        self._task: asyncio.Task[None] | None = None
        self._queues: set[asyncio.Queue[str]] = set()
        # Latest plc_state event seen on the SUB, cached so the
        # dashboard bridge's heartbeat can read the current PLC gear/
        # nvh id without needing its own PLC SUB socket. Populated by
        # _recv_loop when a message with `type == "plc_state"` arrives.
        self._plc_state_cache: dict[str, Any] = {
            "nvh_cmd": "IDLE",
            "gear_id": -1,
            "nvh_id": -1,
            "final_log_trigger": False,
        }

    async def start(self) -> None:
        self._context = zmq.asyncio.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.connect(self._sub_url)
        self._socket.setsockopt(zmq.SUBSCRIBE, b"")
        self._task = asyncio.create_task(self._recv_loop(), name="live-relay-recv")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._socket is not None:
            self._socket.close(linger=0)
            self._socket = None
        if self._context is not None:
            self._context.term()
            self._context = None

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._queues.discard(queue)

    def plc_state(self) -> dict[str, Any]:
        """Snapshot of the last-seen PLC state. Safe to call from any
        thread -- the cache is a plain dict updated only by _recv_loop
        (single-writer via `dict.update`) and Python dict ops are
        atomic w.r.t. the GIL."""
        return dict(self._plc_state_cache)

    async def _recv_loop(self) -> None:
        assert self._socket is not None
        while True:
            message = await self._socket.recv_string()
            # Sniff plc_state to keep the cache warm. Malformed JSON or
            # missing fields is expected during startup / non-PLC
            # producers -- log at debug, don't fail.
            try:
                payload = json.loads(message)
                if isinstance(payload, dict) and payload.get("type") == "plc_state":
                    self._plc_state_cache = {
                        "nvh_cmd": payload.get("nvh_cmd", "IDLE"),
                        "gear_id": payload.get("gear_id", -1),
                        "nvh_id": payload.get("nvh_id", -1),
                        "final_log_trigger": payload.get("final_log_trigger", False),
                    }
            except (ValueError, TypeError):
                pass  # not JSON or not a dict -- pass through unchanged
            for queue in list(self._queues):
                self._enqueue(queue, message)

    @staticmethod
    def _enqueue(queue: asyncio.Queue[str], message: str) -> None:
        while True:
            try:
                queue.put_nowait(message)
                return
            except asyncio.QueueFull:
                logger.warning(
                    "live_relay queue full (maxsize=%d); dropping oldest message",
                    _QUEUE_MAXSIZE,
                )
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    # Another task drained it between our put and get -- just retry.
                    continue
