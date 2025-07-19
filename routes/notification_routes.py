from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from db import get_db
from models import Notification, User
from auth import get_current_user
from notif_service import notification_service
from pydantic import BaseModel
from datetime import datetime
from schemas import NotificationResponse, SendNotificationRequest

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

@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = db.query(Notification)\
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    
    return {"message": "Notification marked as read"}

@router.get("/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = db.query(Notification)\
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).count()
    
    return {"unread_count": count}