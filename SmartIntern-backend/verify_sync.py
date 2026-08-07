import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api.models import Job
from api.routes.jobs import sync_jobs
from dotenv import load_dotenv

async def main():
    load_dotenv()
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017/smartintern")
    print(f"Connecting to MongoDB at {mongo_url}...")
    client = AsyncIOMotorClient(mongo_url)
    await init_beanie(database=client.smartintern, document_models=[Job])
    
    print("Running sync_jobs()...")
    result = await sync_jobs(current_user="admin")
    print("\nSync Result:")
    print(result)

    print("\nQuerying jobs by source...")
    adzuna_count = await Job.find(Job.source == "adzuna").count()
    remotive_count = await Job.find(Job.source == "remotive").count()
    jsearch_count = await Job.find(Job.source == "jsearch").count()
    mock_count = await Job.find(Job.source == "mock").count()
    
    print(f"Adzuna: {adzuna_count}")
    print(f"Remotive: {remotive_count}")
    print(f"JSearch: {jsearch_count}")
    print(f"Mock: {mock_count}")

if __name__ == "__main__":
    asyncio.run(main())
