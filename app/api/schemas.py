"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# User schemas
class UserRegisterRequest(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLoginRequest(BaseModel):
    """User login request"""
    username: str
    password: str


class UserResponse(BaseModel):
    """User response"""
    id: int
    username: str
    email: str
    credits: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserInfoResponse(BaseModel):
    """User info response"""
    id: int
    username: str
    email: str
    credits: int
    created_at: str
    updated_at: str


# Authentication schemas
class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserInfoResponse


class LoginResponse(BaseModel):
    """Login response"""
    success: bool
    message: str
    data: Optional[TokenResponse] = None


class RegisterResponse(BaseModel):
    """Registration response"""
    success: bool
    message: str
    data: Optional[UserInfoResponse] = None


# Generic response schemas
class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Generic error response"""
    success: bool = False
    message: str
    detail: Optional[str] = None


# Credit schemas
class AddCreditsRequest(BaseModel):
    """Add credits request"""
    amount: int = Field(..., gt=0, description="Amount of credits to add")


class CreditsResponse(BaseModel):
    """Credits response"""
    credits: int
    message: str