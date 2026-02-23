import requests
import time
import json

base_url = "http://localhost:8001"
# reusing previous logic for token if needed, but let's just make a new user to be safe or use existing
timestamp = int(time.time())
email = f"test_tips_{timestamp}@example.com"
password = "password123"

# Signup
print(f"Creating user: {email}")
signup_url = f"{base_url}/auth/signup"
resp = requests.post(signup_url, json={"email": email, "password": password, "full_name": "Tips User", "skills": ["Java"]})
if resp.status_code != 200:
    print(f"Signup failed: {resp.text}")
    exit(1)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n--- Testing Interview Tips ---")
position = "Software Engineer"
print(f"Requesting tips for: {position}")

start = time.time()
try:
    tips_resp = requests.post(
        f"{base_url}/ai/interview-tips", 
        json={"position": position}, 
        headers=headers,
        timeout=60
    )
    duration = time.time() - start
    
    if tips_resp.status_code == 200:
        data = tips_resp.json()
        print(f"Response ({duration:.2f}s):")
        print(json.dumps(data, indent=2))
        
        if "tips" in data and isinstance(data["tips"], list) and len(data["tips"]) > 0:
             print("✅ Success: Received interview tips")
        else:
             print("⚠️ Warning: Response structure unexpected")
    else:
        print(f"❌ Failed: {tips_resp.status_code} - {tips_resp.text}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
