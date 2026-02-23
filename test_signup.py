import requests
import json
import time

# Use a unique email every time by appending timestamp
timestamp = int(time.time())
unique_email = f"test_user_{timestamp}@example.com"

url = "http://localhost:8000/auth/signup"
payload = {
    "email": unique_email,
    "password": "securepassword123",
    "full_name": "Test Script User",
    "branch": "CSE",
    "graduation_year": "2024",
    "skills": ["Python", "React"]
}

print(f"Testing Signup with: {unique_email}")

try:
    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: User created!")
    else:
        print("❌ FAILED: Unexpected status code")

except Exception as e:
    print(f"❌ ERROR: {e}")
