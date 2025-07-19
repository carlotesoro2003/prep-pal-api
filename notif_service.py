import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from  models import InterviewSession, Notification
from db import SessionLocal
from websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.running = False
        self.check_interval = 60  # Check every minute

    async def start_notification_scheduler(self):
        """Start the background task for checking upcoming sessions"""
        self.running = True
        logger.info("Starting notification scheduler...")
        
        while self.running:
            try:
                await self.check_upcoming_sessions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in notification scheduler: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_notification_scheduler(self):
        """Stop the notification scheduler"""
        self.running = False
        logger.info("Notification scheduler stopped")

    async def check_upcoming_sessions(self):
        """Check for sessions starting soon and send notifications"""
        db = SessionLocal()
        try:
            now = datetime.now()
            # Check for sessions starting in 15 minutes
            upcoming_time = now + timedelta(minutes=15)
            
            sessions = db.query(InterviewSession).filter(
                InterviewSession.scheduled_at.between(now, upcoming_time),
                InterviewSession.notification_sent.is_(False)
            ).all()

            logger.info(f"Found {len(sessions)} upcoming sessions to notify")

            for session in sessions:
                await self.send_session_reminder(db, session)
                session.notification_sent = True
                
            if sessions:
                db.commit()

        except Exception as e:
            logger.error(f"Error checking upcoming sessions: {e}")
            db.rollback()
        finally:
            db.close()

    async def send_session_reminder(self, db: Session, session: InterviewSession):
        """Send reminder notification for an upcoming session"""
        try:
            time_until = session.scheduled_at - datetime.now()
            minutes_until = int(time_until.total_seconds() / 60)
            
            # Create notification record
            notification = Notification(
                user_id=session.user_id,
                title="Interview Session Starting Soon",
                message=f"Your session '{session.title}' starts in {minutes_until} minutes",
                type="session_reminder",
                action_url=f"/home/sessions/{session.id}",
                is_read=False
            )
            db.add(notification)
            db.flush()  # Get the notification ID

            # Send real-time notification via WebSocket
            await manager.send_notification(
                user_id=session.user_id,
                title="Interview Session Starting Soon",
                message=f"Your session '{session.title}' starts in {minutes_until} minutes",
                action_url=f"/home/sessions/{session.id}"
            )

            logger.info(f"Sent reminder for session {session.id} to user {session.user_id}")

        except Exception as e:
            logger.error(f"Error sending session reminder for session {session.id}: {e}")

    async def send_custom_notification(self, user_id: int, title: str, message: str, action_url: str = None):
        """Send a custom notification to a user"""
        db = SessionLocal()
        try:
            # Create notification record
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type="custom",
                action_url=action_url,
                is_read=False
            )
            db.add(notification)
            db.commit()

            # Send real-time notification via WebSocket
            await manager.send_notification(
                user_id=user_id,
                title=title,
                message=message,
                action_url=action_url
            )

            logger.info(f"Sent custom notification to user {user_id}")

        except Exception as e:
            logger.error(f"Error sending custom notification to user {user_id}: {e}")
            db.rollback()
        finally:
            db.close()

notification_service = NotificationService()