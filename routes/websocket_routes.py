from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from websocket_manager import manager
from auth import get_current_user_from_token, get_current_user
import models  # Add this import
import logging
from sqlalchemy.orm import Session
from db import get_db, SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_user_from_websocket_token(token: str, db: Session):
    try:
        user = await get_current_user_from_token(token, db)
        return user
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        return None

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: str = Query(...)):
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        user = await get_user_from_websocket_token(token, db)
        if not user or user.id != user_id:
            logger.error(f"WebSocket auth failed: user={user}, user_id={user_id}, token={token}")
            await websocket.close(code=4001, reason="Unauthorized")
            return

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
        db.close()  # <-- Always close the DB session!

@router.get("/ws/status")
async def get_websocket_status():
    return {
        "total_connections": manager.get_total_connections(),
        "active_users": len(manager.active_connections)
    }

@router.post("/interview-sessions/{session_id}/end")
async def end_session(
    session_id: int,
    current_user: models.User = Depends(get_current_user)  # Fix: Add proper type
):


    # Send notification
    await manager.send_notification(
        user_id=current_user.id,
        title="Session Ended",
        message=f"Your interview session has ended.",
        action_url=f"/home/sessions/{session_id}"
    )
    
    return {"message": "Session ended"}

# Fix: Remove the 'a' typo and add proper function
async def send_session_reminder(session_id: int, user_id: int):
    await manager.send_notification(
        user_id=user_id,
        title="Session Starting Soon",
        message="Your interview session starts in 15 minutes.",
        action_url=f"/home/sessions/{session_id}"
    )