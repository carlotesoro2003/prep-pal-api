from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import manager
import json

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif message.get("type") == "join_user":
                user_id = message.get("user_id")
                if user_id:
                    manager.user_connections[user_id] = websocket
            
    except WebSocketDisconnect:
        # Client disconnected normally
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)