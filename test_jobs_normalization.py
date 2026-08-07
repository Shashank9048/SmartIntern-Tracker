import sys
import os

# Add SmartIntern-backend to sys.path
sys.path.append(os.path.join(os.getcwd(), "SmartIntern-backend"))

from api.routes.jobs import normalize_job_item

def test_normalization():
    print("--- Testing normalize_job_item ---")
    
    # 1. JSearch style with job_apply_link
    raw_jsearch = {
        "job_title": "Software Engineer Intern",
        "employer_name": "Google",
        "job_country": "India",
        "job_apply_link": "https://careers.google.com/jobs/123"
    }
    norm1 = normalize_job_item(raw_jsearch, "JSearch")
    print("Test 1 (JSearch primary link):", norm1)
    assert norm1["apply_url"] == "https://careers.google.com/jobs/123"
    
    # 2. Remotive style with url
    raw_remotive = {
        "title": "Backend Developer",
        "company_name": "Stripe",
        "candidate_required_location": "Remote",
        "url": "https://remotive.com/job/456"
    }
    norm2 = normalize_job_item(raw_remotive, "Remotive")
    print("Test 2 (Remotive url):", norm2)
    assert norm2["apply_url"] == "https://remotive.com/job/456"

    # 3. JSearch fallback apply_options
    raw_apply_options = {
        "job_title": "Frontend Engineer",
        "employer_name": "Meta",
        "apply_options": [{"apply_link": "https://meta.com/careers/789"}]
    }
    norm3 = normalize_job_item(raw_apply_options, "JSearch")
    print("Test 3 (apply_options deeplink):", norm3)
    assert norm3["apply_url"] == "https://meta.com/careers/789"

    # 4. Fallback Google Search
    raw_missing = {
        "title": "Fullstack Intern",
        "company_name": "Acme Corp"
    }
    norm4 = normalize_job_item(raw_missing, "Unknown")
    print("Test 4 (Google fallback):", norm4)
    assert "google.com/search?q=Acme+Corp+Fullstack+Intern+careers+apply" in norm4["apply_url"]

    print("\nALL FUNCTIONAL NORMALIZATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_normalization()
