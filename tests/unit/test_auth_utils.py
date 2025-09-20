"""
Unit tests for authentication utilities
"""
import pytest
from datetime import datetime, timedelta

from app.utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_token_hash,
    validate_password_strength,
    validate_email
)


class TestPasswordHashing:
    """Test password hashing functions"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "TestPassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt hash format
    
    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "TestPassword123"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "TestPassword123"
        wrong_password = "WrongPassword"
        hashed = hash_password(password)
        
        assert verify_password(wrong_password, hashed) is False


class TestJWTTokens:
    """Test JWT token functions"""
    
    def test_create_access_token(self):
        """Test JWT token creation"""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert "." in token  # JWT format has dots
    
    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry"""
        data = {"sub": "123", "username": "testuser"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_access_token_valid(self):
        """Test decoding valid JWT token"""
        data = {"sub": "123", "username": "testuser"}
        token = create_access_token(data)
        
        decoded = decode_access_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == "123"
        assert decoded["username"] == "testuser"
        assert "exp" in decoded
    
    def test_decode_access_token_invalid(self):
        """Test decoding invalid JWT token"""
        invalid_token = "invalid.token.here"
        decoded = decode_access_token(invalid_token)
        
        assert decoded is None
    
    def test_get_token_hash(self):
        """Test token hashing"""
        token = "sample_token_123"
        hash1 = get_token_hash(token)
        hash2 = get_token_hash(token)
        
        assert hash1 == hash2  # Same token should produce same hash
        assert len(hash1) == 64  # SHA256 produces 64 character hex string
        assert hash1 != token  # Hash should be different from original


class TestPasswordValidation:
    """Test password strength validation"""
    
    def test_validate_strong_password(self):
        """Test validation of strong password"""
        password = "StrongPass123"
        is_valid, message = validate_password_strength(password)
        
        assert is_valid is True
        assert message == ""
    
    def test_validate_short_password(self):
        """Test validation of short password"""
        password = "Short1"
        is_valid, message = validate_password_strength(password)
        
        assert is_valid is False
        assert "at least 8 characters" in message
    
    def test_validate_no_uppercase(self):
        """Test validation of password without uppercase"""
        password = "lowercase123"
        is_valid, message = validate_password_strength(password)
        
        assert is_valid is False
        assert "uppercase letter" in message
    
    def test_validate_no_lowercase(self):
        """Test validation of password without lowercase"""
        password = "UPPERCASE123"
        is_valid, message = validate_password_strength(password)
        
        assert is_valid is False
        assert "lowercase letter" in message
    
    def test_validate_no_digit(self):
        """Test validation of password without digit"""
        password = "NoDigitsHere"
        is_valid, message = validate_password_strength(password)
        
        assert is_valid is False
        assert "digit" in message


class TestEmailValidation:
    """Test email validation"""
    
    def test_validate_valid_email(self):
        """Test validation of valid email"""
        emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org"
        ]
        
        for email in emails:
            assert validate_email(email) is True
    
    def test_validate_invalid_email(self):
        """Test validation of invalid email"""
        emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user@domain",
            "user.domain.com"
        ]
        
        for email in emails:
            assert validate_email(email) is False