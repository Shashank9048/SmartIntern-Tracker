import requests
import json
import time

# 1. Setup
base_url = "http://localhost:8000"
timestamp = int(time.time())
email = f"test_resume_{timestamp}@example.com"
password = "password123"

# 2. Signup
print(f"Creating user: {email}")
signup_url = f"{base_url}/auth/signup"
signup_payload = {
    "email": email,
    "password": password,
    "full_name": "Test User",
    "skills": ["Python", "Full Stack"]
}
resp = requests.post(signup_url, json=signup_payload)
if resp.status_code != 200:
    print(f"❌ Signup Failed: {resp.text}")
    exit(1)
    
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ Signup Successful")

# 3. Analyze Resume (Direct Text)
print("Testing Direct Resume Analysis...")
analyze_url = f"{base_url}/ai/analyze"
analyze_payload = {
    "resume_text": "John Doe. Python Developer. Skills: Django, FastAPI, React.",
    "job_description": "We need a Python developer who knows Django and React."
}

try:
    resp = requests.post(analyze_url, json=analyze_payload, headers=headers)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print("✅ Analysis Successful!")
        print(f"Match Score: {data.get('match_score')}")
        print(f"Match Label: {data.get('match_label')}")
        print(f"Skills Found: {data.get('skills_found')}")
        
        # Verify structure
        if "improvement_priority" in data and isinstance(data["improvement_priority"], list):
             print("✅ Improvement Priority structure valid")
        else:
             print("❌ Improvement Priority missing or invalid")
             print(data.keys())

    else:
        print(f"❌ Analysis Failed: {resp.text}")

except Exception as e:
    print(f"❌ Error: {e}")
