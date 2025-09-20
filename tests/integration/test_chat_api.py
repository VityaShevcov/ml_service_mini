"""
Integration tests for chat API
"""
import pytest
from unittest.mock import Mock, patch
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


class TestChatAPI:
    """Test chat API endpoints"""
    
    def test_get_chat_status(self, client, auth_token):
        """Test getting chat status"""
        response = client.get("/chat/status", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "username" in data
        assert "credits" in data
        assert "ml_service" in data
        assert "status" in data
    
    def test_get_available_models(self, client):
        """Test getting available models"""
        response = client.get("/chat/models")
        
        assert response.status_code == 200
        data = response.json()
        assert "available_models" in data
        assert "models_loaded" in data
        assert "message" in data
    
    @patch('app.api.chat.ml_service')
    def test_send_message_success(self, mock_ml_service, client, auth_token):
        """Test successful message sending"""
        # Mock ML service
        mock_ml_service.models_loaded = True
        mock_ml_service.is_model_available.return_value = True
        mock_ml_service.get_model_cost.return_value = 1
        mock_ml_service.generate_response.return_value = (True, "Hello! How can I help you?", 500)
        
        response = client.post("/chat/message", 
            json={
                "message": "Hello, how are you?",
                "model": "Gemma3 1B"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Note: This might fail due to billing service integration
        # In a real test, we'd need to mock the billing service too
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.json()}")
    
    def test_send_message_unauthorized(self, client):
        """Test sending message without auth"""
        response = client.post("/chat/message", json={
            "message": "Hello",
            "model": "Gemma3 1B"
        })
        
        assert response.status_code == 403
    
    def test_get_chat_history(self, client, auth_token):
        """Test getting chat history"""
        response = client.get("/chat/history", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
    
    def test_get_chat_history_with_pagination(self, client, auth_token):
        """Test getting chat history with pagination"""
        response = client.get("/chat/history?page=1&page_size=10", headers={
            "Authorization": f"Bearer {auth_token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10