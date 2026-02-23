import requests
import json
import time

# 1. Setup
base_url = "http://localhost:8000"
timestamp = int(time.time())
email = f"test_parser_{timestamp}@example.com"
password = "password123"

# 2. Signup
print(f"Creating user: {email}")
signup_url = f"{base_url}/auth/signup"
signup_payload = {
    "email": email,
    "password": password,
    "full_name": "Test User",
    "skills": ["Python"]
}
resp = requests.post(signup_url, json=signup_payload)
if resp.status_code != 200:
    print(f"❌ Signup Failed: {resp.text}")
    exit(1)
    
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ Signup Successful")

# 3. Parse Resume
print("Testing Resume Parsing...")
parse_url = f"{base_url}/ai/parse_resume"
resume_text = """
John Doe
Email: john.doe@example.com
Phone: 123-456-7890
LinkedIn: linkedin.com/in/johndoe

Experience:
Software Engineer at Tech Corp (2020-Present)
- Built web apps using React and Python.
- Managed database migrations.

Education:
B.S. in Computer Science, University of Examples (2016-2020)

Skills: Python, JavaScript, React, SQL
"""

parse_payload = {
    "resume_text": resume_text
}

try:
    resp = requests.post(parse_url, json=parse_payload, headers=headers)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print("✅ Parsing Successful!")
        print(json.dumps(data, indent=2))
        
        # Validation
        if data.get("name") == "John Doe" and "Python" in data.get("skills", []):
             print("✅ Data validation passed")
        else:
             print("❌ Data validation failed")

    else:
        print(f"❌ Parsing Failed: {resp.text}")

except Exception as e:
    print(f"❌ Error: {e}")
