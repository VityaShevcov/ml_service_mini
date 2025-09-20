"""
Unit tests for BillingService
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.billing_service import BillingService
from app.services.user_service import UserService


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
def billing_service(db_session):
    """Create BillingService instance"""
    return BillingService(db_session)


@pytest.fixture
def user_service(db_session):
    """Create UserService instance"""
    return UserService(db_session)


@pytest.fixture
def test_user(user_service):
    """Create test user with initial credits"""
    success, message, user = user_service.register_user(
        username="testuser",
        email="test@example.com",
        password="TestPass123"
    )
    return user


class TestBillingService:
    """Test BillingService functionality"""
    
    def test_charge_credits_success(self, billing_service, test_user):
        """Test successful credit charge"""
        success, message, remaining = billing_service.charge_credits(
            user_id=test_user.id,
            amount=30,
            description="Test charge"
        )
        
        assert success is True
        assert "Successfully charged 30 credits" in message
        assert remaining == 70  # 100 - 30
    
    def test_charge_credits_insufficient(self, billing_service, test_user):
        """Test charge with insufficient credits"""
        success, message, remaining = billing_service.charge_credits(
            user_id=test_user.id,
            amount=150,  # More than initial 100
            description="Test charge"
        )
        
        assert success is False
        assert "Insufficient credits" in message
        assert remaining == 100  # Should remain unchanged
    
    def test_charge_credits_user_not_found(self, billing_service):
        """Test charge for non-existent user"""
        success, message, remaining = billing_service.charge_credits(
            user_id=999,
            amount=10
        )
        
        assert success is False
        assert "User not found" in message
        assert remaining == 0
    
    def test_add_credits_success(self, billing_service, test_user):
        """Test successful credit addition"""
        success, message, new_balance = billing_service.add_credits(
            user_id=test_user.id,
            amount=50,
            description="Test addition"
        )
        
        assert success is True
        assert "Successfully added 50 credits" in message
        assert new_balance == 150  # 100 + 50
    
    def test_add_credits_negative_amount(self, billing_service, test_user):
        """Test adding negative credits"""
        success, message, new_balance = billing_service.add_credits(
            user_id=test_user.id,
            amount=-10
        )
        
        assert success is False
        assert "Amount must be positive" in message
    
    def test_add_credits_user_not_found(self, billing_service):
        """Test adding credits for non-existent user"""
        success, message, new_balance = billing_service.add_credits(
            user_id=999,
            amount=50
        )
        
        assert success is False
        assert "User not found" in message
        assert new_balance == 0
    
    def test_refund_credits_success(self, billing_service, test_user):
        """Test successful credit refund"""
        # First charge some credits
        billing_service.charge_credits(test_user.id, 30)
        
        # Then refund
        success, message, new_balance = billing_service.refund_credits(
            user_id=test_user.id,
            amount=20,
            description="Test refund"
        )
        
        assert success is True
        assert "Successfully refunded 20 credits" in message
        assert new_balance == 90  # 100 - 30 + 20
    
    def test_refund_credits_negative_amount(self, billing_service, test_user):
        """Test refunding negative amount"""
        success, message, new_balance = billing_service.refund_credits(
            user_id=test_user.id,
            amount=-10
        )
        
        assert success is False
        assert "Refund amount must be positive" in message
    
    def test_get_user_balance(self, billing_service, test_user):
        """Test getting user balance"""
        balance = billing_service.get_user_balance(test_user.id)
        assert balance == 100  # Initial credits
        
        # After charging
        billing_service.charge_credits(test_user.id, 25)
        balance = billing_service.get_user_balance(test_user.id)
        assert balance == 75
    
    def test_get_user_balance_not_found(self, billing_service):
        """Test getting balance for non-existent user"""
        balance = billing_service.get_user_balance(999)
        assert balance is None
    
    def test_get_user_transactions(self, billing_service, test_user):
        """Test getting user transaction history"""
        # Perform some transactions
        billing_service.charge_credits(test_user.id, 20, "Charge 1")
        billing_service.add_credits(test_user.id, 30, "Add 1")
        billing_service.refund_credits(test_user.id, 10, "Refund 1")
        
        transactions = billing_service.get_user_transactions(test_user.id)
        
        assert len(transactions) == 3
        assert transactions[0].transaction_type in ["charge", "add", "refund"]
    
    def test_get_transaction_summary(self, billing_service, test_user):
        """Test getting transaction summary"""
        # Perform various transactions
        billing_service.charge_credits(test_user.id, 30, "Charge 1")
        billing_service.charge_credits(test_user.id, 20, "Charge 2")
        billing_service.add_credits(test_user.id, 40, "Add 1")
        billing_service.refund_credits(test_user.id, 10, "Refund 1")
        
        summary = billing_service.get_transaction_summary(test_user.id)
        
        assert summary["total_transactions"] == 4
        assert summary["total_charged"] == 50  # 30 + 20
        assert summary["total_added"] == 40
        assert summary["total_refunded"] == 10
        assert summary["net_spent"] == 40  # 50 - 10
        assert summary["current_balance"] == 100  # 100 - 30 - 20 + 40 + 10
    
    def test_check_sufficient_credits(self, billing_service, test_user):
        """Test checking sufficient credits"""
        # Should have enough for 50 credits
        has_enough, message = billing_service.check_sufficient_credits(test_user.id, 50)
        assert has_enough is True
        assert "Sufficient credits" in message
        
        # Should not have enough for 150 credits
        has_enough, message = billing_service.check_sufficient_credits(test_user.id, 150)
        assert has_enough is False
        assert "Insufficient credits" in message
    
    def test_check_sufficient_credits_user_not_found(self, billing_service):
        """Test checking credits for non-existent user"""
        has_enough, message = billing_service.check_sufficient_credits(999, 50)
        assert has_enough is False
        assert "User not found" in message
    
    def test_get_model_cost(self, billing_service):
        """Test getting model costs"""
        assert billing_service.get_model_cost("gemma3_1b") == 1
        assert billing_service.get_model_cost("gemma3_12b") == 3
        assert billing_service.get_model_cost("Gemma3 1B") == 1
        assert billing_service.get_model_cost("Gemma3 12B") == 3
        assert billing_service.get_model_cost("unknown_model") == 1  # Default
    
    def test_process_model_usage_success(self, billing_service, test_user):
        """Test processing model usage successfully"""
        success, message, remaining = billing_service.process_model_usage(
            user_id=test_user.id,
            model_name="gemma3_1b",
            description="Test model usage"
        )
        
        assert success is True
        assert "Successfully charged 1 credits" in message
        assert remaining == 99  # 100 - 1
    
    def test_process_model_usage_insufficient_credits(self, billing_service, test_user):
        """Test processing model usage with insufficient credits"""
        # First drain most credits
        billing_service.charge_credits(test_user.id, 99)
        
        # Try to use expensive model
        success, message, remaining = billing_service.process_model_usage(
            user_id=test_user.id,
            model_name="gemma3_12b"  # Costs 3 credits
        )
        
        assert success is False
        assert "Insufficient credits" in message
        assert remaining == 1  # Should have 1 credit left
    
    def test_bulk_add_credits(self, billing_service, user_service):
        """Test bulk credit addition"""
        # Create multiple users
        user1 = user_service.register_user("user1", "user1@test.com", "TestPass123")[2]
        user2 = user_service.register_user("user2", "user2@test.com", "TestPass123")[2]
        user3 = user_service.register_user("user3", "user3@test.com", "TestPass123")[2]
        
        # Bulk add credits
        user_credits = [
            (user1.id, 50),
            (user2.id, 75),
            (user3.id, 25),
            (999, 100)  # Non-existent user
        ]
        
        successful, failed = billing_service.bulk_add_credits(user_credits)
        
        assert successful == 3
        assert failed == 1
        
        # Verify balances
        assert billing_service.get_user_balance(user1.id) == 150  # 100 + 50
        assert billing_service.get_user_balance(user2.id) == 175  # 100 + 75
        assert billing_service.get_user_balance(user3.id) == 125  # 100 + 25
    
    def test_transaction_atomicity(self, billing_service, test_user):
        """Test that transactions are atomic"""
        initial_balance = billing_service.get_user_balance(test_user.id)
        
        # This should succeed
        success1, _, balance1 = billing_service.charge_credits(test_user.id, 20)
        assert success1 is True
        assert balance1 == initial_balance - 20
        
        # This should fail due to insufficient credits
        success2, _, balance2 = billing_service.charge_credits(test_user.id, 200)
        assert success2 is False
        assert balance2 == balance1  # Balance should remain unchanged
        
        # Verify final balance
        final_balance = billing_service.get_user_balance(test_user.id)
        assert final_balance == balance1