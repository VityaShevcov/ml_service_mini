"""
Basic test for ChatService functionality
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.chat_service import ChatService
from unittest.mock import Mock


def test_message_validation():
    """Test message validation functionality"""
    print("=== Testing Message Validation ===")
    
    # Create mock dependencies
    mock_db = Mock()
    mock_ml_service = Mock()
    
    try:
        chat_service = ChatService(mock_db, mock_ml_service)
        print("✓ ChatService created")
        
        # Test valid message
        is_valid, message = chat_service.validate_message("Hello, how are you?")
        print(f"✓ Valid message test: {is_valid}, {message}")
        assert is_valid is True
        
        # Test empty message
        is_valid, message = chat_service.validate_message("")
        print(f"✓ Empty message test: {is_valid}, {message}")
        assert is_valid is False
        
        # Test too long message
        long_message = "x" * 2001
        is_valid, message = chat_service.validate_message(long_message)
        print(f"✓ Long message test: {is_valid}, {message}")
        assert is_valid is False
        
        # Test harmful content
        harmful_message = "Hello <script>alert('xss')</script>"
        is_valid, message = chat_service.validate_message(harmful_message)
        print(f"✓ Harmful content test: {is_valid}, {message}")
        assert is_valid is False
        
        return True
        
    except Exception as e:
        print(f"✗ Message validation test failed: {e}")
        return False


def test_cost_estimation():
    """Test cost estimation functionality"""
    print("\n=== Testing Cost Estimation ===")
    
    # Create mock dependencies
    mock_db = Mock()
    mock_ml_service = Mock()
    mock_ml_service.is_model_available.return_value = True
    mock_ml_service.get_model_info.return_value = {"device": "cuda", "memory_usage_gb": 4.0}
    
    try:
        chat_service = ChatService(mock_db, mock_ml_service)
        
        # Test cost estimation for Gemma3 1B
        cost_info = chat_service.estimate_response_cost("Gemma3 1B")
        print(f"✓ Gemma3 1B cost: {cost_info}")
        assert cost_info["cost"] == 1
        assert cost_info["model_name"] == "Gemma3 1B"
        
        # Test cost estimation for Gemma3 12B
        cost_info = chat_service.estimate_response_cost("Gemma3 12B")
        print(f"✓ Gemma3 12B cost: {cost_info}")
        assert cost_info["cost"] == 3
        assert cost_info["model_name"] == "Gemma3 12B"
        
        return True
        
    except Exception as e:
        print(f"✗ Cost estimation test failed: {e}")
        return False


def test_chat_service_creation():
    """Test ChatService creation and basic functionality"""
    print("\n=== Testing ChatService Creation ===")
    
    try:
        # Create mock dependencies
        mock_db = Mock()
        mock_ml_service = Mock()
        mock_ml_service.models_loaded = True
        mock_ml_service.get_available_models.return_value = ["Gemma3 1B", "Gemma3 12B"]
        
        # Create ChatService
        chat_service = ChatService(mock_db, mock_ml_service)
        print("✓ ChatService created successfully")
        
        # Test that billing service is created
        assert hasattr(chat_service, 'billing_service')
        print("✓ BillingService integrated")
        
        # Test that ML service is stored
        assert chat_service.ml_service == mock_ml_service
        print("✓ MLService integrated")
        
        return True
        
    except Exception as e:
        print(f"✗ ChatService creation test failed: {e}")
        return False


def main():
    """Run all basic tests"""
    print("🧪 Testing ChatService Basic Functionality")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(test_chat_service_creation())
    results.append(test_message_validation())
    results.append(test_cost_estimation())
    
    # Summary
    print(f"\n📊 Test Results:")
    print(f"  Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All basic tests passed!")
        print("\n💡 ChatService is ready for integration!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    main()