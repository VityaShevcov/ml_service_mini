"""
Unit tests for ChatService
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.chat_service import ChatService
from app.services.user_service import UserService
from app.ml.ml_service import MLService
from app.models import User


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
def mock_ml_service():
    """Create mock ML service"""
    ml_service = Mock(spec=MLService)
    ml_service.models_loaded = True
    ml_service.is_model_available.return_value = True
    ml_service.get_available_models.return_value = ["Gemma3 1B", "Gemma3 12B"]
    ml_service.generate_response.return_value = (True, "Mock AI response", 500)
    ml_service.get_model_info.return_value = {"device": "cuda", "memory_usage_gb": 4.0}
    return ml_service


@pytest.fixture
def test_user(db_session):
    """Create test user"""
    user_service = UserService(db_session)
    success, message, user = user_service.register_user(
        username="testuser",
        email="test@example.com",
        password="TestPass123"
    )
    return user


@pytest.fixture
def chat_service(db_session, mock_ml_service):
    """Create ChatService instance"""
    return ChatService(db_session, mock_ml_service)


class TestChatService:
    """Test ChatService functionality"""
    
    def test_send_message_success(self, chat_service, test_user):
        """Test successful message sending"""
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="Hello, how are you?",
            model_name="Gemma3 1B"
        )
        
        assert success is True
        assert response == "Mock AI response"
        assert "interaction_id" in metadata
        assert "credits_charged" in metadata
        assert "processing_time_ms" in metadata
        assert metadata["credits_charged"] == 1  # Gemma3 1B costs 1 credit
    
    def test_send_message_empty(self, chat_service, test_user):
        """Test sending empty message"""
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="",
            model_name="Gemma3 1B"
        )
        
        assert success is False
        assert "empty" in response.lower()
    
    def test_send_message_too_long(self, chat_service, test_user):
        """Test sending message that's too long"""
        long_message = "x" * 2001  # Over 2000 character limit
        
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message=long_message,
            model_name="Gemma3 1B"
        )
        
        assert success is False
        assert "too long" in response.lower()
    
    def test_send_message_insufficient_credits(self, chat_service, test_user):
        """Test sending message with insufficient credits"""
        # Drain user credits first
        chat_service.billing_service.charge_credits(test_user.id, 99)  # Leave only 1 credit
        
        # Try to use expensive model
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="Hello",
            model_name="Gemma3 12B"  # Costs 3 credits
        )
        
        assert success is False
        assert "insufficient" in response.lower() or "credits" in response.lower()
    
    def test_send_message_model_unavailable(self, chat_service, test_user, mock_ml_service):
        """Test sending message with unavailable model"""
        # Mock model as unavailable
        mock_ml_service.is_model_available.return_value = False
        
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="Hello",
            model_name="NonexistentModel"
        )
        
        assert success is False
        assert "not available" in response.lower()
    
    def test_send_message_generation_failed(self, chat_service, test_user, mock_ml_service):
        """Test message sending when ML generation fails"""
        # Mock generation failure
        mock_ml_service.generate_response.return_value = (False, "Generation failed", 0)
        
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="Hello",
            model_name="Gemma3 1B"
        )
        
        assert success is False
        assert "generation failed" in response.lower()
    
    def test_get_conversation_history(self, chat_service, test_user):
        """Test getting conversation history"""
        # Send a few messages first
        chat_service.send_message(test_user, "Hello", "Gemma3 1B")
        chat_service.send_message(test_user, "How are you?", "Gemma3 1B")
        
        # Get history
        history = chat_service.get_conversation_history(test_user.id, limit=10)
        
        assert len(history) == 2
        assert all("id" in item for item in history)
        assert all("prompt" in item for item in history)
        assert all("response" in item for item in history)
    
    def test_get_user_chat_stats(self, chat_service, test_user):
        """Test getting user chat statistics"""
        # Send some messages
        chat_service.send_message(test_user, "Hello", "Gemma3 1B")
        chat_service.send_message(test_user, "How are you?", "Gemma3 12B")
        
        # Get stats
        stats = chat_service.get_user_chat_stats(test_user.id)
        
        assert "total_messages" in stats
        assert "total_credits_spent" in stats
        assert "favorite_model" in stats
        assert "models_used" in stats
        assert stats["total_messages"] == 2
        assert stats["total_credits_spent"] == 4  # 1 + 3 credits
    
    def test_estimate_response_cost(self, chat_service):
        """Test estimating response cost"""
        cost_info = chat_service.estimate_response_cost("Gemma3 1B")
        
        assert "model_name" in cost_info
        assert "cost" in cost_info
        assert "available" in cost_info
        assert cost_info["model_name"] == "Gemma3 1B"
        assert cost_info["cost"] == 1
    
    def test_validate_message_valid(self, chat_service):
        """Test message validation with valid message"""
        is_valid, message = chat_service.validate_message("Hello, how are you?")
        
        assert is_valid is True
        assert "valid" in message.lower()
    
    def test_validate_message_empty(self, chat_service):
        """Test message validation with empty message"""
        is_valid, message = chat_service.validate_message("")
        
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_validate_message_too_long(self, chat_service):
        """Test message validation with too long message"""
        long_message = "x" * 2001
        is_valid, message = chat_service.validate_message(long_message)
        
        assert is_valid is False
        assert "too long" in message.lower()
    
    def test_validate_message_harmful_content(self, chat_service):
        """Test message validation with potentially harmful content"""
        harmful_message = "Hello <script>alert('xss')</script>"
        is_valid, message = chat_service.validate_message(harmful_message)
        
        assert is_valid is False
        assert "harmful" in message.lower()
    
    def test_ml_service_initialization(self, chat_service, test_user, mock_ml_service):
        """Test ML service initialization when not loaded"""
        # Mock ML service as not loaded initially
        mock_ml_service.models_loaded = False
        mock_ml_service.initialize_models.return_value = {"gemma3_1b": True}
        
        # After initialization call, set as loaded
        def side_effect():
            mock_ml_service.models_loaded = True
            return {"gemma3_1b": True}
        
        mock_ml_service.initialize_models.side_effect = side_effect
        
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="Hello",
            model_name="Gemma3 1B"
        )
        
        # Should succeed after initialization
        assert success is True
        mock_ml_service.initialize_models.assert_called_once()
    
    def test_transaction_rollback_on_error(self, chat_service, test_user, mock_ml_service):
        """Test that transactions are rolled back on errors"""
        # Mock successful generation but billing failure
        mock_ml_service.generate_response.return_value = (True, "AI response", 500)
        
        # Mock billing service to fail
        original_charge = chat_service.billing_service.charge_credits
        chat_service.billing_service.charge_credits = Mock(return_value=(False, "Billing failed", 0))
        
        success, response, metadata = chat_service.send_message(
            user=test_user,
            message="Hello",
            model_name="Gemma3 1B"
        )
        
        assert success is False
        assert "billing" in response.lower()
        
        # Restore original method
        chat_service.billing_service.charge_credits = original_charge