
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import os
from dotenv import load_dotenv

load_dotenv("../.env")

from api.models import Job
from api.routes.jobs import arbeitnow_provider
from services.jobs_provider import _is_real_url
import re as _re

def _normalise_sig(title: str, company: str) -> str:
    combined = f"{title.lower().strip()} {company.lower().strip()}"
    return _re.sub(r"[^a-z0-9 ]", "", combined).strip()

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    await init_beanie(database=client.smartintern, document_models=[Job])
    
    combined_sigs = set()
    raw_jobs = await arbeitnow_provider.fetch_jobs(limit=150)
    print("Raw jobs fetched:", len(raw_jobs))
    
    valid_jobs = [j for j in raw_jobs if _is_real_url(j.application_url)]
    print("Valid URLs:", len(valid_jobs))
    
    deduped = []
    for j in valid_jobs:
        sig = _normalise_sig(j.title, j.company)
        if sig not in combined_sigs:
            deduped.append(j)
            combined_sigs.add(sig)
            
    print("Deduped:", len(deduped))

asyncio.run(main())

