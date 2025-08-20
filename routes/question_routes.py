from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Optional
import math

import services, models, schemas
from db import get_db
from auth import get_current_user

router = APIRouter()



# Question CRUD Endpoints
@router.post("/questions", response_model=schemas.QuestionResponse)
def create_question(
    question: schemas.QuestionCreate,
    db: Session = Depends(get_db),
    current_user : models.User = Depends(get_current_user)
) : 
    return services.create_question(db, question, current_user.id)

    
@router.get("/questions", response_model=schemas.QuestionListResponse)
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
@router.get("/questions/{question_id}", response_model=schemas.QuestionResponse)
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

@router.put("/questions/{question_id}", response_model=schemas.QuestionResponse)
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

@router.delete("/questions/{question_id}")
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
@router.post("/question-categories", response_model=schemas.QuestionCategoryResponse)
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

@router.get("/question-categories", response_model=schemas.QuestionCategoryListResponse)
def get_question_categories(db: Session = Depends(get_db)):
    """Get all question categories"""
    categories = services.get_question_categories(db)
    return {
        "categories": categories,
        "total": len(categories)
    }

@router.get("/question-categories/{category_id}", response_model=schemas.QuestionCategoryResponse)
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

@router.put("/question-categories/{category_id}", response_model=schemas.QuestionCategoryResponse)
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

@router.delete("/question-categories/{category_id}")
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
@router.get("/question-categories/{category_id}/questions", response_model=schemas.QuestionListResponse)
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
@router.get("/questions/{question_id}/tags", response_model=list[schemas.TagResponse])
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


@router.post("/questions/{question_id}/tags", response_model=list[schemas.TagResponse])
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
