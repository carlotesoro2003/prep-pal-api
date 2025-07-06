from models import User, PasswordResetToken
from sqlalchemy.orm import Session
from schemas import UserCreate, PasswordResetRequest, PasswordRestConfirm
from auth import get_password_hash
import secrets
from datetime import datetime, timedelta, timezone

#User Services Functions 
def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

#create a new user
def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email, 
        password_hash=hashed_password,
        last_name=user.last_name,
        first_name=user.first_name,
        full_name = user.first_name + " " + user.last_name,
        avatar_url=user.avatar_url,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Password Reset Services Functions
def create_password_reset_token(db: Session, user_id: int) -> str:
    """Create a new password reset token for a user"""
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    
    # Set expiration time (1 hour from now)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
    # Create the token record
    db_token = PasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    
    return token

def get_password_reset_token(db: Session, token: str):
    """Get a password reset token if it's valid and not expired"""
    return db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()

def use_password_reset_token(db: Session, token: str) -> bool:
    """Mark a password reset token as used"""
    db_token = get_password_reset_token(db, token)
    if db_token:
        db_token.used = True
        db.commit()
        return True
    return False

def update_user_password(db: Session, user_id: int, new_password: str) -> bool:
    """Update a user's password"""
    user = get_user_by_id(db, user_id)
    if user:
        user.password_hash = get_password_hash(new_password)
        db.commit()
        return True
    return False

def cleanup_expired_tokens(db: Session):
    """Clean up expired password reset tokens"""
    db.query(PasswordResetToken).filter(
        PasswordResetToken.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.commit()