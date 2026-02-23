import requests
try:
    resp = requests.get("http://localhost:8000/", timeout=5)
    print(f"Backend Status: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Backend Check Failed: {e}")
