from models import User, PasswordResetToken, Question, QuestionCategory, TestCase, UserAnswer, Tag, QuestionTag
from sqlalchemy import or_, and_, func, desc
from sqlalchemy.orm import Session, joinedload, selectinload
from schemas import (
    UserCreate, PasswordResetRequest, PasswordRestConfirm, 
    QuestionCreate, QuestionUpdate, QuestionCategoryCreate, QuestionCategoryUpdate,
    TestCaseCreate, TestCaseUpdate, UserAnswerCreate, UserAnswerUpdate, TagCreate
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
        full_name=user.full_name,  # Use the provided full_name from schema
        avatar_url=user.avatar_url,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

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
def create_question(db: Session, question: QuestionCreate, created_by: int) -> Question:
    """Create a new question with test cases"""
    # Extract test cases before creating question
    test_cases_data = question.test_cases or []
    question_data = question.dict(exclude={"test_cases"})
    
    # Create the question
    db_question = Question(**question_data, created_by=created_by)
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    
    # Create test cases if provided
    for test_case_data in test_cases_data:
        create_test_case(db, test_case_data, db_question.id)
    
    # Return question with all related data
    return get_question_by_id(db, db_question.id)

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
    skip: int = 0, 
    limit: int = 100,
    category_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    question_type: Optional[str] = None,
    status: Optional[str] = None,
    created_by: Optional[int] = None,
    search: Optional[str] = None,
    is_public: Optional[bool] = None
) -> Tuple[List[Question], int]:
    """Get questions with filtering and eager loading"""
    # Base query with eager loading
    query = db.query(Question).options(
        joinedload(Question.category),
        selectinload(Question.test_cases)
    )
    
    # Build filters list
    filters = []
    
    if category_id:
        filters.append(Question.category_id == category_id)
    if difficulty:
        filters.append(Question.difficulty == difficulty)
    if question_type:
        filters.append(Question.question_type == question_type)
    if status:
        filters.append(Question.status == status)
    else:
        filters.append(Question.status == "published")  # Default to published
    if created_by:
        filters.append(Question.created_by == created_by)
    if is_public is not None:
        filters.append(Question.is_public == is_public)
    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(
                Question.title.ilike(search_term),
                Question.description.ilike(search_term)
            )
        )
    
    # Apply all filters at once
    if filters:
        query = query.filter(and_(*filters))
    
    # Order by creation date
    query = query.order_by(desc(Question.created_at))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    questions = query.offset(skip).limit(limit).all()

    for q in questions:
        tag_objs = (
            db.query(Tag)
            .join(QuestionTag, Tag.id == QuestionTag.tag_id)
            .filter(QuestionTag.question_id == q.id)
            .all()
        )
        q.tags = tag_objs
    
    return questions, total

def update_question(db: Session, question_id: int, question_update: QuestionUpdate) -> Optional[Question]:
    """Update a question"""
    db_question = get_question_by_id(db, question_id)
    if not db_question:
        return None
    
    update_data = question_update.dict(exclude_unset=True)
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
    # Check if question exists
    question = get_question_by_id(db, answer.question_id)
    if not question:
        raise ValueError("Question not found")
    
    # Create answer using schema
    db_answer = UserAnswer(**answer.dict(), user_id=user_id)
    
    # Set test case info for coding questions
    if question.question_type == "coding":
        db_answer.total_test_cases = len(question.test_cases)
        # TODO: Implement code execution logic
        db_answer.test_cases_passed = 0
        db_answer.is_correct = False
        db_answer.score = 0
    
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return db_answer

def get_user_answers(
    db: Session,
    user_id: Optional[int] = None,
    question_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[UserAnswer], int]:
    """Get user answers with filtering"""
    query = db.query(UserAnswer)
    
    filters = []
    if user_id:
        filters.append(UserAnswer.user_id == user_id)
    if question_id:
        filters.append(UserAnswer.question_id == question_id)
    
    if filters:
        query = query.filter(and_(*filters))
    
    query = query.order_by(desc(UserAnswer.submitted_at))
    
    total = query.count()
    answers = query.offset(skip).limit(limit).all()
    
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
    for field, value in update_data.items():
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