from fastapi import FastAPI, Depends, HTTPException, status, Response, BackgroundTasks, Body, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
import services, models, schemas
from db import get_db, engine
from sqlalchemy.orm import Session
from auth import authenticate_user, create_access_token, create_refresh_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from email_service import send_password_reset_email
from typing import Optional, List
import math
import subprocess
import tempfile
import os   
import time
import signal
from schemas import InterviewSessionCreate, InterviewSessionUpdate, InterviewSessionResponse, InterviewSessionListResponse, SessionQuestionResponse, RecordingUrlRequest, AIChatInterviewStartRequest, AIChatInterviewStartResponse, AIChatMessageRequest, AIChatMessageResponse
from jose import JWTError, jwt
from auth import SECRET_KEY, ALGORITHM
from gemini_ai import generate_interview_questions, ai_employer_feedback
from routes import websocket_routes, notification_routes
from notif_service import notification_service
import asyncio
from contextlib import asynccontextmanager


# Initialize FastAPI app
app = FastAPI()

# CORS middleware - IMPORTANT: This must be configured correctly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  
    allow_credentials=True,  
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(websocket_routes.router)
app.include_router(notification_routes.router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event to start notification scheduler"""
    # Start the notification service scheduler
    await notification_service.start_notification_scheduler()
    yield
    # Stop the notification service scheduler
    notification_service.stop_notification_scheduler()
    

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
@app.post("/refresh-token")
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
def create_answer(
    answer: schemas.UserAnswerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print("Received answer submission:", answer)
    try:
        db_answer = services.create_user_answer(db, answer, current_user.id)
        return db_answer
    except ValueError as e:
        print("ValueError:", e)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print("Exception:", e)
        raise HTTPException(status_code=500, detail=f"Failed to create answer: {str(e)}")
    

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
    question_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all answers submitted by the current user"""
    answers, total = services.get_user_answers(
        db,
        user_id=current_user.id,
        question_id=question_id
    )
    return {
        "answers": answers,
        "total": total,
        "page": 1,
        "per_page": total,
        "total_pages": 1
    }


@app.post("/code/run", response_model=schemas.CodeExecutionResponse)
async def run_code(
    request: schemas.CodeExecutionRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Execute code against test cases"""
    try:
        results = []
        # Use the provided time_limit or default to 5 seconds
        time_limit = getattr(request, "time_limit", 5)
        for test_case in request.test_cases:
            result = await execute_code_safely(
                code=request.code,
                language=request.language,
                input_data=test_case.get("input_data", ""),
                expected_output=test_case.get("expected_output", ""),
                timeout=time_limit  # Use the time limit per question
            )
            results.append(result)

        return {"results": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
async def execute_code_safely(code: str, language: str, input_data: str, expected_output: str, timeout: int = 5):
    """Execute code with proper error handling and security"""
    start_time = time.time()
    
    try:
        if language == "python":
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                # Add input processing to the code
                modified_code = f"""
import sys
import json

# User's code
{code}

# Process input
try:
    input_data = '''{input_data}'''
    if input_data.strip():
        # Try to parse as JSON first, then as string
        try:
            parsed_input = json.loads(input_data)
        except:
            parsed_input = input_data.strip()
        
        # If there's a main function, call it
        if 'def main(' in '''{code}''':
            result = main(parsed_input)
            print(json.dumps(result) if not isinstance(result, str) else result)
        else:
            # Look for a function that matches common naming patterns
            import re
            function_match = re.search(r'def\\s+(\\w+)\\s*\\([^)]*\\):', '''{code}''')
            if function_match:
                function_name = function_match.group(1)
                if function_name != 'main':
                    result = eval(f'{{function_name}}(parsed_input)')
                    print(json.dumps(result) if not isinstance(result, str) else result)
            else:
                # Execute the code and capture any print statements
                exec(compile('''{code}''', '<string>', 'exec'))
    else:
        # Just execute the code
        exec(compile('''{code}''', '<string>', 'exec'))
except Exception as e:
    print(f"Error: {{e}}")
    sys.exit(1)
"""
                f.write(modified_code)
                temp_file = f.name
            
            # Execute with timeout and resource limits
            process = subprocess.Popen(
                ["python", temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                actual_output = stdout.strip()
                error_message = stderr.strip() if stderr else None
                
                # Clean up
                os.unlink(temp_file)
                
            except subprocess.TimeoutExpired:
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                process.wait()
                os.unlink(temp_file)
                
                return {
                    "input": input_data,
                    "expected_output": expected_output,
                    "actual_output": "",
                    "passed": False,
                    "execution_time": timeout * 1000,
                    "memory_usage": 0,
                    "error_message": "Time limit exceeded"
                }
                
        elif language == "javascript":
            # For Node.js execution
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                modified_code = f"""
const input_data = `{input_data}`;

// User's code
{code}

// Try to execute main function if exists
try {{
    if (typeof main === 'function') {{
        let parsedInput;
        try {{
            parsedInput = JSON.parse(input_data);
        }} catch {{
            parsedInput = input_data.trim();
        }}
        const result = main(parsedInput);
        console.log(typeof result === 'string' ? result : JSON.stringify(result));
    }} else {{
        // Look for any function and try to call it
        const functionMatch = `{code}`.match(/function\\s+(\\w+)\\s*\\([^)]*\\)/);
        if (functionMatch) {{
            const functionName = functionMatch[1];
            let parsedInput;
            try {{
                parsedInput = JSON.parse(input_data);
            }} catch {{
                parsedInput = input_data.trim();
            }}
            const result = eval(`${{functionName}}(parsedInput)`);
            console.log(typeof result === 'string' ? result : JSON.stringify(result));
        }}
    }}
}} catch (e) {{
    console.error('Error:', e.message);
    process.exit(1);
}}
"""
                f.write(modified_code)
                temp_file = f.name
            
            process = subprocess.Popen(
                ["node", temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                actual_output = stdout.strip()
                error_message = stderr.strip() if stderr else None
                
                os.unlink(temp_file)
                
            except subprocess.TimeoutExpired:
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                process.wait()
                os.unlink(temp_file)
                
                return {
                    "input": input_data,
                    "expected_output": expected_output,
                    "actual_output": "",
                    "passed": False,
                    "execution_time": timeout * 1000,
                    "memory_usage": 0,
                    "error_message": "Time limit exceeded"
                }
                
        else:
            return {
                "input": input_data,
                "expected_output": expected_output,
                "actual_output": "",
                "passed": False,
                "execution_time": 0,
                "memory_usage": 0,
                "error_message": f"Language {language} not supported"
            }
        
        execution_time = int((time.time() - start_time) * 1000)  # Convert to ms
        
        # Compare outputs (normalize whitespace)
        actual_normalized = actual_output.strip()
        expected_normalized = expected_output.strip()
        passed = actual_normalized == expected_normalized
        
        return {
            "input": input_data,
            "expected_output": expected_output,
            "actual_output": actual_output,
            "passed": passed,
            "execution_time": execution_time,
            "memory_usage": 0,  # Would need system monitoring for real memory usage
            "error_message": error_message
        }
        
    except Exception as e:
        return {
            "input": input_data,
            "expected_output": expected_output,
            "actual_output": "",
            "passed": False,
            "execution_time": 0,
            "memory_usage": 0,
            "error_message": str(e)
        }
    

#INTERVIEW SESSION CRUD ENDPOINTS
@app.post("/interview-sessions", response_model=InterviewSessionResponse)
def create_interview_session(
    session_data: InterviewSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.create_interview_session(db, session_data, current_user.id)
    return session

@app.get("/interview-sessions", response_model=InterviewSessionListResponse)
def get_interview_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    sessions, total = services.get_interview_sessions(db, current_user.id)
    return {"sessions": sessions, "total": total}

@app.get("/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
def get_interview_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.get_interview_session_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.put("/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
def update_interview_session(
    session_id: int,
    session_update: InterviewSessionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.get_interview_session_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    updated = services.update_interview_session(db, session_id, session_update)
    return updated

@app.delete("/interview-sessions/{session_id}")
def delete_interview_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.get_interview_session_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    success = services.delete_interview_session(db, session_id)
    return {"success": success}

@app.post("/interview-sessions/{session_id}/recording")
def save_recording_url(
    session_id: int,
    req: RecordingUrlRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.get_interview_session_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.recording_url = req.recording_url
    db.commit()
    return {"success": True}

# SESSION QUESTION CRUD ENDPOINTS
@app.post("/interview-sessions/{session_id}/questions", response_model=SessionQuestionResponse)
def add_session_question(
    session_id: int,
    sq_data: schemas.SessionQuestionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.get_interview_session_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    sq = services.add_session_question(db, session_id, sq_data)
    return sq

#AI INTERVIEW SESSION ENDPOINT
@app.post("/ai-interview-sesssions", response_model= InterviewSessionResponse)
def create_ai_interview_session(
    session_data: schemas.InterviewSessionCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Create the interview session
    session = services.create_interview_session(db, session_data, current_user.id)
    # 2. Generate AI questions
    questions = generate_interview_questions(session_data.title, session_data.difficulty)
    # 3. Store questions in SessionQuestion
    for idx, q in enumerate(questions):
        sq_data = schemas.SessionQuestionCreate(
            order_index=idx,
            question_title=q.get("title"),
            question_description=q.get("description"),
            question_type=q.get("type", "theory"),
            difficulty=q.get("difficulty", session_data.difficulty)
        )
        services.add_session_question(db, session.id, sq_data)
    return session


@app.post("/ai-feedback")
def ai_feedback(
    question: str = Body(...),
    answer: str = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    feedback = ai_employer_feedback(question, answer)
    return {"feedback": feedback}


@app.post("/ai-chat-interview/start", response_model=AIChatInterviewStartResponse)
def ai_chat_interview_start(
    req: AIChatInterviewStartRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    questions = generate_interview_questions(req.role, intro=req.intro)
    if not questions or not isinstance(questions, list):
        raise HTTPException(status_code=500, detail="AI did not return questions.")
    first_q = questions[0]
    # Format the first question for the chat
    ai_message = (
        f"Thank you for sharing! Let's start your mock interview for the {req.role} position.\n"
        f"Here is your first question:\n\n"
        f"{first_q.get('title', '')}\n{first_q.get('description', '')}"
    )
    return {"ai_message": ai_message, "questions": questions}

@app.post("/ai-chat-interview/message", response_model=AIChatMessageResponse)
def ai_chat_interview_message(
    req: AIChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Get AI feedback for the user's answer
    feedback = ai_employer_feedback(req.question, req.answer)
    ai_message = "Thank you for your answer! Here is my feedback and the next question (if any)."
    return {"ai_message": ai_message, "feedback": feedback}