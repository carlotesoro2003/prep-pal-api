from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime   
from enum import Enum

# Schemas for User 
class UserBase(BaseModel):
    last_name: str
    first_name: str
    email: str
    full_name: str
    avatar_url: Optional[str] = None 

class UserCreate(UserBase):
    password: str

    
    @field_validator('password')  
    @classmethod
    def validate_password(cls, value: str): 
        if len(value) < 5:
            raise ValueError("Password must be at least 5 characters long")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter")
        return value 

class UserResponse(UserBase):
    id: int
    created_at: datetime 
    updated_at: datetime  
    last_login: Optional[datetime] = None  

    class Config:
        from_attributes = True

# Schema for Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[int] = None
    email: Optional[str] = None
    full_name: Optional[str] = None

    @field_validator('id', 'email', 'full_name', mode='before')
    @classmethod
    def validate_optional_fields(cls, value):
        if value is None:
            return None
        return value
    
# Schema for Password Reset Request
class PasswordResetRequest(BaseModel):
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str):
        if not value or "@" not in value:
            raise ValueError("Invalid email address")
        return value
    
class PasswordRestConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator('token', 'new_password')
    @classmethod
    def validate_fields(cls, value: str):
        if not value:
            raise ValueError("This field cannot be empty")
        return value
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, value: str):
        if len(value) < 5:
            raise ValueError("Password must be at least 5 characters long")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in value):
            raise ValueError("Password must contain at least one letter")
        return value
    
class PasswordResetResponse(BaseModel):
    message: str

# Enums for better validation
class QuestionType(str, Enum):
    theory = "theory"
    coding = "coding"
    multiple_choice = "multiple_choice"

class QuestionStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"

# Question Category Schemas
class QuestionCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None

class QuestionCategoryCreate(QuestionCategoryBase):
    pass

class QuestionCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None

class QuestionCategoryResponse(QuestionCategoryBase):
    id: int

    class Config:
        from_attributes = True

class QuestionCategoryListResponse(BaseModel):
    categories: List[QuestionCategoryResponse]
    total: int

# Test Case Schemas
class TestCaseBase(BaseModel):
    input_data: str
    expected_output: str
    is_sample: bool = False
    points: int = 1
    description: Optional[str] = None

class TestCaseCreate(TestCaseBase):
    pass

class TestCaseUpdate(BaseModel):
    input_data: Optional[str] = None
    expected_output: Optional[str] = None
    is_sample: Optional[bool] = None
    points: Optional[int] = None
    description: Optional[str] = None

class TestCaseResponse(TestCaseBase):
    id: int
    question_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Tag Schemas
class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class TagResponse(TagBase):
    id: int

    class Config:
        from_attributes = True


# Question Tag Schemas
class QuestionTagCreate(BaseModel):
    question_id: int
    tag_id: int

class QuestionTagResponse(BaseModel):
    question_id: int
    tag_id: int
    created_at: datetime
    tag: TagResponse

    class Config:
        from_attributes = True

