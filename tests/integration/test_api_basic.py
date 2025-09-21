"""
Basic test for API functionality
"""
import requests
import time
import subprocess
import sys
from threading import Thread


def start_server():
    """Start the FastAPI server"""
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        pass


def test_api_endpoints():
    """Test basic API endpoints"""
    base_url = "http://127.0.0.1:7860"
    
    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(3)
    
    try:
        # Test health endpoint
        print("Testing health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health check: {response.status_code} - {response.json()}")
        
        # Test ML status endpoint
        print("Testing ML status endpoint...")
        response = requests.get(f"{base_url}/ml/status", timeout=5)
        print(f"ML status: {response.status_code} - {response.json()}")
        
        # Test available models endpoint
        print("Testing available models endpoint...")
        response = requests.get(f"{base_url}/ml/models", timeout=5)
        print(f"Available models: {response.status_code} - {response.json()}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"API test failed: {e}")
        return False


def main():
    """Run API tests"""
    print("=== API Basic Tests ===")
    
    # Start server in background thread
    server_thread = Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Test API endpoints
    success = test_api_endpoints()
    
    if success:
        print("\n🎉 Basic API tests passed!")
    else:
        print("\n❌ API tests failed!")
    
    return success


if __name__ == "__main__":
    main()