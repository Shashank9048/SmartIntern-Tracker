import asyncio
import os
from dotenv import load_dotenv

# Find .env file in parent dir
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, "..", ".env")
load_dotenv(env_path)

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from api.routes.jobs import (
    sync_jobs,
    get_jobs,
    get_recommended_jobs
)
from api.models import Application, User, ResumeAnalysis, ChatHistory, Reminder, Automation, AutomationLog, Resume, Job, UserJobMatch, TrackedJob, Notification

async def create_dummy_user():
    user = await User.find_one(User.email == "test@example.com")
    if not user:
        user = User(
            email="test@example.com",
            password_hash="test",
            name="Test User",
            is_active=True,
            is_admin=True,
            skills=["Python", "React", "JavaScript"]
        )
        await user.insert()
    return user

async def run_tests():
    try:
        # Initialize DB
        client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
        await init_beanie(database=client["smart_intern_tracker"], document_models=[
            Application, User, ResumeAnalysis, ChatHistory, Reminder, Automation, AutomationLog, Resume, Job, UserJobMatch, TrackedJob, Notification
        ])
        
        await create_dummy_user()
        print("Testing POST /jobs/sync")
        sync_result = await sync_jobs(current_user="test@example.com")
        print("Sync result:")
        providers = sync_result.get("providers", {})
        for name, data in providers.items():
            print(f"{name}: {data}")
            
        print("\nTesting GET /jobs")
        jobs = await get_jobs(query="software intern", location="India", limit=5, current_user="test@example.com")
        print(f"GET /jobs returned {len(jobs)} jobs")
        for j in jobs:
            print(f" - {j.title} at {j.company} (Source: {j.source}, URL: {j.application_url})")

        print("\nTesting GET /jobs/recommended")
        rec_jobs = await get_recommended_jobs(min_score=0, limit=5, current_user="test@example.com")
        print(f"GET /jobs/recommended returned {len(rec_jobs)} jobs")
        for r in rec_jobs:
            j = r["job"]
            print(f" - [Score {r['match_score']}] {j['title']} at {j['company']} (Source: {j['source']}, URL: {j['apply_url']})")

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_tests())
