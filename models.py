from db import Base
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, TIMESTAMP,
    ARRAY, DECIMAL, func
)

# Users
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    last_name = Column(String(50), nullable=False)
    first_name = Column(String(50), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    avatar_url = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

#Password Reset TOken 

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# User Settings
class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme = Column(String(20), default="light")
    language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")
    font_size = Column(String(10), default="medium")
    notifications_enabled = Column(Boolean, default=True)
    email_notifications = Column(Boolean, default=True)
    two_factor_enabled = Column(Boolean, default=False)
    recovery_codes = Column(ARRAY(Text))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


# Question Categories
class QuestionCategory(Base):
    __tablename__ = "question_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)
    icon = Column(String(20))


# Questions
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("question_categories.id"))
    difficulty = Column(String(10))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


# Tags
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


# User Question Progress
class UserQuestionProgress(Base):
    __tablename__ = "user_question_progress"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    status = Column(String(20))
    attempts = Column(Integer, default=0)
    last_attempted = Column(TIMESTAMP(timezone=True))
    solved_at = Column(TIMESTAMP(timezone=True))
    bookmarked = Column(Boolean, default=False)
    notes = Column(Text)


# Interview Sessions
class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    type = Column(String(20))
    difficulty = Column(String(10))
    scheduled_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))
    duration_minutes = Column(Integer)
    feedback = Column(Text)
    rating = Column(Integer)
    recording_url = Column(String(255))


# Questions in Sessions
class SessionQuestion(Base):
    __tablename__ = "session_questions"

    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    order_index = Column(Integer, nullable=False)
    user_answer = Column(Text)
    feedback = Column(Text)
    time_spent_seconds = Column(Integer)


# Peer Sessions
class PeerSession(Base):
    __tablename__ = "peer_sessions"

    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    max_participants = Column(Integer)
    scheduled_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))
    status = Column(String(20))


# Billing Plans
class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)
    price_monthly = Column(DECIMAL(10, 2))
    price_yearly = Column(DECIMAL(10, 2))
    features = Column(ARRAY(Text))
    is_active = Column(Boolean, default=True)


# User Subscriptions
class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    plan_id = Column(Integer, ForeignKey("billing_plans.id"))
    status = Column(String(20))
    payment_method = Column(String(50))
    current_period_start = Column(TIMESTAMP(timezone=True))
    current_period_end = Column(TIMESTAMP(timezone=True))
    cancel_at_period_end = Column(Boolean, default=False)


# Payment History
class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="SET NULL"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    payment_date = Column(TIMESTAMP(timezone=True), server_default=func.now())
    payment_method = Column(String(50))
    receipt_url = Column(String(255))


# User Goals
class UserGoal(Base):
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    target_date = Column(DateTime(timezone=True))
    target_questions = Column(Integer)
    completed_questions = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


# Notifications
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    action_url = Column(String(255))
