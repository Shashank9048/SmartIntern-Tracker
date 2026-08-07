import requests

res = requests.post("http://127.0.0.1:8000/api/tracked-jobs")
print("Response for /api/tracked-jobs:", res.status_code)

res = requests.post("http://127.0.0.1:8000/tracked-jobs")
print("Response for /tracked-jobs:", res.status_code)
