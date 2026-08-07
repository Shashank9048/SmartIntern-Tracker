
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv("../.env")

from api.models import Job, User, Application, UserJobMatch, Notification, Automation, TrackedJob, Resume
from api.routes.jobs import get_recommended_jobs

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.smartintern, document_models=[Job, User, Application, UserJobMatch, Notification, Automation, TrackedJob, Resume])
    
    u = User(email="test@example.com", auth0_id="test", full_name="Test", password_hash="hash", created_at=datetime.now(), updated_at=datetime.now())
    r = Resume(user_id="test@example.com", raw_text="test", resume_version="v1", created_at=datetime.now(), updated_at=datetime.now())
    await u.insert()
    await r.insert()

    rec_jobs = await get_recommended_jobs(min_score=0, limit=200, current_user="test@example.com")
    print("Recommended jobs count:", len(rec_jobs))
    
    arbeitnow = [j for j in rec_jobs if j.get("job", {}).get("source") == "arbeitnow"]
    print("Recommended Arbeitnow jobs:", len(arbeitnow))
    
    await u.delete()
    await r.delete()

asyncio.run(main())

