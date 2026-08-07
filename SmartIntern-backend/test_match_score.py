import asyncio
import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, "..", ".env")
load_dotenv(env_path)

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from api.models import User, Job, TrackedJob, UserJobMatch
from api.auth import create_access_token
import httpx

async def run():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    await init_beanie(database=client["smart_intern_tracker"], document_models=[User, Job, TrackedJob, UserJobMatch])
    
    user = await User.find_one(User.email == "test@example.com")
    token = create_access_token(data={"sub": user.email})
    
    # get a job to test with
    job = await Job.find_one()
    
    print(f"Testing with job_id: {job.id}")
    
    # Delete any existing match or tracked job
    await UserJobMatch.find(UserJobMatch.user_id == user.email).delete()
    await TrackedJob.find(TrackedJob.user_id == user.email).delete()

    # Create a dummy match with score 82
    match = UserJobMatch(
        user_id=user.email,
        job_id=str(job.id),
        match_score=82,
        resume_version="test"
    )
    await match.insert()
    print("Created UserJobMatch with score 82")
    
    async with httpx.AsyncClient() as hc:
        res = await hc.post(
            "http://127.0.0.1:8000/api/tracked-jobs",
            json={"job_id": str(job.id), "status": "applied"},
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Status code:", res.status_code)
        print("Response:", res.text)

if __name__ == "__main__":
    asyncio.run(run())
