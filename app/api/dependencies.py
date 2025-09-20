"""
FastAPI dependencies for authentication and database
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.user_service import UserService
from app.models import User


# Security scheme for JWT tokens
security = HTTPBearer()


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Get UserService instance"""
    return UserService(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> User:
    """
    Get current authenticated user from JWT token
    """
    token = credentials.credentials
    user = user_service.get_user_by_token(token)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> Optional[User]:
    """
    Get current user if token is provided and valid, otherwise return None
    """
    if credentials is None:
        return None
    
    token = credentials.credentials
    return user_service.get_user_by_token(token)