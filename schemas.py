from pydantic import BaseModel, field_validator
from typing import Optional 
from datetime import datetime   

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