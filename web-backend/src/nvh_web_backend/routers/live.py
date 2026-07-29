from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/live/ws")
async def live_ws(websocket: WebSocket) -> None:
    relay = websocket.app.state.live_relay
    await websocket.accept()
    queue = relay.subscribe()
    try:
        while True:
            message = await queue.get()
            await websocket.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        relay.unsubscribe(queue)
