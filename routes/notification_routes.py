from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from db import get_db
from models import Notification, User
from auth import get_current_user
from datetime import datetime
from schemas import NotificationRequest,NotificationResponse, SystemNotificationRequest
from websocket_manager import manager
import os

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationResponse])
async def get_user_notifications(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notifications = db.query(Notification)\
        .filter(Notification.user_id == current_user.id)\
        .order_by(Notification.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return notifications

@router.post("/", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to create this notification")
    
    new_notification = Notification(
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        created_at=datetime.utcnow()
    )
    
    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)
    
    message_to_broadcast = {
        "action": "new_notification",
        "data": {
            "id": new_notification.id,
            "user_id": new_notification.user_id,
            "title": new_notification.title,
            "message": new_notification.message,
            "created_at": str(new_notification.created_at)
        }
    }

    await manager.broadcast(message_to_broadcast)

    return new_notification


@router.post("/system", response_model=NotificationResponse)
async def create_system_notification(
    notification: SystemNotificationRequest,
    db: Session = Depends(get_db),
    system_key: str = None
):
    # Verify system key for security
    if system_key != os.getenv("SYSTEM_NOTIFICATION_KEY", "your-secret-key"):
        raise HTTPException(status_code=403, detail="Invalid system key")
    
    # Verify user exists
    user = db.query(User).filter(User.id == notification.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_notification = Notification(
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        created_at=datetime.utcnow()
    )
    
    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)
    
    # Send via WebSocket (your existing code)
    message_to_broadcast = {
        "action": "new_notification",
        "data": {
            "id": new_notification.id,
            "user_id": new_notification.user_id,
            "title": new_notification.title,
            "message": new_notification.message,
            "created_at": str(new_notification.created_at)
        }
    }

    await manager.send_to_user(new_notification.user_id, message_to_broadcast)

    return new_notification