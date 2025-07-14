from db import Base
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, TIMESTAMP,
    ARRAY, DECIMAL, func
)
from sqlalchemy.orm import relationship

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

#Password Reset Token 
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
    questions = relationship("Question", back_populates="category")


# Questions - UPDATED to track creator
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("question_categories.id"))
    
    difficulty = Column(String(10))
    
    # NEW: Track who created the question
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    category = relationship("QuestionCategory", back_populates="questions")
    test_cases = relationship("TestCase", back_populates="question", cascade="all, delete-orphan")
    user_answers = relationship("UserAnswer", back_populates="question")
    creator = relationship("User", foreign_keys=[created_by])
    
    # NEW: Question type and coding-related fields
    question_type = Column(String(20), default="theory")  # "theory", "coding", "multiple_choice"
    starter_code = Column(Text)  # Template code for coding questions
    solution_code = Column(Text)  # Reference solution
    time_limit = Column(Integer, default=5)  # seconds for coding questions
    memory_limit = Column(Integer, default=256)  # MB for coding questions
    
    # NEW: Question status and visibility
    status = Column(String(20), default="draft")  # "draft", "published", "archived"
    is_public = Column(Boolean, default=True)  # Whether other users can see this question
    
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

# Test Cases for coding questions
class TestCase(Base):
    __tablename__ = "test_cases"
    
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    question = relationship("Question", back_populates="test_cases")
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    is_sample = Column(Boolean, default=False)  # Sample test case visible to users
    points = Column(Integer, default=1)
    description = Column(String(255))  # Optional description of the test case
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

#  User Answers - Store all user answers to questions
class UserAnswer(Base):
    __tablename__ = "user_answers"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer_text = Column(Text)  # For theory questions
    source_code = Column(Text)  # For coding questions
    language = Column(String(20))  # Programming language used
    is_correct = Column(Boolean)  # Whether the answer is correct
    score = Column(Integer, default=0)  # Points earned
    time_taken_seconds = Column(Integer)  # Time spent on this answer
    submitted_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # For coding questions - execution results
    execution_time = Column(Integer)  # milliseconds
    memory_used = Column(Integer)  # KB
    test_cases_passed = Column(Integer, default=0)
    total_test_cases = Column(Integer, default=0)
    error_message = Column(Text)

    user = relationship("User")
    question = relationship("Question", back_populates="user_answers")

# Tags
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

# NEW: Question Tags - Many-to-many relationship
class QuestionTag(Base):
    __tablename__ = "question_tags"
    
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

# User Question Progress - UPDATED
class UserQuestionProgress(Base):
    __tablename__ = "user_question_progress"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    status = Column(String(20))  # "not_started", "in_progress", "completed", "skipped"
    attempts = Column(Integer, default=0)
    best_score = Column(Integer, default=0)  # NEW: Best score achieved
    last_attempted = Column(TIMESTAMP(timezone=True))
    solved_at = Column(TIMESTAMP(timezone=True))
    bookmarked = Column(Boolean, default=False)
    notes = Column(Text)
    time_spent_total_seconds = Column(Integer, default=0)  # NEW: Total time spent

# NEW: Question Reviews/Ratings
class QuestionReview(Base):
    __tablename__ = "question_reviews"
    
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review_text = Column(Text)
    helpful_votes = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

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