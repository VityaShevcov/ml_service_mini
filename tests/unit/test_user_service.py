"""
Unit tests for UserService
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.user_service import UserService
from app.utils.auth import hash_password, create_access_token


@pytest.fixture
def db_session():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def user_service(db_session):
    """Create UserService instance"""
    return UserService(db_session)


class TestUserService:
    """Test UserService functionality"""
    
    def test_register_user_success(self, user_service):
        """Test successful user registration"""
        success, message, user = user_service.register_user(
            username="testuser",
            email="test@example.com",
            password="TestPass123"
        )
        
        assert success is True
        assert "successfully" in message
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.credits == 100  # Default initial credits
    
    def test_register_user_duplicate_username(self, user_service):
        """Test registration with duplicate username"""
        # Register first user
        user_service.register_user("testuser", "test1@example.com", "TestPass123")
        
        # Try to register with same username
        success, message, user = user_service.register_user(
            "testuser", "test2@example.com", "TestPass123"
        )
        
        assert success is False
        assert "already exists" in message
        assert user is None
    
    def test_register_user_duplicate_email(self, user_service):
        """Test registration with duplicate email"""
        # Register first user
        user_service.register_user("testuser1", "test@example.com", "TestPass123")
        
        # Try to register with same email
        success, message, user = user_service.register_user(
            "testuser2", "test@example.com", "TestPass123"
        )
        
        assert success is False
        assert "already registered" in message
        assert user is None
    
    def test_register_user_weak_password(self, user_service):
        """Test registration with weak password"""
        success, message, user = user_service.register_user(
            "testuser", "test@example.com", "weak"
        )
        
        assert success is False
        assert "Password must" in message
        assert user is None
    
    def test_register_user_invalid_email(self, user_service):
        """Test registration with invalid email"""
        success, message, user = user_service.register_user(
            "testuser", "invalid-email", "TestPass123"
        )
        
        assert success is False
        assert "Invalid email" in message
        assert user is None
    
    def test_authenticate_user_success(self, user_service):
        """Test successful user authentication"""
        # Register user first
        user_service.register_user("testuser", "test@example.com", "TestPass123")
        
        # Authenticate
        success, message, user = user_service.authenticate_user("testuser", "TestPass123")
        
        assert success is True
        assert "successful" in message
        assert user is not None
        assert user.username == "testuser"
    
    def test_authenticate_user_wrong_password(self, user_service):
        """Test authentication with wrong password"""
        # Register user first
        user_service.register_user("testuser", "test@example.com", "TestPass123")
        
        # Try wrong password
        success, message, user = user_service.authenticate_user("testuser", "WrongPass")
        
        assert success is False
        assert "Invalid username or password" in message
        assert user is None
    
    def test_authenticate_user_not_found(self, user_service):
        """Test authentication with non-existent user"""
        success, message, user = user_service.authenticate_user("nonexistent", "TestPass123")
        
        assert success is False
        assert "Invalid username or password" in message
        assert user is None
    
    def test_create_user_session(self, user_service):
        """Test creating user session"""
        # Register and authenticate user
        _, _, user = user_service.register_user("testuser", "test@example.com", "TestPass123")
        
        # Create session
        success, message, token = user_service.create_user_session(user)
        
        assert success is True
        assert "successfully" in message
        assert token is not None
        assert isinstance(token, str)
    
    def test_get_user_by_token(self, user_service):
        """Test getting user by token"""
        # Register user and create session
        _, _, user = user_service.register_user("testuser", "test@example.com", "TestPass123")
        _, _, token = user_service.create_user_session(user)
        
        # Get user by token
        retrieved_user = user_service.get_user_by_token(token)
        
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.username == user.username
    
    def test_get_user_by_invalid_token(self, user_service):
        """Test getting user by invalid token"""
        user = user_service.get_user_by_token("invalid_token")
        assert user is None
    
    def test_logout_user(self, user_service):
        """Test user logout"""
        # Register user and create session
        _, _, user = user_service.register_user("testuser", "test@example.com", "TestPass123")
        _, _, token = user_service.create_user_session(user)
        
        # Logout
        success = user_service.logout_user(token)
        assert success is True
        
        # Token should no longer be valid
        retrieved_user = user_service.get_user_by_token(token)
        assert retrieved_user is None
    
    def test_update_user_credits(self, user_service):
        """Test updating user credits"""
        # Register user
        _, _, user = user_service.register_user("testuser", "test@example.com", "TestPass123")
        
        # Update credits
        success = user_service.update_user_credits(user.id, 50)
        assert success is True
        
        # Verify credits updated
        user_info = user_service.get_user_info(user.id)
        assert user_info["credits"] == 50
    
    def test_get_user_info(self, user_service):
        """Test getting user info"""
        # Register user
        _, _, user = user_service.register_user("testuser", "test@example.com", "TestPass123")
        
        # Get user info
        user_info = user_service.get_user_info(user.id)
        
        assert user_info is not None
        assert user_info["username"] == "testuser"
        assert user_info["email"] == "test@example.com"
        assert user_info["credits"] == 100
        assert "created_at" in user_info
        assert "updated_at" in user_info
    
    def test_get_user_info_not_found(self, user_service):
        """Test getting info for non-existent user"""
        user_info = user_service.get_user_info(999)
        assert user_info is None