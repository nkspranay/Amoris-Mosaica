"""
WebSocket progress handler.

Manages active WebSocket connections keyed by session_id.
The engine calls emit() during mosaic generation — this routes
those events to the correct connected client.

Endpoint: WS /ws/progress/{session_id}
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Tracks active WebSocket connections by session_id.
    Thread-safe for asyncio — single event loop assumed.
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id] = websocket
        print(f"[ws] Client connected: {session_id}")

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        print(f"[ws] Client disconnected: {session_id}")

    async def send(
        self,
        session_id: str,
        stage: str,
        percent: int,
        eta_ms: Optional[int] = None,
    ) -> None:
        """
        Send a progress event to the client with the given session_id.
        Silently skips if the client is no longer connected.
        """
        websocket = self._connections.get(session_id)
        if websocket is None:
            return

        payload = {
            "stage":   stage,
            "percent": percent,
            "eta_ms":  eta_ms,
            "done":    stage == "done",
            "error":   stage == "error",
        }

        try:
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0)  # yield to event loop to flush the frame
        except Exception as e:
            print(f"[ws] Failed to send to {session_id}: {e}")
            self.disconnect(session_id)

    def is_connected(self, session_id: str) -> bool:
        return session_id in self._connections


# Shared singleton — imported by route handlers to build the emitter
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Emitter factory
# ---------------------------------------------------------------------------

def build_emitter(session_id: str):
    """
    Returns an async emitter function bound to a session_id.
    Pass this into generate_mosaic() as the emit parameter.
    """
    async def emitter(stage: str, percent: int, eta_ms: Optional[int] = None) -> None:
        await manager.send(session_id, stage, percent, eta_ms)

    return emitter


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/progress/{session_id}")
async def websocket_progress(websocket: WebSocket, session_id: str):
    """
    Client connects here before submitting a generate request.
    Stays open to receive progress events during mosaic generation.
    Sends a heartbeat every 15s to keep the connection alive on Render.
    """
    await manager.connect(session_id, websocket)

    try:
        while True:
            # Keep connection alive — send heartbeat periodically
            # Also listens for any client messages (e.g. cancel — future feature)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    # If ping fails, client is likely disconnected
                    manager.disconnect(session_id)
                    break

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[ws] Unexpected error for {session_id}: {e}")
        manager.disconnect(session_id)