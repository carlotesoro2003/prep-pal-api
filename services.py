from models import User, PasswordResetToken, Question, QuestionCategory, TestCase, UserAnswer, Tag, QuestionTag, InterviewSession, SessionQuestion
from sqlalchemy import or_, and_, func, desc
from sqlalchemy.orm import Session, joinedload, selectinload
from schemas import (
    UserCreate, UserUpdate,
    QuestionCreate, QuestionUpdate, QuestionCategoryCreate, QuestionCategoryUpdate,
    TestCaseCreate, TestCaseUpdate, UserAnswerCreate, UserAnswerUpdate, TagCreate, InterviewSessionCreate, 
    InterviewSessionUpdate, SessionQuestionCreate
)
from auth import get_password_hash
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

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
        full_name=user.full_name,  
        avatar_url=user.avatar_url,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

#update user inifo
def update_user(db: Session, user_id: int, user_update: UserUpdate):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    update_data = user_update.dict(exclude_unset=True)
    first_name = update_data.get("first_name", user.first_name)
    last_name = update_data.get("last_name", user.last_name)
    bio = update_data.get("bio", user.bio)
    update_data["full_name"] = f"{first_name} {last_name}".strip()
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user

# Password Reset Services Functions
def create_password_reset_token(db: Session, user_id: int) -> str:
    """Create a new password reset token for a user"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    
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

# Question Category Services - USING THE IMPORTS LIKE A SMART PERSON
def create_question_category(db: Session, category: QuestionCategoryCreate) -> QuestionCategory:
    """Create a new question category"""
    existing_category = db.query(QuestionCategory).filter(
        QuestionCategory.name.ilike(category.name)
    ).first()
    
    if existing_category:
        raise ValueError("Category name already exists")
    
    # Use the schema directly with **category.dict()
    db_category = QuestionCategory(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def get_question_categories(db: Session) -> List[QuestionCategory]:
    """Get all question categories"""
    return db.query(QuestionCategory).order_by(QuestionCategory.name).all()

def get_question_category_by_id(db: Session, category_id: int) -> Optional[QuestionCategory]:
    """Get a question category by ID"""
    return db.query(QuestionCategory).filter(QuestionCategory.id == category_id).first()

def update_question_category(db: Session, category_id: int, category_update: QuestionCategoryUpdate) -> Optional[QuestionCategory]:
    """Update a question category"""
    db_category = get_question_category_by_id(db, category_id)
    if not db_category:
        return None
    
    if category_update.name and category_update.name != db_category.name:
        existing_category = db.query(QuestionCategory).filter(
            QuestionCategory.name.ilike(category_update.name),
            QuestionCategory.id != category_id
        ).first()
        
        if existing_category:
            raise ValueError("Category name already exists")
    
    # Use exclude_unset=True to only update provided fields
    update_data = category_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_category, field, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_question_category(db: Session, category_id: int) -> bool:
    """Delete a question category"""
    db_category = get_question_category_by_id(db, category_id)
    if not db_category:
        return False
    
    questions_count = db.query(Question).filter(Question.category_id == category_id).count()
    if questions_count > 0:
        raise ValueError(f"Cannot delete category. It has {questions_count} associated questions.")
    
    db.delete(db_category)
    db.commit()
    return True

# Test Case Services - ACTUALLY USING THE IMPORTS
def create_test_case(db: Session, test_case: TestCaseCreate, question_id: int) -> TestCase:
    """Create a test case for a question"""
    db_test_case = TestCase(**test_case.dict(), question_id=question_id)
    db.add(db_test_case)
    db.commit()
    db.refresh(db_test_case)
    return db_test_case

def get_test_cases_by_question(db: Session, question_id: int) -> List[TestCase]:
    """Get all test cases for a question"""
    return db.query(TestCase).filter(TestCase.question_id == question_id).all()

def update_test_case(db: Session, test_case_id: int, test_case_update: TestCaseUpdate) -> Optional[TestCase]:
    """Update a test case"""
    db_test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not db_test_case:
        return None
    
    update_data = test_case_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_test_case, field, value)
    
    db.commit()
    db.refresh(db_test_case)
    return db_test_case

def delete_test_case(db: Session, test_case_id: int) -> bool:
    """Delete a test case"""
    db_test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not db_test_case:
        return False
    
    db.delete(db_test_case)
    db.commit()
    return True

# Question Services - WITH PROPER EAGER LOADING
def create_question(
    db: Session, 
    question_data: QuestionCreate, 
    created_by: int
) -> Question:
    """Create a question with tags and test cases"""
    
    # Create the question
    question = Question(
        title=question_data.title,
        description=question_data.description,
        category_id=question_data.category_id,
        difficulty=question_data.difficulty,
        question_type=question_data.question_type,
        starter_code=question_data.starter_code,
        solution_code=question_data.solution_code,
        time_limit=question_data.time_limit,
        memory_limit=question_data.memory_limit,
        status=question_data.status,
        is_public=question_data.is_public,
        created_by=created_by,
        function_name=question_data.function_name,
        parameters=[p.dict() for p in question_data.parameters] if question_data.parameters else None,
    )
    
    db.add(question)
    db.flush()  # Get the question ID
    
    # Add test cases
    if question_data.test_cases:
        for test_case_data in question_data.test_cases:
            test_case = TestCase(
                question_id=question.id,
                input_data=test_case_data.input_data,
                expected_output=test_case_data.expected_output,
                is_sample=test_case_data.is_sample,
                points=test_case_data.points,
                description=test_case_data.description
            )
            db.add(test_case)
    
    # Add tags
    if question_data.tags:
        for tag_data in question_data.tags:
            # Check if tag exists
            tag = db.query(Tag).filter(Tag.name == tag_data.name).first()
            if not tag:
                tag = Tag(name=tag_data.name)
                db.add(tag)
                db.flush()
            
            # Create question-tag relationship
            question_tag = QuestionTag(
                question_id=question.id,
                tag_id=tag.id
            )
            db.add(question_tag)
    
    db.commit()
    db.refresh(question)
    
    # Load relationships
    question = db.query(Question).options(
        joinedload(Question.category),
        selectinload(Question.test_cases)
    ).filter(Question.id == question.id).first()
    
    # Load tags
    tag_objs = (
        db.query(Tag)
        .join(QuestionTag, Tag.id == QuestionTag.tag_id)
        .filter(QuestionTag.question_id == question.id)
        .all()
    )
    question.tags = tag_objs
    
    return question

def get_question_by_id(db: Session, question_id: int) -> Optional[Question]:
    question = db.query(Question).options(
        joinedload(Question.category),
        selectinload(Question.test_cases)
    ).filter(Question.id == question_id).first()
    if question:
        # Attach tags
        tag_objs = (
            db.query(Tag)
            .join(QuestionTag, Tag.id == QuestionTag.tag_id)
            .filter(QuestionTag.question_id == question_id)
            .all()
        )
        question.tags = tag_objs  # Dynamically attach for schema
    return question

def get_questions(
    db: Session, 

) -> Tuple[List[Question], int]:
    """Get all questions without filtering and pagination"""
    
    # Build the base query
    query = db.query(Question).options(
        joinedload(Question.category),
        selectinload(Question.test_cases)
    )
    
    # Remove all filters - just get all questions
    # No filters applied
    
    # Get total count
    total = query.count()
    
    # Get all questions without pagination, ordered by creation date
    questions = query.order_by(desc(Question.created_at)).all()
    
    # Debug logging
    print(f"Total questions found: {total}")
    print(f"Questions returned: {len(questions)}")
    print(f"Question IDs: {[q.id for q in questions]}")
    
    # Add tags to questions
    for question in questions:
        tag_objs = (
            db.query(Tag)
            .join(QuestionTag, Tag.id == QuestionTag.tag_id)
            .filter(QuestionTag.question_id == question.id)
            .all()
        )
        question.tags = tag_objs
    
    return questions, total

def update_question(db: Session, question_id: int, question_update: QuestionUpdate) -> Optional[Question]:
    """Update a question"""
    db_question = get_question_by_id(db, question_id)
    if not db_question:
        return None

    update_data = question_update.dict(exclude_unset=True)
    # Ensure parameters is a list of dicts if present
    if "parameters" in update_data and update_data["parameters"]:
        update_data["parameters"] = [p.dict() if hasattr(p, "dict") else p for p in update_data["parameters"]]
    for field, value in update_data.items():
        setattr(db_question, field, value)

    db.commit()
    db.refresh(db_question)
    return db_question

def delete_question(db: Session, question_id: int) -> bool:
    """Delete a question"""
    db_question = get_question_by_id(db, question_id)
    if not db_question:
        return False
    
    db.delete(db_question)
    db.commit()
    return True

# User Answer Services - USING THE SCHEMAS PROPERLY
def create_user_answer(db: Session, answer: UserAnswerCreate, user_id: int) -> UserAnswer:
    """Create a user answer"""
    question = get_question_by_id(db, answer.question_id)
    if not question:
        raise ValueError("Question not found")
    
    #calculate score and correctness base on test results
    is_correct = False
    test_cases_passed = 0
    total_test_cases = 0
    score = 0

    if answer.test_results:
        total_test_cases = len(answer.test_results)
        test_cases_passed = sum(1 for result in answer.test_results if result.get("passed", False))
        is_correct = test_cases_passed == total_test_cases
        score = int((test_cases_passed / total_test_cases) * 100) if total_test_cases > 0 else 0

    db_answer = UserAnswer(
        user_id=user_id,
        question_id=answer.question_id,
        answer_content=answer.answer_content,
        answer_type=answer.answer_type,
        code_language=answer.code_language,
        test_results=answer.test_results,
        is_correct=is_correct,
        score=score,
        test_cases_passed=test_cases_passed,
        total_test_cases=total_test_cases
    )

    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return db_answer

def get_user_answers(
    db: Session,
    user_id: Optional[int] = None,
    question_id: Optional[int] = None
) -> Tuple[List[UserAnswer], int]:
    """Get user answers with filtering (no pagination)"""
    query = db.query(UserAnswer)
    
    filters = []
    if user_id:
        filters.append(UserAnswer.user_id == user_id)
    if question_id:
        filters.append(UserAnswer.question_id == question_id)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Fix: Change submitted_at to created_at
    query = query.order_by(desc(UserAnswer.created_at))
    
    answers = query.all()
    total = len(answers)
    
    return answers, total

def get_user_answer_by_id(db: Session, answer_id: int) -> Optional[UserAnswer]:
    """Get a user answer by ID"""
    return db.query(UserAnswer).filter(UserAnswer.id == answer_id).first()

def update_user_answer(db: Session, answer_id: int, answer_update: UserAnswerUpdate) -> Optional[UserAnswer]:
    """Update a user answer"""
    db_answer = get_user_answer_by_id(db, answer_id)
    if not db_answer:
        return None
    
    update_data = answer_update.dict(exclude_unset=True)

    if "question_id" in update_data and update_data["question_id"] is None:
        update_data.pop("question_id")

    if "test_results" in update_data:
        test_results = update_data["test_results"]
        
        if test_results:
            total_test_cases = len(test_results)
            test_cases_passed = sum(1 for result in test_results if result.get("passed", False))
            is_correct = test_cases_passed == total_test_cases
            score = int((test_cases_passed / total_test_cases) * 100) if total_test_cases > 0 else 0
            
            update_data.update({
                "is_correct": is_correct,
                "score": score,
                "test_cases_passed": test_cases_passed,
                "total_test_cases": total_test_cases
            })

    for field,value in update_data.items():
        setattr(db_answer, field, value)

    db.commit()
    db.refresh(db_answer)
    return db_answer



# Tag Services - SIMPLE AND CLEAN
def get_tags(db: Session) -> List[Tag]:
    """Get all tags"""
    return db.query(Tag).order_by(Tag.name).all()

def create_tag(db: Session, tag: TagCreate) -> Tag:
    """Create a new tag"""
    db_tag = Tag(**tag.dict())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def get_or_create_tag(db: Session, tag_name: str) -> Tag:
    """Get existing tag or create new one"""
    db_tag = db.query(Tag).filter(Tag.name == tag_name).first()
    if not db_tag:
        db_tag = create_tag(db, TagCreate(name=tag_name))
    return db_tag



#INTERVIEW SESSIONS SERVICES 
def create_interview_session(db: Session, session_data: InterviewSessionCreate, user_id: int):
    session = InterviewSession(
        user_id=user_id,
        title=session_data.title,
        type=session_data.type,
        difficulty=session_data.difficulty,
        scheduled_at=session_data.scheduled_at,
        end_at=session_data.end_at,
        feedback=session_data.feedback,
        rating=session_data.rating,
        recording_url=session_data.recording_url
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_interview_sessions(db: Session, user_id: int):
    sessions = db.query(InterviewSession).filter(InterviewSession.user_id == user_id).order_by(InterviewSession.scheduled_at.desc()).all()
    return sessions, len(sessions)

def get_interview_session_by_id(db: Session, session_id: int):
    return db.query(InterviewSession).filter(InterviewSession.id == session_id).first()


def update_interview_session(db: Session, session_id: int, session_update: InterviewSessionUpdate):
    session = get_interview_session_by_id(db, session_id)
    if not session:
        return None
    update_data = session_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session

def delete_interview_session(db: Session, session_id: int):
    session = get_interview_session_by_id(db, session_id)
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True


#SESSION QUESTIONS SERVICES
def add_session_question(db: Session, session_id: int, sq_data: SessionQuestionCreate):
    sq = SessionQuestion(
        session_id=session_id,  
        order_index=sq_data.order_index,
        question_title=sq_data.question_title,
        question_description=sq_data.question_description,
        question_type=sq_data.question_type,
        difficulty=sq_data.difficulty,
        user_answer=sq_data.user_answer,
        feedback=sq_data.feedback,
        time_spent_seconds=sq_data.time_spent_seconds
    )
    db.add(sq)
    db.commit()
    db.refresh(sq)
    return sq