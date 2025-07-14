from fastapi import FastAPI, Depends, HTTPException, status, Response, BackgroundTasks, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
import services, models, schemas
from db import get_db, engine
from sqlalchemy.orm import Session
from auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from email_service import send_password_reset_email
from typing import Optional
import math

app = FastAPI()

# CORS middleware - IMPORTANT: This must be configured correctly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  
    allow_credentials=True,  
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
        value=access_token,
        httponly=False,  # Set to False so JavaScript can read it
        secure=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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


# Question CRUD Endpoints
@app.post("/questions", response_model=schemas.QuestionResponse)
def create_question(
    question: schemas.QuestionCreate,
    db: Session = Depends(get_db),
    current_user : models.User = Depends(get_current_user)
) : 
    return services.create_question(db, question, current_user.id)

    
@app.get("/questions", response_model=schemas.QuestionListResponse)
def get_questions(
    db: Session = Depends(get_db)
):
    """Get all questions without filtering and pagination"""
    
    # Call service without any parameters to get all questions
    questions, total = services.get_questions(db)
    
    # Debug logging
    print(f"API returning: {len(questions)} questions")
    print(f"Question IDs: {[q.id for q in questions]}")
    
    return {
        "questions": questions,
        "total": total,
        "page": 1,
        "per_page": total,  # Return all questions in one page
        "total_pages": 1
    }
@app.get("/questions/{question_id}", response_model=schemas.QuestionResponse)
def get_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific question by ID"""
    question = services.get_question_by_id(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    return question

@app.put("/questions/{question_id}", response_model=schemas.QuestionResponse)
def update_question(
    question_id: int,
    question_update: schemas.QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a question"""
    # Check if question exists
    existing_question = services.get_question_by_id(db, question_id)
    if not existing_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Validate category exists if provided
    if question_update.category_id:
        category = services.get_question_category_by_id(db, question_update.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category does not exist"
            )
    
    updated_question = services.update_question(db, question_id, question_update)
    return updated_question

@app.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a question"""
    success = services.delete_question(db, question_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    return {"message": "Question deleted successfully"}

# Question Categories CRUD Endpoints
@app.post("/question-categories", response_model=schemas.QuestionCategoryResponse)
def create_question_category(
    category: schemas.QuestionCategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new question category"""
    try:
        return services.create_question_category(db, category)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.get("/question-categories", response_model=schemas.QuestionCategoryListResponse)
def get_question_categories(db: Session = Depends(get_db)):
    """Get all question categories"""
    categories = services.get_question_categories(db)
    return {
        "categories": categories,
        "total": len(categories)
    }

@app.get("/question-categories/{category_id}", response_model=schemas.QuestionCategoryResponse)
def get_question_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific question category by ID"""
    category = services.get_question_category_by_id(db, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category

@app.put("/question-categories/{category_id}", response_model=schemas.QuestionCategoryResponse)
def update_question_category(
    category_id: int,
    category_update: schemas.QuestionCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a question category"""
    try:
        updated_category = services.update_question_category(db, category_id, category_update)
        if not updated_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        return updated_category
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.delete("/question-categories/{category_id}")
def delete_question_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a question category"""
    try:
        success = services.delete_question_category(db, category_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        return {"message": "Category deleted successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Get questions by category
@app.get("/question-categories/{category_id}/questions", response_model=schemas.QuestionListResponse)
def get_questions_by_category(
    category_id: int,
    page: int = 1,
    per_page: int = 10,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all questions in a specific category"""
    # Check if category exists
    category = services.get_question_category_by_id(db, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 10
    
    # Calculate offset
    skip = (page - 1) * per_page
    
    # Get questions in this category
    questions, total = services.get_questions(
        db, 
        skip=skip, 
        limit=per_page,
        category_id=category_id,
        difficulty=difficulty,
        search=search
    )
    
    # Calculate total pages
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    
    return {
        "questions": questions,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }

#Question Tags CRUD Endpoints
@app.get("/questions/{question_id}/tags", response_model=list[schemas.TagResponse])
def get_tags_for_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """Get all tags for a question"""
    tags = (
        db.query(models.Tag)
        .join(models.QuestionTag, models.Tag.id == models.QuestionTag.tag_id)
        .filter(models.QuestionTag.question_id == question_id)
        .all()
    )
    return tags


@app.post("/questions/{question_id}/tags", response_model=list[schemas.TagResponse])
def add_tags_to_question(
    question_id: int,
    tags: list[schemas.TagCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Add tags to a question (creates tags if they don't exist)"""
    question = services.get_question_by_id(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    # Only creator can add tags (or add admin check)
    if question.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to add tags to this question")

    tag_objs = []
    for tag_data in tags:
        tag = services.get_or_create_tag(db, tag_data.name)
        # Check if already tagged
        exists = db.query(models.QuestionTag).filter_by(
            question_id=question_id, tag_id=tag.id
        ).first()
        if not exists:
            db.add(models.QuestionTag(question_id=question_id, tag_id=tag.id))
            db.commit()
        tag_objs.append(tag)
    return tag_objs

# User Answers CRUD Endpoints
@app.post("/answers", response_model=schemas.UserAnswerResponse)
def create_user_answer(
    answer: schemas.UserAnswerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Submit a new answer to a question"""
    try:
        return services.create_user_answer(db, answer, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/answers/{answer_id}", response_model=schemas.UserAnswerResponse)
def get_user_answer(
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific user answer"""
    answer = services.get_user_answer_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this answer")
    return answer

@app.put("/answers/{answer_id}", response_model=schemas.UserAnswerResponse)
def update_user_answer(
    answer_id: int,
    answer_update: schemas.UserAnswerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a user answer"""
    answer = services.get_user_answer_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this answer")
    updated = services.update_user_answer(db, answer_id, answer_update)
    return updated

@app.get("/my-answers", response_model=schemas.UserAnswerListResponse)
def get_my_answers(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    question_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all answers submitted by the current user"""
    skip = (page - 1) * per_page
    answers, total = services.get_user_answers(
        db,
        user_id=current_user.id,
        question_id=question_id,
        skip=skip,
        limit=per_page
    )
    total_pages = max(1, math.ceil(total / per_page))
    return {
        "answers": answers,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }