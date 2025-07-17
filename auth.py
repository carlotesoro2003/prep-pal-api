from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Response, Cookie, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from db import get_db
from models import User
import os
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Secret key for JWT encoding/decoding
SECRET_KEY = os.getenv("SECRET_KEY")
# Algorithm used for JWT
ALGORITHM = "HS256"
# Token expiration time in minutes
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# OAuth2 password bearer token - SET auto_error=False to allow cookie fallback
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Function to verify password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Function to hash password
def get_password_hash(password: str):
    return pwd_context.hash(password)

# GET USER BY EMAIL
def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

# Authenticate user
def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return False
    return user

# Create access token
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

#Create refresh token
def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) or timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# FIXED: Updated get_current_user function
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Try to get token from cookie first
    cookie_token = request.cookies.get("access_token")
    
    # Try to get token from Authorization header
    auth_header = request.headers.get("Authorization")
    header_token = None
    if auth_header and auth_header.startswith("Bearer "):
        header_token = auth_header.replace("Bearer ", "")
    
    # Use cookie token first, then header token, then the token from oauth2_scheme
    if cookie_token:
        token = cookie_token
    elif header_token:
        token = header_token
    elif token:
        # Remove "Bearer " prefix if present from oauth2_scheme
        token = token.replace("Bearer ", "")
    
    # If no token from any source, raise exception
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user