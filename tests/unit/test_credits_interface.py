"""
Unit tests for CreditsInterface
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from app.ui.credits_interface import CreditsInterface


class TestCreditsInterface:
    """Test cases for CreditsInterface"""
    
    @pytest.fixture
    def credits_interface(self):
        """CreditsInterface instance for testing"""
        return CreditsInterface("http://localhost:8000")
    
    def test_init(self, credits_interface):
        """Test CreditsInterface initialization"""
        assert credits_interface.api_base_url == "http://localhost:8000"
        assert credits_interface.current_token is None
        assert credits_interface.current_user is None
    
    def test_set_auth(self, credits_interface):
        """Test setting authentication"""
        token = "test_token_123"
        user_info = {"id": 1, "username": "testuser"}
        
        credits_interface.set_auth(token, user_info)
        
        assert credits_interface.current_token == token
        assert credits_interface.current_user == user_info
    
    @patch('app.ui.credits_interface.requests.get')
    def test_get_current_balance_success(self, mock_get, credits_interface):
        """Test successful balance retrieval"""
        credits_interface.set_auth("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": 150}
        mock_get.return_value = mock_response
        
        # Test
        balance, status = credits_interface.get_current_balance()
        
        # Assertions
        assert balance == 150
        assert "✅ Current balance: 150 credits" in status
        
        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"
    
    def test_get_current_balance_not_authenticated(self, credits_interface):
        """Test balance retrieval when not authenticated"""
        balance, status = credits_interface.get_current_balance()
        
        assert balance == 0
        assert "❌ Not authenticated" in status
    
    @patch('app.ui.credits_interface.requests.get')
    def test_get_current_balance_api_error(self, mock_get, credits_interface):
        """Test balance retrieval with API error"""
        credits_interface.set_auth("test_token")
        
        # Mock API error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        # Test
        balance, status = credits_interface.get_current_balance()
        
        # Assertions
        assert balance == 0
        assert "❌ Failed to get balance: HTTP 500" in status
    
    @patch('app.ui.credits_interface.requests.post')
    def test_add_credits_success(self, mock_post, credits_interface):
        """Test successful credit addition"""
        credits_interface.set_auth("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"new_balance": 250}
        mock_post.return_value = mock_response
        
        # Test
        success, message, new_balance = credits_interface.add_credits(100, "Test top-up")
        
        # Assertions
        assert success == True
        assert "✅ Added 100 credits. New balance: 250" in message
        assert new_balance == 250
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["amount"] == 100
        assert call_args[1]["json"]["description"] == "Test top-up"
    
    def test_add_credits_invalid_amount(self, credits_interface):
        """Test credit addition with invalid amount"""
        credits_interface.set_auth("test_token")
        
        # Test with zero amount
        success, message, new_balance = credits_interface.add_credits(0)
        assert success == False
        assert "❌ Amount must be positive" in message
        assert new_balance == 0
        
        # Test with negative amount
        success, message, new_balance = credits_interface.add_credits(-50)
        assert success == False
        assert "❌ Amount must be positive" in message
        assert new_balance == 0
    
    def test_add_credits_not_authenticated(self, credits_interface):
        """Test credit addition when not authenticated"""
        success, message, new_balance = credits_interface.add_credits(100)
        
        assert success == False
        assert "❌ Not authenticated" in message
        assert new_balance == 0
    
    @patch('app.ui.credits_interface.requests.get')
    def test_get_transaction_history_success(self, mock_get, credits_interface):
        """Test successful transaction history retrieval"""
        credits_interface.set_auth("test_token")
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "created_at": "2024-01-01T12:00:00Z",
                    "transaction_type": "add",
                    "amount": 100,
                    "description": "Credit purchase"
                },
                {
                    "created_at": "2024-01-01T13:00:00Z",
                    "transaction_type": "charge",
                    "amount": -10,
                    "description": "Chat with gemma3-1b"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test
        history, status = credits_interface.get_transaction_history(20)
        
        # Assertions
        assert len(history) == 2
        assert "✅ Loaded 2 transactions" in status
        
        # Check first transaction (credit added)
        first_transaction = history[0]
        assert "➕ Credit Added" in first_transaction[1]
        assert "+100" in first_transaction[2]
        
        # Check second transaction (credit used)
        second_transaction = history[1]
        assert "➖ Credit Used" in second_transaction[1]
        assert "-10" in second_transaction[2]
    
    def test_get_transaction_history_not_authenticated(self, credits_interface):
        """Test transaction history when not authenticated"""
        history, status = credits_interface.get_transaction_history()
        
        assert history == []
        assert "❌ Not authenticated" in status
    
    def test_get_credit_packages(self, credits_interface):
        """Test credit packages retrieval"""
        packages = credits_interface.get_credit_packages()
        
        # Should return predefined packages
        assert len(packages) > 0
        assert all("amount" in package for package in packages)
        assert all("price" in package for package in packages)
        assert all("bonus" in package for package in packages)
        assert all("description" in package for package in packages)
        
        # Check that packages are sorted by amount
        amounts = [package["amount"] for package in packages]
        assert amounts == sorted(amounts)
    
    @patch('app.ui.credits_interface.time.sleep')  # Mock sleep to speed up test
    def test_simulate_payment_success(self, mock_sleep, credits_interface):
        """Test successful payment simulation"""
        credits_interface.set_auth("test_token")
        
        # Mock add_credits method
        with patch.object(credits_interface, 'add_credits') as mock_add_credits:
            mock_add_credits.return_value = (True, "Credits added", 350)
            
            # Test payment for 250 credit package (with 25 bonus)
            success, message = credits_interface.simulate_payment(250, "Credit Card")
            
            # Assertions
            assert success == True
            assert "✅ Payment successful!" in message
            assert "275 credits" in message  # 250 + 25 bonus
            
            # Verify add_credits was called with correct total
            mock_add_credits.assert_called_once_with(275, "Credit purchase: Popular Choice (Credit Card)")
    
    def test_simulate_payment_invalid_package(self, credits_interface):
        """Test payment simulation with invalid package"""
        credits_interface.set_auth("test_token")
        
        success, message = credits_interface.simulate_payment(999, "Credit Card")
        
        assert success == False
        assert "❌ Invalid package selected" in message
    
    def test_simulate_payment_credit_addition_fails(self, credits_interface):
        """Test payment simulation when credit addition fails"""
        credits_interface.set_auth("test_token")
        
        # Mock add_credits to fail
        with patch.object(credits_interface, 'add_credits') as mock_add_credits:
            mock_add_credits.return_value = (False, "Database error", 0)
            
            success, message = credits_interface.simulate_payment(100, "PayPal")
            
            assert success == False
            assert "❌ Payment processed but credit addition failed" in message
    
    def test_create_interface(self, credits_interface):
        """Test interface creation"""
        interface = credits_interface.create_interface()
        
        # Should return a Gradio Blocks object
        assert hasattr(interface, 'launch')  # Basic check for Gradio interface
    
    @patch('app.ui.credits_interface.requests.get')
    def test_transaction_history_date_formatting(self, mock_get, credits_interface):
        """Test that transaction dates are properly formatted"""
        credits_interface.set_auth("test_token")
        
        # Mock API response with various date formats
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "created_at": "2024-01-01T12:30:45Z",
                    "transaction_type": "add",
                    "amount": 100,
                    "description": "Test transaction"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Test
        history, status = credits_interface.get_transaction_history()
        
        # Check date formatting
        first_transaction = history[0]
        date_str = first_transaction[0]
        
        # Should be formatted as YYYY-MM-DD HH:MM:SS
        assert "2024-01-01 12:30:45" in date_str
    
    def test_package_info_generation(self, credits_interface):
        """Test that package information is correctly generated"""
        packages = credits_interface.get_credit_packages()
        
        # Test package with bonus
        package_with_bonus = next(p for p in packages if p["bonus"] > 0)
        total_credits = package_with_bonus["amount"] + package_with_bonus["bonus"]
        
        # Verify calculations
        assert total_credits > package_with_bonus["amount"]
        assert package_with_bonus["bonus"] >= 0
        
        # Test package without bonus
        package_without_bonus = next(p for p in packages if p["bonus"] == 0)
        assert package_without_bonus["amount"] > 0