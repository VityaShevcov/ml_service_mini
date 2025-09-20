"""
Test all API endpoints
"""
import requests
import time
import json


def test_endpoints():
    """Test all available endpoints"""
    base_url = "http://127.0.0.1:7860"
    
    print("=== Testing API Endpoints ===")
    
    # Test health endpoints
    print("\n1. Testing health endpoints...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"Root endpoint: {response.status_code}")
        
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health endpoint: {response.status_code}")
    except Exception as e:
        print(f"Health endpoints failed: {e}")
    
    # Test ML endpoints
    print("\n2. Testing ML endpoints...")
    try:
        response = requests.get(f"{base_url}/ml/status", timeout=5)
        print(f"ML status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Models loaded: {data.get('models_loaded', False)}")
            print(f"  Device: {data.get('device', 'unknown')}")
        
        response = requests.get(f"{base_url}/ml/models", timeout=5)
        print(f"ML models: {response.status_code}")
    except Exception as e:
        print(f"ML endpoints failed: {e}")
    
    # Test chat endpoints (without auth)
    print("\n3. Testing chat endpoints...")
    try:
        response = requests.get(f"{base_url}/chat/models", timeout=5)
        print(f"Chat models: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Available models: {len(data.get('available_models', []))}")
    except Exception as e:
        print(f"Chat endpoints failed: {e}")
    
    # Test auth endpoints
    print("\n4. Testing auth endpoints...")
    try:
        # Test registration
        response = requests.post(f"{base_url}/auth/register", 
            json={
                "username": "testuser123",
                "email": "test123@example.com",
                "password": "TestPass123"
            },
            timeout=5
        )
        print(f"Auth register: {response.status_code}")
        
        if response.status_code == 200:
            # Test login
            response = requests.post(f"{base_url}/auth/login",
                json={
                    "username": "testuser123",
                    "password": "TestPass123"
                },
                timeout=5
            )
            print(f"Auth login: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data", {}).get("access_token"):
                    token = data["data"]["access_token"]
                    
                    # Test authenticated endpoints
                    headers = {"Authorization": f"Bearer {token}"}
                    
                    response = requests.get(f"{base_url}/auth/me", headers=headers, timeout=5)
                    print(f"Auth me: {response.status_code}")
                    
                    response = requests.get(f"{base_url}/billing/balance", headers=headers, timeout=5)
                    print(f"Billing balance: {response.status_code}")
                    
                    response = requests.get(f"{base_url}/chat/status", headers=headers, timeout=5)
                    print(f"Chat status: {response.status_code}")
    
    except Exception as e:
        print(f"Auth endpoints failed: {e}")
    
    print("\n=== Endpoint testing completed ===")


if __name__ == "__main__":
    print("Starting endpoint tests...")
    print("Make sure the server is running with: python main.py")
    print("Waiting 2 seconds for server...")
    time.sleep(2)
    
    test_endpoints()