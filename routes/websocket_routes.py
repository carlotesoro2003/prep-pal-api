from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from websocket_manager import manager
from auth import get_current_user_from_token
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_user_from_websocket_token(token: str):
    try:
        user = await get_current_user_from_token(token)
        return user
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        return None

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: str = Query(...)):
    user = await get_user_from_websocket_token(token)
    if not user or user.id != user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    try:
        await manager.connect(websocket, user_id)
        
        await manager.send_personal_message({
            "type": "connection_status",
            "data": {"status": "connected", "user_id": user_id}
        }, user_id)
        
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket message handling: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        manager.disconnect(websocket, user_id)

@router.get("/ws/status")
async def get_websocket_status():
    return {
        "total_connections": manager.get_total_connections(),
        "active_users": len(manager.active_connections)
    }