# Question Schemas
class QuestionBase(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    difficulty: Optional[Difficulty] = None
    question_type: QuestionType = QuestionType.theory
    starter_code: Optional[str] = None
    solution_code: Optional[str] = None
    time_limit: int = 5
    memory_limit: int = 256
    status: QuestionStatus = QuestionStatus.draft
    is_public: bool = True

class QuestionCreate(QuestionBase):
    test_cases: Optional[List[TestCaseCreate]] = []
    tags: Optional[List[TagCreate]] = []

class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    difficulty: Optional[Difficulty] = None
    question_type: Optional[QuestionType] = None
    starter_code: Optional[str] = None
    solution_code: Optional[str] = None
    time_limit: Optional[int] = None
    memory_limit: Optional[int] = None
    status: Optional[QuestionStatus] = None
    is_public: Optional[bool] = None

class QuestionResponse(QuestionBase):
    id: int 
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    category: Optional[QuestionCategoryResponse] = None
    test_cases: List[TestCaseResponse] = []
    tags: List[TagResponse] = []
    class Config:
        from_attributes = True

class QuestionListResponse(BaseModel):
    questions: List[QuestionResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

# User Answer Schemas
class UserAnswerBase(BaseModel):
    answer_content: Optional[str] = None
    source_code: Optional[str] = None
    language: Optional[str] = None
    time_taken_seconds: Optional[int] = None

class UserAnswerCreate(UserAnswerBase):
    question_id: int
    answer_content: str
    answer_type: str = "coding" 
    code_language: Optional[str] = None
    test_results: Optional[List[Dict[str, Any]]] = None  

class UserAnswerUpdate(BaseModel):
    answer_text: Optional[str] = None
    source_code: Optional[str] = None
    language: Optional[str] = None

class UserAnswerResponse(UserAnswerBase):
    id: int
    user_id: int
    question_id: int
    answer_content: str
    answer_type: str
    code_language: Optional[str] = None
    test_results: Optional[List[Dict[str, Any]]] = None
    score: Optional[int] = None
    is_correct: bool
    feedback: Optional[str] = None
    execution_time: Optional[int] = None
    memory_used: Optional[int] = None
    test_cases_passed: Optional[int] = None
    total_test_cases: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserAnswerListResponse(BaseModel):
    answers: List[UserAnswerResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


#Code Execution Schemas
class CodeExecutionRequest(BaseModel):
    code: str
    language: str
    test_cases: List[Dict[str, Any]]
    time_limit: Optional[int] = 5

class TestCaseResult(BaseModel):
    input: str
    expected_output: str
    actual_output: str
    passed: bool
    execution_time: int
    memory_usage: int
    error_message: Optional[str] = None

class CodeExecutionResponse(BaseModel):
    results: List[TestCaseResult]



#INTERVIEW SESSION SCHEMAS 
class InterviewSessionBase(BaseModel):
    title: str
    type: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    scheduled_at: Optional[datetime] = None
    end_at: Optional[datetime] = None  # <-- NEW FIELD
    feedback: Optional[str] = None
    rating: Optional[int] = None
    recording_url: Optional[str] = None

class InterviewSessionCreate(InterviewSessionBase):
    pass

class InterviewSessionUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    scheduled_at: Optional[datetime] = None
    end_at: Optional[datetime] = None  # <-- NEW FIELD
    feedback: Optional[str] = None
    rating: Optional[int] = None
    recording_url: Optional[str] = None

class InterviewSessionResponse(InterviewSessionBase):
    id: int
    user_id: int
    scheduled_at: Optional[datetime]
    end_at: Optional[datetime]  # <-- NEW FIELD
    completed_at: Optional[datetime]
    created_at: Optional[datetime]
    feedback: Optional[str]
    rating: Optional[int]
    recording_url: Optional[str]

    class Config:
        from_attributes = True

class InterviewSessionListResponse(BaseModel):
    sessions: List[InterviewSessionResponse]
    total: int


#SESSION QUESTION SCHEMAS
class SessionQuestionBase(BaseModel):
    order_index: int
    question_title: str
    question_description: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    user_answer: Optional[str] = None
    feedback: Optional[str] = None
    time_spent_seconds: Optional[int] = None

class SessionQuestionCreate(SessionQuestionBase):
    pass

class SessionQuestionResponse(SessionQuestionBase):
    session_id: int

    class Config:
        from_attributes = True

class RecordingUrlRequest(BaseModel):
    recording_url: str


#AI CHAT INTEREVIEW START REQUEST 

class AIChatInterviewStartRequest(BaseModel):
    intro: str
    role: str

class AIChatInterviewStartResponse(BaseModel):
    ai_message: str
    questions: list[Dict]

class AIChatMessageRequest(BaseModel):
    question: str
    answer: str

class AIChatMessageResponse(BaseModel):
    ai_message: str
    feedback: Optional[str] = None


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    action_url: str = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class SendNotificationRequest(BaseModel):
    title: str
    message: str
    action_url: str = None