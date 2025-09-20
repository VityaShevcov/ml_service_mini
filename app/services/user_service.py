"""
User service for authentication and user management
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models import User, UserSession
from app.models.crud import UserCRUD, UserSessionCRUD
from app.utils.auth import (
    hash_password, 
    verify_password, 
    create_access_token, 
    decode_access_token,
    get_token_hash,
    validate_password_strength,
    validate_email
)
from app.utils.logging import get_logger, log_user_action
from config import settings


logger = get_logger(__name__)


class UserService:
    """Service for user authentication and management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def register_user(
        self, 
        username: str, 
        email: str, 
        password: str
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Register a new user
        Returns (success, message, user)
        """
        try:
            # Validate input
            if not username or len(username) < 3:
                return False, "Username must be at least 3 characters long", None
            
            if not validate_email(email):
                return False, "Invalid email format", None
            
            is_valid, password_error = validate_password_strength(password)
            if not is_valid:
                return False, password_error, None
            
            # Check if user already exists
            existing_user = UserCRUD.get_by_username(self.db, username)
            if existing_user:
                return False, "Username already exists", None
            
            existing_email = UserCRUD.get_by_email(self.db, email)
            if existing_email:
                return False, "Email already registered", None
            
            # Create user
            password_hash = hash_password(password)
            user = UserCRUD.create(
                db=self.db,
                username=username,
                email=email,
                password_hash=password_hash,
                initial_credits=settings.initial_credits
            )
            
            log_user_action(logger, user.id, "user_registered", username=username, email=email)
            return True, "User registered successfully", user
            
        except Exception as e:
            logger.error("user_registration_failed", error=str(e), username=username, email=email)
            return False, "Registration failed due to server error", None
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """
        Authenticate user with username and password
        Returns (success, message, user)
        """
        try:
            # Get user by username
            user = UserCRUD.get_by_username(self.db, username)
            if not user:
                log_user_action(logger, 0, "login_failed", username=username, reason="user_not_found")
                return False, "Invalid username or password", None
            
            # Verify password
            if not verify_password(password, user.password_hash):
                log_user_action(logger, user.id, "login_failed", username=username, reason="invalid_password")
                return False, "Invalid username or password", None
            
            log_user_action(logger, user.id, "login_success", username=username)
            return True, "Authentication successful", user
            
        except Exception as e:
            logger.error("authentication_failed", error=str(e), username=username)
            return False, "Authentication failed due to server error", None
    
    def create_user_session(self, user: User) -> Tuple[bool, str, Optional[str]]:
        """
        Create a new user session and return JWT token
        Returns (success, message, token)
        """
        try:
            # Create JWT token
            token_data = {
                "sub": str(user.id),
                "username": user.username,
                "email": user.email
            }
            
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
            token = create_access_token(token_data, expires_delta)
            
            # Store session in database
            token_hash = get_token_hash(token)
            expires_at = datetime.utcnow() + expires_delta
            
            UserSessionCRUD.create(
                db=self.db,
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at
            )
            
            log_user_action(logger, user.id, "session_created", username=user.username)
            return True, "Session created successfully", token
            
        except Exception as e:
            logger.error("session_creation_failed", error=str(e), user_id=user.id)
            return False, "Failed to create session", None
    
    def get_user_by_token(self, token: str) -> Optional[User]:
        """
        Get user by JWT token
        Returns user if token is valid, None otherwise
        """
        try:
            # Decode token
            payload = decode_access_token(token)
            if not payload:
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                return None
            
            # Check if session exists in database
            token_hash = get_token_hash(token)
            session = UserSessionCRUD.get_by_token_hash(self.db, token_hash)
            if not session:
                return None
            
            # Get user
            user = UserCRUD.get_by_id(self.db, int(user_id))
            return user
            
        except Exception as e:
            logger.error("token_validation_failed", error=str(e))
            return None
    
    def logout_user(self, token: str) -> bool:
        """
        Logout user by invalidating token
        Returns success status
        """
        try:
            token_hash = get_token_hash(token)
            
            # Get session
            session = UserSessionCRUD.get_by_token_hash(self.db, token_hash)
            if session:
                # Delete session
                UserSessionCRUD.delete_by_user(self.db, session.user_id)
                log_user_action(logger, session.user_id, "logout_success")
                return True
            
            return False
            
        except Exception as e:
            logger.error("logout_failed", error=str(e))
            return False
    
    def update_user_credits(self, user_id: int, new_credits: int) -> bool:
        """
        Update user credits
        Returns success status
        """
        try:
            success = UserCRUD.update_credits(self.db, user_id, new_credits)
            if success:
                log_user_action(logger, user_id, "credits_updated", new_credits=new_credits)
            return success
            
        except Exception as e:
            logger.error("credits_update_failed", error=str(e), user_id=user_id)
            return False
    
    def get_user_info(self, user_id: int) -> Optional[dict]:
        """
        Get user information
        Returns user info dict or None
        """
        try:
            user = UserCRUD.get_by_id(self.db, user_id)
            if user:
                return {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "credits": user.credits,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat()
                }
            return None
            
        except Exception as e:
            logger.error("get_user_info_failed", error=str(e), user_id=user_id)
            return None
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        Returns number of deleted sessions
        """
        try:
            deleted_count = UserSessionCRUD.delete_expired(self.db)
            logger.info("expired_sessions_cleaned", deleted_count=deleted_count)
            return deleted_count
            
        except Exception as e:
            logger.error("session_cleanup_failed", error=str(e))
            return 0