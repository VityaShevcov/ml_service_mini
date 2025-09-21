"""
Test Gradio interface components
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ui.auth_interface import AuthInterface
from app.ui.chat_interface import ChatInterface
from app.ui.main_interface import MainInterface


def test_auth_interface():
    """Test authentication interface"""
    print("=== Testing AuthInterface ===")
    
    try:
        auth = AuthInterface()
        print(f"✓ AuthInterface created")
        print(f"  API URL: {auth.api_base_url}")
        
        # Test interface creation
        interface = auth.create_auth_interface()
        print(f"✓ Auth Gradio interface created")
        
        return True
    except Exception as e:
        print(f"✗ AuthInterface test failed: {e}")
        return False


def test_chat_interface():
    """Test chat interface"""
    print("\n=== Testing ChatInterface ===")
    
    try:
        chat = ChatInterface()
        print(f"✓ ChatInterface created")
        print(f"  API URL: {chat.api_base_url}")
        
        # Test getting available models
        models = chat.get_available_models()
        print(f"✓ Available models: {models}")
        
        # Test interface creation
        interface = chat.create_chat_interface()
        print(f"✓ Chat Gradio interface created")
        
        return True
    except Exception as e:
        print(f"✗ ChatInterface test failed: {e}")
        return False


def test_main_interface():
    """Test main interface"""
    print("\n=== Testing MainInterface ===")
    
    try:
        main = MainInterface()
        print(f"✓ MainInterface created")
        print(f"  API URL: {main.api_base_url}")
        
        # Test interface creation
        interface = main.create_main_interface()
        print(f"✓ Main Gradio interface created")
        
        return True
    except Exception as e:
        print(f"✗ MainInterface test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Testing Gradio Interface Components")
    print("=" * 50)
    
    results = []
    
    # Test components
    results.append(test_auth_interface())
    results.append(test_chat_interface())
    results.append(test_main_interface())
    
    # Summary
    print(f"\n📊 Test Results:")
    print(f"  Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All tests passed!")
        print("\n💡 To launch the interface:")
        print("   1. Start FastAPI server: python main.py")
        print("   2. Start Gradio interface: python gradio_app.py")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    main()