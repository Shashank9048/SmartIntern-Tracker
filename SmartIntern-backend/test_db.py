
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
from dotenv import load_dotenv
load_dotenv("../.env")
from api.models import Job

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.smartintern, document_models=[Job])
    
    total_jobs = await Job.find_all().count()
    print("Total jobs in DB:", total_jobs)
    
    sources = await Job.distinct("source")
    print("Sources:", sources)

asyncio.run(main())

