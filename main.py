from fastapi import FastAPI, Depends, HTTPException, status, Response, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
import services, models, schemas
from db import get_db, engine
from sqlalchemy.orm import Session
from auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from email_service import send_password_reset_email

app = FastAPI()

# CORS middleware - IMPORTANT: This must be configured correctly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Add both
    allow_credentials=True,  # CRUCIAL for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "PrepPal API is running!", "version": "1.0.0"}

# Registration endpoint
@app.post("/register", response_model=schemas.UserResponse)
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
@app.post("/token")
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
    
    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    
    print(f"Setting cookie with token: {access_token[:20]}...")  # Debug log
    return {"message": "Login successful"}

# Current user endpoint
@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


# Logout endpoint
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        path="/"
    )
    return {"message": "Logged out successfully"}


# Forgot Password endpoint
@app.post("/forgot-password", response_model=schemas.PasswordResetResponse)
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
@app.post("/reset-password", response_model=schemas.PasswordResetResponse)
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
@app.get("/validate-reset-token/{token}")
async def validate_reset_token(token: str, db: Session = Depends(get_db)):
    token_record = services.get_password_reset_token(db, token)
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"message": "Token is valid"}

# Protected route
@app.get("/protected")
def protected_route(current_user: models.User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.full_name}, you have access to this protected route!"}