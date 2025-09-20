"""
Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.user_service import UserService
from app.api.dependencies import get_user_service, get_current_user
from app.api.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    RegisterResponse,
    LoginResponse,
    TokenResponse,
    UserInfoResponse,
    SuccessResponse,
    AddCreditsRequest,
    CreditsResponse
)
from app.models import User


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: UserRegisterRequest,
    user_service: UserService = Depends(get_user_service)
):
    """Register a new user"""
    success, message, user = user_service.register_user(
        username=request.username,
        email=request.email,
        password=request.password
    )
    
    if not success:
        return RegisterResponse(success=False, message=message)
    
    user_info = UserInfoResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        credits=user.credits,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )
    
    return RegisterResponse(
        success=True,
        message=message,
        data=user_info
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: UserLoginRequest,
    user_service: UserService = Depends(get_user_service)
):
    """Login user and return JWT token"""
    # Authenticate user
    success, message, user = user_service.authenticate_user(
        username=request.username,
        password=request.password
    )
    
    if not success:
        return LoginResponse(success=False, message=message)
    
    # Create session and token
    session_success, session_message, token = user_service.create_user_session(user)
    
    if not session_success:
        return LoginResponse(success=False, message=session_message)
    
    user_info = UserInfoResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        credits=user.credits,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat()
    )
    
    token_response = TokenResponse(
        access_token=token,
        user=user_info
    )
    
    return LoginResponse(
        success=True,
        message="Login successful",
        data=token_response
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Logout current user"""
    # Note: In a real implementation, we'd need to get the token from the request
    # For now, we'll just return success
    return SuccessResponse(
        success=True,
        message="Logout successful"
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return UserInfoResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        credits=current_user.credits,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat()
    )


@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    current_user: User = Depends(get_current_user)
):
    """Get current user credits"""
    return CreditsResponse(
        credits=current_user.credits,
        message=f"You have {current_user.credits} credits"
    )


@router.post("/credits/add", response_model=CreditsResponse)
async def add_credits(
    request: AddCreditsRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Add credits to current user account"""
    new_credits = current_user.credits + request.amount
    
    success = user_service.update_user_credits(current_user.id, new_credits)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add credits"
        )
    
    return CreditsResponse(
        credits=new_credits,
        message=f"Added {request.amount} credits. New balance: {new_credits}"
    )