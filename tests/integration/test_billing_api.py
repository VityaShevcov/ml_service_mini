"""
Integration tests for billing API
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database import Base, get_db


@pytest.fixture
def test_db():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    """Create user and get auth token"""
    # Register user
    client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPass123"
    })
    
    # Login and get token
    response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "TestPass123"
    })
    
    return response.json()["data"]["access_token"]


class TestBillingAPI:
    """Test billing API endpoints"""
    
    def test_get_balance(self, client, auth_token):
        """Test getting user balance"""
        response = client.get("/billing/balance", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 100  # Initial credits
        assert "Current balance" in data["message"]
    
    def test_get_balance_unauthorized(self, client):
        """Test getting balance without auth"""
        response = client.get("/billing/balance")
        assert response.status_code == 403
    
    def test_add_credits(self, client, auth_token):
        """Test adding credits"""
        response = client.post("/billing/add", 
            json={"amount": 50},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 150  # 100 + 50
        assert "Successfully added 50 credits" in data["message"]
    
    def test_add_credits_negative(self, client, auth_token):
        """Test adding negative credits"""
        response = client.post("/billing/add", 
            json={"amount": -10},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_charge_credits(self, client, auth_token):
        """Test charging credits"""
        response = client.post("/billing/charge", 
            json={"amount": 30, "description": "Test charge"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 70  # 100 - 30
        assert "Successfully charged 30 credits" in data["message"]
    
    def test_charge_credits_insufficient(self, client, auth_token):
        """Test charging more credits than available"""
        response = client.post("/billing/charge", 
            json={"amount": 150},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Insufficient credits" in data["detail"]
    
    def test_refund_credits(self, client, auth_token):
        """Test refunding credits"""
        # First charge some credits
        client.post("/billing/charge", 
            json={"amount": 40},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Then refund
        response = client.post("/billing/refund", 
            json={"amount": 20, "description": "Test refund"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 80  # 100 - 40 + 20
        assert "Successfully refunded 20 credits" in data["message"]
    
    def test_get_transactions(self, client, auth_token):
        """Test getting transaction history"""
        # Perform some transactions
        client.post("/billing/charge", 
            json={"amount": 20},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        client.post("/billing/add", 
            json={"amount": 30},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Get transactions
        response = client.get("/billing/transactions", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 2
        assert data["total_count"] == 2
    
    def test_get_transactions_with_pagination(self, client, auth_token):
        """Test getting transactions with pagination"""
        # Perform multiple transactions
        for i in range(5):
            client.post("/billing/charge", 
                json={"amount": 5},
                headers={"Authorization": f"Bearer {auth_token}"}
            )
        
        # Get first 3 transactions
        response = client.get("/billing/transactions?skip=0&limit=3", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 3
    
    def test_get_transaction_summary(self, client, auth_token):
        """Test getting transaction summary"""
        # Perform various transactions
        client.post("/billing/charge", 
            json={"amount": 30},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        client.post("/billing/add", 
            json={"amount": 50},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        client.post("/billing/refund", 
            json={"amount": 10},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        response = client.get("/billing/summary", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_transactions"] == 3
        assert data["total_charged"] == 30
        assert data["total_added"] == 50
        assert data["total_refunded"] == 10
        assert data["current_balance"] == 130  # 100 - 30 + 50 + 10
    
    def test_check_sufficient_credits(self, client, auth_token):
        """Test checking sufficient credits"""
        # Check for amount user has
        response = client.get("/billing/check/50", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["sufficient"] is True
        assert data["current_balance"] == 100
        assert data["required_amount"] == 50
        
        # Check for amount user doesn't have
        response = client.get("/billing/check/150", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["sufficient"] is False
    
    def test_get_model_cost(self, client):
        """Test getting model costs"""
        # Test Gemma3 1B cost
        response = client.get("/billing/model-cost/gemma3_1b")
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "gemma3_1b"
        assert data["cost"] == 1
        
        # Test Gemma3 12B cost
        response = client.get("/billing/model-cost/gemma3_12b")
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "gemma3_12b"
        assert data["cost"] == 3
        
        # Test unknown model (should default to 1)
        response = client.get("/billing/model-cost/unknown_model")
        
        assert response.status_code == 200
        data = response.json()
        assert data["cost"] == 1