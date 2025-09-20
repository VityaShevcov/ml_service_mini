"""
Integration tests for authentication API
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


class TestAuthAPI:
    """Test authentication API endpoints"""
    
    def test_register_user_success(self, client):
        """Test successful user registration"""
        response = client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "successfully" in data["message"]
        assert data["data"]["username"] == "testuser"
        assert data["data"]["credits"] == 100
    
    def test_register_user_duplicate_username(self, client):
        """Test registration with duplicate username"""
        # Register first user
        client.post("/auth/register", json={
            "username": "testuser",
            "email": "test1@example.com",
            "password": "TestPass123"
        })
        
        # Try to register with same username
        response = client.post("/auth/register", json={
            "username": "testuser",
            "email": "test2@example.com",
            "password": "TestPass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already exists" in data["message"]
    
    def test_register_user_invalid_email(self, client):
        """Test registration with invalid email"""
        response = client.post("/auth/register", json={
            "username": "testuser",
            "email": "invalid-email",
            "password": "TestPass123"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_login_success(self, client):
        """Test successful login"""
        # Register user first
        client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123"
        })
        
        # Login
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "TestPass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
        assert data["data"]["user"]["username"] == "testuser"
    
    def test_login_wrong_password(self, client):
        """Test login with wrong password"""
        # Register user first
        client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123"
        })
        
        # Try wrong password
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "WrongPassword"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid username or password" in data["message"]
    
    def test_get_current_user_info(self, client):
        """Test getting current user info"""
        # Register and login
        client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123"
        })
        
        login_response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "TestPass123"
        })
        
        token = login_response.json()["data"]["access_token"]
        
        # Get user info
        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["credits"] == 100
    
    def test_get_current_user_info_unauthorized(self, client):
        """Test getting user info without token"""
        response = client.get("/auth/me")
        
        assert response.status_code == 403  # Forbidden
    
    def test_get_credits(self, client):
        """Test getting user credits"""
        # Register and login
        client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123"
        })
        
        login_response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "TestPass123"
        })
        
        token = login_response.json()["data"]["access_token"]
        
        # Get credits
        response = client.get("/auth/credits", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 100
        assert "You have 100 credits" in data["message"]
    
    def test_add_credits(self, client):
        """Test adding credits"""
        # Register and login
        client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123"
        })
        
        login_response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "TestPass123"
        })
        
        token = login_response.json()["data"]["access_token"]
        
        # Add credits
        response = client.post("/auth/credits/add", 
            json={"amount": 50},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["credits"] == 150
        assert "Added 50 credits" in data["message"]