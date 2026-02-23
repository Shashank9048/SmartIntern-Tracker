import requests
import json

base_url = "http://localhost:8001"

print("--- Checking /ping ---")
try:
    resp = requests.get(f"{base_url}/ping", timeout=5)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text}")
except Exception as e:
    print(f"Ping Failed: {e}")

print("\n--- Checking /ai/interview-tips ---")
try:
    # Need auth? Yes, Depends(get_current_user)
    # Login first
    login_resp = requests.post(f"{base_url}/auth/login", json={"email": "test_tips_1771521585@example.com", "password": "password123"})
    if login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        tips_resp = requests.post(f"{base_url}/ai/interview-tips", json={"position": "Developer"}, headers=headers, timeout=10)
        print(f"Status: {tips_resp.status_code}")
        print(f"Body: {tips_resp.text[:200]}...")
    else:
        print(f"Login failed for existing user: {login_resp.status_code}")
        # Try creating new user if needed, but reusing previous email from step 923 output
        
except Exception as e:
    print(f"Tips Failed: {e}")
