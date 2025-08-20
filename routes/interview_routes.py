from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import services, models, schemas
from db import get_db
from auth import get_current_user
from schemas import (
    InterviewSessionCreate,
    InterviewSessionUpdate,
    InterviewSessionResponse,
    InterviewSessionListResponse,
    SessionQuestionResponse,
    RecordingUrlRequest,
    AIChatInterviewStartRequest,
    AIChatInterviewStartResponse,
    AIChatMessageRequest,
    AIChatMessageResponse,
)
from gemini_ai import generate_interview_questions, ai_employer_feedback

router = APIRouter()


#INTERVIEW SESSION CRUD ENDPOINTS
@router.post("/interview-sessions", response_model=InterviewSessionResponse)
def create_interview_session(
    session_data: InterviewSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.create_interview_session(db, session_data, current_user.id)
    return session

@router.get("/interview-sessions", response_model=InterviewSessionListResponse)
def get_interview_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    sessions, total = services.get_interview_sessions(db, current_user.id)
    return {"sessions": sessions, "total": total}

@router.get("/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
def get_interview_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    session = services.get_interview_session_by_id(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.put("/interview-sessions/{session_id}", response_model=InterviewSessionResponse)
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

@router.delete("/interview-sessions/{session_id}")
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

@router.post("/interview-sessions/{session_id}/recording")
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
@router.post("/interview-sessions/{session_id}/questions", response_model=SessionQuestionResponse)
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
@router.post("/ai-interview-sesssions", response_model= InterviewSessionResponse)
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


@router.post("/ai-feedback")
def ai_feedback(
    question: str = Body(...),
    answer: str = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    feedback = ai_employer_feedback(question, answer)
    return {"feedback": feedback}


@router.post("/ai-chat-interview/start", response_model=AIChatInterviewStartResponse)
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

@router.post("/ai-chat-interview/message", response_model=AIChatMessageResponse)
def ai_chat_interview_message(
    req: AIChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Use follow_up_count from the request, default to 0 if not present
    follow_up_count = getattr(req, "follow_up_count", 0)
    feedback, follow_up, new_follow_up_count = ai_employer_feedback(req.question, req.answer, follow_up_count)
    ai_message = "Thank you for your answer! Here is my feedback and the next question (if any)."
    return {
        "ai_message": ai_message,
        "feedback": feedback,
        "followUpQuestion": follow_up,
        "follow_up_count": new_follow_up_count
    }

