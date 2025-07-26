import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import InterviewSession, Notification
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
            now = datetime.now(timezone.utc)
            fifteen_min = now + timedelta(minutes=15)
            five_min = now + timedelta(minutes=5)

            # 15 min reminders
            sessions_15 = db.query(InterviewSession).filter(
                InterviewSession.scheduled_at.between(now, fifteen_min),
                InterviewSession.notification_sent.is_(False)
            ).all()

            # 5 min reminders
            sessions_5 = db.query(InterviewSession).filter(
                InterviewSession.scheduled_at.between(now, five_min),
                InterviewSession.notification_5min_sent.is_(False)
            ).all()

            # Ongoing sessions (started but not ended)
            ongoing_sessions = db.query(InterviewSession).filter(
                InterviewSession.scheduled_at <= now,
                InterviewSession.end_at.is_(None),
                InterviewSession.ongoing_notification_sent.is_(False)
            ).all()

            logger.info(f"15min: {len(sessions_15)}, 5min: {len(sessions_5)}, ongoing: {len(ongoing_sessions)} sessions to notify")

            for session in sessions_15:
                await self.send_session_reminder(db, session, minutes=15)
                session.notification_sent = True

            for session in sessions_5:
                await self.send_session_reminder(db, session, minutes=5)
                session.notification_5min_sent = True

            for session in ongoing_sessions:
                await self.send_ongoing_session_notification(db, session)
                session.ongoing_notification_sent = True

            if sessions_15 or sessions_5 or ongoing_sessions:
                db.commit()

        except Exception as e:
            logger.error(f"Error checking upcoming sessions: {e}")
            db.rollback()
        finally:
            db.close()

    async def send_session_reminder(self, db: Session, session: InterviewSession, minutes: int):
        """Send reminder notification for an upcoming session"""
        try:
            now_aware = datetime.now(timezone.utc)
            scheduled_at = session.scheduled_at
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            time_until = scheduled_at - now_aware
            minutes_until = int(time_until.total_seconds() / 60)

            notification = Notification(
                user_id=session.user_id,
                title=f"Interview Session Starting in {minutes} Minutes",
                message=f"Your session '{session.title}' starts in {minutes_until} minutes",
                type=f"session_reminder_{minutes}",
                action_url=f"/home/sessions/{session.id}",
                is_read=False
            )
            db.add(notification)
            db.flush()

            await manager.send_notification(
                user_id=session.user_id,
                title=f"Interview Session Starting in {minutes} Minutes",
                message=f"Your session '{session.title}' starts in {minutes_until} minutes",
                action_url=f"/home/sessions/{session.id}"
            )

            logger.info(f"Sent {minutes}min reminder for session {session.id} to user {session.user_id}")

        except Exception as e:
            logger.error(f"Error sending {minutes}min session reminder for session {session.id}: {e}")

    async def send_ongoing_session_notification(self, db: Session, session: InterviewSession):
        """Send notification if a session is ongoing"""
        try:
            notification = Notification(
                user_id=session.user_id,
                title="Interview Session Ongoing",
                message=f"Your session '{session.title}' is currently ongoing.",
                type="session_ongoing",
                action_url=f"/home/sessions/{session.id}",
                is_read=False
            )
            db.add(notification)
            db.flush()

            await manager.send_notification(
                user_id=session.user_id,
                title="Interview Session Ongoing",
                message=f"Your session '{session.title}' is currently ongoing.",
                action_url=f"/home/sessions/{session.id}"
            )

            logger.info(f"Sent ongoing session notification for session {session.id} to user {session.user_id}")

        except Exception as e:
            logger.error(f"Error sending ongoing session notification for session {session.id}: {e}")

    async def send_custom_notification(self, user_id: int, title: str, message: str, action_url: str = None):
        """Send a custom notification to a user"""
        db = SessionLocal()
        try:
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