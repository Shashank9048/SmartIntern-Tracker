import asyncio
import os
import sys

# Set a dummy secret key to avoid RuntimeError from auth.py
os.environ["SECRET_KEY"] = "dummysecretkeyforlocaltestingonlysoauthdoesnotcrash"

from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "SmartIntern-backend")))
load_dotenv(os.path.join(os.path.dirname(__file__), "SmartIntern-backend", ".env"))

from services.jobs_provider import JoobleProvider, AdzunaProvider, _is_direct_employer_url

async def main():
    print("Testing AdzunaProvider...")
    adzuna = AdzunaProvider()
    if not adzuna.app_id:
        print("Missing ADZUNA credentials")
    else:
        adz_jobs = await adzuna.fetch_jobs(query="software intern", location="India", limit=5)
        print(f"Adzuna returned {len(adz_jobs)} jobs.")
        for j in adz_jobs:
            print(f"- {j.title} at {j.company} | Loc: {j.location} | Remote: {j.work_mode}")
            print(f"  URL: {j.application_url}")

    print("\nTesting JoobleProvider...")
    jooble = JoobleProvider()
    if not jooble.api_key:
        print("Missing JOOBLE credentials")
    else:
        joo_jobs = await jooble.fetch_jobs(query="software intern", location="India", limit=5)
        print(f"Jooble returned {len(joo_jobs)} jobs.")
        for j in joo_jobs:
            print(f"- {j.title} at {j.company} | Loc: {j.location} | Remote: {j.work_mode}")
            print(f"  URL: {j.application_url}")

if __name__ == "__main__":
    asyncio.run(main())
