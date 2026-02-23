import requests
import time

BASE_URL = "http://localhost:8001"
EMAIL = f"test_user_{int(time.time())}@example.com"
PASSWORD = "password123"
NEW_PASSWORD = "newpassword456"

def test_personalization():
    print(f"Testing Personalization for {EMAIL}...")
    
    # 1. Signup
    print("\n1. Signup...")
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": EMAIL,
        "password": PASSWORD,
        "full_name": "Test User"
    })
    if resp.status_code != 200:
        print(f"Signup Failed: {resp.text}")
        return
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Signup Successful")
    
    # 2. Get Profile
    print("\n2. Get Profile...")
    resp = requests.get(f"{BASE_URL}/user/me", headers=headers)
    if resp.status_code != 200:
        print(f"Get Profile Failed: {resp.text}")
        return
    profile = resp.json()
    print(f"Profile: {profile['full_name']} ({profile['email']})")
    assert profile["full_name"] == "Test User"
    
    # 3. Update Profile
    print("\n3. Update Profile...")
    resp = requests.patch(f"{BASE_URL}/user/me", headers=headers, json={
        "full_name": "Updated Name",
        "preferences": {"theme": "dark"}
    })
    if resp.status_code != 200:
        print(f"Update Profile Failed: {resp.text}")
        return
    updated_profile = resp.json()
    print(f"Updated Profile: {updated_profile['full_name']}, Theme: {updated_profile['preferences']['theme']}")
    assert updated_profile["full_name"] == "Updated Name"
    assert updated_profile["preferences"]["theme"] == "dark"
    
    # 4. Change Password
    print("\n4. Change Password...")
    resp = requests.post(f"{BASE_URL}/user/change-password", headers=headers, json={
        "current_password": PASSWORD,
        "new_password": NEW_PASSWORD
    })
    if resp.status_code != 200:
        print(f"Change Password Failed: {resp.text}")
        return
    print("Password Changed")
    
    # 5. Login with New Password
    print("\n5. Login with New Password...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": EMAIL,
        "password": NEW_PASSWORD
    })
    if resp.status_code != 200:
        print(f"Login Failed: {resp.text}")
        return
    new_token = resp.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    print("Login Successful")
    
    # 6. Dashboard Stats (Empty)
    print("\n6. Dashboard Stats (Empty)...")
    resp = requests.get(f"{BASE_URL}/dashboard/stats", headers=new_headers)
    if resp.status_code != 200:
        print(f"Stats Failed: {resp.text}")
        return
    stats = resp.json()
    print(f"Stats: {stats}")
    assert stats["total"] == 0
    
    # 7. Add Application and Check Stats
    print("\n7. Add Application and Check Stats...")
    app_data = {
        "user_email": EMAIL,
        "company": "Test Corp",
        "role": "Intern",
        "status": "Interview"
    }
    requests.post(f"{BASE_URL}/applications", headers=new_headers, json=app_data)
    
    resp = requests.get(f"{BASE_URL}/dashboard/stats", headers=new_headers)
    stats = resp.json()
    print(f"Stats after add: {stats}")
    assert stats["total"] == 1
    assert stats["interviews"] == 1
    
    print("\nAll Personalization Tests Passed! ✅")

if __name__ == "__main__":
    try:
        test_personalization()
    except Exception as e:
        print(f"Test Crashed: {e}")
