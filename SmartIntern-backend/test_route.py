import requests

response = requests.post(
    "http://127.0.0.1:8000/api/tracked-jobs",
    json={"job_id": "test", "status": "applied"}
)
print("Status code:", response.status_code)
print("Response text:", response.text)
