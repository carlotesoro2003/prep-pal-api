import asyncio
import httpx
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from db import SessionLocal
from models import InterviewSession
import os

# Get the API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

async def session_notification_worker():
    print("Session notification worker started")
    
    while True:
        db = None
        try:
            db = SessionLocal()
            now = datetime.utcnow()

            # Notify for sessions starting in 15 minutes
            await check_upcoming_sessions(db, now)
            
            # Notify for ongoing sessions
            await check_ongoing_sessions(db, now)

        except SQLAlchemyError as e:
            print(f"Database error in notification worker: {e}")
        except Exception as e:
            print(f"Session notification worker error: {e}")
        finally:
            if db:
                db.close()
        
        await asyncio.sleep(60)  # Check every 60 seconds

async def check_upcoming_sessions(db: Session, now: datetime):
    try:
        soon = now + timedelta(minutes=15)
        sessions_15 = db.query(InterviewSession).filter(
            InterviewSession.scheduled_at >= now,
            InterviewSession.scheduled_at < soon,
            InterviewSession.notification_sent == False
        ).all()
        
        for session in sessions_15:
            success = await send_notification_via_api(
                session.user_id,
                "Session starting soon",
                f"Your session '{session.title}' starts at {session.scheduled_at.strftime('%H:%M')}"
            )
            
            if success:
                session.notification_sent = True
            
        if sessions_15:
            db.commit()
            
    except Exception as e:
        print(f"Error checking upcoming sessions: {e}")
        db.rollback()

async def check_ongoing_sessions(db: Session, now: datetime):
    try:
        ongoing_sessions = db.query(InterviewSession).filter(
            InterviewSession.scheduled_at <= now,
            InterviewSession.end_at > now,
            InterviewSession.ongoing_notification_sent == False
        ).all()
        
        for session in ongoing_sessions:
            success = await send_notification_via_api(
                session.user_id,
                "Session is ongoing",
                f"Your session '{session.title}' is now ongoing."
            )
            
            if success:
                session.ongoing_notification_sent = True
            
        if ongoing_sessions:
            db.commit()
            
    except Exception as e:
        print(f"Error checking ongoing sessions: {e}")
        db.rollback()

async def send_notification_via_api(user_id: int, title: str, message: str) -> bool:
    """Send notification using the POST /notifications endpoint"""
    try:
        # You'll need to get a valid token for the user
        # For now, we'll use a system token or admin token
        # Alternative: Create a system user or bypass auth for internal calls
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/api/notifications/",
                json={
                    "user_id": user_id,
                    "title": title,
                    "message": message
                },
                headers={
                    "Authorization": f"Bearer {await get_system_token(user_id)}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                print(f"Notification sent successfully to user {user_id}: {title}")
                return True
            else:
                print(f"Failed to send notification: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"Error sending notification via API: {e}")
        return False

async def get_system_token(user_id: int) -> str:
    """Generate a token for system notifications"""
    # Option 1: Create a system token (recommended)
    # You can create a special system user or use JWT directly
    
    # Option 2: Generate a temporary token for the user
    from auth import create_access_token
    return create_access_token(data={"sub": str(user_id)})


async def send_notification_via_api(user_id: int, title: str, message: str) -> bool:
    """Send notification using the system endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/api/notifications/system",
                json={
                    "user_id": user_id,
                    "title": title,
                    "message": message
                },
                params={
                    "system_key": os.getenv("SYSTEM_NOTIFICATION_KEY", "your-secret-key")
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"Notification sent successfully to user {user_id}: {title}")
                return True
            else:
                print(f"Failed to send notification: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"Error sending notification via API: {e}")
        return False