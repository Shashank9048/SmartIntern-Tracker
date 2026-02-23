import requests
import time
import json

base_url = "http://localhost:8001"
# reuse user or create new
timestamp = int(time.time())
email = f"test_auto_{timestamp}@example.com"
password = "password123"

# Signup
print(f"Creating user: {email}")
signup_url = f"{base_url}/auth/signup"
resp = requests.post(signup_url, json={"email": email, "password": password, "full_name": "Auto User", "skills": ["Python"]})
if resp.status_code != 200:
    print(f"Signup failed: {resp.text}")
    exit(1)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Create Application with status Interview
print("Creating dummy application...")
app_data = {
    "user_email": email,
    "company": "TestCorp",
    "role": "SDE Intern",
    "status": "Interview",
    "match_score": 90,
    "next_action_date": "2024-12-25T10:00:00"
}
app_resp = requests.post(f"{base_url}/applications", json=app_data, headers=headers)
if app_resp.status_code != 200:
     print(f"Create App Failed: {app_resp.text}")
     exit(1)

print("\n--- Testing GET /applications/interviews ---")
try:
    interviews_resp = requests.get(f"{base_url}/applications/interviews", headers=headers, timeout=10)
    
    if interviews_resp.status_code == 200:
        data = interviews_resp.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if isinstance(data, list) and len(data) > 0 and data[0]["company"] == "TestCorp":
             print("✅ Success: Received interviews list")
        else:
             print("⚠️ Warning: List empty or mismatch")
    else:
        print(f"❌ Failed: {interviews_resp.status_code} - {interviews_resp.text}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
