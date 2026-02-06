from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import json
import asyncio

router = APIRouter()

# Store active WebSocket connections
active_connections: Dict[int, list] = {}


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, list] = {}

    async def connect(self, websocket: WebSocket, session_id: int):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: int):
        if session_id in self.active_connections:
            self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_progress_update(self, session_id: int, data: dict):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(data)
                except:
                    pass

    async def broadcast(self, session_id: int, message: str):
        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_text(message)
                except:
                    pass


manager = ConnectionManager()


@router.websocket("/sessions/{session_id}")
async def websocket_session_progress(websocket: WebSocket, session_id: int):
    """WebSocket endpoint for real-time session progress updates"""
    await manager.connect(websocket, session_id)

    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()

            # Echo back (optional)
            await websocket.send_json({
                "type": "ping",
                "message": "Connection alive"
            })

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id)


async def send_session_update(session_id: int, update_data: dict):
    """Helper function to send updates to all connected clients for a session"""
    await manager.send_progress_update(session_id, update_data)
