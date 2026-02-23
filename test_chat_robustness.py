import requests
import time
import json

base_url = "http://localhost:8000"
# Login/Signup reuse tokens if possible, or create new
timestamp = int(time.time())
email = f"test_robust_{timestamp}@example.com"
password = "password123"

# Signup
print(f"Creating user: {email}")
signup_url = f"{base_url}/auth/signup"
resp = requests.post(signup_url, json={"email": email, "password": password, "full_name": "Test User", "skills": ["Python"]})
if resp.status_code != 200:
    print(f"Signup failed: {resp.text}")
    exit(1)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n--- Testing Chat Robustness ---")
messages = [
    "Hello, how are you?",
    "What is the best way to prepare for a Python interview?",
    "Tell me a joke about programming."
]

for i, msg in enumerate(messages):
    print(f"\nSending Message {i+1}: {msg}")
    start = time.time()
    try:
        chat_resp = requests.post(
            f"{base_url}/ai/chat", 
            json={"message": msg}, 
            headers=headers,
            timeout=60 # Long timeout for retries
        )
        duration = time.time() - start
        
        if chat_resp.status_code == 200:
            reply = chat_resp.json().get("reply")
            print(f"Response ({duration:.2f}s): {reply[:100]}...")
            if "Error:" in reply:
                 print("Received Error Message from Backend (Handled Gracefully)")
        else:
            print(f"Failed: {chat_resp.status_code} - {chat_resp.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
        
    # Rapid fire check (simulating burst if we removed sleep)
    # time.sleep(1) 
