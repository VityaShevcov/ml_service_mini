"""
Unit tests for database models
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, CreditTransaction, ModelInteraction, UserSession
from app.models.crud import UserCRUD, CreditTransactionCRUD, ModelInteractionCRUD, UserSessionCRUD


@pytest.fixture
def db_session():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


class TestUserModel:
    """Test User model and CRUD operations"""
    
    def test_create_user(self, db_session):
        """Test user creation"""
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            initial_credits=50
        )
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.credits == 50
        assert user.created_at is not None
    
    def test_get_user_by_username(self, db_session):
        """Test getting user by username"""
        # Create user
        UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Get user
        user = UserCRUD.get_by_username(db_session, "testuser")
        assert user is not None
        assert user.username == "testuser"
    
    def test_update_credits(self, db_session):
        """Test updating user credits"""
        # Create user
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            initial_credits=100
        )
        
        # Update credits
        success = UserCRUD.update_credits(db_session, user.id, 50)
        assert success is True
        
        # Verify update
        updated_user = UserCRUD.get_by_id(db_session, user.id)
        assert updated_user.credits == 50


class TestCreditTransactionModel:
    """Test CreditTransaction model and CRUD operations"""
    
    def test_create_transaction(self, db_session):
        """Test transaction creation"""
        # Create user first
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create transaction
        transaction = CreditTransactionCRUD.create(
            db=db_session,
            user_id=user.id,
            amount=-5,
            transaction_type="charge",
            description="Model usage"
        )
        
        assert transaction.id is not None
        assert transaction.user_id == user.id
        assert transaction.amount == -5
        assert transaction.transaction_type == "charge"
    
    def test_get_transactions_by_user(self, db_session):
        """Test getting transactions by user"""
        # Create user
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create transactions
        CreditTransactionCRUD.create(
            db=db_session,
            user_id=user.id,
            amount=-3,
            transaction_type="charge"
        )
        CreditTransactionCRUD.create(
            db=db_session,
            user_id=user.id,
            amount=10,
            transaction_type="add"
        )
        
        # Get transactions
        transactions = CreditTransactionCRUD.get_by_user(db_session, user.id)
        assert len(transactions) == 2


class TestModelInteractionModel:
    """Test ModelInteraction model and CRUD operations"""
    
    def test_create_interaction(self, db_session):
        """Test interaction creation"""
        # Create user first
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create interaction
        interaction = ModelInteractionCRUD.create(
            db=db_session,
            user_id=user.id,
            model_name="gemma3_1b",
            prompt="Hello",
            response="Hi there!",
            credits_charged=1,
            processing_time_ms=500
        )
        
        assert interaction.id is not None
        assert interaction.model_name == "gemma3_1b"
        assert interaction.credits_charged == 1
    
    def test_get_stats_by_model(self, db_session):
        """Test getting statistics by model"""
        # Create user
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create interactions
        ModelInteractionCRUD.create(
            db=db_session,
            user_id=user.id,
            model_name="gemma3_1b",
            prompt="Test 1",
            response="Response 1",
            credits_charged=1
        )
        ModelInteractionCRUD.create(
            db=db_session,
            user_id=user.id,
            model_name="gemma3_1b",
            prompt="Test 2",
            response="Response 2",
            credits_charged=1
        )
        ModelInteractionCRUD.create(
            db=db_session,
            user_id=user.id,
            model_name="gemma3_12b",
            prompt="Test 3",
            response="Response 3",
            credits_charged=3
        )
        
        # Get stats
        stats = ModelInteractionCRUD.get_stats_by_model(db_session)
        
        assert "gemma3_1b" in stats
        assert "gemma3_12b" in stats
        assert stats["gemma3_1b"]["count"] == 2
        assert stats["gemma3_1b"]["total_credits"] == 2
        assert stats["gemma3_12b"]["count"] == 1
        assert stats["gemma3_12b"]["total_credits"] == 3


class TestUserSessionModel:
    """Test UserSession model and CRUD operations"""
    
    def test_create_session(self, db_session):
        """Test session creation"""
        # Create user first
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create session
        expires_at = datetime.utcnow() + timedelta(hours=1)
        session = UserSessionCRUD.create(
            db=db_session,
            user_id=user.id,
            token_hash="token_hash_123",
            expires_at=expires_at
        )
        
        assert session.id is not None
        assert session.user_id == user.id
        assert session.token_hash == "token_hash_123"
    
    def test_get_session_by_token(self, db_session):
        """Test getting session by token hash"""
        # Create user
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create session
        expires_at = datetime.utcnow() + timedelta(hours=1)
        UserSessionCRUD.create(
            db=db_session,
            user_id=user.id,
            token_hash="token_hash_123",
            expires_at=expires_at
        )
        
        # Get session
        session = UserSessionCRUD.get_by_token_hash(db_session, "token_hash_123")
        assert session is not None
        assert session.user_id == user.id
    
    def test_delete_expired_sessions(self, db_session):
        """Test deleting expired sessions"""
        # Create user
        user = UserCRUD.create(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )
        
        # Create expired session
        expired_time = datetime.utcnow() - timedelta(hours=1)
        UserSessionCRUD.create(
            db=db_session,
            user_id=user.id,
            token_hash="expired_token",
            expires_at=expired_time
        )
        
        # Create valid session
        valid_time = datetime.utcnow() + timedelta(hours=1)
        UserSessionCRUD.create(
            db=db_session,
            user_id=user.id,
            token_hash="valid_token",
            expires_at=valid_time
        )
        
        # Delete expired sessions
        deleted_count = UserSessionCRUD.delete_expired(db_session)
        assert deleted_count == 1
        
        # Verify only valid session remains
        session = UserSessionCRUD.get_by_token_hash(db_session, "valid_token")
        assert session is not None
        
        expired_session = UserSessionCRUD.get_by_token_hash(db_session, "expired_token")
        assert expired_session is None