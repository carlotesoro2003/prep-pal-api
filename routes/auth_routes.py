from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timedelta
from jose import JWTError, jwt
from schemas import UserUpdate
import services, models, schemas
from db import get_db
from auth import (
    authenticate_user, create_access_token, create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, SECRET_KEY, ALGORITHM
)
from email_service import send_password_reset_email

router = APIRouter()


# Registration endpoint
@router.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = services.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    new_user = services.create_user(db, user)
    return new_user

# Login endpoint
@router.post("/token")
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"id": user.id, "email": user.email, "full_name": user.full_name},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(
        data={"id": user.id, "email": user.email, "full_name": user.full_name}
    )
    
    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Set to False so JavaScript can read it
        secure=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )

    #Set httpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/"
    )
    
    print(f"Setting cookie with token: {access_token[:20]}...")
    
    # Return token in response body
    response_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Login successful"
    }
    print(f"Returning response: {response_data}")
    return response_data


#Refresh token endpoint
@router.post("/refresh-token")
def refresh_access_token(
    response: Response,
    refresh_token: str = Body(...),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        user_id = payload.get("id")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        access_token = create_access_token(
            data={"id": user.id, "email": user.email, "full_name": user.full_name}
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# Current user endpoint
@router.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/users/me", response_model=schemas.UserResponse)
def update_profile(user_update: UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    updated = services.update_user(db, current_user.id, user_update)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated


# Logout endpoint
@router.post("/logout")
def logout(response: Response):
    # Log before attempting to delete cookie
    # print("Logout endpoint called. Attempting to delete access_token cookie.")
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        path="/"
    )
    # Also delete refresh_token for completeness
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        samesite="lax",
        path="/"
    )
    # print("Logout endpoint: access_token and refresh_token cookies deleted (if present).")
    return {"message": "Logged out successfully"}


# Forgot Password endpoint
@router.post("/forgot-password", response_model=schemas.PasswordResetResponse)
async def forgot_password(
    background_tasks: BackgroundTasks,
    request: schemas.PasswordResetRequest,
    db: Session = Depends(get_db)
):
    # Check if user exists
    user = services.get_user_by_email(db, request.email)
    
    # Always return success message for security (don't reveal if email exists)
    if not user:
        return {"message": "If an account with this email exists, you will receive a password reset link."}
    
    # Clean up expired tokens
    services.cleanup_expired_tokens(db)
    
    # Create reset token
    reset_token = services.create_password_reset_token(db, user.id)
    
    # Send email in background
    background_tasks.add_task(
        send_password_reset_email,
        request.email,
        reset_token,
        user.full_name
    )
    
    return {"message": "If an account with this email exists, you will receive a password reset link."}

# Reset Password endpoint
@router.post("/reset-password", response_model=schemas.PasswordResetResponse)
async def reset_password(
    request: schemas.PasswordRestConfirm,
    db: Session = Depends(get_db)
):
    # Get the reset token
    token_record = services.get_password_reset_token(db, request.token)
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update the user's password
    success = services.update_user_password(db, token_record.user_id, request.new_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
    
    # Mark token as used
    services.use_password_reset_token(db, request.token)
    
    return {"message": "Password has been reset successfully"}

# Validate Reset Token endpoint (optional - for frontend validation)
@router.get("/validate-reset-token/{token}")
async def validate_reset_token(token: str, db: Session = Depends(get_db)):
    token_record = services.get_password_reset_token(db, token)
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"message": "Token is valid"}

# Protected route
@router.get("/protected")
def protected_route(current_user: models.User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.full_name}, you have access to this protected route!"}