import requests
import json
import time

# Use a unique email
timestamp = int(time.time())
unique_email = f"frontend_test_{timestamp}@example.com"

# Exact payload from app/signup/page.tsx
payload = {
    "email": unique_email,
    "password": "password123",
    "full_name": "Frontend Test User",
    "branch": "cse",
    "graduation_year": "2026",
    "skills": ["React", "Node.js"]
}

url = "http://localhost:8000/auth/signup"

print(f"Testing signup with payload: {json.dumps(payload, indent=2)}")

try:
    # 1. Signup
    response = requests.post(url, json=payload)
    print(f"Signup Status: {response.status_code}")
    print(f"Signup Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        
        # 2. Get Profile (to simulate refreshUser)
        profile_url = "http://localhost:8000/user/me"
        headers = {"Authorization": f"Bearer {token}"}
        profile_res = requests.get(profile_url, headers=headers)
        print(f"Profile Status: {profile_res.status_code}")
        print(f"Profile Response: {profile_res.text}")
        
    else:
        print("❌ Signup failed")

except Exception as e:
    print(f"❌ Error: {e}")
