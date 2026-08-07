
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
from dotenv import load_dotenv

load_dotenv("../.env")

from api.models import Job, User, Application, UserJobMatch, Notification, Automation, TrackedJob, Resume
from services.scheduler import NotificationScheduler
import logging
logging.basicConfig(level=logging.INFO)

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.smartintern, document_models=[Job, User, Application, UserJobMatch, Notification, Automation, TrackedJob, Resume])
    
    scheduler = NotificationScheduler()
    await scheduler.run_jobs_sync()

asyncio.run(main())

