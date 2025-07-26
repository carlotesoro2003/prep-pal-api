import json
import asyncio
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            except ValueError:
                pass  # Connection already removed
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    async def send_personal_message(self, message: dict, user_id: int):
        websockets = self.active_connections.get(user_id, [])
        for ws in websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")

    async def send_notification(self, user_id: int, title: str, message: str, action_url: str = None):
        notification = {
            "type": "notification",
            "data": {
                "title": title,
                "message": message,
                "action_url": action_url,
                "timestamp": datetime.now().isoformat()
            }
        }
        await self.send_personal_message(notification, user_id)

    def get_user_connection_count(self, user_id: int) -> int:
        return len(self.active_connections.get(user_id, []))

    def get_total_connections(self) -> int:
        return sum(len(connections) for connections in self.active_connections.values())

manager = ConnectionManager()