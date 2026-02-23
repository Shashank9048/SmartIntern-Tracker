import requests
import json

url = "http://localhost:8000/auth/signup"
payload = {
    "email": "shashanksingh9048@gmail.com",
    "password": "Arise",
    "full_name": "Shashank Singh",
    "branch": "cse", 
    "graduation_year": "2027",
    "skills": ["Python", "React"]
}

print(f"Creating User: {payload['email']}")

try:
    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: User Shashank Singh created!")
    elif response.status_code == 400 and "already registered" in response.text:
       print("ℹ️ NOTE: User already exists.")
    else:
        print("❌ FAILED: Unexpected status code")

except Exception as e:
    print(f"❌ ERROR: {e}")
