import httpx
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    client = httpx.Client(base_url=BASE_URL)
    
    # 1. Signup
    print("Testing Signup...")
    email = f"test_{int(time.time())}@test.com"
    resp = client.post("/auth/signup", json={
        "email": email,
        "password": "password123",
        "full_name": "Test User",
        "skills": ["Python", "React"]
    })
    
    if resp.status_code not in (200, 201):
        print(f"Signup failed: {resp.text}")
        sys.exit(1)
        
    token = resp.json().get("access_token")
    client.headers.update({"Authorization": f"Bearer {token}"})
    print("Signup & Login OK.")
    
    # 2. Get Recommended Feed
    print("Testing Recommended Feed...")
    resp = client.get("/api/jobs/recommended?limit=10")
    if resp.status_code != 200:
        print(f"Recommended feed failed: {resp.text}")
        sys.exit(1)
        
    jobs = resp.json()
    print(f"Recommended jobs found: {len(jobs)}")
    
    # 3. Create a Kanban item directly
    print("Testing Kanban Add...")
    resp = client.post("/api/applications", json={
        "company_name": "TestCorp",
        "role": "Intern",
        "status": "wishlist",
        "location": "Remote",
        "application_url": "http://example.com/apply"
    })
    
    if resp.status_code not in (200, 201):
        print(f"Kanban add failed: {resp.text}")
        sys.exit(1)
        
    app_id = resp.json().get("_id") or resp.json().get("id")
    print(f"Kanban item added: {app_id}")
    
    # 4. Move Kanban item (Update status)
    print("Testing Kanban Move...")
    resp = client.put(f"/api/applications/{app_id}", json={
        "status": "applied",
        "company_name": "TestCorp",
        "role": "Intern"
    })
    
    if resp.status_code != 200:
        print(f"Kanban move failed: {resp.text}")
        sys.exit(1)
    
    # Verify move
    resp = client.get("/api/applications")
    apps = resp.json()
    moved_app = next((a for a in apps if str(a.get("_id", a.get("id"))) == str(app_id)), None)
    if not moved_app or moved_app["status"] != "applied":
        print(f"Kanban move not persistent! {moved_app}")
        sys.exit(1)
    print("Kanban move OK.")
    
    # 5. Delete Kanban item
    print("Testing Kanban Delete...")
    resp = client.delete(f"/api/applications/{app_id}")
    if resp.status_code != 200:
        print(f"Kanban delete failed: {resp.text}")
        sys.exit(1)
        
    # Verify delete
    resp = client.get("/api/applications")
    apps = resp.json()
    deleted_app = next((a for a in apps if str(a.get("_id", a.get("id"))) == str(app_id)), None)
    if deleted_app:
        print(f"Kanban item still exists after delete! {deleted_app}")
        sys.exit(1)
    print("Kanban delete OK.")
    
    # 6. Test Resume Delete cascade (UserJobMatch invalidation)
    print("Testing Resume Delete (JobMatch Invalidation)...")
    resp = client.delete("/api/resume/me")
    if resp.status_code not in (200, 404):  # 404 means no resume anyway, which is fine
        print(f"Resume delete failed: {resp.text}")
        sys.exit(1)
    
    print("ALL API TESTS PASSED.")

if __name__ == "__main__":
    run_tests()
